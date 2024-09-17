from pprint import pprint

from django.contrib.auth.decorators import login_required
from django.core.handlers.wsgi import WSGIRequest
from django.http import HttpResponse
from django.shortcuts import render, get_object_or_404
from django.template.loader import render_to_string
from django.views.decorators.http import require_POST, require_http_methods
from django.contrib import messages
from functools import partial
from icecream import ic

from demo.assignments.approvals import NewAssignmentApproval
from demo.assignments.widget_helpers import (
    WIDGET_DIR,
    signoff_notify,
    render_new_messages,
    render_assignment_selector,
    render_assignment_details
)
from signoffs.core.models.fields import ApprovalField
from signoffs.models import ApprovalSignet
from demo.assignments.models import Assignment
from signoffs.shortcuts import get_approval_or_404


# Change behviour to update individual pieces rather then entire assignment-details. show messages after everything that has messages
# use hx-patch on elements that should be updated?


def get_request(request) -> tuple[WSGIRequest, bool]:
    """Return a tuple `request, is_htmx` where request is the htmx request if `is_htmx`"""
    is_htmx = False
    if hasattr(request, "htmx"):
        htmx_request = request.htmx.request
        is_htmx = True
        return htmx_request, is_htmx
    return request, is_htmx


@login_required
def dashboard_view(request):
    assignments = Assignment.objects.all()
    ctx = {
        "assignments": assignments,
        "render_approval": True,
        "is_oob": False
    }
    return render(
        request, "assignments/dashboard.html", ctx
    )


def update_oob_content(request):  # add behaviour to update headers before sending request from the front end
    request, _ = get_request(request)
    ic(request)
    return HttpResponse("Hello")

# def update_from_submission(request):
#     html = "\n".join([
#         # assignment.approval.render(request_user=request.user, request=request),
#         render_assignment_details(request, assignment),
#         render_assignment_selector(request, Assignment.objects.all(), notify=True) if signed else "",
#         render_new_messages(request)
#     ])


def sign_approval_signoff(request):
    request, _ = get_request(request)
    # ic([item for item in request.POST.items()])
    approval = get_approval_or_404(request.POST['approval_type'], pk=request.POST['stamp'])
    assignment = get_object_or_404(Assignment, pk=request.POST['subject_pk'])
    approval.subject = assignment
    form = approval.get_posted_signoff_form(request.POST, request.user)

    if not (form and form.is_valid()):
        ic(approval.next_signoffs(for_user=request.user))
        messages.warning(request, f'You do not have permission to sign this signoff.')

    elif not form.is_signed_off():
        messages.warning(request, f'You must check the box to sign.')

    else:
        if signet := form.sign(user=request.user):
            assignment.bump_status()
            messages.success(request, f'{signet.signoff.id} signed successfully!')
        else:
            messages.error(request, "Error signing form. Please don't try again later.")

    return HttpResponse(
        approval.render(request_user=request.user, request=request) +
        render_assignment_selector(request, Assignment.objects.all()) +
        render_assignment_details(request, assignment, render_approval=False) +
        render_new_messages(request)
    )


# TODO: use DELETE method
@require_http_methods(['POST'])
def revoke_signoff(request, signet_pk):
    request, _ = get_request(request)
    signet = get_object_or_404(ApprovalSignet, pk=signet_pk)
    assignment = get_object_or_404(Assignment, pk=request.POST['subject_pk'])
    signet.signoff.revoke_if_permitted(user=request.user)
    if not signet.id:
        assignment.bump_status(decrease=True)
        messages.success(request, "Signoff revoked!")
    else:
        messages.error(request, "Failed to revoke signoff.")
    return HttpResponse(
        # request must be supplied to underlying `render_to_string()`,
        # otherwise the csrf_token will not be rendered (renders as `none` instead)
        assignment.approval.render(request_user=request.user, request=request) +
        render_assignment_selector(request, Assignment.objects.all()) +
        render_assignment_details(request, assignment, render_approval=False) +
        render_new_messages(request)
    )


def assignment_details(request, assignment_pk):
    request, _ = get_request(request)
    assignment = get_object_or_404(Assignment, pk=assignment_pk)
    return HttpResponse(
        render_assignment_details(request, assignment, is_oob=False) +
        render_new_messages(request),
    )


def list_assignments(request):
    assignments = Assignment.objects.all()
    html = "\n".join([
        # assignment.approval.render(request_user=request.user, request=request),
        render_assignment_details(request, assignments.first()),
        render_assignment_selector(request, assignments, is_oob=False),
        render_new_messages(request)
    ])
    return HttpResponse(html)


def refresh_messages(request):
    new_messages = messages.get_messages(request)
    return HttpResponse(render_to_string(WIDGET_DIR/"messages.html", dict(new_messages=new_messages), request))


@require_http_methods(['DELETE'])
def erase_assignment_progress(request, assignment_pk):
    request, _ = get_request(request)
    assignment = get_object_or_404(Assignment, pk=assignment_pk)
    assignment.erase_progress()
    assignment.approval_stamp = assignment.approval.stamp
    assignment.approval_stamp.save()
    messages.success(request, f"Cleared all signoff data for {assignment.assignment_name}")
    return HttpResponse(
        render_assignment_selector(request, Assignment.objects.all()) +
        render_assignment_details(request, assignment, render_approval=True, is_oob=False) +
        render_new_messages(request)
    )


# @require_POST
# def sign_signoff(request):
#     request, is_htmx = get_request(request)
#     s_cls = registry.get_signoff_type(request.POST["signoff_id"])
#     form = s_cls.forms.get_signoff_form(request.POST)
#
#     if form.is_signed_off() and form.is_valid():
#         signet = form.sign(request.user)
#         if signet:
#             messages.success(request, f'{s_cls.id} signed successfully!')
#         else:
#             messages.error(request, f'Error signing {s_cls.id}')
#
#     if approval_id := request.POST.get('approval_id'):
#         approval = get_approval_or_404(approval_id, pk=request.POST['stamp'])
#         html_content = approval.render(request_user=request.user)
#         messages.info(request, f'Updated approval {approval.id}')
#     else:
#         html_content = signet.signoff.render(request_user=request.user)
#
#     if is_htmx:
#         html_content += render_to_string(WIDGET_DIR/"messages.html", {}, request)
#     return HttpResponse(html_content)


# test buttons


def test_messages(request):
    request, _ = get_request(request)

    messages.info(request, "Info First")
    messages.error(request, "Error Second")
    messages.success(request, "Success Third")

    messages_html = render_new_messages(request)
    return HttpResponse(messages_html)
