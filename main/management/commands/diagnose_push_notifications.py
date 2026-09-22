from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from main.models import Calculator, DeviceToken, Notification, Profile, Review


class Command(BaseCommand):
    help = "Report push-notification eligibility and configuration without exposing secrets"

    def add_arguments(self, parser):
        parser.add_argument("--username", required=True)

    def handle(self, *args, **options):
        profile = Profile.objects.filter(
            username__iexact=options["username"].strip()
        ).first()
        if profile is None:
            raise CommandError("Profile was not found.")

        calculator_course_ids = Calculator.objects.filter(user=profile).values_list(
            "course_id", flat=True
        )
        reviewed_course_ids = Review.objects.filter(
            user=profile,
            is_active=True,
            course_id__in=calculator_course_ids,
        ).values_list("course_id", flat=True)
        devices = DeviceToken.objects.filter(user=profile)
        notifications = Notification.objects.filter(user=profile)

        self.stdout.write("Profile: {} (id={})".format(profile.username, profile.id))
        self.stdout.write("Calculators: {}".format(calculator_course_ids.count()))
        self.stdout.write("Reviewed calculator courses: {}".format(reviewed_course_ids.count()))
        self.stdout.write(
            "Unreviewed calculator courses: {}".format(
                calculator_course_ids.exclude(course_id__in=reviewed_course_ids).count()
            )
        )
        self.stdout.write(
            "Device tokens: total={}, active={}, android={}, ios={}".format(
                devices.count(),
                devices.filter(is_active=True).count(),
                devices.filter(is_active=True, platform=DeviceToken.Platform.ANDROID).count(),
                devices.filter(is_active=True, platform=DeviceToken.Platform.IOS).count(),
            )
        )
        self.stdout.write(
            "Notifications: total={}, unread={}, calculator={}, review={}".format(
                notifications.count(),
                notifications.filter(read_at__isnull=True).count(),
                notifications.filter(type=Notification.Type.CALCULATOR_REMINDER).count(),
                notifications.filter(type=Notification.Type.COURSE_REVIEW_REMINDER).count(),
            )
        )
        credential_source = (
            "base64_service_account"
            if getattr(settings, "FIREBASE_CREDENTIALS_BASE64", "")
            else "application_default_credentials"
        )
        self.stdout.write(
            "Firebase: enabled={}, credential_source={}".format(
                bool(getattr(settings, "FIREBASE_ENABLED", False)),
                credential_source,
            )
        )
