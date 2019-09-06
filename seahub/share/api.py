# -*- coding: utf-8 -*-
from collections import namedtuple
from datetime import timedelta, datetime

from rest_framework import status
from rest_framework.authentication import SessionAuthentication
from rest_framework.permissions import IsAdminUser, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from django.utils import translation, timezone

from seahub.api2.authentication import TokenAuthentication
from seahub.api2.throttling import UserRateThrottle
from seahub.api2.utils import api_error
from seahub.base.accounts import User
from seahub.constants import PINGAN_COMPANY_SECURITY
from seahub.profile.models import DetailedProfile
from seahub.share.models import ApprovalChain, approval_chain_str2list, \
    FileShare, UserApprovalChain, approval_chain_list2str, \
    is_valid_approval_chain_str
from seahub.utils import is_valid_email
from seahub.views.sysadmin_pingan import download_links_excel_report


class ApprovalChainView(APIView):
    authentication_classes = (TokenAuthentication, SessionAuthentication)
    permission_classes = (IsAdminUser, )
    throttle_classes = (UserRateThrottle, )

    def get(self, request):
        """List department approval chain.

        e.g.

        curl -v -H 'Authorization: Token 5f7435e5e585f935b84067bd0b6088cf8af9f6ac' -H 'Accept: application/json; indent=4' http://127.0.0.1:8000/api/v2.1/admin/approval-chain/

        """
        qs = ApprovalChain.objects.values_list('department',
                                               flat=True).distinct()

        return Response({'count': len(qs)})

    def put(self, request):
        """Add or update department approval chain.

        e.g.

        curl -X PUT -d "chain=测试部门1<->a@pingan.com.cn->b@pingan.com.cn->c@pingan.com.cn | d@pingan.com.cn&chain=测试部门2<->a@pingan.com.cn->b@pingan.com.cn->c@pingan.com.cn" -v -H 'Authorization: Token 5f7435e5e585f935b84067bd0b6088cf8af9f6ac' -H 'Accept: application/json; indent=4' http://127.0.0.1:8000/api/v2.1/admin/approval-chain/

        """
        chain_list = request.data.getlist('chain', None)
        if not chain_list:
            error_msg = 'chain invalid.'
            return api_error(status.HTTP_400_BAD_REQUEST, error_msg)

        success = []
        failed = []
        for ele in chain_list:
            splits = ele.split('<->')
            if len(splits) != 2:
                failed.append(ele)
                continue

            dept = splits[0].strip()
            chain = splits[1].strip()
            if not dept or not chain:
                failed.append(ele)
                continue

            # remove duplicated records
            ApprovalChain.objects.filter(department=dept).delete()

            chain_list = approval_chain_str2list(chain)
            for e in chain_list:
                if isinstance(e, basestring):
                    if not is_valid_email(e):
                        failed.append(ele)
                        continue
                    try:
                        u = User.objects.get(email=e)
                        if not u.is_active:
                            failed.append(ele)
                            continue
                    except User.DoesNotExist:
                        failed.append(ele)
                        continue
                else:
                    for x in e[1:]:
                        if not is_valid_email(x):
                            failed.append(ele)
                            continue
                    try:
                        u = User.objects.get(email=x)
                        if not u.is_active:
                            failed.append(ele)
                            continue
                    except User.DoesNotExist:
                        failed.append(ele)
                        continue

            ApprovalChain.objects.create_chain(dept, chain_list)
            success.append(ele)

        result = {
            'success': success,
            'failed': failed,
        }
        return Response(result)


class UserApprovalChainsView(APIView):
    authentication_classes = (TokenAuthentication, SessionAuthentication)
    permission_classes = (IsAdminUser, )
    throttle_classes = (UserRateThrottle, )

    def get(self, request):
        """Count user approval chains.

        e.g.

        curl -v -H 'Authorization: Token 5f7435e5e585f935b84067bd0b6088cf8af9f6ac' -H 'Accept: application/json; indent=4' http://127.0.0.1:8000/api/v2.1/admin/user-approval-chains/

        """
        qs = UserApprovalChain.objects.values_list('user',
                                                   flat=True).distinct()

        return Response({'count': len(qs)})

    def put(self, request):
        """Add or update user approval chain.

        e.g.

        curl -X PUT -d "chain=a@pingan.com.cn<->a@pingan.com.cn->b@pingan.com.cn->c@pingan.com.cn | d@pingan.com.cn&chain=b@pingan.com.cn<->a@pingan.com.cn->b@pingan.com.cn->c@pingan.com.cn" -v -H 'Authorization: Token 5f7435e5e585f935b84067bd0b6088cf8af9f6ac' -H 'Accept: application/json; indent=4' http://127.0.0.1:8000/api/v2.1/admin/user-approval-chains/

        """
        chain_list = request.data.getlist('chain', None)
        if not chain_list:
            error_msg = 'chain invalid.'
            return api_error(status.HTTP_400_BAD_REQUEST, error_msg)

        success = []
        failed = []
        for ele in chain_list:
            # check whether chain string is valid
            if not is_valid_approval_chain_str(ele):
                failed.append(ele)
                continue

            splits = ele.split('<->')
            user = splits[0].strip()
            chain = splits[1].strip()
            chain_list = approval_chain_str2list(chain)

            # remove duplicated records
            UserApprovalChain.objects.filter(user=user).delete()

            UserApprovalChain.objects.create_chain(user, chain_list)
            success.append(ele)

        result = {
            'success': success,
            'failed': failed,
        }
        return Response(result)


class UserApprovalChainView(APIView):
    authentication_classes = (TokenAuthentication, SessionAuthentication)
    permission_classes = (IsAdminUser, )
    throttle_classes = (UserRateThrottle, )

    def get(self, request, user):
        """Get user approval chain.

        e.g.

        curl -v -H 'Authorization: Token 5f7435e5e585f935b84067bd0b6088cf8af9f6ac' -H 'Accept: application/json; indent=4' http://127.0.0.1:8000/api/v2.1/admin/user-approval-chains/a@pingan.com.cn/

        """
        if UserApprovalChain.objects.filter(user=user).count() == 0:
            return Response(status=404)

        chain_obj = namedtuple('ChainObj', ['user', 'chain', 'chain_raw'])
        chain = UserApprovalChain.objects.get_by_user(user)
        chain_str = approval_chain_list2str(chain)
        chain_raw = approval_chain_list2str(chain, with_nickname=False)
        chain_obj(user=user, chain=chain_str, chain_raw=chain_raw)

        return Response({'chain': chain_str})

    def delete(self, request, user):
        """Delete user approval chain.

        e.g.

        curl -X DELETE -v -H 'Authorization: Token 5f7435e5e585f935b84067bd0b6088cf8af9f6ac' -H 'Accept: application/json; indent=4' http://127.0.0.1:8000/api/v2.1/admin/user-approval-chains/a@pingan.com.cn/

        """
        if UserApprovalChain.objects.filter(user=user).count() == 0:
            return Response(status=404)

        UserApprovalChain.objects.filter(user=user).delete()
        return Response({'success': True})


class SysDownloadLinksReport(APIView):
    """List download links.

    e.g.

    curl -v -H 'Authorization: Token afef525019166d0e29bfe126cf6163c8c5bc82a5' -H 'Accept: application/json; indent=4' http://seacloud.docker:8000/api/v2.1/admin/download-link-excel/?start=2018-06-07T14:50:00&end=2018-06-07T14:55:00
    """
    authentication_classes = (TokenAuthentication, SessionAuthentication)
    permission_classes = (IsAuthenticated, )
    throttle_classes = (UserRateThrottle, )

    def get(self, request):

        if not (request.user.is_staff or request.user.role == PINGAN_COMPANY_SECURITY):
            error_msg = 'Permission denied.'
            return api_error(status.HTTP_403_FORBIDDEN, error_msg)

        translation.activate('zh-cn')

        end_date = timezone.now()
        start_date = end_date - timedelta(days=60)

        start_date_str = request.GET.get('start', '')
        end_date_str = request.GET.get('end', '')
        if start_date_str and end_date_str:
            try:
                start_date = datetime.strptime(start_date_str, '%Y-%m-%dT%H:%M:%S')
                end_date = datetime.strptime(end_date_str, '%Y-%m-%dT%H:%M:%S')
            except Exception:
                pass

        download_links = FileShare.objects.filter(s_type='f').filter(
            ctime__lte=end_date).filter(ctime__gte=start_date)


        head, data_list = download_links_excel_report(download_links)

        ret = {
            'data': [],
            'start_time': start_date_str,
            'end_time': end_date_str,
        }
        for e in data_list:
            d = {}
            d['filename'] = e[0]
            d['from_user'] = e[1]

            try:
                d_p = DetailedProfile.objects.get(user=e[1])
                d['department'] = d_p.department
                d['company'] = d_p.company
            except DetailedProfile.DoesNotExist:
                d['department'] = ''
                d['company'] = ''

            d['send_to'] = e[2]
            d['statue'] = e[3]
            d['created_at'] = e[4]
            d['first_download_time'] = e[5]
            d['downlods'] = e[6]
            d['expiration'] = e[7]
            d['link'] = e[8]

            d['dlp_status'] = e[9]
            d['dlp_time'] = e[10]

            d['human'] = e[11:]

            ret['data'].append(d)

        return Response(ret)
