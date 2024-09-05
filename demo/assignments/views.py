"""
CRUD and list views for Assignment app
"""
from django.contrib import messages
from django.contrib.auth.decorators import (
    login_required,
    user_passes_test,
    permission_required,
)
from django.shortcuts import HttpResponseRedirect, get_object_or_404, render, reverse

from .forms import AssignmentForm
from .models import Assignment
from ..registration import permissions


@login_required
@user_passes_test(permissions.has_signed_terms, login_url="terms_of_service")
@permission_required(
    "is_staff",
    login_url="my_assignments",
    raise_exception="Only staff users may create assignments",
)
def create_assignment_view(request):
    if not request.user.is_staff:
        messages.error(
            request, "You must be registered as staff to create a new assignment."
        )
    form = AssignmentForm

    if request.method == "POST" and request.user.is_staff:
        form = form(request.POST)
        if form.is_valid():
            assignment = form.save(commit=False)
            assignment.assigned_by = request.user
            assignment.save()
            return HttpResponseRedirect(
                reverse("assignment:detail", args=(assignment.id,))
            )
    context = {
        "form": form,
    }
    return render(
        request,
        "assignments/create_assignment.html",
        context=context,
    )


@login_required
@user_passes_test(permissions.has_signed_terms, login_url="terms_of_service")
def assignment_detail_view(request, assignment_id):
    assignment = get_object_or_404(Assignment, pk=assignment_id)
    # signoff = assignment.approval.get_next_signoff(for_user=request.user)
    if request.method == "POST":  # and signoff:
        return sign_assignment_view(request, assignment_id)
    else:
        context = {"assignment": assignment}  # , "signoff": signoff}
        return render(request, "assignments/assignment_detail.html", context=context)


@login_required
@user_passes_test(permissions.has_signed_terms, login_url="terms_of_service")
def sign_assignment_view(request, assignment_id):
    assignment = get_object_or_404(Assignment, pk=assignment_id)
    signoff = assignment.approval.get_next_signoff(for_user=request.user)
    if request.method == "POST" and signoff:
        signoff_form = signoff.forms.get_signoff_form(request.POST)
        if signoff_form.is_valid():
            signoff.sign(request.user, commit=True)
            assignment.bump_status()
            assignment.save()
        else:
            messages.error(request, "You do not have permission to sign this signoff")
    return HttpResponseRedirect(reverse("assignment:detail", args=(assignment.id,)))


# List views


def my_assignments_view(request):
    page_title = "My Assignments"
    empty_text = "You have no assignments"
    return assignment_list_base_view(
        request, page_title, empty_text, assigned_to=request.user
    )


def all_assignments_view(request):
    page_title = "All Assignments"
    empty_text = "There are no assignments"
    return assignment_list_base_view(request, page_title, empty_text)


@login_required
@user_passes_test(permissions.has_signed_terms, login_url="terms_of_service")
def assignment_list_base_view(
    request, page_title=None, empty_text=None, **filter_kwargs
):
    empty_text = empty_text or "Assignments will appear here."
    if filter_kwargs:
        assignments = Assignment.objects.filter(**filter_kwargs)
    else:
        assignments = Assignment.objects.all()
    context = {
        "assignments": assignments,
        "page_title": page_title,
        "empty_text": empty_text,
    }
    return render(request, "assignments/assignment_list_view.html", context=context)
