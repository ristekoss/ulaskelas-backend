from django.test import SimpleTestCase

from UlasKelas.email_config import resolve_notification_recipients


class ResolveNotificationRecipientsTest(SimpleTestCase):
    def test_uses_multi_recipient_list_when_available(self):
        recipients = resolve_notification_recipients(
            ["first@example.com", "second@example.com"],
            "legacy@example.com",
        )

        self.assertEqual(recipients, ["first@example.com", "second@example.com"])

    def test_falls_back_to_legacy_recipient_when_list_is_empty(self):
        recipients = resolve_notification_recipients([], "legacy@example.com")

        self.assertEqual(recipients, ["legacy@example.com"])

    def test_returns_empty_list_when_both_are_empty(self):
        recipients = resolve_notification_recipients([], "")

        self.assertEqual(recipients, [])

    def test_ignores_empty_values_in_multi_recipient_list(self):
        recipients = resolve_notification_recipients(
            ["first@example.com", "", "second@example.com"],
            "legacy@example.com",
        )

        self.assertEqual(recipients, ["first@example.com", "second@example.com"])
