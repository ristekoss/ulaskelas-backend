from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [("main", "0030_device_token_notification")]

    operations = [
        migrations.RemoveField(
            model_name="slcmautofillsession",
            name="popup_opened_at",
        ),
        migrations.RemoveField(
            model_name="slcmautofillsession",
            name="popup_token_hash",
        ),
        migrations.RemoveField(
            model_name="slcmautofillsession",
            name="popup_url",
        ),
    ]
