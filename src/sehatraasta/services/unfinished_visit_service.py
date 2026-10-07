"""Keep unfinished form values separate from validated visit records."""
from datetime import datetime, timezone
import re
import sqlite3
from uuid import uuid4

from sehatraasta.storage.db import connect_database
from sehatraasta.storage.errors import StorageError, log_storage_error

META = {'csrf', 'had_errors', 'intent', 'lang', 'unfinished_id', 'unfinished_revision'}
BASE = {'mode', 'patient_id', 'name', 'birth_year', 'language', 'creation_time', 'source_facility', 'destination', 'status',
        'capture', 'medical_date_kind', 'medical_date_value'}
ROW = re.compile(r'(medications|orders|results|imaging|instructions|costs)\.(rows|[0-9]{1,7}\.[a-z_]+(?:__custom)?)')


class UnfinishedVisitService:
    def __init__(self, database):
        self.database = database

    def save(self, fields, draft_id='', revision=0):
        if type(revision) is not int or revision < 0:
            raise ValueError('invalid unfinished visit revision')
        cleaned = self.validate_fields(fields)
        if draft_id and not re.fullmatch(r'UV-[A-F0-9]{32}', draft_id):
            raise ValueError('invalid unfinished visit ID')
        return self._save(cleaned, draft_id, revision)

    @staticmethod
    def validate_fields(fields):
        if not isinstance(fields, dict):
            raise ValueError('invalid unfinished visit fields')
        cleaned = {}
        size = 0
        for name, values in fields.items():
            if name in META:
                continue
            if not isinstance(name, str) or (name not in BASE and not ROW.fullmatch(name)):
                raise ValueError('invalid unfinished visit fields')
            if not isinstance(values, list) or not all(isinstance(value, str) for value in values):
                raise ValueError('invalid unfinished visit fields')
            if len(values) > 64 or any(len(value) > 65536 for value in values):
                raise ValueError('unfinished visit too large')
            if not values or (name in BASE and len(values) != 1):
                raise ValueError('invalid unfinished visit fields')
            size += sum(len(value.encode('utf-8')) for value in values)
            cleaned[name] = values
        if size > 128 * 1024 or len(cleaned) > 800:
            raise ValueError('unfinished visit too large')
        return cleaned

    def _save(self, cleaned, draft_id, revision):
        draft_id = draft_id or 'UV-' + uuid4().hex.upper()
        stamp = datetime.now(timezone.utc).isoformat(timespec='seconds')
        connection = connect_database(self.database)
        try:
            with connection:
                connection.execute('BEGIN IMMEDIATE')
                old = connection.execute('SELECT * FROM visit_drafts WHERE draft_id = ?', (draft_id,)).fetchone()
                if (old is None and revision != 0) or (old is not None and old['revision'] != revision):
                    raise ValueError('unfinished visit changed; reopen before saving')
                patient_id = None
                if cleaned.get('mode') == ['existing']:
                    selected = cleaned.get('patient_id', [''])[0]
                    if connection.execute('SELECT 1 FROM patients WHERE patient_id = ?', (selected,)).fetchone():
                        patient_id = selected
                next_revision = revision + 1
                if old is None:
                    connection.execute('INSERT INTO visit_drafts VALUES (?, ?, ?, ?, ?)',
                                       (draft_id, patient_id, stamp, stamp, next_revision))
                else:
                    connection.execute('UPDATE visit_drafts SET patient_id = ?, updated_at = ?, revision = ? WHERE draft_id = ?',
                                       (patient_id, stamp, next_revision, draft_id))
                    connection.execute('DELETE FROM visit_draft_fields WHERE draft_id = ?', (draft_id,))
                for name, values in cleaned.items():
                    for position, value in enumerate(values):
                        connection.execute('INSERT INTO visit_draft_fields VALUES (?, ?, ?, ?)', (draft_id, name, position, value))
            return {'draft_id': draft_id, 'revision': next_revision, 'updated_at': stamp}
        except sqlite3.Error as error:
            log_storage_error(self.database, 'save_unfinished', error)
            raise StorageError('could not save unfinished visit') from None
        finally:
            connection.close()

    def get(self, draft_id):
        connection = connect_database(self.database, read_only=True)
        try:
            row = connection.execute('SELECT * FROM visit_drafts WHERE draft_id = ?', (draft_id,)).fetchone()
            if row is None:
                raise ValueError('unfinished visit not found')
            fields = {}
            for field in connection.execute('SELECT * FROM visit_draft_fields WHERE draft_id = ? ORDER BY field_name, position', (draft_id,)):
                fields.setdefault(field['field_name'], []).append(field['value'])
            return dict(row, fields=self.validate_fields(fields))
        except sqlite3.Error as error:
            log_storage_error(self.database, 'read_unfinished', error)
            raise StorageError('could not read unfinished visit') from None
        finally:
            connection.close()

    def list(self):
        connection = connect_database(self.database, read_only=True)
        try:
            rows = connection.execute('''SELECT d.*, COALESCE(p.display_name, n.value, '') AS display_name,
                COALESCE(f.value, '') AS facility, COALESCE(c.value, '') AS capture FROM visit_drafts d
                LEFT JOIN patients p ON p.patient_id = d.patient_id
                LEFT JOIN visit_draft_fields n ON n.draft_id = d.draft_id AND n.field_name = 'name' AND n.position = 0
                LEFT JOIN visit_draft_fields f ON f.draft_id = d.draft_id AND f.field_name = 'source_facility' AND f.position = 0
                LEFT JOIN visit_draft_fields c ON c.draft_id = d.draft_id AND c.field_name = 'capture' AND c.position = 0
                ORDER BY d.updated_at DESC''').fetchall()
            return [dict(row) for row in rows]
        except sqlite3.Error as error:
            log_storage_error(self.database, 'list_unfinished', error)
            raise StorageError('could not list unfinished visits') from None
        finally:
            connection.close()
