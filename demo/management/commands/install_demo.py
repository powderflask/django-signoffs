from django.core import management
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Migrate the demo DB and install some sample data"

    def handle(self, *args, **options):
        management.call_command("migrate")
        management.call_command("create_article_data")
