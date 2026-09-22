from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import api_view

from main.integrations.slcm_autofill import (
    expire_stale_sessions,
    start_scraper,
)
from main.integrations.slcm_irs import import_courses
from main.models import Course, Profile, SLCMAutofillSession
from main.utils import response


ACTIVE_STATUSES = [
    SLCMAutofillSession.Status.WAITING_LOGIN,
    SLCMAutofillSession.Status.SCRAPING,
    SLCMAutofillSession.Status.READY,
]


def _profile(request):
    return Profile.objects.get(username=str(request.user))


def _current_semester(profile, today=None):
    """Calculate the student's current semester from their NPM entry year."""
    today = today or timezone.localdate()
    npm = (profile.npm or "").strip()
    if len(npm) < 2 or not npm[:2].isdigit():
        return None

    entry_year = 2000 + int(npm[:2])
    # UI's odd semester runs from August through January, followed by the even
    # semester from February through July.
    academic_year_start = today.year if today.month >= 8 else today.year - 1
    semester_in_year = 1 if today.month >= 8 or today.month == 1 else 2
    semester = (academic_year_start - entry_year) * 2 + semester_in_year
    return str(semester) if semester > 0 else None


def _serialize(session):
    data = {
        "session_id": str(session.id),
        "given_semester": session.given_semester,
        "status": session.status,
        "expires_at": session.expires_at,
        "source_period": session.source_period or None,
        "preview": session.preview if session.status in {
            SLCMAutofillSession.Status.READY,
            SLCMAutofillSession.Status.IMPORTED,
        } else None,
        "error": session.error,
    }
    return data


@api_view(["POST"])
def slcm_autofill_sessions(request):
    profile = _profile(request)
    username = request.data.get("username")
    password = request.data.get("password")
    if not isinstance(username, str) or not username.strip():
        return response(
            error={"code": "INVALID_CREDENTIALS", "message": "username is required."},
            status=status.HTTP_400_BAD_REQUEST,
        )
    if username.strip().casefold() != profile.username.casefold():
        return response(
            error={
                "code": "IDENTITY_MISMATCH",
                "message": "The SSO username must match the authenticated profile.",
            },
            status=status.HTTP_400_BAD_REQUEST,
        )
    if not isinstance(password, str) or not password:
        return response(
            error={"code": "INVALID_CREDENTIALS", "message": "password is required."},
            status=status.HTTP_400_BAD_REQUEST,
        )
    given_semester = request.data.get("given_semester")
    if given_semester is None:
        given_semester = _current_semester(profile)
        if given_semester is None:
            return response(
                error={
                    "code": "SEMESTER_UNAVAILABLE",
                    "message": "Current semester cannot be determined from the user's NPM.",
                },
                status=status.HTTP_422_UNPROCESSABLE_ENTITY,
            )
    elif not isinstance(given_semester, str) or not given_semester.strip():
        return response(
            error={"code": "INVALID_SEMESTER", "message": "given_semester must be a non-empty string."},
            status=status.HTTP_400_BAD_REQUEST,
        )
    given_semester = given_semester.strip()
    if len(given_semester) > 20:
        return response(
            error={"code": "INVALID_SEMESTER", "message": "given_semester cannot exceed 20 characters."},
            status=status.HTTP_400_BAD_REQUEST,
        )
    expire_stale_sessions()
    with transaction.atomic():
        active = SLCMAutofillSession.objects.select_for_update().filter(
            user=profile, status__in=ACTIVE_STATUSES
        ).first()
        if active is not None:
            return response(
                error={
                    "code": "SESSION_ALREADY_ACTIVE",
                    "message": "This user already has an active SLCM autofill session.",
                    "session_id": str(active.id),
                },
                status=status.HTTP_409_CONFLICT,
            )
        session = SLCMAutofillSession.objects.create(
            user=profile,
            given_semester=given_semester,
            expires_at=timezone.now() + timedelta(seconds=settings.SLCM_AUTOFILL_TIMEOUT_SECONDS),
        )
        transaction.on_commit(
            lambda: start_scraper(session.id, username.strip(), password)
        )
    return response(data=_serialize(session), status=status.HTTP_201_CREATED)


@api_view(["GET", "DELETE"])
def slcm_autofill_session(request, session_id):
    expire_stale_sessions()
    session = SLCMAutofillSession.objects.filter(pk=session_id, user=_profile(request)).first()
    if session is None:
        return response(error="SLCM autofill session was not found.", status=status.HTTP_404_NOT_FOUND)
    if request.method == "DELETE":
        if session.status not in ACTIVE_STATUSES:
            return response(
                error={"code": "SESSION_NOT_ACTIVE", "message": "Only an active session can be cancelled."},
                status=status.HTTP_409_CONFLICT,
            )
        session.status = SLCMAutofillSession.Status.CANCELLED
        session.save(update_fields=["status", "updated_at"])
        return response(status=status.HTTP_204_NO_CONTENT)
    return response(data=_serialize(session))


@api_view(["POST"])
def slcm_autofill_confirm(request, session_id):
    profile = _profile(request)
    expire_stale_sessions()
    with transaction.atomic():
        session = SLCMAutofillSession.objects.select_for_update().filter(
            pk=session_id, user=profile
        ).first()
        if session is None:
            return response(error="SLCM autofill session was not found.", status=status.HTTP_404_NOT_FOUND)
        if session.status == SLCMAutofillSession.Status.IMPORTED:
            return response(data=_serialize(session))
        if session.status != SLCMAutofillSession.Status.READY:
            return response(
                error={"code": "SESSION_NOT_READY", "message": "The SLCM preview is not ready to import."},
                status=status.HTTP_409_CONFLICT,
            )
        course_ids = [item["id"] for item in session.preview.get("matched", [])]
        courses_by_id = Course.objects.in_bulk(course_ids)
        courses = [courses_by_id[course_id] for course_id in course_ids if course_id in courses_by_id]
        if not courses:
            return response(
                error={"code": "NO_MATCHED_COURSES", "message": "No matched courses are available to import."},
                status=status.HTTP_409_CONFLICT,
            )
        result = import_courses(profile, session.given_semester, courses)
        session.status = SLCMAutofillSession.Status.IMPORTED
        session.save(update_fields=["status", "updated_at"])
    data = _serialize(session)
    data["result"] = {
        "inserted": len(result["inserted"]),
        "duplicates": len(result["duplicates"]),
    }
    return response(data=data)
