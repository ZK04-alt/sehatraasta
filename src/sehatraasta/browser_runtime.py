"""Socket-free Flask transport inside a local browser worker.

The worker commits collect_files() before delivering a response. Session
cookies stay in the private filesystem and never become network cookies.
"""
from http.cookies import SimpleCookie
from io import BytesIO
import json
from pathlib import Path
import secrets
from urllib.parse import unquote, urlsplit

from werkzeug.test import EnvironBuilder

from sehatraasta.services.bundle_service import BundleService
from sehatraasta.storage import SQLiteRepository
from sehatraasta.web import create_app


class BrowserApplication:
    def __init__(self, root: Path, mount: str = '/sehatraasta/iphone/app',
                 origin: str = 'https://zk04-alt.github.io'):
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        if not mount.startswith('/') or mount.endswith('/') or '\\' in mount:
            raise ValueError('Invalid application mount')
        parsed = urlsplit(origin)
        if parsed.scheme not in ('https', 'http') or not parsed.hostname or parsed.path:
            raise ValueError('Invalid application origin')
        if parsed.username or parsed.password or parsed.query or parsed.fragment:
            raise ValueError('Invalid application origin')
        self.mount, self.origin = mount, origin
        secret = self.root / '.session-key'
        if not secret.exists():
            secret.write_text(secrets.token_hex(32), encoding='ascii')
        self.cookie_path = self.root / '.browser-cookies.json'
        self.cookies = json.loads(self.cookie_path.read_text(encoding='utf-8')) if self.cookie_path.exists() else {}
        pointer = self.root / 'active-dataset'
        database = self.root / 'sehatraasta.sqlite'
        if pointer.exists():
            relative = Path(pointer.read_text(encoding='utf-8'))
            database = (self.root / relative).resolve()
            if relative.is_absolute() or not database.is_relative_to(self.root) or not database.is_file():
                raise ValueError('Invalid active dataset')
        self.app = create_app({
            'DATABASE': database, 'SECRET_KEY': secret.read_text(encoding='ascii'),
            'BROWSER_APP': True, 'TRUSTED_HOSTS': [parsed.hostname],
        })
        self.app.extensions['bundles'] = BundleService(SQLiteRepository(database))

        def activate_restore(name):
            restored = self.app.config['DATABASE'].parent / 'restores' / name / 'sehatraasta.sqlite'
            restored = restored.resolve()
            if not restored.is_relative_to(self.root) or not restored.is_file():
                raise ValueError('Invalid active dataset')
            service = BundleService(SQLiteRepository(restored))
            pending = pointer.with_suffix('.tmp')
            pending.write_text(restored.relative_to(self.root).as_posix(), encoding='utf-8')
            pending.replace(pointer)
            self.app.config.update(DATABASE=restored, DATASET_GENERATION=secrets.token_hex(24))
            self.app.extensions['bundles'] = service

        self.app.config['ACTIVATE_RESTORE'] = activate_restore

    def handle(self, method: str, path: str, query: str,
               headers: list[tuple[str, str]], body: bytes) -> dict:
        """Run one scoped request. This transport cannot contact a server."""
        if path == self.mount:
            suffix = '/'
        elif path.startswith(self.mount + '/'):
            suffix = path[len(self.mount):]
        else:
            return self._rejected()
        decoded = suffix
        for _ in range(5):
            previous = decoded
            decoded = unquote(decoded)
            if decoded == previous:
                break
        if ('\\' in decoded or '\x00' in decoded or '//' in decoded or '%' in decoded
                or any(part in ('.', '..') for part in decoded.split('/'))):
            return self._rejected()
        if method not in ('GET', 'HEAD', 'POST'):
            return self._rejected()
        allowed_headers = [(key, value) for key, value in headers
                           if key.lower() not in ('cookie', 'host', 'content-length', 'connection')]
        builder = EnvironBuilder(method=method, path=decoded, base_url=self.origin + self.mount + '/',
                                 query_string=query, headers=allowed_headers,
                                 input_stream=BytesIO(body), content_length=len(body))
        environ = builder.get_environ()
        environ['SCRIPT_NAME'] = self.mount
        environ['REMOTE_ADDR'] = '127.0.0.1'
        environ['HTTP_COOKIE'] = '; '.join(key + '=' + value for key, value in self.cookies.items())
        response = {}

        def start_response(status, response_headers, exc_info=None):
            response['status'] = int(status.split(' ', 1)[0])
            response['headers'] = []
            for key, value in response_headers:
                if key.lower() == 'set-cookie':
                    parsed = SimpleCookie()
                    parsed.load(value)
                    for name, cookie in parsed.items():
                        if cookie['max-age'] == '0':
                            self.cookies.pop(name, None)
                        else:
                            self.cookies[name] = cookie.value
                else:
                    response['headers'].append((key, value))

        result = self.app(environ, start_response)
        try:
            response['body'] = b''.join(result)
        finally:
            if hasattr(result, 'close'):
                result.close()
            builder.close()
        pending = self.cookie_path.with_suffix('.tmp')
        pending.write_text(json.dumps(self.cookies), encoding='utf-8')
        pending.replace(self.cookie_path)
        return response

    def collect_files(self) -> list[tuple[str, bytes]]:
        files = []
        for path in sorted(self.root.rglob('*')):
            if path.is_symlink():
                raise ValueError('Invalid private storage path')
            if path.is_file():
                files.append((path.relative_to(self.root).as_posix(), path.read_bytes()))
        return files

    @staticmethod
    def _rejected():
        return {'status': 400, 'headers': [('Content-Type', 'text/plain; charset=utf-8'),
                                         ('Cache-Control', 'no-store')],
                'body': b'This request cannot be opened.'}
