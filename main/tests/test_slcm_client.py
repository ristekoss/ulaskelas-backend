import base64
import json
from unittest.mock import MagicMock

from django.test import SimpleTestCase
from requests import Response

from main.integrations.slcm_client import (
    SLCMClient,
    SLCMProtocolError,
)


def response(status, url, body=None, headers=None, text=None):
    result = Response()
    result.status_code = status
    result.url = url
    result.headers.update(headers or {})
    if body is not None:
        result._content = json.dumps(body).encode()
        result.headers["Content-Type"] = "application/json"
    else:
        result._content = (text or "").encode()
    return result


def user_token(username="test-user"):
    payload = base64.urlsafe_b64encode(
        json.dumps({"userInfo": {"username": username}}).encode()
    ).rstrip(b"=").decode()
    return "header.{}.signature".format(payload)


class SLCMClientTest(SimpleTestCase):
    def test_fetch_course_plan_completes_pkce_flow_and_normalizes_courses(self):
        session = MagicMock()
        login_html = (
            '<form action="https://login.ui.ac.id/realms/main/login-actions/'
            'authenticate?session_code=abc&amp;execution=def"></form>'
        )

        def request(method, url, **kwargs):
            if method == "GET" and "openid-connect/auth" in url:
                request.state = kwargs["params"]["state"]
                self.assertEqual(kwargs["params"]["code_challenge_method"], "S256")
                return response(200, url, text=login_html)
            if method == "POST" and "login-actions/authenticate" in url:
                return response(
                    302,
                    url,
                    headers={
                        "Location": "https://slcm.ui.ac.id/portal#code=code-1&state={}".format(
                            request.state
                        )
                    },
                )
            if method == "POST" and "openid-connect/token" in url:
                self.assertIn("code_verifier", kwargs["data"])
                return response(
                    200,
                    url,
                    body={
                        "access_token": "access",
                        "refresh_token": "refresh",
                        "id_token": "identity",
                        "token_type": "Bearer",
                        "expires_in": 300,
                    },
                )
            if url.endswith("/akademik/api/user"):
                return response(200, url, body={"data": {"userToken": user_token()}})
            if url.endswith("/akademik/api/v1/class/period"):
                self.assertEqual(kwargs["headers"]["x-app-token"], user_token())
                return response(200, url, body={"data": [{"year": 2026, "term": 1, "period": "2026-1"}]})
            if url.endswith("/akademik/api/course-plan/me/classes"):
                return response(
                    200,
                    url,
                    body={
                        "warning-stale-data": True,
                        "data": [
                            {
                                "kode_mata_kuliah": " CSGE601020 ",
                                "nama_mata_kuliah": "Dasar Pemrograman ",
                                "jumlah_sks": 4,
                                "periods": ["24/08/2026 - 18/12/2026"],
                                "dates": ["Selasa"],
                                "rooms": ["A6.02"],
                            }
                        ],
                    },
                )
            raise AssertionError("Unexpected request: {} {}".format(method, url))

        session.request.side_effect = request
        result = SLCMClient(session=session, retries=0).fetch_course_plan(
            "test-user", "secret"
        )

        self.assertEqual(result["username"], "test-user")
        self.assertEqual(result["period"], "2026-1")
        self.assertTrue(result["warning_stale_data"])
        self.assertEqual(
            result["courses"],
            [{"code": "CSGE601020", "name": "Dasar Pemrograman", "credits": 4}],
        )

    def test_course_plan_rejects_mismatched_meeting_arrays(self):
        with self.assertRaisesMessage(SLCMProtocolError, "different lengths"):
            SLCMClient._parse_course_plan(
                {
                    "warning-stale-data": False,
                    "data": [
                        {
                            "kode_mata_kuliah": "CSGE601020",
                            "nama_mata_kuliah": "Dasar Pemrograman",
                            "jumlah_sks": 4,
                            "periods": ["period"],
                            "dates": [],
                            "rooms": [],
                        }
                    ],
                }
            )

    def test_login_form_rejects_unexpected_origin(self):
        session = MagicMock()
        session.request.return_value = response(
            200,
            "https://login.ui.ac.id/login",
            text='<form action="https://evil.example/login-actions/authenticate"></form>',
        )
        with self.assertRaisesMessage(SLCMProtocolError, "unexpected origin"):
            SLCMClient(session=session, retries=0).login("test-user", "secret")
