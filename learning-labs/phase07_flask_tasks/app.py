"""Small service-to-Flask exercise. Fictional tasks; memory-only storage."""
import secrets
from flask import Flask, render_template, request, redirect, session, flash


class TaskService:
    def __init__(self):
        self.tasks = []

    def add(self, title):
        if not isinstance(title, str) or not title.strip():
            raise ValueError('Enter a task title.')
        task = {'id': len(self.tasks) + 1, 'title': title}
        self.tasks.append(task)
        return task

    def list_tasks(self):
        return list(self.tasks)

    def get(self, identifier):
        return next((task for task in self.tasks if str(task['id']) == identifier), None)


def create_app(service=None):
    app = Flask(__name__)
    app.secret_key = secrets.token_hex(32)
    app.config.update(DEBUG=False, TRUSTED_HOSTS=['localhost', '127.0.0.1'], MAX_CONTENT_LENGTH=8192,
                      SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE='Strict')
    service = service or TaskService()
    app.extensions['tasks'] = service

    @app.route('/tasks', methods=['GET', 'POST'])
    def tasks():
        session.setdefault('csrf', secrets.token_hex(24))
        error, status, title = '', 200, ''
        if request.method == 'POST':
            if not secrets.compare_digest(request.form.get('csrf', ''), session['csrf']):
                return render_template('error.html', message='Reload the form and try again.', status=400), 400
            title = request.form.get('title', '')
            try:
                service.add(title)
                session['csrf'] = secrets.token_hex(24)
                flash('Task saved.')
                return redirect('/tasks', code=303)
            except ValueError as problem:
                error, status = str(problem), 422
        return render_template('tasks.html', tasks=service.list_tasks(), error=error, value=title), status

    @app.get('/tasks/<identifier>')
    def task(identifier):
        task = service.get(identifier)
        if task is None:
            return render_template('error.html', message='Task not found.', status=404), 404
        return render_template('task.html', task=task)

    @app.errorhandler(Exception)
    def failure(error):
        return render_template('error.html', message='Task storage is unavailable. No save was confirmed.', status=500), 500

    return app


if __name__ == '__main__':
    create_app().run(host='127.0.0.1', port=5001, debug=False)
