# Copyright (c) 2012-2016 Seafile Ltd.
from django.conf.urls import url

from views import *

urlpatterns = [
    url(r'^link/send/$', send_shared_link, name='send_shared_link'),
    url(r'^link/save/$', save_shared_link, name='save_shared_link'),
    url(r'^upload_link/send/$', send_shared_upload_link, name='send_shared_upload_link'),
    url(r'^ajax/private-share-dir/$', ajax_private_share_dir, name='ajax_private_share_dir'),
    url(r'^ajax/get-link-audit-code/$', ajax_get_link_audit_code, name='ajax_get_link_audit_code'),
]

######################### Start PingAn Group related ########################
from .views_pingan import *
urlpatterns += [
    url(r'^links/verify/$', list_file_share_verify, name='list_file_share_verify'),
    url(r'^links/verify/remove/(?P<sid>\d+)/$', remove_file_share_verify, name='remove_file_share_verify'),
    url(r'^links/export-verified-links/$', export_verified_links, name='export_verified_links'),
    url(r'^ajax/change-download-link-status/$', ajax_change_dl_link_status, name='ajax_change_dl_link_status'),
    url(r'^ajax/get-link-verify-code/$', ajax_get_link_verify_code, name='ajax_get_link_verify_code'),
    url(r'^ajax/remind-revisers/$', ajax_remind_revisers, name='ajax_remind_revisers'),
    url(r'^ajax/get-link-receivers/$', ajax_get_link_receivers, name='ajax_get_link_receivers'),
    url(r'^ajax/email-link-receivers/$', ajax_email_link_receivers, name='ajax_email_link_receivers'),
    url(r'^ajax/get-link-status/$', ajax_get_link_status, name='ajax_get_link_status'),
]
######################### End PingAn Group related ##########################
