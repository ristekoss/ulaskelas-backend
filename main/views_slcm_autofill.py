import secrets
from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.shortcuts import redirect
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny

from main.integrations.slcm_autofill import (
    expire_stale_sessions,
    hash_popup_token,
    start_scraper,
    validate_slcm_url,
)
from main.integrations.slcm_irs import import_courses
from main.models import Course, Profile, SLCMAutofillSession
from main.utils import response


ACTIVE_STATUSES = [
    SLCMAutofillSession.Status.WAITING_LOGIN,
    SLCMAutofillSession.Status.SCRAPING,
    SLCMAutofillSession.Status.READY,
]
BROWSER_STATUSES = [
    SLCMAutofillSession.Status.WAITING_LOGIN,
    SLCMAutofillSession.Status.SCRAPING,
]


def _profile(request):
    return Profile.objects.get(username=str(request.user))


def _serialize(session, include_popup=False):
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
    if include_popup:
        data["popup_url"] = session.popup_url
    return data


@api_view(["POST"])
def slcm_autofill_sessions(request):
    given_semester = request.data.get("given_semester")
    if not isinstance(given_semester, str) or not given_semester.strip():
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
    try:
        validate_slcm_url()
    except ValueError as exc:
        return response(
            error={"code": "SLCM_NOT_CONFIGURED", "message": str(exc)},
            status=status.HTTP_503_SERVICE_UNAVAILABLE,
        )

    profile = _profile(request)
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
        # The bundled browser exposes one interactive desktop, so serialize sessions globally.
        global_active = SLCMAutofillSession.objects.select_for_update().filter(
            status__in=BROWSER_STATUSES
        ).first()
        if global_active is not None:
            return response(
                error={"code": "BROWSER_BUSY", "message": "The SLCM login browser is currently in use."},
                status=status.HTTP_409_CONFLICT,
            )
        token = secrets.token_urlsafe(32)
        session = SLCMAutofillSession.objects.create(
            user=profile,
            given_semester=given_semester,
            popup_token_hash=hash_popup_token(token),
            expires_at=timezone.now() + timedelta(seconds=settings.SLCM_AUTOFILL_TIMEOUT_SECONDS),
        )
        popup_path = reverse("v1:slcm-autofill-popup", kwargs={"token": token})
        session.popup_url = request.build_absolute_uri(popup_path)
        session.save(update_fields=["popup_url", "updated_at"])
        transaction.on_commit(lambda: start_scraper(session.id))
    return response(data=_serialize(session, include_popup=True), status=status.HTTP_201_CREATED)


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


@api_view(["GET"])
@permission_classes([AllowAny])
def slcm_autofill_popup(request, token):
    token_hash = hash_popup_token(token)
    with transaction.atomic():
        session = SLCMAutofillSession.objects.select_for_update().filter(
            popup_token_hash=token_hash,
            popup_opened_at__isnull=True,
            status=SLCMAutofillSession.Status.WAITING_LOGIN,
            expires_at__gt=timezone.now(),
        ).first()
        if session is None:
            return response(
                error={"code": "INVALID_POPUP_TOKEN", "message": "Popup token is invalid or expired."},
                status=status.HTTP_404_NOT_FOUND,
            )
        session.popup_opened_at = timezone.now()
        session.save(update_fields=["popup_opened_at", "updated_at"])
    target = (
        settings.SLCM_BROWSER_PUBLIC_URL.rstrip("/")
        + "/?autoconnect=1&resize=scale&show_dot=true"
    )
    return redirect(target)
