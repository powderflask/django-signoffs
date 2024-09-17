from pathlib import Path

from django.contrib import messages
from django.db.models import QuerySet
from django.shortcuts import HttpResponse
from django.template.loader import render_to_string

from functools import partial

from icecream import ic

from demo.assignments.models import Assignment
from signoffs.core.approvals import AbstractApproval

WIDGET_DIR = Path("assignments/dashboard-widgets")
"""Htmx widgets directory for dashboard view"""


# partially just here to keep track of event names, but makes it convenient to add messages
EVENT_MESSAGES = {
    "signoffSigned": ("success", "Signoff Signed Successfully"),
    "signoffSignFailed": ("error", "Failed to sign signoff"),
    "signoffRevoked": ("success", "Signoff Revoked Successfully"),
    "signoffRevokeFailed": ("error", "Signoff Revoke Failed"),
    "approvalCompleted": ("success", "Approval Completed Successfully"),
    "approvalRevoked": ("success", "Approval Revoked Successfully"),
    "approvalRevokeFailed": ("error", "Failed to revoke approval"),
}
update_approval_trigger = "approvalUpdated"
update_signoff_trigger = "signoffUpdated"


def signoff_notify(request, event: str, override_message=None):
    tag = 'warning'
    item = EVENT_MESSAGES[event]
    if len(item) == 2 and isinstance(item, tuple):
        tag, message = item
    elif isinstance(item, str):
        message = item
    else:
        raise ValueError(f"Unknown event value: {event}")
    if override_message:
        message = override_message
    tag = getattr(messages, tag.upper())
    messages.add_message(request, tag, message)


# def render_items_to_str(request, *items, with_messages=True):
#     """Return one string of html for all items passed in"""
#     if not items:
#         return []
#     html = ""
#     for item in items:
#         if isinstance(item, Assignment):
#             html += render_assignment_details(request, item)
#
#         elif isinstance(item, QuerySet) and isinstance(item.first(), Assignment):
#             html += render_assignment_selector(request, item)
#
#         elif isinstance(item, AbstractApproval):
#             html += render_approval_widget(request, item)
#
#         elif with_messages and messages.get_messages(request):
#             html += render_new_messages(request)
#         else:
#             ic('failed to render', item)
#     return html


def render_new_messages(request, is_oob=True, notify=False):
    if notify:
        messages.info(request, "Loaded Messages")
    ctx = {"is_oob": is_oob}
    return render_to_string(WIDGET_DIR/"messages.html", ctx, request)


def render_assignment_details(request, assignment: Assignment, is_oob=True, notify=False, render_approval=True):
    if notify:
        messages.info(request, f"Loaded {assignment}")
    ctx = {
        "assignment": assignment,
        "is_oob": is_oob,
        "render_approval": render_approval,
    }
    return render_to_string(
        WIDGET_DIR/"assignment_details.html", ctx, request=request,
    )


def render_assignment_selector(request, qs: QuerySet, is_oob=True, notify=False):
    if notify:
        messages.info(request, "Loaded Assignments")
    ctx = {
        "page_title": "All Assignments",
        "empty_text": "There are no assignments.",
        "assignments": qs,
        "is_oob": is_oob,
    }
    return render_to_string(
        WIDGET_DIR/"list-assignments.html", context=ctx, request=request,
    )
