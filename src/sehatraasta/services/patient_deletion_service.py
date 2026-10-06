"""Delete one patient and their owned records without touching other patients."""
from pathlib import Path
import sqlite3

from sehatraasta.storage.db import connect_database
from sehatraasta.storage.errors import StorageError, log_storage_error
from .file_service import FileService


class PatientDeletionService:
    def __init__(self, database):
        self.database = Path(database)

    def delete(self, patient_id, revision):
        """Commit all metadata together, then remove the patient's stored files.

        Return the count of files awaiting cleanup after an I/O failure. Existing
        attachment reconciliation can retry those unreferenced files safely.
        A stale confirmation must never delete records added since it was shown.
        """
        connection = connect_database(self.database)
        paths = []
        try:
            with connection:
                connection.execute('BEGIN IMMEDIATE')
                row = connection.execute('SELECT revision FROM patients WHERE patient_id = ?', (patient_id,)).fetchone()
                if row is None:
                    raise ValueError('patient not found')
                if row['revision'] != revision:
                    raise ValueError('patient changed; review before deleting')
                files = FileService(self.database)
                rows = connection.execute('SELECT m.stored_name FROM managed_attachments m JOIN referral_bundles b USING(bundle_id) WHERE b.patient_id = ?', (patient_id,)).fetchall()
                paths = [files._path(row['stored_name']) for row in rows]
                # These three tables use deferred references rather than CASCADE.
                for table in ('managed_attachments', 'file_audit_events', 'bundle_tokens'):
                    connection.execute(f'DELETE FROM {table} WHERE bundle_id IN (SELECT bundle_id FROM referral_bundles WHERE patient_id = ?)', (patient_id,))
                connection.execute('DELETE FROM patients WHERE patient_id = ?', (patient_id,))
        except (sqlite3.Error, OSError) as error:
            log_storage_error(self.database, 'patient_delete', error)
            raise StorageError('could not delete patient; no records were removed') from None
        finally:
            connection.close()
        pending = 0
        for path in paths:
            try:
                path.unlink(missing_ok=True)
            except OSError as error:
                pending += 1
                log_storage_error(self.database, 'patient_file_cleanup', error)
        return pending
