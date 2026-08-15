import hashlib
import logging
import threading
from datetime import timedelta
from urllib.parse import urlparse

from django.conf import settings
from django.db import close_old_connections
from django.utils import timezone

from main.integrations.slcm_irs import IRSParseError, parse_latest_history, resolve_courses
from main.models import CourseSemester, SLCMAutofillSession


logger = logging.getLogger(__name__)

TABLE_EXTRACTOR = r"""
return Array.from(document.querySelectorAll("table")).map((table) => {
  const allRows = Array.from(table.querySelectorAll("tr")).filter(
    (row) => row.closest("table") === table
  );
  if (!allRows.length) return {headers: [], rows: []};
  let headers = Array.from(table.querySelectorAll("thead th"))
    .filter((cell) => cell.closest("table") === table)
    .map((cell) => cell.innerText.trim());
  let bodyRows = Array.from(table.querySelectorAll("tbody tr"))
    .filter((row) => row.closest("table") === table);
  if (!headers.length) {
    headers = Array.from(allRows[0].children).map((cell) => cell.innerText.trim());
    bodyRows = allRows.slice(1);
  } else if (!bodyRows.length) {
    const headerRow = table.querySelector("thead tr");
    bodyRows = allRows.filter((row) => row !== headerRow);
  }
  const caption = table.querySelector("caption");
  let periodLabel = caption ? caption.innerText.trim() : "";
  if (!periodLabel) {
    let sibling = table.previousElementSibling;
    for (let i = 0; sibling && i < 5; i += 1) {
      const text = sibling.innerText ? sibling.innerText.trim() : "";
      if (text && /20\d{2}/.test(text)) { periodLabel = text; break; }
      sibling = sibling.previousElementSibling;
    }
  }
  const rows = [], rowPeriods = [];
  let currentPeriod = periodLabel;
  bodyRows.forEach((row) => {
    const values = Array.from(row.children).map((cell) => cell.innerText.trim());
    if (values.length === 1 && /Tahun Ajaran\s+20\d{2}\s*\/\s*20\d{2}\s+Term\s+[123]/i.test(values[0])) {
      currentPeriod = values[0];
    } else {
      rows.push(values); rowPeriods.push(currentPeriod);
    }
  });
  return {headers, period_label: periodLabel, row_periods: rowPeriods, rows};
});
"""


def hash_popup_token(token):
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def validate_slcm_url():
    url = settings.SLCM_IRS_URL
    parsed = urlparse(url)
    if parsed.scheme != "https" or not parsed.hostname or not (
        parsed.hostname == "slcm.ui.ac.id" or parsed.hostname.endswith(".slcm.ui.ac.id")
    ):
        raise ValueError("SLCM_IRS_URL must use HTTPS and the slcm.ui.ac.id domain.")
    return url


def expire_stale_sessions():
    SLCMAutofillSession.objects.filter(
        status__in=[
            SLCMAutofillSession.Status.WAITING_LOGIN,
            SLCMAutofillSession.Status.SCRAPING,
            SLCMAutofillSession.Status.READY,
        ],
        expires_at__lte=timezone.now(),
    ).update(status=SLCMAutofillSession.Status.EXPIRED)


def start_scraper(session_id):
    thread = threading.Thread(target=_scrape_session, args=(str(session_id),), daemon=True)
    thread.start()


def configure_mobile_chrome(options):
    """Configure Chrome for a phone-sized, touch-enabled SLCM login."""
    width = max(320, int(settings.SLCM_BROWSER_SCREEN_WIDTH))
    height = max(568, int(settings.SLCM_BROWSER_SCREEN_HEIGHT))
    options.add_argument("--window-size={},{}".format(width, height))
    options.add_argument("--force-device-scale-factor=1")
    options.add_experimental_option(
        "mobileEmulation",
        {
            "deviceMetrics": {
                "width": width,
                "height": height,
                "pixelRatio": 1,
                "touch": True,
                "mobile": True,
            }
        },
    )
    return options


def _scrape_session(session_id):
    close_old_connections()
    driver = None
    try:
        from selenium import webdriver
        from selenium.common.exceptions import TimeoutException
        from selenium.webdriver.support.ui import WebDriverWait

        session = SLCMAutofillSession.objects.get(pk=session_id)
        if session.status != SLCMAutofillSession.Status.WAITING_LOGIN:
            return
        chrome_options = configure_mobile_chrome(webdriver.ChromeOptions())
        driver = webdriver.Remote(
            command_executor=settings.SLCM_BROWSER_REMOTE_URL,
            options=chrome_options,
        )
        driver.get(validate_slcm_url())

        def find_history(current_driver):
            if SLCMAutofillSession.objects.filter(
                pk=session_id,
                status__in=[SLCMAutofillSession.Status.CANCELLED, SLCMAutofillSession.Status.EXPIRED],
            ).exists():
                raise RuntimeError("SLCM autofill session was cancelled.")
            tables = current_driver.execute_script(TABLE_EXTRACTOR) or []
            try:
                return parse_latest_history(tables)
            except IRSParseError:
                return False

        timeout = max(1, int(settings.SLCM_AUTOFILL_TIMEOUT_SECONDS))
        history = WebDriverWait(driver, timeout, poll_frequency=1).until(find_history)
        SLCMAutofillSession.objects.filter(
            pk=session_id, status=SLCMAutofillSession.Status.WAITING_LOGIN
        ).update(status=SLCMAutofillSession.Status.SCRAPING)
        resolved, unmatched = resolve_courses(history["courses"])
        session = SLCMAutofillSession.objects.get(pk=session_id)
        existing_ids = set(
            CourseSemester.objects.filter(
                semester__userCumulativeGPA__user=session.user,
                semester__given_semester=session.given_semester,
                course_id__in=[course.id for course in resolved],
            ).values_list("course_id", flat=True)
        )
        matched = []
        duplicates = []
        for course in resolved:
            item = {"id": course.id, "code": course.code, "name": course.name, "sks": course.sks}
            (duplicates if course.id in existing_ids else matched).append(item)
        SLCMAutofillSession.objects.filter(
            pk=session_id, status=SLCMAutofillSession.Status.SCRAPING
        ).update(
            status=SLCMAutofillSession.Status.READY,
            source_period=history["period"],
            preview={"matched": matched, "duplicates": duplicates, "unmatched": unmatched},
            error=None,
            expires_at=timezone.now() + timedelta(seconds=settings.SLCM_AUTOFILL_TIMEOUT_SECONDS),
        )
    except TimeoutException:
        _fail(session_id, "LOGIN_TIMEOUT", "Timed out waiting for SLCM login or IRS content.")
    except Exception as exc:
        logger.exception("SLCM autofill session %s failed", session_id)
        _fail(session_id, "BROWSER_ERROR", str(exc))
    finally:
        if driver is not None:
            try:
                driver.quit()
            except Exception:
                logger.warning("Could not close SLCM browser session", exc_info=True)
        close_old_connections()


def _fail(session_id, code, message):
    SLCMAutofillSession.objects.filter(
        pk=session_id,
        status__in=[SLCMAutofillSession.Status.WAITING_LOGIN, SLCMAutofillSession.Status.SCRAPING],
    ).update(status=SLCMAutofillSession.Status.FAILED, error={"code": code, "message": message})
