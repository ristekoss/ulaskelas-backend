from django.core.management.base import BaseCommand, CommandError

from main.integrations.siak_irs import (
    IRSParseError,
    collect_page_tables,
    import_courses,
    parse_irs_tables,
    resolve_courses,
)
from main.models import CourseSemester, Profile


DEFAULT_SIAK_URL = "https://academic.ui.ac.id/"


class Command(BaseCommand):
    help = (
        "Open a temporary browser session and import the active SIAK IRS into "
        "a local calculator semester."
    )

    def add_arguments(self, parser):
        parser.add_argument("--username", required=True)
        parser.add_argument("--semester", required=True)
        parser.add_argument("--siak-url", default=DEFAULT_SIAK_URL)
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
        profile = Profile.objects.filter(
            username__iexact=options["username"]
        ).first()
        if profile is None:
            raise CommandError(
                "Profile with username={} was not found.".format(options["username"])
            )

        scraped_courses = self._scrape(options["siak_url"])
        resolved, unmatched = resolve_courses(scraped_courses)
        existing_codes = set(
            CourseSemester.objects.filter(
                semester__userCumulativeGPA__user=profile,
                semester__given_semester=str(options["semester"]),
                course__in=resolved,
            ).values_list("course__code", flat=True)
        )

        self._print_preview(
            profile=profile,
            semester=options["semester"],
            resolved=resolved,
            unmatched=unmatched,
            existing_codes=existing_codes,
        )
        if options["dry_run"]:
            self.stdout.write(self.style.WARNING("Dry run: no data was changed."))
            return
        if not resolved:
            raise CommandError(
                "None of the SIAK course codes exist in the local course catalog."
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

    def _scrape(self, siak_url):
        try:
            from playwright.sync_api import Error as PlaywrightError
            from playwright.sync_api import sync_playwright
        except ImportError as exc:
            raise CommandError(
                "Playwright is not installed. Install dependencies and run "
                "`python -m playwright install chromium`."
            ) from exc

        try:
            with sync_playwright() as playwright:
                browser = playwright.chromium.launch(headless=False)
                context = browser.new_context()
                try:
                    page = context.new_page()
                    page.goto(siak_url, wait_until="domcontentloaded")
                    self.stdout.write(
                        "Complete the SIAK challenge/login, open the active IRS "
                        "page, then return here."
                    )
                    input("Press Enter when the IRS table is visible... ")
                    tables = []
                    for frame in list(page.frames):
                        try:
                            tables.extend(collect_page_tables(frame))
                        except PlaywrightError as exc:
                            if frame.is_detached() or "Frame was detached" in str(exc):
                                continue
                            raise
                    return parse_irs_tables(tables)
                finally:
                    context.close()
                    browser.close()
        except IRSParseError as exc:
            raise CommandError(str(exc)) from exc
        except PlaywrightError as exc:
            raise CommandError("SIAK browser session failed: {}".format(exc)) from exc

    def _print_preview(
        self, profile, semester, resolved, unmatched, existing_codes
    ):
        self.stdout.write(
            "Target: {} ({}) — semester {}".format(
                profile.name, profile.username, semester
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
            self.stdout.write(self.style.WARNING("Unmatched SIAK courses:"))
            for course in unmatched:
                self.stdout.write(
                    "  {} — {} ({} SKS)".format(
                        course["code"], course["name"], course["credits"]
                    )
                )
