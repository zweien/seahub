# -*- coding: utf-8 -*-
# Copyright (c) 2012-2016 Seafile Ltd.
import operator
import datetime
import logging
from collections import namedtuple

from django.db import models
from django.db.models import Q
from django.utils import timezone
from django.utils.translation import ugettext as _
from django.contrib.auth.hashers import make_password, check_password
from constance import config

from seahub.base.fields import LowerCaseCharField
from seahub.utils import normalize_file_path, normalize_dir_path, gen_token,\
    get_service_url, send_html_email
from seahub.constants import PERMISSION_READ, PERMISSION_ADMIN
from seahub.utils import is_valid_org_id

######################### Start PingAn Group related ########################
import os
import posixpath
from seaserv import ccnet_api
from seahub.base.templatetags.seahub_tags import email2nickname
from seahub.profile.models import DetailedProfile
from seahub.share.constants import STATUS_VERIFING, STATUS_PASS, STATUS_VETO
from seahub.share.settings import ENABLE_FILESHARE_CHECK
from seahub.utils import is_valid_email
from seahub.utils.ip import get_remote_ip
from seahub.utils.mail import send_pafile_html_email_with_dj_template
from seahub.settings import SITE_NAME
from seahub.utils.hasher import AESPasswordHasher
######################### End PingAn Group related ##########################

# Get an instance of a logger
logger = logging.getLogger(__name__)


class AnonymousShare(models.Model):
    """
    Model used for sharing repo to unregistered email.
    """
    repo_owner = LowerCaseCharField(max_length=255)
    repo_id = models.CharField(max_length=36)
    anonymous_email = LowerCaseCharField(max_length=255)
    token = models.CharField(max_length=25, unique=True)

def _get_link_key(token, is_upload_link=False):
    return 'visited_ufs_' + token if is_upload_link else \
        'visited_fs_' + token

def set_share_link_access(request, token, is_upload_link=False):
    """Remember which shared download/upload link user can access without
    providing password.
    """
    if request.session:
        link_key = _get_link_key(token, is_upload_link)
        request.session[link_key] = True
    else:
        # should never reach here in normal case
        logger.warn('Failed to remember shared link password, request.session'
                    ' is None when set shared link access.')

def check_share_link_access(request, token, is_upload_link=False):
    """Check whether user can access shared download/upload link without
    providing password.
    """
    link_key = _get_link_key(token, is_upload_link)
    if request.session.get(link_key, False):
        return True
    else:
        return False

def check_share_link_common(request, sharelink, is_upload_link=False):
    """Check if user can view a share link
    """

    msg = ''
    if not sharelink.is_encrypted():
        return (True, msg)

    # if CAN access shared download/upload link without providing password
    # return True
    if check_share_link_access(request, sharelink.token, is_upload_link):
        return (True, msg)

    if request.method != 'POST':
        return (False, msg)

    password = request.POST.get('password', None)
    if not password:
        msg = _("Password can\'t be empty")
        return (False, msg)

    if password == sharelink.get_password():
        set_share_link_access(request, sharelink.token, is_upload_link)
        return (True, msg)
    else:
        msg = _("Please enter a correct password.")
        return (False, msg)

class FileShareManager(models.Manager):

    def _make_password(self, password):
        aes = AESPasswordHasher()
        return aes.encode(password)

    def _add_file_share(self, username, repo_id, path, s_type,
                        password=None, expire_date=None,
                        permission='view_download', org_id=None):
        if password is not None:
            password_enc = self._make_password(password)
        else:
            password_enc = None

        token = gen_token(max_length=config.SHARE_LINK_TOKEN_LENGTH)
        fs = super(FileShareManager, self).create(
            username=username, repo_id=repo_id, path=path, token=token,
            s_type=s_type, password=password_enc, expire_date=expire_date,
            permission=permission)
        fs.save()

        if is_valid_org_id(org_id):
            OrgFileShare.objects.set_org_file_share(org_id, fs)

        return fs

    def _get_file_share_by_path(self, username, repo_id, path):
        fs = list(super(FileShareManager, self).filter(repo_id=repo_id).filter(
            username=username).filter(path=path))
        if len(fs) > 0:
            return fs[0]
        else:
            return None

    def _get_valid_file_share_by_token(self, token):
        """Return share link that exists and not expire, otherwise none.
        """
        try:
            fs = self.get(token=token)
        except self.model.DoesNotExist:
            return None

        if fs.expire_date is None:
            return fs
        else:
            if timezone.now() > fs.expire_date:
                return None
            else:
                return fs

    ########## public methods ##########
    def create_file_link(self, username, repo_id, path, password=None,
                         expire_date=None, permission='view_download',
                         org_id=None):
        """Create download link for file.
        """
        path = normalize_file_path(path)
        return self._add_file_share(username, repo_id, path, 'f', password,
                                    expire_date, permission, org_id)

    def get_file_link_by_path(self, username, repo_id, path):
        path = normalize_file_path(path)
        return self._get_file_share_by_path(username, repo_id, path)

    def get_valid_file_link_by_token(self, token):
        return self._get_valid_file_share_by_token(token)

    def create_dir_link(self, username, repo_id, path, password=None,
                        expire_date=None, permission='view_download',
                        org_id=None):
        """Create download link for directory.
        """
        path = normalize_dir_path(path)
        return self._add_file_share(username, repo_id, path, 'd', password,
                                    expire_date, permission, org_id)

    def get_dir_link_by_path(self, username, repo_id, path):
        path = normalize_dir_path(path)
        return self._get_file_share_by_path(username, repo_id, path)

    def get_valid_dir_link_by_token(self, token):
        return self._get_valid_file_share_by_token(token)

    def list_file_links(self):  # TODO: move to CE
        return super(FileShareManager, self).filter(s_type='f')


class ExtraSharePermissionManager(models.Manager):
    def get_user_permission(self, repo_id, username):
        """Get user's permission of a library.
        return
            e.g. 'admin'
        """
        record_list = super(ExtraSharePermissionManager, self).filter(
            repo_id=repo_id, share_to=username
        )
        if len(record_list) > 0:
            return record_list[0].permission
        else:
            return None

    def get_repos_with_admin_permission(self, username):
        """Get repo id list a user has admin permission.
        """
        shared_repos = super(ExtraSharePermissionManager, self).filter(
            share_to=username, permission=PERMISSION_ADMIN
        )
        return [e.repo_id for e in shared_repos]

    def get_admin_users_by_repo(self, repo_id):
        """Gets the share and permissions of the record in the specified repo ID.
        return
            e.g. ['admin_user1', 'admin_user2']
        """
        shared_repos = super(ExtraSharePermissionManager, self).filter(
            repo_id=repo_id, permission=PERMISSION_ADMIN
        )

        return [e.share_to for e in shared_repos]

    def batch_is_admin(self, in_datas):
        """return the data that input data is admin 
        e.g.
            in_datas:
                [(repo_id1, username1), (repo_id2, admin1)]
            admin permission data returnd:
                [(repo_id2, admin1)]
        """
        if len(in_datas) <= 0:
            return []
        query = reduce(
            operator.or_,
            (Q(repo_id=data[0], share_to=data[1]) for data in in_datas)
        )
        db_data = super(ExtraSharePermissionManager, self).filter(query).filter(permission=PERMISSION_ADMIN)
        return [(e.repo_id, e.share_to) for e in db_data]

    def create_share_permission(self, repo_id, username, permission):
        self.model(repo_id=repo_id, share_to=username, 
                   permission=permission).save()

    def delete_share_permission(self, repo_id, share_to):
        super(ExtraSharePermissionManager, self).filter(repo_id=repo_id, 
                                                   share_to=share_to).delete()

    def update_share_permission(self, repo_id, share_to, permission):
        super(ExtraSharePermissionManager, self).filter(repo_id=repo_id, 
                                                   share_to=share_to).delete()
        if permission in [PERMISSION_ADMIN]:
            self.create_share_permission(repo_id, share_to, permission)


class ExtraGroupsSharePermissionManager(models.Manager):
    def get_group_permission(self, repo_id, gid):
        record_list = super(ExtraGroupsSharePermissionManager, self).filter(
            repo_id=repo_id, group_id=gid
        )
        if len(record_list) > 0:
            return record_list[0].permission
        else:
            return None


    def get_repos_with_admin_permission(self, gid):
        """ return admin repo in specific group
            e.g: ['repo_id1', 'repo_id2']
        """
        return super(ExtraGroupsSharePermissionManager, self).filter(
            group_id=gid, permission='admin'
        ).values_list('repo_id', flat=True)

    def get_admin_groups_by_repo(self, repo_id):
        """ return admin groups in specific repo
            e.g: ['23', '12']
        """
        return super(ExtraGroupsSharePermissionManager, self).filter(
            repo_id=repo_id, permission='admin'
        ).values_list('group_id', flat=True)

    def batch_get_repos_with_admin_permission(self, gids):
        """ 
        """
        if len(gids) <= 0:
            return []
        db_data = super(ExtraGroupsSharePermissionManager, self).filter(group_id__in=gids, permission=PERMISSION_ADMIN)
        return [(e.repo_id, e.group_id) for e in db_data]

    def create_share_permission(self, repo_id, gid, permission):
        self.model(repo_id=repo_id, group_id=gid, permission=permission).save()

    def delete_share_permission(self, repo_id, gid):
        super(ExtraGroupsSharePermissionManager, self).filter(repo_id=repo_id, 
                                                             group_id=gid).delete()

    def update_share_permission(self, repo_id, gid, permission):
        super(ExtraGroupsSharePermissionManager, self).filter(repo_id=repo_id, 
                                                       group_id=gid).delete()
        if permission in [PERMISSION_ADMIN]:
            self.create_share_permission(repo_id, gid, permission)


class ExtraGroupsSharePermission(models.Model):
    repo_id = models.CharField(max_length=36, db_index=True)
    group_id = models.IntegerField(db_index=True)
    permission = models.CharField(max_length=30)
    objects = ExtraGroupsSharePermissionManager()


class ExtraSharePermission(models.Model):
    repo_id = models.CharField(max_length=36, db_index=True)
    share_to = models.CharField(max_length=255, db_index=True)
    permission = models.CharField(max_length=30)
    objects = ExtraSharePermissionManager()


class FileShare(models.Model):
    """
    Model used for file or dir shared link.
    """
    PERM_VIEW_DL = 'view_download'
    PERM_VIEW_ONLY = 'view_only'

    PERM_EDIT_DL = 'edit_download'
    PERM_EDIT_ONLY = 'edit_only'

    PERMISSION_CHOICES = (
        (PERM_VIEW_DL, 'Preview only and can download'),
        (PERM_VIEW_ONLY, 'Preview only and disable download'),
        (PERM_EDIT_DL, 'Edit and can download'),
        (PERM_EDIT_ONLY, 'Edit and disable download'),
    )

    username = LowerCaseCharField(max_length=255, db_index=True)
    repo_id = models.CharField(max_length=36, db_index=True)
    path = models.TextField()
    token = models.CharField(max_length=100, unique=True)
    ctime = models.DateTimeField(default=datetime.datetime.now)
    view_cnt = models.IntegerField(default=0)
    s_type = models.CharField(max_length=2, db_index=True, default='f') # `f` or `d`
    password = models.CharField(max_length=128, null=True)
    expire_date = models.DateTimeField(null=True)
    permission = models.CharField(max_length=50, db_index=True,
                                  choices=PERMISSION_CHOICES,
                                  default=PERM_VIEW_DL)

    objects = FileShareManager()

    def get_password(self):
        if self.password:
            try:
                aes = AESPasswordHasher()
                return aes.decode(self.password)
            except Exception:
                logger.error('Error occurred when get share link password')
                return ''
        else:
            return ''

    def is_file_share_link(self):
        return True if self.s_type == 'f' else False

    def is_dir_share_link(self):
        return False if self.is_file_share_link() else True

    def is_encrypted(self):
        return True if self.password is not None else False

    def is_expired(self):
        if self.expire_date is not None and timezone.now() > self.expire_date:
            return True
        else:
            return False

    def is_owner(self, owner):
        return owner == self.username

    def get_full_url(self):
        service_url = get_service_url().rstrip('/')
        if self.is_file_share_link():
            return '%s/f/%s/' % (service_url, self.token)
        else:
            return '%s/d/%s/' % (service_url, self.token)

    def get_permissions(self):
        perm_dict = {}
        if self.permission == FileShare.PERM_VIEW_DL:
            perm_dict['can_edit'] = False
            perm_dict['can_download'] = True
        elif self.permission == FileShare.PERM_VIEW_ONLY:
            perm_dict['can_edit'] = False
            perm_dict['can_download'] = False
        elif self.permission == FileShare.PERM_EDIT_DL:
            perm_dict['can_edit'] = True
            perm_dict['can_download'] = True
        elif self.permission == FileShare.PERM_EDIT_ONLY:
            perm_dict['can_edit'] = True
            perm_dict['can_download'] = False
        else:
            assert False
        return perm_dict

    def get_name(self):         # TODO: move to CE
        return os.path.basename(self.path)

    ######################### Start PingAn Group related ##################
    def get_approval_chain(self, flat=False):
        username = self.username

        # 1. get from share link chain info table
        ret = FileShareApprovalChain.objects.get_by_share_link(self, flat=flat)
        if ret:
            return ret

        # 2. get from user approval chain
        chain_list = UserApprovalChain.objects.get_by_user(username, flat=flat)
        if len(chain_list) == 0:
            logger.error('Use approval chain is empty for user: %s' % username)
        else:
            return chain_list

        # 3. get chain by share link user department
        d_profile = DetailedProfile.objects.get_detailed_profile_by_user(
            username)
        if not d_profile:
            logger.error('No detailed profile(department, ... etc) found for user %s' % username)
            return []

        chain_list = ApprovalChain.objects.get_by_department(
            d_profile.department, flat=flat)
        if len(chain_list) == 0:
            logger.error('Approval chain is empty for user: %s' % username)

        return chain_list

    def pass_verify(self):
        if not ENABLE_FILESHARE_CHECK:
            return True

        return True if self.get_status() == STATUS_PASS else False

    def is_verifing(self):
        if not ENABLE_FILESHARE_CHECK:
            return False

        return True if self.get_status() == STATUS_VERIFING else False

    def reject_verify(self):
        if not ENABLE_FILESHARE_CHECK:
            return False

        return True if self.get_status() == STATUS_VETO else False

    def get_pass_time(self):
        if not self.pass_verify():
            return ''

        chain_status = FileShareApprovalStatus.objects.\
                       get_chain_status_by_share_link(share_link=self)
        if not chain_status:
            return ''

        target = chain_status[-1]  # look up pass time at last step
        if not get_chain_step_sibling_type(target):
            target_time = target.vtime
        else:
            for ele in target[1:]:
                if ele.vtime:
                    target_time = ele.vtime
                    break

        return target_time.strftime('%Y-%m-%d %H:%M') if target_time else ''

    def get_status(self):
        if not ENABLE_FILESHARE_CHECK:
            return None

        return FileShareApprovalStatus.objects.get_status(self)

    def get_short_status_str(self):
        if not ENABLE_FILESHARE_CHECK:
            return None

        s = self.get_status()
        if s == STATUS_PASS:
            return _('Approved')
        elif s == STATUS_VERIFING:
            return _('Verifing')
        elif s == STATUS_VETO:
            return _('Rejected')

    def get_status_str(self):
        if not ENABLE_FILESHARE_CHECK:
            return None

        s = self.get_status()
        if s == STATUS_PASS:
            return _('Your share link is verified.')
        elif s == STATUS_VERIFING:
            return _('Your share link is waiting for verify.')
        elif s == STATUS_VETO:
            return _('Your share link is rejected.')

    def get_verbose_status(self):
        if not ENABLE_FILESHARE_CHECK:
            return None
        return FileShareApprovalStatus.objects.get_verbose_status(self)

    def get_verbose_status_str(self, show_password=False):
        rst = []
        v_stats = self.get_verbose_status()
        if not v_stats:
            return _('No revisers found. Please contact system admin.')

        for s, v in v_stats:
            rst.append(v)

        status_str = ';'.join(rst)

        if self.pass_verify():
            status_str += '<br><br>'
            extra_info = FileShareExtraInfo.objects.filter(share_link=self)
            if len(extra_info) > 0:
                sent_to_emails = ', '.join([x.sent_to for x in extra_info])
                status_str += u'该文件下载链接已外发至邮件：' + sent_to_emails
                status_str += u'（发送于' + self.get_pass_time() + u'）'
                status_str += '<br><br>'

            if show_password is True:
                status_str += _('Password:') + ' '
                decoded_pwd = self.get_decoded_password(self.password)
                if decoded_pwd:
                    status_str += '%s' % decoded_pwd
                else:
                    status_str += _('Unsupported password format, please regenerate link if you want to show password.')
                status_str += '<br><br>'

            # status_str += u'<button id="re-send-btn">重发邮件</button>'

        return status_str

    def get_decoded_password(self, password):
        return decode_password(password)

    def get_decoded_password_str(self):
        if not self.password:
            return None

        pwd = self.get_decoded_password(self.password)
        if pwd:
            return pwd
        else:
            return _('Unsupported password format, please regenerate link if you want to show password.')

    def need_remind(self):
        """Return `True` if DLP finished revise, while other people still in progress.

        """
        chain_status = FileShareApprovalStatus.objects.\
                       get_chain_status_by_share_link(share_link=self)
        if not chain_status:
            return False

        dlp_status = chain_status[0]
        if dlp_status.status == STATUS_VERIFING:
            return False        # no need to remind people if DLP is verifing

        if self.get_status() == STATUS_VERIFING:
            return True
        else:
            return False

    def email_receivers(self, send_to=None):
        if not send_to:
            extra_info = FileShareExtraInfo.objects.filter(share_link=self)
            if extra_info:
                send_to = [x.sent_to for x in extra_info]

        if not send_to:
            return

        def is_pa_email(email):
            """Check whether `email` is PingAn email address.
            """
            from fnmatch import fnmatch
            from seahub.share.settings import PA_EMAIL_PATTERN_LIST
            for patt in PA_EMAIL_PATTERN_LIST:
                if not patt:
                    continue

                if fnmatch(email, patt) is True:
                    return True

            return False

        for x in send_to:
            c = {
                'email': self.username,
                'to_email': x,
                'file_shared_link': self.get_full_url(),
                'file_shared_name': self.get_name(),
                'file_shared_type': _(u"file")
            }
            if is_pa_email(x):
                send_html_email(
                    _(u'A file is shared to you on %s') % SITE_NAME,
                    'shared_link_email.html',
                    c, None, [x])
            else:
                send_pafile_html_email_with_dj_template(
                    [x], _(u'A file is shared to you on %s') % SITE_NAME,
                    'share/pa_shared_link_email.html', c)
    #################### END PingAn Group related ######################


class OrgFileShareManager(models.Manager):
    def set_org_file_share(self, org_id, file_share):
        """Set a share link as org share link.

        Arguments:
        - `org_id`:
        - `file_share`:
        """
        ofs = self.model(org_id=org_id, file_share=file_share)
        ofs.save(using=self._db)
        return ofs

class OrgFileShare(models.Model):
    """
    Model used for organization file or dir shared link.
    """
    org_id = models.IntegerField(db_index=True)
    file_share = models.OneToOneField(FileShare)
    objects = OrgFileShareManager()

    objects = OrgFileShareManager()

class UploadLinkShareManager(models.Manager):

    def _make_password(self, password):
        aes = AESPasswordHasher()
        return aes.encode(password)

    def _get_upload_link_by_path(self, username, repo_id, path):
        ufs = list(super(UploadLinkShareManager, self).filter(repo_id=repo_id).filter(
            username=username).filter(path=path))
        if len(ufs) > 0:
            return ufs[0]
        else:
            return None

    def get_upload_link_by_path(self, username, repo_id, path):
        path = normalize_dir_path(path)
        return self._get_upload_link_by_path(username, repo_id, path)

    def create_upload_link_share(self, username, repo_id, path,
                                 password=None, expire_date=None):
        path = normalize_dir_path(path)
        token = gen_token(max_length=config.SHARE_LINK_TOKEN_LENGTH)
        if password is not None:
            password_enc = self._make_password(password)
        else:
            password_enc = None
        uls = super(UploadLinkShareManager, self).create(
            username=username, repo_id=repo_id, path=path, token=token,
            password=password_enc, expire_date=expire_date)
        uls.save()
        return uls

    def get_valid_upload_link_by_token(self, token):
        """Return upload link that exists and not expire, otherwise none.
        """
        try:
            fs = self.get(token=token)
        except self.model.DoesNotExist:
            return None

        if fs.expire_date is None:
            return fs
        else:
            if timezone.now() > fs.expire_date:
                return None
            else:
                return fs

class UploadLinkShare(models.Model):
    """
    Model used for shared upload link.
    """
    username = LowerCaseCharField(max_length=255, db_index=True)
    repo_id = models.CharField(max_length=36, db_index=True)
    path = models.TextField()
    token = models.CharField(max_length=100, unique=True)
    ctime = models.DateTimeField(default=datetime.datetime.now)
    view_cnt = models.IntegerField(default=0)
    password = models.CharField(max_length=128, null=True)
    expire_date = models.DateTimeField(null=True)
    objects = UploadLinkShareManager()

    def get_password(self):
        if self.password:
            try:
                aes = AESPasswordHasher()
                return aes.decode(self.password)
            except Exception:
                logger.error('Error occurred when get share link password')
                return ''
        else:
            return ''

    def is_encrypted(self):
        return True if self.password is not None else False

    def is_owner(self, owner):
        return owner == self.username

    def is_expired(self):
        if self.expire_date is not None and timezone.now() > self.expire_date:
            return True
        else:
            return False


class PrivateFileDirShareManager(models.Manager):
    def add_private_file_share(self, from_user, to_user, repo_id, path, perm):
        """
        """
        path = normalize_file_path(path)
        token = gen_token(max_length=10)

        pfs = self.model(from_user=from_user, to_user=to_user, repo_id=repo_id,
                         path=path, s_type='f', token=token, permission=perm)
        pfs.save(using=self._db)
        return pfs

    def add_read_only_priv_file_share(self, from_user, to_user, repo_id, path):
        """
        """
        return self.add_private_file_share(from_user, to_user, repo_id,
                                           path, PERMISSION_READ)

    def get_private_share_in_file(self, username, repo_id, path):
        """Get a file that private shared to ``username``.
        """
        path = normalize_file_path(path)

        ret = super(PrivateFileDirShareManager, self).filter(
            to_user=username, repo_id=repo_id, path=path, s_type='f')
        return ret[0] if len(ret) > 0 else None

    def add_private_dir_share(self, from_user, to_user, repo_id, path, perm):
        """
        """
        path = normalize_dir_path(path)
        token = gen_token(max_length=10)

        pfs = self.model(from_user=from_user, to_user=to_user, repo_id=repo_id,
                         path=path, s_type='d', token=token, permission=perm)
        pfs.save(using=self._db)
        return pfs

    def get_private_share_in_dir(self, username, repo_id, path):
        """Get a directory that private shared to ``username``.
        """
        path = normalize_dir_path(path)

        ret = super(PrivateFileDirShareManager, self).filter(
            to_user=username, repo_id=repo_id, path=path, s_type='d')
        return ret[0] if len(ret) > 0 else None

    def get_priv_file_dir_share_by_token(self, token):
        return super(PrivateFileDirShareManager, self).get(token=token)

    def delete_private_file_dir_share(self, from_user, to_user, repo_id, path):
        """
        """
        super(PrivateFileDirShareManager, self).filter(
            from_user=from_user, to_user=to_user, repo_id=repo_id,
            path=path).delete()

    def list_private_share_out_by_user(self, from_user):
        """List files/directories private shared from ``from_user``.
        """
        return super(PrivateFileDirShareManager, self).filter(
            from_user=from_user)

    def list_private_share_in_by_user(self, to_user):
        """List files/directories private shared to ``to_user``.
        """
        return super(PrivateFileDirShareManager, self).filter(
            to_user=to_user)

    def list_private_share_in_dirs_by_user_and_repo(self, to_user, repo_id):
        """List directories private shared to ``to_user`` base on ``repo_id``.
        """
        return super(PrivateFileDirShareManager, self).filter(
            to_user=to_user, repo_id=repo_id, s_type='d')

class PrivateFileDirShare(models.Model):
    from_user = LowerCaseCharField(max_length=255, db_index=True)
    to_user = LowerCaseCharField(max_length=255, db_index=True)
    repo_id = models.CharField(max_length=36, db_index=True)
    path = models.TextField()
    token = models.CharField(max_length=10, unique=True)
    permission = models.CharField(max_length=5)           # `r` or `rw`
    s_type = models.CharField(max_length=5, default='f') # `f` or `d`
    objects = PrivateFileDirShareManager()


###### signal handlers
from django.dispatch import receiver
from seahub.signals import repo_deleted

@receiver(repo_deleted)
def remove_share_info(sender, **kwargs):
    repo_id = kwargs['repo_id']

    FileShare.objects.filter(repo_id=repo_id).delete()
    UploadLinkShare.objects.filter(repo_id=repo_id).delete()

    # remove record of extra share
    ExtraSharePermission.objects.filter(repo_id=repo_id).delete()
    ExtraGroupsSharePermission.objects.filter(repo_id=repo_id).delete()


######################### Start PingAn Group related ########################
# TODO: remove in the future, use `FileShareApprovalStatus`
class FileShareVerify(models.Model):
    STATUS_CHOICES = (
        (STATUS_VERIFING, 'Verifing'),
        (STATUS_PASS, 'Pass'),
        (STATUS_VETO, 'Veto')
    )

    share_link = models.ForeignKey(FileShare)
    DLP_status = models.IntegerField(choices=STATUS_CHOICES,
                                     default=STATUS_VERIFING)
    DLP_vtime = models.DateTimeField(blank=True, null=True)

    line_manager_status = models.IntegerField(choices=STATUS_CHOICES,
                                              default=STATUS_VERIFING)
    line_manager_vtime = models.DateTimeField(blank=True, null=True)
    line_manager_msg = models.TextField(blank=True, null=True)
    department_head_status = models.IntegerField(choices=STATUS_CHOICES,
                                                 default=STATUS_VERIFING)
    department_head_vtime = models.DateTimeField(blank=True, null=True)
    department_head_msg = models.TextField(blank=True, null=True)
    comanager_head_status = models.IntegerField(choices=STATUS_CHOICES,
                                                default=STATUS_VERIFING)
    comanager_head_vtime = models.DateTimeField(blank=True, null=True)
    comanager_head_msg = models.TextField(blank=True, null=True)
    compliance_owner_status = models.IntegerField(choices=STATUS_CHOICES,
                                                  default=STATUS_VERIFING)
    compliance_owner_vtime = models.DateTimeField(blank=True, null=True)
    compliance_owner_msg = models.TextField(blank=True, null=True)
    compliance_owner2_status = models.IntegerField(choices=STATUS_CHOICES,
                                                  default=STATUS_VERIFING)
    compliance_owner2_vtime = models.DateTimeField(blank=True, null=True)
    compliance_owner2_msg = models.TextField(blank=True, null=True)

    # objects = FileShareVerifyManager()

    def dlp_pass(self):
        return True if self.DLP_status == STATUS_PASS else False
    def dlp_veto(self):
        return True if self.DLP_status == STATUS_VETO else False
    def dlp_verifying(self):
        return True if self.DLP_status == STATUS_VERIFING else False

    def line_manager_pass(self):
        return True if self.line_manager_status == STATUS_PASS else False
    def line_manager_veto(self):
        return True if self.line_manager_status == STATUS_VETO else False
    def line_manager_verifying(self):
        return True if self.line_manager_status == STATUS_VERIFING else False

    def department_head_pass(self):
        return True if self.department_head_status == STATUS_PASS else False
    def department_head_veto(self):
        return True if self.department_head_status == STATUS_VETO else False
    def department_head_verifying(self):
        return True if self.department_head_status == STATUS_VERIFING else False

    def comanager_head_pass(self):
        return True if self.comanager_head_status == STATUS_PASS else False
    def comanager_head_veto(self):
        return True if self.comanager_head_status == STATUS_VETO else False
    def comanager_head_verifying(self):
        return True if self.comanager_head_status == STATUS_VERIFING else False

    def compliance_owner_pass(self):
        return True if self.compliance_owner_status == STATUS_PASS else False
    def compliance_owner_veto(self):
        return True if self.compliance_owner_status == STATUS_VETO else False
    def compliance_owner_verifying(self):
        return True if self.compliance_owner_status == STATUS_VERIFING else False

    def compliance_owner2_pass(self):
        return True if self.compliance_owner2_status == STATUS_PASS else False
    def compliance_owner2_veto(self):
        return True if self.compliance_owner2_status == STATUS_VETO else False
    def compliance_owner2_verifying(self):
        return True if self.compliance_owner2_status == STATUS_VERIFING else False


class FileShareReviserChainManager(models.Manager):
    def add_file_share_reviser(
            self, department_name,
            line_manager_name, line_manager_account, line_manager_email,
            department_head_name, department_head_account, department_head_email,
            comanager_head_name, comanager_head_account, comanager_head_email,
            compliance_owner_name, compliance_owner_account, compliance_owner_email,
            compliance_owner2_name='', compliance_owner2_account='',
            compliance_owner2_email=''):

        reviser = self.model(department_name=department_name,

                             line_manager_name=line_manager_name,
                             line_manager_account=line_manager_account,
                             line_manager_email=line_manager_email,

                             department_head_name=department_head_name,
                             department_head_account=department_head_account,
                             department_head_email=department_head_email,

                             comanager_head_name=comanager_head_name,
                             comanager_head_account=comanager_head_account,
                             comanager_head_email=comanager_head_email,

                             compliance_owner_name=compliance_owner_name,
                             compliance_owner_account=compliance_owner_account,
                             compliance_owner_email=compliance_owner_email,

                             compliance_owner2_name=compliance_owner2_name,
                             compliance_owner2_account=compliance_owner2_account,
                             compliance_owner2_email=compliance_owner2_email,
        )

        reviser.save(using=self._db)

        return reviser

# TODO: remove in the future, use `FileShareApprovalChain`
class FileShareReviserChain(models.Model):
    department_name = models.CharField(max_length=200, db_index=True)

    line_manager_name = models.CharField(max_length=1024)
    line_manager_account = models.CharField(max_length=1024)
    line_manager_email = models.EmailField()

    department_head_name = models.CharField(max_length=1024)
    department_head_account = models.CharField(max_length=1024)
    department_head_email = models.EmailField()

    comanager_head_name = models.CharField(max_length=1024)
    comanager_head_account = models.CharField(max_length=1024)
    comanager_head_email = models.EmailField()

    compliance_owner_name = models.CharField(max_length=1024)
    compliance_owner_account = models.CharField(max_length=1024)
    compliance_owner_email = models.EmailField()

    compliance_owner2_name = models.CharField(max_length=1024, blank=True,
                                              null=True)
    compliance_owner2_account = models.CharField(max_length=1024, blank=True,
                                                 null=True)
    compliance_owner2_email = models.EmailField(blank=True, null=True)

    objects = FileShareReviserChainManager()

    def __unicode__(self):
        if self.compliance_owner2_email:
            return 'id: %s, department name: %s <--> %s %s %s %s|%s' % (
                self.pk, self.department_name, self.line_manager_email,
                self.department_head_email, self.comanager_head_email,
                self.compliance_owner_email, self.compliance_owner2_email)
        else:
            return 'id: %s, department name: %s <--> %s %s %s %s' % (
                self.pk, self.department_name, self.line_manager_email,
                self.department_head_email, self.comanager_head_email,
                self.compliance_owner_email)


# class FileShareReviserMap(models.Model):
#     """Direct map for user and revisor, if there is a record in this table,
#     we will not use department relation for revisors anymore.
#     """
#     username = LowerCaseCharField(max_length=255, db_index=True)
#     reviser_name = models.CharField(max_length=1024)
#     reviser_account = models.CharField(max_length=1024)
#     reviser_email = models.EmailField()

#     def __unicode__(self):
#         return '%s <--> %s (%s)' % (self.username, self.reviser_name, self.reviser_email)

class FileShareVerifyIgnore(models.Model):
    """Ignore user from share link verification. In some usercases, boss does
    not want to be verified when generate shared link.
    """
    username = LowerCaseCharField(max_length=255)


class FileShareReceiverManager(models.Manager):
    def batch_add_emails(self, share_link, emails):
        """Batch add receiver emails.
        """
        if not emails:
            return

        added = list(self.filter(share_link=share_link))
        for email in set(emails):
            if email in added:
                continue

            self.model(share_link=share_link, email=email).save()


class FileShareReceiver(models.Model):
    share_link = models.ForeignKey(FileShare)
    email = models.CharField(max_length=255)
    phone = models.CharField(max_length=50, blank=True, null=True)
    objects = FileShareReceiverManager()


class FileShareExtraInfo(models.Model):
    """Exrta infos for revisers to review.
    """
    share_link = models.ForeignKey(FileShare)
    sent_to = models.CharField(max_length=255)
    note = models.TextField()

    class Meta:
        unique_together = ("share_link", "sent_to")


class FileShareDownloadsManager(models.Manager):
    def add(self, share_link, username):
        """Record download info.

        Arguments:
        - `self`:
        - `share_link`:
        - `username`:
        """
        if len(self.filter(share_link=share_link, is_first_download=True)) > 0:
            is_first_download = False
        else:
            if share_link.pass_verify() and username != share_link.username:
                is_first_download = True
            else:
                is_first_download = False

        o = self.model(share_link=share_link, download_time=timezone.now(),
                       is_first_download=is_first_download)
        o.save(using=self._db)
        return o

    def get_first_download_time(self, share_link):
        r = self.filter(share_link=share_link, is_first_download=True)
        return r[0].download_time if r else None


class FileShareDownloads(models.Model):
    """
    Model used to record download info(download time, etc..)
    """
    share_link = models.ForeignKey(FileShare)
    download_time = models.DateTimeField()
    is_first_download = models.BooleanField()
    objects = FileShareDownloadsManager()


class UploadLinkShareUploads(models.Model):
    """
    Model used to record upload info(file name, upload time, IP, etc..).
    """
    upload_link = models.ForeignKey(UploadLinkShare)
    file_name = models.CharField(max_length=2048)
    file_size = models.BigIntegerField()
    upload_time = models.DateTimeField(db_index=True)
    upload_ip = models.CharField(max_length=20, db_index=True)


def is_valid_approval_chain_str(chain_str):
    """

    chain_str: 'a@pingan.com.cn' -> 'b@pingan.com.cn' | 'c@pingan.com.cn' -> 'd@pingan.com.cn'
    """
    splits = chain_str.split('<->')
    if len(splits) != 2:
        return False

    user = splits[0].strip()
    chain = splits[1].strip()
    if not user or not chain:
        return False

    try:
        if not ccnet_api.get_emailuser(user):
            return False
    except Exception:
        return False

    chain_list = approval_chain_str2list(chain)
    for e in chain_list:
        if isinstance(e, basestring):
            if not is_valid_email(e):
                return False

            try:
                ccnet_user_obj = ccnet_api.get_emailuser(e)
            except Exception:
                return False
        else:
            for x in e[1:]:
                if not is_valid_email(x):
                    return False
            try:
                ccnet_user_obj = ccnet_api.get_emailuser(x)
            except Exception:
                return False

        if not ccnet_user_obj:
            return False
        if not ccnet_user_obj.is_active:
            return False

    return True

def approval_chain_str2list(chain_str):
    """

    chain_str: 'a@pingan.com.cn' -> 'b@pingan.com.cn' | 'c@pingan.com.cn' -> 'd@pingan.com.cn'
    """
    chain_str = chain_str.strip()
    ele_list = [x.strip() for x in chain_str.split('->') if x.strip()]
    ret = []
    for x in ele_list:
        l = [y.strip() for y in x.split('|') if y.strip()]
        if len(l) > 1:
            ret.append(tuple(['op_or'] + l))
        else:
            ret.append(l[0])
    return ret

def approval_chain_list2str(chain_list, with_nickname=True):
    def get_nickname(username):
        nickname_cache = {}
        nickname = nickname_cache.get(username)
        if not nickname:
            nickname = email2nickname(username)
            nickname_cache[username] = nickname
        return nickname

    l = []
    for ele in chain_list:
        if isinstance(ele, basestring):
            if with_nickname:
                l.append("(%s) %s" % (get_nickname(ele), ele))
            else:
                l.append("%s" % (ele))
        else:
            t = []
            for x in ele[1:]:
                if with_nickname:
                    t.append("(%s) %s" % (get_nickname(x), x))
                else:
                    t.append("%s" % (x))
            l.append(' | '.join(t))

    return ' -> '.join(l)

class ApprovalChainManager(models.Manager):
    def create_chain(self, dept, chain_list):
        """

        chain_list -> ['a@pingan.com.cn', ('op_or', 'b@pingan.com.cn', 'c@pingan.com.cn')]
        """
        if not chain_list or not dept:
            return False

        parent = None
        for ele in chain_list:
            if isinstance(ele, basestring):
                obj = super(ApprovalChainManager, self).create(
                    parent=parent, email=ele, department=dept)
                parent = obj
            else:
                sibling_type = ele[0]
                objs = []
                for x in ele[1:]:
                    obj = super(ApprovalChainManager, self).create(
                        parent=parent, email=x, department=dept,
                        sibling_type=sibling_type
                    )
                    objs.append(obj)
                parent = objs[0]

        return True

    def get_by_department(self, dept, flat=False):
        """
        e.g.

        [u'a@pingan.com.cn', ('op_or', u'b@pingan.com.cn', u'c@pingan.com.cn'), u'd@pingan.com.cn']
        """
        # find root node which has no parent
        def find_root(l):
            x = []
            for ele in l:
                if not ele.parent:
                    x.append(ele)
            return x

        # find child nodes
        def find_child(l, parent_node):
            x = []
            for ele in l:
                if ele.parent and ele.parent == parent_node:
                    x.append(ele)
            return x

        # find sibling nodes
        def find_siblings(l, node):
            x = []
            for ele in l:
                if ele.parent == node.parent:
                    x.append(ele)
            return x

        if flat is True:
            return super(ApprovalChainManager, self).filter(department=dept).\
                values_list('email', flat=True)
        else:
            values = super(ApprovalChainManager, self).filter(department=dept)

            if len(values) == 0:
                return []

            ret = []
            root_node = find_root(values)
            if root_node:
                if len(root_node) > 1:
                    ret.append(tuple(['op_or'] + [x.email for x in root_node]))
                else:
                    ret.append(root_node[0].email)
            else:
                logger.warn('No root node in department chain: %s' % dept)
                return []

            root = root_node[0]
            while True:
                child = find_child(values, root)
                if not child:
                    break

                if len(child) == 1:
                    ret.append(child[0].email)
                else:
                    ret.append(tuple(['op_or'] + [x.email for x in child]))
                root = child[0]

            return ret

    def get_emails(self):
        l = super(ApprovalChainManager, self).values_list('email', flat=True)
        return list(set(l))


class ApprovalChain(models.Model):
    """Department approval chain"""
    parent = models.ForeignKey('self', blank=True, null=True,
                               on_delete=models.SET_NULL)
    sibling_type = models.CharField(max_length=255, default='')
    email = LowerCaseCharField(db_index=True, max_length=255)
    department = models.CharField(max_length=255, db_index=True)
    ctime = models.DateTimeField(db_index=True, default=timezone.now)
    mtime = models.DateTimeField(default=timezone.now)
    objects = ApprovalChainManager()


class UserApprovalChainManager(models.Manager):
    def create_chain(self, user, chain_list):
        """

        chain_list -> ['a@pingan.com.cn', ('op_or', 'b@pingan.com.cn', 'c@pingan.com.cn')]
        """
        if not chain_list or not user:
            return False

        parent = None
        for ele in chain_list:
            if isinstance(ele, basestring):
                obj = super(UserApprovalChainManager, self).create(
                    parent=parent, email=ele, user=user)
                parent = obj
            else:
                sibling_type = ele[0]
                objs = []
                for x in ele[1:]:
                    obj = super(UserApprovalChainManager, self).create(
                        parent=parent, email=x, user=user,
                        sibling_type=sibling_type
                    )
                    objs.append(obj)
                parent = objs[0]

        return True

    def get_by_user(self, user, flat=False):
        """
        e.g.

        [u'a@pingan.com.cn', ('op_or', u'b@pingan.com.cn', u'c@pingan.com.cn'), u'd@pingan.com.cn']
        """
        # find root node which has no parent
        def find_root(l):
            x = []
            for ele in l:
                if not ele.parent:
                    x.append(ele)
            return x

        # find child nodes
        def find_child(l, parent_node):
            x = []
            for ele in l:
                if ele.parent and ele.parent == parent_node:
                    x.append(ele)
            return x

        # find sibling nodes
        def find_siblings(l, node):
            x = []
            for ele in l:
                if ele.parent == node.parent:
                    x.append(ele)
            return x

        if flat is True:
            return super(UserApprovalChainManager, self).filter(user=user).\
                values_list('email', flat=True)
        else:
            values = super(UserApprovalChainManager, self).filter(user=user)

            if len(values) == 0:
                return []

            ret = []
            root_node = find_root(values)
            if root_node:
                if len(root_node) > 1:
                    ret.append(tuple(['op_or'] + [x.email for x in root_node]))
                else:
                    ret.append(root_node[0].email)
            else:
                logger.warn('No root node in user chain: %s' % user)
                return []

            root = root_node[0]
            while True:
                child = find_child(values, root)
                if not child:
                    break

                if len(child) == 1:
                    ret.append(child[0].email)
                else:
                    ret.append(tuple(['op_or'] + [x.email for x in child]))
                root = child[0]

            return ret

    def get_emails(self):
        l = super(UserApprovalChainManager, self).values_list('email', flat=True)
        return list(set(l))


class UserApprovalChain(models.Model):
    """User approval chain, used to replace deaprtment approval chain"""
    parent = models.ForeignKey('self', blank=True, null=True,
                               on_delete=models.SET_NULL)
    sibling_type = models.CharField(max_length=255, default='')
    email = LowerCaseCharField(db_index=True, max_length=255)
    user = LowerCaseCharField(db_index=True, max_length=255)
    ctime = models.DateTimeField(db_index=True, default=timezone.now)
    mtime = models.DateTimeField(default=timezone.now)
    objects = UserApprovalChainManager()


def get_chain_step_sibling_type(ele):
    # Return 'op_or' or 'op_and' if current step has multiple revisers.
    # Otherwize return None, means this step has only one reviser.
    try:
        ele.email
        return None
    except:
        return ele[0]

def get_chain_step_status(ele):
    if not get_chain_step_sibling_type(ele):  # no siblings
        return ele.status
    else:
        for x in ele[1:]:
            if x.status == STATUS_PASS:
                return STATUS_PASS
            if x.status == STATUS_VETO:
                return STATUS_VETO
        return STATUS_VERIFING

def get_chain_step_emails(ele):
    if not get_chain_step_sibling_type(ele):  # no siblings
        return [ele.email]
    else:
        return [x.email for x in ele[1:]]

def get_chain_next_step(chain_status_list, cur_email):
    next_step = None
    next_idx = 0
    for idx, obj in enumerate(chain_status_list):
        if get_chain_step_sibling_type(obj):  # siblings
            siblings = obj[1:]
            if cur_email in [x.email for x in siblings]:
                next_idx = idx + 1
            else:               # cur_email not in current step, goto next
                continue
        else:  # no siblings
            if cur_email == obj.email:
                next_idx = idx + 1
            else:               # cur_email not in current step, goto next
                continue

        try:
            next_ele = chain_status_list[next_idx]
            if get_chain_step_status(next_ele) != STATUS_VERIFING:
                continue
            else:
                next_step = next_ele
                break
        except IndexError:
            pass

    return next_step

class FileShareApprovalStatusManager(models.Manager):
    def get_dlp_status(self):
        return super(FileShareApprovalStatusManager, self).filter(email='dlp')

    def get_dlp_status_by_share_link(self, share_link):
        r = super(FileShareApprovalStatusManager, self).filter(share_link=share_link).filter(email='dlp')
        if len(r) == 0:
            return None
        else:
            return r[0]

    def get_by_email(self, username):
        return super(FileShareApprovalStatusManager, self).filter(email=username)

    def get_chain_status_by_share_link(self, share_link):
        """
        e.g.

        [stat_obj(email='dlp', status=1),
            stat_obj(email='a@pingan.com.cn', status=1),
            ('op_or', stat_obj(email='b@pingan.com.cn', status=0),
                      stat_obj(email='c@pingan.com.cn', status=1))]
        """
        status_dict = {}
        vtime_dict = {}
        msg_dict = {}
        for x in super(FileShareApprovalStatusManager, self).filter(share_link=share_link):
            status_dict[x.email] = x.status
            vtime_dict[x.email] = x.vtime
            msg_dict[x.email] = x.msg

        stat_obj = namedtuple('ApprovalStatusTuple', ['email', 'status', 'vtime', 'msg'])
        ret = [stat_obj(email='dlp', status=status_dict.get('dlp', STATUS_VERIFING),
               vtime=vtime_dict.get('dlp', None), msg=msg_dict.get('dlp', ''))]
        chain_list = share_link.get_approval_chain()
        if not chain_list:      # no reviser chain found for share link
            return []

        for ele in chain_list:
            if isinstance(ele, basestring):
                ret.append(stat_obj(email=ele, status=status_dict.get(
                    ele, STATUS_VERIFING), vtime=vtime_dict.get(ele, None), msg=msg_dict.get(ele, '')))
            else:
                tmp_list = [ele[0]]
                for x in ele[1:]:
                    tmp_list.append(
                        stat_obj(email=x,
                                 status=status_dict.get(x, STATUS_VERIFING),
                                 vtime=vtime_dict.get(x, None),
                                 msg=msg_dict.get(x, '')))
                ret.append(tuple(tmp_list))

        return ret

    def get_status(self, share_link):
        """Return status of share link.

        0: verifing
        1: pass
        2: veto
        """
        chain_status = self.get_chain_status_by_share_link(share_link)
        if not chain_status:
            return STATUS_VERIFING

        people_status = chain_status[1:]  # ignore first DLP status
        if not people_status:
            return STATUS_VERIFING

        status_list = []
        for ele in people_status:
            if get_chain_step_sibling_type(ele):
                tmp_status = STATUS_VERIFING
                for x in ele[1:]:  # ignore 'op_or'
                    if x.status == STATUS_PASS:
                        tmp_status = STATUS_PASS
                        break
                    if x.status == STATUS_VETO:
                        tmp_status = STATUS_VETO
                        break
                status_list.append(tmp_status)
            else:
                status_list.append(ele.status)

        for y in status_list:
            if y == STATUS_VERIFING:
                return STATUS_VERIFING
            if y == STATUS_VETO:
                return STATUS_VETO
        return STATUS_PASS

    def get_verbose_status(self, share_link):
        """Return verbose status of share link.

        e.g.
        [(0, 'Awating DLP verifing'),
        (0, 'Awaiting a (a@pingan.com.cn) verifing'),
        (0, 'Awaiting b (b@pingna.com.cn) | c (c@pingan.com.cn) verifing'),
        (0, 'Awaiting d (d@pingan.com.cn) verifing'),
        ]
        """
        chain_status = self.get_chain_status_by_share_link(share_link)
        if not chain_status:
            return []

        status_list = []

        # 1. add first DLP status
        dlp_status = chain_status[0]
        if dlp_status.status == STATUS_VERIFING:
            dlp_msg = _('Awaiting DLP verifing')
        elif dlp_status.status == STATUS_PASS:
            if dlp_status.vtime:
                dlp_msg = _('DLP passed at %s') % dlp_status.vtime.strftime('%Y-%m-%d')
            else:
                dlp_msg = _('DLP passed')
        elif dlp_status.status == STATUS_VETO:
            if dlp_status.vtime:
                dlp_msg = _('DLP veto at %s') % dlp_status.vtime.strftime('%Y-%m-%d')
            else:
                dlp_msg = _('DLP veto')
        status_list.append((dlp_status.status, dlp_msg))

        # 2. add people status in the chain
        for ele in chain_status[1:]:
            step_status = get_chain_step_status(ele)
            step_emails = get_chain_step_emails(ele)
            if step_status == STATUS_VERIFING:
                target_name = ' | '.join(
                    ["%s %s" % (email2nickname(x), x) for x in step_emails])
                target_msg = _('Awaiting %s verifing') % target_name
            elif step_status == STATUS_PASS:
                if get_chain_step_sibling_type(ele):
                    for x in ele[1:]:  # ignore 'op_or'
                        if x.status == STATUS_PASS:
                            target = x
                            break
                else:
                    target = ele

                target_name = "%s %s" % (email2nickname(target.email), target.email)
                if target.vtime:
                    target_msg = _('%(info)s passed at %(date)s') % {
                        'info': target_name,
                        'date': target.vtime.strftime('%Y-%m-%d')
                    }
                else:
                    target_msg = _('%s passed') % target_name
                if target.msg:  # add optional user approval msg
                    target_msg += ' (' + target.msg + ')'
            else:
                if get_chain_step_sibling_type(ele):
                    for x in ele[1:]:  # ignore 'op_or'
                        if x.status == STATUS_VETO:
                            target = x
                            break
                else:
                    target = ele

                target_name = "%s %s" % (email2nickname(target.email), target.email)
                if target.vtime:
                    target_msg = _('%(info)s veto at %(date)s') % {
                        'info': target_name,
                        'date': target.vtime.strftime('%Y-%m-%d')
                    }
                else:
                    target_msg = _('%s veto') % target_name
                if target.msg:  # add optional user approval msg
                    target_msg += ' (' + target.msg + ')'
            status_list.append((step_status, target_msg))

        return status_list

    def set_status(self, share_link, status, username, msg=None):
        """Set verify status.
        """
        try:
            s = super(FileShareApprovalStatusManager, self).get(
                share_link=share_link, email=username)
        except self.model.DoesNotExist:
            s = super(FileShareApprovalStatusManager, self).create(
                share_link=share_link, email=username)

        if s.status != STATUS_VERIFING:
            logger.warn('share link is already verified. status: %s' % status)
            return s

        s.status = status
        s.vtime = datetime.datetime.now()
        if msg is not None:
            s.msg = msg
        s.save()
        return s


class FileShareApprovalStatus(models.Model):
    STATUS_CHOICES = (
        (STATUS_VERIFING, 'Verifing'),
        (STATUS_PASS, 'Pass'),
        (STATUS_VETO, 'Veto')
    )

    DLP_EMAIL = 'dlp'           # use 'dlp' as email value for DLP records

    share_link = models.ForeignKey(FileShare)
    email = LowerCaseCharField(db_index=True, max_length=255)
    status = models.IntegerField(choices=STATUS_CHOICES,
                                 default=STATUS_VERIFING)
    msg = models.TextField(blank=True, null=True)
    ctime = models.DateTimeField(db_index=True, default=timezone.now)
    vtime = models.DateTimeField(blank=True, null=True)

    objects = FileShareApprovalStatusManager()

    class Meta:
        unique_together = (('share_link', 'email'),)


class FileShareApprovalChainManager(models.Manager):
    def get_by_share_link(self, share_link, flat=False):
        """
        e.g.
        [u'a@pingan.com.cn', ('op_or', u'b@pingan.com.cn', u'c@pingan.com.cn'), u'd@pingan.com.cn']
        """
        # find root node which has no parent
        def find_root(l):
            x = []
            for ele in l:
                if not ele.parent:
                    x.append(ele)
            return x

        # find child nodes
        def find_child(l, parent_node):
            x = []
            for ele in l:
                if ele.parent and ele.parent == parent_node:
                    x.append(ele)
            return x

        # find sibling nodes
        def find_siblings(l, node):
            x = []
            for ele in l:
                if ele.parent == node.parent:
                    x.append(ele)
            return x

        if flat is True:
            return super(FileShareApprovalChainManager, self).filter(
                share_link=share_link).\
                values_list('email', flat=True)
        else:
            values = super(FileShareApprovalChainManager, self).filter(
                share_link=share_link)

            if len(values) == 0:
                return []

            ret = []
            root_node = find_root(values)
            if root_node:
                if len(root_node) > 1:
                    ret.append(tuple(['op_or'] + [x.email for x in root_node]))
                else:
                    ret.append(root_node[0].email)
            else:
                logger.warn('No root node in department chain: %s' % share_link.pk)
                return []

            root = root_node[0]
            while True:
                child = find_child(values, root)
                if not child:
                    break

                if len(child) == 1:
                    ret.append(child[0].email)
                else:
                    ret.append(tuple(['op_or'] + [x.email for x in child]))
                root = child[0]

            return ret

    def create_fs_approval_chain(self, share_link):
        username = share_link.username
        chain = []

        # 1. get user approval chain
        chain = UserApprovalChain.objects.get_by_user(username)

        # 2. get chain from user department
        if not chain:
            d_profile = DetailedProfile.objects.get_detailed_profile_by_user(username)
            if d_profile:
                chain = ApprovalChain.objects.get_by_department(d_profile.department)
            else:
                logger.error('No detailed profile(department, ... etc) found for user %s' % username)

        if not chain:
            return

        # 3. create share link chain info
        parent = None
        for ele in chain:
            if isinstance(ele, basestring):
                obj = super(FileShareApprovalChainManager, self).create(
                    share_link=share_link, parent=parent, email=ele)
                parent = obj
            else:
                sibling_type = ele[0]
                objs = []
                for x in ele[1:]:
                    obj = super(FileShareApprovalChainManager, self).create(
                        share_link=share_link, parent=parent, email=x,
                        sibling_type=sibling_type
                    )
                    objs.append(obj)
                parent = objs[0]

        return True


class FileShareApprovalChain(models.Model):
    """Share link approval chain info. Use department approval chain info
    if link not found in this table.
    """
    share_link = models.ForeignKey(FileShare)
    email = LowerCaseCharField(db_index=True, max_length=255)
    parent = models.ForeignKey('self', blank=True, null=True,
                               on_delete=models.SET_NULL)
    sibling_type = models.CharField(max_length=255, default='')
    objects = FileShareApprovalChainManager()


class FileShareDecryptAudit(models.Model):
    """Record share link decrypt failed attempt.
    share link info, request ip, user agent.
    """
    share_link = models.ForeignKey(FileShare)
    decrypt_success = models.BooleanField(db_index=True)
    repo_id = models.CharField(max_length=36, db_index=True)
    path = models.TextField()
    ip = models.CharField(max_length=20, db_index=True)
    device = models.CharField(max_length=256)
    ctime = models.DateTimeField(default=datetime.datetime.now, db_index=True)


########## Handle signals to remove file share
from django.dispatch import receiver
from seahub.signals import file_deleted, file_edited
from seahub.share.signals import file_shared_link_created, file_shared_link_decrypted

@receiver([file_deleted, file_edited])
def file_updated_cb(sender, **kwargs):
    """Remove file share when file is deleted/edited/replaced.

    Arguments:
    - `sender`:
    - `**kwargs`:
    """
    repo_id = kwargs['repo_id']
    parent_dir = kwargs['parent_dir']
    file_name = kwargs['file_name']
    username = kwargs['username']
    path = posixpath.join(parent_dir, file_name)

    FileShare.objects.filter(username=username).filter(
        repo_id=repo_id).filter(path=path).delete()

########## Handle signals to add extra info when shared link created.
@receiver(file_shared_link_created)
def fs_created_cb(sender, **kwargs):
    l = [x.strip() for x in kwargs['sent_to'] if x.strip()]
    sent_to = sorted(set(l), key=lambda x: l.index(x))

    note = kwargs['note']
    for e in sent_to:
        FileShareExtraInfo.objects.create(share_link=sender, sent_to=e,
                                          note=note)

########## Handle signals to record file share decrypt info
@receiver(file_shared_link_decrypted)
def fs_decrypted_cb(sender, **kwargs):
    fs = kwargs['fileshare']
    if not isinstance(fs, FileShare):
        return

    req = kwargs['request']
    success = kwargs['success']

    FileShareDecryptAudit(share_link=fs, decrypt_success=success,
                          repo_id=fs.repo_id, path=fs.path,
                          ip=get_remote_ip(req),
                          device=req.META.get("HTTP_USER_AGENT", '-')[:255]).save()

######################## End PingAn Group related ##########################
