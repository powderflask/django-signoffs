""" Default settings can be overridden in project settings """

from django.conf import settings

# Autodiscover all 'signoffs' modules in installed apps
# Module name to autodiscover 'signoffs' -  None to disable (e.g. if signoffs are defined in models.py)
SIGNOFFS_AUTODISCOVER_MODULE = getattr(
    settings, "SIGNOFFS_AUTODISCOVER_MODULE", "signoffs"
)

# dictionary or callable(signet) that returns default values for mutable signet fields.
SIGNOFFS_SIGNET_DEFAULTS = getattr(settings, "SIGNOFFS_SIGNET_DEFAULTS", None)

# SIGNOFFS_SETTING = getattr(settings, 'SIGNOFFS_SETTING', 'DEFAULT')
