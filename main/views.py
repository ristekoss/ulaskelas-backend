from main.utils import process_sso_profile
from sso.utils import authenticate, get_cas_client
from rest_framework.decorators import api_view, permission_classes
from rest_framework import permissions, status
from rest_framework.response import Response
from datetime import datetime
# Create your views here.


@api_view(['GET'])
@permission_classes((permissions.AllowAny,))
def sample_api(request):
    """
    Just an overly simple sample enpoint to call.
    """
    time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    message = 'API Call succeed on %s' % time
    return Response({'message': message})


@api_view(['GET', 'POST'])
@permission_classes((permissions.AllowAny,))
def login(request):
    """
    Verify SSO UI ticket and service_url.
    Create a new user & profile if it doesn't exists
    and return token if ticket is valid.
    """
    # TODO: Testing with actual frontend
    data = request.POST
    ticket = data.get("ticket")
    service_url = data.get("service_url")
    if (ticket is not None) and (service_url is not None):
        client = get_cas_client(service_url)
        sso_profile = authenticate(ticket, client)
        if sso_profile is not None:
            token = process_sso_profile(sso_profile)
            data = {'token': token, 'profile': sso_profile}
            return Response(data=data)

    data = {'message': 'invalid ticket',
            'received_ticket': ticket,
            'received_service_url': service_url, }
    return Response(data=data, status=status.HTTP_401_UNAUTHORIZED)