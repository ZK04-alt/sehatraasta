"""Browser transfer adapter. Existing services own file and backup rules."""
from pathlib import Path
from tempfile import TemporaryDirectory
from uuid import uuid4

from .attachment_validation import validate_attachment_filename, validate_attachment_size, validate_attachment_signature
from .file_service import FileService
from .dataset_backup import DatasetBackupService
from .export_service import ExportService
from .identifiers import IDAllocator


class WebTransferService:
    def __init__(self, bundles):
        self.bundles = bundles
        self.database = bundles.repository.path

    def upload(self, uploaded, bundle_id, attachment_id, category, day, provenance, synthetic=None, **links):
        if attachment_id is None:
            attachment_id = IDAllocator(self.bundles.repository).allocate('attachment')
        extension = validate_attachment_filename(uploaded.filename)
        content = uploaded.stream.read(5242881)
        validate_attachment_size(len(content))
        validate_attachment_signature(extension, content[:8])
        with TemporaryDirectory(prefix='sr-upload-') as folder:
            path = Path(folder) / (uuid4().hex + extension)
            path.write_bytes(content)
            return FileService(self.database).import_file(bundle_id, attachment_id, path,
                category, day, provenance, synthetic=synthetic, original_name=uploaded.filename,
                expected_visit=self.bundles.expected_visit, **links)

    def export(self, bundle_id):
        with TemporaryDirectory(prefix='sr-export-') as folder:
            path = Path(folder) / 'bundle.json'
            ExportService(self.bundles).export_bundle(bundle_id, path)
            return path.read_bytes()

    def backup(self):
        with TemporaryDirectory(prefix='sr-backup-') as folder:
            name = DatasetBackupService(self.database).create(folder)
            return (Path(folder) / name).read_bytes()

    def restore(self, uploaded, confirm=False):
        # The destination is generated locally. A browser never supplies a path.
        with TemporaryDirectory(prefix='sr-restore-') as folder:
            path = Path(folder) / 'archive.zip'
            uploaded.save(path)
            service = DatasetBackupService(self.database)
            summary = service.dry_run(path)
            if not confirm:
                return summary, None
            name = 'restore-' + uuid4().hex
            target = Path(self.database).parent / 'restores' / name
            service.restore(path, target, confirmed=True)
            return summary, name
