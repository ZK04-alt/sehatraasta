"""Materialize text captured from actual v1.5 into isolated test artifacts."""
import hashlib
from io import BytesIO
import json
from pathlib import Path
import sqlite3
from zipfile import ZipFile, ZIP_DEFLATED

FIXTURE = Path(__file__).with_name('v15_artifacts.json')
MIGRATIONS = Path(__file__).parents[2] / 'src/sehatraasta/storage/migrations'


def fixture():
    return json.loads(FIXTURE.read_text(encoding='utf-8'))


def members(kind):
    return {name: bytes.fromhex(value['hex']) if name.startswith('attachments/') else
            json.dumps(value, ensure_ascii=False, indent=2).encode('utf-8')
            for name, value in fixture()[kind].items() if name != 'manifest.json'}


def archive(kind):
    contents = members(kind)
    output = BytesIO()
    with ZipFile(output, 'w', ZIP_DEFLATED) as target:
        target.writestr('manifest.json', json.dumps({name: hashlib.sha256(value).hexdigest()
            for name, value in contents.items()}, ensure_ascii=False, indent=2))
        for name, value in contents.items():
            target.writestr(name, value)
    return output.getvalue()


def database(folder):
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / 'v15.sqlite'
    data = fixture()
    connection = sqlite3.connect(target)
    try:
        for name, digest in data['migrations_lf'].items():
            source = (MIGRATIONS / name).read_bytes().replace(b'\r\n', b'\n')
            assert hashlib.sha256(source).hexdigest() == digest, 'Historical migration changed'
            connection.executescript(source.decode('utf-8'))
        connection.execute('DELETE FROM schema_version')
        for name, rows in data['backup']['dataset.json']['tables'].items():
            for row in rows:
                columns = list(row)
                connection.execute('INSERT INTO "' + name + '" (' +
                    ','.join('"' + column + '"' for column in columns) + ') VALUES (' +
                    ','.join('?' for _ in columns) + ')', [row[column] for column in columns])
        connection.commit()
    finally:
        connection.close()
    for name, content in members('backup').items():
        if name.startswith('attachments/'):
            path = folder / name
            path.parent.mkdir(exist_ok=True)
            path.write_bytes(content)
    return target
