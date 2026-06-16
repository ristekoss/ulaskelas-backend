import logging

import environ
from django.conf import settings
from django.core.mail import send_mail
from django.urls import reverse

logger = logging.getLogger(__name__)
env = environ.Env()


def build_admin_change_url(model_name, object_id, legacy_link_env=None):
    admin_base_url = env("ULASKELAS_ADMIN_LINK", default="").rstrip("/")
    legacy_link = env(legacy_link_env, default="") if legacy_link_env else ""

    if legacy_link:
        return f"{admin_base_url}/?next={legacy_link}/{object_id}/change/"

    admin_path = reverse(f"admin:main_{model_name}_change", args=[object_id])
    if admin_base_url:
        return f"{admin_base_url}{admin_path}"
    return admin_path


def send_submission_notification(subject, message, event_type, object_id):
    recipients = settings.NOTIFICATION_RECIPIENT_EMAILS
    if not recipients:
        logger.warning(
            "Skipping submission notification because recipient list is empty. "
            "event_type=%s object_id=%s",
            event_type,
            object_id,
        )
        return False

    try:
        send_mail(
            subject=subject,
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=recipients,
            fail_silently=False,
        )
        return True
    except Exception:
        logger.exception(
            "Failed to send submission notification. event_type=%s object_id=%s recipients=%s",
            event_type,
            object_id,
            recipients,
        )
        return False
