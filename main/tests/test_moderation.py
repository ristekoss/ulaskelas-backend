from django.test import SimpleTestCase, override_settings

from main.moderation import contains_trigger_word, normalize_moderation_text


@override_settings(MODERATION_TRIGGER_WORDS=("kata kasar", "asu"))
class ModerationMatcherTest(SimpleTestCase):
    def test_matches_case_insensitive_phrase_across_punctuation(self):
        self.assertTrue(contains_trigger_word("Ini KATA—KASAR sekali"))

    def test_normalizes_compatible_unicode_characters(self):
        self.assertTrue(contains_trigger_word("ＡＳＵ"))

    def test_does_not_match_trigger_inside_another_word(self):
        self.assertFalse(contains_trigger_word("Kasur baru"))

    def test_ignores_blank_and_duplicate_spacing(self):
        self.assertEqual(normalize_moderation_text("  Kata\t\n kasar  "), "kata kasar")
        self.assertFalse(contains_trigger_word("Pertanyaan biasa", ("", "   ")))
