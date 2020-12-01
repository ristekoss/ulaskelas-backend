# Generated by Django 3.1.2 on 2020-12-01 11:30

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('main', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='Curriculum',
            fields=[
                ('id', models.AutoField(auto_created=True,
                                        primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=31)),
                ('year', models.PositiveSmallIntegerField()),
            ],
        ),
        migrations.CreateModel(
            name='Tag',
            fields=[
                ('id', models.AutoField(auto_created=True,
                                        primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=31)),
            ],
        ),
        migrations.CreateModel(
            name='Course',
            fields=[
                ('id', models.AutoField(auto_created=True,
                                        primary_key=True, serialize=False, verbose_name='ID')),
                ('code', models.CharField(max_length=10)),
                ('name', models.CharField(max_length=127)),
                ('aliasName', models.CharField(max_length=63)),
                ('sks', models.PositiveSmallIntegerField()),
                ('description', models.CharField(max_length=127)),
                ('curriculums', models.ManyToManyField(to='main.Curriculum')),
                ('prerequisites', models.ManyToManyField(to='main.Course')),
                ('tags', models.ManyToManyField(to='main.Tag')),
            ],
        ),
        migrations.AddField(
            model_name='profile',
            name='bookmarked_courses',
            field=models.ManyToManyField(to='main.Course'),
        ),
    ]
