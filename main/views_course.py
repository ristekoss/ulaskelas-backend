import functools
import logging

from django.db.models import Case, Count, F, FloatField, Prefetch, Q, Value, When
from django_filters.rest_framework.backends import DjangoFilterBackend
from django_auto_prefetching import AutoPrefetchViewSetMixin
from live_config.views import get_config
from rapidfuzz import fuzz
from rest_framework import status, viewsets
from rest_framework.decorators import api_view
from rest_framework.filters import SearchFilter

from courseUpdater.courseApi import is_supported_educational_program
from .models import Course, Review, ReviewTag, StudyProgramCourse
from .serializers import CourseSerializer
from .utils import get_paged_obj, get_profile_term, response, response_paged


logger = logging.getLogger(__name__)


def _display_name(value):
    """Return the local display name from a bilingual config value."""
    return (value or "").split("(", 1)[0].strip()


def _active_study_program_courses_prefetch():
    return Prefetch(
        "study_program_courses",
        queryset=StudyProgramCourse.objects.filter(
            is_active=True, study_program__is_supported=True
        ).select_related("study_program"),
        to_attr="active_study_program_courses",
    )


def get_major_choices():
    """Return supported programs with stable org-code identifiers."""
    orgs = get_config("kd_org") or {}
    available_org_codes = set(
        StudyProgramCourse.objects.filter(
            is_active=True, study_program__is_supported=True
        ).values_list("study_program_id", flat=True)
    )
    choices = []
    for org_code, org in orgs.items():
        educational_program = org.get("educational_program", "")
        if not is_supported_educational_program(educational_program):
            continue

        faculty = _display_name(org.get("faculty"))
        study_program = _display_name(org.get("study_program"))
        educational_program_display = _display_name(educational_program)
        choices.append(
            {
                "id": org_code,
                "org_code": org_code,
                "faculty": faculty,
                "study_program": study_program,
                "educational_program": educational_program_display,
                "display_name": "{} - {} - {}".format(
                    faculty, study_program, educational_program_display
                ),
                "available": org_code in available_org_codes,
            }
        )
    return sorted(choices, key=lambda item: item["display_name"].casefold())


def is_known_supported_major(org_code):
    org = (get_config("kd_org") or {}).get(org_code)
    return bool(
        org
        and is_supported_educational_program(org.get("educational_program", ""))
    )


@api_view(["GET"])
def majors(request):
    return response(data={"majors": get_major_choices()})


class CourseViewSet(AutoPrefetchViewSetMixin, viewsets.ReadOnlyModelViewSet):
    serializer_class = CourseSerializer
    filter_backends = [SearchFilter, DjangoFilterBackend]
    search_fields = ["name", "description", "code"]

    def get_queryset(self):
        return Course.objects.annotate(review_count=Count("reviews")).prefetch_related(
            _active_study_program_courses_prefetch()
        )

    def list(self, request, *args, **kwargs):
        courses = self.get_queryset()
        show_all = request.query_params.get("show_all", "").lower() == "true"
        requested_major = request.query_params.get("major")
        effective_major = requested_major

        if effective_major is None and not show_all:
            profile = request.user.profile_set.get()
            effective_major = profile.org_code

        if effective_major is not None:
            if not is_known_supported_major(effective_major):
                return response(
                    error={
                        "code": "MAJOR_NOT_SUPPORTED",
                        "message": (
                            "Major was not found or is outside the supported "
                            "program scope."
                        ),
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )
            courses = courses.filter(
                study_program_courses__study_program_id=effective_major,
                study_program_courses__is_active=True,
            ).annotate(
                program_term=F("study_program_courses__program_term"),
                annotated_course_type=F("study_program_courses__course_type"),
            )
        else:
            # show_all is still a catalog view: courses that disappeared from
            # every supported SunJad catalog remain stored only for history.
            courses = courses.filter(
                study_program_courses__is_active=True,
                study_program_courses__study_program__is_supported=True,
            )

        courses = filter_course(
            request, courses, program_filtered=effective_major is not None
        )

        if not show_all and request.query_params.get("term") is None:
            profile = request.user.profile_set.get()
            if effective_major is not None:
                courses = courses.filter(program_term=get_profile_term(profile))
            else:
                courses = courses.filter(term=get_profile_term(profile))

        courses = courses.order_by("name").distinct()
        if "page" not in request.GET:
            data = self.get_serializer(courses, many=True).data
            return response(data={"courses": data})

        courses, total_page = get_paged_obj(
            courses, request.GET["page"], _sort_by_id=False
        )
        data = self.get_serializer(courses, many=True).data
        return response_paged(data={"courses": data}, total_page=total_page)

    def retrieve(self, request, pk=None, *args, **kwargs):
        course = (
            Course.objects.filter(id=pk)
            .prefetch_related(
                Prefetch(
                    "reviews",
                    queryset=Review.objects.prefetch_related(
                        Prefetch(
                            "review_tags",
                            queryset=ReviewTag.objects.select_related("tag"),
                        )
                    ),
                ),
                _active_study_program_courses_prefetch(),
            )
            .get()
        )
        return response(data={"course": self.get_serializer(course).data})


def filter_course(request, courses, program_filtered=False):
    code = request.query_params.get("code")
    if code is not None:
        courses = courses.filter(code__icontains=code)

    code_descriptions = request.query_params.get("code_desc")
    if code_descriptions is not None:
        requested_descriptions = code_descriptions.split(",")
        course_prefixes = get_config("course_prefixes") or {}
        reverse_course_prefix = {value: key for key, value in course_prefixes.items()}
        prefixes = [
            reverse_course_prefix[value]
            for value in requested_descriptions
            if value in reverse_course_prefix
        ]
        if not prefixes:
            return courses.none()
        courses = courses.filter(
            functools.reduce(
                lambda left, right: left | right,
                [Q(code__startswith=prefix) for prefix in prefixes],
            )
        )

    name = request.query_params.get("name")
    if name is not None:
        course_names = [(course.id, course.name) for course in courses]
        scored = {}
        for course_id, course_name in course_names:
            score = fuzz.WRatio(name.lower(), course_name.lower())
            if score > 70:
                scored[course_id] = score

        courses = courses.filter(id__in=scored.keys()).annotate(
            fuzzy_score=Case(
                *[When(id=key, then=Value(value)) for key, value in scored.items()],
                output_field=FloatField(),
            )
        ).order_by("-fuzzy_score")

    sks_values = request.query_params.get("sks")
    if sks_values is not None:
        courses = courses.filter(sks__in=sks_values.split(","))

    term_values = request.query_params.get("term")
    if term_values is not None:
        term_values = term_values.split(",")
        if program_filtered:
            courses = courses.filter(program_term__in=term_values)
        else:
            courses = courses.filter(term__in=term_values)

    course_types = request.query_params.get("course_type")
    if course_types is not None:
        valid_types = {
            choice[0] for choice in StudyProgramCourse.CourseType.choices
        }
        requested_types = {
            value.strip().upper()
            for value in course_types.split(",")
            if value.strip()
        }
        if not requested_types or not requested_types.issubset(valid_types):
            return courses.none()
        if program_filtered:
            courses = courses.filter(annotated_course_type__in=requested_types)
        else:
            courses = courses.filter(
                study_program_courses__is_active=True,
                study_program_courses__course_type__in=requested_types,
            )

    return courses
