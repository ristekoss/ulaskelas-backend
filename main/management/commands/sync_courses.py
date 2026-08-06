import logging

from django.core.management.base import BaseCommand, CommandError

from courseUpdater.courseApi import (
    CourseCatalogUnavailable,
    CourseSyncError,
    get_supported_program_configs,
    update_courses,
)


logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Synchronize SunJad courses for one or all supported UI study programs."

    def add_arguments(self, parser):
        parser.add_argument("--org-code", dest="org_code")
        parser.add_argument(
            "--all",
            action="store_true",
            dest="sync_all",
            help="Synchronize all configured S1, D3, and D4 programs.",
        )

    def handle(self, *args, **options):
        org_code = options.get("org_code")
        sync_all = options.get("sync_all")
        if bool(org_code) == bool(sync_all):
            raise CommandError("Choose exactly one of --org-code or --all.")

        org_codes = (
            sorted(get_supported_program_configs())
            if sync_all
            else [org_code]
        )
        unavailable = []
        failed = []
        for current_org_code in org_codes:
            try:
                result = update_courses(current_org_code)
                self.stdout.write(
                    self.style.SUCCESS(
                        "{org_code}: {active_courses} active, "
                        "{inactive_courses} inactive, {skipped_courses} skipped".format(
                            **result
                        )
                    )
                )
            except CourseCatalogUnavailable as exc:
                unavailable.append(current_org_code)
                logger.warning(
                    "Course catalog unavailable for org_code=%s",
                    current_org_code,
                )
                self.stderr.write(
                    self.style.WARNING("{}: {}".format(current_org_code, exc))
                )
            except CourseSyncError as exc:
                failed.append(current_org_code)
                logger.exception(
                    "Course synchronization failed for org_code=%s", current_org_code
                )
                self.stderr.write(
                    self.style.ERROR("{}: {}".format(current_org_code, exc))
                )

        if unavailable:
            self.stderr.write(
                self.style.WARNING(
                    "Course catalog unavailable for {} program(s): {}".format(
                        len(unavailable), ", ".join(unavailable)
                    )
                )
            )

        if failed:
            raise CommandError(
                "Synchronization failed for {} program(s): {}".format(
                    len(failed), ", ".join(failed)
                )
            )
