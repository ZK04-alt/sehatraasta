"""On-device HTTP transport. Only the app's private session can reach SR."""
from http.cookies import SimpleCookie
import hmac
import json
from pathlib import Path
import secrets
import threading

from werkzeug.serving import WSGIRequestHandler, make_server
from sehatraasta.web import create_app
from sehatraasta.services.bundle_service import BundleService
from sehatraasta.storage import SQLiteRepository

_server = None
_connection = None
_lock = threading.Lock()


class PrivateSession:
    def __init__(self, app, token):
        self.app, self.token = app, token

    def __call__(self, environ, start_response):
        cookies = SimpleCookie()
        try:
            cookies.load(environ.get('HTTP_COOKIE', ''))
            value = cookies['sr_device'].value if 'sr_device' in cookies else ''
        except Exception:
            value = ''
        if not hmac.compare_digest(value.encode('utf-8'), self.token.encode('ascii')):
            start_response('403 Forbidden', [('Content-Type', 'text/plain'), ('Cache-Control', 'no-store')])
            return [b'Access denied']
        return self.app(environ, start_response)


class QuietHandler(WSGIRequestHandler):
    def log(self, *args, **kwargs):
        pass


def start(directory, cache_directory=None):
    global _server, _connection
    with _lock:
        if _server:
            return _connection
        root = Path(directory) / 'records'
        root.mkdir(parents=True, exist_ok=True)
        secret = root / '.session-key'
        if not secret.exists():
            secret.write_text(secrets.token_hex(32), encoding='ascii')
        pointer = root / 'active-dataset'
        database = root / 'sehatraasta.sqlite'
        if pointer.exists():
            database = (root / pointer.read_text(encoding='utf-8')).resolve()
            if not database.is_relative_to(root.resolve()) or not database.is_file():
                raise ValueError('Invalid active dataset')
        app = create_app({'DATABASE': database,
                          'SECRET_KEY': secret.read_text(encoding='ascii'), 'ANDROID_APP': True})
        if cache_directory:
            def render_report(content):
                import base64
                from java import jclass
                renderer = jclass('org.sehatraasta.app.ReportRenderer')
                return json.loads(str(renderer.render(base64.b64encode(content).decode('ascii'), cache_directory)))
            app.config['RENDER_REPORT_PDF'] = render_report
        def activate_restore(name):
            database = app.config['DATABASE'].parent / 'restores' / name / 'sehatraasta.sqlite'
            service = BundleService(SQLiteRepository(database))
            pending = pointer.with_suffix('.tmp')
            pending.write_text(str(database.relative_to(root)), encoding='utf-8')
            pending.replace(pointer)
            app.config['DATABASE'] = database
            app.extensions['bundles'] = service
        app.config['ACTIVATE_RESTORE'] = activate_restore
        token = secrets.token_hex(32)
        _server = make_server('127.0.0.1', 0, PrivateSession(app, token),
                              threaded=False, request_handler=QuietHandler)
        threading.Thread(target=_server.serve_forever, daemon=True, name='sr-local').start()
        _connection = json.dumps({'origin': f'http://127.0.0.1:{_server.server_port}', 'token': token})
        return _connection
