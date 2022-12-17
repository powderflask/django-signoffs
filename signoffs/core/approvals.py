"""
    An Approval defines the "signing order" for a sequence of one or more Signoffs.
    Approval Types are registered subclasses of AbstractApproval
        - they define the behaviour for an Approval.
    Persistence layer for Approval state is provided by a Stamp model (think "Stamp of Approval" or TimeStamp)
        - one concrete Stamp model can back any number of Approval Types
        - can think of an Approval instance as the "plugin behaviour" for a Stamp instance.
"""
from typing import Callable, Type, Optional, Union

from django.apps import apps
from django.db import transaction
from django.core.exceptions import ImproperlyConfigured, PermissionDenied
from django.urls import reverse
from django.utils.text import slugify

from signoffs.core import models, utils
from signoffs.core.models import managers
from signoffs.core.renderers import ApprovalRenderer
from signoffs.core.status import ApprovalStatus
from signoffs.core.signing_order import SigningOrderManager


# type name shorts
opt_str = Union[bool, Optional[str]]
stamp_type = Union[str, Type[models.AbstractApprovalStamp]]


# The business logic for revoking an approval may be dependent on context that can't be encoded in an Approval
# Application logic may also need a way to revoke approvals without triggering Approval permission or signal logic.
# revoke_approval provides the default implementation for basic revoke business logic.
# Implementors can override the behaviour of Approval.revoke() by either overriding the class method or by injecting
#      a function with the same signature as the default implementation provided here...

def revoke_approval(approval, user, reason=''):
    """
    Force revoke the given approval for user regardless of permissions or approval state!
    Default implementation revokes ALL related signets on behalf of the user
    """
    with transaction.atomic():
        # First mark approval as no longer approved, b/c signoffs can't be revoked from approved approval
        approval.stamp.approved = False
        # Revoke all signoffs in reverse order
        for signoff in reversed(approval.signatories.signoffs()):
            signoff.revoke(user=user, reason=reason)

        approval.save()


class DefaultApprovalBusinessLogic:
    """
    Defines the business logic for Approving and Revoking an Approval instance
    """
    # Process / permissions to revoke an approval of this Type: False for irrevocable;  None (falsy) for unrestricted
    revoke_perm: opt_str = ''                   # e.g. 'approvals.delete_stamp'
    revoke_method: Callable = revoke_approval   # injectable implementation for revoke approval algorithm
    # Define URL patterns for revoking approvals
    revoke_url_name: str = ''

    def __init__(self, revoke_perm=None, revoke_method=None, revoke_url_name=None):
        """ Override default actions, or leave parameter None to use class default """
        self.revoke_perm = revoke_perm if revoke_perm is not None else self.revoke_perm
        self.revoke_method = revoke_method or type(self).revoke_method  # don't bind revoke_method to self here
        self.revoke_url_name = revoke_url_name or self.revoke_url_name

    # Approve Actions / Rules

    def can_sign(self, approval, user):
        """ return True iff the given user can sign any of the next signoffs required on the approval """
        return not approval.is_approved() and len(approval.next_signoffs(for_user=user)) > 0

    def ready_to_approve(self, approval):
        """ return True iff the approval's signing order is complete and ready to be approved """
        # Note: code duplicated in process.ApprovalProcess so function can be overriden with approval process logic here.
        return not approval.is_approved() and approval.is_complete()

    def approve_if_ready(self, approval):
        """ Approve and save the approval is it meets all ready conditions """
        if self.ready_to_approve(approval):
            self.approve(approval)

    def approve(self, approval, commit=True, **kwargs):
        """
        Approve the approval and save it's Stamp.   Prefer to use approve_if_ready to enforce business rules.
        No permissions or signoff completion logic involved here - just force into approved state!
        If self.is_approved() raises PermissionDenied -- can't approval an approved approval :-P
        kwargs passed directly to save() - use commit=False to approve without saving
        """
        if not approval.is_approved():
            approval.stamp.approve()
            if commit:
                approval.save(**kwargs)
        else:
            raise PermissionDenied('Attempt to approve approved approval {approval}'.format(approval=approval))

    # Revoke Actions / Rules

    def is_permitted_revoker(self, approval_type, user):
        """ return True iff user has permission to revoke approvals of given Type """
        revoke_perm = self.revoke_perm
        return False if self.revoke_perm is False else \
            user.has_perm(revoke_perm) if revoke_perm else True

    def can_revoke(self, approval, user):
        """ return True iff the approval can be revoked by given user """
        # Note: assumes a user with permission to revoke an approval would also have permission to revoke all signoffs within.
        # Note: code duplicated in process.ApprovalProcess so function can be overriden with approval process logic here.
        return approval.is_approved() and self.is_permitted_revoker(type(approval), user)

    def revoke(self, approval, user, reason=''):
        """ Revoke the approval for user if they have permission, otherwise raise PermissionDenied """
        if not approval.is_approved():
            raise PermissionDenied('Attempt to revoke unapproved approval {a}'.format(a=self))
        if not self.can_revoke(approval, user):
            raise PermissionDenied(
                'User {u} does not have permission to revoke approval {a}'.format(u=user, a=self))

        return self.revoke_method(approval, user, reason)

    def get_revoke_url(self, approval, args=None, kwargs=None):
        """ Return the URL for requests to revoke the approval """
        args = args or [approval.stamp.pk, ]
        kwargs = kwargs or {}
        return reverse(self.revoke_url_name, args=args, kwargs=kwargs) if self.revoke_url_name else ''


ApprovalLogic = DefaultApprovalBusinessLogic    # Give it a nicer name


class AbstractApproval:
    """
    Defines the signing order and semantics for an Approval
        - what is it, how is it labelled, what signoffs need to be  collected, in what sequence, etc.
        - default meta-data values can be overridden by subclasses or passed to .register() factory
    An Approval Type (class) defines the implementation for a specific type of approval.
        - define and register new Approval Types with factory method:: `BaseApproval.register(...)`
    The data for an Approval instance is backed and persisted by an ApprovalStamp and its related Signets.
    Approval Types are stored in code, not in the DB, as they define application logic, not application data.
        - they are registered in the signoffs.registry.approvals where they can be retrieved by id
    Stamp records are stored in DB with a reference to Approval.id - be cautious not to change or delete in-use id's!
    Signing Order Manager - default signing order is alphabetic, based on Signoff Fields / attribute defined on Approval
        - use ordering API on Approval instance over accessing signing_order directly!
    """
    # id must be unique per type class, but human-legible / meaningful - dotted path recommended e.g. 'myapp.approval'
    id: str = 'approval.abstract'  # unique identifier for type - used like FK, don't mess with these!

    # stampModel is required - every Approval Type must supply a concrete Stamp model to provide persistence layer
    stampModel: stamp_type = None     # concrete Approval Stamp Model class or 'app.model' string - REQUIRED

    # Manager for the entire collection of signoffs related to an Approval instance
    signoffsManager: type = managers.StampSignoffsManager  # injectable Manager class
    # Optional Signing Order Manager drives ordering API to determine "next" signoff available to a given user.
    signing_order: SigningOrderManager = None     # injected via SigningOrder descriptor - don't access directly.

    # Approval business logic, actions, and permissions
    logic: ApprovalLogic = ApprovalLogic()   # injectable implementations for Approval business logic

    # Accessor for approval status info
    status: ApprovalStatus = ApprovalStatus()

    # Define visual representation for approvals of this Type. Label is a rendering detail, but common override.
    label: str = ''     # Label for the Approval, e.g., "Authorize Leave", empty string for no label
    render: ApprovalRenderer = ApprovalRenderer()   # injectable object that knows how to render an approval

    # Registration for Approval Types (aka sub-class factory)

    @classmethod
    def register(cls, id, **kwargs):
        """
        Create, register, and return a new subclass of cls with overrides for given kwargs attributes
        Standard mechanism to define new Approval Types, typically in my_app/models.py or my_app/approvals.py
            MyApproval = AbstractApproval.register('my_appproval_type', label='Approve it!', ...)
        """
        from signoffs import registry
        class_name = utils.id_to_camel(id)
        kwargs['id'] = id
        approval_type = type(class_name, (cls,), kwargs)
        registry.approvals.register(approval_type)
        return approval_type

    @classmethod
    def validate(cls):
        """ Run any class validation that must pass before class can be registered.  Invoked by registry. """
        if cls.stampModel is None:
            raise ImproperlyConfigured('Approval Type {id} must specify a Stamp Model.'.format(id=cls.id))
        return True

    # Approval Type accessors

    @classmethod
    def get_stampModel(cls):
        """ Always use this accessor as the stampModel attribute may be an "app.Model" label """
        if not cls.stampModel:
            raise ImproperlyConfigured('No Stamp Model associated with Approval {cls}.'.format(cls=cls))
        if isinstance(cls.stampModel, str):
            cls.stampModel = apps.get_model(cls.stampModel)
        return cls.stampModel

    @classmethod
    def get_stamp_queryset(cls, prefetch=('signatories',)):
        """ Return a base (unfiltered) queryset of ALL Stamps for this Approval Type """
        return cls.get_stampModel().objects.filter(approval_id=cls.id).prefetch_related(*prefetch).all()

    # Approval Type behaviours

    @classmethod
    def create(cls, **kwargs):
        """ Create and return an approval backed by a new Stamp instance """
        approval = cls(**kwargs)
        approval.save()
        return approval

    # Approval instance behaviours

    def __init__(self, stamp=None, subject=None, **kwargs):
        """
        Construct an Approval instance backed by the given stamp or an instance of cls.stampModel(**kwargs)
        subject is optional: the object this approval is meant to approve - set by ApprovalField but otherwise unused.
        """
        self.stamp = stamp or self.get_new_stamp(**kwargs)
        self._subject = subject
        if not self.stamp.approval_id == self.id:
            raise ImproperlyConfigured('Approval Type {self} does not match Stamp Model {id}.'.format(
                self=self, id=self.stamp.approval_id))

    @property
    def subject(self):
        """
        The object being approved, if provided.
        Sub-classes with stamp FK relations may want to override this to access the stamp related object.
        subject is set by model Fields for convenient access to owner obj, but value is not used by any core logic.
        """
        return self._subject

    @property
    def slug(self):
        """ A slugified version of the signoff id, for places where a unique identifier slug is required """
        return slugify(self.id)

    @property
    def stamp_model(self):
        """ return the signoff model for this type """
        return self.get_stampModel()

    def get_new_stamp(self, **kwargs):
        """ Get a new, unsaved stamp instance for this approval type """
        Stamp = self.stamp_model
        return Stamp(approval_id=self.id, **kwargs)

    def __str__(self):
        return str(self.stamp)

    def __eq__(self, other):
        return isinstance(other, AbstractApproval) and self.id == other.id and self.stamp == other.stamp

    # Signoff Manager accessors

    @property
    def signoffs(self):
        """
        Return an ApprovalSignoffsManager for access to this approval's signoff set
        Default implementation returns manager for signoffs backed by stamp's signet_set manager.
        Concrete Approval Types may inject a custom signoffsManager for custom set of signoffs.
        """
        return self.signoffsManager(self.stamp, subject=self)

    def is_signed(self):
        """ Return True iff this approval has at least one signoff """
        return self.signoffs.exists()

    def has_signed(self, user):
        """ Return True iff given user is a signatory on this approval's set of signoffs """
        return any(s.user == user for s in self.signatories.all())

    # Approval Business Logic Delegation

    def can_sign(self, user):
        """ return True iff the given user can sign any of the next signoffs required on this approval """
        return self.logic.can_sign(self, user)

    def ready_to_approve(self):
        """ return True iff this approval's signing order is complete and ready to be approved """
        return self.logic.ready_to_approve(self)

    def approve_if_ready(self):
        """ Approve and save this approval is it meets all ready conditions """
        return self.logic.approve_if_ready(self)

    def approve(self, commit=True, **kwargs):
        """
        Approve this stamp. No permissions or signoff logic involved here - just force into approved state!
        Raises PermissionDenied if self.is_approved() -- can't approval an approved approval :-P
        kwargs passed directly to save() - use commit=False to approve without saving
        """
        return self.logic.approve(self, commit=commit, **kwargs)

    @classmethod
    def is_permitted_revoker(cls, user):
        """ return True iff user has permission to revoke approvals of this type """
        return cls.logic.is_permitted_revoker(cls, user)

    def can_revoke(self, user):
        """ return True iff this approval can be revoked by given user """
        return self.logic.can_revoke(self, user)

    def revoke(self, user, **kwargs):
        """ Revoke this approval for user if they have permission, otherwise raise PermissionDenied """
        self.logic.revoke(self, user, **kwargs)

    def get_revoke_url(self, args=None, kwargs=None):
        """ Return the URL for requests to revoke this approval """
        return self.logic.get_revoke_url(self, args=args, kwargs=kwargs)

    # Stamp Delegation

    @property
    def signatories(self):
        """
        Return queryset of Signets representing the signatories on this approval
        Default implementation simply returns Stamp's "reverse" signet_set manager.
        Concrete Approval Types can override to provide any sensible qs of signets.
        """
        return self.stamp.signatories

    @property
    def timestamp(self):
        """ Return the timestamp approval was granted, None otherwise """
        return self.stamp.timestamp if self.is_approved() else None

    def has_signatories(self):
        """ return True iff this approval has any signatories """
        return len(self.signatories.all()) > 0

    def is_approved(self):
        """ return True iff this Approval is in an approved state """
        return self.stamp.is_approved()

    def save(self, *args, **kwargs):
        """ Attempt to save the Stamp of Approval, with the provided given associated data """
        self.stamp.save(*args, **kwargs)
        return self

    @classmethod
    def has_object_relation(cls):
        return cls.get_stampModel().has_object_relation()

    # SigningOrder delegates - signing_order on approval instance is a SigningOrderManager
    # Assumptions:
    #  - signoffs have a "stamp" relation (FK to Stamp) -  SigningOrder requires a "reverse" set accessor
    #   (could loosen this assumption by making name of that relation configurable with "stamp" as default

    def is_complete(self):
        """
        Is this approval process complete and ready to be approved?
        Default implementation returns False if no signing order, True if the signing order is complete.
        Concrete Approval Types can override this method to customize conditions under which this approval is complete.
        """
        return bool(self.signing_order and self.signing_order.match.is_complete)

    def next_signoff_types(self, for_user=None):
        """
        Return list of next signoff type(s) (Signoff Type) required in this approval process.
        Default impl returns next signoffs from the approval's signing order or [] if no signing order is available.
        Concrete Approval Types can override this with custom business logic to provide signing order automation.
        """
        signoff_types = self.signing_order.match.next if self.signing_order else []
        return [
            signoff for signoff in signoff_types
                if (for_user is None or signoff.is_permitted_signer(for_user))
        ]

    def next_signoffs(self, for_user=None):
        """
        Return list of next signoff instance(s) required in this approval process.
        """
        signoffs = (
            signoff(stamp=self.stamp, subject=self, user=for_user) for signoff in self.next_signoff_types(for_user)
        )
        return [s for s in signoffs if s.can_sign(for_user)]

    def get_next_signoff(self, for_user=None):
        """
        Return the next available signoffs for given user, or None
        Again, ideally define ApprovalLogic or SigningOrder rather than overriding behaviour here.
        """
        next = self.next_signoffs(for_user=for_user)
        return next[0] if next else None


class BaseApproval(AbstractApproval):
    """
    A base Approval Type to be used as base class or to register concrete Approval Types
    Concrete Types will require a concrete Stamp Model to back the approval.
    """
    id = 'signoffs.base-approval'
    stampModel = None


def user_can_revoke_approval(approval_descriptor):
    """
    Return a callable suitable to pass as permission argument to fsm.transition
    Input is an approval_descriptor so that an ApprovalField can be used to define the permission for a FSM transition
      defined in the same class.  For example...

        class MyProcess(models.Model):
            ...
            my_approval, my_approval_stamp = ApprovalField(.....)
            ...
            @fsm.transition(..., permission=user_can_revoke_approval(my_approval))
            def approve_it(self, approval):
                ...
    """
    def has_revoke_perm(instance, user):
        """ Determine if the user has permission to revoke instance.approval """
        approval = approval_descriptor.__get__(instance, type(instance))
        return approval.can_revoke(user)
    return has_revoke_perm
