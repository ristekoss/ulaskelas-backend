from django.core.management.base import BaseCommand
from django.db import transaction

from courseUpdater.courseApi import is_invalid_course_code
from main.models import (
    Bookmark,
    Calculator,
    Course,
    CourseSemester,
    Question,
    StudyProgramCourse,
)


class Command(BaseCommand):
    help = (
        "Deactivate mappings for invalid course codes and delete invalid courses "
        "that have no user-owned references. Runs as a dry-run by default."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--apply",
            action="store_true",
            dest="apply_changes",
            help="Apply the cleanup. Without this flag, only report planned changes.",
        )

    def handle(self, *args, **options):
        apply_changes = options["apply_changes"]
        candidates = [
            course
            for course in Course.objects.all().order_by("id")
            if is_invalid_course_code(course.code)
        ]

        summary = {
            "candidates": len(candidates),
            "deleted": 0,
            "retained": 0,
            "mappings_deactivated": 0,
        }

        if apply_changes:
            with transaction.atomic():
                self._process_candidates(candidates, summary, apply_changes=True)
        else:
            self._process_candidates(candidates, summary, apply_changes=False)

        mode = "APPLIED" if apply_changes else "DRY RUN"
        mapping_summary = (
            "deactivated" if apply_changes else "would be deactivated"
        )
        self.stdout.write(
            "{}: {candidates} candidate(s), {deleted} deleted, "
            "{retained} retained, {mappings_deactivated} active mapping(s) "
            "{}".format(mode, mapping_summary, **summary)
        )
        if not apply_changes:
            self.stdout.write("Run again with --apply to perform this cleanup.")

    def _process_candidates(self, candidates, summary, apply_changes):
        for course in candidates:
            course_id = course.id
            course_code = course.code
            reference_counts = self._get_user_reference_counts(course)
            total_references = sum(reference_counts.values())
            active_mappings = StudyProgramCourse.objects.filter(
                course=course,
                is_active=True,
            )
            mapping_count = active_mappings.count()

            if total_references:
                action = "retain and deactivate mappings"
                summary["retained"] += 1
                summary["mappings_deactivated"] += mapping_count
                if apply_changes:
                    active_mappings.update(is_active=False)
            else:
                action = "delete"
                summary["deleted"] += 1
                if apply_changes:
                    course.delete()

            references = ", ".join(
                "{}={}".format(name, count)
                for name, count in reference_counts.items()
                if count
            ) or "none"
            self.stdout.write(
                "Course id={} code={!r}: {}; active_mappings={}; references={}".format(
                    course_id,
                    course_code,
                    action,
                    mapping_count,
                    references,
                )
            )

    @staticmethod
    def _get_user_reference_counts(course):
        return {
            "reviews": course.reviews.count(),
            "bookmarks": Bookmark.objects.filter(course=course).count(),
            "calculators": Calculator.objects.filter(course=course).count(),
            "course_semesters": CourseSemester.objects.filter(course=course).count(),
            "questions": Question.objects.filter(course=course).count(),
        }
