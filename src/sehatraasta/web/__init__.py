"""Local referral workspace with request validation and private storage."""
from pathlib import Path
import secrets
import sqlite3
from time import time
from urllib.parse import urlsplit
from urllib.parse import urlencode

from flask import Flask, g, request, session, render_template
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired
from werkzeug.exceptions import HTTPException, SecurityError

from sehatraasta.presentation.catalogs import LANGUAGES, translate
from sehatraasta.presentation.errors import error_from_exception
from sehatraasta.storage.errors import StorageError, log_storage_error


def create_app(config=None):
    from . import messages
    app = Flask(__name__)
    app.config.from_mapping(SECRET_KEY=secrets.token_hex(32), DATABASE=Path('instance/sehatraasta.sqlite').resolve(),
        DEBUG=False, MAX_CONTENT_LENGTH=102 * 1024 * 1024, MAX_FORM_MEMORY_SIZE=128 * 1024,
        MAX_FORM_PARTS=100, SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE='Strict',
        TRUSTED_HOSTS=['127.0.0.1', 'localhost'], FORM_MAX_AGE=3600)
    if config:
        app.config.update(config)
    app.extensions['used_forms'] = {}
    from .routes import pages
    app.register_blueprint(pages)
    from .passport_messages import MESSAGES as passport_messages
    from .report_messages import MESSAGES as report_messages
    from .remediation_messages import MESSAGES as remediation_messages
    from sehatraasta.presentation.catalogs import MESSAGES
    MESSAGES.update(passport_messages)
    MESSAGES.update(report_messages)
    MESSAGES.update(remediation_messages)
    from sehatraasta.domain.medical_dates import visit_sort_key
    app.jinja_env.filters['sort_visits'] = lambda visits: sorted(visits, key=visit_sort_key)

    def signer():
        return URLSafeTimedSerializer(app.secret_key, salt='sr-form')

    def form_token(path=None, errors=None, visit_context=None):
        if 'csrf' not in session:
            session['csrf'] = secrets.token_hex(24)
        return signer().dumps({'session': session['csrf'], 'path': path or request.path,
                               'nonce': secrets.token_hex(16), 'errors': errors or [], 'visit_context':visit_context})

    @app.before_request
    def prepare_request():
        language = request.args.get('lang', session.get('lang', 'en'))
        if request.method == 'POST':
            language = request.form.get('lang', language)
        g.language = language if language in LANGUAGES else 'en'
        g.form_nonce = None
        g.previous_errors = []
        g.expected_visit = None
        g.enforce_visit_context = False
        if request.remote_addr not in (None, '127.0.0.1', '::1'):
            return render_template('error.html', title='error.local', code='error.local', status=403), 403
        if request.method == 'POST':
            origin = request.headers.get('Origin')
            if origin and (urlsplit(origin).netloc != request.host or urlsplit(origin).scheme != request.scheme):
                return render_template('error.html', title='error.form', code='error.form', status=403), 403
            try:
                token = signer().loads(request.form.get('csrf', ''), max_age=app.config['FORM_MAX_AGE'])
                if token['session'] != session.get('csrf') or token['path'] != request.path:
                    raise BadSignature('invalid')
            except (BadSignature, SignatureExpired, KeyError):
                return render_template('error.html', title='error.form', code='error.form', status=400), 400
            used = app.extensions['used_forms']
            for key, timestamp in list(used.items()):
                if time() - timestamp > app.config['FORM_MAX_AGE']:
                    del used[key]
            if token['nonce'] in used:
                return render_template('error.html', title='error.duplicate', code='error.duplicate', status=409), 409
            g.form_nonce = token['nonce']
            g.previous_errors = token.get('errors', [])
            g.expected_visit = token.get('visit_context')
        session['lang'] = g.language

    @app.context_processor
    def context():
        language = getattr(g, 'language', 'en')
        language_urls = {}
        for code in LANGUAGES:
            parameters = request.args.to_dict(flat=False)
            parameters['lang'] = [code]
            language_urls[code] = request.path + '?' + urlencode(parameters, doseq=True)
        def medical_date_label(visit):
            if visit.medical_date_kind == 'unknown':
                return translate('date.unknown', language)
            label = translate('date.' + visit.medical_date_kind, language)
            return label + ': ' + visit.medical_date_value
        def document_date_label(document):
            return document.date.isoformat() if document.date else translate('date.unknown', language)
        return dict(t=lambda key: translate(key, language), lang=language,
                    medical_date_label=medical_date_label, document_date_label=document_date_label,
                    direction=LANGUAGES[language][1], languages=LANGUAGES,
                    language_urls=language_urls, form_token=form_token)

    @app.after_request
    def headers(response):
        response.headers['Content-Security-Policy'] = "default-src 'none'; style-src 'self'; script-src 'self'; worker-src 'self'; img-src 'self' data:; font-src 'self' data:; connect-src 'self'; form-action 'self'; base-uri 'none'; frame-ancestors 'none'"
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['X-Frame-Options'] = 'DENY'
        # Keep same-origin form Origin headers usable; send no referrer off-site.
        response.headers['Referrer-Policy'] = 'same-origin'
        response.headers['Cache-Control'] = 'no-store'
        return response

    @app.errorhandler(Exception)
    def handle_error(error):
        if isinstance(error, SecurityError):
            # Rejected hosts have no URL adapter. Do not call url_for here.
            return render_template('rejected.html'), 400
        if isinstance(error, HTTPException):
            status = error.code
            code = 'error.not_found' if status == 404 else 'error.too_large' if status == 413 else 'error.form'
        elif isinstance(error, (StorageError, sqlite3.Error, OSError)):
            status, code = 503, 'error.unavailable'
        elif isinstance(error, ValueError):
            presented = error_from_exception(error)
            status, code = presented.status, presented.code
        else:
            status, code = 500, 'error.unexpected'
        if status >= 500:
            log_storage_error(app.config['DATABASE'], 'web_request', error)
        return render_template('error.html', title=code, code=code, status=status), status

    return app
