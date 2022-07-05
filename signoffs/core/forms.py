"""
Forms for collecting signoffs.
The challenge here is that the Signet form itself is just a labelled checkbox - it doesn't display any model fields.
Yet, it should behave like a model form, defining a signoff instance once validated.
And the form is only displayed when there is no instance - you can't edit a saved signoff, only revoke it.
So these forms don't have an instance - they are only used to "add" a signoff.
Yet, the form is being used to sign off on something specific, so it likely needs a relation to something concrete.
And the form needs an association to the Signoff Type so it can be rendered correctly.

So, a concrete form will likely need to be associated with a concrete object unless it is unambiguous from the context.
This gets quite tricky when multiple signoffs are collected in a formset - ensuring each form is associated with the
   related data it is signing-off on is critical.
"""
import typing
from django import forms
from django.core.exceptions import ValidationError, PermissionDenied

from signoffs.core import signoffs


class SignoffField(forms.BooleanField):
    """
    Collects one Signet for a particular Signoff type.
    A Signoff type object must be supplied as the first argument.
    Defaults to optional (users can accept form without signing off - set required=True explicitly for required signoff.
    Default label is signoff_type.label

    Value of field is None (no signoff) or a Signoff object that needs to be associated with a User object
      and any other relations required for the signoff (i.e., relation to object being signed off)
    """

    def __init__(self, signoff_type: typing.Type[signoffs.AbstractSignoff],
                 *, required=False, label=None, **kwargs):
        label = label or signoff_type.label
        super().__init__(required=required, label=label, **kwargs)
        self.signoff_type = signoff_type

    def clean(self, value):
        """ Returns an incomplete signoff instance of the correct type, or None if not signed off """
        value = super().clean(value)
        return self.signoff_type() if value else None


class AbstractSignoffForm(forms.Form):
    """ Abstract Base class for the signoff_form_factory """
    signoff = SignoffField(signoffs.BaseSignoff)
    signoff_id = forms.Field(widget=forms.HiddenInput)

    def __init__(self, *args, **kwargs):
        """ As per normal form, accepts 'user' as optional kwarg: the user who is signing off """
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)

    def _validate_permission(self, signoff, exception_type):
        """ Validate that this signoff ready to save with a user object that has permission to do so. """
        if not signoff.can_save():
            raise exception_type(
                "User {u} is not permitted to signoff on {so}".format(u=self.user, so=signoff)
            )

    def clean(self):
        """ Add user to signoff, if supplied, and validate they can save the signoff """
        cleaned_data = super().clean()
        signoff = cleaned_data.get('signoff')

        if signoff and not signoff.id == cleaned_data.get('signoff_id'):
            raise ValidationError("Invalid signoff form - signoff type does not match form")

        if signoff and self.user:
            signoff.update(user=self.user)
            self._validate_permission(signoff, ValidationError)

    def is_signed_off(self):
        """ return True iff this form is signed off """
        return self.is_valid() and self.cleaned_data.get('signoff') is not None

    def save(self, commit=True, **signet_attrs):
        """
        Save the signoff created by this form, with the extra signet attributes
        Raises ValueError if the form does not validate or PermissionDenied signoff has invalid/no user
        returns the saved signoff instance, or None if the signoff was not actually saved.
        """
        if not self.is_valid():
            raise ValueError("Attempt to save an invalid form.  Always call is_valid() before saving!")

        if self.is_signed_off():
            signoff = self.cleaned_data.get('signoff')
            signoff.update(**signet_attrs)
            if commit:
                self._validate_permission(signoff, PermissionDenied)
                signoff.save()
            return signoff
        # nothing to do if it's not actually signed...


def signoff_form_factory(signoff_type, signoff_field_class=SignoffField, signoff_field_kwargs=None,
                         baseForm=AbstractSignoffForm, form_prefix=None,):
    """
    Returns a Form class suited to collecting a signoff.
    Not unlike modelform_factory, except the model is provided by the signoff_type.
    baseForm can be overridden to add additional fields and/or fully customize validation and save logic.
    Validation ensures the type of signoff in POST matches the type provided.
    If a user object is passed to form, validation also ensures user has permission to sign off.
    Saving this form with a User performs a permissions check and adds the signoff, if required.
    """
    signoff_field_kwargs = signoff_field_kwargs or {}

    class SignoffForm(baseForm):
        prefix = form_prefix

        signoff = signoff_field_class(signoff_type=signoff_type, **signoff_field_kwargs)
        signoff_id = forms.CharField(initial=signoff_type.id, widget=forms.HiddenInput)

    return SignoffForm
