import functools
from rapidfuzz import fuzz
from django_filters.rest_framework.backends import DjangoFilterBackend
from courseUpdater import courseApi
from live_config.views import get_config
from rest_framework.filters import SearchFilter
from rest_framework import status, viewsets
from rest_framework.decorators import api_view
from .utils import get_paged_obj, get_profile_term, response, response_paged
from django.db.models import (
    F,
    Case,
    Count,
    FloatField,
    Func,
    IntegerField,
    Prefetch,
    Q,
    Value,
    When,
)
from django_auto_prefetching import AutoPrefetchViewSetMixin

from .models import Course, Review, ReviewTag
from .serializers import CourseSerializer
import logging

logger = logging.getLogger(__name__)


def _display_name(value):
    """Return the local display name from a bilingual config value."""
    return value.split("(", 1)[0].strip()


def get_major_choices():
    """Build the unique, sorted faculty-study-program display values."""
    orgs = get_config("kd_org") or {}
    choices = {
        "{} - {}".format(
            _display_name(org["faculty"]), _display_name(org["study_program"])
        )
        for org in orgs.values()
        if org.get("faculty") and org.get("study_program")
    }
    return sorted(choices, key=str.casefold)


def get_study_program_for_major(major):
    """Resolve a display major to the study-program config key."""
    orgs = get_config("kd_org") or {}
    requested_major = major.strip().casefold()
    matches = {}

    for org in orgs.values():
        faculty = org.get("faculty")
        study_program = org.get("study_program")
        if not faculty or not study_program:
            continue

        full_label = "{} - {}".format(
            _display_name(faculty), _display_name(study_program)
        ).casefold()
        program_label = _display_name(study_program).casefold()
        if requested_major == full_label or requested_major == program_label:
            matches[study_program] = study_program

    if len(matches) == 1:
        return next(iter(matches.values()))
    return None


@api_view(["GET"])
def majors(request):
    return response(data={"majors": get_major_choices()})


class CourseViewSet(AutoPrefetchViewSetMixin, viewsets.ReadOnlyModelViewSet):
    serializer_class = CourseSerializer
    filter_backends = [SearchFilter, DjangoFilterBackend]
    search_fields = ["name", "aliasName", "description", "code"]

    def get_queryset(self):
        return Course.objects.annotate(review_count=Count("reviews"))

    def filter_by_study_program(self, courses, study_program):
        try:
            course_prefixes = [
                prefix.strip()
                for prefix in get_config("study_program")[study_program].split(",")
                if prefix.strip()
            ]
        except:
            logger.error(
                "Failed to get course prefix, study program {}".format(study_program)
            )
            return None

        courses = courses.filter(
            functools.reduce(
                lambda a, b: a | b, [Q(code__startswith=x) for x in course_prefixes]
            )
        )
        return courses

    def list(self, request, *args, **kwargs):
        courses = self.get_queryset()
        error = None

        courses = filter_course(request, courses)
        courses.order_by("name")

        show_all = request.GET.get("show_all", "").lower() == "true"
        requested_major = request.query_params.get("major")
        if requested_major is not None:
            study_program = get_study_program_for_major(requested_major)
            if study_program is None:
                return response(
                    error="Major not found or has no course mapping.",
                    status=status.HTTP_400_BAD_REQUEST,
                )

            courses = self.filter_by_study_program(courses, study_program)
            if courses is None:
                return response(
                    error="Major not found or has no course mapping.",
                    status=status.HTTP_400_BAD_REQUEST,
                )

        if not show_all:
            profile = request.user.profile_set.get()
            courses = courses.filter(term=get_profile_term(profile))

            if requested_major is None:
                study_program = profile.study_program
                courses = self.filter_by_study_program(courses, study_program)

            if courses == None:
                error = "Study program not found."

        if not "page" in request.GET:
            data = self.get_serializer(courses, many=True).data
            return response(data={"courses": data}, error=error)

        page = request.GET["page"]
        courses, total_page = get_paged_obj(courses, page, _sort_by_id=False)
        data = self.get_serializer(courses, many=True).data
        return response_paged(
            data={"courses": data}, error=error, total_page=total_page
        )

    def retrieve(self, request, pk=None, *args, **kwargs):
        courses = (
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
                )
            )
            .get()
        )
        data = self.get_serializer(courses, many=False).data

        return response(data={"course": data})


def filter_course(request, courses):
    code = request.query_params.get("code")
    if code != None:
        courses = courses.filter(Q(code__icontains=code))

    lst_code_desc = request.query_params.get("code_desc")
    if lst_code_desc != None:
        lst_code_desc = lst_code_desc.split(",")
        course_prefixes = get_config("course_prefixes")
        reverse_course_prefix = {v: k for k, v in course_prefixes.items()}
        courses = courses.filter(
            functools.reduce(
                lambda a, b: a | b,
                [Q(code__icontains=reverse_course_prefix[x]) for x in lst_code_desc],
            )
        )

    name = request.query_params.get("name")
    if name != None:
        course_names = [(c.id, c.name) for c in courses]
        scored = {}
        for cid, cname in course_names:
            score = fuzz.WRatio(name.lower(), cname.lower())
            if score > 70:
                scored[cid] = score

        courses = (
            courses.filter(id__in=scored.keys())
            .annotate(
                fuzzy_score=Case(
                    *[When(id=k, then=Value(v)) for k, v in scored.items()],
                    output_field=FloatField(),
                )
            )
            .order_by("-fuzzy_score")
        )

    lst_sks = request.query_params.get("sks")
    if lst_sks != None:
        lst_sks = lst_sks.split(",")
        courses = courses.filter(
            functools.reduce(lambda a, b: a | b, [Q(sks=sks) for sks in lst_sks])
        )

    lst_term = request.query_params.get("term")
    if lst_term != None:
        lst_term = lst_term.split(",")
        courses = courses.filter(
            functools.reduce(lambda a, b: a | b, [Q(term=term) for term in lst_term])
        )

    return courses
