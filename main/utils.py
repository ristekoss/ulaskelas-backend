from datetime import datetime
import os
from django.contrib.auth.models import User
from django.core.paginator import Paginator
from rest_framework.authtoken.models import Token
from rest_framework.response import Response
from rest_framework import status
from .models import Profile, UserCumulativeGPA


def process_sso_profile(sso_profile):
    try:
        user = User.objects.get(username__iexact=sso_profile['username'])
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
        is_blocked=False,
    )

def get_profile_term(profile):
		dt = datetime.today()
		term = ((dt.year % 100) - int(profile.npm[:2])) * 2
		term += 0 if dt.month < 7 else 1
		return term

def response(status = status.HTTP_200_OK, data = None, error = None):
    return Response({
					"data": data,
					"error": error,
				}, status=status)

def validate_params(request, params):
    for param in params:
        res = request.query_params.get(param)
        if res is None:
            return response(error="{} is required".format(param), status=status.HTTP_404_NOT_FOUND)
    return None
	
def validate_body(request, attrs):
    for attr in attrs:
        res = request.data.get(attr)
        if res is None:
            return response(error="{} is required".format(attr), status=status.HTTP_404_NOT_FOUND)
    return None

def response_paged(status = status.HTTP_200_OK, data = None, error = None, total_page = 1):
    return Response({
					"data": data,
					"total_page": total_page,
					"error": error,
				}, status=status)

def get_paged_obj(objs, page):
    objs = objs.order_by('id')
    paginator = Paginator(objs, 10)
    objs = paginator.get_page(page)
    return objs, paginator.num_pages


def check_notexist_and_create_user_cumulative_gpa(user):
    user_cumulative_gpa = UserCumulativeGPA.objects.get(user = user)
    if not user_cumulative_gpa :
        user_cumulative_gpa = UserCumulativeGPA.objects.create(user = user)
        user_cumulative_gpa.save()
    return user_cumulative_gpa

def validate_body_minimum(request, attrs):
    # At least one element in attrs must be present in request.data
    for attr in attrs:
        res = request.data.get(attr)
        if res is not None:
            return None
    return response(error="None of the following attributes are present in the request data: {}.".format(attrs), status=status.HTTP_404_NOT_FOUND)

def add_semester_gpa(user_cumulative_gpa, total_sks, semester_gpa):
    user_cumulative_gpa.total_sks += total_sks
    user_cumulative_gpa.total_gpa += semester_gpa * total_sks
    user_cumulative_gpa.cumulative_gpa = user_cumulative_gpa.total_gpa / user_cumulative_gpa.total_sks
    user_cumulative_gpa.save()

def delete_semester_gpa(user_cumulative_gpa, total_sks, semester_gpa):
    user_cumulative_gpa.total_sks -= total_sks
    user_cumulative_gpa.total_gpa -= semester_gpa * total_sks

    if user_cumulative_gpa.total_sks == 0:
        user_cumulative_gpa.cumulative_gpa = 0
    else:
        user_cumulative_gpa.cumulative_gpa = user_cumulative_gpa.total_gpa / user_cumulative_gpa.total_sks
    
    user_cumulative_gpa.save()