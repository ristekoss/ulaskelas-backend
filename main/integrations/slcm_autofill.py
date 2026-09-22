import logging
import threading
from datetime import timedelta

from django.conf import settings
from django.db import close_old_connections
from django.utils import timezone

from main.integrations.slcm_client import SLCMClient, SLCMError
from main.integrations.slcm_irs import resolve_courses
from main.models import CourseSemester, SLCMAutofillSession


logger = logging.getLogger(__name__)


def expire_stale_sessions():
    SLCMAutofillSession.objects.filter(
        status__in=[
            SLCMAutofillSession.Status.WAITING_LOGIN,
            SLCMAutofillSession.Status.SCRAPING,
            SLCMAutofillSession.Status.READY,
        ],
        expires_at__lte=timezone.now(),
    ).update(status=SLCMAutofillSession.Status.EXPIRED)


def start_scraper(session_id, username, password):
    thread = threading.Thread(
        target=_fetch_session,
        args=(str(session_id), username, password),
        daemon=True,
    )
    thread.start()


def _fetch_session(session_id, username, password):
    close_old_connections()
    try:
        session = SLCMAutofillSession.objects.get(pk=session_id)
        if session.status != SLCMAutofillSession.Status.WAITING_LOGIN:
            return
        SLCMAutofillSession.objects.filter(
            pk=session_id, status=SLCMAutofillSession.Status.WAITING_LOGIN
        ).update(status=SLCMAutofillSession.Status.SCRAPING)

        client = SLCMClient(
            timeout=settings.SLCM_REQUEST_TIMEOUT_SECONDS,
            retries=settings.SLCM_REQUEST_RETRIES,
        )
        history = client.fetch_course_plan(username, password)
        session = SLCMAutofillSession.objects.get(pk=session_id)
        if session.status in {
            SLCMAutofillSession.Status.CANCELLED,
            SLCMAutofillSession.Status.EXPIRED,
        }:
            return
        if history["username"].casefold() != session.user.username.casefold():
            _fail(
                session_id,
                "IDENTITY_MISMATCH",
                "The authenticated SSO account does not match the target profile.",
            )
            return

        resolved, unmatched = resolve_courses(history["courses"])
        existing_ids = set(
            CourseSemester.objects.filter(
                semester__userCumulativeGPA__user=session.user,
                semester__given_semester=session.given_semester,
                course_id__in=[course.id for course in resolved],
            ).values_list("course_id", flat=True)
        )
        matched, duplicates = [], []
        for course in resolved:
            item = {
                "id": course.id,
                "code": course.code,
                "name": course.name,
                "sks": course.sks,
            }
            (duplicates if course.id in existing_ids else matched).append(item)
        SLCMAutofillSession.objects.filter(
            pk=session_id, status=SLCMAutofillSession.Status.SCRAPING
        ).update(
            status=SLCMAutofillSession.Status.READY,
            source_period=history["period"],
            preview={
                "matched": matched,
                "duplicates": duplicates,
                "unmatched": unmatched,
                "warning_stale_data": history["warning_stale_data"],
            },
            error=None,
            expires_at=timezone.now()
            + timedelta(seconds=settings.SLCM_AUTOFILL_TIMEOUT_SECONDS),
        )
    except SLCMError as exc:
        _fail(session_id, exc.code, str(exc))
    except Exception:
        logger.exception("SLCM autofill session %s failed", session_id)
        _fail(session_id, "SLCM_ERROR", "The SLCM import failed unexpectedly.")
    finally:
        password = None
        close_old_connections()


def _fail(session_id, code, message):
    SLCMAutofillSession.objects.filter(
        pk=session_id,
        status__in=[
            SLCMAutofillSession.Status.WAITING_LOGIN,
            SLCMAutofillSession.Status.SCRAPING,
        ],
    ).update(
        status=SLCMAutofillSession.Status.FAILED,
        error={"code": code, "message": message},
    )
