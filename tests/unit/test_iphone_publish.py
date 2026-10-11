"""Publication boundaries, tested with a local bare Git remote."""
from hashlib import sha256
from importlib.util import module_from_spec, spec_from_file_location
import json
from pathlib import Path
import subprocess

import pytest

ROOT = Path(__file__).resolve().parents[2]
APK = 'https://github.com/ZK04-alt/sehatraasta/releases/download/v1.6.0/SehatRaasta-1.6.0.apk'


def publisher():
    path = ROOT / 'scripts/publish_iphone.py'
    assert path.is_file(), 'iPhone publisher is missing'
    spec = spec_from_file_location('iphone_publisher', path)
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def git(root, *args):
    return subprocess.check_output(['git', *args], cwd=root).decode().strip()


@pytest.fixture
def website(tmp_path):
    remote, repo, build = [tmp_path / name for name in ('remote.git', 'checkout', 'build')]
    remote.mkdir(); repo.mkdir(); build.mkdir()
    git(remote, 'init', '--bare', '-q')
    git(repo, 'init', '-q', '-b', 'website')
    git(repo, 'config', 'user.name', 'Publication Test')
    git(repo, 'config', 'user.email', 'fixture@example.invalid')
    git(repo, 'config', 'core.autocrlf', 'false')
    git(repo, 'remote', 'add', 'origin', str(remote))
    for name in ('.nojekyll', 'index.html', 'privacy.html', 'logo.svg', 'style.css'):
        content = subprocess.check_output(['git', 'show', 'origin/website:' + name], cwd=ROOT)
        (repo / name).write_bytes(content)
    git(repo, 'add', '.')
    git(repo, 'commit', '-qm', 'website fixture')
    git(repo, 'push', '-q', 'origin', 'website')
    head = git(repo, 'rev-parse', 'HEAD')
    (build / 'index.html').write_text('<title>SehatRaasta</title>')
    content = (build / 'index.html').read_bytes()
    (build / 'asset-manifest.json').write_text(json.dumps({'source_revision': head,
        'assets': [{'path': 'index.html', 'size': len(content), 'sha256': sha256(content).hexdigest()}]}))
    return repo, remote, build, head


def test_iphone_landing_preserves_android_and_other_attribution(website):
    repo, remote, build, head = website
    commit = publisher().publish_iphone(build, head, repository=repo)
    index = git(remote, 'show', commit + ':index.html')
    privacy = git(remote, 'show', commit + ':privacy.html')
    assert APK in index and 'href="iphone/"' in index
    assert '<strong>SehatRaasta 1.6.0</strong> by Zunair Ali Khan.' not in index
    assert 'By Zunair Ali Khan' in index and 'm.zunairalikhan@gmail.com' in privacy
    assert 'https://github.com/ZK04-alt/sehatraasta/tree/main' in index
    assert 'Add to Home Screen' in index and 'Safari' in index
    assert 'browser storage' in privacy and 'clearing website data' in privacy
    for name in ('logo.svg', 'style.css', '.nojekyll'):
        assert git(remote, 'rev-parse', head + ':' + name) == git(remote, 'rev-parse', commit + ':' + name)
    assert git(repo, 'rev-parse', 'HEAD') == head
    assert git(repo, 'status', '--porcelain') == ''
    assert git(remote, 'rev-parse', 'website') == commit


def test_changed_remote_is_not_overwritten(website):
    repo, remote, build, head = website
    with pytest.raises(ValueError, match='website branch changed'):
        publisher().publish_iphone(build, '0' * 40, repository=repo)
    assert git(remote, 'rev-parse', 'website') == head


def test_damaged_build_cannot_be_published(website):
    repo, remote, build, head = website
    (build / 'index.html').write_text('Changed bytes')
    with pytest.raises(ValueError, match='build integrity'):
        publisher().publish_iphone(build, head, repository=repo)
    assert git(remote, 'rev-parse', 'website') == head


def test_unlisted_private_file_cannot_be_published(website):
    repo, remote, build, head = website
    (build / 'records.sqlite').write_bytes(b'Private fixture')
    with pytest.raises(ValueError, match='unexpected build file'):
        publisher().publish_iphone(build, head, repository=repo)
    assert git(remote, 'rev-parse', 'website') == head
