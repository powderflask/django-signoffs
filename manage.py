#!/usr/bin/env python
"""Django's command-line utility for administrative tasks."""
import os
import sys


def main():
    """Run administrative tasks."""
    # app = sys.argv[1] if len(sys.argv) > 0 else 'tests'
    # assert app in APPS, f"Invalid app argument: {app}, must be one of {APPS}"

    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'demo.settings')
    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "Couldn't import Django. Are you sure it's installed and "
            "available on your PYTHONPATH environment variable? Did you "
            "forget to activate a virtual environment?"
        ) from exc
    execute_from_command_line(sys.argv)


if __name__ == '__main__':
    main()
