"""Plain school-office form. Local learning lab, NOT the application web GUI.

Run from the repository root with PYTHONPATH=src. Uses no external resources.
"""
import argparse
from datetime import date
from html import escape
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
import re
import secrets
import sqlite3
from urllib.parse import parse_qs, urlsplit

from sehatraasta.presentation.catalogs import LANGUAGES, translate
from sehatraasta.presentation.errors import UIError


def validate(values):
    errors = []
    name = values.get("name", "")
    if not name.strip():
        errors.append(UIError("error.required", "name"))
    elif len(name) > 80:
        errors.append(UIError("error.name", "name"))
    text = values.get("date", "")
    if not text:
        errors.append(UIError("error.required", "date"))
    else:
        try:
            if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", text):
                raise ValueError()
            date.fromisoformat(text)
        except ValueError:
            errors.append(UIError("error.date", "date"))
    if values.get("synthetic") != "yes":
        errors.append(UIError("error.synthetic", "synthetic"))
    return errors


class AppointmentStore:
    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self.path)
        try:
            tables = {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")}
            if tables and tables != {'requests'}:
                raise ValueError('choose a separate lab database; existing database was not changed')
            with connection:
                connection.execute("CREATE TABLE IF NOT EXISTS requests (id INTEGER PRIMARY KEY, name TEXT NOT NULL, date TEXT NOT NULL, UNIQUE(name, date))")
        finally:
            connection.close()

    def save(self, values):
        errors = validate(values)
        if errors:
            return errors
        connection = sqlite3.connect(self.path)
        try:
            with connection:
                connection.execute("INSERT INTO requests(name, date) VALUES (?, ?)", (values["name"], values["date"]))
        except sqlite3.IntegrityError:
            return [UIError("error.duplicate", "name", 409)]
        finally:
            connection.close()
        return []

    def list_requests(self):
        connection = sqlite3.connect(self.path)
        try:
            return connection.execute("SELECT id, name, date FROM requests ORDER BY id").fetchall()
        finally:
            connection.close()


def shell(language, title_key, content, preview=False):
    title = escape(translate(title_key, language))
    direction = LANGUAGES[language][1]
    review = '' if language == 'en' else '<p class="warning">' + escape(translate('warning.review', language)) + '</p>'
    preview_text = '<p class="warning">' + escape(translate('state.preview', language)) + '</p>' if preview else ''
    return f'''<!doctype html><html lang="{language}" dir="{direction}">
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title><link rel="stylesheet" href="/tokens.css"></head><body>
<a class="skip" href="#main">{escape(translate('nav.skip', language))}</a>
<header><nav><a href="/?lang={language}">{escape(translate('lab.title', language))}</a>
<a href="/requests?lang={language}">{escape(translate('lab.list', language))}</a>
<a href="/states?lang={language}">{escape(translate('lab.states', language))}</a></nav>{review}</header>
<main id="main" tabindex="-1"><h1>{title}</h1><p class="warning">{escape(translate('lab.warning', language))}</p>
{preview_text}{content}</main></body></html>'''


def message_html(text):
    """Keep fixed date examples in reading order inside RTL sentences."""
    text = escape(text)
    for token in ('2026-09-20', 'YYYY-MM-DD'):
        text = text.replace(token, '<bdi dir="ltr">' + token + '</bdi>')
    return text


def form(language, token, values=None, errors=None, preview=False):
    values = values or {}
    errors = errors or []
    message = lambda key: message_html(translate(key, language))
    labels = {"name": "field.name", "date": "field.date", "synthetic": "field.confirm"}
    summary = ''
    if errors:
        summary = '<section class="summary" role="alert" aria-labelledby="error-heading" tabindex="-1" autofocus><h2 id="error-heading">' + message('error.summary') + '</h2><ul>'
        for error in errors:
            summary += f'<li><a href="#{error.field}">{message(labels[error.field])}: {message_html(error.message(language))}</a></li>'
        summary += '</ul></section>'
    options = ''.join(f'<option value="{code}" {"selected" if code == language else ""}>{escape(name)}</option>' for code, (name, direction) in LANGUAGES.items())
    content = summary + f'''<form method="post" action="/">
<input type="hidden" name="csrf" value="{escape(token)}">
<input type="hidden" name="had_errors" value="{int(bool(errors))}">
<div class="language"><label for="language">{message('nav.language')}</label>
<select id="language" name="language">{options}</select>
<button type="submit" name="intent" value="language" formnovalidate>{message('action.language')}</button></div>'''
    for field, input_type, help_key in (("name", "text", "help.name"), ("date", "text", "help.date")):
        error = next((item for item in errors if item.field == field), None)
        invalid = ' aria-invalid="true"' if error else ''
        described = field + '-help' + (' ' + field + '-error' if error else '')
        limit = ' maxlength="80"' if field == 'name' else ' maxlength="10" pattern="[0-9]{4}-[0-9]{2}-[0-9]{2}"'
        direction = 'auto' if field == 'name' else 'ltr'
        content += f'<label for="{field}">{message(labels[field])}</label><p class="help" id="{field}-help">{message(help_key)}</p>'
        content += f'<input id="{field}" name="{field}" type="{input_type}" dir="{direction}" value="{escape(values.get(field, ""), quote=True)}" required{limit}{invalid} aria-describedby="{described}">'
        if error:
            content += f'<p class="error" id="{field}-error">{message_html(error.message(language))}</p>'
    error = next((item for item in errors if item.field == 'synthetic'), None)
    invalid = ' aria-invalid="true" aria-describedby="synthetic-error"' if error else ''
    checked = ' checked' if values.get('synthetic') == 'yes' else ''
    content += f'<label for="synthetic"><input id="synthetic" type="checkbox" name="synthetic" value="yes" required{checked}{invalid}> {message("field.confirm")}</label>'
    if error:
        content += f'<p id="synthetic-error" class="error">{escape(error.message(language))}</p>'
    content += '<button type="submit" name="intent" value="save">' + message('action.save') + '</button></form>'
    return shell(language, 'lab.title', content, preview)


def listing(language, records, saved=False, preview=False, printing=False):
    content = '<p role="status" class="status">' + escape(translate('status.saved', language)) + '</p>' if saved else ''
    if not records:
        content += '<p>' + escape(translate('state.empty', language)) + '</p>'
    for ID, name, day in records:
        content += f'<article class="record"><h2><bdi dir="ltr">AP-{ID:03d}</bdi></h2><p><bdi dir="auto">{escape(name)}</bdi></p><p><bdi dir="ltr">{escape(day)}</bdi></p></article>'
    if not printing:
        content += f'<a href="/print?lang={language}">{escape(translate("action.print", language))}</a>'
    content += '<nav class="language" aria-label="' + escape(translate('nav.language', language)) + '">'
    for code, (name, _) in LANGUAGES.items():
        content += f'<a lang="{code}" href="/requests?lang={code}">{escape(name)}</a> '
    return shell(language, 'lab.list', content + '</nav>', preview)


def error_page(language, code, preview=False):
    content = f'<p role="alert">{escape(translate(code, language))}</p><a href="/?lang={language}">{escape(translate("action.back", language))}</a>'
    return shell(language, code, content, preview)


STATES = ('initial', 'empty_submission', 'one_invalid', 'multiple_invalid', 'success',
          'duplicate', 'empty_list', 'unavailable', '404', '500', 'print')


def state_page(language, state, token):
    values = {"name": "Demo مثال AP-001", "date": "2026-09-20", "synthetic": "yes"}
    if state == 'initial':
        return form(language, token, preview=True), 200
    if state == 'empty_submission':
        return form(language, token, {}, validate({}), True), 422
    if state in ('one_invalid', 'multiple_invalid'):
        values['date'] = 'invalid'
        if state == 'multiple_invalid':
            values['name'] = ''
        return form(language, token, values, validate(values), True), 422
    if state == 'duplicate':
        return form(language, token, values, [UIError('error.duplicate', 'name', 409)], True), 409
    if state in ('success', 'empty_list', 'print'):
        records = [] if state == 'empty_list' else [(1, values['name'], values['date'])]
        return listing(language, records, state == 'success', True, state == 'print'), 200
    if state in ('unavailable', '404', '500'):
        codes = {'unavailable': ('error.unavailable', 503), '404': ('error.not_found', 404), '500': ('error.unexpected', 500)}
        code, status = codes[state]
        return error_page(language, code, True), status
    return error_page(language, 'error.not_found', True), 404


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass  # Do not log submitted names or URL contents.

    def respond(self, body, status=200, content_type="text/html; charset=utf-8"):
        data = body.encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type', content_type)
        self.send_header('Content-Length', str(len(data)))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('Content-Security-Policy', "default-src 'none'; style-src 'self'; form-action 'self'; base-uri 'none'; frame-ancestors 'none'")
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        query = urlsplit(self.path)
        params = parse_qs(query.query)
        language = params.get('lang', ['en'])[0]
        if language not in LANGUAGES:
            language = 'en'
        allowed = {f'127.0.0.1:{self.server.server_port}', f'localhost:{self.server.server_port}'}
        if self.headers.get('Host') not in allowed:
            self.respond(error_page(language, 'error.unexpected'), 403)
            return
        try:
            if query.path == '/tokens.css':
                from sehatraasta import presentation
                self.respond((Path(presentation.__file__).parent / 'tokens.css').read_text(), content_type='text/css')
            elif query.path == '/':
                self.respond(form(language, self.server.token))
            elif query.path in ('/requests', '/print'):
                self.respond(listing(language, self.server.store.list_requests(), params.get('saved') == ['1'], printing=query.path == '/print'))
            elif query.path == '/states':
                if 'state' in params:
                    body, status = state_page(language, params['state'][0], self.server.token)
                    self.respond(body, status)
                else:
                    links = '<ul>' + ''.join(f'<li><a href="/states?lang={language}&amp;state={state}"><bdi dir="ltr">{state}</bdi></a></li>' for state in STATES) + '</ul>'
                    self.respond(shell(language, 'lab.states', links, True))
            else:
                self.respond(error_page(language, 'error.not_found'), 404)
        except sqlite3.Error:
            self.respond(error_page(language, 'error.unavailable'), 503)
        except Exception:
            self.respond(error_page(language, 'error.unexpected'), 500)

    def do_POST(self):
        language = 'en'
        try:
            length = int(self.headers.get('Content-Length', '0'))
            if length < 0 or length > 8192:
                self.respond(error_page(language, 'error.unexpected'), 413)
                return
            values = {key: items[0] for key, items in parse_qs(self.rfile.read(length).decode('utf-8'), keep_blank_values=True).items()}
            language = values.get('language', 'en')
            if language not in LANGUAGES:
                language = 'en'
            origins = {f'http://127.0.0.1:{self.server.server_port}', f'http://localhost:{self.server.server_port}'}
            hosts = {urlsplit(origin).netloc for origin in origins}
            if self.path != '/' or self.headers.get('Host') not in hosts or self.headers.get('Origin') not in origins | {None} or not secrets.compare_digest(values.get('csrf', ''), self.server.token):
                self.respond(error_page(language, 'error.unexpected'), 403)
                return
            if values.get('intent') == 'language':
                errors = validate(values) if values.get('had_errors') == '1' else []
                self.respond(form(language, self.server.token, values, errors))
                return
            errors = self.server.store.save(values)
            if errors:
                self.respond(form(language, self.server.token, values, errors), errors[0].status)
            else:
                self.send_response(303)
                self.send_header('Location', '/requests?lang=' + language + '&saved=1')
                self.send_header('Content-Length', '0')
                self.end_headers()
        except sqlite3.Error:
            # Preserve submitted values after a storage failure.
            body = form(language, self.server.token, values, [UIError('error.unavailable', 'name', 503)])
            self.respond(body, 503)
        except Exception:
            self.respond(error_page(language, 'error.unexpected'), 500)


def make_server(database, port=8766):
    store = AppointmentStore(database)
    server = HTTPServer(('127.0.0.1', port), Handler)
    server.store = store
    server.token = secrets.token_hex(32)
    return server


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Fictional school office appointment lab. Not a clinical app.')
    parser.add_argument('--database', required=True, help='Separate lab database, never the SehatRaasta database.')
    parser.add_argument('--port', type=int, default=8766)
    args = parser.parse_args()
    server = make_server(args.database, args.port)
    print(f'Learning lab: http://127.0.0.1:{server.server_port} (Ctrl+C to stop)')
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
