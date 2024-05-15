from django.contrib.auth.models import User
from django.db import models

from signoffs.models import Signet, SignoffSet, SignoffSingle
from signoffs.signoffs import SignoffRenderer, SignoffUrlsManager, SimpleSignoff
from .signets import LikeSignet
from ..signoffs import publication_approval_signoff, publication_request_signoff


class Article(models.Model):
    class PublicationStatus(models.TextChoices):
        NOT_REQUESTED = "not_requested", "Publication Not Requested"
        PENDING = "pending", "Publication Pending"
        APPROVED = "approved", "Published"

    title = models.CharField(max_length=200, null=False, blank=False)
    author = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="article_author"
    )
    summary = models.TextField(max_length=100, null=False, blank=False)
    article_text = models.TextField(max_length=1000, null=False, blank=False)

    publication_request_signoff = SignoffSingle(publication_request_signoff)
    publication_approval_signoff = SignoffSingle(publication_approval_signoff)
    publication_status = models.CharField(
        max_length=25,
        choices=PublicationStatus.choices,
        default="not_requested",
        null=False,
        blank=False,
    )
    # is_published = models.BooleanField(default=False)
    # publish_signoff, publish_signet = SignoffField(publish_article_signoff)
    likes = SignoffSet(
        "like_signoff",
        signet_set_accessor="like_signatories",
    )

    def update_publication_status(self):
        status = self.PublicationStatus.NOT_REQUESTED
        # if self.publication_request_signoff:
        if self.publication_request_signoff.has_signed(
            self.author
        ):  # checking if this exists isn't enough since its revokable
            status = self.PublicationStatus.PENDING
            if self.publication_approval_signoff.exists():
                status = self.PublicationStatus.APPROVED
        self.publication_status = status

    def has_liked(self, user):
        return self.likes.has_signed(user=user)

    def __str__(self):
        if self.author.get_full_name() != "":
            return f"{self.author.get_full_name()} - {self.title}"
        else:
            return f"{self.author.username} - {self.title}"

    def delete(self, *args, **kwargs):
        # if self.is_published:
        #     self.publish_signet.delete()  # Delete the signet associated with the article
        super().delete(*args, **kwargs)  # Delete the article itself

    def total_likes(self):
        return self.likes.count()

    def is_author(self, user=None, username=None):
        if user is None and username is None:
            raise ValueError("Either user or username must be provided.")
        return self.author == user or self.author.username == username

    def get_author_name(self):
        if self.author.get_full_name() != "":
            return self.author.get_full_name()
        else:
            return self.author.username

    # def publish(self, user):
    #     self.is_published = True
    #     self.save()
    #     self.publish_signoff.sign_if_permitted(user)
    #     if self.publish_signoff.signatory:
    #         return True
    #     else:
    #         return False
    #
    # def unpublish(self, user):
    #     self.is_published = False
    #     self.save()
    #     self.publish_signoff.revoke_if_permitted(user)


# TODO: move Signets to signets and signoffs to signoffs
like_signoff = SimpleSignoff.register(
    id="like_signoff",
    signetModel=LikeSignet,
    sigil_label="Liked by",
    render=SignoffRenderer(signet_template="signoffs/like_signet.html"),
)


class Comment(models.Model):
    article = models.ForeignKey(Article, on_delete=models.CASCADE)
    author = models.ForeignKey(User, on_delete=models.CASCADE)
    comment_text = models.TextField(max_length=250)

    comment_signoff = SignoffSingle(
        "comment_signoff", signet_set_accessor="comment_signet"
    )

    def __str__(self):
        return f"Comment by {self.author.username} on {self.article.title}"


class CommentSignet(Signet):
    # TODO: Replace ForeignKey with SignoffUnique
    comment = models.ForeignKey(
        "Comment", unique=True, on_delete=models.CASCADE, related_name="comment_signet"
    )


comment_signoff = SimpleSignoff.register(
    id="comment_signoff",
    signetModel=CommentSignet,
    sigil_label="Posted by",
    render=SignoffRenderer(signet_template="signoffs/comment_signet.html"),
    urls=SignoffUrlsManager(revoke_url_name="article:revoke_comment"),
)
