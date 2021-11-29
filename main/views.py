import json
from django_filters.rest_framework.backends import DjangoFilterBackend
from live_config.views import get_config
from rest_framework.decorators import api_view, permission_classes
from rest_framework import permissions, status
from rest_framework.fields import CreateOnlyDefault
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.filters import SearchFilter
from rest_framework import viewsets
from datetime import datetime
from .utils import process_sso_profile, response, validateBody, validateParams
from sso.decorators import with_sso_ui
from sso.utils import get_logout_url
from django.core import serializers
from django.db.models import Count, Prefetch
from django.db import transaction
from django_auto_prefetching import AutoPrefetchViewSetMixin

from .decorators import query_count
from .models import Course, Review, Profile, ReviewLike, ReviewTag, Tag, Bookmark
from .serializers import AccountSerializer, CourseSerializer, CourseDetailSerializer, ReviewDSSerializer, ReviewSerializer, BookmarkSerializer
from django.http.response import HttpResponseRedirect
from courseUpdater import courseApi
from django.shortcuts import redirect
import logging


logger = logging.getLogger(__name__)

@api_view(['GET'])
@permission_classes((permissions.AllowAny,))
def update_course(request):
	"""
	For populate courses data 
	"""
	start = datetime.now()
	courseApi.update_courses()
	finish = datetime.now()

	latency = (finish-start).seconds
	time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
	message = 'Course updated succeed on %s, elapsed time: %s seconds' % (time, latency)
	return Response({'message': message})

@api_view(['GET'])
@permission_classes((permissions.AllowAny,))
def ping(request):
    """
    Just ping.
    """
    return Response("pong")

# TODO: Refactor login, logout, token to viewset
@api_view(['GET', 'POST'])
@permission_classes((permissions.AllowAny,))
@with_sso_ui()
def login(request, sso_profile):
    """
    Handle SSO UI login.
    Create a new user & profile if it doesn't exists
    and return token if SSO login suceed.
    """
    if sso_profile is not None:
        redirect_url = request.query_params.get("redirect_url")
        token = process_sso_profile(sso_profile)
        username = sso_profile['username']
        if redirect_url is None:
            return HttpResponseRedirect(
                '/token?token=%s&username=%s' % (token, username))
        else:
            return redirect(
                '%s?token=%s&username=%s' % (redirect_url, token, username))
			
    data = {'message': 'invalid sso'}
    return Response(data=data, status=status.HTTP_401_UNAUTHORIZED)


@api_view(['GET'])
@permission_classes((permissions.AllowAny,))
def token(request):
	return Response(request.GET)


@api_view(['GET'])
def logout(request):
    """
    Handle SSO UI logout.
    Remember that this endpoint require Token Authorization. 
    """
    return HttpResponseRedirect(get_logout_url(request))


# @api_view(['GET'])
# # Default permission for any endpoint: permissions.IsAuthenticated
# def restricted_sample_endpoint(request):
#     """
#     Simple sample enpoint that require Token Authorization.
#     """
#     message = 'If you can see this, it means you\'re already logged in.'
#     username = request.user.username
#     if hasattr(request.user, 'profile'):
#         profile = request.user.profile
#     else:
#         profile = None
#     # It's just quick hacks for temporary output.
#     # Should be used Django Rest Serializer instead.
#     profile_json = serializers.serialize('json', [profile])
#     return Response({'message': message,
#                      'username': username,
#                      'profile': profile_json})


class CourseViewSet(AutoPrefetchViewSetMixin, viewsets.ReadOnlyModelViewSet):
	permission_classes = [permissions.AllowAny]  # temprorary
	serializer_class = CourseSerializer
	filter_backends = [SearchFilter, DjangoFilterBackend]
	search_fields = ['name', 'aliasName', 'description', 'code']
	# filterset_fields = ['curriculums__name', 'tags__name', 'sks',
	# 					'prerequisites__name']

	def get_queryset(self):
		return Course.objects.annotate(review_count=Count('reviews'))

	def list(self, request, *args, **kwargs):
		courses = self.get_queryset()
		data = self.get_serializer(courses, many=True).data
		return response(data={'courses': data})

	def retrieve(self, request, pk=None, *args, **kwargs):
		courses = Course.objects.filter(id=pk).prefetch_related(
			Prefetch('reviews', queryset=Review.objects.prefetch_related(
				Prefetch('review_tags', queryset=ReviewTag.objects.select_related('tag'))
				))
			).get()
		data = CourseDetailSerializer(courses, many=False).data

		return response(data={'course': data})

def create_review_tag(review, tags):
	for i in tags:
		tag = i.upper()
		tag_obj = Tag.objects.get(tag_name=tag)
		ReviewTag.objects.create(review = review, tag = tag_obj)
		return None

def get_review_by_id(request):
	id = request.query_params.get("id")
	review = Review.objects.filter(id=id).filter(is_active=True).first()
	if review == None:
		return response(error="Review ID not found", status=status.HTTP_404_NOT_FOUND)

	review_likes = ReviewLike.objects.filter(review__id=id)
	review_tags = ReviewTag.objects.all()
	return response(data=ReviewSerializer(review, context={'review_likes': review_likes, 'review_tags':review_tags}).data)

@api_view(['GET', 'PUT', 'POST','DELETE'])
def review(request):
	"""
	Handle CRUD Review.
	Remember that this endpoint require Token Authorization. 
    """
	user = Profile.objects.get(username=str(request.user))

	if request.method == 'GET':
		isById = validateParams(request, ['id'])
		if isById == None:
			return get_review_by_id(request)
		
		isValid = validateParams(request, ['course_code'])
		if isValid != None:
			return isValid
		code = request.query_params.get("course_code")
		
		course = Course.objects.filter(code=code).first()
		if course is None:
			return response(error="Course not found", status=status.HTTP_404_NOT_FOUND)
		reviews = Review.objects.filter(course=course).filter(is_active=True)
		if reviews.exists():
			review_likes = ReviewLike.objects.filter(review__course=course)
			review_tags = ReviewTag.objects.all()
			return response(data=ReviewSerializer(reviews, many=True, context={'review_likes': review_likes, 'review_tags':review_tags}).data)
		return response(data=[])

	if request.method == 'POST':
		isValid = validateBody(request, ['course_code', 'academic_year', 'semester', 'content', 'is_anonym', 'tags'])
		if isValid != None:
			return isValid
		
		course = Course.objects.filter(code=request.data.get("course_code")).first()
		if course is None:
			return response(error="Course not found", status=status.HTTP_404_NOT_FOUND)
		
		tags = request.data.get("tags")
		academic_year = request.data.get("academic_year")
		semester = request.data.get("semester")
		content = request.data.get("content")
		is_anonym = request.data.get("is_anonym")

		try:
			with transaction.atomic():
				review = Review.objects.create(
					user=user,
					course=course,
					academic_year = academic_year,
					semester = semester,
					content = content,
					is_anonym = is_anonym
				)
				create_review_tag(review, tags)
		except Exception as e:
			logger.error("Failed to save review, request data {}".format(request.data))
			return response(error="Failed to save review, error message: {}".format(e), status=status.HTTP_404_NOT_FOUND)

		return response(data=ReviewSerializer(review).data, status=status.HTTP_201_CREATED)
		

	if request.method == 'PUT':
		isValid = validateBody(request, ['review_id', 'content'])
		if isValid != None:
			return isValid

		review_id = request.data.get("review_id")
		content = request.data.get("content")

		review = Review.objects.filter(user=user, id=review_id).first()
		if review is None:
			return response(error="Review does not exist", status=status.HTTP_409_CONFLICT)

		review.content = content
		review.save()

		return response(data=ReviewSerializer(review).data, status=status.HTTP_201_CREATED)
	
	if request.method == 'DELETE':
		isValid = validateParams(request, ['review_id'])
		if isValid != None:
			return isValid

		review_id = request.query_params.get("review_id")
		
		review = Review.objects.filter(user=user, id=review_id).first()
		if review is None:
			return response(error="Review does not exist", status=status.HTTP_409_CONFLICT)
		review.is_active = False
		review.save()
		return response(status=status.HTTP_200_OK)

@api_view(['GET', 'POST'])
def ds_review(request):
	"""
	Handle RU Review for DS.
	Remember that this endpoint require Token Authorization. 
    """
	if request.method == 'GET':
		reviews = Review.objects.filter(hate_speech_status='WAITING').filter(is_active=True)
		if reviews.exists():
			return response(data=ReviewDSSerializer(reviews, many=True).data)
		return response(data=[])

	if request.method == 'POST':
		reviews = request.data
		try:
			with transaction.atomic():
				for rev in reviews:
					review = Review.objects.get(id=rev.get('id'))
					review.sentimen = rev.get('sentimen')
					review.hate_speech_status = rev.get('hate_speech_status')
					review.save()

				return response()
		except Exception as e:
			logger.error("Failed to update review, request data {}".format(request.data))
			return response(error="Failed to update review, error message: {}".format(e), status=status.HTTP_404_NOT_FOUND)


@api_view(['POST'])
def like(request):
	"""
	Handle CUD Like.
	Remember that this endpoint require Token Authorization. 
    """
	user = Profile.objects.get(username=str(request.user))

	if request.method == 'POST':
		isValid = validateBody(request, ['review_id', 'is_like'])
		if isValid != None:
			return isValid
		
		review_id = request.data.get("review_id")
		is_like = request.data.get("is_like")
		
		review = Review.objects.filter(id=review_id).first()
		if review is None:
			return response(error="Review not found", status=status.HTTP_404_NOT_FOUND)

		review_likes = ReviewLike.objects.filter(review=review).first()
		if review_likes is None:
			review_likes = ReviewLike.objects.create(user=user, review=review)

		if is_like == False:
			review_likes.delete()
		
		return response(status=status.HTTP_201_CREATED)


@api_view(['GET', 'POST'])
def bookmark(request):
	user = Profile.objects.get(username=str(request.user))
	if request.method == 'GET':
		bookmarks = Bookmark.objects.filter(user=user)
		return response(data=BookmarkSerializer(bookmarks, many=True).data)

	if request.method == 'POST':
		isValid = validateBody(request, ['course_code', 'is_bookmark'])
		if isValid != None:
			return isValid

		course_code = request.data.get("course_code")
		is_bookmark = request.data.get("is_bookmark")
		course = Course.objects.filter(code=course_code).first()
				
		if course is None:
			return response(error="Course not found", status=status.HTTP_404_NOT_FOUND)

		bookmark = Bookmark.objects.filter(user=user, course=course).first()
		if bookmark is None:
			bookmark = Bookmark.objects.create(user=user, course=course)
		
		if is_bookmark == False:
			bookmark.delete()

		return response(data=BookmarkSerializer(bookmark).data, status=status.HTTP_201_CREATED)

@api_view(['GET', 'POST', 'DELETE'])
@permission_classes((permissions.AllowAny,)) #temp
def tag(request):
	"""
	Handle CR Tag.
	Remember that this endpoint require Token Authorization. 
    """
	if request.method == 'GET':
		tags = Tag.objects.filter(is_active=True)
		res_tags = []
		for tag in tags:
			res_tags.append(tag.tag_name)
		return response(data = {'tags': res_tags})

	if request.method == 'POST':
		isValid = validateBody(request, ['tags'])
		if isValid != None:
			return isValid
		
		tags = request.data.get("tags")
		for tag in tags:
			tag = tag.upper()
			try:
				Tag.objects.get(tag_name=tag)
			except:
				Tag.objects.create(tag_name=tag)
		return response(status=status.HTTP_201_CREATED)
	
	if request.method == 'DELETE':
		isValid = validateBody(request, ['tags'])
		if isValid != None:
			return isValid
		
		tags = request.data.get("tags")
		for tag in tags:
			tag = tag.upper()
			try:
				Tag.objects.get(tag_name=tag).update(is_active=False)
			except:
				continue
		return response(status=status.HTTP_200_OK)

# @api_view(['GET'])
# @permission_classes((permissions.AllowAny,))
# def update_courses(request):
# 	from courseUpdater.courseApi import update_courses
# 	"""
# 	Just an overly simple sample enpoint to call.
# 	"""
# 	try:
# 		update_courses()
# 		return Response({'update': 'success'})
# 	except:
# 		return Response({'update': 'failed'})

@api_view(['GET'])
def account(request):
	"""
	Return current user's data
	Remember that this endpoint require Token Authorization. 
    """
	user = Profile.objects.get(username=str(request.user))
	return response(data=AccountSerializer(user, many=False).data)