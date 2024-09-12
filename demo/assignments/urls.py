from django.urls import path

from . import views, htmx_views

app_name = "assignment"

urlpatterns = [
    path("new/", views.create_assignment_view, name="new"),
    path(
        "detail/<int:assignment_pk>/",
        views.assignment_detail_view,
        name="detail",
    ),
    path("all-assignments/", views.all_assignments_view, name="all_assignments"),
    path("my-assignments/", views.my_assignments_view, name="my_assignments"),
    path("dashboard/", htmx_views.dashboard_view, name="dashboard"),
]

widget_urlpatterns = [
    path("widget/list-assignments/", htmx_views.list_assignments, name="list-assignments"),
    path("widget/assignment-details/<int:assignment_pk>/", htmx_views.assignment_details, name="assignment-details"),
    path("widget/sign-signoff/", htmx_views.sign_assignment, name="sign-signoff"),
    path("widget/revoke-signoff/<int:signet_pk>/", htmx_views.revoke_signoff, name="revoke-signoff"),
    path("widget/refresh-messages/", htmx_views.refresh_messages, name="refresh-messages"),
    path("widget/erase-progress/<int:assignment_pk>/", htmx_views.erase_assignment_progress, name="erase-progress"),
]

urlpatterns += widget_urlpatterns
