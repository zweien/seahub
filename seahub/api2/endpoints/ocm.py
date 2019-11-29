import logging
import random
import string

from rest_framework import status
from rest_framework.authentication import SessionAuthentication
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from django.utils.translation import ugettext as _

from seahub.api2.authentication import TokenAuthentication
from seahub.api2.throttling import UserRateThrottle
from seahub.api2.utils import api_error
from seahub.base.accounts import User
from seahub.settings import ENABLE_OCM, SUPPORTED_OCM_PROTOCOLS, \
    SEAFILE_PROTOCOL, WEBDAV_PROTOCOL

from seaserv import seafile_api, ccnet_api

from seahub.utils import is_valid_email
from seahub.utils.repo import get_available_repo_perms, get_repo_owner
from seahub.share.utils import is_repo_admin, share_dir_to_user
from seahub.constants import PERMISSION_READ_WRITE
from seahub.repo_api_tokens.models import RepoAPITokens
from seahub.repo_api_tokens.utils import permission_check_admin_owner
from seahub.base.templatetags.seahub_tags import email2nickname
from seahub.constants import PERMISSION_READ, PERMISSION_READ_WRITE, \
        PERMISSION_ADMIN, OCM_NOTIFICATION_SHARE_DECLINED, OCM_NOTIFICATION_SHARE_UNSHARED
from seahub.ocm.models import OCMShareManager, OCMShareReceivedManager, OCMShareReceived, OCMShare
from seahub.ocm import OCM_PROVIDER_ID
from seahub.utils import is_org_context, is_valid_username, \
                          send_perm_audit_msg
from seahub.profile.models import Profile

logger = logging.getLogger(__name__)


def gen_shared_secret(length=23):
    return ''.join(random.choice(string.ascii_letters) for i in range(length))


class OCMProtocolView(APIView):
    authentication_classes = (TokenAuthentication, SessionAuthentication)
    throttle_classes = (UserRateThrottle,)

    def get(self, request):
        """
        return ocm protocol info to remote server
        """
        result = {}
        if ENABLE_OCM:
            result['support_ocm'] = True
            result['supported_protocal'] = SEAFILE_PROTOCOL
        else:
            result['support_ocm'] = False
            result['supported_protocal'] = []
        return Response(result)


class OCMSharesView(APIView):
    authentication_classes = (TokenAuthentication, SessionAuthentication)
    permission_classes = (IsAuthenticated,)
    throttle_classes = (UserRateThrottle,)

    def get(self, request):
        """
        list ocm shares
        """
        ocm_share_list = []
        ocm_shares = OCMShare.objects.all()
        for ocm_share in ocm_shares:
            ocm_share_list.append(ocm_share.to_dict())
        return Response({'ocm_share_list': ocm_share_list})

    def post(self, request):
        """
        prepare provider server info for ocm
        """

        # argument check
        to_user = request.data.get('to_user', '')
        if not to_user:
            error_msg = 'to_user invalid.'
            return api_error(status.HTTP_400_BAD_REQUEST, error_msg)

        to_server_url = request.data.get('to_server_url', '').lower().strip()
        if not to_server_url:
            error_msg = 'to_server_url invalid.'
            return api_error(status.HTTP_400_BAD_REQUEST, error_msg)

        repo_id = request.data.get('repo_id', '')
        if not repo_id:
            error_msg = 'repo_id invalid.'
            return api_error(status.HTTP_400_BAD_REQUEST, error_msg)

        repo = seafile_api.get_repo(repo_id)
        if not repo:
            return api_error(status.HTTP_404_NOT_FOUND, 'Library %s not found.' % repo_id)

        path = request.GET.get('path', '/')
        if seafile_api.get_dir_id_by_path(repo.id, path) is None:
            return api_error(status.HTTP_404_NOT_FOUND, 'Folder %s not found.' % path)

        if repo.encrypted and path != '/':
            return api_error(status.HTTP_400_BAD_REQUEST, 'Folder invalid.')

        permission = request.data.get('permission', PERMISSION_READ)
        if permission not in get_available_repo_perms():
            return api_error(status.HTTP_400_BAD_REQUEST, 'permission invalid.')
        print('333')

        to_user_obj = None
        try:
            to_user_obj = User.objects.get(email=to_user)
        except User.DoesNotExist:
            pass
        if not to_user_obj:
            try:
                User.objects.create_user(to_user)
                Profile.objects.add_or_update(to_user, ocm_user=True, ocm_server=to_server_url)
            except Exception as e:
                logger.error(e)
                error_msg = 'Internal Server Error'
                return api_error(status.HTTP_500_INTERNAL_SERVER_ERROR, error_msg)

        print('www')

        # if has share to that user
        # if self.has_shared_to_user(request, repo_id, path, to_user):
        #     # need implement to_user's email is same, but url not same
        #     error_msg = 'Already shared to user %s at %s'
        #     return api_error(status.HTTP_400_BAD_REQUEST, error_msg)

        org_id = None
        if is_org_context(request):
            org_id = request.user.org.org_id
            repo_owner = seafile_api.get_org_repo_owner(repo_id)
        else:
            repo_owner = seafile_api.get_repo_owner(repo_id)
        print('444')

        # create share to user to that user
        share_dir_to_user(
            repo=repo,
            path=path,
            owner=repo_owner,
            share_from=request.user.username,
            share_to=to_user,
            permission=permission,
            org_id=org_id
        )
        print('555')

        ocm_share = OCMShare.objects.create_ocm_share(
            shared_secret=gen_shared_secret(),
            from_user=request.user.username,
            to_user=to_user,
            to_server_url=to_server_url,
            repo_id=repo_id,
            repo_name=repo.repo_name,
            path=path,
            permission=permission
        )

        res = ocm_share.to_dict()
        res['provider_id'] = OCM_PROVIDER_ID
        res['owner'] = repo_owner
        res['owner_name'] = email2nickname(repo_owner),

        return Response(res)


class OCMShareView(APIView):
    authentication_classes = (TokenAuthentication, SessionAuthentication)
    #permission_classes = (IsAuthenticated,)
    throttle_classes = (UserRateThrottle,)

    def post(self, request):
        """
        delete ocm share by shared secret
        """

        ocm_share = OCMShare.objects.filter(shared_secret=shared_secret)
        if not ocm_share:
            error_msg = 'shared_secret %s not found.' % shared_secret
            return api_error(status.HTTP_404_NOT_FOUND, error_msg)

        to_user, to_server_url = ocm_share[0].to_user, ocm_share[0].to_server_url

        try:
            ocm_share.delete()
        except Exception as e:
            logging.error(e)
            return api_error(status.HTTP_500_INTERNAL_SERVER_ERROR, 'Internal Server Error')

        # if no other shares to same user at same server, delete that dummy user
        other_shares = OCMShare.objects.filter(to_user=to_user, to_server_url=to_server_url)
        if not other_shares:
            # delete user
            try:
                User.objects.get(email=to_user).delete()
            except Exception as e:
                logger.error(e)
                error_msg = 'Internal Server Error'
                return api_error(status.HTTP_500_INTERNAL_SERVER_ERROR, error_msg)

        return Response({'success': True})


class OCMSharesReceivedView(APIView):
    authentication_classes = (TokenAuthentication, SessionAuthentication)
    #permission_classes = (IsAuthenticated,)
    throttle_classes = (UserRateThrottle,)

    def get(self, request):
        """
        list ocm shares received
        """
        ocm_share_received_list = []
        ocm_shares_received = OCMShare.objects.all()
        for ocm_share_received in ocm_shares_received:
            ocm_share_received_list.append(ocm_share_received.to_dict())
        return Response({'ocm_share_received_list': ocm_share_received_list})

    def post(self, request):
        """
        create ocm in consumer server
        """

        # argument check
        share_with = request.data.get('shareWith', '')
        if not share_with:
            error_msg = 'shareWith invalid.'
            return api_error(status.HTTP_400_BAD_REQUEST, error_msg)

        # curently only support repo share
        repo_name = request.data.get('name', '')
        if not repo_name:
            error_msg = 'name invalid.'
            return api_error(status.HTTP_400_BAD_REQUEST, error_msg)

        sender = request.data.get('sender', '')
        if not sender:
            error_msg = 'sender invalid.'
            return api_error(status.HTTP_400_BAD_REQUEST, error_msg)

        # other ocm protocol fields currently not used
        #
        # description = request.data.get('description', '')
        # provider_id = request.data.get('providerId', '')
        # owner = request.data.get('owner', '')
        # ownerDisplayName = request.data.get('ownerDisplayName', '')
        # senderDisplayName = request.data.get('senderDisplayName', '')
        # shareType = request.data.get('shareType', '')
        # resourceType = request.data.get('resourceType', '')

        """
        parse and check protocol, protocol is like:

        "protocol": {
          "name": "Seafile API",
          "options": {
            "sharedSecret": "hfiuhworzwnur98d3wjiwhr",
            "permissions": "read, write",
            "repo_id": "<repo_id>",
            "apiToken": "<api token>",
          }
        }

        or webdav protocol
        "protocol": {
          "name": "webdav",
          "options": {
            "sharedSecret": "hfiuhworzwnur98d3wjiwhr",
            "permissions": "read, write",
          }
        }
        """
        protocol = request.data.get('protocol', {})
        if not protocol:
            error_msg = 'protocol invalid.'
            return api_error(status.HTTP_400_BAD_REQUEST, error_msg)

        if 'name' not in protocol.keys():
            error_msg = 'protocol.name invalid.'
            return api_error(status.HTTP_400_BAD_REQUEST, error_msg)

        if protocol['name'] not in SUPPORTED_OCM_PROTOCOLS:
            error_msg = 'protocol %s not support.' % protocol['name']
            return api_error(status.HTTP_400_BAD_REQUEST, error_msg)

        if 'options' not in protocol.keys():
            error_msg = 'protocol.options invalid.'
            return api_error(status.HTTP_400_BAD_REQUEST, error_msg)

        if 'sharedSecret' not in protocol['options'].keys():
            error_msg = 'protocol.options.sharedSecret invalid.'
            return api_error(status.HTTP_400_BAD_REQUEST, error_msg)

        if 'permissions' not in protocol['options'].keys():
            error_msg = 'protocol.options.permissions invalid.'
            return api_error(status.HTTP_400_BAD_REQUEST, error_msg)

        if protocol['name'] == SEAFILE_PROTOCOL:
            shared_secret = protocol['options']['sharedSecret']
            permissions = protocol['options']['permissions']
            repo_id = protocol['options']['repoId']
            token = protocol['options']['apiToken']

        # web dav
        #
        # elif protocol['name'] == WEBDAV_PROTOCOL:
        #     shared_secret = protocol['options']['sharedSecret']
        #     permissions = protocol['options']['permissions']

        ocm_share_received = OCMShareReceived.objects.create_ocm_share_received(
            shared_secret=shared_secret,
            from_user=sender,
            to_user=share_with,
            from_server_url=request.META['REMOTE_HOST'],
            repo_id=repo_id,
            repo_name=repo_name,
            permission=permissions,
            token=token
        )

        res = ocm_share_received.to_dict()
        return Response(res)


class OCMShareReceivedView(APIView):
    #authentication_classes = (TokenAuthentication, SessionAuthentication)
    #permission_classes = (IsAuthenticated,)
    throttle_classes = (UserRateThrottle,)

    def post(self, request):
        """
        delete ocm share received
        """

        notification_type = request.data.get('notificationType', '')
        if not notification_type:
            error_msg = 'notificationType invalid.'
            return api_error(status.HTTP_400_BAD_REQUEST, error_msg)

        if notification_type != OCM_NOTIFICATION_SHARE_UNSHARED:
            error_msg = 'notificationType %s invalid.' % notification_type
            return api_error(status.HTTP_400_BAD_REQUEST, error_msg)

        ocm_share_received = OCMShareReceived.objects.filter(shared_secret=shared_secret)
        if not ocm_share_received:
            error_msg = 'shared_secret %s not found.' % shared_secret
            return api_error(status.HTTP_404_NOT_FOUND, error_msg)

        try:
            ocm_share_received.delete()
        except Exception as e:
            logging.error(e)
            return api_error(status.HTTP_500_INTERNAL_SERVER_ERROR, 'Internal Server Error')

        return Response({'success': True})
