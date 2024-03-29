from django.conf import settings

__all__ = []

DEFAULTS = {
    "SSO_UI_URL": "https://sso.ui.ac.id/cas2/",
    "SUNJAD_BASE_URL": " https://api.susunjadwal.cs.ui.ac.id/",
    "SSO_UI_FORCE_SERVICE_HTTPS": False,
}


for key, value in list(DEFAULTS.items()):
    if not hasattr(settings, key):
        setattr(settings, key, value)
