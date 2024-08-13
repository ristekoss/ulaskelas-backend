from datetime import datetime
import logging
import math
import uuid

from django.urls import reverse
import requests
from rest_framework.decorators import api_view
from rest_framework import status

from main.views_calculator import score_component
from .serializers import AddQuestionSerializer, CalculatorSerializer, QuestionSerializer, ScoreComponentSerializer, TanyaTemanProfileSerializer, UserCumulativeGPASerializer, UserGPASerializer, CourseForSemesterSerializer, SemesterWithCourseSerializer, HideVerificationQuestionSerializer

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
    
    is_history = request.query_params.get('is_history') != None
    questions = filtered_question(request)
    return tanya_teman_paged(request, questions, is_history)
  
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
  
  if request.method == "DELETE":
    if question.user.pk != user.pk :
      return response(error="You are not allowed to delete other person's question", status=status.HTTP_403_FORBIDDEN)
    question.delete()
    return response(status=status.HTTP_204_NO_CONTENT)
  
def tanya_teman_paged(request, questions, is_history):
  page = request.query_params.get('page')
  if page is None:
    return response(error='page is required', status=status.HTTP_400_BAD_REQUEST)
  
  questions, total_page = get_paged_questions(questions, page)
  return response_paged(data={
    'questions': QuestionSerializer(questions, many=True).data 
                  if is_history else 
                    HideVerificationQuestionSerializer(questions, many=True).data
  }, total_page=total_page)


def filtered_question(request):
  is_paling_banyak_disukai = request.query_params.get('paling_banyak_disukai') != None
  is_terverifikasi = request.query_params.get('terverifikasi') != None
  is_menunggu_verifikasi = request.query_params.get('menunggu_verifikasi') != None
  is_history = request.query_params.get('is_history') != None
  user = Profile.objects.get(username=str(request.user))

  # Note: The filter should be changed to Question.VerificationStatus.APPROVED (previously WAITING, see line 120)
  #       after implementing the verification flow
  questions = Question.objects.all()
  if is_history:
      questions = questions.filter(user=user)
  else :
      questions = questions.filter(verification_status=Question.VerificationStatus.WAITING)
  
  if is_paling_banyak_disukai:
      return questions.order_by('like_count')
  if is_terverifikasi:
      return questions.filter(verification_status=Question.VerificationStatus.APPROVED).order_by('created_at')
  if is_menunggu_verifikasi:
      return questions.filter(verification_status=Question.VerificationStatus.WAITING).order_by('created_at')
  return questions.order_by('created_at')