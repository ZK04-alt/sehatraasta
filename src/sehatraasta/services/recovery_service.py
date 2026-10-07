"""Persistent local recovery of normalized rows and managed originals.

Removed rows are absent from the active dataset. Retained bytes are still local
and belong in backup, until a separately requested permanent deletion succeeds.
"""
from datetime import datetime, timezone
import json
from uuid import uuid4

from sehatraasta.storage.db import connect_database
from sehatraasta.storage.errors import StorageError, log_storage_error
from .correction_service import CorrectionService
from .file_service import FileService


ROW_TABLES = ('patients', 'referral_bundles', 'encounters', 'medication_items',
    'instructions', 'attachments', 'investigation_orders', 'diagnostic_results',
    'imaging_items', 'cost_entries', 'category_reviews', 'audit_events',
    'managed_attachments', 'file_audit_events', 'bundle_tokens', 'referral_context', 'visit_drafts', 'visit_draft_fields', 'removed_items')
INTEGER_KEYS = {'encounters':'encounter_id','instructions':'instruction_id',
    'investigation_orders':'order_id','category_reviews':'review_id',
    'audit_events':'audit_event_id','file_audit_events':'event_id'}


def validate_snapshot_values(tables):
    """Use the same domain validators for retained rows as active records."""
    from datetime import date
    from decimal import Decimal
    from sehatraasta import domain as d
    try:
        orders={r['order_id']:(r['bundle_id'],d.InvestigationOrder(r['test_name'],date.fromisoformat(r['order_date']),r['ordering_source'],d.InvestigationOrderStatus[r['workflow_status']])) for r in tables.get('investigation_orders',[])}
        for table,rows in tables.items():
            for r in rows:
                if table in INTEGER_KEYS and type(r[INTEGER_KEYS[table]]) is not int:
                    raise ValueError('invalid retained integer ID')
                if table=='patients': d.Patient(r['patient_id'],r['display_name'],r['birth_year'],d.Language[r['language']])
                elif table=='referral_bundles': d.ReferralBundle(r['bundle_id'],datetime.fromisoformat(r['creation_time']),r['source_facility'],r['destination'],d.ReferralStatus[r['referral_status']],medical_date_kind=r['medical_date_kind'],medical_date_value=r['medical_date_value'])
                elif table=='medication_items': d.MedicationItem(*(r[key] for key in ('verbatim_name','strength','dose_text','route_text','frequency_text','duration_text','instructions','source','medication_id')))
                elif table=='encounters': d.Encounter(date.fromisoformat(r['date']),r['facility'],r['clinician_display_text'],r['source_note'])
                elif table=='instructions': d.Instruction(r['category'],d.Language[r['language']],r['verbatim_text'],r['author_source'],date.fromisoformat(r['date']))
                elif table=='investigation_orders': d.InvestigationOrder(r['test_name'],date.fromisoformat(r['order_date']),r['ordering_source'],d.InvestigationOrderStatus[r['workflow_status']])
                elif table=='diagnostic_results':
                    retained_order=orders.get(r['investigation_order_id'])
                    if retained_order and retained_order[0]!=r['bundle_id']: raise ValueError('retained order belongs to another visit')
                    d.DiagnosticResult(r['test_name'],date.fromisoformat(r['result_date']),r['source_summary'],r['result_id'],r['interpretation_note'],retained_order[1] if retained_order else None)
                elif table=='imaging_items': d.ImagingItem(r['modality'],r['body_part'],date.fromisoformat(r['date']),r['facility'],r['report'],r['imaging_id'],r['attachment_id'])
                elif table=='cost_entries':
                    if type(r['amount_paisa']) is not int: raise ValueError('invalid retained amount')
                    d.CostEntry(r['cost_entry_id'],d.CostCategory[r['category']],Decimal(r['amount_paisa'])/100,date.fromisoformat(r['date']),r['source'],r['note'],r['source_type'],r['source_identifier'],r['reported_by_label'])
                elif table=='attachments': d.Attachment(r['attachment_id'],r['category'],r['original_display_name'],r['mime_type'],r['sha256'],date.fromisoformat(r['date']) if r['date'] else None,r['source'],r['size_bytes'],r['generated_stored_name'])
                elif table=='category_reviews': d.CategoryReview(d.ReviewCategory[r['category']],d.PresenceState[r['presence_state']],r['reviewer_text'],datetime.fromisoformat(r['reviewed_time']),r['note'])
                elif table=='audit_events': d.AuditEvent(datetime.fromisoformat(r['timestamp']),r['action'],r['entity_type'],r['entity_id'],r['actor_label'],r['result'])
                elif table=='bundle_tokens':
                    from .qr_service import make_payload
                    make_payload(r['token'])
                elif table=='referral_context':
                    from .referral_context import validate_context
                    validate_context(r)
        from .unfinished_visit_service import UnfinishedVisitService
        for draft in tables.get('visit_drafts',[]):
            fields={}
            for row in tables.get('visit_draft_fields',[]):
                if row['draft_id']==draft['draft_id']: fields.setdefault(row['field_name'],[]).append(row['value'])
            UnfinishedVisitService.validate_fields(fields)
    except (ValueError,TypeError,KeyError,OverflowError):
        raise ValueError('invalid retained record values') from None


class RecoveryService:
    def __init__(self, database):
        self.database = database
        self.corrections = CorrectionService(database)

    def list(self):
        connection = connect_database(self.database, read_only=True)
        try:
            items = []
            for row in connection.execute('SELECT * FROM removed_items ORDER BY removed_at DESC,item_id'):
                item = {key:row[key] for key in row.keys() if key!='snapshot'}
                patient = connection.execute('SELECT display_name,birth_year FROM patients WHERE patient_id=?',(row['parent_patient'],)).fetchone()
                visit = connection.execute('SELECT source_facility,medical_date_value FROM referral_bundles WHERE bundle_id=?',(row['parent_visit'],)).fetchone()
                snapshot = self.snapshot(connection,row['snapshot'])
                if patient is None and snapshot['tables'].get('patients'):
                    patient = snapshot['tables']['patients'][0]
                if visit is None and snapshot['tables'].get('referral_bundles'):
                    visit = snapshot['tables']['referral_bundles'][0]
                item['context'] = ' · '.join(str(value) for value in [patient['display_name'] if patient else '',
                    patient['birth_year'] if patient else '',visit['source_facility'] if visit else '',
                    visit['medical_date_value'] if visit else ''] if value)
                items.append(item)
            return items
        finally:
            connection.close()

    @staticmethod
    def snapshot(connection, value, depth=0):
        if depth > 8:
            raise ValueError('removed record nesting exceeds recovery limits')
        data = json.loads(value)
        if not isinstance(data, dict) or set(data) != {'tables', 'links'} or not isinstance(data['tables'], dict) or not isinstance(data['links'], list):
            raise ValueError('invalid removed record')
        for table, rows in data['tables'].items():
            if table not in ROW_TABLES or not isinstance(rows, list):
                raise ValueError('invalid removed rows')
            columns = {row[1] for row in connection.execute('PRAGMA table_info("' + table + '")')}
            if any(not isinstance(row, dict) or set(row) != columns for row in rows):
                raise ValueError('invalid removed columns')
            if table == 'removed_items':
                for row in rows:
                    RecoveryService.snapshot(connection, row['snapshot'], depth+1)
        for link in data['links']:
            if not isinstance(link, dict) or set(link) != {'table','key','id','column','before','after'} or link['table'] not in ROW_TABLES:
                raise ValueError('invalid removed relationship')
            columns = {row[1] for row in connection.execute('PRAGMA table_info("' + link['table'] + '")')}
            if link['key'] not in columns or link['column'] not in columns:
                raise ValueError('invalid removed relationship')
            allowed = {('imaging_items','imaging_id','attachment_id'),('diagnostic_results','result_id','investigation_order_id'),
                *[('managed_attachments','attachment_id',column) for column in ('order_id','result_id','imaging_id','instruction_id')]}
            if (link['table'],link['key'],link['column']) not in allowed or link['after'] is not None:
                raise ValueError('invalid removed relationship')
        return data

    @classmethod
    def validate_item(cls, connection, item, inherited_visits=None):
        """Bind recovery rows to the identity shown, including nested removals."""
        data=cls.snapshot(connection,item['snapshot'])
        tables=data['tables']
        kind,patient,visit=item['kind'],item['parent_patient'],item['parent_visit']
        if kind not in ('patient','visit','document','replacement','record') or not patient:
            raise ValueError('invalid removed ownership')
        allowed=set(ROW_TABLES)-{'patients','visit_drafts','visit_draft_fields'}
        if kind=='patient':
            allowed=set(ROW_TABLES)
            if visit is not None or len(tables.get('patients',[]))!=1 or tables['patients'][0]['patient_id']!=patient:
                raise ValueError('invalid removed patient ownership')
            visits={row[0] for row in connection.execute('SELECT bundle_id FROM referral_bundles WHERE patient_id=?',(patient,))}
            visits.update(row['bundle_id'] for snapshot in cls.snapshots(connection,item['snapshot'])
                for row in snapshot['tables'].get('referral_bundles',[]) if row['patient_id']==patient)
        else:
            if not visit: raise ValueError('invalid removed visit ownership')
            visits={visit}
            current=connection.execute('SELECT patient_id FROM referral_bundles WHERE bundle_id=?',(visit,)).fetchone()
            if (current and current[0]!=patient) or (not current and kind!='visit' and visit not in (inherited_visits or set())):
                raise ValueError('invalid removed visit ownership')
            if kind=='visit' and (len(tables.get('referral_bundles',[]))!=1 or tables['referral_bundles'][0]['bundle_id']!=visit):
                raise ValueError('invalid removed visit rows')
            if kind in ('document','replacement'):
                allowed={'attachments','managed_attachments'}
                if len(tables.get('attachments',[]))!=1 or len(tables.get('managed_attachments',[])) not in (0,1) or (kind=='replacement' and not tables.get('managed_attachments')):
                    raise ValueError('invalid removed document rows')
            elif kind=='record':
                from .correction_service import RECORDS
                allowed={record[0] for record in RECORDS.values()}
                if len(tables)!=1 or sum(len(rows) for rows in tables.values())!=1:
                    raise ValueError('invalid removed record rows')
        if set(tables)-allowed: raise ValueError('invalid removed row set')
        drafts={row['draft_id'] for row in tables.get('visit_drafts',[])}
        for table,rows in tables.items():
            for row in rows:
                if table=='removed_items':
                    if row['parent_patient']!=patient or (kind=='visit' and row['parent_visit']!=visit):
                        raise ValueError('invalid nested removed ownership')
                    cls.validate_item(connection,row,visits)
                elif ('patient_id' in row and row['patient_id']!=patient) or ('bundle_id' in row and row['bundle_id'] not in visits):
                    raise ValueError('invalid removed row ownership')
                elif table=='visit_draft_fields' and row['draft_id'] not in drafts:
                    raise ValueError('invalid removed draft ownership')
        link_sources={'attachment_id':('attachments','attachment_id'),'investigation_order_id':('investigation_orders','order_id'),
            'order_id':('investigation_orders','order_id'),'result_id':('diagnostic_results','result_id'),
            'imaging_id':('imaging_items','imaging_id'),'instruction_id':('instructions','instruction_id')}
        for link in data['links']:
            source,key=link_sources[link['column']]
            if link['before'] not in {row[key] for row in tables.get(source,[])}:
                raise ValueError('invalid removed link source')
            target=connection.execute('SELECT bundle_id FROM '+link['table']+' WHERE '+link['key']+'=?',(link['id'],)).fetchone()
            if target and target[0] not in visits: raise ValueError('invalid removed link ownership')
        validate_snapshot_values(tables)
        return data

    @classmethod
    def maximum_id(cls, connection, table, key):
        if INTEGER_KEYS.get(table)!=key: raise ValueError('invalid integer allocator')
        maximum=connection.execute('SELECT COALESCE(MAX('+key+'),0) FROM '+table).fetchone()[0]
        for row in connection.execute('SELECT snapshot FROM removed_items'):
            for snapshot in cls.snapshots(connection,row[0]):
                maximum=max(maximum,max((saved[key] for saved in snapshot['tables'].get(table,[])),default=0))
        return maximum

    @staticmethod
    def retain(connection, kind, label, patient_id, visit_id, tables, links=None):
        identifier = 'RM-' + uuid4().hex
        connection.execute('INSERT INTO removed_items VALUES (?,?,?,?,?,?,?,?)',
            (identifier, kind, label, patient_id, visit_id, datetime.now(timezone.utc).isoformat(),
             'removed', json.dumps({'tables':tables, 'links':links or []}, ensure_ascii=False)))
        return identifier

    def remove(self, kind, identifier, revision):
        if kind not in ('patient', 'visit', 'document'):
            raise ValueError('invalid removal kind')
        with self.corrections.transaction() as connection:
            if kind in ('patient','visit'):
                column='parent_patient' if kind=='patient' else 'parent_visit'
                if connection.execute("SELECT 1 FROM removed_items WHERE "+column+"=? AND state='purging'",(identifier,)).fetchone():
                    raise ValueError('finish pending permanent cleanup in Removed items before removing this parent')
            tables, links = {}, []
            if kind == 'patient':
                patient = connection.execute('SELECT * FROM patients WHERE patient_id=?', (identifier,)).fetchone()
                if patient is None or patient['revision'] != revision:
                    raise ValueError('patient changed; reopen before removing')
                patient_id, visit_id, label = identifier, None, patient['display_name']
                tables['patients'] = [dict(patient)]
                tables['visit_drafts'] = [dict(row) for row in connection.execute('SELECT * FROM visit_drafts WHERE patient_id=?',(identifier,))]
                tables['visit_draft_fields'] = [dict(row) for row in connection.execute('SELECT f.* FROM visit_draft_fields f JOIN visit_drafts d USING(draft_id) WHERE d.patient_id=?',(identifier,))]
                visits = [row[0] for row in connection.execute('SELECT bundle_id FROM referral_bundles WHERE patient_id=?', (identifier,))]
            elif kind == 'visit':
                patient_id = self.corrections.owner(connection, identifier, revision)
                visit_id, visits = identifier, [identifier]
                label = connection.execute('SELECT display_name FROM patients WHERE patient_id=?', (patient_id,)).fetchone()[0]
            else:
                original = connection.execute('SELECT * FROM attachments WHERE attachment_id=?', (identifier,)).fetchone()
                if original is None:
                    raise ValueError('document not found')
                patient_id = self.corrections.owner(connection, original['bundle_id'], revision)
                visit_id, visits, label = original['bundle_id'], [], original['original_display_name']
                tables['attachments'] = [dict(original)]
                tables['managed_attachments'] = [dict(row) for row in connection.execute('SELECT * FROM managed_attachments WHERE attachment_id=?', (identifier,))]
                for row in connection.execute('SELECT imaging_id FROM imaging_items WHERE attachment_id=?', (identifier,)):
                    links.append({'table':'imaging_items','key':'imaging_id','id':row[0], 'column':'attachment_id','before':identifier,'after':None})
                connection.execute('UPDATE imaging_items SET attachment_id=NULL WHERE attachment_id=?', (identifier,))
                connection.execute('DELETE FROM managed_attachments WHERE attachment_id=?', (identifier,))
                connection.execute('DELETE FROM attachments WHERE attachment_id=?', (identifier,))
            for visit in visits:
                for table in ROW_TABLES[1:-3]:
                    tables.setdefault(table, []).extend(dict(row) for row in connection.execute('SELECT * FROM "' + table + '" WHERE bundle_id=?', (visit,)))
                for table in ('managed_attachments', 'file_audit_events', 'bundle_tokens'):
                    connection.execute('DELETE FROM "' + table + '" WHERE bundle_id=?', (visit,))
                connection.execute('DELETE FROM referral_bundles WHERE bundle_id=?', (visit,))
            if kind in ('patient', 'visit'):
                column = 'parent_patient' if kind == 'patient' else 'parent_visit'
                tables['removed_items'] = [dict(row) for row in connection.execute('SELECT * FROM removed_items WHERE ' + column + '=?', (identifier,))]
                connection.execute('DELETE FROM removed_items WHERE ' + column + '=?', (identifier,))
            item = self.retain(connection, kind, label, patient_id, visit_id, tables, links)
            if kind == 'patient':
                connection.execute('DELETE FROM patients WHERE patient_id=?', (identifier,))
            else:
                self.corrections.touch(connection, patient_id)
            return item

    def remove_record(self, kind, identifier, revision):
        from .correction_service import RECORDS, record_links
        if kind not in RECORDS:
            raise ValueError('invalid record kind')
        table, key, fields = RECORDS[kind]
        with self.corrections.transaction() as connection:
            row = connection.execute('SELECT * FROM '+table+' WHERE '+key+'=?',(identifier,)).fetchone()
            if row is None:
                raise ValueError('record not found')
            patient_id = self.corrections.owner(connection,row['bundle_id'],revision)
            links = record_links(connection,kind,identifier)
            for link in links:
                connection.execute('UPDATE '+link['table']+' SET '+link['column']+'=NULL WHERE '+link['key']+'=?',(link['id'],))
            label = next((row[column] for column in ('verbatim_name','test_name','modality','category','facility') if column in row.keys()), kind)
            item = self.retain(connection,'record',label,patient_id,row['bundle_id'],{table:[dict(row)]},links)
            connection.execute('DELETE FROM '+table+' WHERE '+key+'=?',(identifier,))
            self.corrections.touch(connection,patient_id)
            return item

    @classmethod
    def retained_files(cls, connection):
        files = []
        for row in connection.execute('SELECT snapshot FROM removed_items'):
            for snapshot in cls.snapshots(connection, row[0]):
                files.extend(snapshot['tables'].get('managed_attachments', []))
        return files

    @classmethod
    def snapshots(cls, connection, value):
        snapshot = cls.snapshot(connection, value)
        yield snapshot
        for child in snapshot['tables'].get('removed_items', []):
            yield from cls.snapshots(connection, child['snapshot'])

    def restore(self, item_id):
        with self.corrections.transaction() as connection:
            row = connection.execute('SELECT * FROM removed_items WHERE item_id=?', (item_id,)).fetchone()
            if row is None or row['state'] != 'removed':
                raise ValueError('removed item not available for restore')
            if row['kind'] != 'patient' and connection.execute('SELECT 1 FROM patients WHERE patient_id=?', (row['parent_patient'],)).fetchone() is None:
                raise ValueError('restore the patient before restoring its records')
            data = self.validate_item(connection, row)
            files = FileService(self.database)
            import hashlib
            for original in data['tables'].get('attachments',[]):
                if connection.execute('SELECT 1 FROM attachments WHERE sha256=?',(original['sha256'],)).fetchone():
                    raise ValueError('duplicate active original; resolve before restoring')
            for snapshot in self.snapshots(connection,row['snapshot']):
              for original in snapshot['tables'].get('managed_attachments', []):
                content = files._path(original['stored_name']).read_bytes()
                if hashlib.sha256(content).hexdigest() != original['sha256']:
                    raise ValueError('retained original is missing or changed; restore a backup')
            for table in ROW_TABLES:
                for saved in data['tables'].get(table, []):
                    columns = list(saved)
                    connection.execute('INSERT INTO "' + table + '" (' + ','.join('"' + column + '"' for column in columns) + ') VALUES (' + ','.join('?' for _ in columns) + ')', list(saved.values()))
            for link in data['links']:
                updated = connection.execute('UPDATE "' + link['table'] + '" SET "' + link['column'] + '"=? WHERE "' + link['key'] + '"=? AND "' + link['column'] + '" IS ?', (link['before'], link['id'], link['after']))
                if updated.rowcount != 1:
                    raise ValueError('linked record changed; restore would overwrite a correction')
            connection.execute('DELETE FROM removed_items WHERE item_id=?', (item_id,))
            self.corrections.touch(connection, row['parent_patient'])

    def permanent(self, item_id):
        files = FileService(self.database)
        with self.corrections.transaction() as connection:
            row = connection.execute('SELECT * FROM removed_items WHERE item_id=?', (item_id,)).fetchone()
            if row is None:
                return 0
            data = self.validate_item(connection, row)
            originals = [original for snapshot in self.snapshots(connection, row['snapshot']) for original in snapshot['tables'].get('managed_attachments', [])]
            active = {item[0] for item in connection.execute('SELECT stored_name FROM managed_attachments')}
            others = {item['stored_name'] for saved in connection.execute('SELECT snapshot FROM removed_items WHERE item_id!=?', (item_id,)) for snapshot in self.snapshots(connection, saved[0]) for item in snapshot['tables'].get('managed_attachments', [])}
            if any(item['stored_name'] in active | others for item in originals):
                raise ValueError('retained bytes are still owned by another item')
            paths = [files._path(item['stored_name']) for item in originals]
            connection.execute("UPDATE removed_items SET state='purging' WHERE item_id=?", (item_id,))
        pending = 0
        for path in paths:
            try:
                path.unlink(missing_ok=True)
            except OSError as error:
                pending += 1
                log_storage_error(self.database, 'permanent_cleanup', error)
        if pending == 0:
            with self.corrections.transaction() as connection:
                connection.execute("DELETE FROM removed_items WHERE item_id=? AND state='purging'", (item_id,))
        return pending
