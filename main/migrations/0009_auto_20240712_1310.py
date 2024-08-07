# Generated by Django 3.1.2 on 2024-07-12 13:10

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('main', '0008_usercumulativegpa_usergpa'),
    ]

    operations = [
        migrations.AlterField(
            model_name='usergpa',
            name='given_semester',
            field=models.PositiveSmallIntegerField(),
        ),
        migrations.AddConstraint(
            model_name='usergpa',
            constraint=models.UniqueConstraint(fields=('userCumulativeGPA', 'given_semester'), name='unique_userCumulativeGPA_given_semester'),
        ),
    ]
