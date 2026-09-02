import uuid

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [("main", "0027_studyprogram_studyprogramcourse")]

    operations = [
        migrations.CreateModel(
            name="SLCMAutofillSession",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("given_semester", models.CharField(max_length=20)),
                ("status", models.CharField(choices=[("waiting_login", "Waiting for login"), ("scraping", "Scraping"), ("ready", "Ready"), ("imported", "Imported"), ("failed", "Failed"), ("expired", "Expired"), ("cancelled", "Cancelled")], default="waiting_login", max_length=20)),
                ("popup_token_hash", models.CharField(max_length=64, unique=True)),
                ("popup_opened_at", models.DateTimeField(blank=True, null=True)),
                ("popup_url", models.TextField(blank=True)),
                ("source_period", models.CharField(blank=True, max_length=127)),
                ("preview", models.JSONField(blank=True, default=dict)),
                ("error", models.JSONField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("expires_at", models.DateTimeField()),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to="main.profile")),
            ],
        ),
        migrations.AddIndex(
            model_name="slcmautofillsession",
            index=models.Index(fields=["user", "status"], name="main_slcmaf_user_id_d7a931_idx"),
        ),
    ]
