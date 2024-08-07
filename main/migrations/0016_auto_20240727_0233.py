# Generated by Django 3.1.2 on 2024-07-27 02:33

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('main', '0015_usergpa_semester_mutu'),
    ]

    operations = [
        migrations.CreateModel(
            name='ScoreSubcomponent',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('subcomponent_number', models.PositiveIntegerField()),
                ('subcomponent_score', models.FloatField(null=True)),
                ('score_component', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='main.scorecomponent')),
            ],
        ),
        migrations.AddConstraint(
            model_name='scoresubcomponent',
            constraint=models.UniqueConstraint(fields=('score_component', 'subcomponent_number'), name='unique_number'),
        ),
    ]
