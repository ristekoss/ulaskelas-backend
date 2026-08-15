from urllib.parse import urlparse

from django.core.management.base import BaseCommand, CommandError

from main.integrations.slcm_irs import (
    IRSParseError,
    collect_page_tables,
    import_courses,
    parse_latest_history,
    resolve_courses,
)
from main.models import CourseSemester, Profile


IRS_TABLE_MARKER = """
() => Array.from(document.querySelectorAll("table")).some((table) => {
  const normalize = (value) => (value || "")
    .normalize("NFKC")
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, " ")
    .trim();
  const firstRow = table.querySelector("thead tr") || table.querySelector("tr");
  if (!firstRow) return false;
  const headers = Array.from(firstRow.children).map((cell) =>
    normalize(cell.innerText)
  );
  const has = (aliases) => headers.some((header) => aliases.includes(header));
  const hasRequiredHeaders = has([
    "code", "course code", "kode", "kode mata kuliah", "kode matakuliah",
    "kode mk"
  ])
    && has([
      "course", "course name", "mata kuliah", "matakuliah", "nama",
      "nama mata kuliah", "nama matakuliah", "nama mk"
    ])
    && has(["credit", "credits", "credit units", "jumlah sks", "sks"]);
  if (!hasRequiredHeaders) return false;
  return Array.from(table.querySelectorAll("tr")).some((row) =>
    row !== firstRow && Array.from(row.children).some((cell) =>
      normalize(cell.innerText) !== ""
    )
  );
})
"""


class Command(BaseCommand):
    help = (
        "Open a temporary browser session and import the latest non-empty SLCM "
        "IRS period into a local calculator semester."
    )

    def add_arguments(self, parser):
        parser.add_argument("--username", required=True)
        parser.add_argument("--semester", required=True)
        parser.add_argument(
            "--irs-url",
            required=True,
            help="SLCM URL that displays the student's IRS.",
        )
        parser.add_argument(
            "--login-timeout",
            type=int,
            default=300,
            help="Seconds to wait for interactive SLCM login and IRS content.",
        )
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
        if options["login_timeout"] <= 0:
            raise CommandError("login-timeout must be greater than zero.")
        self._validate_irs_url(options["irs_url"])

        scraped_history = self._scrape(options["irs_url"], options["login_timeout"])
        scraped_courses = scraped_history["courses"]
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
            source_period=scraped_history["period"],
            resolved=resolved,
            unmatched=unmatched,
            existing_codes=existing_codes,
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

    @staticmethod
    def _validate_irs_url(irs_url):
        parsed_url = urlparse(irs_url)
        if parsed_url.scheme not in {"http", "https"} or not parsed_url.netloc:
            raise CommandError("irs-url must be a valid HTTP(S) URL.")

    def _scrape(self, irs_url, login_timeout):
        try:
            from playwright.sync_api import Error as PlaywrightError
            from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
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
                    page.goto(irs_url, wait_until="domcontentloaded")
                    self.stdout.write(
                        "Complete the SLCM login in the browser. The latest IRS "
                        "period will be read automatically."
                    )
                    page.wait_for_function(
                        IRS_TABLE_MARKER,
                        timeout=login_timeout * 1000,
                    )
                    tables = []
                    for frame in list(page.frames):
                        try:
                            tables.extend(collect_page_tables(frame))
                        except PlaywrightError as exc:
                            if frame.is_detached() or "Frame was detached" in str(exc):
                                continue
                            raise
                    return parse_latest_history(tables)
                finally:
                    context.close()
                    browser.close()
        except IRSParseError as exc:
            raise CommandError(str(exc)) from exc
        except PlaywrightTimeoutError as exc:
            raise CommandError(
                "Timed out waiting for SLCM login or IRS content."
            ) from exc
        except PlaywrightError as exc:
            raise CommandError(
                "SLCM browser session failed: {}".format(exc)
            ) from exc

    def _print_preview(
        self,
        profile,
        semester,
        source_period,
        resolved,
        unmatched,
        existing_codes,
    ):
        self.stdout.write(
            "Target: {} ({}) — calculator semester {} — SLCM period {}".format(
                profile.name, profile.username, semester, source_period
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
