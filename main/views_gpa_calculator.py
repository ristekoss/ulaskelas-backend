import logging

from rest_framework.decorators import api_view
from rest_framework import status
from .serializers import UserCumulativeGPASerializer, UserGPASerializer

from .utils import response, validate_body, check_notexist_and_create_user_cumulative_gpa, validate_body_minimum, add_semester_gpa, delete_semester_gpa
from .models import Profile, UserGPA, UserCumulativeGPA
from django.db.models import F

logger = logging.getLogger(__name__)


@api_view(['GET', 'POST', 'DELETE', 'PUT'])
def gpa_calculator(request):

	user = Profile.objects.get(username=str(request.user))

	if request.method == 'GET':
		user_cumulative_gpa = check_notexist_and_create_user_cumulative_gpa(user)

		user_gpas = UserGPA.objects.filter(userCumulativeGPA = user_cumulative_gpa)
		return response(data={'all_semester_gpa':UserGPASerializer(user_gpas, many=True).data, 'cumulative_gpa': UserCumulativeGPASerializer(user_cumulative_gpa).data})
	
	if request.method == 'POST':
		is_valid = validate_body(request, ['semester_gpa', 'total_sks'])

		if is_valid != None :
			return is_valid
		
		semester_gpa = request.data.get('semester_gpa')
		total_sks = request.data.get('total_sks')

		user_cumulative_gpa = check_notexist_and_create_user_cumulative_gpa(user)

		user_gpa = UserGPA.objects.create(userCumulativeGPA=user_cumulative_gpa, \
											total_sks=total_sks, \
											semester_gpa=semester_gpa)
		
		add_semester_gpa(user_cumulative_gpa, 
											total_sks=total_sks, 
											semester_gpa=semester_gpa)

		return response(data=UserGPASerializer(user_gpa).data, status=status.HTTP_201_CREATED)
	
	if request.method == 'DELETE':
		user_cumulative_gpa = check_notexist_and_create_user_cumulative_gpa(user)

		user_gpa = UserGPA.objects.filter(userCumulativeGPA=user_cumulative_gpa).order_by('given_semester').last()

		if user_gpa is None:
			return response(error="There is no gpa to delete.", status=status.HTTP_404_NOT_FOUND)

		delete_semester_gpa(user_cumulative_gpa,
												total_sks=user_gpa.total_sks,
												semester_gpa=user_gpa.semester_gpa)

		user_gpa.delete()

		return response(status=status.HTTP_200_OK)
	
	if request.method == 'PUT':
		is_valid = validate_body(request, ['given_semester'])
		if is_valid != None:
			return is_valid
		
		is_valid = validate_body_minimum(request, ['total_sks', 'semester_gpa'])
		if is_valid != None:
			return is_valid
		
		given_semester = request.data.get('given_semester')

		user_cumulative_gpa = check_notexist_and_create_user_cumulative_gpa(user)
		user_gpa = UserGPA.objects.filter(userCumulativeGPA=user_cumulative_gpa,
																		given_semester=given_semester).first()
		
		if user_gpa is None:
			return response(error="There is no object with given_semester={}.".format(given_semester), status=status.HTTP_404_NOT_FOUND)

		total_sks = request.data.get('total_sks') or user_gpa.total_sks
		semester_gpa = request.data.get('semester_gpa') or user_gpa.semester_gpa

		#Updates Cumulative GPA / Indeks Prestasi Kumulatif
		delete_semester_gpa(user_cumulative_gpa,
												total_sks=user_gpa.total_sks,
												semester_gpa=user_gpa.semester_gpa)
		add_semester_gpa(user_cumulative_gpa,
												total_sks=total_sks,
												semester_gpa=semester_gpa)
		
		user_gpa.total_sks = total_sks
		user_gpa.semester_gpa = semester_gpa
		user_gpa.save()

		return response(data=UserGPASerializer(user_gpa).data, status=status.HTTP_200_OK)