"""Transfer one referral offline. Import adds a separate patient copy; never name-matches."""
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sqlite3
import zlib
from tempfile import TemporaryDirectory
from uuid import uuid4
from zipfile import ZipFile, ZIP_DEFLATED, BadZipFile

from sehatraasta.storage import SQLiteRepository, StorageError
from sehatraasta.storage.db import connect_database, check_database
from .dataset_backup import DatasetBackupService, TABLES, encoded, read_tables, migrate_legacy_tables
from .file_service import FileService
from .identifiers import IDAllocator
from .qr_service import QRService
from .archive_reader import read_checked_members

# Leave room for multipart headers within the existing 55 MiB HTTP limit.
MAX_BYTES = 50 * 1024 * 1024

TEXT_IDS = {'patients': ('patient_id', 'patient'), 'referral_bundles': ('bundle_id', 'bundle'),
    'attachments': ('attachment_id', 'attachment'), 'medication_items': ('medication_id', 'medication'),
    'diagnostic_results': ('result_id', 'result'), 'imaging_items': ('imaging_id', 'imaging'),
    'cost_entries': ('cost_entry_id', 'cost')}
INT_IDS = {'encounters': 'encounter_id', 'instructions': 'instruction_id',
    'investigation_orders': 'order_id', 'category_reviews': 'review_id',
    'audit_events': 'audit_event_id', 'file_audit_events': 'event_id'}
INSERT_ORDER = ('patients', 'referral_bundles', 'attachments', 'medication_items', 'encounters',
    'instructions', 'investigation_orders', 'diagnostic_results', 'imaging_items', 'cost_entries',
    'category_reviews', 'audit_events', 'managed_attachments', 'file_audit_events',
    'bundle_tokens', 'referral_context')


class PassportService:
    def __init__(self, database):
        self.database = Path(database)

    def export(self, bundle_id):
        QRService(self.database).for_bundle(bundle_id)
        connection = connect_database(self.database)
        try:
            with connection:
                connection.execute('BEGIN IMMEDIATE')
                check_database(connection)
                all_tables = read_tables(connection)
                owner = connection.execute('SELECT patient_id FROM referral_bundles WHERE bundle_id=?', (bundle_id,)).fetchone()
                if owner is None:
                    raise ValueError('bundle not found')
                tables = {name: [] if name in ('visit_drafts', 'visit_draft_fields', 'removed_items') else rows if name == 'schema_version' else
                    [row for row in rows if row['patient_id'] == owner[0]] if name == 'patients' else
                    [row for row in rows if row['bundle_id'] == bundle_id]
                    for name, rows in all_tables.items()}
                members = {'passport.json': encoded({'format': 'sehatraasta-passport', 'version': 3, 'tables': tables})}
                files = FileService(self.database)
                for row in tables['managed_attachments']:
                    with files._path(row['stored_name']).open('rb') as stream:
                        content = stream.read(5242881)
                    if len(content) > 5242880 or hashlib.sha256(content).hexdigest() != row['sha256']:
                        raise ValueError('attachment integrity check failed')
                    members['attachments/' + row['stored_name']] = content
                if sum(map(len, members.values())) > MAX_BYTES or len(members) > 999:
                    raise ValueError('passport exceeds transfer limits')
                from io import BytesIO
                output = BytesIO()
                with ZipFile(output, 'w', ZIP_DEFLATED) as archive:
                    archive.writestr('manifest.json', encoded({name: hashlib.sha256(content).hexdigest() for name, content in members.items()}))
                    for name, content in members.items():
                        archive.writestr(name, content)
                content = output.getvalue()
                if len(content) > MAX_BYTES:
                    raise ValueError('passport exceeds transfer limits')
                return content
        finally:
            connection.close()

    def _read(self, content):
        from io import BytesIO
        try:
            if len(content) > MAX_BYTES:
                raise ValueError()
            with ZipFile(BytesIO(content)) as archive:
                infos = archive.infolist()
                names = [item.filename for item in infos]
                if len(names) != len(set(names)) or len(names) > 1000 or sum(item.file_size for item in infos) > MAX_BYTES:
                    raise ValueError()
                if 'passport.json' not in names or 'manifest.json' not in names:
                    raise ValueError()
                for item in infos:
                    if item.is_dir() or (item.external_attr >> 16) & 0o170000 == 0o120000:
                        raise ValueError()
                    if item.filename not in ('passport.json', 'manifest.json'):
                        if not item.filename.startswith('attachments/'):
                            raise ValueError()
                        FileService(self.database)._path(item.filename[12:])
                members = read_checked_members(archive,infos,MAX_BYTES)
            manifest = json.loads(members.pop('manifest.json'))
            if not isinstance(manifest, dict) or set(manifest) != set(members):
                raise ValueError()
            if any(hashlib.sha256(data).hexdigest() != manifest[name] for name, data in members.items()):
                raise ValueError()
            document = json.loads(members.pop('passport.json'))
            if document['format'] != 'sehatraasta-passport' or type(document['version']) is not int or document['version'] not in (1, 2, 3):
                raise ValueError()
            tables = document['tables']
            versions = [row['version'] for row in tables['schema_version']]
            if any(type(version) is not int for version in versions) or versions!=list(range(1,len(versions)+1)):
                raise ValueError()
            if (document['version']==1 and versions not in ([1,2,3],[1,2,3,4])) or (document['version']==2 and versions!=[1,2,3,4,5]) or (document['version']==3 and versions!=[1,2,3,4,5,6]):
                raise ValueError()
            # Earlier passports predate unfinished visit storage. They contain only completed records.
            if set(tables) == set(TABLES) - {'visit_drafts', 'visit_draft_fields', 'removed_items'}:
                tables['visit_drafts'] = []
                tables['visit_draft_fields'] = []
                tables['schema_version'].append({'version': 4, 'applied_at': 'legacy passport migration'})
            if set(tables) not in (set(TABLES), set(TABLES)-{'removed_items'}) or len(tables['patients']) != 1 or len(tables['referral_bundles']) != 1 or len(tables['bundle_tokens']) != 1:
                raise ValueError()
            if tables['visit_drafts'] or tables['visit_draft_fields'] or tables.get('removed_items'):
                raise ValueError()  # Unfinished entries are never shared in a single-visit passport.
            tables = migrate_legacy_tables(tables)
            with TemporaryDirectory(prefix='sr-passport-check-') as name:
                DatasetBackupService(self.database)._restore_staged(Path(name), tables, members)
                patient = SQLiteRepository(Path(name) / 'sehatraasta.sqlite').list_patients()[0]
                summary = {'patient': patient.name, 'birth_year': patient.birth_year,
                    'destination': patient.referrals[0].destination, 'documents': len(members)}
            return tables, members, summary
        except (ValueError, KeyError, TypeError, IndexError, OSError, sqlite3.Error, StorageError, BadZipFile, RuntimeError, UnicodeError, zlib.error):
            raise ValueError('invalid passport file') from None

    def preview(self, content):
        return self._read(content)[2]

    def import_passport(self, content, confirmed=False):
        if confirmed is not True:
            raise ValueError('confirm passport import')
        tables, members, _ = self._read(content)
        tables = deepcopy(tables)
        allocator = IDAllocator(SQLiteRepository(self.database))
        connection = connect_database(self.database)
        created = []
        files = FileService(self.database)
        try:
            with connection:
                connection.execute('BEGIN IMMEDIATE')
                connection.execute('PRAGMA defer_foreign_keys=ON')
                token = tables['bundle_tokens'][0]['token']
                from .recovery_service import RecoveryService
                retained_tokens={row['token'] for removed in connection.execute('SELECT snapshot FROM removed_items')
                    for snapshot in RecoveryService.snapshots(connection,removed[0]) for row in snapshot['tables'].get('bundle_tokens',[])}
                if connection.execute('SELECT 1 FROM bundle_tokens WHERE token=?', (token,)).fetchone() or token in retained_tokens:
                    raise ValueError('passport already imported')
                maps = {}
                for table, (column, kind) in TEXT_IDS.items():
                    maps[column] = {row[column]: allocator.allocate(kind) for row in tables[table]}
                for table, column in INT_IDS.items():
                    maximum = RecoveryService.maximum_id(connection,table,column)
                    maps[column] = {row[column]: maximum + index + 1 for index, row in enumerate(tables[table])}
                maps['investigation_order_id'] = maps['order_id']
                for table in INSERT_ORDER:
                    for row in tables[table]:
                        for column, mapping in maps.items():
                            if column in row and row[column] is not None:
                                row[column] = mapping[row[column]]
                        if table == 'patients':
                            row['revision'] = 0
                        if table == 'attachments' and row['generated_stored_name']:
                            row['generated_stored_name'] = ''  # Replaced with the generated import name below.
                for managed in tables['managed_attachments']:
                    files.check_duplicate(connection,managed['sha256'])
                    old_name = managed['stored_name']
                    managed['stored_name'] = uuid4().hex + Path(old_name).suffix
                    attachment = next(row for row in tables['attachments'] if row['attachment_id'] == managed['attachment_id'])
                    attachment['generated_stored_name'] = managed['stored_name']
                    files.root.mkdir(parents=True, exist_ok=True)
                    target = files._path(managed['stored_name'])
                    created.append(target)
                    with target.open('xb') as stream:
                        stream.write(members['attachments/' + old_name])
                        stream.flush()
                        import os
                        os.fsync(stream.fileno())
                for table in INSERT_ORDER:
                    columns = [row[1] for row in connection.execute('PRAGMA table_info("' + table + '")')]
                    sql = 'INSERT INTO "' + table + '" (' + ','.join('"' + col + '"' for col in columns) + ') VALUES (' + ','.join('?' for col in columns) + ')'
                    for row in tables[table]:
                        connection.execute(sql, [row[col] for col in columns])
                bundle_id = tables['referral_bundles'][0]['bundle_id']
                connection.execute("INSERT INTO audit_events(audit_event_id,bundle_id,timestamp,action,entity_type,entity_id,actor_label,result) VALUES (?,?,?,'import passport','referral',?,'device user','success')",
                    (RecoveryService.maximum_id(connection,'audit_events','audit_event_id')+1,bundle_id, datetime.now(timezone.utc).isoformat(), bundle_id))
                check_database(connection)
            return bundle_id
        except Exception:
            for path in created:
                try:
                    path.unlink(missing_ok=True)
                except OSError as error:
                    from sehatraasta.storage.errors import log_storage_error
                    log_storage_error(self.database, 'passport_cleanup', error)
            raise
        finally:
            connection.close()
