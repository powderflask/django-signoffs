from django.urls import path

from . import views

app_name = "assignment"

urlpatterns = [
    path("new/", views.create_assignment_view, name="new"),
    path(
        "detail/<int:assignment_id>/",
        views.assignment_detail_view,
        name="detail",
    ),
    path("all-assignments/", views.all_assignments_view, name="all_assignments"),
    path("my-assignments/", views.my_assignments_view, name="my_assignments"),
]
