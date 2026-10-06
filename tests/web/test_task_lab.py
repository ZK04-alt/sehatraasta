from pathlib import Path
import importlib.util
import re
import pytest

path = Path(__file__).resolve().parents[2] / 'learning-labs/phase07_flask_tasks/app.py'
spec = importlib.util.spec_from_file_location('task_lab', path)
lab = importlib.util.module_from_spec(spec)
spec.loader.exec_module(lab)


@pytest.fixture
def app():
    app = lab.create_app()
    app.template_folder = str(path.parent / 'templates')
    app.static_folder = str(path.parent / 'static')
    app.config['TESTING'] = True
    return app


def submit(client, title):
    page = client.get('/tasks').data.decode()
    token = re.search(r'name="csrf" type="hidden" value="([^"]+)"', page)[1]
    return client.post('/tasks', data={'csrf': token, 'title': title})


def test_service_stores_task():
    service = lab.TaskService()
    assert service.add('Fictional task')['id'] == 1
    assert service.get('1')['title'] == 'Fictional task'


def test_service_rejects_blank():
    service = lab.TaskService()
    with pytest.raises(ValueError):
        service.add(' ')
    assert service.list_tasks() == []


def test_empty(app):
    response = app.test_client().get('/tasks')
    assert response.status_code == 200 and b'No tasks yet' in response.data


def test_save_redirect(app):
    assert submit(app.test_client(), 'Demo').status_code == 303


def test_success_status(app):
    client = app.test_client()
    submit(client, 'Demo')
    assert b'role="status"' in client.get('/tasks').data


def test_blank_no_insert(app):
    assert submit(app.test_client(), ' ').status_code == 422
    assert app.extensions['tasks'].list_tasks() == []


def test_unknown(app):
    assert app.test_client().get('/tasks/unknown').status_code == 404


def test_detail(app):
    client = app.test_client()
    submit(client, 'Demo')
    assert b'Demo' in client.get('/tasks/1').data


def test_failure(app, monkeypatch):
    def fail():
        raise OSError('private details')
    monkeypatch.setattr(app.extensions['tasks'], 'list_tasks', fail)
    response = app.test_client().get('/tasks')
    assert response.status_code == 500 and b'private details' not in response.data


def test_escaped(app):
    client = app.test_client()
    submit(client, '<script>bad()</script>')
    assert b'&lt;script&gt;' in client.get('/tasks').data


def test_no_token(app):
    assert app.test_client().post('/tasks', data={'title': 'Demo'}).status_code == 400
