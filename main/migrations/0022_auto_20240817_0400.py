# Generated by Django 3.1.2 on 2024-08-17 04:00

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('main', '0021_auto_20240815_0451'),
    ]

    operations = [
        migrations.AlterField(
            model_name='question',
            name='attachment',
            field=models.CharField(max_length=120, null=True),
        ),
    ]