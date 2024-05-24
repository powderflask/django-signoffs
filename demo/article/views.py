"""
Article CRUD, Comment, Publication, and utility Views
"""
from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.shortcuts import HttpResponseRedirect, get_object_or_404, redirect, render
from django.urls import reverse

from signoffs.shortcuts import get_signet_or_404

from ..registration import permissions
from .forms import ArticleForm, CommentForm
from .models.models import Article, Comment, comment_signoff
from .models.signets import ArticleSignet, LikeSignet
from .signoffs import publication_approval_signoff, publication_request_signoff

# Article CRUD views


@login_required
@user_passes_test(permissions.has_signed_terms, login_url="terms_of_service")
def new_article_view(request):
    user = request.user
    if request.method == "POST":
        print(request.POST)
        form = ArticleForm(request.POST)
        if form.is_valid():
            draft = form.save(commit=False)
            draft.author = user
            draft.save()
    else:
        form = ArticleForm()
    context = {"form": form, "article": Article()}
    return render(request, "article/new_article.html", context=context)


@login_required
def edit_article_view(request, article_id):
    article = get_object_or_404(Article, id=article_id)

    if request.method == "POST":
        form = ArticleForm(request.POST, instance=article)
        if form.is_valid():
            article = form.save(commit=False)
            article.author = request.user
            article.save()
            return redirect("article:detail", article.id)
    else:
        form = ArticleForm(instance=article)

    return render(
        request, "article/edit_article.html", {"form": form, "article": article}
    )


def article_detail_view(request, article_id):
    user = request.user

    article = Article.objects.get(id=article_id)
    article.update_publication_status()
    has_liked = article.likes.has_signed(user=user)
    comments = Comment.objects.filter(article=article)

    if request.method == "POST":
        if request.POST.get("signoff_id") == publication_request_signoff.id:
            return request_publication_view(request, article.id)
        elif request.POST.get("signoff_id") == publication_approval_signoff.id:
            return approve_publication_view(request, article.id)

    if article.publication_request_signoff.has_signed(article.author):
        pr_signoff = article.signatories.get(
            user=article.author, article=article
        ).get_signoff()
    else:
        pr_signoff = publication_request_signoff

    pa_signoff = publication_approval_signoff.get(
        article=article, signoff_id="publication_approval_signoff"
    )

    if not pa_signoff.is_signed():
        pa_signoff = publication_approval_signoff

    context = {
        "article": article,
        "form": CommentForm(),
        "user_has_liked": has_liked,
        "comments": comments,
        "publication_request_signoff": pr_signoff,
        "publication_approval_signoff": pa_signoff,
    }
    return render(request, "article/article_detail.html", context)


@login_required
def delete_article_view(request, article_id):
    article = get_object_or_404(Article, id=article_id)

    if request.method == "POST":
        article.delete()
        return redirect("article:my_articles")
    else:
        return render(request, "article/delete_article.html", {"article": article})


# Article List views


def base_article_list_view(request, page_title=None, empty_text=None, **filter_kwargs):
    empty_text = empty_text or "Published articles will appear here."
    # filter_kwargs['is_published'] = True
    articles = Article.objects.filter(**filter_kwargs)
    context = {"articles": articles, "page_title": page_title, "empty_text": empty_text}
    return render(request, "article/article_list_view.html", context=context)


@login_required
def my_articles_view(request):
    return base_article_list_view(
        request,
        page_title="My Articles",
        empty_text="You haven't written any articles yet.",
        author=request.user,
    )


def all_articles_view(request):
    return base_article_list_view(
        request,
        page_title="All Articles",
        empty_text="Published articles will appear here.",
    )


@login_required
def all_liked_articles_view(request):
    return base_article_list_view(
        request,
        page_title="Liked Articles",
        empty_text="Articles you like will appear here.",
        like_signatories__user=request.user,
    )


@login_required
def request_publication_view(request, article_id):
    article = get_object_or_404(Article, id=article_id)
    signoff_form = article.publication_request_signoff.forms.get_signoff_form(
        request.POST
    )
    if signoff_form.is_valid() and signoff_form.is_signed_off():
        signet = signoff_form.sign(user=request.user, commit=False)
        signet.article = article
        signet.save()
        article.update_publication_status()
        article.save()
    return HttpResponseRedirect(reverse("article:detail", args=(article.id,)))


def revoke_publication_request_view(request, signet_pk):
    signet = get_signet_or_404(publication_request_signoff, signet_pk)
    signoff = signet.get_signoff()
    article = signet.article
    signoff.revoke_if_permitted(request.user, signet=signet)

    approval_signoff = publication_approval_signoff.get(
        article=article,
    )
    if approval_signoff.has_user():
        approval_signoff.revoke_if_permitted(
            request.user, reason="Publication Request Revoked"
        )

    return HttpResponseRedirect(reverse("article:detail", args=(article.id,)))


# Article Publication views


@login_required
def approve_publication_view(request, article_id):
    article = get_object_or_404(Article, id=article_id)

    if not request.user.is_staff or request.user == article.author:
        messages.error(
            request,
            "You do not have permission to approve this article for publication.",
        )
        return HttpResponseRedirect(reverse("article:detail", args=(article.id,)))

    signoff_form = article.publication_approval_signoff.forms.get_signoff_form(
        request.POST
    )

    if signoff_form.is_valid() and signoff_form.is_signed_off():
        signet = signoff_form.sign(user=request.user, commit=False)
        signet.article = article
        signet.save()
    return HttpResponseRedirect(reverse("article:detail", args=(article.id,)))


@login_required
def revoke_publication_approval_view(request, signet_pk):
    signet = get_object_or_404(ArticleSignet, id=signet_pk)
    signoff = signet.get_signoff()
    article = signet.article
    signoff.revoke_if_permitted(request.user)
    signet.delete()
    return HttpResponseRedirect(reverse("article:detail", args=(article.id,)))


@login_required
def pending_publication_requests(request):
    """Returns a queryset of pending publication requests."""
    if not request.user.is_staff:
        messages.error(
            request,
            "You must be a staff member to view the page you were trying to access",
        )
        return redirect("article:all_articles")

    return base_article_list_view(
        request,
        page_title="Pending Publication Requests",
        empty_text="There are no pending publication requests.",
        publication_status=Article.PublicationStatus.PENDING,
    )


# Comment and Like Article views


def add_comment(request, article_id):
    print(request.POST)
    user = request.user
    article = get_object_or_404(Article, id=article_id)
    if request.method == "POST":
        form = CommentForm(request.POST)
        if form.is_valid():
            comment = form.save(commit=False)
            comment.author = user
            comment.article = article
            comment.comment_signoff.create(user)
            comment.save()
            return HttpResponseRedirect(reverse("article:detail", args=(article.id,)))
        else:
            messages.error(
                request, "You must agree to the terms before posting your comment."
            )


@login_required
def revoke_comment_view(request, signet_pk):
    comment = get_signet_or_404(comment_signoff, signet_pk).comment
    comment.delete()
    return redirect(request.META.get("HTTP_REFERER", "article:all_articles"))


@login_required
def like_article_view(request, article_id):
    user = request.user
    article = get_object_or_404(Article, id=article_id)

    if article.likes.has_signed(user=user):
        like = LikeSignet.objects.get(
            signoff_id="like_signoff", article=article, user=user
        ).signoff
        like.revoke_if_permitted(user=user)
    else:
        article.likes.create(user=user)

    return redirect("article:detail", article.id)
