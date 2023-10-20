"""
    A Signoff defines the business and presentation logic for collecting a single "signature"

    Signoff Types are registered subclasses of AbstractSignoff
        - they define the behaviour for a Signoff.
    Persistence layer for Signoff state is provided by a Signet model
        - one concrete Signet model can back any number of Signoff Types
        - can think of a Signoff instance as the strategy for managing a Signet instance.
"""
from typing import Callable, Optional, Type, Union

from django.apps import apps
from django.core.exceptions import ImproperlyConfigured, PermissionDenied
from django.utils.text import slugify

from signoffs.core import models, utils
from signoffs.core.forms import SignoffFormsManager
from signoffs.core.renderers import SignoffRenderer
from signoffs.core.urls import SignoffUrlsManager

# type definitions shorts
opt_str = Union[bool, Optional[str]]
opt_callable = Union[Type, Callable]
signet_type = Union[str, Type[models.AbstractSignet]]
revoke_type = Union[str, Type[models.AbstractRevokedSignet]]


# The business logic for signing and revoking a signoff may be dependent on context that shouldn't be encoded in a Signoff
# Application logic may also need a way to sign or revoke without triggering Signoff permissions or signal logic.
# sign_signoff and revoke_signoff provide the default implementations for basic business logic for these operations.
# Implementors can override the behaviour by either overriding the class method or by injecting
#      a function with the same signature as the default implementations provided here...


def sign_signoff(signoff, user, commit=True, **kwargs):
    """
    Force signature onto given signoff for given user and save its signet, regardless of permissions or signoff state

    kwargs are passed directly to save - use commit=False to sign without saving.
    """
    signoff.signet.sign(user)
    signoff.signet.update(defaults=True, **signoff.get_signet_defaults(user))
    if commit:
        signoff.save(**kwargs)
    return signoff


def revoke_signoff(signoff, user, reason="", revokeModel=None, **kwargs):
    """
    Force revoke the given signoff for user regardless of permissions or signoff state.

    @param revokeModel: if supplied, create record of revocation, otherwise just delete the signet.
    """
    if revokeModel:
        return revokeModel.objects.create(
            signet=signoff.signet, user=user, reason=reason
        )
    else:
        signoff.signet.delete()
        signoff.signet.id = None


class DefaultSignoffBusinessLogic:
    """
    Defines the default business logic for signing and revoking a `Signoff` instance

    :::{note}
    `SignoffBusinessLogic` should *not* encode contextual (e.g., approval or approval process) business logic.
    :::
    """

    # Base permission and injectable logic for signing a signoff. Falsy for unrestricted
    perm: opt_str = ""  # e.g. 'signet.add_signet',
    sign_method: Callable = sign_signoff  # signing algorithm

    # Base permission and injectable logic for revoking a signoff. False to make irrevocable;  None (falsy) to use perm
    revoke_perm: opt_str = ""  # e.g. 'signet.delete_signet',
    revoke_method: Callable = revoke_signoff  # revoke signoffs algorithm

    def __init__(
        self, perm=None, sign_method=None, revoke_perm=None, revoke_method=None
    ):
        """Override default actions / permissions, or None to use class default"""
        self.perm = perm if perm is not None else self.perm
        self.sign_method = (
            sign_method or type(self).sign_method
        )  # don't bind sign_method to self here
        self.revoke_perm = revoke_perm if revoke_perm is not None else self.revoke_perm
        self.revoke_method = (
            revoke_method or type(self).revoke_method
        )  # don't bind revoke_method to self here

    # Make it easy to mix together business logic pieces in inline declarations
    @classmethod
    def mixin(cls, *mixins):
        """Return a subclass of this class with the given mixin classes mixed in"""

        # TODO: use functional syntax and build a suitable name for each class
        class MixedLogic(*mixins, cls):
            pass

        return MixedLogic

    # Signing Actions / Rules

    def is_permitted_signer(self, signoff_type, user):
        """Return True iff user has permission to sign a signoff of given type"""
        return (
            user is not None
            and user.id
            and (user.has_perm(self.perm) if self.perm else True)
        )

    def can_sign(self, signoff, user):
        """Return True iff the signoff instance can be signed by given user"""
        return not signoff.is_signed() and self.is_permitted_signer(type(signoff), user)

    def sign_if_permitted(self, signoff, user, commit=True, **kwargs):
        """
        Sign signoff for given user and save signet, if self.can_sign(user)
        raises PermissionDenied otherwise
        kwargs are passed directly to save - use commit=False to sign without saving.
        """
        if not self.can_sign(signoff, user):
            raise PermissionDenied(f"User {user} is not allowed to sign {signoff}")
        return self.sign(signoff, user, commit, **kwargs)

    def sign(self, signoff, user, commit=True, **kwargs):
        """
        Sign signoff for given user and save signet, regardless of permissions or signoff state - careful!

        kwargs are passed directly to save - use commit=False to sign without saving.
        Prefer to use `sign_if_permitted` to enforce business rules.
        """
        return self.sign_method(signoff, user, commit=commit, **kwargs)

    # Revoke Actions / Rules

    def is_permitted_revoker(self, signoff_type, user):
        """return True iff user has permission to revoke signoffs of given type"""
        revoke_perm = self.revoke_perm or self.perm
        return (
            False
            if self.revoke_perm is False
            else user.has_perm(revoke_perm)
            if revoke_perm
            else True
        )

    def can_revoke(self, signoff, user):
        """return True iff the signoff can be revoked by given user"""
        return signoff.is_signed() and self.is_permitted_revoker(type(signoff), user)

    def revoke_if_permitted(self, signoff, user, reason="", **kwargs):
        """Revoke the signoff for user if they have permission, otherwise raise PermissionDenied"""
        if not self.can_revoke(signoff, user):
            raise PermissionDenied(
                f"User {user} does not have permission to revoke {signoff.signet}"
            )
        return self.revoke(signoff, user, reason, **kwargs)

    def revoke(self, signoff, user, reason="", **kwargs):
        """
        Revoke the signoff regardless of permissions or signoff state - careful!

        kwargs are passed directly to concrete revoke_method.
        Prefer to use `revoke_if_permitted` to enforce business rules.
        """
        kwargs.setdefault("revokeModel", signoff.revoke_model)
        return self.revoke_method(signoff, user, reason=reason, **kwargs)


class SignoffLogic(DefaultSignoffBusinessLogic):
    """Public API: Alias for `DefaultSignoffBusinessLogic"""


class AbstractSignoff:
    """
    Defines the abstract semantics for a Signoff and serves as base class for all concrete Signoff Types.

    A `Signoff Type` (i.e. subclass of `AbstractSignoff`) defines the behaviours for a specific type of signoff.

    A `Signoff` instance represents a timestamped agreement by a `User`, persisted by a `Signet` model instance.
    Signoffs are pure code objects, not stored in the DB - they define application logic, not application data.
    A Signoff Type defines:
      - how the `Signet` is labelled and rendered,
      - what permission is required to sign or revoke it,
      - what forms are used to sign and revoke them, etc.
    The default meta-data and services can be overridden in a subclass or passed to .register() factory.
    Signoff Types are registered in the `signoffs.registry.signoffs` registry where they can be retrieved by id
    :::{caution}
    `Signet` records are stored in DB with a reference to `Signoff.id`
     Be cautions not to change or delete id's that are in-use.
    :::
    """

    # id must be unique per type class, but human-legible / meaningful - dotted path recommended e.g. 'myapp.signoff'
    id: str = "signoff.abstract"  # unique identifier for type - used like FK, don't mess with these!

    # signetModel is required - every Signoff Type must supply a concrete Signet model to provide persistence layer
    signetModel: signet_type = None  # concrete model or 'app.model' string - REQUIRED

    # Signoff business logic, actions, and permissions
    logic: SignoffLogic = DefaultSignoffBusinessLogic()

    # revokeModel is optional - if provided, revoked signoff "receipts" will be kept, otherwise the signoff is deleted.
    revokeModel: revoke_type = None  # concrete model, if revoked signoffs are tracked

    # Define visual representation for signoffs of this Type. Label is a rendering detail, but common override.
    label: str = ""  # Label for (checkbox) form field, empty string for no label
    render: SignoffRenderer = SignoffRenderer()  # presentation logic service
    forms: SignoffFormsManager = SignoffFormsManager()  # Forms service
    urls: SignoffUrlsManager = SignoffUrlsManager()  # service to provide endpoints

    # Registration for Signoff Types (a.k.a. subclasses)

    @classmethod
    def register(cls, id, **kwargs):
        """
        Create, register, and return a new subclass of cls with overrides for given kwargs attributes

        Standard mechanism to define new Signoff types, typically in `my_app/models.py` or `my_app/signoffs.py`
        Usage:
        ```
            MySignoff = AbstractSignoff.register('my_signoff_type', label='Sign it!', ...)
        ```
        """
        from signoffs import registry

        class_name = utils.id_to_camel(id)
        kwargs["id"] = id
        signoff_type = type(class_name, (cls,), kwargs)
        registry.signoffs.register(signoff_type)
        return signoff_type

    @classmethod
    def validate(cls):
        """Run any class validation that must pass before class can be registered.  Invoked by registry."""
        if cls.signetModel is None:
            raise ImproperlyConfigured(
                f"Signoff Type {cls.id} must specify a Signet Model."
            )
        return True

    # Signoff Type accessors

    @classmethod
    def get_signetModel(cls):
        """Always use this accessor as the signetModel attribute may be an "app.Model" label"""
        if not cls.signetModel:
            raise ImproperlyConfigured(
                f"No Signet Model associated with Signoff {cls}."
            )
        if isinstance(cls.signetModel, str):
            cls.signetModel = apps.get_model(cls.signetModel)
        return cls.signetModel

    @classmethod
    def get_signet_queryset(cls):
        """Return a base (unfiltered) queryset of ALL signets for this Signoff Type"""
        return cls.get_signetModel().all_signets.filter(signoff_id=cls.id)

    @classmethod
    def get_revoked_signets_queryset(cls):
        """Return a base (unfiltered) queryset of ALL revoked signets for this Signoff Type"""
        return cls.get_signetModel().revoked_signets.filter(signoff_id=cls.id)

    @classmethod
    def get_revokeModel(cls):
        """Always use this accessor as the revokeModel attributed may be an "app.Model" label"""
        if isinstance(cls.revokeModel, str):
            cls.revokeModel = apps.get_model(cls.revokeModel)
        return cls.revokeModel

    @classmethod
    def get(cls, queryset=None, **filters):
        """
        Return the saved signoff that matches filters or a new signoff with these initial values if none exists

        Raises `MultipleObjectsReturned` if more than one signoff matches filter criteria.
        """
        SignetModel = cls.get_signetModel()
        queryset = queryset or SignetModel.objects.all()
        filters["signoff_id"] = cls.id
        try:
            return queryset.get(**filters).signoff
        except SignetModel.DoesNotExist:
            return cls(**filters)

    # Signoff Type behaviours

    @classmethod
    def create(cls, user, **kwargs):
        """Create and return a signoff signed by given user"""
        signoff = cls(**kwargs)
        signoff.sign_if_permitted(user=user)
        return signoff

    # Signoff instance behaviours

    def __init__(self, signet=None, subject=None, **kwargs):
        """
        Construct a Signoff instance backed by the given signet or an instance of `cls.signetModel(**kwargs)`

        `subject` is optional: the object this signoff is signing off on - set by `SignoffField` but otherwise unused.
        """
        if signet and kwargs:
            raise ImproperlyConfigured(
                "Construct signoff with either existing signet OR creation kwargs, not both."
            )
        self.signet = signet or self.get_new_signet(**kwargs)
        self._subject = subject
        if not self.signet.signoff_id == self.id:
            raise ImproperlyConfigured(
                f"Signoff Type {self} does not match Signet Model {self.signet.signoff_id}."
            )

    @property
    def subject(self):
        """
        The object being signed off on, if provided.

        Subclass with signet FK relations may want to override this to access the signet related object.
        `subject` is set by model Fields for convenient access to owner obj, but value is not used by core logic.
        """
        return self._subject

    @subject.setter
    def subject(self, subject):
        self._subject = subject

    @property
    def slug(self):
        """A slugified version of the signoff id, for places where a unique identifier slug is required"""
        return slugify(self.id)

    @property
    def signet_model(self):
        """Return the signoff model for this type"""
        return self.get_signetModel()

    @property
    def revoke_model(self):
        """Return the revoke model for this type"""
        return self.get_revokeModel()

    def get_new_signet(self, **initial_values):
        """Get a new, unsaved signet instance for this signoff type, with given optional initial values"""
        Signet = self.signet_model
        return Signet(
            signoff_id=self.id,
            **{
                k: v
                for k, v in initial_values.items()
                if k not in Signet.read_only_fields
            },
        )

    def __str__(self):
        return str(self.signet)

    def __eq__(self, other):
        return (
            isinstance(other, AbstractSignoff)
            and self.id == other.id
            and self.signet == other.signet
        )

    def matches(self, other):
        """Return True iff this signoff is of same type as other, which may be a signoff instance or a str"""
        return self.id == other if isinstance(other, str) else self.id == other.id

    def get_signet_defaults(self, user):
        """
        Return a dictionary of default values for fields this signoff's signet -

        Called during signoff.sign - provides default values that will NOT override values already set on the signet.
        See signets.get_signet_defaults for further docs.
        """
        return {}  # default implementation uses signets.get_signet_defaults

    # Signoff / Revoke Business Logic Delegation

    @classmethod
    def is_permitted_signer(cls, user):
        """return True iff user has permission to sign a signoff of this Type"""
        return cls.logic.is_permitted_signer(cls, user)

    def can_sign(self, user):
        """return True iff this signoff instance can be signed by given user"""
        return self.logic.can_sign(self, user)

    def sign_if_permitted(self, user, commit=True, **kwargs):
        """
        Sign for given user and save signet, if self.can_sign(user), raise `PermissionDenied` otherwise

        `kwargs` are passed directly to sign_method - use `commit=False` to sign without saving.
        """
        return self.logic.sign_if_permitted(self, user, commit=commit, **kwargs)

    def sign(self, user, commit=True, **kwargs):
        """
        Sign for given user and save signet, regardless of permissions or signoff state

        `kwargs` are passed directly to sign_method - use `commit=False` to sign without saving.
        """
        return self.logic.sign(self, user, commit=commit, **kwargs)

    @classmethod
    def is_permitted_revoker(cls, user):
        """Return True iff user has permission to revoke signoffs of this Type"""
        return cls.logic.is_permitted_revoker(cls, user)

    def can_revoke(self, user):
        """Return True iff this signoff can be revoked by given user"""
        return self.logic.can_revoke(self, user)

    def revoke_if_permitted(self, user, reason="", **kwargs):
        """Revoke this signoff for user if they have permission, otherwise raise PermissionDenied"""
        return self.logic.revoke_if_permitted(self, user, reason, **kwargs)

    def revoke(self, user, reason="", **kwargs):
        """
        Revoke this signoff regardless of permissions or signoff state - careful!

        Prefer to use `revoke_if_permitted` to enforce business rules.
        """
        return self.logic.revoke(self, user, reason, **kwargs)

    # Signet Delegation

    @property
    def signatory(self):
        """Return the user who signed, or AnonymousUser if signed but no signatory, None if not yet signed"""
        return self.signet.signatory

    @property
    def sigil(self):
        """Return the "sigil" on this signoff if it is signed, None otherwise"""
        return self.signet.sigil if self.is_signed() else None

    @property
    def sigil_label(self):
        """Return a label for the "sigil" on this signoff, if it is signed, None  otherwise"""
        return self.signet.sigil_label if self.is_signed() else None

    @property
    def timestamp(self):
        """Return the timestamp on this signoff if it is signed, None otherwise"""
        return self.signet.timestamp if self.is_signed() else None

    def has_user(self):
        """return True iff this signoff has a user-relation"""
        return self.signet.has_user()

    def can_save(self):
        """return True iff this signoff's signet is ready to be saved"""
        return self.signet.can_save() and self.can_sign(self.signet.user)

    def update(self, **attrs):
        """Update signet model fields with any attrs that match by name"""
        self.signet.update(**attrs)
        return self

    def validate_save(self):
        """Raise PermissionDenied if this Signoff cannot be saved, otherwise just pass."""
        if not self.can_sign(self.signet.user):
            raise PermissionDenied(
                f"User {self.signet.user} does not have permission to save {self}"
            )

    def save(self, *args, **kwargs):
        """Attempt to save a Signet with the provided associated data for this Signoff"""
        self.validate_save()
        self.signet.save(*args, **kwargs)
        return self

    def is_signed(self):
        """return True if this Signoff has been signed but not revoked"""
        return self.signet.is_signed() and not self.is_revoked()

    def is_revoked(self):
        """return True if this Signoff has been revoked"""
        return self.revokeModel and self.signet.is_revoked()

    @classmethod
    def has_object_relation(cls):
        return cls.get_signetModel().has_object_relation()


class BaseSignoff(AbstractSignoff):
    """
    A base Signoff Type to be used as abstract base class to register concrete Signoff Types
    Concrete Types will require a concrete Signet Model to back the signoff.
    :::{tip}
    Register new Signoff Types with:: `BaseSignoff.register(...)`
    :::
    """

    id = "signoffs.base-signoff"
    signetModel = None  # Concrete signetModel must be defined for registered Signoffs
    revokeModel = None  # revoking just deletes Signet unless a revokeModel is provided
    label = "I consent"


__all__ = [
    "sign_signoff",
    "revoke_signoff",
    "AbstractSignoff",
    "BaseSignoff",
    "DefaultSignoffBusinessLogic",
    "SignoffLogic",
]
