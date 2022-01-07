import functools
from django_filters.rest_framework.backends import DjangoFilterBackend
from live_config.views import get_config
from rest_framework.filters import SearchFilter
from rest_framework import viewsets
from .utils import get_paged_obj, get_profile_term, response, response_paged
from django.db.models import Count, Prefetch, Q
from django_auto_prefetching import AutoPrefetchViewSetMixin

from .models import Course, Review, ReviewTag
from .serializers import CourseSerializer
import logging

logger = logging.getLogger(__name__)


class CourseViewSet(AutoPrefetchViewSetMixin, viewsets.ReadOnlyModelViewSet):
	serializer_class = CourseSerializer
	filter_backends = [SearchFilter, DjangoFilterBackend]
	search_fields = ['name', 'aliasName', 'description', 'code']

	def get_queryset(self):
		return Course.objects.annotate(review_count=Count('reviews'))

	def filter_by_study_program(self, courses, study_program):
		try:
			course_prefixes = get_config('study_program')[study_program].split(',')
		except:
			logger.error("Failed to get course prefix, study program {}".format(study_program))
			return None

		courses = courses.filter(functools.reduce(lambda a, b: a | b, [Q(code__contains=x) for x in course_prefixes]))
		return courses

	def list(self, request, *args, **kwargs):
		courses = self.get_queryset()
		error = None

		courses = filter_course(request, courses)

		if not ('show_all' in request.GET and request.GET['show_all'].lower() == 'true'):
			profile = request.user.profile_set.get()
			courses = courses.filter(term=get_profile_term(profile))
			study_program = profile.study_program
			courses = self.filter_by_study_program(courses, study_program)

			if courses == None:
				error = 'Study program not found.'
		
		if not 'page' in request.GET:
			data = self.get_serializer(courses, many=True).data
			return response(data={'courses': data}, error=error)
		
		page = request.GET['page']
		courses, total_page = get_paged_obj(courses, page)
		data = self.get_serializer(courses, many=True).data
		return response_paged(data={'courses': data}, error=error, total_page=total_page)

	def retrieve(self, request, pk=None, *args, **kwargs):
		courses = Course.objects.filter(id=pk).prefetch_related(
			Prefetch('reviews', queryset=Review.objects.prefetch_related(
				Prefetch('review_tags', queryset=ReviewTag.objects.select_related('tag'))
				))
			).get()
		data = self.get_serializer(courses, many=False).data

		return response(data={'course': data})

def filter_course(request, courses):
	code = request.query_params.get("code")
	if code != None:
		courses = courses.filter(Q(code__icontains=code))

	code_desc = request.query_params.get("code_desc")
	if code_desc != None:
		course_prefixes = get_config('course_prefixes')
		reverse_course_prefix = {v: k for k, v in course_prefixes.items()}
		if code_desc in reverse_course_prefix:
			print(reverse_course_prefix[code_desc])
			courses = courses.filter(Q(code__icontains=reverse_course_prefix[code_desc]))
	
	name = request.query_params.get("name")
	if name != None:
		courses = courses.filter(Q(name__icontains=name))

	sks = request.query_params.get("sks")
	if sks != None:
		courses = courses.filter(Q(sks=sks))

	term = request.query_params.get("term")
	if term != None:
		courses = courses.filter(Q(term=term))
	
	return courses