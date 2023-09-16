import sys

import django
from django.contrib.auth.models import User
from django.core.management.base import BaseCommand

from demo.assignments.models import Assignment


class Command(BaseCommand):
    help = "Populate demo data for the Editor app"

    def handle(self, *args, **options):
        self.create_assignments()
        self.stdout.write(
            self.style.SUCCESS("Demo Assignments data populated successfully")
        )

    def create_assignments(self):
        try:
            assignments_data = [
                {
                    "assignment_name": "Assignment 1",
                    "details": "Write an article on topic 1",
                    "assigned_to": User.objects.get(username="author1"),
                },
                {
                    "assignment_name": "Assignment 2",
                    "details": "Write an article on topic 2",
                    "assigned_to": User.objects.get(username="author2"),
                },
                {
                    "assignment_name": "Assignment 3",
                    "details": "Edit article on topic 3",
                    "assigned_to": User.objects.get(username="author3"),
                },
            ]
        except django.contrib.auth.models.User.DoesNotExist as e:
            error_message = f"""
{e}
No default users were found. Please run "python manage.py create_article_data and try again.
"""
            self.stdout.write(self.style.ERROR(error_message))
            sys.exit()

        for data in assignments_data:
            assignment = Assignment.objects.create(**data)
            staff_user = User.objects.get(username="editor1")
            assign_project_signoff = assignment.approval.get_next_signoff(
                for_user=staff_user
            )
            assign_project_signoff.sign(user=staff_user)
            author_user = data["assigned_to"]
            accept_project_signoff = assignment.approval.get_next_signoff(
                for_user=author_user
            )
            accept_project_signoff.sign(user=author_user)
