from rest_framework.views import APIView
from rest_framework.reverse import reverse
from rest_framework.response import Response
from django.shortcuts import get_object_or_404

from seahub.api2.throttling import AnonRateThrottle
from seahub.base.models import ClientSSOToken
from seahub.utils import get_service_url


class ClientSSOLink(APIView):
    throttle_classes = (AnonRateThrottle, )
    permission_classes = ()

    def get(self, request, uuid):
        # query SSO status
        t = get_object_or_404(ClientSSOToken, token=uuid)
        if not t.is_success():
            return Response({'status': t.status})

        t.accessed()

        return Response({
            'status': t.status,
            'email': t.email,
            'apiToken': t.api_key
        })

    def post(self, request):
        # create SSO link
        t = ClientSSOToken.objects.new()

        return Response({
            'link': get_service_url().rstrip('/') + reverse(
                'client_sso', args=[t.token])
        })
