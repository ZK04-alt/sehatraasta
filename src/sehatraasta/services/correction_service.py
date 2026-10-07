"""Local corrections with revision checks and transaction-owned file staging."""
from contextlib import contextmanager
from datetime import date, datetime
import hashlib
import os
from pathlib import Path
import sqlite3

from sehatraasta.domain import Patient, Language, AttachmentCategory
from sehatraasta.domain.medical_dates import validate_medical_date
from sehatraasta.storage.db import connect_database
from sehatraasta.storage.errors import StorageError, log_storage_error
from .attachment_inspection import generate_attachment_stored_name
from .attachment_validation import validate_attachment_filename
from .file_service import FileService, read_source

# Fixed table/field names. Submitted values never select SQL identifiers.
RECORDS = {
    'medication': ('medication_items','medication_id', {'name':'verbatim_name','strength':'strength','dose':'dose_text','route':'route_text','frequency':'frequency_text','duration':'duration_text','instructions':'instructions','source':'source'}),
    'order': ('investigation_orders','order_id', {'name':'test_name','date':'order_date','source':'ordering_source','workflow_status':'workflow_status'}),
    'result': ('diagnostic_results','result_id', {'name':'test_name','date':'result_date','source':'source_summary','interpretation':'interpretation_note'}),
    'imaging': ('imaging_items','imaging_id', {'modality':'modality','body_part':'body_part','date':'date','facility':'facility','report':'report','attachment_id':'attachment_id'}),
    'instruction': ('instructions','instruction_id', {'category':'category','language':'language','text':'verbatim_text','source':'author_source','date':'date'}),
    'cost': ('cost_entries','cost_entry_id', {'category':'category','amount':'amount_paisa','date':'date','source':'source','source_type':'source_type','source_identifier':'source_identifier','note':'note'}),
    'encounter': ('encounters','encounter_id', {'date':'date','facility':'facility','clinician_display_text':'clinician_display_text','source_note':'source_note'}),
}


def record_links(connection, kind, identifier):
    links = []
    if kind == 'order':
        for row in connection.execute('SELECT result_id FROM diagnostic_results WHERE investigation_order_id=?', (identifier,)):
            links.append({'table':'diagnostic_results','key':'result_id','id':row[0], 'column':'investigation_order_id','before':identifier,'after':None})
    managed = {'order':'order_id','result':'result_id','imaging':'imaging_id','instruction':'instruction_id'}.get(kind)
    if managed:
        for row in connection.execute('SELECT attachment_id FROM managed_attachments WHERE '+managed+'=?', (identifier,)):
            links.append({'table':'managed_attachments','key':'attachment_id','id':row[0], 'column':managed,'before':identifier,'after':None})
    return links


class CorrectionService:
    def __init__(self, database):
        self.database = Path(database)

    @contextmanager
    def transaction(self):
        connection = connect_database(self.database)
        try:
            with connection:
                connection.execute('BEGIN IMMEDIATE')
                yield connection
                if connection.execute('PRAGMA foreign_key_check').fetchone():
                    raise ValueError('correction would break record relationships')
        except (OSError, sqlite3.Error) as error:
            log_storage_error(self.database, 'correction', error)
            raise StorageError('correction could not be saved; previous records remain') from None
        finally:
            connection.close()

    @staticmethod
    def owner(connection, visit_id, revision):
        row = connection.execute('SELECT p.* FROM patients p JOIN referral_bundles b USING(patient_id) WHERE b.bundle_id=?', (visit_id,)).fetchone()
        if row is None:
            raise ValueError('visit not found')
        if row['revision'] != revision:
            raise ValueError('records changed; reopen before saving')
        return row['patient_id']

    @staticmethod
    def touch(connection, *patient_ids):
        # Cross-patient moves must not make a source revision valid on a less
        # edited destination. Advance both beyond every involved revision.
        revision = max(connection.execute('SELECT revision FROM patients WHERE patient_id=?', (identifier,)).fetchone()[0]
            for identifier in set(patient_ids)) + 1
        for patient_id in set(patient_ids):
            connection.execute('UPDATE patients SET revision=? WHERE patient_id=?', (revision, patient_id))
            from sehatraasta.storage.sqlite_repository import SQLiteRepository
            from sehatraasta.storage.repositories import _patient_from_dict
            patient = connection.execute('SELECT * FROM patients WHERE patient_id=?', (patient_id,)).fetchone()
            _patient_from_dict({'ID':patient_id, 'name':patient['display_name'], 'birth_year':patient['birth_year'],
                'language':patient['language'], 'referral_bundles':[SQLiteRepository._read_bundle(connection, row)
                    for row in connection.execute('SELECT * FROM referral_bundles WHERE patient_id=?', (patient_id,))]})

    def patient(self, patient_id, revision, name, birth_year, language):
        Patient(patient_id, name, birth_year, Language[language])
        with self.transaction() as connection:
            updated = connection.execute('UPDATE patients SET display_name=?, birth_year=?, language=?, revision=revision+1 WHERE patient_id=? AND revision=?',
                (name, birth_year, language, patient_id, revision))
            if updated.rowcount != 1:
                raise ValueError('patient changed; reopen before saving')

    def visit(self, visit_id, revision, *, patient_id, facility, destination, date_kind, date_value):
        kind, value = validate_medical_date(date_kind, date_value)
        if not isinstance(facility, str) or not isinstance(destination, str):
            raise ValueError('invalid visit details')
        with self.transaction() as connection:
            previous = self.owner(connection, visit_id, revision)
            if connection.execute('SELECT 1 FROM patients WHERE patient_id=?', (patient_id,)).fetchone() is None:
                raise ValueError('destination patient not found')
            connection.execute('UPDATE referral_bundles SET patient_id=?, source_facility=?, destination=?, medical_date_kind=?, medical_date_value=? WHERE bundle_id=?',
                (patient_id, facility, destination, kind, value, visit_id))
            connection.execute('UPDATE removed_items SET parent_patient=? WHERE parent_visit=?', (patient_id, visit_id))
            self.touch(connection, previous, patient_id)

    def record(self, kind, identifier, revision, values, destination_visit, unlink=False):
        if kind not in RECORDS:
            raise ValueError('invalid record kind')
        from enum import Enum
        from sehatraasta.storage.sqlite_repository import amount_to_paisa
        table, key, fields = RECORDS[kind]
        with self.transaction() as connection:
            row = connection.execute('SELECT * FROM '+table+' WHERE '+key+'=?', (identifier,)).fetchone()
            if row is None:
                raise ValueError('record not found')
            previous = self.owner(connection, row['bundle_id'], revision)
            target = connection.execute('SELECT patient_id FROM referral_bundles WHERE bundle_id=?', (destination_visit,)).fetchone()
            if target is None:
                raise ValueError('destination visit not found')
            changes = {}
            for name, value in values.items():
                if name not in fields and not (kind=='result' and name=='order_name'):
                    raise ValueError('invalid record field')
                if name == 'order_name':
                    order = connection.execute('SELECT order_id FROM investigation_orders WHERE bundle_id=? AND test_name=?', (destination_visit, value)).fetchall() if value else []
                    if value and len(order) != 1:
                        raise ValueError('linked test is ambiguous or missing')
                    changes['investigation_order_id'] = order[0][0] if order else None
                else:
                    changes[fields[name]] = amount_to_paisa(value) if name=='amount' else value.name if isinstance(value,Enum) else value.isoformat() if isinstance(value,date) else value
            if destination_visit != row['bundle_id']:
                links = record_links(connection,kind,identifier)
                own_link = {'result':'investigation_order_id','imaging':'attachment_id'}.get(kind)
                if (links or (own_link and row[own_link])) and not unlink:
                    raise ValueError('linked record: move the whole visit or explicitly unlink before moving')
                if unlink:
                    for link in links:
                        connection.execute('UPDATE '+link['table']+' SET '+link['column']+'=NULL WHERE '+link['key']+'=?',(link['id'],))
                    if own_link:
                        changes[own_link] = None
            changes['bundle_id'] = destination_visit
            connection.execute('UPDATE '+table+' SET '+','.join(column+'=?' for column in changes)+' WHERE '+key+'=?', (*changes.values(),identifier))
            self.touch(connection, previous, target['patient_id'])

    def document(self, attachment_id, revision, *, name, category, document_date, destination_visit, unlink=False, provenance=None):
        category = AttachmentCategory(category).value
        extension = validate_attachment_filename(name)
        if document_date is not None and (not isinstance(document_date, date) or isinstance(document_date, datetime)):
            raise ValueError('invalid document date')
        with self.transaction() as connection:
            row = connection.execute('SELECT * FROM managed_attachments WHERE attachment_id=?', (attachment_id,)).fetchone()
            if row is None:
                raise ValueError('document not found')
            previous = self.owner(connection, row['bundle_id'], revision)
            destination = connection.execute('SELECT patient_id FROM referral_bundles WHERE bundle_id=?', (destination_visit,)).fetchone()
            if destination is None:
                raise ValueError('destination visit not found')
            if extension != Path(row['stored_name']).suffix:
                raise ValueError('keep the document filename extension; use Replace to change file type')
            linked = any(row[key] for key in ('order_id', 'result_id', 'imaging_id', 'instruction_id', 'medication_list'))
            imaging = connection.execute('SELECT 1 FROM imaging_items WHERE attachment_id=?', (attachment_id,)).fetchone()
            if destination_visit != row['bundle_id'] and (linked or imaging) and not unlink:
                raise ValueError('linked document: move the whole visit or explicitly unlink before moving')
            if unlink:
                connection.execute('UPDATE managed_attachments SET order_id=NULL, result_id=NULL, imaging_id=NULL, instruction_id=NULL, medication_list=0 WHERE attachment_id=?', (attachment_id,))
                connection.execute('UPDATE imaging_items SET attachment_id=NULL WHERE attachment_id=?', (attachment_id,))
            connection.execute('UPDATE attachments SET bundle_id=?, original_display_name=?, category=?, date=? WHERE attachment_id=?',
                (destination_visit, name, category, document_date.isoformat() if document_date else None, attachment_id))
            connection.execute('UPDATE managed_attachments SET bundle_id=?, category=? WHERE attachment_id=?', (destination_visit, category, attachment_id))
            if provenance is not None:
                from sehatraasta.domain import Provenance
                if not isinstance(provenance,Provenance):
                    raise ValueError('invalid document source')
                provenance.__post_init__()
                connection.execute('UPDATE attachments SET source=? WHERE attachment_id=?',(provenance.source or 'source not supplied',attachment_id))
                connection.execute('UPDATE managed_attachments SET source_type=?,source_identifier=? WHERE attachment_id=?',
                    (provenance.source_type.value,provenance.source_identifier,attachment_id))
            self.touch(connection, previous, destination['patient_id'])

    def replace(self, attachment_id, revision, source_path, original_name=None):
        content, extension, mime = read_source(source_path)
        name = original_name or Path(source_path).name
        if validate_attachment_filename(name) != extension:
            raise ValueError('replacement filename does not match its type')
        digest = hashlib.sha256(content).hexdigest()
        files = FileService(self.database)
        staged = files._path(generate_attachment_stored_name(extension))
        old = None
        committed = False
        try:
            with self.transaction() as connection:
                row = connection.execute('SELECT * FROM managed_attachments WHERE attachment_id=?', (attachment_id,)).fetchone()
                if row is None:
                    raise ValueError('document not found')
                patient_id = self.owner(connection, row['bundle_id'], revision)
                files.check_duplicate(connection,digest,attachment_id)
                old = files._path(row['stored_name'])
                if digest == row['sha256']:
                    connection.execute('UPDATE attachments SET original_display_name=? WHERE attachment_id=?', (name, attachment_id))
                    self.touch(connection, patient_id)
                    return
                from .recovery_service import RecoveryService
                import secrets
                from .identifiers import ALPHABET
                previous = dict(connection.execute('SELECT * FROM attachments WHERE attachment_id=?', (attachment_id,)).fetchone())
                retained = dict(row)
                retained_id = 'AT-' + ''.join(secrets.choice(ALPHABET) for _ in range(6))
                previous['attachment_id'] = retained['attachment_id'] = retained_id
                for key in ('order_id', 'result_id', 'imaging_id', 'instruction_id'):
                    retained[key] = None
                retained['medication_list'] = 0
                RecoveryService.retain(connection, 'replacement', previous['original_display_name'], patient_id,
                    row['bundle_id'], {'attachments':[previous], 'managed_attachments':[retained]})
                files.root.mkdir(parents=True, exist_ok=True)
                with staged.open('xb') as stream:
                    stream.write(content)
                    stream.flush()
                    os.fsync(stream.fileno())
                connection.execute('UPDATE attachments SET original_display_name=?, generated_stored_name=?, mime_type=?, size_bytes=?, sha256=? WHERE attachment_id=?',
                    (name, staged.name, mime, len(content), digest, attachment_id))
                connection.execute('UPDATE managed_attachments SET stored_name=?, sha256=? WHERE attachment_id=?', (staged.name, digest, attachment_id))
                self.touch(connection, patient_id)
            committed = True
        finally:
            if not committed:
                files.cleanup_uncommitted(staged)
        # Previous bytes are retained in Removed items until intentional deletion.
