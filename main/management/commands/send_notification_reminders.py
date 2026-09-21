import calendar
from datetime import date

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
import pytz

from main.models import Calculator, DeviceToken, Notification, Profile, Review
from main.push_notifications import CALCULATOR_BODY, COURSE_REVIEW_BODY, create_notification


class Command(BaseCommand):
    help = "Send idempotent calculator or course-review reminders"

    def add_arguments(self, parser):
        parser.add_argument("--type", choices=("calculator", "review"), required=True)
        parser.add_argument(
            "--date",
            help="Override Asia/Jakarta date (YYYY-MM-DD), for operations/testing",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Report eligible recipients without creating notifications or sending push messages",
        )

    def handle(self, *args, **options):
        try:
            current_date = (
                date.fromisoformat(options["date"])
                if options["date"]
                else timezone.now().astimezone(pytz.timezone("Asia/Jakarta")).date()
            )
        except ValueError as exc:
            raise CommandError("--date must use YYYY-MM-DD") from exc

        if options["type"] == "calculator":
            result = self._calculator(current_date, options["dry_run"])
        else:
            last_day = calendar.monthrange(current_date.year, current_date.month)[1]
            if current_date.day != last_day:
                self.stdout.write(
                    "Skipped: {} is not the last day of the month".format(
                        current_date
                    )
                )
                return
            result = self._review(current_date, options["dry_run"])
        self.stdout.write(
            self.style.SUCCESS(
                "{}: eligible={}, active_devices={}, created={}, deduplicated={}".format(
                    "Dry run" if options["dry_run"] else "Completed",
                    result["eligible"],
                    result["active_devices"],
                    result["created"],
                    result["deduplicated"],
                )
            )
        )

    @staticmethod
    def _result():
        return {"eligible": 0, "active_devices": 0, "created": 0, "deduplicated": 0}

    @staticmethod
    def _active_device_count(profile):
        return DeviceToken.objects.filter(user=profile, is_active=True).count()

    def _calculator(self, current_date, dry_run=False):
        iso_year, iso_week, _ = current_date.isocalendar()
        profiles = Profile.objects.filter(calculator__isnull=False).distinct()
        result = self._result()
        dedupe_key = "calculator:{}-{:02d}".format(iso_year, iso_week)
        for profile in profiles.iterator():
            result["eligible"] += 1
            result["active_devices"] += self._active_device_count(profile)
            if Notification.objects.filter(user=profile, dedupe_key=dedupe_key).exists():
                result["deduplicated"] += 1
                continue
            if dry_run:
                result["created"] += 1
                continue
            item = create_notification(
                user=profile,
                notification_type=Notification.Type.CALCULATOR_REMINDER,
                title="Reminder Kalkulator",
                body=CALCULATOR_BODY,
                target=Notification.Target.GRADE_CALCULATOR,
                dedupe_key=dedupe_key,
            )
            result["created"] += item is not None
            result["deduplicated"] += item is None
        return result

    def _review(self, current_date, dry_run=False):
        profiles = Profile.objects.filter(calculator__isnull=False).distinct()
        result = self._result()
        dedupe_key = "course-review-monthly:{:%Y-%m}".format(current_date)
        for profile in profiles.iterator():
            course_ids = Calculator.objects.filter(user=profile).values_list(
                "course_id", flat=True
            )
            reviewed_ids = Review.objects.filter(
                user=profile, is_active=True
            ).values_list("course_id", flat=True)
            if not course_ids.exclude(course_id__in=reviewed_ids).exists():
                continue
            result["eligible"] += 1
            result["active_devices"] += self._active_device_count(profile)
            if Notification.objects.filter(user=profile, dedupe_key=dedupe_key).exists():
                result["deduplicated"] += 1
                continue
            if dry_run:
                result["created"] += 1
                continue
            item = create_notification(
                user=profile,
                notification_type=Notification.Type.COURSE_REVIEW_REMINDER,
                title="Reminder Course Review",
                body=COURSE_REVIEW_BODY,
                target=Notification.Target.COURSE_REVIEW,
                dedupe_key=dedupe_key,
            )
            result["created"] += item is not None
            result["deduplicated"] += item is None
        return result
