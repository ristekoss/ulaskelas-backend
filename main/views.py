from django.shortcuts import render
from rest_framework.decorators import api_view, permission_classes
from rest_framework import permissions
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
