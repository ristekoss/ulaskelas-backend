import calendar
from datetime import date

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
import pytz

from main.models import Calculator, Notification, Profile, Review
from main.push_notifications import CALCULATOR_BODY, COURSE_REVIEW_BODY, create_notification


class Command(BaseCommand):
    help = "Send idempotent calculator or course-review reminders"

    def add_arguments(self, parser):
        parser.add_argument("--type", choices=("calculator", "review"), required=True)
        parser.add_argument(
            "--date",
            help="Override Asia/Jakarta date (YYYY-MM-DD), for operations/testing",
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
            created = self._calculator(current_date)
        else:
            last_day = calendar.monthrange(current_date.year, current_date.month)[1]
            if current_date.day != last_day:
                self.stdout.write(
                    "Skipped: {} is not the last day of the month".format(
                        current_date
                    )
                )
                return
            created = self._review(current_date)
        self.stdout.write(
            self.style.SUCCESS("Created {} notification(s)".format(created))
        )

    def _calculator(self, current_date):
        iso_year, iso_week, _ = current_date.isocalendar()
        profiles = Profile.objects.filter(calculator__isnull=False).distinct()
        created = 0
        for profile in profiles.iterator():
            item = create_notification(
                user=profile,
                notification_type=Notification.Type.CALCULATOR_REMINDER,
                title="Reminder Kalkulator",
                body=CALCULATOR_BODY,
                target=Notification.Target.GRADE_CALCULATOR,
                dedupe_key="calculator:{}-{:02d}".format(iso_year, iso_week),
            )
            created += item is not None
        return created

    def _review(self, current_date):
        profiles = Profile.objects.filter(calculator__isnull=False).distinct()
        created = 0
        for profile in profiles.iterator():
            course_ids = Calculator.objects.filter(user=profile).values_list(
                "course_id", flat=True
            )
            reviewed_ids = Review.objects.filter(
                user=profile, is_active=True
            ).values_list("course_id", flat=True)
            if not course_ids.exclude(course_id__in=reviewed_ids).exists():
                continue
            item = create_notification(
                user=profile,
                notification_type=Notification.Type.COURSE_REVIEW_REMINDER,
                title="Reminder Course Review",
                body=COURSE_REVIEW_BODY,
                target=Notification.Target.COURSE_REVIEW,
                dedupe_key="course-review-monthly:{:%Y-%m}".format(current_date),
            )
            created += item is not None
        return created
