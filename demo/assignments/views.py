"""
CRUD and list views for Assignment app
"""
from django.contrib import messages
from django.shortcuts import HttpResponseRedirect, get_object_or_404, render, reverse

from .forms import AssignmentForm
from .models import Assignment


def create_assignment_view(request):
    if not request.user.is_staff:
        messages.error(
            request, "You must be registered as staff to create a new assignment."
        )
    form = AssignmentForm

    if request.method == "POST":
        form = form(request.POST)
        if form.is_valid():
            assignment = form.save()
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


def assignment_detail_view(request, assignment_id):
    if not request.user.is_staff:
        messages.error(
            request, "You must be registered as staff to create a new project."
        )

    assignment = get_object_or_404(Assignment, pk=assignment_id)
    if request.method == "POST":
        return assignment_signoffs_view(request, assignment_id)
    else:
        context = {"assignment": assignment}
        return render(request, "assignments/assignment_detail.html", context=context)


def assignment_signoffs_view(request, assignment_id):
    assignment = get_object_or_404(Assignment, pk=assignment_id)
    if request.method == "POST":
        if request.user == assignment.assigned_to or request.user.is_staff:
            signoff = assignment.approval.get_next_signoff(for_user=request.user)
            signoff_form = signoff.forms.get_signoff_form(request.POST)
            if signoff_form.is_valid():
                signoff_form.sign(request.user)
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
