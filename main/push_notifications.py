import base64
import json
import logging

from django.conf import settings
from django.db import IntegrityError, transaction

from .models import DeviceToken, Notification, Review

logger = logging.getLogger(__name__)

CALCULATOR_BODY = "Sudah update nilai kamu minggu ini?"
COURSE_REVIEW_BODY = "Bagikan pengalamanmu! Tulis ulasan matkul semester ini"


def _firebase_messaging():
    if not getattr(settings, "FIREBASE_ENABLED", False):
        return None
    try:
        import firebase_admin
        from firebase_admin import credentials, messaging

        if not firebase_admin._apps:
            encoded = getattr(settings, "FIREBASE_CREDENTIALS_BASE64", "")
            if encoded:
                info = json.loads(base64.b64decode(encoded).decode("utf-8"))
                firebase_admin.initialize_app(credentials.Certificate(info))
            else:
                firebase_admin.initialize_app()
        return messaging
    except Exception:
        logger.exception("Failed to initialize Firebase Admin")
        return None


def unread_count(user):
    return Notification.objects.filter(user=user, read_at__isnull=True).count()


def send_push(notification):
    messaging = _firebase_messaging()
    if messaging is None:
        logger.warning(
            "Push skipped notification=%s reason=firebase_unavailable",
            notification.id,
        )
        return
    devices = list(DeviceToken.objects.filter(user=notification.user, is_active=True))
    if not devices:
        logger.warning(
            "Push skipped notification=%s user=%s reason=no_active_device",
            notification.id,
            notification.user_id,
        )
        return

    data = {
        "notification_id": str(notification.id),
        "type": notification.type,
        "target": notification.target,
        "badge": str(unread_count(notification.user)),
    }
    if notification.course_id:
        data["course_id"] = str(notification.course_id)

    message = messaging.MulticastMessage(
        tokens=[device.token for device in devices],
        notification=messaging.Notification(
            title=notification.title, body=notification.body
        ),
        data=data,
        android=messaging.AndroidConfig(
            notification=messaging.AndroidNotification(
                notification_count=int(data["badge"])
            )
        ),
        apns=messaging.APNSConfig(
            payload=messaging.APNSPayload(
                aps=messaging.Aps(badge=int(data["badge"]))
            )
        ),
    )
    try:
        result = messaging.send_each_for_multicast(message)
    except Exception:
        logger.exception("Failed to send notification id=%s", notification.id)
        return

    invalid_codes = {"registration-token-not-registered", "invalid-registration-token"}
    invalid_ids = []
    for device, response in zip(devices, result.responses):
        if response.success:
            continue
        code = str(getattr(response.exception, "code", "") or "")
        if any(invalid_code in code for invalid_code in invalid_codes):
            invalid_ids.append(device.id)
        logger.warning(
            "FCM delivery failed notification=%s device=%s code=%s",
            notification.id,
            device.id,
            code,
        )
    if invalid_ids:
        DeviceToken.objects.filter(id__in=invalid_ids).update(is_active=False)
    logger.info(
        "Push completed notification=%s devices=%s success=%s failure=%s invalidated=%s",
        notification.id,
        len(devices),
        result.success_count,
        result.failure_count,
        len(invalid_ids),
    )


def create_notification(
    *, user, notification_type, title, body, target, dedupe_key, course=None
):
    try:
        with transaction.atomic():
            notification = Notification.objects.create(
                user=user,
                type=notification_type,
                title=title,
                body=body,
                target=target,
                course=course,
                dedupe_key=dedupe_key,
            )
    except IntegrityError:
        logger.info(
            "Notification deduplicated user=%s key=%s",
            user.id,
            dedupe_key,
        )
        return None
    logger.info(
        "Notification created id=%s user=%s type=%s key=%s",
        notification.id,
        user.id,
        notification_type,
        dedupe_key,
    )
    transaction.on_commit(lambda: send_push(notification))
    return notification


def remind_course_review_after_grade_edit(calculator):
    if Review.objects.filter(
        user=calculator.user, course=calculator.course, is_active=True
    ).exists():
        logger.info(
            "Course-review reminder skipped user=%s course=%s reason=active_review",
            calculator.user_id,
            calculator.course_id,
        )
        return None
    return create_notification(
        user=calculator.user,
        notification_type=Notification.Type.COURSE_REVIEW_REMINDER,
        title="Reminder Course Review",
        body=COURSE_REVIEW_BODY,
        target=Notification.Target.COURSE_REVIEW,
        course=calculator.course,
        dedupe_key="course-review-edit:{}".format(calculator.course_id),
    )
