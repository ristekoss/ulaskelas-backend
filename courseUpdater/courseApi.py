import requests
from main.models import Course

def update_courses():
    print("UPDATE CALLED")
    json = _get_courses_json()
    if json is not None:
        courses_json = json['courses']
        for course_json in courses_json:
            course = getCourse(course_json)
            course.save()

def _get_courses_json():
    url = 'https://3e081de5-8b4c-46ea-8736-99476c47204b.mock.pstmn.io/courses'

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
    course.description = course_json['description']
    course.name = course_json['name']
    course.term = int(course_json['term'])
    course.prerequisites = course_json['prerequisite']
    return course