import importlib.util
import sys
import types
from pathlib import Path

import pytest


class FakeResponse:
    def __init__(self, status_code):
        self.status_code = status_code
        self.failures = []
        self.successful = False

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        return False

    def failure(self, message):
        self.failures.append(message)

    def success(self):
        self.successful = True


class FakeClient:
    def __init__(self, response_status=302):
        self.cookies = {'csrftoken': 'csrf-test-token'}
        self.response_status = response_status
        self.requests = []

    def get(self, path, **kwargs):
        self.requests.append(('GET', path, kwargs))
        return FakeResponse(200)

    def post(self, path, **kwargs):
        self.requests.append(('POST', path, kwargs))
        return FakeResponse(self.response_status)


class FakeHttpUser:
    def __init__(self):
        self.client = FakeClient()


def load_locustfile(monkeypatch):
    locust_module = types.ModuleType('locust')
    locust_module.HttpUser = FakeHttpUser
    locust_module.between = lambda minimum, maximum: (minimum, maximum)
    locust_module.task = lambda weight=1: lambda function: function
    monkeypatch.setitem(sys.modules, 'locust', locust_module)

    path = Path(__file__).parents[1] / 'locust' / 'locustfile.py'
    spec = importlib.util.spec_from_file_location('crm_locustfile', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_locust_user_logs_in_with_configured_credentials_and_csrf(monkeypatch):
    monkeypatch.setenv('LOCUST_USERNAME', 'load-test@example.com')
    monkeypatch.setenv('LOCUST_PASSWORD', 'test-password')
    module = load_locustfile(monkeypatch)
    user = module.CrmUser()

    user.on_start()

    assert user.client.requests == [
        ('GET', '/login/', {}),
        (
            'POST',
            '/login/',
            {
                'data': {
                    'email': 'load-test@example.com',
                    'senha': 'test-password',
                    'csrfmiddlewaretoken': 'csrf-test-token',
                },
                'allow_redirects': False,
                'catch_response': True,
            },
        ),
    ]


def test_locust_user_requires_credentials_before_sending_requests(monkeypatch):
    monkeypatch.delenv('LOCUST_USERNAME', raising=False)
    monkeypatch.delenv('LOCUST_PASSWORD', raising=False)
    module = load_locustfile(monkeypatch)
    user = module.CrmUser()

    with pytest.raises(RuntimeError, match='LOCUST_USERNAME and LOCUST_PASSWORD'):
        user.on_start()

    assert user.client.requests == []


def test_locust_user_does_not_shadow_locust_task_registry(monkeypatch):
    module = load_locustfile(monkeypatch)

    assert not callable(module.CrmUser.__dict__.get('tasks'))


def test_locust_user_loads_only_read_only_crm_pages(monkeypatch):
    monkeypatch.setenv('LOCUST_USERNAME', 'load-test@example.com')
    monkeypatch.setenv('LOCUST_PASSWORD', 'test-password')
    module = load_locustfile(monkeypatch)
    user = module.CrmUser()

    user.dashboard()
    user.reception()
    user.tasks_page()
    user.contacts()

    assert [(method, path) for method, path, _ in user.client.requests] == [
        ('GET', '/dashboard/'),
        ('GET', '/recepcao/'),
        ('GET', '/tarefas/'),
        ('GET', '/contatos/'),
    ]
