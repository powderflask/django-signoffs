"""
Forms for collecting and revoking signoffs.

Challenges:
 - the `Signet` form itself is just a labelled checkbox - it doesn't display any model fields.
   Yet, it should behave like a model form, defining a signoff instance once validated.
 - the form is only displayed when there is no instance - you can't edit a saved signoff, only revoke it.
   So these forms don't have an instance - they are only used to "add" a signoff.
 - the form itself likely needs an association to the Signoff Type so it can be rendered correctly.
 - so, the signoff type itself might be obtained from the request data (e.g., in a generic view)
   So if the request is bad, it may not be possible to construct a Form class to validate rest of data.

Signets with relations:
The form is being used to sign off on something specific, so it likely needs a relation to some concrete object.
So the view will need some way to know which object is being signed off on.

To solve this for concrete `Signets` with relational fields, try ONE of these approaches:
  - pre-create the signoff instance, with relations in place, and pass it to the form.
    The `Signet` instance, with its relations, will be saved if form validates and is signed.
  - specialize `AbstractSignoffForm` to add hidden fields with the extra relation data;
    Use initial data to populate these fields and
    be sure to override `clean()` to validate the extra data.
"""
from typing import Callable, Type, Union

from django import forms
from django.core.exceptions import ImproperlyConfigured, ValidationError

from signoffs.core.utils import class_service

opt_callable = Union[Type, Callable]


class AbstractSignoffForm(forms.ModelForm):
    """Abstract Base class for the signoff_form_factory"""

    signed_off = forms.BooleanField(label="I consent", required=False)
    signoff_id = forms.Field(widget=forms.HiddenInput, required=True)

    class Meta:
        model = None  # Concrete Forms must supply the signoff's signetModel: signoff.get_signetModel()
        exclude = ["user", "sigil", "sigil_label", "timestamp"]

    def __init__(self, *args, instance=None, **kwargs):
        """
        Form accepts an optional signoff, used like the instance parameter for ModelForms to pass initial values.
        Form also accepts 'user' as optional kwarg: the user who is signing off
        """
        if instance and instance.is_signed():
            raise ValueError(f"Attempt to edit a signed signoff! {instance}")
        self.signoff_instance = instance
        super().__init__(
            *args, instance=instance.signet if instance else None, **kwargs
        )

    def is_signed_off(self):
        """return True iff this form is signed off"""
        return self.is_valid() and self.cleaned_data.get("signed_off")

    def clean(self):
        """
        Validate signoff for consistency with the instance form was intialized with.

        :::{note}
        Don't be tempted to check permissions here!  The form is clean even if user doesn't have permission!
        :::
        """
        cleaned_data = super().clean()

        # the signoff returned from cleaned_data must match the form's signoff instance
        id = cleaned_data.get("signoff_id")
        if self.signoff_instance is not None and self.signoff_instance.id != id:
            raise ValidationError(
                f"Invalid signoff form - signoff type {type(self.signoff_instance)} does not match form {id}"
            )

        return cleaned_data

    def sign(self, user, commit=True):
        """
        Sign and save this form for the given user, without checking permissions (no business logic invoked!)

        :return: the saved signoff instance, or None if the signoff was not actually signed.

        :::{note}
        If signoff has m2m relations and commit==False, caller is responsible to call self.save_m2m()
        :::
        """
        signet = super().save(commit=False)
        if self.is_signed_off() and signet:
            signoff = signet.signoff
            signoff.sign(user=user, commit=commit)
            return signoff
        # nothing to do if it's not actually signed...

    def save(self, *args, **kwargs):
        """Disable normal form save() method - signoff forms must be signed by a user"""
        raise ImproperlyConfigured("Use the sign() method to save signoff forms!")


def signoff_form_factory(
    signoff_type,
    baseForm=AbstractSignoffForm,
    form_prefix=None,
    signoff_field_kwargs=None,
):
    """
    Returns a Form class suited to collecting a signoff.
    Not unlike modelform_factory, except the model is provided by the signoff_type.
    baseForm can be overridden to add additional fields and/or fully customize validation and save logic.
    Validation ensures the type of signoff in POST matches the type provided.
    Signing this form with a User performs a permissions check and saves the signoff, if required.
    """
    signoff_field_kwargs = signoff_field_kwargs or {}
    signoff_field_kwargs.setdefault("label", signoff_type.label)
    signoff_field_kwargs.setdefault("required", False)

    class SignoffForm(baseForm):
        class Meta(baseForm.Meta):
            model = signoff_type.get_signetModel()

        prefix = form_prefix

        signed_off = forms.BooleanField(**signoff_field_kwargs)

        signoff_id = forms.CharField(initial=signoff_type.id, widget=forms.HiddenInput)

    return SignoffForm


class AbstractSignoffRevokeForm(forms.Form):
    """
    Form used to validate requests to revoke a signoff - not really intended to be user-facing.
    Not intended to collect signoffs, but rather simply to house the validation logic for revoke requests,
        which may be delete rather than post requests.
    It is not a ModelForm so it remains as generic as possible, though in many ways a Signet ModelForm might be useful.
    """

    signoff_id = forms.CharField(widget=forms.HiddenInput)
    signet_pk = forms.IntegerField(widget=forms.HiddenInput)

    def __init__(self, *args, **kwargs):
        """
        Form requires the signetModel class of the signet to be revoked
        """
        super().__init__(*args, **kwargs)

    def _get_signoff_type(self):
        from signoffs import registry

        try:
            return registry.get_signoff_type(self.cleaned_data.get("signoff_id"))
        except ImproperlyConfigured as e:
            raise ValidationError(str(e))

    def _get_signet(self, signoff_type):
        signetModel = signoff_type.get_signetModel()
        try:
            return signetModel.objects.get(pk=self.cleaned_data.get("signet_pk"))
        except signetModel.DoesNotExist as e:
            raise ValidationError(str(e))

    def clean(self):
        """
        Validate the signoff type for the form's signet matches the form's signoff type

        :::{note}
        Don't be tempted to check permissions here!  The form is clean even if user doesn't have permission!
        :::
        """
        cleaned_data = super().clean()
        signoff_type = self._get_signoff_type()
        signet = self._get_signet(signoff_type) if signoff_type else None
        if not signoff_type or not signet or not signet.signoff_id == signoff_type.id:
            raise ValidationError(
                f"Invalid signoff type {signoff_type} does not match form signet {signet}"
            )

        signoff_instance = signet.signoff
        cleaned_data["signoff"] = signoff_instance
        return cleaned_data

    def revoke(self, user, commit=True):
        """
        Revoke the signoff validated by this form, and return the revoked signoff,
        without checking permissions (no business logic invoked!)

        If commit is False, the form is validated and the signoff to be revoked is returned - up to you to revoke it.
        """
        if not self.is_valid():
            raise ValueError(
                "Attempt to save an invalid form.  Always call is_valid() before saving!"
            )

        signoff = self.cleaned_data.get("signoff")
        if not user or not signoff:
            raise ValueError(
                f"Invalid User {user} or signoff {signoff} for revoke operation."
            )
        if commit:
            signoff.revoke(user)
        return signoff

    def save(self, *args, **kwargs):
        """Disable normal form save() method - signoff forms must be signed by a user"""
        raise ImproperlyConfigured("Use the revoke() method to revoke signoff forms!")


def revoke_form_factory(
    signoff_type,
    baseForm=AbstractSignoffRevokeForm,
    form_prefix=None,
    signoff_field_kwargs=None,
):
    """
    Returns a Form class suited to validation a signoff revoke request.
    Not unlike modelform_factory, except the model is provided by the signoff_type.
    baseForm can be overridden to add additional fields and/or fully customize validation and save logic.
    Validation ensures the type of signoff in POST matches the type provided.
    Revoking this form with a User performs a permissions check and deletes the signoff's signet, if required.
    """

    class SignoffRevokeForm(baseForm):
        prefix = form_prefix

        signoff_id = forms.CharField(initial=signoff_type.id, widget=forms.HiddenInput)

    return SignoffRevokeForm


class SignoffTypeForms:
    """Manage the forms used by a particular signoff type - usually injected using a FormsManager service"""

    signoff_form: opt_callable = AbstractSignoffForm
    """baseForm type passed to signoff_form_factory or a callable that returns a Form subclass"""

    revoke_form: opt_callable = AbstractSignoffRevokeForm
    """baseForm type passed to revoke_form_factory or a callable that returns a Form subclass"""

    def __init__(self, signoff_type, signoff_form=None, revoke_form=None):
        self.signoff_type = signoff_type
        self.signoff_form = (
            signoff_form or type(self).signoff_form
        )  # don't bind forms to instance!
        self.revoke_form = revoke_form or type(self).revoke_form

    # Forms for collecting & revoking signoffs

    @staticmethod
    def _get_form_class(candidate):
        """candidate may be a Form subclass or a callable that returns one - return the Form subclass either way"""
        return (
            candidate()
            if callable(candidate) and not isinstance(candidate, type)
            else candidate
        )

    def get_signoff_form_class(self, **kwargs):
        """Return a form class suitable for collecting a signoff of this Type.  kwargs passed through to factory."""
        form = self._get_form_class(self.signoff_form)
        kwargs.setdefault("baseForm", form)
        return signoff_form_factory(signoff_type=self.signoff_type, **kwargs)

    def get_revoke_form_class(self, **kwargs):
        """Return a form class suitable for validating revoke request for a signoff of this Type."""
        form = self._get_form_class(self.revoke_form)
        kwargs.setdefault("baseForm", form)
        return revoke_form_factory(signoff_type=self.signoff_type, **kwargs)

    def get_signoff_form(self, data=None, **kwargs):
        """Return a form instance suited to collecting this signoff type for simple case, no factory args required"""
        return self.get_signoff_form_class()(data=data, **kwargs)

    def get_revoke_form(self, data=None, **kwargs):
        """Return a form instance suited to revoking this signoff type for simple case, no factory args required"""
        return self.get_revoke_form_class()(data=data, **kwargs)


class SignoffFormsManager(class_service(service_class=SignoffTypeForms)):
    """
    A descriptor class that "injects" a `SignoffTypeForms` instance into a Signoff instance.

    To inject custom form services:
      - provide a custom service_class:  `forms=SignoffFormsManager(service_class=MyInstanceForms)`
      - OR specialize class attributes:
        `MySignoffFormsManager = utils.service(SignoffTypeForms, signoff_form=mySignoffForm)`
      - OR both... `MySignoffFormsManager = utils.service(MyInstanceForms)`
    """


__all__ = [
    "AbstractSignoffForm",
    "signoff_form_factory",
    "AbstractSignoffRevokeForm",
    "revoke_form_factory",
    "SignoffTypeForms",
    "SignoffFormsManager",
]
