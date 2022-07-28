import requests
from main.models import Course
from django.conf import settings as django_settings
import logging

def update_courses():
    print("UPDATE CALLED")
    json = _get_courses_json()
    logging.info("Sunjad courses response: {}".format(json))

    if json is not None:
        courses_json = json['courses']
        for course_json in courses_json:
            if course_json['code']:
                course = getCourse(course_json)
                course.save()

def _get_courses_json():
    url = django_settings.SUNJAD_BASE_URL + 'susunjadwal/api/courses'

    r = requests.get(url)

    try:
        r.raise_for_status()
        return r.json()
    except:
        return None

def getCourse(course_json):
    try:
        course = Course.objects.get(code = course_json['code'])
        if (course.curriculum < course_json['curriculum']):
            course = populateCourseData(course, course_json)
    except Exception as e:
        course = Course()
        course.code = course_json['code']
        course = populateCourseData(course, course_json)
    return course

def populateCourseData(course, course_json):
    course.curriculum = course_json['curriculum']
    course.sks = int(course_json['credit'])
    course.description = course_json['description'] if course_json['description'] else ""
    course.name = course_json['name']
    course.term = int(course_json['term'])
    course.prerequisite = course_json['prerequisite'] if course_json['prerequisite'] else ""
    return course