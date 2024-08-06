from datetime import datetime
import math
import os
from django.contrib.auth.models import User
from django.core.paginator import Paginator
from rest_framework.authtoken.models import Token
from rest_framework.response import Response
from rest_framework import status

from .models import Calculator, Course, Profile, ScoreComponent, UserCumulativeGPA, UserGPA, ScoreSubcomponent
from .fasilkom_courses import IK_COURSES, SI_COURSES


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
    user_cumulative_gpa = UserCumulativeGPA.objects.filter(user = user).first()
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

def add_course_to_semester(semester: UserGPA, sks: int, score: float=0.0):
    semester.total_sks += sks
    semester.semester_mutu += sks * score
    update_gpa(semester)

def delete_course_to_semester(semester: UserGPA, sks: int, score: float):
    semester.total_sks -= sks
    semester.semester_mutu -= sks * score
    update_gpa(semester)

def update_gpa(semester: UserGPA):
    if semester.total_sks == 0:
        semester.semester_gpa = 0
    else:
        semester.semester_gpa = semester.semester_mutu / semester.total_sks
    semester.save()

def update_course_score(user_cumulative_gpa: UserCumulativeGPA, 
                        semester: UserGPA, 
                        prev_sks: int, prev_score: float, cur_sks: int, cur_score: float):
    old_semester_sks, old_semester_gpa = semester.total_sks, semester.semester_gpa
    delete_course_to_semester(semester, prev_sks, prev_score)
    add_course_to_semester(semester, cur_sks, cur_score)
    new_semester_sks, new_semester_gpa = semester.total_sks, semester.semester_gpa

    update_semester_gpa(user_cumulative_gpa=user_cumulative_gpa,
                        old_gpa=old_semester_gpa,
                        old_sks=old_semester_sks,
                        new_gpa=new_semester_gpa,
                        new_sks=new_semester_sks)

def add_semester_gpa(user_cumulative_gpa: UserCumulativeGPA, total_sks: int, semester_gpa: float):
    user_cumulative_gpa.total_sks += total_sks
    user_cumulative_gpa.total_gpa += semester_gpa * total_sks
    update_cumulative_gpa(user_cumulative_gpa)

def delete_semester_gpa(user_cumulative_gpa: UserCumulativeGPA, total_sks: int, semester_gpa: float):
    user_cumulative_gpa.total_sks -= total_sks
    user_cumulative_gpa.total_gpa -= semester_gpa * total_sks
    update_cumulative_gpa(user_cumulative_gpa)

def update_cumulative_gpa(user_cumulative_gpa: UserCumulativeGPA):
    if user_cumulative_gpa.total_sks == 0:
        user_cumulative_gpa.cumulative_gpa = 0
    else:
        user_cumulative_gpa.cumulative_gpa = user_cumulative_gpa.total_gpa / user_cumulative_gpa.total_sks

    user_cumulative_gpa.save()

def update_semester_gpa(user_cumulative_gpa: UserCumulativeGPA, 
                        old_sks: int, old_gpa: float, new_sks: int, new_gpa: float):
    delete_semester_gpa(user_cumulative_gpa, old_sks, old_gpa)
    add_semester_gpa(user_cumulative_gpa, new_sks, new_gpa)

def get_course_by_code(course_code):
    return Course.objects.filter(code=course_code).first()

def get_fasilkom_courses(study_program):
    courses_by_program = IK_COURSES if "Ilmu Komputer" in study_program else SI_COURSES
    study_program_courses = [[]]
    for term in range(1,9):
        courses_in_term = courses_by_program[term]
        term_course = []
        for course_code in courses_in_term:
            course = get_course_by_code(course_code)
            if course != None:
                term_course.append(course)
        
        study_program_courses.append(term_course)
    return study_program_courses

def get_score(score: float) -> float :
    if score < 40:
        return 0    # E
    if score < 55:
        return 1.0  # D
    if score < 60:
        return 2.0  # C
    if score < 65:
        return 2.3  # C+
    if score < 70:
        return 2.7  # B-
    if score < 75:
        return 3.0  # B
    if score < 80:
        return 3.3  # B+
    if score < 85:
        return 3.7  # A-
    
    return 4.0      # A

def get_null_sum_from_component(score_component: ScoreComponent) -> float :
    frequency = ScoreSubcomponent.objects.filter(score_component=score_component).count()
    null_sum = 0.0
    score_subcomponents = ScoreSubcomponent.objects.filter(score_component=score_component)
    for score_subcomponent in score_subcomponents:
        null_contribution = 0 if score_subcomponent.subcomponent_score != None else score_component.weight / frequency
        null_sum += null_contribution
    return null_sum

def get_null_sum_from_calculator(calculator: Calculator) -> float :
    null_sum = 0.0
    score_components = ScoreComponent.objects.filter(calculator=calculator)
    for score_component in score_components:
        null_sum += get_null_sum_from_component(score_component)
    return null_sum

def get_recommended_score(calculator: Calculator, target_score: int) -> float :
    current_score = calculator.total_score
    score_left = max(target_score - current_score, 0)
    percentage_left = get_null_sum_from_calculator(calculator)

    if percentage_left == 0:
        return 0
    
    return score_left / percentage_left * 100