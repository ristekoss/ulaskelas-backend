# Generated by Django 3.1.2 on 2024-08-15 04:51

from django.db import migrations, models
import django.utils.timezone


class Migration(migrations.Migration):

    dependencies = [
        ('main', '0020_auto_20240809_0024'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='question',
            name='updated_at',
        ),
        migrations.AlterField(
            model_name='question',
            name='created_at',
            field=models.DateTimeField(default=django.utils.timezone.now),
        ),
    ]