import os
import json
from cas import CASClient
from django.conf import settings as django_settings
from six.moves import urllib_parse


def normalize_username(username):
    return username.lower()


def get_protocol(request):
    if request.is_secure() or django_settings.SSO_UI_FORCE_SERVICE_HTTPS:
        return "https"

    return "http"


def get_service_url(request, redirect_to=None):
    protocol = get_protocol(request)
    host = request.get_host()
    service = urllib_parse.urlunparse(
        (protocol, host, request.path, "", "", ""))

    return service


def get_cas_client(service_url=None, request=None):
    server_url = django_settings.SSO_UI_URL
    if server_url and request and server_url.startswith("/"):
        scheme = request.META.get("X-Forwarded-Proto", request.scheme)
        server_url = scheme + "://" + request.META["HTTP_HOST"] + server_url

    return CASClient(service_url=service_url, server_url=server_url, version=2)


def authenticate(ticket, client):
    username, attributes, _ = client.verify_ticket(ticket)

    if not username:
        return None

    if "kd_org" in attributes:
        attributes.update(get_additional_info(attributes["kd_org"]) or {})

    sso_profile = {"username": username, "attributes": attributes}
    return sso_profile


def get_additional_info(kd_org):
    path = os.path.dirname(os.path.abspath(__file__))
    filename = os.path.join(path, "additional-info.json")

    with open(filename, "r") as fd:
        as_json = json.load(fd)
        if kd_org in as_json:
            return as_json[kd_org]

    return None


def get_logout_url(request):
    service_url = get_service_url(request)
    client = get_cas_client(service_url)
    return client.get_logout_url()
