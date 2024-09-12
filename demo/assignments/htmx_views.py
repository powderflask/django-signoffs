from pprint import pprint

from django.contrib.auth.decorators import login_required
from django.core.handlers.wsgi import WSGIRequest
from django.http import HttpResponse
from django.shortcuts import render, get_object_or_404
from django.template.loader import render_to_string
from django.views.decorators.http import require_POST, require_http_methods
from django.contrib import messages
from icecream import ic

from demo.assignments.widget_helpers import (
    render_new_messages,
    render_assignment_selector,
    render_assignment_details
)
from signoffs.models import ApprovalSignet
from signoffs import registry
from signoffs.shortcuts import get_approval_or_404, get_signoff_or_404, get_signet_or_404

from demo.assignments.models import Assignment
from .widget_helpers import WIDGET_DIR
from pathlib import Path




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
    messages.info(request, 'Loaded Dashboard')
    return render(
        request, "assignments/dashboard.html", {"assignments": assignments}
    )


def sign_assignment(request):
    request, _ = get_request(request)
    assignment = get_object_or_404(Assignment, pk=request.POST["subject_pk"])  # request.POST['subject_cls']
    form = assignment.approval.get_posted_signoff_form(request.POST, request.user)

    if not (form and form.is_valid()):
        messages.warning(request, f'You do not have permission to sign this signoff.')
    elif not form.is_signed_off():
        messages.warning(request, f'You must check the box to sign.')
    else:
        if signet := form.sign(user=request.user):
            messages.success(request, f'{signet.signoff.id} signed successfully!')
            assignment.bump_status()
        else:
            messages.error(request, "Error signing form. Please don't try again later.")

    html = render_assignment_details(request, assignment)

    # html = "\n".join([
        # assignment.approval.render(request_user=request.user, request=request),
        # render_assignment_details(request, assignment),
        # render_assignment_selector(request, Assignment.objects.all()),
    # ])
    # print(html)
    return HttpResponse(
        html,
        headers={
            'HX-Retarget': '#assignment-details',
            'HX-Reswap': 'outerHTML',
            'HX-Trigger': 'update-messages, update-approval'
        }
    )


@require_http_methods(['POST'])
def revoke_signoff(request, signet_pk):
    request, _ = get_request(request)
    ic(request.POST)
    signet = get_object_or_404(ApprovalSignet, pk=signet_pk)
    assignment = get_object_or_404(Assignment, pk=request.POST['subject_pk'])
    signet.signoff.revoke_if_permitted(user=request.user)
    if signet.is_revoked():
        assignment.bump_status(increase=False)
        messages.success(request, "Signoff revoked!")
    else:
        messages.error(request, "Failed to revoke signoff.")
    return HttpResponse(
        headers={
            "HX-Trigger": "update-messages, update-approval",
            # "HX-Retarget": "closest div.signoffs.approval",
        }
    )


def assignment_details(request, assignment_pk):
    assignment = get_object_or_404(Assignment, pk=assignment_pk)
    messages.info(request, f"Loaded {assignment.assignment_name}")
    return HttpResponse(
        render_assignment_details(request, assignment),
        headers={"HX-Trigger": "update-messages"},
    )


def list_assignments(request):
    assignments = Assignment.objects.all()
    return HttpResponse(render_assignment_selector(request, assignments))


def refresh_messages(request):
    new_messages = messages.get_messages(request)
    return HttpResponse(render_to_string(WIDGET_DIR/"messages.html", dict(new_messages=new_messages), request))


@require_http_methods(['DELETE'])
def erase_assignment_progress(request, assignment_pk):
    request, _ = get_request(request)
    assignment = get_object_or_404(Assignment, pk=assignment_pk)
    assignment.erase_progress()
    messages.success(request, f"Cleared all signoff data for {assignment.assignment_name}")
    return HttpResponse(
        'Reloading Page...',
        headers={'HX-Refresh': 'true', 'HX-Trigger': 'update-messages'}
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
