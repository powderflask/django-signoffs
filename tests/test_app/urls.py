from django.conf import settings
from django.urls import include, path

import signoffs.urls
from tests.test_app import views

# ensure signoff_id converter is registered - how should a reusable app ensure its converters are registered?
SignoffIdConverter = signoffs.urls.SignoffIdConverter


# Views for interactive testing
urlpatterns = [
    path(
        "signoff/<id:signoff_id>/<int:pk>/detail/",
        view=views.SignoffDetailView.as_view(),
        name="detail",
    ),
    path(
        "approval/<id:approval_id>/<int:pk>/detail/",
        view=views.ApprovalDetailView.as_view(),
        name="detail",
    ),
    path("", include("signoffs.urls")),
    path("auth/", include("django.contrib.auth.urls")),
]


if settings.DEBUG:
    from django.contrib.staticfiles.urls import staticfiles_urlpatterns

    urlpatterns += staticfiles_urlpatterns()
