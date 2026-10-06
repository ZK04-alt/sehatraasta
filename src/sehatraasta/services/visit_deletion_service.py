"""Remove one visit with stale-confirmation protection and recoverable cleanup."""
from pathlib import Path
import sqlite3

from sehatraasta.storage.db import connect_database
from sehatraasta.storage.errors import StorageError, log_storage_error
from .file_service import FileService


class VisitDeletionService:
    def __init__(self, database):
        self.database = Path(database)

    def delete(self, bundle_id, revision):
        connection = connect_database(self.database)
        paths = []
        try:
            with connection:
                connection.execute('BEGIN IMMEDIATE')
                row = connection.execute('SELECT p.patient_id, p.revision FROM patients p JOIN referral_bundles b USING(patient_id) WHERE b.bundle_id = ?', (bundle_id,)).fetchone()
                if row is None:
                    raise ValueError('bundle not found')
                if row['revision'] != revision:
                    raise ValueError('visit changed; review before deleting')
                files = FileService(self.database)
                paths = [files._path(item['stored_name']) for item in connection.execute('SELECT stored_name FROM managed_attachments WHERE bundle_id = ?', (bundle_id,))]
                for table in ('managed_attachments', 'file_audit_events', 'bundle_tokens'):
                    connection.execute(f'DELETE FROM {table} WHERE bundle_id = ?', (bundle_id,))
                connection.execute('DELETE FROM referral_bundles WHERE bundle_id = ?', (bundle_id,))
                connection.execute('UPDATE patients SET revision = revision + 1 WHERE patient_id = ?', (row['patient_id'],))
        except (sqlite3.Error, OSError) as error:
            log_storage_error(self.database, 'visit_delete', error)
            raise StorageError('could not delete visit; no records were removed') from None
        finally:
            connection.close()
        pending = 0
        for path in paths:
            try:
                path.unlink(missing_ok=True)
            except OSError as error:
                pending += 1
                log_storage_error(self.database, 'visit_file_cleanup', error)
        return pending
