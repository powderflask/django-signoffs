"""
A form for collecting approval signoffs
"""
from django import forms

from signoffs.core.forms import AbstractSignoffForm

from .models import Signet as ApprovalSignet


class ApprovalSignoffForm(AbstractSignoffForm):
    """Form for collecting approval signoffs"""

    class Meta(AbstractSignoffForm.Meta):
        model = ApprovalSignet
        widgets = {
            "stamp": forms.HiddenInput,
        }
