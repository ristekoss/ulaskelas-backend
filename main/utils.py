from django.contrib.auth.models import User
from rest_framework.authtoken.models import Token
from .models import Profile


def process_sso_profile(sso_profile):
    user = User.objects.get(username=sso_profile['username'])
    if user:
        return Token.objects.get_or_create(user=user)
    else:
        user = User(username=sso_profile['username'])
        user.set_unusable_password()
        user.save()
        generate_user_profile(user, sso_profile)
        return Token.objects.create(user=user)


def generate_user_profile(user, sso_profile):
    attr = sso_profile['attributes']
    return Profile.objects.create(
        user=user,
        name=attr['nama'],
        npm=attr['npm'],
        role=attr['peran_user'],
        org_code=attr['kd_org'],
        faculty=attr['faculty'],
        study_program=attr['study_program'],
        educational_program=attr['educational_program'],
    )
