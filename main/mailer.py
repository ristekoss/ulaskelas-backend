import logging
from urllib.parse import urljoin

import requests
from django.conf import settings
from django.core.mail import send_mail
from requests.auth import HTTPBasicAuth

logger = logging.getLogger(__name__)


def send_notification_email(subject: str, message: str) -> None:
    if settings.USE_RISTEK_MAILER:
        _send_via_ristek_mailer(subject, message)
        return

    send_mail(
        subject=subject,
        message=message,
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=settings.NOTIFICATION_RECIPIENT_EMAILS,
        fail_silently=False,
    )


def _send_via_ristek_mailer(subject: str, message: str) -> None:
    if not settings.MAILER_BASE_URL:
        raise RuntimeError("MAILER_BASE_URL is empty while USE_RISTEK_MAILER=true")
    if not settings.MAILER_AUTH_TOKEN:
        raise RuntimeError("MAILER_AUTH_TOKEN is empty while USE_RISTEK_MAILER=true")
    if not settings.NOTIFICATION_RECIPIENT_EMAILS:
        raise RuntimeError("NOTIFICATION_RECIPIENT_EMAILS is empty")

    endpoint = urljoin(settings.MAILER_BASE_URL.rstrip("/") + "/", "send")
    payload = {
        "from_": settings.DEFAULT_FROM_EMAIL,
        "to": ",".join(settings.NOTIFICATION_RECIPIENT_EMAILS),
        "subject": subject,
        "body": message,
    }

    response = requests.post(
        endpoint,
        data=payload,
        auth=HTTPBasicAuth(settings.MAILER_BASIC_USER, settings.MAILER_AUTH_TOKEN),
        timeout=settings.MAILER_TIMEOUT_SECONDS,
    )
    if response.status_code >= 400:
        logger.error(
            "ristek-mailer failed status=%s body=%s",
            response.status_code,
            response.text[:500],
        )
        raise RuntimeError(f"ristek-mailer request failed: {response.status_code}")
