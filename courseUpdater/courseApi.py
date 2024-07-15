import requests
from main.models import Course
from django.conf import settings as django_settings
import logging
import environ

def update_courses():
    env = environ.Env()
    print("UPDATE CALLED")
    
    url_ik = env("SUNJAD_BASE_URL") + '/susunjadwal/api/majors/60f4f2b38cd53dc0e3b371b9/all_courses'
    _update_courses_on_url(url_ik)
    url_si = env("SUNJAD_BASE_URL") + '/susunjadwal/api/majors/60f505258cd53dc0e3b371d4/all_courses'
    _update_courses_on_url(url_si)
                
def _update_courses_on_url(url: str):
    json = _fetch_courses_json(url)
    logging.info("Sunjad courses response: {}".format(json))

    if json is not None:
        courses_json = json['courses']
        for course_json in courses_json:
            if course_json['code']:
                course = getCourse(course_json)
                course.save()

def _fetch_courses_json(url: str):
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