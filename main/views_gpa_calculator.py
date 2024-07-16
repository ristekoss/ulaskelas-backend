import logging

from rest_framework.decorators import api_view
from rest_framework import status
from .serializers import UserCumulativeGPASerializer, UserGPASerializer, CourseForSemesterSerializer, SemesterWithCourseSerializer

from .utils import response, validate_body, check_notexist_and_create_user_cumulative_gpa, validate_body_minimum, add_semester_gpa, delete_semester_gpa, update_semester_gpa, update_cumulative_gpa, get_fasilkom_courses
from .models import Profile, UserGPA, Course, CourseSemester
from django.db.models import F

logger = logging.getLogger(__name__)


@api_view(['GET', 'DELETE', 'POST'])
def gpa_calculator(request):

	user = Profile.objects.get(username=str(request.user))
	user_cumulative_gpa = check_notexist_and_create_user_cumulative_gpa(user)

	if request.method == 'GET':
		user_gpas = UserGPA.objects.filter(userCumulativeGPA = user_cumulative_gpa)

		courses = get_fasilkom_courses(str(user.study_program))
		fasilkom_courses = []
		for course_term in courses:
			fasilkom_courses.append(CourseForSemesterSerializer(course_term, many=True).data)

		return response(data={
												'all_semester_gpa':UserGPASerializer(user_gpas, many=True).data, 
												'cumulative_gpa': UserCumulativeGPASerializer(user_cumulative_gpa).data,
												'courses': fasilkom_courses
										})
	
	if request.method == 'DELETE':
		UserGPA.objects.filter(userCumulativeGPA__user=user).delete()
		user_cumulative_gpa.total_gpa = 0
		user_cumulative_gpa.total_sks = 0
		update_cumulative_gpa(user_cumulative_gpa)
		return response(status=status.HTTP_204_NO_CONTENT)
	
	if request.method == 'POST':
		is_valid = validate_body(request, ['given_semesters'])
		if is_valid != None:
			return is_valid
		
		given_semesters = []
		try:
			given_semesters = request.data.get('given_semesters', [])
			if not isinstance(given_semesters, list) or not given_semesters:
				return response(error="given_semesters should be a non-empty list", status=status.HTTP_400_BAD_REQUEST)
		except Exception as e:
				return response(error="given_semesters should be a non-empty list", status=status.HTTP_400_BAD_REQUEST)
		
		user_gpas = []
		
		try:
			for given_semester in given_semesters:
				user_gpa = UserGPA.objects.create(userCumulativeGPA=user_cumulative_gpa, given_semester=given_semester)
				user_gpas.append(user_gpa)
		except Exception as e:
			return response(error=str(e), status=status.HTTP_400_BAD_REQUEST)
		
		return response(data=UserGPASerializer(user_gpas, many=True).data, status=status.HTTP_201_CREATED)

	
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

@api_view(['GET', 'DELETE', 'POST'])
def course_semester(request):
	user = Profile.objects.get(username=str(request.user))
	user_cumulative_gpa = check_notexist_and_create_user_cumulative_gpa(user)

	if request.method == 'GET':
		is_valid = validate_body(request, ['given_semester'])

		if is_valid != None :
			return is_valid
		given_semester = request.data.get('given_semester')

		user_gpa = UserGPA.objects.filter(userCumulativeGPA=user_cumulative_gpa, given_semester=given_semester).first()
		if user_gpa is None:
			return response(error="There is no user_gpa with given_semester={}".format(given_semester), status=status.HTTP_404_NOT_FOUND)

		return response(data=SemesterWithCourseSerializer(user_gpa).data)

	if request.method == 'DELETE':
		given_semester = request.data.get('given_semester')

		if given_semester is None :
			CourseSemester.objects.filter(semester__userCumulativeGPA__user=user).delete()
		else :
			CourseSemester.objects.filter(semester__userCumulativeGPA__user=user, semester__given_semester=given_semester).delete()
		return response(status=status.HTTP_200_OK)
	
	if request.method == 'POST':
		is_valid = validate_body(request, ['course_ids', 'given_semester'])
		if is_valid != None:
			return is_valid
		
		course_id, given_semester = [], 0
		try:
			course_ids = request.data.get('course_ids', [])
			given_semester = request.data.get('given_semester')
			if not isinstance(course_ids, list) or not course_ids:
				return response(error="course_ids should be a non-empty list", status=status.HTTP_400_BAD_REQUEST)
		except Exception as e:
				return response(error="course_ids should be a non-empty list", status=status.HTTP_400_BAD_REQUEST)

		semester = UserGPA.objects.filter(userCumulativeGPA=user_cumulative_gpa, given_semester=given_semester).first()
		if semester is None:
			return response(error="No such semester with given_semester={}".format(given_semester), status=status.HTTP_404_NOT_FOUND)
		
		try:
			for course_id in course_ids:
				course = Course.objects.filter(pk=course_id).first()

				if course is None:
					return response(error="No such course with course_id={}".format(course_id), status=status.HTTP_404_NOT_FOUND)

				course_semester = CourseSemester.objects.create(course=course, semester=semester)
		except Exception as e:
			return response(error=str(e), status=status.HTTP_400_BAD_REQUEST)

		return response(data=SemesterWithCourseSerializer(semester).data, status=status.HTTP_201_CREATED)

@api_view(['DELETE'])
def course_semester_with_course_id(request, course_id):
	user = Profile.objects.get(username=str(request.user))
	user_cumulative_gpa = check_notexist_and_create_user_cumulative_gpa(user)

	if request.method == 'DELETE':
		given_semester = request.data.get('given_semester')

		if given_semester != None :
			semester = UserGPA.objects.filter(userCumulativeGPA=user_cumulative_gpa, given_semester=given_semester).first()

			if semester is None:
				return response(error="No such semester with given_semester={}".format(given_semester), status=status.HTTP_404_NOT_FOUND)
			
			CourseSemester.objects.filter(course__pk=course_id, semester=semester).delete()
			return response(status=status.HTTP_204_NO_CONTENT)
		
		CourseSemester.objects.filter(course__pk=course_id).delete()
		return response(status=status.HTTP_204_NO_CONTENT)