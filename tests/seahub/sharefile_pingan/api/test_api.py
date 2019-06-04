# -*- coding: utf-8 -*-
import json

from django.core.urlresolvers import reverse
from seahub.share.models import UserApprovalChain, approval_chain_str2list
from seahub.test_utils import BaseTestCase
from ..mixins import AddDownloadLinkMixin

def _create_chain():
    user = 'a@pingan.com.cn'
    chain = '%s <-> a@pingan.com.cn -> b@pingan.com.cn' % user
    UserApprovalChain.objects.create_chain(
        user, approval_chain_str2list(chain)
    )
    assert UserApprovalChain.objects.filter(user=user).count() > 0


class UserApprovalChainsViewTest(BaseTestCase):
    def setUp(self):
        self.url = reverse('api-v2.1-user-approval-chains')
        self.login_as(self.admin)

    def tearDown(self):
        pass

    def test_can_count(self):
        resp = self.client.get(self.url)
        json_resp = json.loads(resp.content)
        self.assertEqual(0, json_resp['count'])

        _create_chain()

        resp = self.client.get(self.url)
        json_resp = json.loads(resp.content)
        self.assertEqual(1, json_resp['count'])

    def test_can_add(self):
        resp = self.client.put(
            self.url,
            'chain=a@pingan.com.cn<->%s | %s&chain=b@pingan.com.cn<-> %s -> %s' % (
                self.user.username, self.admin.username,
                self.user.username, self.admin.username,
            ),
            'application/x-www-form-urlencoded',
        )

        json_resp = json.loads(resp.content)
        assert len(json_resp['success']) == 2
        assert len(UserApprovalChain.objects.values_list('user', flat=True).distinct()) == 2

        # update one record
        resp = self.client.put(
            self.url,
            'chain=a@pingan.com.cn<->%s -> %s' % (
                self.user.username, self.admin.username,

            ),
            'application/x-www-form-urlencoded',
        )

        json_resp = json.loads(resp.content)
        assert len(json_resp['success']) == 1
        assert len(UserApprovalChain.objects.values_list('user', flat=True).distinct()) == 2


    def test_invalid_reviser(self):
        resp = self.client.put(
            self.url,
            'chain=a@pingan.com.cn<->%s | %s&chain=b@pingan.com.cn<-> %s -> %s' % (
                self.user.username, self.admin.username,
                self.user.username, 'xx@xx.com',
            ),
            'application/x-www-form-urlencoded',
        )

        json_resp = json.loads(resp.content)
        assert len(json_resp['success']) == 1
        assert len(json_resp['failed']) == 1
        assert len(UserApprovalChain.objects.values_list('user', flat=True).distinct()) == 1


class UserApprovalChainViewTest(BaseTestCase):
    def setUp(self):
        self.url = reverse('api-v2.1-user-approval-chain', args=['a@pingan.com.cn'])
        self.login_as(self.admin)

    def test_can_get(self):
        resp = self.client.get(self.url)
        self.assertEqual(404, resp.status_code)

        _create_chain()
        resp = self.client.get(self.url)
        self.assertEqual(200, resp.status_code)

        json_resp = json.loads(resp.content)
        assert json_resp['chain'] is not None

    def test_can_delete(self):
        user = 'a@pingan.com.cn'
        chain = '%s <-> a@pingan.com.cn -> b@pingan.com.cn' % user
        UserApprovalChain.objects.create_chain(
            user, approval_chain_str2list(chain)
        )
        assert UserApprovalChain.objects.filter(user=user).count() > 0

        resp = self.client.delete(self.url)
        self.assertEqual(200, resp.status_code)
        assert UserApprovalChain.objects.filter(user=user).count() == 0

        resp = self.client.delete(self.url)
        self.assertEqual(404, resp.status_code)


class ShareLinksTest(BaseTestCase):

    def setUp(self):
        self.url = reverse('api-v2.1-approval-chain')

    def tearDown(self):
        pass

    def test_permission(self):
        self.login_as(self.user)
        resp = self.client.get(self.url)
        assert resp.status_code == 403

    def test_put(self):
        self.login_as(self.admin)

        chain1 = 'dev1 <-> a@pingan.com.cn -> b@pingan.com.cn | c@pingan.com.cn'
        chain2 = 'dev2 <-> a@pingan.com.cn -> b@pingan.com.cn -> c@pingan.com.cn'

        resp = self.client.put(self.url, "chain=%s&chain=%s" % (chain1, chain2),
                               'application/x-www-form-urlencoded')

        json_resp = json.loads(resp.content)
        assert len(json_resp['failed']) == 0
        assert len(json_resp['success']) == 2

    def test_get(self):
        self.login_as(self.admin)
        resp = self.client.get(self.url)
        json_resp = json.loads(resp.content)
        assert json_resp['count'] == 0

        chain1 = 'dev1 <-> a@pingan.com.cn -> b@pingan.com.cn | c@pingan.com.cn'
        resp = self.client.put(self.url, "chain=%s" % (chain1),
                               'application/x-www-form-urlencoded')

        resp = self.client.get(self.url)
        json_resp = json.loads(resp.content)
        assert json_resp['count'] == 1


# class SysDownloadLinksReportTest(BaseTestCase, AddDownloadLinkMixin):
#     def setUp(self):
#         self.url = reverse('api-v2.1-sys-download-links-report')
#         self.login_as(self.admin)

#         self.add_shared_file_link()

#     def test_can_get(self):
#         resp = self.client.get(self.url + '?start=2018-01-01T00:00:00&end=2018-08-01T00:00:00')
