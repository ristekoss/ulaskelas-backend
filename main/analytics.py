from mixpanel import Mixpanel
from django.conf import settings
import logging


logger = logging.getLogger(__name__)

try:
    mp = Mixpanel(settings.MIXPANEL_TOKEN)
except Exception as e:
    logger.error("Mixpanel token is not set or invalid:", e)
    mp = None


def track_event(user_id, event_name, properties=None):
    if not mp:
        logger.warning("Mixpanel is not configured, event tracking is disabled.")
        return

    try:
        mp.track(user_id, event_name, properties or {})
    except Exception as e:
        logger.error(f"Failed to track event '{event_name}' for user '{user_id}': {e}")
