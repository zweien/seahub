# Copyright (c) 2012-2016 Seafile Ltd.
import logging

from django.conf import settings
from django.core.urlresolvers import reverse
from django.http import HttpResponseRedirect
from django.utils.http import is_safe_url, urlquote
from django.shortcuts import get_object_or_404

from seahub.auth import REDIRECT_FIELD_NAME
from seahub.auth.decorators import login_required
from seahub.base.models import ClientSSOToken

# Get an instance of a logger
logger = logging.getLogger(__name__)

def sso(request):
    # Ensure the user-originating redirection url is safe.
    if REDIRECT_FIELD_NAME in request.GET:
        next_page = request.GET[REDIRECT_FIELD_NAME]
        if not is_safe_url(url=next_page, host=request.get_host()):
            next_page = settings.LOGIN_REDIRECT_URL
    else:
        next_page = reverse('libraries')

    if getattr(settings, 'ENABLE_REMOTE_USER_AUTHENTICATION', False):
        return HttpResponseRedirect(next_page)

    if getattr(settings, 'ENABLE_SHIB_LOGIN', False):
        return HttpResponseRedirect(next_page)

    if getattr(settings, 'ENABLE_KRB5_LOGIN', False):
        return HttpResponseRedirect(next_page)

    # send next page back to other views
    next_param = '?%s=' % REDIRECT_FIELD_NAME + urlquote(next_page)
    if getattr(settings, 'ENABLE_ADFS_LOGIN', False):
        return HttpResponseRedirect(reverse('saml2_login') + next_param)

    if getattr(settings, 'ENABLE_OAUTH', False):
        return HttpResponseRedirect(reverse('oauth_login') + next_param)

    if getattr(settings, 'ENABLE_CAS', False):
        return HttpResponseRedirect(reverse('cas_ng_login') + next_param)

    if getattr(settings, 'ENABLE_WORK_WEIXIN_OAUTH', False):
        return HttpResponseRedirect(reverse('work_weixin_oauth_login') + next_param)

    return HttpResponseRedirect(next_page)

def shib_login(request):
    if REDIRECT_FIELD_NAME in request.GET:
        next_page = request.GET[REDIRECT_FIELD_NAME]
        next_param = '?%s=' % REDIRECT_FIELD_NAME + urlquote(next_page)
        return HttpResponseRedirect(reverse('sso') + next_param)
    else:
        return HttpResponseRedirect(reverse('sso'))

def client_sso(request, uuid):
    next_page = reverse('client_sso_complete', args=[uuid, ])

    # client platform args used to create api v2 token
    req_qs = request.META['QUERY_STRING']
    if req_qs:
        next_page = next_page + '?' + req_qs

    # light security check
    if not is_safe_url(url=next_page, host=request.get_host()):
        logger.error('%s is not safe url.' % next_page)
        next_page = reverse('client_sso_complete', args=[uuid, ])

    redirect_url = reverse('saml2_login') + '?next=' + urlquote(next_page)
    return HttpResponseRedirect(redirect_url)

@login_required
def client_sso_complete(request, uuid):
    t = get_object_or_404(ClientSSOToken, token=uuid)
    username = request.user.username

    if t.is_waiting():
        from seahub.api2.utils import get_token_v1, get_token_v2
        # generate tokenv2 using information in request params
        keys = (
            'platform',
            'device_id',
            'device_name',
            'client_version',
            'platform_version',
        )
        if all(['shib_' + key in request.GET for key in keys]):
            platform = request.GET['shib_platform']
            device_id = request.GET['shib_device_id']
            device_name = request.GET['shib_device_name']
            client_version = request.GET['shib_client_version']
            platform_version = request.GET['shib_platform_version']
            api_token = get_token_v2(
                request, username, platform, device_id,
                device_name, client_version, platform_version)
        elif all(['shib_' + key not in request.GET for key in keys]):
            api_token = get_token_v1(username)

        t.completed(email=username, api_key=api_token.key)
        logger.info('Client SSO success, uuid: %s, user: %s' % (uuid, username))

    else:
        logger.warn('Client SSO token is not waiting, skip.')

    return HttpResponseRedirect(reverse('libraries'))
