"""Patient-supplied context; never interprets clinical text."""
from datetime import date, datetime, timezone
import sqlite3

from sehatraasta.storage.db import connect_database
from sehatraasta.storage.errors import StorageError, log_storage_error

TEXT_FIELDS = ('medical_history', 'allergies', 'referral_reason', 'referral_notes', 'department', 'source')


def validate_context(values):
    result = {}
    for name in TEXT_FIELDS:
        value = values.get(name, '')
        if not isinstance(value, str) or len(value) > 4000 or '\x00' in value:
            raise ValueError('invalid ' + name.replace('_', ' '))
        result[name] = value.strip()
    day = values.get('follow_up_date')
    if day not in (None, ''):
        if isinstance(day, datetime):
            raise ValueError('invalid follow up date')
        day = date.fromisoformat(day) if isinstance(day, str) else day
        if not isinstance(day, date):
            raise ValueError('invalid follow up date')
        day = day.isoformat()
    result['follow_up_date'] = day or None
    return result


class ReferralContextService:
    def __init__(self, database):
        self.database = database

    def get(self, bundle_id):
        connection = connect_database(self.database, read_only=True)
        try:
            row = connection.execute('SELECT * FROM referral_context WHERE bundle_id = ?', (bundle_id,)).fetchone()
            return dict(row) if row else {**dict.fromkeys(TEXT_FIELDS, ''), 'follow_up_date': None}
        finally:
            connection.close()

    def save(self, bundle_id, values, expected_visit=None):
        data = validate_context(values)
        connection = connect_database(self.database)
        try:
            with connection:
                connection.execute('BEGIN IMMEDIATE')
                if expected_visit is not None:
                    row=connection.execute('SELECT b.bundle_id,p.patient_id,p.revision FROM referral_bundles b JOIN patients p USING(patient_id) WHERE b.bundle_id=?',(bundle_id,)).fetchone()
                    if row is None or list(row)!=expected_visit:
                        raise ValueError('patient or visit changed; reopen before saving')
                if not connection.execute('SELECT 1 FROM referral_bundles WHERE bundle_id = ?', (bundle_id,)).fetchone():
                    raise ValueError('bundle not found')
                connection.execute('''INSERT INTO referral_context
                    (bundle_id, medical_history, allergies, referral_reason, referral_notes, department,
                     follow_up_date, source, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(bundle_id) DO UPDATE SET medical_history=excluded.medical_history,
                     allergies=excluded.allergies, referral_reason=excluded.referral_reason,
                     referral_notes=excluded.referral_notes, department=excluded.department,
                     follow_up_date=excluded.follow_up_date, source=excluded.source, updated_at=excluded.updated_at''',
                    (bundle_id, *(data[name] for name in TEXT_FIELDS[:5]), data['follow_up_date'],
                     data['source'], datetime.now(timezone.utc).isoformat(timespec='seconds')))
                from .recovery_service import RecoveryService
                connection.execute("INSERT INTO audit_events(audit_event_id, bundle_id, timestamp, action, entity_type, entity_id, actor_label, result) VALUES (?, ?, ?, 'update context', 'referral', ?, 'device user', 'success')",
                    (RecoveryService.maximum_id(connection,'audit_events','audit_event_id')+1,bundle_id, datetime.now(timezone.utc).isoformat(), bundle_id))
                connection.execute('UPDATE patients SET revision=revision+1 WHERE patient_id=(SELECT patient_id FROM referral_bundles WHERE bundle_id=?)', (bundle_id,))
        except sqlite3.Error as error:
            log_storage_error(self.database, 'save_context', error)
            raise StorageError('could not save referral notes') from None
        finally:
            connection.close()
