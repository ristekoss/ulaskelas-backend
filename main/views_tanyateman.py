from datetime import datetime
import logging
import math
import uuid

from django.urls import reverse
import requests
from rest_framework.decorators import api_view
from rest_framework import status

from main.views_calculator import score_component
from .serializers import AddQuestionSerializer, CalculatorSerializer, QuestionSerializer, ScoreComponentSerializer, TanyaTemanProfileSerializer, UserCumulativeGPASerializer, UserGPASerializer, CourseForSemesterSerializer, SemesterWithCourseSerializer

from .utils import get_recommended_score, get_score, response, response_paged, update_course_score, validate_body, check_notexist_and_create_user_cumulative_gpa, validate_body_minimum, add_semester_gpa, delete_semester_gpa, update_semester_gpa, update_cumulative_gpa, get_fasilkom_courses, add_course_to_semester, validate_params, delete_course_to_semester, get_paged_questions
from .models import Calculator, Course, Profile, Question
from django.db.models import F
import boto3
import environ

logger = logging.getLogger(__name__)
env = environ.Env()

@api_view(['GET', 'PUT', 'POST','DELETE'])
def tanya_teman(request):
  user = Profile.objects.get(username=str(request.user))

  if request.method == 'POST':
    serializer = AddQuestionSerializer(data=request.data)
    if serializer.is_valid():
      attachment_file = serializer.validated_data['attachment_file']
      question_text = serializer.validated_data['question_text']
      course_id = serializer.validated_data['course_id']
      is_anonym = serializer.validated_data['is_anonym']

      course = Course.objects.filter(pk=course_id).first()
      if course is None:
        return response(error="No such Course", status=status.HTTP_404_NOT_FOUND)
      
      if is_anonym > 1:
        return response(error="is_anonym should be between 0 and 1", status=status.HTTP_400_BAD_REQUEST)

      s3 = boto3.client('s3', aws_access_key_id=env("ACCESS_KEY_ID"),
                        aws_secret_access_key=env("ACCESS_KEY_SECRET"),
                        region_name=env("AWS_REGION"))

      bucket_name = env("BUCKET_NAME")
      folder_prefix = env("AWS_S3_FOLDER_PREFIX")
      timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
      extension = attachment_file.name.split('.')[-1]

      if not extension:
        return response(error="File extension not found.", status=status.HTTP_400_BAD_REQUEST)
      
      if not folder_prefix:
        return response(error="Folder prefix not found.", status=status.HTTP_400_BAD_REQUEST)

      key = f"{folder_prefix}/{uuid.uuid4()}_{timestamp}.{extension}"
      try:
        s3.upload_fileobj(attachment_file, bucket_name, key)
        question = Question.objects.create(user=user, question_text=question_text, course=course, is_anonym=is_anonym, attachment=key)
        return response(data={"message": "Image uploaded successfully", "key": key}, status=status.HTTP_200_OK)
      except Exception as e:
        return response(error=str(e), status=status.HTTP_400_BAD_REQUEST)
    else:
      return response(error=serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
  if request.method == 'GET':
    id = request.query_params.get('id')
    if id != None:
      return tanya_teman_with_id(request, id)

    # Note: Need to change filter to be Question.VerificationStatus.APPROVED 
    #       after implementing the flow to verify the status
    questions = Question.objects.filter(verification_status=Question.VerificationStatus.WAITING).order_by('created_at')
    page = request.query_params.get('page')
    if page is None:
      return response(error='page is required', status=status.HTTP_400_BAD_REQUEST)
    questions, total_page = get_paged_questions(questions, page)
    return response_paged(data={'questions': QuestionSerializer(questions, many=True).data}, total_page=total_page)
  
def tanya_teman_with_id(request, id):
  user = Profile.objects.get(username=str(request.user))
  question = Question.objects.filter(pk=id).first()
  if question is None:
    return response(error="No matching question", status=status.HTTP_404_NOT_FOUND)
  
  if request.method == "GET":
    return response(data={
      "question": QuestionSerializer(question).data,
      "current_user": TanyaTemanProfileSerializer(user).data
    }, status=status.HTTP_200_OK)