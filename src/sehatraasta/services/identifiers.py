"""Server-side identifiers, independent of HTTP and translated interface text."""
import secrets
import string

from sehatraasta.storage.errors import StorageError

ALPHABET = '23456789ABCDEFGHJKLMNPQRSTUVWXYZ'
PREFIXES = {'patient': 'PT', 'medication': 'MD', 'result': 'DR',
            'imaging': 'IM', 'cost': 'CE', 'attachment': 'AT'}


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
