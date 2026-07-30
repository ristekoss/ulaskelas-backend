from django.test import TestCase

from main.models import Tag
from main.utils import get_paged_obj


class PaginationTest(TestCase):
    def setUp(self):
        Tag.objects.bulk_create(
            [Tag(tag_name="TAG-{:02d}".format(index)) for index in range(11)]
        )

    def test_valid_page_returns_requested_page(self):
        tags, total_page = get_paged_obj(Tag.objects.all(), 2)

        self.assertEqual(total_page, 2)
        self.assertEqual([tag.tag_name for tag in tags], ["TAG-10"])

    def test_non_numeric_page_falls_back_to_first_page(self):
        tags, total_page = get_paged_obj(Tag.objects.all(), "invalid")

        self.assertEqual(total_page, 2)
        self.assertEqual(len(tags), 10)
        self.assertEqual(tags[0].tag_name, "TAG-00")

    def test_page_above_total_returns_empty_list(self):
        tags, total_page = get_paged_obj(Tag.objects.all(), 3)

        self.assertEqual(total_page, 2)
        self.assertEqual(tags, [])
