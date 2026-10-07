"""Server-side identifiers, independent of HTTP and translated interface text."""
import secrets
import string

from sehatraasta.storage.errors import StorageError

ALPHABET = '23456789ABCDEFGHJKLMNPQRSTUVWXYZ'
PREFIXES = {'patient': 'PT', 'medication': 'MD', 'result': 'DR',
            'imaging': 'IM', 'cost': 'CE', 'attachment': 'AT'}
TEXT_KEYS = {'patients': 'patient_id', 'referral_bundles': 'bundle_id',
             'medication_items': 'medication_id', 'diagnostic_results': 'result_id',
             'imaging_items': 'imaging_id', 'cost_entries': 'cost_entry_id',
             'attachments': 'attachment_id'}


class IDAllocator:
    def __init__(self, repository):
        self.used = set()
        for patient in repository.list_patients():
            self.used.add(patient.ID)
            for bundle in patient.referrals:
                self.used.add(bundle.ID)
                for records in (bundle.medication_item, bundle.diagnostic_results,
                                bundle.imaging_items, bundle.cost_entries, bundle.attachments):
                    self.used.update(item.ID for item in records)
        # Non-persistent repositories have no retained SQLite snapshots.
        if getattr(repository, 'path', None) is None:
            return
        from sehatraasta.storage.db import connect_database
        connection = connect_database(repository.path, read_only=True)
        try:
            self.used.update(self.reserved(connection))
        finally:
            connection.close()

    @staticmethod
    def reserved(connection):
        from .recovery_service import RecoveryService
        used = set()
        for table, key in TEXT_KEYS.items():
            used.update(row[0] for row in connection.execute(f'SELECT {key} FROM {table}'))
        for item in connection.execute('SELECT * FROM removed_items'):
            RecoveryService.validate_item(connection, item)
            for snapshot in RecoveryService.snapshots(connection, item['snapshot']):
                for table, key in TEXT_KEYS.items():
                    used.update(row[key] for row in snapshot['tables'].get(table, []))
        return used

    @classmethod
    def from_connection(cls, connection):
        """Allocate within an existing write transaction, including its rows."""
        allocator = cls.__new__(cls)
        allocator.used = cls.reserved(connection)
        return allocator

    def allocate(self, kind):
        for _ in range(10):
            if kind == 'bundle':
                letters = ''.join(secrets.choice(string.ascii_uppercase) for _ in range(12))
                candidate = f'SR-{letters}-{secrets.randbelow(1000):03d}'
            else:
                suffix = ''.join(secrets.choice(ALPHABET) for _ in range(6))
                candidate = PREFIXES[kind] + '-' + suffix
            if candidate not in self.used:
                self.used.add(candidate)  # Reserve before allocating another row in this intake.
                return candidate
        raise StorageError('Could not allocate an identifier')
