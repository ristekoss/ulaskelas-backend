from django.conf import settings

__all__ = []

DEFAULTS = {
    "SSO_UI_URL": "https://sso.ui.ac.id/cas2/",
    "SSO_UI_FORCE_SERVICE_HTTPS": False,
    # notice: SUNJAD_BASE_URL is now an .env variable
}


for key, value in list(DEFAULTS.items()):
    if not hasattr(settings, key):
        setattr(settings, key, value)
