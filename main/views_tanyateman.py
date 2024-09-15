from datetime import datetime
import logging
import math
import uuid

from django.urls import reverse
import requests
from rest_framework.decorators import api_view
from rest_framework import status

from main.views_calculator import score_component
from .serializers import AddQuestionSerializer, CalculatorSerializer, QuestionSerializer, ScoreComponentSerializer, TanyaTemanProfileSerializer, UserCumulativeGPASerializer, UserGPASerializer, CourseForSemesterSerializer, SemesterWithCourseSerializer, HideVerificationQuestionSerializer, AnswerQuestionSerializer, AnswerSerializer
from .utils import get_recommended_score, get_score, response, response_paged, update_course_score, validate_body, check_notexist_and_create_user_cumulative_gpa, validate_body_minimum, add_semester_gpa, delete_semester_gpa, update_semester_gpa, update_cumulative_gpa, get_fasilkom_courses, add_course_to_semester, validate_params, delete_course_to_semester, get_paged_questions
from .models import Calculator, Course, LikePost, Profile, Question, Answer, get_attachment_presigned_url
from django.contrib.contenttypes.models import ContentType
from django.db.models import Q
import boto3
import environ
from django.core.mail import send_mail
from django.conf import settings

logger = logging.getLogger(__name__)
env = environ.Env()

@api_view(['GET', 'PUT', 'POST','DELETE'])
def tanya_teman(request):
  user = Profile.objects.get(username=str(request.user))

  if request.method == 'POST':
    serializer = AddQuestionSerializer(data=request.data)
    if not serializer.is_valid():
      return response(error=serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    attachment_file = serializer.validated_data.get('attachment_file', None)
    question_text = serializer.validated_data['question_text']
    course_id = serializer.validated_data['course_id']
    is_anonym = serializer.validated_data['is_anonym']

    response_attachment = upload_attachment(attachment_file)
    if response_attachment[0] == "error":
      return response_attachment[1]
    
    key = response_attachment[1]

    course = Course.objects.filter(pk=course_id).first()
    if course is None:
      return response(error="No such Course", status=status.HTTP_404_NOT_FOUND)
    
    if is_anonym > 1 or is_anonym < 0:
      return response(error="is_anonym should be between 0 and 1", status=status.HTTP_400_BAD_REQUEST)
    
    question = Question.objects.create(
      user=user, 
      question_text=question_text, 
      course=course, 
      is_anonym=is_anonym, 
      attachment=key
    )

    admin_link = env("ULASKELAS_ADMIN_LINK")
    question_link = env("ULASKELAS_QUESTION_LINK")
    send_mail(
        subject=f"New Question (ID {question.pk}) by {user.username}",
        message= \
          f"""A new question with id={question.pk} has been posted by {user.username}. 
          \n\nQuestion text: {question_text}.
          \n\nQuestion Link: {admin_link}/?next={question_link}/{question.id}/change/
          \n\nImage Link: {get_attachment_presigned_url(question.attachment)}""",
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[settings.NOTIFICATION_RECIPIENT_EMAIL],
        fail_silently=False,
    )

    return response(data={"message": "Image uploaded successfully", "key": key}, status=status.HTTP_200_OK)
    
  if request.method == 'GET':
    id = request.query_params.get('id')
    if id != None:
      return tanya_teman_with_id(request, id)
    
    is_history = request.query_params.get('is_history') != None
    questions = filtered_question(request)
    return tanya_teman_paged(request, questions, is_history)
  
  if request.method == 'DELETE':
    id = request.query_params.get('id')
    if id is None:
      return response(error="id is required", status=status.HTTP_400_BAD_REQUEST)
    if not id.isnumeric():
      return response(error="id should be a number", status=status.HTTP_400_BAD_REQUEST)
    return tanya_teman_with_id(request, id)
  
  if request.method == 'PUT':
    is_like = request.query_params.get("is_like")
    if is_like is None:
      return response(error="The only allowed PUT request for /tanya-teman is to like/unlike a Question.", status=status.HTTP_400_BAD_REQUEST)
    
    id = request.query_params.get('id')
    if id is None:
      return response(error="id is required", status=status.HTTP_400_BAD_REQUEST)
    if not id.isnumeric():
      return response(error="id should be a number", status=status.HTTP_400_BAD_REQUEST)
    
    question = Question.objects.filter(pk=id).first()
    if question is None:
      return response(error="No matching question", status=status.HTTP_404_NOT_FOUND)
    
    content_type = ContentType.objects.get_for_model(Question)
    question_like = LikePost.objects.filter(content_type=content_type, object_id=id, user=user).first()
    if question_like is None:
      LikePost.objects.create(
          user=user,
          content_type=content_type,
          object_id=id
      )
      question.like_count += 1
      question.save()
    else:
      question_like.delete()
      question.like_count -= 1
      question.save()

    return response(status=status.HTTP_200_OK)


@api_view(['GET', 'POST', 'PUT'])
def jawab_teman(request):
  user = Profile.objects.get(username=str(request.user))

  if request.method == 'POST':
    serializer = AnswerQuestionSerializer(data=request.data)
    if not serializer.is_valid():
      return response(error=serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    attachment_file = serializer.validated_data.get('attachment_file', None)
    answer_text = serializer.validated_data['answer_text']
    question_id = serializer.validated_data['question_id']
    is_anonym = serializer.validated_data['is_anonym']

    response_attachment = upload_attachment(attachment_file)
    if response_attachment[0] == "error":
      return response_attachment[1]
    
    key = response_attachment[1]

    question = Question.objects.filter(pk=question_id).first()
    if question is None:
      return response(error="No such Question", status=status.HTTP_404_NOT_FOUND)
    
    if is_anonym > 1 or is_anonym < 0:
      return response(error="is_anonym should be between 0 and 1", status=status.HTTP_400_BAD_REQUEST)
    
    answer = Answer.objects.create(
      user=user, 
      answer_text=answer_text, 
      question=question,
      is_anonym=is_anonym, 
      attachment=key
    )
    question.reply_count += 1
    question.save()

    admin_link = env("ULASKELAS_ADMIN_LINK")
    answer_link = env("ULASKELAS_ANSWER_LINK")
    send_mail(
        subject=f"New Answer (ID {answer.pk}) by {user.username}",
        message= \
          f"""A new answer with id={answer.pk} has been posted by {user.username}.
          \n\nRespective Question: {question.question_text}
          \n\nAnswer text: {answer_text}.
          \n\nAnswer Link: {admin_link}/?next={answer_link}/{answer.id}/change/
          \n\nImage Link: {get_attachment_presigned_url(answer.attachment)}""",
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[settings.NOTIFICATION_RECIPIENT_EMAIL],
        fail_silently=False,
    )

    return response(data={"message": "Image uploaded successfully", "key": key}, status=status.HTTP_200_OK)
  
  if request.method == 'GET':
    question_id = request.query_params.get('question_id')
    if question_id is None:
      return response(error="question_id is required", status=status.HTTP_400_BAD_REQUEST)
    
    question = Question.objects.filter(pk=question_id).first()
    if question is None:
      return response(error="No such Question", status=status.HTTP_404_NOT_FOUND)
    
    # returns all reply/answer from all approved or answered by the current user
    all_replies = Answer.objects.filter(
                    Q(question=question),
                    Q(verification_status=Answer.VerificationStatus.APPROVED) | Q(user=user))
    return jawab_teman_paged(request, all_replies)
  
  if request.method == 'PUT':
    is_like = request.query_params.get("is_like")
    if is_like is None:
      return response(error="The only allowed PUT request for /jawab-teman is to like/unlike an Answer.", status=status.HTTP_400_BAD_REQUEST)
    
    id = request.query_params.get('id')
    if id is None:
      return response(error="id is required", status=status.HTTP_400_BAD_REQUEST)
    if not id.isnumeric():
      return response(error="id should be a number", status=status.HTTP_400_BAD_REQUEST)
    
    answer = Answer.objects.filter(pk=id).first()
    if answer is None:
      return response(error="No matching answer", status=status.HTTP_404_NOT_FOUND)
    
    content_type = ContentType.objects.get_for_model(Answer)
    answer_like = LikePost.objects.filter(content_type=content_type, object_id=id, user=user).first()
    if answer_like is None:
      LikePost.objects.create(
          user=user,
          content_type=content_type,
          object_id=id
      )
      answer.like_count += 1
      answer.save()
    else:
      answer_like.delete()
      answer.like_count -= 1
      answer.save()

    return response(status=status.HTTP_200_OK)


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
  user = Profile.objects.get(username=str(request.user))
  if page is None:
    return response(error='page is required', status=status.HTTP_400_BAD_REQUEST)
  
  questions, total_page = get_paged_questions(questions, page)

  list_questions = None
  if is_history: 
    list_questions = QuestionSerializer(questions, many=True).data
  else:
    list_questions = HideVerificationQuestionSerializer(questions, many=True).data
  list_questions = add_is_liked(user, list_questions, is_question=True)

  return response_paged(data={
    'questions': list_questions
  }, total_page=total_page)

def jawab_teman_paged(request, answers):
  page = request.query_params.get('page')
  user = Profile.objects.get(username=str(request.user))
  question = answers[0].question if len(answers) > 0 else None
  like_count = question.like_count if question != None else 0
  reply_count = question.reply_count if question != None else 0
  if page is None:
    return response(error='page is required', status=status.HTTP_400_BAD_REQUEST)
  
  answers, total_page = get_paged_questions(answers, page)
  list_answers = AnswerSerializer(answers, many=True).data
  list_answers = add_is_liked(user, list_answers, is_question=False)
  return response_paged(data={
    'answers': list_answers,
    'like_count': like_count,
    'reply_count': len(answers)
  }, total_page=total_page)


def filtered_question(request):
  is_paling_banyak_disukai = request.query_params.get('paling_banyak_disukai') != None
  is_terverifikasi = request.query_params.get('terverifikasi') != None
  is_menunggu_verifikasi = request.query_params.get('menunggu_verifikasi') != None
  is_history = request.query_params.get('is_history') != None
  course_id = request.query_params.get('course_id')
  keyword = request.query_params.get('keyword')
  user = Profile.objects.get(username=str(request.user))

  questions = Question.objects.all()
  if is_history:
    questions = questions.filter(user=user)
  else :
    questions = questions.filter(verification_status=Question.VerificationStatus.APPROVED)

  if course_id != None:
    questions = questions.filter(course__pk=course_id)
  if keyword != None:
    questions = questions.filter(Q(question_text__icontains=keyword))

  if is_paling_banyak_disukai:
    return questions.order_by('-like_count')
  if is_terverifikasi:
    return questions.filter(verification_status=Question.VerificationStatus.APPROVED).order_by('-created_at')
  if is_menunggu_verifikasi:
    return questions.filter(verification_status=Question.VerificationStatus.WAITING).order_by('-created_at')
  return questions.order_by('-created_at')

'''
upload_attachment returns ('error', response) if the attachment file is not valid
and returns ('success', key) otherwise
'''
def upload_attachment(attachment_file):
    if attachment_file is None : 
      return "success", None

    s3 = boto3.client('s3', aws_access_key_id=env("ACCESS_KEY_ID"),
                      aws_secret_access_key=env("ACCESS_KEY_SECRET"),
                      region_name=env("AWS_REGION"))

    bucket_name = env("BUCKET_NAME")
    folder_prefix = env("AWS_S3_FOLDER_PREFIX")
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    extension = attachment_file.name.split('.')[-1]

    if not extension:
      return "error", response(error="File extension not found.", status=status.HTTP_400_BAD_REQUEST)
    
    if str(extension) not in ['jpg', 'jpeg', 'png']:
      return "error", response(error="File must be jpg, jpeg, or png.", status=status.HTTP_400_BAD_REQUEST)
    
    if not folder_prefix:
      return "error", response(error="Folder prefix not found.", status=status.HTTP_400_BAD_REQUEST)
    
    max_size_in_bytes = 5 * 1024 * 1024  # 5 MB
    if attachment_file.size > max_size_in_bytes:
        return "error", response(error="File size must be less than 5 MB.", status=status.HTTP_400_BAD_REQUEST)

    key = f"{folder_prefix}/{uuid.uuid4()}_{timestamp}.{extension}"
    try:
      s3.upload_fileobj(attachment_file, bucket_name, key)
      return "success", key
    except Exception as e:
      return "error", response(error=str(e), status=status.HTTP_400_BAD_REQUEST)
    
def add_is_liked(user, posts, is_question):
  list_posts = []
  if is_question:
    content_type = ContentType.objects.get_for_model(Question)
  else:
    content_type = ContentType.objects.get_for_model(Answer)
  for post in posts:
    post_like = LikePost.objects.filter(content_type=content_type, object_id=post['id'], user=user).first()
    post['liked_by_user'] = 1 if post_like != None else 0
    
    if is_question:
      post['reply_count'] = get_reply_count(user, post['id'])
    list_posts.append(post)
  return list_posts

def get_reply_count(user, question_id):
  return Answer.objects.filter(
                    Q(question__pk=question_id),
                    Q(verification_status=Answer.VerificationStatus.APPROVED) | Q(user=user)).count()