from django.conf import settings
from django.core.urlresolvers import reverse
from django.test import override_settings
from django.utils.http import urlquote

from seahub.base.models import ClientSSOToken
from seahub.test_utils import BaseTestCase
from seahub.views.sso import sso


class SSOTest(BaseTestCase):
    def setUp(self):
        self.url = reverse(sso)

    @override_settings(ENABLE_SHIB_LOGIN=True)
    def test_sso(self):
        resp = self.client.get(self.url)
        self.assertEqual(302, resp.status_code)
        assert resp.get('location') == '/'

        resp = self.client.get(self.url + '?next=/foo')
        assert resp.get('location') == '/foo'

        resp = self.client.get(self.url + '?next=' + urlquote('http://testserver\@example.com'))
        self.assertRegexpMatches(resp['Location'], settings.LOGIN_REDIRECT_URL)

    # def test_client_sso(self):
    #     resp = self.client.get(reverse('client_sso', args=['123456', ]))
    #     assert '/client-sso/123456/complete' in resp['Location']

    def test_client_sso_complete(self):
        self.login_as(self.user)

        t = ClientSSOToken.objects.new()
        assert t.api_key is None
        assert t.email is None

        resp = self.client.get(reverse('client_sso_complete', args=[t.token]))
        self.assertEqual(resp.status_code, 302)

        t2 = ClientSSOToken.objects.get(token=t.token)
        assert t2.api_key is not None
        assert t2.email == self.user.username
