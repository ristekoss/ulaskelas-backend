import logging

from django.shortcuts import get_object_or_404
from rest_framework.decorators import api_view
from rest_framework import status
from .serializers import CourseSemesterSerializer, UserCumulativeGPASerializer, UserGPASerializer, CourseSerializer, CourseForSemesterSerializer

from .utils import response, validate_body, check_notexist_and_create_user_cumulative_gpa, validate_body_minimum, add_semester_gpa, delete_semester_gpa, update_semester_gpa, update_cumulative_gpa
from .models import Profile, UserGPA, UserCumulativeGPA, Course, CourseSemester
from django.db.models import F
from .content_course import COURSE_IK, COURSE_SI

logger = logging.getLogger(__name__)


@api_view(['GET', 'DELETE'])
def gpa_calculator(request):

	user = Profile.objects.get(username=str(request.user))
	user_cumulative_gpa = check_notexist_and_create_user_cumulative_gpa(user)

	if request.method == 'GET':
		user_gpas = UserGPA.objects.filter(userCumulativeGPA = user_cumulative_gpa)
		courses = COURSE_IK if ("Ilmu Komputer" in str(user.study_program)) else COURSE_SI
		return response(data={
												'all_semester_gpa':UserGPASerializer(user_gpas, many=True).data, 
												'cumulative_gpa': UserCumulativeGPASerializer(user_cumulative_gpa).data,
												'courses': courses
										})
	
	if request.method == 'DELETE':
		UserGPA.objects.filter(user=user).delete()
		user_cumulative_gpa.total_gpa = 0
		user_cumulative_gpa.total_sks = 0
		update_cumulative_gpa(user_cumulative_gpa)
		return response(status=status.HTTP_204_NO_CONTENT)

	
@api_view(['GET', 'DELETE', 'PUT', 'POST'])
def gpa_calculator_with_semester(request, given_semester):
	user = Profile.objects.get(username=str(request.user))
	user_cumulative_gpa = check_notexist_and_create_user_cumulative_gpa(user)
	user_gpa = UserGPA.objects.filter(userCumulativeGPA = user_cumulative_gpa, \
																			given_semester = given_semester).first()

	if request.method == 'GET':
		if user_gpa is None :
			return response(error="There is no object with given_semester={}".format(given_semester), status=status.HTTP_404_NOT_FOUND)

		return response(data=UserGPASerializer(user_gpa).data, status=status.HTTP_200_OK)
	
	if request.method == 'DELETE':
		if user_gpa is None :
			return response(error="There is no object with given_semester={}".format(given_semester), status=status.HTTP_404_NOT_FOUND)
		
		delete_semester_gpa(user_cumulative_gpa, total_sks=user_gpa.total_sks,semester_gpa=user_gpa.semester_gpa)
		user_gpa.delete()

		return response(status=status.HTTP_204_NO_CONTENT)

	if request.method == 'PUT':
		is_valid = validate_body_minimum(request, ['total_sks', 'semester_gpa'])

		if is_valid != None:
			return is_valid
		
		if user_gpa is None:
			return response(error="There is no object with given_semester={}.".format(given_semester), status=status.HTTP_404_NOT_FOUND)
		
		total_sks = request.data.get('total_sks') or user_gpa.total_sks
		semester_gpa = request.data.get('semester_gpa') or user_gpa.semester_gpa

		#Updates Cumulative GPA / Indeks Prestasi Kumulatif
		update_semester_gpa(user_cumulative_gpa=user_cumulative_gpa, \
													old_sks=user_gpa.total_sks, \
													old_gpa=user_gpa.semester_gpa, \
													new_sks=total_sks, \
													new_gpa=semester_gpa)
		
		user_gpa.total_sks = total_sks
		user_gpa.semester_gpa = semester_gpa
		user_gpa.save()

		return response(data=UserGPASerializer(user_gpa).data, status=status.HTTP_200_OK)
	
	if request.method == 'POST':
		is_valid = validate_body(request, ['semester_gpa', 'total_sks'])

		if is_valid != None :
			return is_valid
		
		try:
			semester_gpa = request.data.get('semester_gpa')
			total_sks = request.data.get('total_sks')

			user_gpa = UserGPA.objects.create(userCumulativeGPA=user_cumulative_gpa, \
												given_semester=given_semester, \
												total_sks=total_sks, \
												semester_gpa=semester_gpa)
			
			add_semester_gpa(user_cumulative_gpa, 
												total_sks=total_sks, 
												semester_gpa=semester_gpa)

			return response(data=UserGPASerializer(user_gpa).data, status=status.HTTP_201_CREATED)
		except Exception as e:
			return response(error=str(e), status=status.HTTP_400_BAD_REQUEST)

@api_view(['GET', 'POST'])
def course(request):
	user = Profile.objects.get(username=str(request.user))

	if request.method == 'GET':
		all_course = Course.objects.all()
		return response(data=CourseForSemesterSerializer(all_course, many=True).data)

	if request.method == 'POST':
		is_valid = validate_body(request, ['name', 'sks', 'description'])
		if is_valid != None:
			return is_valid
		
		code = request.data.get('code') or "CSCEXXXXXX"
		name = request.data.get('name')
		sks = request.data.get('sks')
		description = request.data.get('description')
		term = request.data.get('term') or 1

		course = Course.objects.create(
			code=code,
			name=name,
			sks=sks,
			description=description,
			term=term
		)

		return response(data=CourseForSemesterSerializer(course).data, status=status.HTTP_201_CREATED)

@api_view(['GET', 'DELETE', 'POST'])
def course_semester(request):
	user = Profile.objects.get(username=str(request.user))
	user_cumulative_gpa = check_notexist_and_create_user_cumulative_gpa(user)

	if request.method == 'GET':
		given_semester = request.data.get('given_semester')

		if given_semester is None :
			course_semesters = CourseSemester.objects.filter(semester__userCumulativeGPA__user=user)
		else :
			course_semesters = CourseSemester.objects.filter(semester__userCumulativeGPA__user=user, semester__given_semester=given_semester)
		return response(data=CourseSemesterSerializer(course_semesters, many=True).data, status=status.HTTP_200_OK)

	if request.method == 'DELETE':
		given_semester = request.data.get('given_semester')

		if given_semester is None :
			CourseSemester.objects.filter(semester__userCumulativeGPA__user=user).delete()
		else :
			CourseSemester.objects.filter(semester__userCumulativeGPA__user=user, semester__given_semester=given_semester).delete()
		return response(status=status.HTTP_200_OK)
	
	if request.method == 'POST':
		is_valid = validate_body(request, ['course_id', 'given_semester'])
		if is_valid != None:
			return is_valid
		
		course_id = request.data.get('course_id')
		given_semester = request.data.get('given_semester')

		semester = UserGPA.objects.filter(userCumulativeGPA=user_cumulative_gpa, given_semester=given_semester).first()
		if semester is None:
			return response(error="No such semester with given_semester={}".format(given_semester), status=status.HTTP_404_NOT_FOUND)
		
		course = Course.objects.filter(pk=course_id).first()

		if course is None:
			return response(error="No such course with course_id={}".format(course_id), status=status.HTTP_404_NOT_FOUND)

		course_semester = CourseSemester.objects.create(course=course, semester=semester)

		return response(data=CourseSemesterSerializer(course_semester).data, status=status.HTTP_201_CREATED)

@api_view(['DELETE'])
def course_semester_with_course_id(request, course_id):
	user = Profile.objects.get(username=str(request.user))
	user_cumulative_gpa = check_notexist_and_create_user_cumulative_gpa(user)

	if request.method == 'DELETE':
		print("HALOOOO")
		given_semester = request.data.get('given_semester')

		if given_semester != None :
			semester = UserGPA.objects.filter(userCumulativeGPA=user_cumulative_gpa, given_semester=given_semester).first()

			if semester is None:
				return response(error="No such semester with given_semester={}".format(given_semester), status=status.HTTP_404_NOT_FOUND)
			
			CourseSemester.objects.filter(course__pk=course_id, semester=semester).delete()
			return response(status=status.HTTP_204_NO_CONTENT)
		
		CourseSemester.objects.filter(course__pk=course_id).delete()
		return response(status=status.HTTP_204_NO_CONTENT)