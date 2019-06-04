# -*- coding: utf-8 -*-
"""Utility functions used for share link verify in PingAn Group.
"""
import base64
import os
import logging
import string

from django.utils import translation
from django.utils.translation import ugettext as _

from .settings import (FUSE_MOUNT_POINT, DLP_SCAN_POINT,
                       ENABLE_FILESHARE_DLP_CHECK)
from seahub.profile.models import Profile, DetailedProfile
from seahub.share.constants import STATUS_PASS, STATUS_VETO
from seahub.share.models import (FileShareApprovalChain, ApprovalChain,
                                 UserApprovalChain, FileShareApprovalStatus)
from seahub.utils import get_service_url, send_html_email

# Get an instance of a logger
logger = logging.getLogger(__name__)

def _symbol_link_file_for_dlp_check(username, repo, fileshare):
    # Add symbol link for DLP check
    old_cwd = os.getcwd()
    fuse_file = os.path.join(FUSE_MOUNT_POINT, username,
                             repo.id + '_' + repo.name,
                             fileshare.path.lstrip('/')).encode('utf-8')  # for lartin system locale

    if os.path.exists(fuse_file):
        d_p = DetailedProfile.objects.get_detailed_profile_by_user(username)
        if d_p and d_p.company:
            dlp_prefix = './%s/' % base64.b64encode(d_p.company.encode('utf-8'))
        else:
            dlp_prefix = './'

        symlink = fuse_file.replace(FUSE_MOUNT_POINT, dlp_prefix).rstrip('/')

        try:
            os.chdir(DLP_SCAN_POINT)
            if not os.path.exists(os.path.dirname(symlink)):
                os.makedirs(os.path.dirname(symlink))
            os.symlink(fuse_file, symlink)
            logger.info('Create symbol link %s for %s' % (symlink, fuse_file))
        except OSError as e:
            logger.error(e)
    else:
        logger.error('File %s not found in fuse.' % fuse_file)

    os.chdir(old_cwd)  # restore previous current working dir


def check_share_link(request, fileshare, repo):
    """DLP and huamn check share link when create share link.
    """
    username = request.user.username

    # record share link approval info
    FileShareApprovalChain.objects.create_fs_approval_chain(fileshare)

    # set default DLP status
    fs_v = FileShareApprovalStatus(share_link=fileshare,
                                   email=FileShareApprovalStatus.DLP_EMAIL)

    if not ENABLE_FILESHARE_DLP_CHECK:
        # dlp is disabled, pass
        # TODO: notify next revisers ?
        fs_v.DLP_status = STATUS_PASS

    fs_v.save()

    if ENABLE_FILESHARE_DLP_CHECK:
        _symbol_link_file_for_dlp_check(username, repo, fileshare)

def is_file_link_reviser(username):
    """Check whether a user is a reviser.
    """
    all_revisers = ApprovalChain.objects.get_emails()
    all_revisers += UserApprovalChain.objects.get_emails()
    all_revisers += FileShareApprovalChain.objects.values_list('email',
                                                               flat=True)

    return True if username in set(map(string.lower, all_revisers)) else False


def email_reviser(fileshare, reviser_email):
    """Send email to revisers to verify shared link.
    If DLP veto, show veto message to revisers.
    """
    subject = _('Please verify new share link.')

    app_status = FileShareApprovalStatus.objects.get_dlp_status_by_share_link(fileshare)
    if app_status is not None:
        show_dlp_veto_msg = app_status == STATUS_VETO
    else:
        show_dlp_veto_msg = False

    c = {
        'email': fileshare.username,
        'file_name': fileshare.get_name(),
        'file_shared_link': fileshare.get_full_url(),
        'service_url': get_service_url(),
        'show_dlp_veto_msg': show_dlp_veto_msg,
    }
    try:
        send_html_email(subject, 'share/share_link_verify_email.html',
                        c, None, [reviser_email])
        logger.info('Send email to %s, link: %s' % (reviser_email,
                                                    fileshare.get_full_url()))
    except Exception as e:
        logger.error('Faied to send email to %s, please check email settings.' % reviser_email)
        logger.error(e)

def email_verify_result(fileshare, email_to, source='DLP', result_code=1):
    """Send email to `email_to` about shared link verify result.
    """
    # save current language
    cur_language = translation.get_language()

    # get and active user language
    user_language = Profile.objects.get_user_language(email_to)
    translation.activate(user_language)

    c = {
        'source': source,
        'result_code': result_code,
        'file_name': fileshare.get_name(),
        'service_url': get_service_url().rstrip('/'),
    }
    subject = _('Verification status of your share link.')
    try:
        send_html_email(subject, 'share/share_link_verify_result_email.html',
                        c, None, [email_to])
        logger.info('Send verify result email to %s, link: %s' % (
            email_to, fileshare.get_full_url()))
    except Exception as e:
        logger.error('Faied to send verify result email to %s' % email_to)
        logger.error(e)

    # restore current language
    translation.activate(cur_language)
