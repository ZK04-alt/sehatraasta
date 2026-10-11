"""Packaging checks: only public source and explicitly pinned dependencies."""
from hashlib import sha256
import importlib.util
import json
from pathlib import Path
import subprocess
from zipfile import ZipFile

import pytest


ROOT = Path(__file__).resolve().parents[2]
CORE_FILES = ['pyodide.mjs', 'pyodide.asm.mjs', 'pyodide.asm.wasm',
              'python_stdlib.zip', 'pyodide-lock.json', 'LICENSE',
              'CPython-LICENSE.txt', 'Emscripten-LICENSE.txt']


def builder():
    source = ROOT / 'scripts/build_iphone.py'
    assert source.is_file(), 'Offline iPhone packager is missing'
    spec = importlib.util.spec_from_file_location('iphone_build', source)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def runtime_files(tmp_path):
    # Controlled packaging inputs only. Actual WASM execution has its own gate.
    root = tmp_path / 'runtime'
    root.mkdir()
    assets = []
    for name in CORE_FILES:
        content = ('Public fixture for ' + name).encode()
        (root / name).write_bytes(content)
        assets.append({'path': name, 'size': len(content), 'sha256': sha256(content).hexdigest()})
    (root / 'runtime-lock.json').write_text(json.dumps({'version': '314.0.7', 'assets': assets}))
    return root


def build(tmp_path, runtime_files):
    destination = tmp_path / 'public'
    manifest = builder().build_iphone(destination, runtime_dir=runtime_files)
    return destination, manifest


def test_package_excludes_local_records(tmp_path, runtime_files):
    destination, _ = build(tmp_path, runtime_files)
    with ZipFile(destination / 'application.zip') as archive:
        names = archive.namelist()
        assert 'sehatraasta/browser_runtime.py' in names
        assert 'sehatraasta/storage/migrations/006_removed_items.sql' in names
        assert 'sehatraasta/web/templates/document_capture.html' in names
        assert all(not name.startswith(('instance/', 'docs/', 'tests/', '.git/')) for name in names)
        assert not any(name.endswith(('.sqlite', '.pyd', '.pyc', '.apk')) for name in names)
        assert not any('.session-key' in name or 'active-dataset' in name for name in names)


def test_package_includes_runtime_licenses(tmp_path, runtime_files):
    destination, manifest = build(tmp_path, runtime_files)
    assert (destination / 'runtime/LICENSE').is_file()
    assert (destination / 'runtime/CPython-LICENSE.txt').is_file()
    assert (destination / 'runtime/Emscripten-LICENSE.txt').is_file()
    with ZipFile(destination / 'application.zip') as archive:
        names = archive.namelist()
        for library in ['flask', 'werkzeug', 'jinja2', 'markupsafe', 'itsdangerous',
                        'click', 'blinker', 'qrcode', 'pypng']:
            assert any(name.startswith('licenses/' + library + '/') for name in names), library
        assert 'markupsafe/_native.py' in names
    assert manifest['dependencies']['flask'] == '3.1.3'


def test_package_hashes_all_assets(tmp_path, runtime_files):
    destination, manifest = build(tmp_path, runtime_files)
    paths = {item['path'] for item in manifest['assets']}
    assert 'application.zip' in paths
    assert 'app/static/vendor/pdfjs/pdf.worker.min.mjs' in paths
    assert 'runtime/pyodide.asm.wasm' in paths
    for item in manifest['assets']:
        content = (destination / item['path']).read_bytes()
        assert len(content) == item['size']
        assert sha256(content).hexdigest() == item['sha256']
    actual = {path.relative_to(destination).as_posix() for path in destination.rglob('*') if path.is_file()}
    assert actual == paths | {'asset-manifest.json'}


def test_package_preserves_source(tmp_path, runtime_files):
    original = (ROOT / 'src/sehatraasta/browser_runtime.py').read_bytes()
    head = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
    destination, manifest = build(tmp_path, runtime_files)
    assert manifest['source_revision'] == head
    assert (ROOT / 'src/sehatraasta/browser_runtime.py').read_bytes() == original
    with ZipFile(destination / 'application.zip') as archive:
        committed = subprocess.check_output(['git', 'show', head + ':src/sehatraasta/browser_runtime.py'], cwd=ROOT)
        assert archive.read('sehatraasta/browser_runtime.py') == committed


def test_modified_runtime_is_rejected_before_output(tmp_path, runtime_files):
    (runtime_files / 'pyodide.asm.wasm').write_bytes(b'Changed bytes')
    destination = tmp_path / 'public'
    with pytest.raises(ValueError, match='runtime integrity'):
        builder().build_iphone(destination, runtime_dir=runtime_files)
    assert not destination.exists()


def test_python_only_change_has_a_new_offline_cache_identity(tmp_path, runtime_files, monkeypatch):
    module = builder()
    first = module.build_iphone(tmp_path / 'first', runtime_dir=runtime_files)
    original = module.application_files

    def changed(ref):
        files = original(ref)
        files['sehatraasta/browser_runtime.py'] += b'\n# Changed Python fixture\n'
        return files

    monkeypatch.setattr(module, 'application_files', changed)
    second = module.build_iphone(tmp_path / 'second', runtime_dir=runtime_files)
    assert first['asset_set'] != second['asset_set']
