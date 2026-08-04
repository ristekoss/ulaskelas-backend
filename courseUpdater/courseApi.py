import logging

import environ
import requests
from django.db import transaction
from django.utils import timezone

from live_config.views import get_config
from main.models import Course, StudyProgram, StudyProgramCourse


logger = logging.getLogger(__name__)
SUPPORTED_EDUCATIONAL_PROGRAM_PREFIXES = ("S1 ", "D3 ", "D4 ")
COURSE_TYPE_ALIASES = {
    "MANDATORY": StudyProgramCourse.CourseType.MANDATORY,
    "WAJIB": StudyProgramCourse.CourseType.MANDATORY,
    "ELECTIVE": StudyProgramCourse.CourseType.ELECTIVE,
    "PILIHAN": StudyProgramCourse.CourseType.ELECTIVE,
}


class CourseSyncError(Exception):
    """Raised when a SunJad response cannot safely update the local catalog."""


def is_supported_educational_program(value):
    return bool(value) and value.startswith(SUPPORTED_EDUCATIONAL_PROGRAM_PREFIXES)


def get_supported_program_configs():
    orgs = get_config("kd_org") or {}
    return {
        org_code: org
        for org_code, org in orgs.items()
        if is_supported_educational_program(org.get("educational_program", ""))
    }


def ensure_study_program(org_code):
    org = (get_config("kd_org") or {}).get(org_code)
    if org is None:
        raise CourseSyncError("Unknown org_code: {}".format(org_code))
    if not is_supported_educational_program(org.get("educational_program", "")):
        raise CourseSyncError("Unsupported educational program: {}".format(org_code))

    study_program, _ = StudyProgram.objects.update_or_create(
        org_code=org_code,
        defaults={
            "faculty": org.get("faculty", ""),
            "study_program": org.get("study_program", ""),
            "educational_program": org.get("educational_program", ""),
            "is_supported": True,
        },
    )
    return study_program


def update_courses(major_kd):
    """Synchronize one program and return a summary of the applied changes."""
    study_program = ensure_study_program(major_kd)
    baseurl = environ.Env()("SUNJAD_BASE_URL")
    if not isinstance(baseurl, str) or not baseurl.strip():
        raise CourseSyncError("SUNJAD_BASE_URL is not configured")

    url = "{}/majors/kd/{}/all_courses".format(baseurl.rstrip("/"), major_kd)
    payload = _fetch_courses_json(url)
    return _apply_courses_payload(study_program, payload)


def _fetch_courses_json(url):
    try:
        response = requests.get(url, timeout=20)
        response.raise_for_status()
        payload = response.json()
    except (requests.RequestException, ValueError) as exc:
        raise CourseSyncError("Failed to fetch SunJad courses") from exc

    if not isinstance(payload, dict) or not isinstance(payload.get("courses"), list):
        raise CourseSyncError("Invalid SunJad courses response")
    return payload


def _apply_courses_payload(study_program, payload):
    courses_json = payload.get("courses")
    if not isinstance(courses_json, list):
        raise CourseSyncError("Invalid SunJad courses response")

    active_mapping_ids = set()
    skipped = 0
    with transaction.atomic():
        for course_json in courses_json:
            try:
                course = _upsert_course(course_json)
            except (KeyError, TypeError, ValueError) as exc:
                skipped += 1
                logger.warning(
                    "Skipping invalid SunJad course for org_code=%s: %s",
                    study_program.org_code,
                    exc,
                )
                continue

            mapping, _ = StudyProgramCourse.objects.update_or_create(
                study_program=study_program,
                course=course,
                defaults={
                    "program_term": int(course_json["term"]),
                    "curriculum": str(course_json.get("curriculum") or ""),
                    "course_type": _resolve_course_type(course_json),
                    "is_active": True,
                },
            )
            active_mapping_ids.add(mapping.id)

        if courses_json and not active_mapping_ids:
            raise CourseSyncError("SunJad returned no valid course records")

        stale_count = 0
        if skipped == 0:
            stale_mappings = StudyProgramCourse.objects.filter(
                study_program=study_program, is_active=True
            )
            if active_mapping_ids:
                stale_mappings = stale_mappings.exclude(id__in=active_mapping_ids)
            stale_count = stale_mappings.update(is_active=False)

        study_program.last_synced_at = timezone.now()
        study_program.save(update_fields=["last_synced_at"])

    return {
        "org_code": study_program.org_code,
        "active_courses": len(active_mapping_ids),
        "inactive_courses": stale_count,
        "skipped_courses": skipped,
    }


def _upsert_course(course_json):
    code = str(course_json["code"]).strip()
    if not code:
        raise ValueError("course code is empty")

    curriculum = str(course_json.get("curriculum") or "")
    course = Course.objects.filter(code=code).order_by("-curriculum", "id").first()
    if course is None:
        course = Course(code=code)

    # Course.term remains populated for legacy consumers. Program-specific
    # filtering uses StudyProgramCourse.program_term.
    course.curriculum = curriculum
    course.sks = int(course_json["credit"])
    course.description = course_json.get("description") or ""
    course.name = str(course_json["name"])
    course.term = int(course_json["term"])
    course.prerequisites = course_json.get("prerequisite") or ""
    course.save()
    return course


def _resolve_course_type(course_json):
    raw_type = (
        course_json.get("course_type")
        or course_json.get("type")
        or course_json.get("category")
    )
    if raw_type:
        normalized_type = str(raw_type).strip().upper()
        resolved = COURSE_TYPE_ALIASES.get(normalized_type)
        if resolved:
            return resolved
        if normalized_type.startswith("WAJIB"):
            return StudyProgramCourse.CourseType.MANDATORY
        if normalized_type.startswith(("PILIHAN", "PEMINATAN")):
            return StudyProgramCourse.CourseType.ELECTIVE

    code = str(course_json.get("code") or "")
    prefix_mappings = get_config("course_prefixes") or {}
    for prefix, description in prefix_mappings.items():
        if not code.startswith(prefix):
            continue
        normalized_description = str(description).casefold()
        if "wajib" in normalized_description:
            return StudyProgramCourse.CourseType.MANDATORY
        if "pilihan" in normalized_description or "peminatan" in normalized_description:
            return StudyProgramCourse.CourseType.ELECTIVE
    return StudyProgramCourse.CourseType.UNKNOWN


# Backwards-compatible helpers retained for callers/tests that imported them.
def getCourse(course_json):
    return _upsert_course(course_json)


def populateCourseData(course, course_json):
    course.curriculum = str(course_json.get("curriculum") or "")
    course.sks = int(course_json["credit"])
    course.description = course_json.get("description") or ""
    course.name = str(course_json["name"])
    course.term = int(course_json["term"])
    course.prerequisites = course_json.get("prerequisite") or ""
    return course
