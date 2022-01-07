import datetime
from rest_framework.decorators import api_view, permission_classes
from rest_framework import permissions, status
from rest_framework.response import Response
from datetime import datetime
from django.db.models import Q
from .utils import get_paged_obj, process_sso_profile, response, response_paged, validate_body
from sso.decorators import with_sso_ui
from sso.utils import get_logout_url

from .models import Course, Review, Profile, ReviewLike, Tag, Bookmark
from .serializers import AccountSerializer, BookmarkSerializer
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
		return redirect('%s?token=%s&username=%s' % (redirect_url, token, username))
			
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

@api_view(['POST'])
def like(request):
	"""
	Handle CUD Like.
	Remember that this endpoint require Token Authorization. 
    """
	user = Profile.objects.get(username=str(request.user))

	if request.method == 'POST':
		is_valid = validate_body(request, ['review_id', 'is_like'])
		if is_valid != None:
			return is_valid
		
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
		page = request.query_params.get("page")
		bookmarks = Bookmark.objects.filter(user=user)
		if page != None:
			bookmarks, total_page = get_paged_obj(bookmarks, page)
			return response_paged(data=BookmarkSerializer(bookmarks, many=True).data, total_page=total_page)
		return response(data=BookmarkSerializer(bookmarks, many=True).data)

	if request.method == 'POST':
		is_valid = validate_body(request, ['course_code', 'is_bookmark'])
		if is_valid != None:
			return is_valid

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
	if request.method == 'GET':
		page = request.query_params.get("page")
		tags = Tag.objects.filter(is_active=True)

		q = request.query_params.get("q")
		if q != None:
			tags = tags.filter(Q(tag_name__icontains=q))
			
		res_tags = []
		if page != None:
			tags, total_page = get_paged_obj(tags, page)
			for tag in tags:
				res_tags.append(tag.tag_name)
			return response_paged(data = {'tags': res_tags}, total_page=total_page)
		for tag in tags:
			res_tags.append(tag.tag_name)
		return response(data = {'tags': res_tags})

	if request.method == 'POST':
		is_valid = validate_body(request, ['tags'])
		if is_valid != None:
			return is_valid
		
		tags = request.data.get("tags")
		for tag in tags:
			tag = tag.upper()
			try:
				Tag.objects.get(tag_name=tag)
			except:
				Tag.objects.create(tag_name=tag)
		return response(status=status.HTTP_201_CREATED)
	
	if request.method == 'DELETE':
		is_valid = validate_body(request, ['tags'])
		if is_valid != None:
			return is_valid
		
		tags = request.data.get("tags")
		for tag in tags:
			tag = tag.upper()
			try:
				Tag.objects.get(tag_name=tag).update(is_active=False)
			except:
				continue
		return response(status=status.HTTP_200_OK)


@api_view(['GET'])
def account(request):
	"""
	Return current user's data
	Remember that this endpoint require Token Authorization. 
    """
	user = Profile.objects.get(username=str(request.user))
	return response(data=AccountSerializer(user, many=False).data)