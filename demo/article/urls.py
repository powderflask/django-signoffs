from django.urls import path

from . import views

app_name = "article"

urlpatterns = [
    path("new/", views.new_article_view, name="new"),
    path(
        "delete/<int:article_id>/",
        views.delete_article_view,
        name="delete",
    ),
    path("edit/<int:article_id>/", views.edit_article_view, name="edit"),
    path("like-article/<int:article_id>/", views.like_article_view, name="like"),
    path(
        "detail/<int:article_id>/",
        views.article_detail_view,
        name="detail",
    ),
    path(
        "detail/revoke-comment/<int:signet_pk>/",
        views.revoke_comment_view,
        name="revoke_comment",
    ),
    path(
        "detail/add-comment/<int:article_id>/",
        views.add_comment,
        name="add_comment",
    ),
    path(
        "detail/request-publication/<int:article_id>/",
        views.request_publication_view,
        name="request_publication",
    ),
    path(
        "detail/revoke-publication-request/<int:signet_pk>/",
        views.revoke_publication_request_view,
        name="revoke_publication_request",
    ),
    path(
        "detail/approve-publication/<int:article_id>/",
        views.approve_publication_view,
        name="approve_publication",
    ),
    path(
        "detail/revoke-publication-approval/<int:signet_pk>/",
        views.revoke_publication_approval_view,
        name="revoke_publication_approval",
    ),
    path("all-articles/", views.all_articles_view, name="all_articles"),
    path("liked-articles/", views.all_liked_articles_view, name="liked_articles"),
    path("my-articles/", views.my_articles_view, name="my_articles"),
    path(
        "pending-requests/",
        views.pending_publication_requests,
        name="publication_requests",
    ),
]
