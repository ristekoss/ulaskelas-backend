import getpass

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from main.integrations.slcm_client import SLCMClient, SLCMError
from main.integrations.slcm_irs import import_courses, resolve_courses
from main.models import CourseSemester, Profile


class Command(BaseCommand):
    help = "Import the authenticated user's current SLCM course plan."

    def add_arguments(self, parser):
        parser.add_argument("--username", required=True)
        parser.add_argument("--semester", required=True)
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show the import preview without changing the database.",
        )
        parser.add_argument(
            "--yes",
            action="store_true",
            help="Apply without the final interactive confirmation.",
        )

    def handle(self, *args, **options):
        username = options["username"].strip()
        profile = Profile.objects.filter(username__iexact=username).first()
        if profile is None:
            raise CommandError(
                "Profile with username={} was not found.".format(username)
            )
        password = getpass.getpass("SSO UI password: ")
        if not password:
            raise CommandError("SSO password must not be empty.")

        try:
            history = SLCMClient(
                timeout=settings.SLCM_REQUEST_TIMEOUT_SECONDS,
                retries=settings.SLCM_REQUEST_RETRIES,
            ).fetch_course_plan(username, password)
        except SLCMError as exc:
            raise CommandError(str(exc)) from exc
        finally:
            password = None

        if history["username"].casefold() != profile.username.casefold():
            raise CommandError(
                "The authenticated SSO account does not match the target profile."
            )
        resolved, unmatched = resolve_courses(history["courses"])
        existing_codes = set(
            CourseSemester.objects.filter(
                semester__userCumulativeGPA__user=profile,
                semester__given_semester=str(options["semester"]),
                course__in=resolved,
            ).values_list("course__code", flat=True)
        )
        self._print_preview(
            profile,
            options["semester"],
            history["period"],
            resolved,
            unmatched,
            existing_codes,
            history["warning_stale_data"],
        )
        if options["dry_run"]:
            self.stdout.write(self.style.WARNING("Dry run: no data was changed."))
            return
        if not resolved:
            raise CommandError(
                "None of the SLCM course codes exist in the local course catalog."
            )
        if not options["yes"]:
            answer = input("Import these courses into the local database? [y/N] ")
            if answer.strip().casefold() not in {"y", "yes"}:
                self.stdout.write(self.style.WARNING("Import cancelled."))
                return

        result = import_courses(profile, options["semester"], resolved)
        self.stdout.write(
            self.style.SUCCESS(
                "Import complete: {} inserted, {} already present, {} unmatched.".format(
                    len(result["inserted"]),
                    len(result["duplicates"]),
                    len(unmatched),
                )
            )
        )

    def _print_preview(
        self,
        profile,
        semester,
        source_period,
        resolved,
        unmatched,
        existing_codes,
        warning_stale_data,
    ):
        self.stdout.write(
            "Target: {} ({}) — calculator semester {} — SLCM period {}".format(
                profile.name, profile.username, semester, source_period
            )
        )
        if warning_stale_data:
            self.stdout.write(
                self.style.WARNING(
                    "SLCM warns that this course-plan data may be stale."
                )
            )
        self.stdout.write("Recognized local courses:")
        for course in resolved:
            marker = " [already present]" if course.code in existing_codes else ""
            self.stdout.write(
                "  {} — {} ({} SKS){}".format(
                    course.code, course.name, course.sks, marker
                )
            )
        if unmatched:
            self.stdout.write(self.style.WARNING("Unmatched SLCM courses:"))
            for course in unmatched:
                self.stdout.write(
                    "  {} — {} ({} SKS)".format(
                        course["code"], course["name"], course["credits"]
                    )
                )
