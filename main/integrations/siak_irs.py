import re
import unicodedata

from django.db import transaction

from main.models import Calculator, Course, CourseSemester, UserGPA
from main.utils import (
    add_course_to_semester,
    add_semester_gpa,
    check_notexist_and_create_user_cumulative_gpa,
)


class IRSParseError(ValueError):
    """Raised when the active IRS table cannot be recognized."""


HEADER_ALIASES = {
    "code": {
        "code",
        "course code",
        "kode",
        "kode mata kuliah",
        "kode matakuliah",
        "kode mk",
    },
    "name": {
        "course",
        "course name",
        "mata kuliah",
        "matakuliah",
        "nama",
        "nama mata kuliah",
        "nama matakuliah",
        "nama mk",
    },
    "credits": {
        "credit",
        "credits",
        "credit units",
        "jumlah sks",
        "sks",
    },
}


def normalize_header(value):
    value = unicodedata.normalize("NFKC", str(value or "")).casefold()
    value = re.sub(r"[^a-z0-9]+", " ", value)
    return " ".join(value.split())


def normalize_course_code(value):
    value = unicodedata.normalize("NFKC", str(value or "")).upper()
    return re.sub(r"\s+", "", value)


def _column_indexes(headers):
    normalized = [normalize_header(header) for header in headers]
    indexes = {}
    for field, aliases in HEADER_ALIASES.items():
        for index, header in enumerate(normalized):
            if header in aliases:
                indexes[field] = index
                break
    return indexes


def parse_irs_tables(tables):
    """
    Parse browser-extracted tables and return unique active-IRS courses.

    ``tables`` is a list of dictionaries containing ``headers`` and ``rows``.
    Keeping this parser independent of Playwright makes it safe to unit test
    without a live SIAK session.
    """
    candidates = []
    observed_headers = []
    for table in tables:
        headers = table.get("headers") or []
        observed_headers.append([normalize_header(value) for value in headers])
        indexes = _column_indexes(headers)
        if {"code", "name", "credits"}.issubset(indexes):
            candidates.append((table, indexes))

    if not candidates:
        readable_headers = "; ".join(
            ", ".join(headers) for headers in observed_headers if headers
        )
        detail = (
            " Observed headers: {}.".format(readable_headers)
            if readable_headers
            else ""
        )
        raise IRSParseError(
            "Could not find an IRS table with course code, name, and SKS columns."
            + detail
        )

    parsed_candidates = [
        _parse_candidate(table, indexes) for table, indexes in candidates
    ]
    courses = max(parsed_candidates, key=len)
    if not courses:
        raise IRSParseError("The recognized IRS table does not contain valid courses.")
    return courses


def _parse_candidate(table, indexes):
    courses = []
    seen_codes = set()
    maximum_index = max(indexes.values())
    for row in table.get("rows") or []:
        if len(row) <= maximum_index:
            continue
        code = normalize_course_code(row[indexes["code"]])
        name = " ".join(str(row[indexes["name"]] or "").split())
        credits_text = str(row[indexes["credits"]] or "").strip()
        credits_match = re.search(r"\d+", credits_text)
        if not code or not name or credits_match is None or code in seen_codes:
            continue
        seen_codes.add(code)
        courses.append(
            {
                "code": code,
                "name": name,
                "credits": int(credits_match.group()),
            }
        )
    return courses


def collect_page_tables(page):
    """Extract table text from the current page without persisting its DOM."""
    return page.evaluate(
        """
        () => Array.from(document.querySelectorAll("table")).map((table) => {
          const allRows = Array.from(table.querySelectorAll("tr"));
          if (allRows.length === 0) {
            return {headers: [], rows: []};
          }

          let headers = Array.from(
            table.querySelectorAll("thead th")
          ).map((cell) => cell.innerText.trim());
          let bodyRows = Array.from(table.querySelectorAll("tbody tr"));

          if (headers.length === 0) {
            headers = Array.from(
              allRows[0].querySelectorAll("th, td")
            ).map((cell) => cell.innerText.trim());
            bodyRows = allRows.slice(1);
          }

          return {
            headers,
            rows: bodyRows.map((row) =>
              Array.from(row.querySelectorAll("th, td")).map(
                (cell) => cell.innerText.trim()
              )
            ),
          };
        })
        """
    )


def resolve_courses(scraped_courses):
    """Resolve scraped codes to local courses and report unmatched entries."""
    resolved = []
    unmatched = []
    seen_ids = set()
    for scraped_course in scraped_courses:
        code = normalize_course_code(scraped_course["code"])
        course = (
            Course.objects.filter(code__iexact=code)
            .order_by("-curriculum", "id")
            .first()
        )
        if course is None:
            unmatched.append(scraped_course)
            continue
        if course.id not in seen_ids:
            seen_ids.add(course.id)
            resolved.append(course)
    return resolved, unmatched


@transaction.atomic
def import_courses(profile, given_semester, courses):
    """Add resolved courses to one calculator semester atomically."""
    cumulative_gpa = check_notexist_and_create_user_cumulative_gpa(profile)
    semester, semester_created = UserGPA.objects.get_or_create(
        userCumulativeGPA=cumulative_gpa,
        given_semester=str(given_semester),
    )
    existing_ids = set(
        CourseSemester.objects.filter(
            semester=semester, course_id__in=[course.id for course in courses]
        ).values_list("course_id", flat=True)
    )
    inserted = []
    duplicates = []
    for course in courses:
        if course.id in existing_ids:
            duplicates.append(course)
            continue

        calculator = Calculator.objects.create(user=profile, course=course)
        CourseSemester.objects.create(
            semester=semester,
            course=course,
            calculator=calculator,
        )
        add_course_to_semester(semester=semester, sks=course.sks)
        add_semester_gpa(
            user_cumulative_gpa=cumulative_gpa,
            total_sks=course.sks,
            semester_gpa=0,
        )
        inserted.append(course)

    return {
        "semester": semester,
        "semester_created": semester_created,
        "inserted": inserted,
        "duplicates": duplicates,
    }
