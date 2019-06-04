# Copyright (c) 2012-2016 Seafile Ltd.
import django.dispatch

share_repo_to_user_successful = django.dispatch.Signal(providing_args=["from_user", "to_user", "repo", "path", "org_id"])
share_repo_to_group_successful = django.dispatch.Signal(providing_args=["from_user", "group_id", "repo", "path", "org_id"])

######################### Start PingAn Group related ########################
file_shared_link_created = django.dispatch.Signal(
    providing_args=["sent_to", "note"])
file_shared_link_verify = django.dispatch.Signal(
    providing_args=["from_user", "to_user", "token"])
file_shared_link_decrypted = django.dispatch.Signal(
    providing_args=["fileshare", "request", "success"])
######################### End PingAn Group related ##########################
