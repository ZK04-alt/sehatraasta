"""Build a public, self-hosted browser package. Never package local records."""
import argparse
from io import BytesIO
from hashlib import sha256
from importlib import metadata
import json
from pathlib import Path, PurePosixPath
import subprocess
from urllib.request import urlopen
from zipfile import ZipFile, ZIP_DEFLATED, ZipInfo


ROOT = Path(__file__).resolve().parents[1]
RUNTIME_VERSION = '314.0.7'
RUNTIME_URL = 'https://cdn.jsdelivr.net/pyodide/v314.0.7/full/'
CORE_FILES = ['pyodide.mjs', 'pyodide.asm.mjs', 'pyodide.asm.wasm',
              'python_stdlib.zip', 'pyodide-lock.json', 'LICENSE',
              'CPython-LICENSE.txt', 'Emscripten-LICENSE.txt']
CORE_LICENSE_URLS = {
    'LICENSE': 'https://raw.githubusercontent.com/pyodide/pyodide/314.0.7/LICENSE',
    'CPython-LICENSE.txt': 'https://raw.githubusercontent.com/python/cpython/v3.14.2/LICENSE',
    'Emscripten-LICENSE.txt': 'https://raw.githubusercontent.com/emscripten-core/emscripten/5.0.3/LICENSE',
}
DEPENDENCIES = {
    'flask': ('3.1.3', 'flask/'), 'werkzeug': ('3.1.8', 'werkzeug/'),
    'jinja2': ('3.1.6', 'jinja2/'), 'markupsafe': ('3.0.3', 'markupsafe/'),
    'itsdangerous': ('2.2.0', 'itsdangerous/'), 'click': ('8.5.0', 'click/'),
    'blinker': ('1.9.0', 'blinker/'), 'qrcode': ('8.2', 'qrcode/'),
    'pypng': ('0.20220715.0', 'png.py'),
}


def describe(path, content):
    return {'path': path, 'size': len(content), 'sha256': sha256(content).hexdigest()}


def prepare_runtime(cache):
    """Download once during building, never during medical-record operations."""
    cache = Path(cache)
    cache.mkdir(parents=True, exist_ok=True)
    lock_path = cache / 'runtime-lock.json'
    previous = json.loads(lock_path.read_text(encoding='utf-8')) if lock_path.exists() else {}
    expected = {item['path']: item for item in previous.get('assets', [])}
    pinned_path = ROOT / 'browser/runtime-lock.json'
    if pinned_path.exists():
        pinned = json.loads(pinned_path.read_text(encoding='utf-8'))
        expected = {item['path']: item for item in pinned['assets']}
    assets = []
    for name in CORE_FILES:
        path = cache / name
        if path.exists():
            content = path.read_bytes()
        else:
            url = CORE_LICENSE_URLS.get(name, RUNTIME_URL + name)
            with urlopen(url, timeout=60) as response:
                content = response.read()
        if name in expected and describe(name, content) != expected[name]:
            raise ValueError('runtime integrity: changed file')
        (cache / name).write_bytes(content)
        assets.append(describe(name, content))
    lock = {'version': RUNTIME_VERSION, 'assets': assets}
    lock_path.write_text(json.dumps(lock, indent=2) + '\n', encoding='utf-8')
    return cache


def runtime_assets(runtime_dir):
    lock = json.loads((runtime_dir / 'runtime-lock.json').read_text(encoding='utf-8'))
    if lock.get('version') != RUNTIME_VERSION:
        raise ValueError('runtime integrity: incorrect version')
    assets = {}
    for item in lock['assets']:
        name = item['path']
        if name not in CORE_FILES or name in assets:
            raise ValueError('runtime integrity: unexpected file')
        content = (runtime_dir / name).read_bytes()
        if describe(name, content) != item:
            raise ValueError('runtime integrity: changed file')
        assets[name] = content
    if set(assets) != set(CORE_FILES):
        raise ValueError('runtime integrity: incomplete runtime')
    return assets


def dependency_files():
    files = {}
    for name, (version, prefix) in DEPENDENCIES.items():
        distribution = metadata.distribution(name)
        if distribution.version != version:
            raise ValueError('Install the pinned dependency version: ' + name + '==' + version)
        licenses = 0
        for item in distribution.files or []:
            path = item.as_posix()
            lower = path.lower()
            if any(word in lower for word in ('license', 'licence', 'copying')):
                files['licenses/' + name + '/' + Path(path).name] = distribution.locate_file(item).read_bytes()
                licenses += 1
            elif path.startswith(prefix) and path.endswith(('.py', '.json', '.txt', '.typed')):
                files[path] = distribution.locate_file(item).read_bytes()
        if not licenses:
            raise ValueError('Dependency licence is missing: ' + name)
    return files


def git(command):
    return subprocess.check_output(['git', *command], cwd=ROOT)


def application_files(source_ref):
    files = {}
    content = git(['-c', 'core.autocrlf=false', 'archive', '--format=zip', source_ref, 'src/sehatraasta/'])
    with ZipFile(BytesIO(content)) as archive:
        for item in archive.infolist():
            path = item.filename
            if item.is_dir() or path.endswith(('.pyc', '.pyd', '.sqlite')) or '__pycache__' in path.split('/'):
                continue
            if not path.startswith('src/sehatraasta/'):
                raise ValueError('Unexpected application source path')
            files[path.removeprefix('src/')] = archive.read(item)
    if 'sehatraasta/browser_runtime.py' not in files:
        raise ValueError('Browser adapter is not committed in the selected source revision')
    files.update(dependency_files())
    return files


def write_archive(path, files):
    with ZipFile(path, 'w', compression=ZIP_DEFLATED, compresslevel=9) as archive:
        for name, content in sorted(files.items()):
            info = ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            archive.writestr(info, content)


def build_iphone(destination: Path, source_ref: str = 'HEAD', runtime_dir=None) -> dict:
    runtime_dir = Path(runtime_dir) if runtime_dir else prepare_runtime(ROOT / 'output/iphone-runtime')
    runtime = runtime_assets(runtime_dir)
    files = application_files(source_ref)
    destination = Path(destination).resolve()
    if destination.exists():
        raise ValueError('Build destination already exists; use a new empty location')
    destination.mkdir(parents=True)
    write_archive(destination / 'application.zip', files)
    public = {'runtime/' + name: data for name, data in runtime.items()}
    prefix = 'sehatraasta/web/static/'
    for name, content in files.items():
        if name.startswith(prefix):
            public['app/static/' + name[len(prefix):]] = content
    browser_source = ROOT / 'browser'
    if browser_source.exists():
        for path in sorted(browser_source.rglob('*')):
            if path.is_file() and path.suffix in ('.html', '.js', '.mjs', '.css', '.webmanifest', '.png', '.svg', '.txt'):
                public[path.relative_to(browser_source).as_posix()] = path.read_bytes()
    identity = sha256()
    for name, content in sorted(public.items()):
        identity.update(name.encode() + b'\0' + sha256(content).digest())
    asset_set = identity.hexdigest()
    if 'service-worker.mjs' in public:
        public['service-worker.mjs'] = public['service-worker.mjs'].replace(b'__BUILD_ID__', asset_set.encode())
    for name, content in public.items():
        if PurePosixPath(name).is_absolute() or '..' in PurePosixPath(name).parts:
            raise ValueError('Invalid public asset path')
        path = destination / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
    assets = [describe(path.relative_to(destination).as_posix(), path.read_bytes())
              for path in sorted(destination.rglob('*')) if path.is_file()]
    revision = git(['rev-parse', source_ref]).decode().strip()
    manifest = {'version': '1.6.0-iphone', 'asset_set': asset_set, 'runtime': RUNTIME_VERSION, 'source_revision': revision,
                'dependencies': {name: pair[0] for name, pair in DEPENDENCIES.items()}, 'assets': assets}
    (destination / 'asset-manifest.json').write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8')
    return manifest


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--source-ref', default='HEAD')
    args = parser.parse_args()
    result = build_iphone(args.output, args.source_ref)
    print('Built', len(result['assets']), 'public assets from', result['source_revision'][:7])
