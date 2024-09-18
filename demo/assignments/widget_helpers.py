from pathlib import Path

from django.contrib import messages
from django.db.models import QuerySet
from django.middleware.csrf import get_token
from django.template.loader import render_to_string

from demo.assignments.models import Assignment

WIDGET_DIR = Path("assignments/dashboard-widgets")
"""Htmx widgets directory for dashboard view"""


def hx_render_approval(approval, **kwargs):
    ctx = dict(
        use_htmx=True,
        inherit_target=True,
        inherit_csrf=False,  # if False, token must be re-inserted below
        is_oob=False,
    )
    ctx.update(**kwargs)
    if request := kwargs.get('request'):  # TODO: fix csrf_token in the actual renderers
        _csrf_token = get_token(request)
        ctx.setdefault('csrf_token', _csrf_token)
    return approval.render(**ctx)


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
