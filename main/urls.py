from django import conf
from rest_framework import routers
from django.urls import path, include

from main.views_tanyateman import jawab_teman, tanya_teman
from .views_gpa_calculator import (
    calculator_status,
    course_semester,
    gpa_calculator,
    gpa_calculator_with_semester,
    course_semester_with_course_id,
    course_component,
    course_subcomponent,
)
from .views_calculator import calculator, score_component
from .views import like, tag, bookmark, account, leaderboard
from .views_review import ds_review, review
from .views_notification import (
    device_token,
    notification_read,
    notification_unread_count,
    notifications,
    notifications_read_all,
)
from .views_course import CourseViewSet, majors
from .views_slcm_autofill import (
    slcm_autofill_confirm,
    slcm_autofill_popup,
    slcm_autofill_session,
    slcm_autofill_sessions,
)

router = routers.SimpleRouter()
router.register("courses", CourseViewSet, basename="courses")

urlpatterns = [
    path("", include(router.urls)),
    path("majors", majors, name="majors"),
    path("bookmarks", bookmark, name="bookmarks"),
    path("reviews", review, name="reviews"),
    path("ds-reviews", ds_review, name="ds-reviews"),
    path("likes", like, name="likes"),
    path("tags", tag, name="tags"),
    path("account", account, name="account"),
    path("leaderboard", leaderboard, name="leaderboard"),
    path("calculator", calculator, name="calculator"),
    path("score-component", score_component, name="score-component"),
    path("calculator-gpa", gpa_calculator, name="gpa-calculator"),
    path("calculator-status", calculator_status, name="calculator-status"),
    path("slcm-autofill/sessions", slcm_autofill_sessions, name="slcm-autofill-sessions"),
    path("slcm-autofill/sessions/<uuid:session_id>", slcm_autofill_session, name="slcm-autofill-session"),
    path("slcm-autofill/sessions/<uuid:session_id>/confirm", slcm_autofill_confirm, name="slcm-autofill-confirm"),
    path("slcm-autofill/popup/<str:token>", slcm_autofill_popup, name="slcm-autofill-popup"),
    path(
        "calculator-gpa/<str:given_semester>",
        gpa_calculator_with_semester,
        name="gpa-calculator-with-semester",
    ),
    path("course-semester", course_semester, name="course-semester"),
    path(
        "course-semester/<str:course_id>",
        course_semester_with_course_id,
        name="course-with-id",
    ),
    path("course-component", course_component, name="course-component"),
    path("course-subcomponent", course_subcomponent, name="course-subcomponent"),
    path("tanya-teman", tanya_teman, name="tanya-teman"),
    path("jawab-teman", jawab_teman, name="jawab-teman"),
    path("device-tokens", device_token, name="device-token"),
    path("notifications", notifications, name="notifications"),
    path(
        "notifications/unread-count",
        notification_unread_count,
        name="notification-unread-count",
    ),
    path(
        "notifications/read-all",
        notifications_read_all,
        name="notifications-read-all",
    ),
    path(
        "notifications/<int:notification_id>/read",
        notification_read,
        name="notification-read",
    ),
] + router.urls
