from rest_framework.decorators import api_view, permission_classes
from rest_framework import permissions, status
from rest_framework.response import Response
from datetime import datetime
from .utils import process_sso_profile
from sso.decorators import with_sso_ui
from django.core import serializers

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
@with_sso_ui()
def login(request, sso_profile):
    """
    Verify SSO UI ticket and service_url.
    Create a new user & profile if it doesn't exists
    and return token if ticket is valid.
    """
    if sso_profile is not None:
        token = process_sso_profile(sso_profile)
        data = {'token': token, 'profile': sso_profile}
        return Response(data=data)

    data = {'message': 'invalid sso'}
    return Response(data=data, status=status.HTTP_401_UNAUTHORIZED)


@api_view(['GET'])
# Default permission for any endpoint: permissions.IsAuthenticated
def restricted_sample_endpoint(request):
    """
    Simple sample enpoint that require Token Authorization.
    """
    message = 'If you can see this, it means you\'re already logged in.'
    username = request.user.username
    if hasattr(request.user, 'profile'):
        profile = request.user.profile
    else:
        profile = None
    # It's just quick hacks for temporary output.
    # Should be used Django Rest Serializer instead.
    profile_json = serializers.serialize('json', [profile])
    return Response({'message': message,
                     'username': username,
                     'profile': profile_json})
