import re
import unicodedata

from django.db import transaction

from main.models import Calculator, Course, CourseSemester, UserGPA
from main.utils import (
    add_course_to_semester,
    add_semester_gpa,
    check_notexist_and_create_user_cumulative_gpa,
)


def normalize_course_code(value):
    value = unicodedata.normalize("NFKC", str(value or "")).upper()
    return re.sub(r"\s+", "", value)


def resolve_courses(scraped_courses):
    """Resolve SLCM codes to local courses and report unmatched entries."""
    resolved = []
    unmatched = []
    seen_ids = set()
    for scraped_course in scraped_courses:
        code = normalize_course_code(scraped_course["code"])
        course = (
            Course.objects.filter(code__iexact=code)
            .order_by("-curriculum", "id")
            .first()
        )
        if course is None:
            unmatched.append(scraped_course)
            continue
        if course.id not in seen_ids:
            seen_ids.add(course.id)
            resolved.append(course)
    return resolved, unmatched


@transaction.atomic
def import_courses(profile, given_semester, courses):
    """Add resolved courses to one calculator semester atomically."""
    if not courses:
        raise ValueError("At least one resolved course is required.")

    cumulative_gpa = check_notexist_and_create_user_cumulative_gpa(profile)
    semester, semester_created = UserGPA.objects.get_or_create(
        userCumulativeGPA=cumulative_gpa,
        given_semester=str(given_semester),
    )
    existing_ids = set(
        CourseSemester.objects.filter(
            semester=semester, course_id__in=[course.id for course in courses]
        ).values_list("course_id", flat=True)
    )
    inserted = []
    duplicates = []
    for course in courses:
        if course.id in existing_ids:
            duplicates.append(course)
            continue

        calculator = Calculator.objects.create(user=profile, course=course)
        CourseSemester.objects.create(
            semester=semester,
            course=course,
            calculator=calculator,
        )
        add_course_to_semester(semester=semester, sks=course.sks)
        add_semester_gpa(
            user_cumulative_gpa=cumulative_gpa,
            total_sks=course.sks,
            semester_gpa=0,
        )
        inserted.append(course)

    return {
        "semester": semester,
        "semester_created": semester_created,
        "inserted": inserted,
        "duplicates": duplicates,
    }
