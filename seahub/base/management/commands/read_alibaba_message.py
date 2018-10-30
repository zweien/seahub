# Copyright (c) 2012-2016 Seafile Ltd.
# encoding: utf-8

import json
import time
import logging
from random import randint
from constance import config

from django.core.management.base import BaseCommand

from seaserv import seafile_api, ccnet_api
from seahub.utils import clear_token
from seahub.signals import repo_transfered
from seahub.share.utils import share_dir_to_user, share_dir_to_group
from seahub.share.models import ExtraSharePermission, FileShare
from seahub.profile.models import Profile
from seahub.options.models import UserOptions
from seahub.utils import normalize_dir_path
from seahub.base.accounts import UNUSABLE_PASSWORD

from seahub.alibaba.models import AlibabaMessageQueue, AlibabaProfile, \
        ALIBABA_MESSAGE_TOPIC_LEAVE_FILE_HANDOVER

from seahub.settings import LOG_DIR
logging.basicConfig(
    level = logging.DEBUG,
    format='%(asctime)s %(filename)s[line:%(lineno)d] %(levelname)s %(message)s',
    datefmt = '%a, %d %b %Y %H:%M:%S',
    filename = normalize_dir_path(LOG_DIR) + 'seahub.log',
)

def get_leave_work_ccnet_email(message):

    message_dict = json.loads(message.message_body)
    leave_work_no = message_dict['leaveWorkNo']

    # existence check for leave worker
    # `False` parameter for select all workers in alibaba profile
    leave_work_profile = AlibabaProfile.objects.get_profile_by_work_no(leave_work_no, False)
    if not leave_work_profile:
        print 'leaveWorkNo %s not found in alibaba profile.' % leave_work_no
        logging.error('leaveWorkNo %s not found in alibaba profile.' % leave_work_no)
        return None

    leave_ccnet_email = leave_work_profile.uid
    if not leave_ccnet_email:
        print 'uid not found for leaveWorkNo %s.' % leave_work_no
        logging.error('uid not found for leaveWorkNo %s.' % leave_work_no)
        return None

    return leave_ccnet_email

def get_super_work_ccnet_email(message):
    message_dict = json.loads(message.message_body)
    super_work_no = message_dict['superWorkNo']

    # existence check for super worker
    # No `False` parameter, only select workers at work
    super_work_profile = AlibabaProfile.objects.get_profile_by_work_no(super_work_no)
    if not super_work_profile:
        print 'superWorkNo %s not found in alibaba profile.' % super_work_no
        logging.error('superWorkNo %s not found in alibaba profile.' % super_work_no)
        return None

    super_ccnet_email = super_work_profile.uid
    if not super_ccnet_email:
        print 'uid not found for superWorkNo %s.' % super_work_no
        logging.error('uid not found for superWorkNo %s.' % super_work_no)
        return None

    return super_ccnet_email

def other_actions_for_leave_worker(ccnet_user_obj):

    email = ccnet_user_obj.email

    # inactive user
    ccnet_api.update_emailuser('DB', ccnet_user_obj.id, UNUSABLE_PASSWORD, 0, 0)

    # remove expired share links
    share_links = FileShare.objects.filter(username=email)
    for link in share_links:
        if link.is_expired():
            link.delete()

    # remove shared in repos
    shared_in_repos = seafile_api.get_share_in_repo_list(email, -1, -1)
    for r in shared_in_repos:
        seafile_api.remove_share(r.repo_id, r.user, email)

    # remove extra(admin) permission
    ExtraSharePermission.objects.filter(share_to=email).delete()

    # clear web api and repo sync token
    clear_token(email)

    # remove seahub profile
    Profile.objects.delete_profile_by_user(email)

    # remove terms and conditions
    if config.ENABLE_TERMS_AND_CONDITIONS:
        from termsandconditions.models import UserTermsAndConditions
        UserTermsAndConditions.objects.filter(username=email).delete()

    # remove user options
    UserOptions.objects.filter(email=email).delete()

def get_unexpired_share_link_repos(email):
    ''' Get owned repos that have unexpired share link
    '''

    repo_ids = []
    share_links = FileShare.objects.filter(username=email)
    for link in share_links:
        if not link.is_expired():
            repo_ids.append(link.repo_id)

    repos = []
    for repo_id in repo_ids:
        repo = seafile_api.get_repo(repo_id)
        if seafile_api.is_repo_owner(email, repo_id) and \
                repo not in repos:
            repos.append(repo)

    return repos

def get_should_delete_repo_ids(owned_repos, shared_out_repos,
        public_repos, share_link_repos):
    """ Retrun repo id list that should been deleted.
    """

    shared_out_repo_ids = [repo.origin_repo_id if repo.is_virtual else repo.id
            for repo in shared_out_repos]

    public_repos_ids = [repo.id for repo in public_repos]

    share_link_repos_ids = [repo.id for repo in share_link_repos]

    # filter out public repos
    # filter out repos that repo/folder has been shared out
    should_delete_repo_ids = [repo.id for repo in owned_repos if repo.id
            not in shared_out_repo_ids + public_repos_ids + share_link_repos_ids]

    return should_delete_repo_ids

def get_repo_folder_share_info(shared_out_repos):
    """ Get repo share info.
    Return:
    [
        (repo_id, folder_path, permission, user_shared_to, group_id_shared_to),
        ...
    ]
    """

    repo_folder_share_info = []
    for repo in shared_out_repos:

        if not repo.is_virtual:
            # repo share to user
            if repo.share_type == 'personal':
                repo_folder_share_info.append((repo.id, '/', repo.permission, repo.user, None))

            # repo share to group
            if repo.share_type == 'group':
                repo_folder_share_info.append((repo.id, '/', repo.permission, None, repo.group_id))
        else:
            # folder share to user
            if repo.share_type == 'personal':
                repo_folder_share_info.append((repo.origin_repo_id, repo.origin_path, \
                        repo.permission, repo.user, None))

            # folder share to group
            if repo.share_type == 'group':
                repo_folder_share_info.append((repo.origin_repo_id, repo.origin_path, \
                        repo.permission, None, repo.group_id))

    return repo_folder_share_info

def get_owned_groups(email):
    owned_groups = []
    groups = ccnet_api.get_groups(email)
    for group in groups:
        if group.creator_name == email:
            owned_groups.append(group)
    return owned_groups

def get_new_group_owner(group_id, leave_ccnet_email, super_ccnet_email):

    members = ccnet_api.get_group_members(group_id)
    if len(members) == 1:
        return None

    if ccnet_api.is_group_user(group_id, super_ccnet_email):
        return super_ccnet_email

    work_no_list = []
    work_no_email_dict = {}
    for member in members:

        email = member.user_name
        if email == leave_ccnet_email:
            continue
        profile_dict = AlibabaProfile.objects.get_profile_dict(email)
        work_no = profile_dict['work_no']

        work_no_list.append(work_no)
        work_no_email_dict[work_no] = email

    def slice_string(string):
        # 'abc123456' to '123456'
        for idx, val in enumerate(string):
            if val.isdigit():
                return string[idx:]

    def numeric_compare(x, y):

        if x.isdigit() and y.isdigit():
            return int(x) - int(y)

        if x.isdigit():
            return -1

        if y.isdigit():
            return 1

        x = slice_string(x)
        y = slice_string(y)
        return int(x) - int(y)

    work_no_list.sort(cmp=numeric_compare)
    return work_no_email_dict[work_no_list[0]]


class Command(BaseCommand):

    help = "Read messages from alibaba message queue database table."

    def handle(self, *args, **options):

        random_second = randint(0, 60 * 10)
        time.sleep(random_second)

        messages = AlibabaMessageQueue.objects.filter(topic=ALIBABA_MESSAGE_TOPIC_LEAVE_FILE_HANDOVER)

        for message in messages:

            if message.lock_version == 1:
                continue

            if message.is_consumed == 1:
                continue

            self.stdout.write("\n\nStart for message %s.\n" % message.id)

            try:
                # get leave alibaba profile
                leave_ccnet_email = get_leave_work_ccnet_email(message)

                # leave NOT in alibaba profile
                # mark exception
                if not leave_ccnet_email:
                    AlibabaMessageQueue.objects.mark_message_exception(message.id)
                    continue

                # get leave ccnet email
                leave_ccnet_user_obj = ccnet_api.get_emailuser(leave_ccnet_email)

                # leave not in Seafile
                if not leave_ccnet_user_obj:
                    AlibabaMessageQueue.objects.mark_message_consumed(message.id)
                    continue

                # get super alibaba profile
                super_ccnet_email = get_super_work_ccnet_email(message)

                # super NOT in alibaba profile
                # mark exception
                if not super_ccnet_email:
                    AlibabaMessageQueue.objects.mark_message_exception(message.id)
                    continue

                # super NOT in seafile
                # create super ccnet user
                if not ccnet_api.get_emailuser(super_ccnet_email):
                    ccnet_api.add_emailuser(super_ccnet_email,
                            UNUSABLE_PASSWORD, 0, 0)

                # lock message
                AlibabaMessageQueue.objects.add_lock(message.id)

                ## the following is for transfer/delete owned groups
                owned_groups = get_owned_groups(leave_ccnet_email)
                for group in owned_groups:
                    new_group_owner = get_new_group_owner(group.id,
                            leave_ccnet_email, super_ccnet_email)
                    if new_group_owner:
                        print '\ntransfer group %s to %s' % (group.id, new_group_owner)
                        logging.error('transfer group %s to %s' % (group.id, new_group_owner))
                        ccnet_api.set_group_creator(group.id, new_group_owner)
                    else:
                        print '\ndelete group %s' % group.id
                        logging.error('delete group %s' % group.id)
                        ccnet_api.remove_group(group.id)

                # remove user from joined groups
                ccnet_api.remove_group_user(leave_ccnet_email)

                # the following is for delete/reshare repo/folder

                # get owned repos
                owned_repos = seafile_api.get_owned_repo_list(leave_ccnet_email)

                # get repos that repo/sub-folder has been shared out
                shared_out_repos = []
                shared_out_repos += seafile_api.get_share_out_repo_list(
                        leave_ccnet_email, -1, -1)
                shared_out_repos += seafile_api.get_group_repos_by_owner(
                        leave_ccnet_email)

                # get owned public repos
                public_repos = seafile_api.list_inner_pub_repos_by_owner(leave_ccnet_email)

                # get owned repos that have unexpired share link
                share_link_repos = get_unexpired_share_link_repos(leave_ccnet_email)

                # delete repos that repo/sub-folder has NOT been shared to
                # user/group/public
                should_delete_repo_ids = get_should_delete_repo_ids(
                        owned_repos, shared_out_repos, public_repos,
                        share_link_repos)

                for repo_id in should_delete_repo_ids:
                    print '\ndelete repo %s' % repo_id
                    logging.error('delete repo %s' % repo_id)
                    seafile_api.remove_repo(repo_id)

                # transfer repo to super
                for repo in share_link_repos:
                    if not seafile_api.is_repo_owner(super_ccnet_email, repo.id):
                        print '\ntransfer repo %s with unexpired share link' % repo.id
                        logging.error('transfer repo %s with unexpired share link' % repo.id)
                        seafile_api.set_repo_owner(repo.id, super_ccnet_email)
                        repo_transfered.send(sender=None, org_id=-1, operator='Administrator',
                                repo_id=repo_id, from_user=leave_ccnet_email,
                                to_user=super_ccnet_email)

                # transfer repo to super
                # reshare repo public
                for repo in public_repos:
                    if not seafile_api.is_repo_owner(super_ccnet_email, repo.id):
                        print '\ntransfer repo %s' % repo.id
                        logging.error('transfer repo %s' % repo.id)
                        seafile_api.set_repo_owner(repo.id, super_ccnet_email)
                        repo_transfered.send(sender=None, org_id=-1, operator='Administrator',
                                repo_id=repo_id, from_user=leave_ccnet_email,
                                to_user=super_ccnet_email)

                    print 'reshare repo %s to public' % repo.id
                    logging.error('reshare repo %s to public' % repo.id)
                    seafile_api.add_inner_pub_repo(repo.id, repo.permission)

                # transfer repo to super
                # reshare repo/folder to user/group
                repo_folder_share_info = get_repo_folder_share_info(shared_out_repos)
                for info in repo_folder_share_info:

                    repo_id, folder_path, permission, to_user, to_group_id = info

                    # transfer repo
                    if not seafile_api.is_repo_owner(super_ccnet_email, repo_id):
                        print '\ntransfer repo %s' % repo_id
                        logging.error('transfer repo %s' % repo_id)
                        seafile_api.set_repo_owner(repo_id, super_ccnet_email)
                        repo_transfered.send(sender=None, org_id=-1, operator='Administrator',
                                repo_id=repo_id, from_user=leave_ccnet_email,
                                to_user=super_ccnet_email)

                    repo = seafile_api.get_repo(repo_id)

                    print 'reshare repo/folder to user/group'
                    print info
                    logging.error('reshare repo/folder to user/group')
                    logging.error(info)
                    if to_user:
                        if to_user == super_ccnet_email:
                            continue
                        share_dir_to_user(repo, folder_path, super_ccnet_email, \
                                super_ccnet_email, to_user, permission)

                    if to_group_id:
                        share_dir_to_group(repo, folder_path, super_ccnet_email, \
                                super_ccnet_email, to_group_id, permission)

                # other actions
                other_actions_for_leave_worker(leave_ccnet_user_obj)

                AlibabaMessageQueue.objects.mark_message_consumed(message.id)
            except Exception as e:
                logging.error(e)
                print e

            AlibabaMessageQueue.objects.remove_lock(message.id)
