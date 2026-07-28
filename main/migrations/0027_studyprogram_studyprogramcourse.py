# Generated manually for cross-faculty course catalog support.

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("main", "0026_auto_20251113_1512"),
    ]

    operations = [
        migrations.CreateModel(
            name="StudyProgram",
            fields=[
                (
                    "org_code",
                    models.CharField(max_length=63, primary_key=True, serialize=False),
                ),
                ("faculty", models.CharField(max_length=127)),
                ("study_program", models.CharField(max_length=127)),
                ("educational_program", models.CharField(max_length=127)),
                ("is_supported", models.BooleanField(default=True)),
                ("last_synced_at", models.DateTimeField(blank=True, null=True)),
            ],
        ),
        migrations.CreateModel(
            name="StudyProgramCourse",
            fields=[
                (
                    "id",
                    models.AutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("program_term", models.PositiveSmallIntegerField()),
                ("curriculum", models.CharField(blank=True, max_length=20)),
                (
                    "course_type",
                    models.CharField(
                        choices=[
                            ("MANDATORY", "Wajib"),
                            ("ELECTIVE", "Pilihan"),
                            ("UNKNOWN", "Belum diketahui"),
                        ],
                        default="UNKNOWN",
                        max_length=16,
                    ),
                ),
                ("is_active", models.BooleanField(default=True)),
                (
                    "course",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="study_program_courses",
                        to="main.course",
                    ),
                ),
                (
                    "study_program",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="course_mappings",
                        to="main.studyprogram",
                    ),
                ),
            ],
        ),
        migrations.AddConstraint(
            model_name="studyprogramcourse",
            constraint=models.UniqueConstraint(
                fields=("study_program", "course"),
                name="unique_study_program_course",
            ),
        ),
        migrations.AddIndex(
            model_name="studyprogramcourse",
            index=models.Index(
                fields=["study_program", "is_active", "program_term"],
                name="main_studyp_study_p_2f01a8_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="studyprogramcourse",
            index=models.Index(
                fields=["course_type"], name="main_studyp_course__192085_idx"
            ),
        ),
    ]
