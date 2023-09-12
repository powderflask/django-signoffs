"""
    Core signoffs framework - does not define any concrete models itself.
    Add contrib.signoffs and/or contrib.approvals to add out-of-the-box concrete models.
"""
from django.apps import AppConfig

from signoffs import settings


class SignoffsConfig(AppConfig):
    name = "signoffs"
    default = True
    default_auto_field = "django.db.models.BigAutoField"

    def ready(self):
        if settings.SIGNOFFS_AUTODISCOVER_MODULE:
            from django.utils.module_loading import autodiscover_modules

            autodiscover_modules(settings.SIGNOFFS_AUTODISCOVER_MODULE)
