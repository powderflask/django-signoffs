from django.db import models

from signoffs.models import Signet

# from article.models.models import Article

#
# class PublicationRequestSignet(Signet):
#     article = models.ForeignKey('Article', on_delete=models.CASCADE, related_name='pub_request_signatories', editable=False)
#
#
# class PublicationApprovalSignet(Signet):
#     article = models.ForeignKey('Article', on_delete=models.CASCADE, related_name='pub_approve_signatories', editable=False)


# class PublicationSignet(Signet):
#     article = models.ForeignKey('Article', on_delete=models.CASCADE, related_name='signatories', editable=False)


class ArticleSignet(Signet):
    article = models.ForeignKey(
        "Article", on_delete=models.CASCADE, related_name="signatories", editable=False
    )


class LikeSignet(Signet):
    article = models.ForeignKey(
        "Article",
        on_delete=models.CASCADE,
        related_name="like_signatories",
        editable=False,
    )
    # when related name is not "signatories", the altered related name must be specified when registering the signoff
    # see the like_signoff in article/signoffs as an example
