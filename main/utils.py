from django.contrib.auth.models import User
from rest_framework.authtoken.models import Token
from rest_framework.response import Response
from rest_framework import status
from .models import Profile


def process_sso_profile(sso_profile):
    try:
        user = User.objects.get(username=sso_profile['username'])
        token, _ = Token.objects.get_or_create(user=user)
    except User.DoesNotExist:
        user = User(username=sso_profile['username'])
        user.set_unusable_password()
        user.save()
        generate_user_profile(user, sso_profile)
        token = Token.objects.create(user=user)
    return token.key

def generate_user_profile(user, sso_profile):
	attr = sso_profile['attributes']
	return Profile.objects.create(
        user=user,
        name=attr['nama'],
        npm=attr['npm'],
        username=sso_profile['username'],
        role=attr['peran_user'],
        org_code=attr['kd_org'],
        faculty=attr['faculty'],
        study_program=attr['study_program'],
        educational_program=attr['educational_program'],
    )

def response(status = status.HTTP_200_OK, data = None, error = None):
    return Response({
					"data": data,
					"error": error,
				}, status=status)

def validateParams(request, params):
    for param in params:
        res = request.query_params.get(param)
        if res is None:
            return response(error="{} is required".format(param), status=status.HTTP_404_NOT_FOUND)
    return None
	
def validateBody(request, attrs):
    for attr in attrs:
        res = request.data.get(attr)
        if res is None:
            return response(error="{} is required".format(attr), status=status.HTTP_404_NOT_FOUND)
    return None