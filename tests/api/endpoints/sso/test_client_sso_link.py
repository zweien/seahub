import json

from seahub.base.models import ClientSSOToken
from seahub.test_utils import BaseTestCase


class ClientSSOLinkTest(BaseTestCase):

    def test_create(self):
        resp = self.client.post('/api2/client-sso-link/')
        self.assertEqual(resp.status_code, 200)

        json_resp = json.loads(resp.content)
        assert json_resp['link'] is not None

    def test_query_status(self):
        t = ClientSSOToken.objects.new()
        url = '/api2/client-sso-link/%s/' % t.token

        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        json_resp = json.loads(resp.content)
        assert json_resp['status'] == 'waiting'

        t.completed(email=self.user.username, api_key='xxx')

        resp = self.client.get(url)
        json_resp = json.loads(resp.content)
        assert json_resp['status'] == 'success'
        assert json_resp['email'] == self.user.username
        assert json_resp['apiToken'] == 'xxx'
