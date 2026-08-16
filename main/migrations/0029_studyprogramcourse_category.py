from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("main", "0028_slcmautofillsession")]

    operations = [
        migrations.AddField(
            model_name="studyprogramcourse",
            name="category",
            field=models.CharField(
                choices=[
                    ("INTERNAL", "Kelas Internal"),
                    ("SHARED", "Kelas Bersama"),
                    ("EXTERNAL", "Kelas Eksternal"),
                    ("UNKNOWN", "Belum diketahui"),
                ],
                default="UNKNOWN",
                max_length=16,
            ),
        ),
        migrations.AddIndex(
            model_name="studyprogramcourse",
            index=models.Index(
                fields=["study_program", "is_active", "category"],
                name="main_studyp_study_p_71c1d0_idx",
            ),
        ),
    ]
