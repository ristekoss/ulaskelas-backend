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
    """Raised when the SLCM IRS table cannot be recognized."""


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
    "period": {
        "academic period",
        "academic term",
        "periode",
        "periode akademik",
        "semester",
        "tahun akademik",
        "tahun ajaran",
        "term",
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


def parse_latest_history(tables):
    """
    Return the latest non-empty academic period from browser-extracted tables.

    ``tables`` is a list of dictionaries containing ``headers`` and ``rows``.
    Keeping this parser independent of Playwright makes it safe to unit test
    without a live SLCM session.
    """
    courses_by_period = {}
    active_period_courses = []
    observed_headers = []
    for table in tables:
        headers = table.get("headers") or []
        observed_headers.append([normalize_header(value) for value in headers])
        indexes = _column_indexes(headers)
        if not {"code", "name", "credits"}.issubset(indexes):
            continue

        if "period" in indexes:
            for period_label, courses in _parse_period_column(table, indexes).items():
                courses_by_period.setdefault(period_label, []).extend(courses)
            continue

        if any(
            _normalize_period_label(period)
            for period in table.get("row_periods") or []
        ):
            for period_label, courses in _parse_row_periods(table, indexes).items():
                courses_by_period.setdefault(period_label, []).extend(courses)
            continue

        period_label = _normalize_period_label(table.get("period_label"))
        if period_label is not None:
            courses_by_period.setdefault(period_label, []).extend(
                _parse_candidate(table, indexes)
            )
        else:
            active_period_courses.extend(_parse_candidate(table, indexes))

    if not any(
        {"code", "name", "credits"}.issubset(_column_indexes(table.get("headers") or []))
        for table in tables
    ):
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

    non_empty_periods = {
        label: _deduplicate_courses(courses)
        for label, courses in courses_by_period.items()
        if courses
    }
    if not non_empty_periods and active_period_courses:
        return {
            "period": "Periode Aktif SLCM",
            "courses": _deduplicate_courses(active_period_courses),
        }
    if not non_empty_periods:
        raise IRSParseError(
            "Course tables were found, but their academic periods could not be "
            "recognized or did not contain valid courses."
        )

    try:
        period_label = max(non_empty_periods, key=_period_sort_key)
    except ValueError as exc:
        raise IRSParseError(
            "Academic period labels were found but could not be ordered."
        ) from exc
    return {
        "period": period_label,
        "courses": non_empty_periods[period_label],
    }


def _parse_period_column(table, indexes):
    courses_by_period = {}
    maximum_index = max(indexes.values())
    for row in table.get("rows") or []:
        if len(row) <= maximum_index:
            continue
        period_label = _normalize_period_label(row[indexes["period"]])
        course = _parse_course_row(row, indexes)
        if period_label is not None and course is not None:
            courses_by_period.setdefault(period_label, []).append(course)
    return courses_by_period


def _parse_row_periods(table, indexes):
    courses_by_period = {}
    row_periods = table.get("row_periods") or []
    maximum_index = max(indexes.values())
    for row_index, row in enumerate(table.get("rows") or []):
        if len(row) <= maximum_index or row_index >= len(row_periods):
            continue
        period_label = _normalize_period_label(row_periods[row_index])
        course = _parse_course_row(row, indexes)
        if period_label is not None and course is not None:
            courses_by_period.setdefault(period_label, []).append(course)
    return courses_by_period


def _parse_candidate(table, indexes):
    courses = []
    maximum_index = max(indexes.values())
    for row in table.get("rows") or []:
        if len(row) <= maximum_index:
            continue
        course = _parse_course_row(row, indexes)
        if course is not None:
            courses.append(course)
    return _deduplicate_courses(courses)


def _parse_course_row(row, indexes):
    code = normalize_course_code(row[indexes["code"]])
    name = " ".join(str(row[indexes["name"]] or "").split())
    credits_text = str(row[indexes["credits"]] or "").strip()
    credits_match = re.search(r"\d+", credits_text)
    if not code or not name or credits_match is None:
        return None
    return {
        "code": code,
        "name": name,
        "credits": int(credits_match.group()),
    }


def _deduplicate_courses(courses):
    unique_courses = []
    seen_codes = set()
    for course in courses:
        if course["code"] not in seen_codes:
            seen_codes.add(course["code"])
            unique_courses.append(course)
    return unique_courses


def _normalize_period_label(value):
    label = " ".join(str(value or "").split())
    return label or None


def _period_sort_key(label):
    normalized = normalize_header(label)
    year_range = re.search(r"\b(20\d{2})\s+(20\d{2})\b", normalized)
    if year_range:
        start_year = int(year_range.group(1))
    else:
        compact_period = re.search(r"\b(20\d{2})\s+([123])\b", normalized)
        if compact_period is None:
            raise ValueError("Unrecognized academic period: {}".format(label))
        start_year = int(compact_period.group(1))

    if re.search(r"\b(pendek|short|antara|term 3|semester 3)\b", normalized):
        term_rank = 3
    elif re.search(r"\b(genap|even|term 2|semester 2)\b", normalized):
        term_rank = 2
    elif re.search(r"\b(ganjil|gasal|odd|term 1|semester 1)\b", normalized):
        term_rank = 1
    else:
        trailing_term = re.search(r"\b([123])\s*$", normalized)
        if trailing_term is None:
            raise ValueError("Unrecognized academic term: {}".format(label))
        term_rank = int(trailing_term.group(1))
    return start_year, term_rank


def collect_page_tables(page):
    """Extract table text from the current page without persisting its DOM."""
    return page.evaluate(
        """
        () => Array.from(document.querySelectorAll("table")).map((table) => {
          const allRows = Array.from(table.querySelectorAll("tr")).filter(
            (row) => row.closest("table") === table
          );
          if (allRows.length === 0) {
            return {headers: [], rows: []};
          }

          let headers = Array.from(
            table.querySelectorAll("thead th")
          ).filter(
            (cell) => cell.closest("table") === table
          ).map((cell) => cell.innerText.trim());
          let bodyRows = Array.from(table.querySelectorAll("tbody tr")).filter(
            (row) => row.closest("table") === table
          );

          if (headers.length === 0) {
            headers = Array.from(allRows[0].children).filter(
              (cell) => ["TH", "TD"].includes(cell.tagName)
            ).map((cell) => cell.innerText.trim());
            bodyRows = allRows.slice(1);
          } else if (bodyRows.length === 0) {
            const headerRow = table.querySelector("thead tr");
            bodyRows = allRows.filter((row) => row !== headerRow);
          }

          const caption = table.querySelector("caption");
          let periodLabel = caption ? caption.innerText.trim() : "";
          if (!periodLabel) {
            let sibling = table.previousElementSibling;
            for (let index = 0; sibling && index < 5; index += 1) {
              const text = sibling.innerText ? sibling.innerText.trim() : "";
              if (text && /20\\d{2}/.test(text)) {
                periodLabel = text;
                break;
              }
              sibling = sibling.previousElementSibling;
            }
          }

          const rows = [];
          const rowPeriods = [];
          let currentPeriod = periodLabel;
          bodyRows.forEach((row) => {
            const cells = Array.from(row.children).filter(
              (cell) => ["TH", "TD"].includes(cell.tagName)
            );
            const values = cells.map((cell) => cell.innerText.trim());
            if (
              values.length === 1 &&
              /Tahun Ajaran\\s+20\\d{2}\\s*\\/\\s*20\\d{2}\\s+Term\\s+[123]/i.test(
                values[0]
              )
            ) {
              currentPeriod = values[0];
              return;
            }
            rows.push(values);
            rowPeriods.push(currentPeriod);
          });

          return {
            headers,
            period_label: periodLabel,
            row_periods: rowPeriods,
            rows,
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
    if not courses:
        raise ValueError("At least one resolved course is required.")

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
