"""
Views related to user registration, ToS, and subscriptions
"""
from django.contrib import messages
from django.contrib.auth import authenticate, login
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render

from signoffs.shortcuts import get_signoff_or_404

from ..article.models.models import Article
from .forms import SignupForm
from .signoffs import newsletter_signoff, terms_signoff

# Registration & Profile views


def signup_view(request):
    if request.method == "POST":
        form = SignupForm(request.POST)

        if form.is_valid():
            form.save()  # Create new user

            username = form.cleaned_data.get("username")
            password = form.cleaned_data.get("password1")
            user = authenticate(username=username, password=password)

            login(request, user)  # Login new user

            return redirect("terms_of_service")

    else:
        form = SignupForm()

    return render(request, "registration/signup.html", {"form": form})


@login_required
def user_profile_view(request, username):
    user = request.user
    terms_so = terms_signoff.get(user=user)
    newsletter_so = newsletter_signoff.get(user=user)
    verified_so = None

    drafts = Article.objects.filter(author=user, publication_status="not_requested")
    my_articles = Article.objects.filter(author=user, publication_status="pending")
    my_published_articles = Article.objects.filter(
        author=user, publication_status="published"
    )
    liked_articles = Article.objects.filter(like_signatories__user=user)

    context = {
        "terms_so": terms_so,
        "newsletter_so": newsletter_so,
        "verified_so": verified_so,
        "drafts": drafts,
        "my_articles": my_articles,
        "my_published_articles": my_published_articles,
        "liked_articles": liked_articles,
    }
    return render(request, "registration/user_profile.html", context)


# ToS and Subscriptions views


@login_required
def terms_of_service_view(request):
    user = request.user
    next_page = request.GET.get("next") or ("user_profile", user.username)

    signoff = terms_signoff.get(user=user)

    if request.method == "POST":
        signoff_form = signoff.forms.get_signoff_form(request.POST)
        if signoff_form.is_signed_off():
            signoff.sign(user)
            return redirect(*next_page)
        else:
            messages.error(request, "You must agree to the Terms of Service.")

    return render(request, "registration/terms_of_service.html", {"signoff": signoff})


@login_required
def newsletter_view(request):
    user = request.user

    signoff = newsletter_signoff.get(user=user)

    if request.method == "POST":
        signoff_form = signoff.forms.get_signoff_form(request.POST)
        if signoff_form.is_signed_off():
            signoff.sign(user)
            return redirect("newsletter")
        else:
            messages.error(
                request, "You must check the box to sign up for our newsletter."
            )

    return render(request, "registration/newsletter.html", {"signoff": signoff})


@login_required
def revoke_newsletter_view(request, signet_pk):
    signoff = get_signoff_or_404(newsletter_signoff, signet_pk)
    signoff.revoke_if_permitted(
        user=request.user, reason="I no longer wish to receive the newsletter."
    )

    return redirect(request.META.get("HTTP_REFERER", "newsletter"))
