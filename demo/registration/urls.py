from django.urls import path

from . import views

urlpatterns = [
    path("signup/", views.signup_view, name="signup"),
    path(
        "signup/terms-of-service/", views.terms_of_service_view, name="terms_of_service"
    ),
    path("signup/newsletter/", views.newsletter_view, name="newsletter"),
    path(
        "signup/newsletter/revoke/<int:signet_pk>/",
        views.revoke_newsletter_view,
        name="revoke_newsletter",
    ),
    path("users/<username>/", views.user_profile_view, name="user_profile"),
]
