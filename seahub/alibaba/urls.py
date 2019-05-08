# Copyright (c) 2012-2018 Seafile Ltd.

from django.conf.urls import url
from seahub.alibaba.views import AlibabaUserEditFileView

urlpatterns = [
    url(r'^api/user-edit-file/$', AlibabaUserEditFileView.as_view(), name="alibaba-api-user-edit-file"),
]
