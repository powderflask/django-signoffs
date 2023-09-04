"""
    A Signoff defines the business logic for collecting a single "signature"
        - permissions, labels, etc.
    Signoff Types are registered subclasses of AbstractSignoff
        - they define the behaviour for a Signoff.
    Persistence layer for Signoff state is provided by a Signet model
        - one concrete Signet model can back any number of Signoff Types
        - can think of a Signoff instance as the "plugin behaviour" for a Signet instance.
"""
from typing import Callable, Type, Optional, Union

from django.apps import apps
from django.core.exceptions import ImproperlyConfigured, PermissionDenied
from django.utils.text import slugify

from signoffs.core import models, utils
from signoffs.core.renderers import SignoffRenderer
from signoffs.core.forms import SignoffFormsManager
from signoffs.core.urls import SignoffUrlsManager


# type definitions shorts
opt_str = Union[bool, Optional[str]]
opt_callable = Union[Type, Callable]
signet_type = Union[str, Type[models.AbstractSignet]]
revoke_type = Union[str, Type[models.AbstractRevokedSignet]]


# The business logic for signing and revoking a signoff may be dependent on context that can't be encoded in a Signoff
# Application logic may also need a way to sign or revoke without triggering Signoff permissions or signal logic.
# sign_signoff and revoke_signoff provides the default implementation for basic business logic for these operations.
# Implementors can override the behaviour by either overriding the class method or by injecting
#      a function with the same signature as the default implementations provided here...

def sign_signoff(signoff, user, commit=True, **kwargs):
    """
    Force signature onto given signoff for given user and save its signet, regardless of permissions or signoff state
    raises PermissionDenied otherwise (or whatever exception_type is given, e.g. ValidationError when saving forms)
    kwargs are passed directly to save - use commit=False to sign without saving.
    """
    signoff.signet.sign(user)
    signoff.signet.update(defaults=True, **signoff.get_signet_defaults(user))
    if commit:
        signoff.save(**kwargs)
    return signoff


def revoke_signoff(signoff, user, reason='', revokeModel=None, **kwargs):
    """
    Force revoke the given signoff for user regardless of permissions or signoff state.

    @param revokeModel: if supplied, create record of revocation, otherwise just delete the signet.
    """
    if revokeModel:
        return revokeModel.objects.create(signet=signoff.signet, user=user, reason=reason)
    else:
        signoff.signet.delete()
        signoff.signet.id = None


class DefaultSignoffBusinessLogic:
    """
    Defines the business logic for Signing and Revoking a Signoff instance
    """
    # Base permission and injectable logic for signing a signoff. Falsy for unrestricted
    perm: opt_str = ''                           # e.g. 'signet.add_signet',
    sign_method: Callable = sign_signoff         # injectable implementation for signing algorithm

    # Base permission and injectable logic for revoking a signoff. False to make irrevocable;  None (falsy) to use perm
    revoke_perm: opt_str = ''                    # e.g. 'signet.delete_signet',
    revoke_method: Callable = revoke_signoff     # injectable implementation for revoke signoffs algorithm

    def __init__(self, perm=None, sign_method=None,
                       revoke_perm=None, revoke_method=None):
        """ Override default actions, or leave parameter None to use class default """
        self.perm = perm if perm is not None else self.perm
        self.sign_method = sign_method or type(self).sign_method  # don't bind sign_method to self here
        self.revoke_perm = revoke_perm if revoke_perm is not None else self.revoke_perm
        self.revoke_method = revoke_method or type(self).revoke_method  # don't bind revoke_method to self here

    # Make it easy to mix together business logic pieces in inline declarations
    @classmethod
    def mixin(cls, *mixins):
        """ Return a subclass of this class with the given mixin classes mixed in """
        # TODO: use functional syntax and build a suitable name for each class
        class MixedLogic(*mixins, cls):
            pass
        return MixedLogic

    # Signing Actions / Rules

    def is_permitted_signer(self, signoff_type, user):
        """ return True iff user has permission to sign a signoff of given type """
        return user is not None and user.id and (user.has_perm(self.perm) if self.perm else True)

    def can_sign(self, signoff, user):
        """ return True iff the signoff instance can be signed by given user """
        return not signoff.is_signed() and self.is_permitted_signer(type(signoff), user)

    def sign_if_permitted(self, signoff, user, commit=True, **kwargs):
        """
        Sign signoff for given user and save signet, if self.can_sign(user)
        raises PermissionDenied otherwise
        kwargs are passed directly to save - use commit=False to sign without saving.
        """
        if not self.can_sign(signoff, user):
            raise PermissionDenied('User {user} is not allowed to sign {signoff}'.format(user=user, signoff=signoff))
        return self.sign(signoff, user, commit, **kwargs)

    def sign(self, signoff, user, commit=True, **kwargs):
        """
        Sign signoff for given user and save signet, regardless of permissions signoff state - careful!
        kwargs are passed directly to save - use commit=False to sign without saving.
        """
        return self.sign_method(signoff, user, commit=commit, **kwargs)

    # Revoke Actions / Rules

    def is_permitted_revoker(self, signoff_type, user):
        """ return True iff user has permission to revoke signoffs of given type """
        revoke_perm = self.revoke_perm or self.perm
        return False if self.revoke_perm is False else \
            user.has_perm(revoke_perm) if revoke_perm else True

    def can_revoke(self, signoff, user):
        """ return True iff the signoff can be revoked by given user """
        return signoff.is_signed() and self.is_permitted_revoker(type(signoff), user)

    def revoke_if_permitted(self, signoff, user, reason='', **kwargs):
        """ Revoke the signoff for user if they have permission, otherwise raise PermissionDenied """
        if not self.can_revoke(signoff, user):
            raise PermissionDenied(f'User {user} does not have permission to revoke {signoff.signet}')
        return self.revoke(signoff, user, reason, **kwargs)

    def revoke(self, signoff, user, reason='', **kwargs):
        """ Revoke the signoff regardless of permissions or signoff state - careful! """
        kwargs.setdefault('revokeModel', signoff.revoke_model)
        return self.revoke_method(signoff, user, reason=reason, **kwargs)


SignoffLogic = DefaultSignoffBusinessLogic    # Give it a nicer name


class AbstractSignoff:
    """
    Defines the semantics for a specific type of Signoff
        - what is it, how is it labelled, what permission is required to sign or revoke it, etc.
        - default meta-data values can be overridden by subclasses or passed to .register() factory
    A Signoff Type (class) defines the behaviours for a specific type of signoff.
        - define and register new Signoff Types with:: `BaseSignoff.register(...)`
    A Signoff instance represents a single User's "sigil", persisted by a Signet model instance.
    Signoff types are stored in code, not in the DB, as they define application logic, not application data.
        - they are registered in the signoffs.registry.signoffs where they can be retrieved by id
    Signet records are stored in DB with a reference to Signoff.id - be cautious not to change or delete in-use id's!
    """
    # id must be unique per type class, but human-legible / meaningful - dotted path recommended e.g. 'myapp.signoff'
    id: str = 'signoff.abstract'  # unique identifier for type - used like FK, don't mess with these!

    # signetModel is required - every Signoff Type must supply a concrete Signet model to provide persistence layer
    signetModel: signet_type = None   # concrete Signet Model class or 'app.model' string - REQUIRED

    # Signoff business logic, actions, and permissions
    logic: SignoffLogic = DefaultSignoffBusinessLogic()

    # revokeModel is optional - if provided, revoked signoff "receipts" will be kept, otherwise the signoff is deleted.
    revokeModel: revoke_type = None   # concrete RevokeSignet model class, if revoked signoffs should be tracked

    # Define visual representation for signoffs of this Type. Label is a rendering detail, but common override.
    label: str = ''         # Label for form field (i.e., checkbox) e.g. 'Report reviewed', empty string for no label
    render: SignoffRenderer = SignoffRenderer()   # object that knows how to render a signoff
    forms: SignoffFormsManager = SignoffFormsManager()   # object with Forms to sign and revoke this signoff type
    urls: SignoffUrlsManager = SignoffUrlsManager()      # default object, replace with one that has actual urls, if needed

    # Registration for Signoff Types (sub-classes)

    @classmethod
    def register(cls, id, **kwargs):
        """
        Create, register, and return a new subclass of cls with overrides for given kwargs attributes
        Standard mechanism to define new Signoff types, typically in my_app/models.py or my_app/signoffs.py
            MySignoff = AbstractSignoff.register('my_signoff_type', label='Sign it!', ...)
        """
        from signoffs import registry
        class_name = utils.id_to_camel(id)
        kwargs['id'] = id
        signoff_type = type(class_name, (cls,), kwargs)
        registry.signoffs.register(signoff_type)
        return signoff_type

    @classmethod
    def validate(cls):
        """ Run any class validation that must pass before class can be registered.  Invoked by registry. """
        if cls.signetModel is None:
            raise ImproperlyConfigured('Signoff Type {id} must specify a Signet Model.'.format(id=cls.id))
        return True

    # Signoff Type accessors

    @classmethod
    def get_signetModel(cls):
        """ Always use this accessor as the signetModel attribute may be an "app.Model" label """
        if not cls.signetModel:
            raise ImproperlyConfigured('No Signet Model associated with Signoff {cls}.'.format(cls=cls))
        if isinstance(cls.signetModel, str):
            cls.signetModel = apps.get_model(cls.signetModel)
        return cls.signetModel

    @classmethod
    def get_signet_queryset(cls):
        """ Return a base (unfiltered) queryset of ALL signets for this Signoff Type """
        return cls.get_signetModel().objects.filter(signoff_id=cls.id)

    @classmethod
    def get_revoked_signets_queryset(cls):
        """ Return a base (unfiltered) queryset of ALL revoked signets for this Signoff Type """
        return cls.get_signetModel().revoked_signets.filter(signoff_id=cls.id)

    @classmethod
    def get_revokeModel(cls):
        """ Always use this accessor as the revokeModel attributed may be an "app.Model" label """
        if isinstance(cls.revokeModel, str):
            cls.revokeModel = apps.get_model(cls.revokeModel)
        return cls.revokeModel

    @classmethod
    def get(cls, queryset=None, **filters):
        """
        Return the saved signoff that matches filters or a new signoff with these initial values if none exists
        Raises MultipleObjectsReturned if more than one signoff matches filter criteria.
        """
        SignetModel = cls.get_signetModel()
        queryset = queryset or SignetModel.objects.all()
        filters['signoff_id'] = cls.id
        try:
            return queryset.get(**filters).signoff
        except SignetModel.DoesNotExist:
            return cls(**filters)

    # Signoff Type behaviours

    @classmethod
    def create(cls, user, **kwargs):
        """ Create and return a signoff signed by given user """
        signoff = cls(**kwargs)
        signoff.sign(user=user)
        return signoff

    # Signoff instance behaviours

    def __init__(self, signet=None, subject=None, **kwargs):
        """
        Construct a Signoff instance backed by the given signet or an instance of cls.signetModel(**kwargs)
        subject is optional: the object this signoff is signing off on - set by SignoffField but otherwise unused.
       """
        if signet and kwargs:
            raise ImproperlyConfigured('Construct signoff with either existing signet OR creation kwargs, not both.')
        self.signet = signet or self.get_new_signet(**kwargs)
        self._subject = subject
        if not self.signet.signoff_id == self.id:
            raise ImproperlyConfigured('Signoff Type {self} does not match Signet Model {id}.'.format(
                self=self, id=self.signet.signoff_id))
    @property
    def subject(self):
        """
        The object being signed off on, if provided.
        Sub-classes with signet FK relations may want to override this to access the signet related object.
        subject is set by model Fields for convenient access to owner obj, but value is not used by any core logic.
        """
        return self._subject

    @property
    def slug(self):
        """ A slugified version of the signoff id, for places where a unique identifier slug is required """
        return slugify(self.id)

    @property
    def signet_model(self):
        """ return the signoff model for this type """
        return self.get_signetModel()

    @property
    def revoke_model(self):
        """ return the revoke model for this type """
        return self.get_revokeModel()

    def get_new_signet(self, **initial_values):
        """ Get a new, unsaved signet instance for this signoff type, with given optional initial values """
        Signet = self.signet_model
        return Signet(
            signoff_id=self.id,
            **{k: v for k, v in initial_values.items() if k not in Signet.read_only_fields}
        )

    def __str__(self):
        return str(self.signet)

    def __eq__(self, other):
        return isinstance(other, AbstractSignoff) and self.id == other.id and self.signet == other.signet

    def matches(self, other):
        """ Return True iff this signoff is of same type as other, which may be a signoff instance or a str """
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
        """ return True iff user has permission to sign a signoff of this Type """
        return cls.logic.is_permitted_signer(cls, user)

    def can_sign(self, user):
        """ return True iff this signoff instance can be signed by given user """
        return self.logic.can_sign(self, user)

    def sign_if_permitted(self, user, commit=True, **kwargs):
        """
        Sign for given user and save signet, if self.can_sign(user), raise PermissionDenied otherwise
        kwargs are passed directly to sign_method - use commit=False to sign without saving.
        """
        return self.logic.sign_if_permitted(self, user, commit=commit, **kwargs)

    def sign(self, user, commit=True, **kwargs):
        """
        Sign for given user and save signet, regardless of permissions or signoff state
        kwargs are passed directly to sign_method - use commit=False to sign without saving.
        """
        return self.logic.sign(self, user, commit=commit, **kwargs)

    @classmethod
    def is_permitted_revoker(cls, user):
        """ return True iff user has permission to revoke signoffs of this Type """
        return cls.logic.is_permitted_revoker(cls, user)

    def can_revoke(self, user):
        """ return True iff this signoff can be revoked by given user """
        return self.logic.can_revoke(self, user)

    def revoke_if_permitted(self, user, reason='', **kwargs):
        """ Revoke this signoff for user if they have permission, otherwise raise PermissionDenied """
        return self.logic.revoke_if_permitted(self, user, reason, **kwargs)

    def revoke(self, user, reason='', **kwargs):
        """ Revoke this signoff regardless of permissions or signoff state - careful! """
        return self.logic.revoke(self, user, reason, **kwargs)

    # Signet Delegation

    @property
    def signatory(self):
        """ Return the user who signed, or AnonymousUser if signed but no signatory, None if not yet signed """
        return self.signet.signatory

    @property
    def sigil(self):
        """ Return the "sigil" on this signoff if it is signed, None otherwise """
        return self.signet.sigil if self.is_signed() else None

    @property
    def sigil_label(self):
        """ Return a label for the "sigil" on this signoff, if it is signed, None  otherwise """
        return self.signet.sigil_label if self.is_signed() else None

    @property
    def timestamp(self):
        """ Return the timestamp on this signoff if it is signed, None otherwise """
        return self.signet.timestamp if self.is_signed() else None

    def has_user(self):
        """ return True iff this signoff has a user-relation """
        return self.signet.has_user()

    def can_save(self):
        """ return True iff this signoff's signet is ready to be saved """
        return self.signet.can_save() and self.can_sign(self.signet.user)

    def update(self, **attrs):
        """ Update signet model fields with any attrs that match by name """
        self.signet.update(**attrs)
        return self

    def validate_save(self):
        """ Raise PermissionDenied if this Signoff cannot be saved, otherwise just pass. """
        if not self.can_sign(self.signet.user):
            raise PermissionDenied(
                'User {u} does not have permission to save {s}'.format(u=self.signet.user, s=self))

    def save(self, *args, **kwargs):
        """ Attempt to save a Signet with the provided associated data for this Signoff """
        self.validate_save()
        self.signet.save(*args, **kwargs)
        return self

    def is_signed(self):
        """ return True if this Signoff has a persistent representation """
        return self.signet.is_signed()

    def is_revoked(self):
        """ return True if this Signoff has been revoked """
        return self.revokeModel and self.signet.is_revoked()

    @classmethod
    def has_object_relation(cls):
        return cls.get_signetModel().has_object_relation()


class BaseSignoff(AbstractSignoff):
    """
    A base Signoff Type to be used as base class or to register concrete Signoff Types
    Concrete Types will require a concrete Signet Model to back the signoff.  Add a permission to restrict who can sign.
    """
    id = 'signoffs.base-signoff'
    signetModel = None                  # Concrete signetModel must be defined for registered Signoffs
    revokeModel = None                  # revoking a signet just deletes it unless a revokeModel is provided
    perm = None                         # unrestricted - any user can sign this
    label = 'I consent'
