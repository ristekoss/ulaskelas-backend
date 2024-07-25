import logging

from django.urls import reverse
import requests
from rest_framework.decorators import api_view
from rest_framework import status

from main.views_calculator import score_component
from .serializers import CalculatorSerializer, ScoreComponentSerializer, UserCumulativeGPASerializer, UserGPASerializer, CourseForSemesterSerializer, SemesterWithCourseSerializer

from .utils import get_score, response, update_course_score, validate_body, check_notexist_and_create_user_cumulative_gpa, validate_body_minimum, add_semester_gpa, delete_semester_gpa, update_semester_gpa, update_cumulative_gpa, get_fasilkom_courses, add_course_to_semester, validate_params, delete_course_to_semester
from .models import Calculator, Profile, ScoreComponent, UserCumulativeGPA, UserGPA, Course, CourseSemester
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
		
		is_auto_fill = request.query_params.get('is_auto_fill')
		courses = get_fasilkom_courses(str(user.study_program))
		
		given_semesters = []
		try:
			given_semesters = request.data.get('given_semesters', [])
			if not isinstance(given_semesters, list) or not given_semesters:
				return response(error="given_semesters should be a non-empty list", status=status.HTTP_400_BAD_REQUEST)
		except Exception as e:
				return response(error="given_semesters should be a non-empty list", status=status.HTTP_400_BAD_REQUEST)
		
		given_semesters = list(set(given_semesters)) #remove duplicate given_semester

		'''
		When handling a semester (given_semester), theres 2 possible error:
		1. The length (string) of given_semester exceeds 20 characters
			Solution: insert/append it to character_limit_exceeded_semester
		2. There is already a semesester with given_semester=given_semester
			Solution: insert/append it to duplicated_semester
		
		if a given_semester passed this 2 checks, it means that we are ready to create a new object UserGPA with given_semester.
		'''
		character_limit_exceeded_semester = []
		duplicated_semester = []
		valid_semester = []
		for given_semester in given_semesters:
			if len(given_semester) > 20:
				character_limit_exceeded_semester.append(given_semester)
				continue

			semester = UserGPA.objects.filter(userCumulativeGPA=user_cumulative_gpa, given_semester=given_semester).first()
			if semester != None:
				duplicated_semester.append(given_semester)
				continue
			
			valid_semester.append(given_semester)

		user_gpas = []
		for given_semester in valid_semester:
			semester = UserGPA.objects.create(userCumulativeGPA=user_cumulative_gpa, given_semester=given_semester)

			if is_auto_fill != None and str(given_semester).isnumeric():
				try:
					given_semester_int = int(given_semester)
					list_courses = courses[given_semester_int]
					for course in list_courses:
						calculator = Calculator.objects.create(user=user, course=course)

						# Update gpa (ip) and cumulative gpa (ipk)
						add_course_to_semester(semester=semester, sks=course.sks)
						add_semester_gpa(user_cumulative_gpa=user_cumulative_gpa,
												total_sks=course.sks,
												semester_gpa=0)
						
						course_semester = CourseSemester.objects.create(course=course, semester=semester, calculator=calculator)
				except Exception as e:
					return response(error=str(e), status=status.HTTP_500_INTERNAL_SERVER_ERROR)
			
			semester = UserGPA.objects.filter(userCumulativeGPA=user_cumulative_gpa, given_semester=given_semester).first()
			user_gpas.append(semester)
		
		return response(data=UserGPASerializer(user_gpas, many=True).data, status=status.HTTP_201_CREATED)

	
@api_view(['GET', 'DELETE'])
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
	
	if request.method == 'POST':
		is_valid = validate_body(request, ['course_ids', 'given_semester'])
		if is_valid != None:
			return is_valid
		
		course_ids, given_semester = [], 0
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
		
		'''
		When handling a course_id, there are 2 possible error:
		1.There is no course with id=course_id
			Solution: insert/append it to nonexsistent_course_ids
		2. There exists course_semester with course.id=course_id and semester=semester. However, (course,semester) should be unique for all course_semester
			Solution: insert/append it to duplicated_course_semester_ids
		
		if a course_id passed this 2 checks, it means that we are ready to create a new object course_semester with course_id.
		'''
		duplicated_course_semester_ids = []
		nonexsistent_course_ids = []
		valid_course_ids = []
		for course_id in course_ids :
			course = Course.objects.filter(pk=course_id).first()
			if course is None:
				nonexsistent_course_ids.append(course_id)
				continue

			course_semester = CourseSemester.objects.filter(course=course, semester=semester).first()
			if course_semester != None:
				duplicated_course_semester_ids.append(course_id)
				continue

			valid_course_ids.append(course_id)
		
		print(valid_course_ids)
		
		for course_id in valid_course_ids:
			course = Course.objects.filter(pk=course_id).first()
			
			calculator = Calculator.objects.create(user=user, course=course)

			# Update gpa (ip) and cumulative gpa (ipk)
			add_course_to_semester(semester=semester, sks=course.sks)
			add_semester_gpa(user_cumulative_gpa=user_cumulative_gpa,
									total_sks=course.sks,
									semester_gpa=0)

			course_semester = CourseSemester.objects.create(course=course, semester=semester, calculator=calculator)

		return response(data={'updated_course':SemesterWithCourseSerializer(semester).data,
													'duplicated_course_semester_ids': duplicated_course_semester_ids,
													'nonexistent_course_ids': nonexsistent_course_ids,
													'inserted_course_ids': valid_course_ids
												}, status=status.HTTP_201_CREATED)

@api_view(['DELETE'])
def course_semester_with_course_id(request, course_id):
	user = Profile.objects.get(username=str(request.user))
	user_cumulative_gpa = check_notexist_and_create_user_cumulative_gpa(user)

	if request.method == 'DELETE':
		is_valid = validate_body(request, ['given_semester'])
		if is_valid != None:
			return is_valid
		given_semester = request.data.get('given_semester')

		semester = UserGPA.objects.filter(userCumulativeGPA=user_cumulative_gpa, given_semester=given_semester).first()
		if semester is None:
			return response(error="No such semester with given_semester={}".format(given_semester), status=status.HTTP_404_NOT_FOUND)
		
		course_semester = CourseSemester.objects.filter(course__pk=course_id, calculator__user=user, semester__given_semester=given_semester).first()
		if course_semester is None:
			return response(error="No matching course semester", status=status.HTTP_404_NOT_FOUND)
		
		# Update gpa (ip) and cumulative gpa (ipk)
		delete_course_to_semester(semester=semester, sks=course_semester.course.sks, score=get_score(course_semester.calculator.total_score))
		delete_semester_gpa(user_cumulative_gpa=user_cumulative_gpa,
								total_sks=course_semester.course.sks,
								semester_gpa=0)
		
		course_semester.delete()
		return response(status=status.HTTP_204_NO_CONTENT)
	
@api_view(['GET', 'POST', 'DELETE', 'PUT'])
def course_component(request):
	user = Profile.objects.get(username=str(request.user))
	user_cumulative_gpa = check_notexist_and_create_user_cumulative_gpa(user)

	if request.method == 'GET':
		is_valid = validate_params(request, ['calculator_id'])

		if is_valid != None:
			is_valid

		calculator_id = request.query_params.get('calculator_id')
		calculator = Calculator.objects.filter(id=calculator_id).first()

		if calculator is None:
			return response(error="Calculator not found", status=status.HTTP_404_NOT_FOUND)

		score_components = ScoreComponent.objects.filter(calculator=calculator)
		return response(data={
			'score_component': ScoreComponentSerializer(score_components, many=True).data,
			'calculator': CalculatorSerializer(calculator).data
		})

	if request.method == 'POST':
		is_valid = validate_body(request, ['calculator_id', 'name', 'weight', 'score'])

		if is_valid != None:
			return is_valid
		
		calculator_id = request.data.get('calculator_id')
		name = request.data.get('name')
		weight = request.data.get('weight')
		score = request.data.get('score')

		calculator = Calculator.objects.filter(pk=calculator_id).first()
		if calculator is None:
			return response(error="There is no calculator with id={}".format(calculator_id), status=status.HTTP_404_NOT_FOUND)
		course_semester = CourseSemester.objects.filter(calculator=calculator).first()
		if course_semester is None:
			return response(error="There is no calculator with id={}".format(calculator_id), status=status.HTTP_404_NOT_FOUND)
		semester = course_semester.semester
		course = course_semester.course

		prev_sks = course.sks
		prev_score = get_score(calculator.total_score)

		score_component = ScoreComponent.objects.create(calculator=calculator, name=name, weight=weight, score=score)
		calculator.total_score += (score * weight / 100)
		calculator.total_percentage += weight
		calculator.save()
		
		update_course_score(user_cumulative_gpa=user_cumulative_gpa,
												semester=semester,
												prev_sks=prev_sks, prev_score=prev_score,
												cur_sks=course.sks, cur_score=get_score(calculator.total_score))
		
		score_component_value = ScoreComponent.objects.filter(calculator=calculator, name=name, weight=weight, score=score).first()
		return response(data=ScoreComponentSerializer(score_component_value).data, status=status.HTTP_201_CREATED)

	if request.method == 'DELETE':
		is_valid = validate_params(request, ['id'])

		if is_valid != None:
				return is_valid

		component_id = request.query_params.get('id')

		score_component = ScoreComponent.objects.filter(id=component_id).first()

		if score_component is None:
				return response(error="Score component not found", status=status.HTTP_404_NOT_FOUND)

		calculator = Calculator.objects.filter(id=score_component.calculator.id).first()
		if calculator is None:
			return response(error="There is no calculator with id={}".format(score_component.calculator.id), status=status.HTTP_404_NOT_FOUND)
		course_semester = CourseSemester.objects.filter(calculator=calculator).first()
		if course_semester is None:
			return response(error="There is no calculator with id={}".format(score_component.calculator.id), status=status.HTTP_404_NOT_FOUND)
		semester = course_semester.semester
		course = course_semester.course

		prev_sks = course.sks
		prev_score = get_score(calculator.total_score)

		calculator.total_score -= (score_component.score * score_component.weight / 100)
		calculator.total_percentage -= score_component.weight

		update_course_score(user_cumulative_gpa=user_cumulative_gpa,
										semester=semester,
										prev_sks=prev_sks, prev_score=prev_score,
										cur_sks=course.sks, cur_score=get_score(calculator.total_score))

		score_component.delete()
		calculator.save()

		return response(status=status.HTTP_200_OK)
