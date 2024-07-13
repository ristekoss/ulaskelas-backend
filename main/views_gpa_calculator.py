import logging

from rest_framework.decorators import api_view
from rest_framework import status
from .serializers import UserCumulativeGPASerializer, UserGPASerializer

from .utils import response, validate_body, check_notexist_and_create_user_cumulative_gpa, validate_body_minimum, add_semester_gpa, delete_semester_gpa, update_semester_gpa, update_cumulative_gpa
from .models import Profile, UserGPA, UserCumulativeGPA
from django.db.models import F

logger = logging.getLogger(__name__)


@api_view(['GET', 'DELETE'])
def gpa_calculator(request):

	user = Profile.objects.get(username=str(request.user))
	user_cumulative_gpa = check_notexist_and_create_user_cumulative_gpa(user)

	if request.method == 'GET':
		user_gpas = UserGPA.objects.filter(userCumulativeGPA = user_cumulative_gpa)
		return response(data={
												'all_semester_gpa':UserGPASerializer(user_gpas, many=True).data, 
												'cumulative_gpa': UserCumulativeGPASerializer(user_cumulative_gpa).data
										})
	
	if request.method == 'DELETE':
		UserGPA.objects.all().delete()
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