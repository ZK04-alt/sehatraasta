"""Publish verified public iPhone assets without switching the application branch."""
import argparse
from hashlib import sha256
import json
import os
from pathlib import Path, PurePosixPath
import subprocess
from tempfile import TemporaryDirectory

ROOT = Path(__file__).resolve().parents[1]
APK = 'https://github.com/ZK04-alt/sehatraasta/releases/download/v1.6.0/SehatRaasta-1.6.0.apk'


def git(repository, *args, data=None, env=None):
    return subprocess.check_output(['git', *args], cwd=repository, input=data, env=env)


def landing_pages(index, privacy):
    old = '<strong>SehatRaasta 1.6.0</strong> by Zunair Ali Khan.'
    new = '<strong>SehatRaasta 1.6.0</strong>'
    if old not in index and new not in index:
        raise ValueError('unexpected landing page')
    index = index.replace(old, new)
    index = index.replace('together on an Android phone.', 'together on an Android phone or iPhone.')
    action = '<h2>Use on iPhone</h2><p><a class="download" href="iphone/">Use on iPhone</a></p><ol><li>Open this page in Safari on the iPhone.</li><li>Tap Use on iPhone, then tap Share and Add to Home Screen.</li><li>Open SehatRaasta from the new icon. Stay online until setup finishes.</li></ol><p>After setup, the app works offline. Save regular backups in Files. Clearing website data can remove saved records. This is a Home Screen web app, not an App Store download.</p>'
    if 'href="iphone/"' not in index:
        index = index.replace('<h2>Where records stay</h2>', action + '<h2>Where records stay</h2>')
    index = index.replace('Updated 9 October 2026.', 'Updated 12 October 2026.')
    if APK not in index or 'https://github.com/ZK04-alt/sehatraasta/tree/main' not in index or 'href="iphone/"' not in index:
        raise ValueError('landing links changed')
    browser = '<h2>Installed iPhone web app</h2><p>The iPhone version stores records and selected originals locally in browser storage (IndexedDB). Its Python application runs on the device. No patient-record server, account or automatic cloud synchronisation is added.</p><p>Initial setup downloads public application files from GitHub Pages. Later app updates also need internet. Record forms, searches, originals and exports are processed locally, not sent to GitHub. GitHub can still process requests for public app assets under its own privacy policy.</p><p>Install from Safari using Add to Home Screen before entering records. Safari and the installed app may have separate records. Browser storage is different from Android app-private storage: clearing website data or browser/OS eviction can remove it. A persistent-storage request is not a guarantee. Keep regular full backups in Files and check restored copies.</p><p>Removing an item inside the app keeps it recoverable until permanent deletion is confirmed. Clearing website data is not the same action and cannot be undone by Removed items. Exports and backups are not encrypted by SehatRaasta. Explicitly saving to a cloud-backed folder or sharing with another app uses that provider, not automatic SehatRaasta upload.</p>'
    if '<h2>Installed iPhone web app</h2>' not in privacy:
        privacy = privacy.replace('<h2>Camera and selected files</h2>', browser + '<h2>Camera and selected files</h2>')
    privacy = privacy.replace('copies are stored in app-private storage with generated names', 'copies are stored locally with generated names')
    privacy = privacy.replace('Updated 8 October 2026.', 'Updated 12 October 2026.')
    return index.encode(), privacy.encode()


def verified_assets(build):
    build = Path(build).resolve()
    manifest = json.loads((build / 'asset-manifest.json').read_text(encoding='utf-8'))
    assets = {'asset-manifest.json': (build / 'asset-manifest.json').read_bytes()}
    for item in manifest['assets']:
        name = item['path']
        path = PurePosixPath(name)
        if path.is_absolute() or '..' in path.parts or not name or any(char in name for char in '\\\r\n\x00') or name in assets:
            raise ValueError('invalid build asset')
        file = build / name
        if file.is_symlink() or file.resolve() != file:
            raise ValueError('invalid build asset')
        content = file.read_bytes()
        if len(content) != item['size'] or sha256(content).hexdigest() != item['sha256']:
            raise ValueError('build integrity failed')
        assets[name] = content
    actual = {file.relative_to(build).as_posix() for file in build.rglob('*') if file.is_file()}
    if actual != set(assets):
        raise ValueError('unexpected build file')
    return manifest, assets


def publish_iphone(build: Path, expected_website_head: str, repository=ROOT, remote='origin') -> str:
    repository = Path(repository).resolve()
    current = git(repository, 'ls-remote', '--heads', remote, 'refs/heads/website').decode().split()
    if not current or current[0] != expected_website_head:
        raise ValueError('website branch changed; inspect before publishing')
    manifest, assets = verified_assets(build)
    revision = git(repository, 'rev-parse', 'HEAD').decode().strip()
    if manifest['source_revision'] != revision:
        raise ValueError('build source does not match this branch')
    if git(repository, 'status', '--porcelain', '--untracked-files=all', '--', 'src/sehatraasta', 'browser', 'scripts/build_iphone.py').strip():
        raise ValueError('commit application changes before publication')
    # Shallow source checkouts may not have the independent website objects.
    git(repository, 'fetch', '--no-tags', remote, 'refs/heads/website')
    refreshed = git(repository, 'ls-remote', '--heads', remote, 'refs/heads/website').decode().split()
    if not refreshed or refreshed[0] != expected_website_head:
        raise ValueError('website branch changed; inspect before publishing')
    index = git(repository, 'show', expected_website_head + ':index.html').decode()
    privacy = git(repository, 'show', expected_website_head + ':privacy.html').decode()
    index, privacy = landing_pages(index, privacy)
    additions = {'index.html': index, 'privacy.html': privacy,
                 **{'iphone/' + name: content for name, content in assets.items()}}
    scratch = repository / 'tmp'
    scratch.mkdir(exist_ok=True)
    with TemporaryDirectory(prefix='iphone-publish-', dir=scratch) as directory:
        env = dict(os.environ, GIT_INDEX_FILE=str(Path(directory) / 'index'))
        git(repository, 'read-tree', expected_website_head, env=env)
        old = git(repository, 'ls-tree', '-r', '--name-only', expected_website_head, '--', 'iphone/').decode().splitlines()
        for start in range(0, len(old), 60):
            git(repository, 'update-index', '--force-remove', '--', *old[start:start + 60], env=env)
        entries = bytearray()
        for name, content in additions.items():
            blob = git(repository, 'hash-object', '-w', '--stdin', data=content).decode().strip()
            entries.extend(('100644 ' + blob + '\t' + name + '\0').encode())
        git(repository, 'update-index', '-z', '--index-info', data=bytes(entries), env=env)
        tree = git(repository, 'write-tree', env=env).decode().strip()
        commit = git(repository, 'commit-tree', tree, '-p', expected_website_head,
                     '-m', 'added iPhone Home Screen app').decode().strip()
        # A concurrent branch change rejects this normal push; never force it.
        subprocess.run(['git', 'push', remote, commit + ':refs/heads/website'], cwd=repository, check=True)
    return commit


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--build', type=Path, required=True)
    parser.add_argument('--expected-website-head', required=True)
    args = parser.parse_args()
    print('Published website commit', publish_iphone(args.build, args.expected_website_head))
