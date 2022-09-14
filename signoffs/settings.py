""" Default settings can be overridden in project settings """

from django.conf import settings

# Autodiscover all 'signoffs' modules in installed apps
# Module name to autodiscover 'signoffs' -  None to disable (e.g. if signoffs are defined in models.py)
SIGNOFFS_AUTODISCOVER_MODULE = getattr(settings, 'SIGNOFFS_AUTODISCOVER_MODULE', 'signoffs')

# value for on_delete in abstract signet models that have a FK to user.
# If you require models.SET_DEFAULT, you will need to override the signet model user ForeignKey explicitly
# Regardless of this setting, App logic always requires concrete user relation to sign / save, but not to view.
# Default SET_NULL is sensible for use-cases where signoff should persist even after user is deleted.
# Note: signoffs.contrib app migrations are based on the default setting - changing it will create a migration issue.
#       Hmmmm. probably best to inherit for Abstract base class and override this in concrete model rather than using this setting :-/
SIGNOFFS_ON_DELETE_USER = getattr(settings, 'SIGNOFFS_ON_DELETE_USER', 'SET_NULL')

# dictionary or callable(signet) that returns default values for mutable signet fields.
SIGNOFFS_SIGNET_DEFAULTS = getattr(settings, 'SIGNOFFS_SIGNET_DEFAULTS', None)

#
# SIGNOFFS_SETTING = getattr(settings, 'SIGNOFFS_SETTING', 'DEFAULT')
