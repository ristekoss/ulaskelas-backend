from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import api_view

from .models import DeviceToken, Notification, Profile
from .push_notifications import unread_count
from .utils import get_paged_obj, response, response_paged, validate_body


def _user(request):
    return Profile.objects.get(username=str(request.user))


def _serialize(item):
    return {
        "id": item.id,
        "type": item.type,
        "title": item.title,
        "body": item.body,
        "target": item.target,
        "course_id": item.course_id,
        "is_read": item.read_at is not None,
        "created_at": item.created_at,
    }


@api_view(["POST", "DELETE"])
def device_token(request):
    user = _user(request)
    error = validate_body(request, ["token"])
    if error is not None:
        return error
    token = request.data["token"]
    if request.method == "DELETE":
        DeviceToken.objects.filter(user=user, token=token).update(is_active=False)
        return response(status=status.HTTP_204_NO_CONTENT)

    error = validate_body(request, ["platform"])
    if error is not None:
        return error
    platform = request.data["platform"]
    if platform not in (DeviceToken.Platform.ANDROID, DeviceToken.Platform.IOS):
        return response(
            error="platform must be android or ios",
            status=status.HTTP_400_BAD_REQUEST,
        )
    device, _ = DeviceToken.objects.update_or_create(
        token=token, defaults={"user": user, "platform": platform, "is_active": True}
    )
    return response(data={"id": device.id}, status=status.HTTP_200_OK)


@api_view(["GET"])
def notifications(request):
    user = _user(request)
    items, total_page = get_paged_obj(
        Notification.objects.filter(user=user)
        .select_related("course")
        .order_by("-created_at"),
        request.query_params.get("page", 1),
        _sort_by_id=False,
    )
    return response_paged(
        data={
            "notifications": [_serialize(item) for item in items],
            "unread_count": unread_count(user),
        },
        total_page=total_page,
    )


@api_view(["GET"])
def notification_unread_count(request):
    return response(data={"unread_count": unread_count(_user(request))})


@api_view(["POST"])
def notification_read(request, notification_id):
    user = _user(request)
    item = Notification.objects.filter(user=user, id=notification_id).first()
    if item is None:
        return response(
            error="Notification not found", status=status.HTTP_404_NOT_FOUND
        )
    if item.read_at is None:
        item.read_at = timezone.now()
        item.save(update_fields=["read_at"])
    return response(data={"unread_count": unread_count(user)})


@api_view(["POST"])
def notifications_read_all(request):
    user = _user(request)
    Notification.objects.filter(user=user, read_at__isnull=True).update(
        read_at=timezone.now()
    )
    return response(data={"unread_count": 0})
