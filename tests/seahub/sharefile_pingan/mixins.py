from dateutil.relativedelta import relativedelta
from django.core.urlresolvers import reverse
from django.utils import timezone

from seahub.share.models import (FileShare, FileShareVerify,
                                 FileShareReviserChain, FileShareApprovalChain,
                                 FileShareApprovalStatus)
from seahub.profile.models import Profile, DetailedProfile


class SetupRevisersMixin(object):
    def setup_revisers(self):

        department = 'dept_A'
        FileShareReviserChain.objects.add_file_share_reviser(
            department,
            # line manager
            self.user.username, self.user.username, self.user.username,
            # department head
            self.user.username, self.user.username, self.user.username,
            # comanager head
            self.admin.username, self.admin.username, self.admin.username,
            # compliance owner
            self.admin.username, self.admin.username, self.admin.username,
        )

        Profile.objects.add_or_update(self.user.username, '', '')
        DetailedProfile.objects.add_detailed_profile(self.user.username, department, '')

        Profile.objects.add_or_update(self.admin.username, '', '')
        DetailedProfile.objects.add_detailed_profile(self.admin.username, department, '')

    def setup_revisers2(self):
        department = 'dept_A'
        FileShareReviserChain.objects.add_file_share_reviser(
            department,
            # line manager
            self.user.username, self.user.username, self.user.username,
            # department head
            self.user.username, self.user.username, self.user.username,
            # comanager head
            self.admin.username, self.admin.username, self.admin.username,
            # compliance owner
            self.admin.username, self.admin.username, self.admin.username,
            # compliance owner2
            self.user.username, self.user.username, self.user.username,
        )

        Profile.objects.add_or_update(self.user.username, '', '')
        DetailedProfile.objects.add_detailed_profile(self.user.username, department, '')

        Profile.objects.add_or_update(self.admin.username, '', '')
        DetailedProfile.objects.add_detailed_profile(self.admin.username, department, '')

    # def setup_reviser_map(self):
    #     FileShareReviserMap.objects.create(
    #         username=self.user.username, reviser_name='', reviser_account='',
    #         reviser_email=self.user.username)


class AddDownloadLinkMixin(object):
    def add_shared_file_link(self, repo_id=None, file_path=None):
        assert len(FileShare.objects.all()) == 0
        assert len(FileShareVerify.objects.all()) == 0

        self.login_as(self.user)

        repo_id = repo_id or self.repo.id
        path = file_path or self.file
        passwd = 'A12345678$'
        expire_date = timezone.now() + relativedelta(days=3)

        fs = FileShare.objects.create_file_link(self.user.username, repo_id, path,
                                                passwd, expire_date)
        FileShareApprovalChain.objects.create_fs_approval_chain(fs)
        fs_v = FileShareApprovalStatus(share_link=fs,
                                       email=FileShareApprovalStatus.DLP_EMAIL)
        fs_v.save()

        assert len(FileShare.objects.all()) == 1
        assert len(FileShareApprovalStatus.objects.all()) == 1
        # assert len(FileShareVerify.objects.all()) == 1

        return FileShare.objects.all()[0]
