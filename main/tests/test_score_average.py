from django.test import SimpleTestCase

from main.utils import calculate_average, normalize_score


class ScoreAverageTest(SimpleTestCase):
    def test_average_ignores_null_scores(self):
        self.assertEqual(calculate_average([80, 70, None]), 75)

    def test_zero_is_a_filled_score(self):
        self.assertEqual(calculate_average([80, 70, 0]), 50)

    def test_all_null_scores_have_no_average(self):
        self.assertIsNone(calculate_average([None, None]))

    def test_empty_string_is_normalized_to_null(self):
        self.assertIsNone(normalize_score(""))
        self.assertEqual(calculate_average([80, "", 70]), 75)
