"""
Forms for collecting and revoking signoffs.
The challenge here is that the Signet form itself is just a labelled checkbox - it doesn't display any model fields.
Yet, it should behave like a model form, defining a signoff instance once validated.
And the form is only displayed when there is no instance - you can't edit a saved signoff, only revoke it.
So these forms don't have an instance - they are only used to "add" a signoff.
Yet, the form is being used to sign off on something specific, so it likely needs a relation to something concrete.
And the form needs an association to the Signoff Type so it can be rendered correctly.

To solve this for concrete signets with additional fields, try one of these approaches:
    - pre-create the signoff instance and pass it to the form.  That instance will be saved if form validates.
    or
    - specialize AbstractSignoffForm to add hidden fields with the extra data;
        override clean() to validate the extra data fields are as expected and save() to update the signet with values.
"""
from django import forms
from django.core.exceptions import ValidationError, ImproperlyConfigured

from signoffs import registry
from signoffs.core import signoffs


class AbstractSignoffForm(forms.Form):
    """ Abstract Base class for the signoff_form_factory """
    signed_off = forms.BooleanField(label=signoffs.AbstractSignoff.label, required=False)
    signoff_id = forms.Field(widget=forms.HiddenInput, required=True)

    def __init__(self, *args, signoff=None, **kwargs):
        """
        Form accepts an optional signoff, used like the instance parameter for ModelForms to pass initial values.
        Form also accepts 'user' as optional kwarg: the user who is signing off
        """
        self.signoff_instance = signoff
        self.user = kwargs.pop('user', None) or (signoff.signatory if signoff else None)
        super().__init__(*args, **kwargs)

    @property
    def signoff_type(self):
        try:
            return registry.get_signoff_type(self.cleaned_data['signoff_id'])
        except ImproperlyConfigured as e:
            raise ValidationError(str(e))

    def is_signed_off(self):
        """ return True iff this form is signed off """
        return self.is_valid() and self.cleaned_data.get('signed_off')

    def get_signoff(self):
        """ Return a signoff instance consitent with the data on the bound form - only if is_valid() and is_bound """
        return self.signoff_type() if self.is_signed_off() else None

    def clean(self):
        """
        Add user to signoff, if supplied, and validate signoff for consistency.
        Note: don't be tempted to check permissions here!  The form is clean even if user doesn't have permission!
        """
        cleaned_data = super().clean()
        signoff = self.get_signoff()

        if not signoff:  # Not signed, nothing to clean!
            return

        # the signoff returned from cleaned_data must match the form's signoff_id and type of the signoff field
        if (
            signoff.id != cleaned_data.get('signoff_id') or
            not isinstance(signoff, self.signoff_type) or
            not (self.signoff_instance == None or self.signoff_instance.id == signoff.id)
        ):
            raise ValidationError(f'Invalid signoff form - signoff type {type(signoff)} does not match form {self.signoff_field_type}')

        # if form was loaded with a signoff instance, preferentially return that one, which may be pre-loaded with other fields
        cleaned_data['signoff'] = self.signoff_instance or signoff
        return cleaned_data

    def save(self, commit=True, **signet_attrs):
        """
        Save the signoff created by this form, with the extra signet attributes
        Raises ValueError if the form does not validate or PermissionDenied signoff has invalid/no user
        returns the saved signoff instance, or None if the signoff was not actually saved.
        """
        if not self.is_valid():
            raise ValueError("Attempt to save an invalid form.  Always call is_valid() before saving!")
        user = signet_attrs.pop('user', self.user)
        if self.is_signed_off():
            signoff = self.cleaned_data.get('signoff')
            signoff.update(**signet_attrs)
            signoff.sign(user=user, commit=commit)
            return signoff
        # nothing to do if it's not actually signed...


def signoff_form_factory(signoff_type, baseForm=AbstractSignoffForm, form_prefix=None, signoff_field_kwargs=None):
    """
    Returns a Form class suited to collecting a signoff.
    Not unlike modelform_factory, except the model is provided by the signoff_type.
    baseForm can be overridden to add additional fields and/or fully customize validation and save logic.
    Validation ensures the type of signoff in POST matches the type provided.
    Saving this form with a User performs a permissions check and adds the signoff, if required.
    """
    signoff_field_kwargs = signoff_field_kwargs or {}
    signoff_field_kwargs.setdefault('label', signoff_type.label)

    class SignoffForm(baseForm):
        prefix = form_prefix

        signed_off = forms.BooleanField(**signoff_field_kwargs)

        signoff_id = forms.CharField(initial=signoff_type.id, widget=forms.HiddenInput)

    return SignoffForm
