"""
    contrib.signets adds basic concrete Signet and RevokedSignet models
"""
from django.apps import AppConfig


class ContribSignetsConfig(AppConfig):
    name = "signoffs.contrib.signets"
    label = "signoffs_signets"
    default = True
    default_auto_field = "django.db.models.BigAutoField"
