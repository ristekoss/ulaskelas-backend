import base64
import binascii
import hashlib
import json
import secrets
import time
from urllib.parse import parse_qs, urljoin, urlparse

import requests
from lxml import html


AUTHORIZATION_URL = "https://login.ui.ac.id/realms/main/protocol/openid-connect/auth"
TOKEN_URL = "https://login.ui.ac.id/realms/main/protocol/openid-connect/token"
USER_URL = "https://slcm.ui.ac.id/akademik/api/user"
ACTIVE_PERIOD_URL = "https://slcm.ui.ac.id/akademik/api/v1/class/period"
MY_CLASSES_URL = "https://slcm.ui.ac.id/akademik/api/course-plan/me/classes"
CLIENT_ID = "slcm-beasiswa"
REDIRECT_URI = "https://slcm.ui.ac.id/portal"
USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36"
)


class SLCMError(Exception):
    code = "SLCM_ERROR"


class SLCMAuthenticationError(SLCMError):
    code = "AUTHENTICATION_FAILED"


class SLCMNetworkError(SLCMError):
    code = "SLCM_NETWORK_ERROR"


class SLCMProtocolError(SLCMError):
    code = "SLCM_PROTOCOL_ERROR"


class SLCMClient:
    """HTTP implementation of the protocol documented by slcm-sdk."""

    def __init__(self, timeout=15, retries=2, retry_delay=0.25, session=None):
        if not isinstance(timeout, (int, float)) or isinstance(timeout, bool) or timeout <= 0:
            raise ValueError("timeout must be positive.")
        if not isinstance(retries, int) or isinstance(retries, bool) or retries < 0:
            raise ValueError("retries must be a non-negative integer.")
        self.timeout = timeout
        self.retries = retries
        self.retry_delay = retry_delay
        self.session = session or requests.Session()
        self.session.headers.update({"User-Agent": USER_AGENT})
        self.tokens = None
        self.x_app_token = None
        self.user = None
        self.active_period = None

    def fetch_course_plan(self, username, password):
        self.login(username, password)
        payload = self._authenticated_get(MY_CLASSES_URL)
        classes, warning = self._parse_course_plan(payload)
        return {
            "username": self._user_username(),
            "period": self.active_period["period"],
            "courses": classes,
            "warning_stale_data": warning,
        }

    def login(self, username, password):
        if not isinstance(username, str) or not username.strip():
            raise SLCMAuthenticationError("SSO username is required.")
        if not isinstance(password, str) or not password:
            raise SLCMAuthenticationError("SSO password is required.")

        verifier = self._base64url(secrets.token_bytes(32))
        challenge = self._base64url(hashlib.sha256(verifier.encode()).digest())
        state = secrets.token_urlsafe(32)
        params = {
            "client_id": CLIENT_ID,
            "redirect_uri": REDIRECT_URI,
            "state": state,
            "response_mode": "fragment",
            "response_type": "code",
            "scope": "openid",
            "nonce": secrets.token_urlsafe(32),
            "code_challenge": challenge,
            "code_challenge_method": "S256",
        }
        login_page = self._request("GET", AUTHORIZATION_URL, params=params)
        self._require_status(login_page, "Loading the SSO login page")
        form_action = self._login_form_action(login_page.text, login_page.url)
        if self._origin(form_action) != self._origin(AUTHORIZATION_URL):
            raise SLCMProtocolError("The SSO login form points to an unexpected origin.")

        response = self._request(
            "POST",
            form_action,
            data={"username": username, "password": password, "credentialId": ""},
            allow_redirects=False,
        )
        if response.status_code != 302:
            if response.status_code == 429 or response.status_code >= 500:
                raise SLCMNetworkError(
                    "Submitting SSO credentials failed (HTTP {}).".format(response.status_code)
                )
            raise SLCMAuthenticationError("SLCM rejected the supplied credentials.")

        location = response.headers.get("Location")
        if not location:
            raise SLCMProtocolError("The SSO response did not include a redirect location.")
        callback = urlparse(urljoin(REDIRECT_URI, location))
        expected = urlparse(REDIRECT_URI)
        if (callback.scheme, callback.netloc, callback.path) != (
            expected.scheme,
            expected.netloc,
            expected.path,
        ):
            raise SLCMAuthenticationError("The SSO response redirected unexpectedly.")
        fragment = parse_qs(callback.fragment)
        if fragment.get("state", [None])[0] != state:
            raise SLCMAuthenticationError("The SSO state did not match.")
        code = fragment.get("code", [None])[0]
        if not code:
            raise SLCMProtocolError("The SSO response did not include an authorization code.")

        token_response = self._request(
            "POST",
            TOKEN_URL,
            data={
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": REDIRECT_URI,
                "client_id": CLIENT_ID,
                "code_verifier": verifier,
            },
        )
        self._require_status(token_response, "Exchanging the SSO code")
        self.tokens = self._parse_tokens(self._json(token_response, "token endpoint"))
        self._complete_authentication()

    def _complete_authentication(self):
        response = self._request(
            "GET", USER_URL, headers={"Authorization": self._authorization_header()}
        )
        self._require_status(response, "Loading the SLCM user session")
        payload = self._json(response, "SLCM /user")
        data = payload.get("data") if isinstance(payload, dict) else None
        token = data.get("userToken") if isinstance(data, dict) else None
        if not isinstance(token, str) or not token:
            raise SLCMProtocolError("SLCM /user response does not contain data.userToken.")
        self.x_app_token = token
        self.user = self._decode_user(token)

        response = self._request("GET", ACTIVE_PERIOD_URL, headers=self._auth_headers())
        self._require_status(response, "Loading the active SLCM period")
        self.active_period = self._parse_active_period(
            self._json(response, "SLCM class/period")
        )

    def _authenticated_get(self, url):
        response = self._request("GET", url, headers=self._auth_headers())
        if response.status_code in (401, 403):
            self._refresh()
            response = self._request("GET", url, headers=self._auth_headers())
        self._require_status(response, "Reading the SLCM course plan")
        return self._json(response, "SLCM course plan")

    def _refresh(self):
        response = self._request(
            "POST",
            TOKEN_URL,
            data={
                "grant_type": "refresh_token",
                "refresh_token": self.tokens["refresh_token"],
                "client_id": CLIENT_ID,
            },
        )
        self._require_status(response, "Refreshing the SLCM token")
        refreshed = self._parse_tokens(
            self._json(response, "token endpoint"), previous=self.tokens
        )
        self.tokens = refreshed
        self._complete_authentication()

    def _request(self, method, url, **kwargs):
        last_error = None
        for attempt in range(self.retries + 1):
            try:
                response = self.session.request(method, url, timeout=self.timeout, **kwargs)
                if response.status_code != 429 and response.status_code < 500:
                    return response
                last_error = SLCMNetworkError(
                    "SLCM request failed (HTTP {}).".format(response.status_code)
                )
            except (requests.Timeout, requests.ConnectionError) as exc:
                last_error = SLCMNetworkError("SLCM could not be reached.")
                last_error.__cause__ = exc
            if attempt < self.retries:
                time.sleep(self.retry_delay * (2 ** attempt))
        raise last_error

    @staticmethod
    def _login_form_action(document, base_url):
        try:
            tree = html.fromstring(document, base_url=base_url)
            actions = tree.xpath(
                "//form[contains(@action, 'login-actions/authenticate')]/@action"
            )
        except (ValueError, TypeError) as exc:
            raise SLCMProtocolError("The SSO login page was malformed.") from exc
        if not actions:
            raise SLCMProtocolError("The SSO login form action was not found.")
        return urljoin(base_url, actions[0])

    @staticmethod
    def _parse_tokens(payload, previous=None):
        if not isinstance(payload, dict):
            raise SLCMProtocolError("The token endpoint returned invalid JSON.")
        access = payload.get("access_token")
        token_type = payload.get("token_type")
        expires = payload.get("expires_in")
        refresh = payload.get("refresh_token") or (previous or {}).get("refresh_token")
        identity = payload.get("id_token") or (previous or {}).get("id_token")
        if (
            not isinstance(access, str)
            or not access
            or not isinstance(token_type, str)
            or not token_type
            or not isinstance(expires, (int, float))
            or isinstance(expires, bool)
            or expires <= 0
            or not isinstance(refresh, str)
            or not refresh
            or not isinstance(identity, str)
            or not identity
        ):
            raise SLCMProtocolError("The token response is missing required fields.")
        return {
            "access_token": access,
            "refresh_token": refresh,
            "id_token": identity,
            "token_type": token_type,
            "expires_in": expires,
        }

    @staticmethod
    def _decode_user(token):
        try:
            encoded = token.split(".")[1]
            encoded += "=" * (-len(encoded) % 4)
            payload = json.loads(base64.urlsafe_b64decode(encoded).decode("utf-8"))
            user = payload.get("userInfo") if isinstance(payload, dict) else None
            return user if isinstance(user, dict) else None
        except (IndexError, ValueError, TypeError, binascii.Error, json.JSONDecodeError):
            return None

    @staticmethod
    def _parse_active_period(payload):
        data = payload.get("data") if isinstance(payload, dict) else None
        if not isinstance(data, list) or not data:
            raise SLCMProtocolError("SLCM did not return an active period.")
        active = data[0]
        if isinstance(active, str):
            parts = active.strip().split("-")
            if len(parts) == 2 and parts[0].isdigit() and parts[1] in {"1", "2", "3"}:
                return {"year": int(parts[0]), "term": int(parts[1]), "period": active.strip()}
        if isinstance(active, dict):
            year, term = active.get("year"), active.get("term")
            if (
                isinstance(year, int)
                and not isinstance(year, bool)
                and isinstance(term, int)
                and not isinstance(term, bool)
                and term in {1, 2, 3}
            ):
                period = active.get("period")
                return {
                    "year": year,
                    "term": term,
                    "period": period.strip() if isinstance(period, str) and period.strip() else "{}-{}".format(year, term),
                }
        raise SLCMProtocolError("SLCM returned a malformed active period.")

    @staticmethod
    def _parse_course_plan(payload):
        if not isinstance(payload, dict) or not isinstance(payload.get("data"), list):
            raise SLCMProtocolError("SLCM course plan does not contain a data array.")
        warning = payload.get("warning-stale-data")
        if not isinstance(warning, bool):
            raise SLCMProtocolError("SLCM warning-stale-data is not a boolean.")
        courses = []
        for index, item in enumerate(payload["data"]):
            if not isinstance(item, dict):
                raise SLCMProtocolError("SLCM course data[{}] is malformed.".format(index))
            periods, dates, rooms = item.get("periods"), item.get("dates"), item.get("rooms")
            if not all(isinstance(values, list) and all(isinstance(value, str) for value in values) for values in (periods, dates, rooms)):
                raise SLCMProtocolError("SLCM meeting fields must be string arrays.")
            if len(periods) != len(dates) or len(dates) != len(rooms):
                raise SLCMProtocolError("SLCM meeting arrays have different lengths.")
            code, name, credits = item.get("kode_mata_kuliah"), item.get("nama_mata_kuliah"), item.get("jumlah_sks")
            if (
                not isinstance(code, str)
                or not code.strip()
                or not isinstance(name, str)
                or not name.strip()
                or not isinstance(credits, (int, float))
                or isinstance(credits, bool)
            ):
                raise SLCMProtocolError("SLCM course fields are malformed at data[{}].".format(index))
            courses.append({"code": code.strip(), "name": name.strip(), "credits": credits})
        return courses, warning

    def _user_username(self):
        username = self.user.get("username") if isinstance(self.user, dict) else None
        if not isinstance(username, str) or not username.strip():
            raise SLCMProtocolError("SLCM did not return the authenticated username.")
        return username.strip()

    def _auth_headers(self):
        return {"Authorization": self._authorization_header(), "x-app-token": self.x_app_token}

    def _authorization_header(self):
        return "{} {}".format(self.tokens["token_type"], self.tokens["access_token"])

    @staticmethod
    def _json(response, source):
        try:
            return response.json()
        except (ValueError, json.JSONDecodeError) as exc:
            raise SLCMProtocolError("{} returned malformed JSON.".format(source)) from exc

    @staticmethod
    def _require_status(response, operation):
        if response.ok:
            return
        if response.status_code in (401, 403):
            raise SLCMAuthenticationError("{} failed.".format(operation))
        if response.status_code == 429 or response.status_code >= 500:
            raise SLCMNetworkError("{} failed (HTTP {}).".format(operation, response.status_code))
        raise SLCMProtocolError("{} failed (HTTP {}).".format(operation, response.status_code))

    @staticmethod
    def _origin(url):
        parsed = urlparse(url)
        return parsed.scheme, parsed.netloc

    @staticmethod
    def _base64url(value):
        return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")
