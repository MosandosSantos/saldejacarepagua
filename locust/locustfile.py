import os

from locust import HttpUser, between, task


class CrmUser(HttpUser):
    wait_time = between(1, 3)

    def on_start(self):
        username = os.getenv('LOCUST_USERNAME', '').strip()
        password = os.getenv('LOCUST_PASSWORD', '')
        turnstile_token = os.getenv('LOCUST_TURNSTILE_TOKEN', '').strip()
        if not username or not password:
            raise RuntimeError('Configure LOCUST_USERNAME and LOCUST_PASSWORD before starting users.')
        if not turnstile_token:
            raise RuntimeError('Configure LOCUST_TURNSTILE_TOKEN before starting users.')

        self.client.get('/login/')
        csrf_token = self.client.cookies.get('csrftoken')
        if not csrf_token:
            raise RuntimeError('Could not read the CSRF token from the login page.')

        with self.client.post(
            '/login/',
            data={
                    'email': username,
                    'senha': password,
                    'cf-turnstile-response': turnstile_token,
                    'csrfmiddlewaretoken': csrf_token,
            },
            allow_redirects=False,
            catch_response=True,
        ) as response:
            if response.status_code != 302:
                response.failure('CRM login failed; check the Locust test account credentials.')
                raise RuntimeError('CRM login failed; check LOCUST_USERNAME and LOCUST_PASSWORD.')
            response.success()

    def _get_page(self, path):
        with self.client.get(
            path,
            name=path,
            allow_redirects=False,
            catch_response=True,
        ) as response:
            if 200 <= response.status_code < 300:
                response.success()
            else:
                response.failure(f'GET {path} returned HTTP {response.status_code}.')

    @task(5)
    def dashboard(self):
        self._get_page('/dashboard/')

    @task(3)
    def reception(self):
        self._get_page('/iniciacao/')

    @task(2)
    def tasks_page(self):
        self._get_page('/tarefas/')

    @task(2)
    def contacts(self):
        self._get_page('/contatos/')
