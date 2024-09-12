from pathlib import Path

from django.contrib import messages
from django.db.models import QuerySet
from django.shortcuts import HttpResponse
from django.template.loader import render_to_string

from icecream import ic

from demo.assignments.models import Assignment
from signoffs.core.approvals import AbstractApproval

WIDGET_DIR = Path("assignments/dashboard-widgets")
"""Htmx widgets directory for dashboard view"""


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


def render_new_messages(request):
    return render_to_string(WIDGET_DIR/"messages.html", {}, request)


def render_assignment_details(request, assignment: Assignment):
    return render_to_string(
        WIDGET_DIR/"assignment_details.html", {"assignment": assignment}, request=request,
    )


def render_assignment_selector(request, qs: QuerySet):
    ctx = {
        "page_title": "All Assignments",
        "empty_text": "There are no assignments",
        "assignments": qs,
    }
    return render_to_string(
        WIDGET_DIR/"list-assignments.html", context=ctx, request=request,
    )
