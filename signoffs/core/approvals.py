"""
    An Approval defines the "signing order" for a sequence of one or more Signoffs.
    Approval Types are registered subclasses of AbstractApproval
        - they define the behaviour for an Approval.
    Persistence layer for Approval state is provided by a Stamp model (think "Stamp of Approval" or TimeStamp)
        - one concrete Stamp model can back any number of Approval Types
        - can think of an Approval instance as the "plugin behaviour" for a Stamp instance.
"""
import inspect
from typing import Callable, Type, Optional, Union

from django.apps import apps
from django.core.exceptions import ImproperlyConfigured, PermissionDenied

from signoffs.core import models, utils
from signoffs.core.models import managers
from signoffs.core.renderers import ApprovalRenderer
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
    # Revoke all signoffs
    for signoff in approval.signatories.signoffs():
        signoff.revoke(user=user, reason=reason)

    approval.stamp.approved = False
    approval.save()


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

    # Process / permissions to revoke an approval of this Type: False for irrevocable;  None (falsy) for unrestricted
    revoke_perm: opt_str = ''                   # e.g. 'approvals.delete_stamp'
    revoke_method: Callable = revoke_approval   # injectable implementation for revoke approval algorithm

    # Define visual representation for approvals of this Type. Label is a rendering detail, but common override.
    label: str = ''     # Label for form field (i.e., checkbox) e.g. 'Approve Project', empty string for no label
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
    def is_permitted_revoker(cls, user):
        """ return True iff user has permission to revoke approvals of this type """
        revoke_perm = cls.revoke_perm
        return False if cls.revoke_perm is False else \
            user.has_perm(revoke_perm) if revoke_perm else True

    @classmethod
    def create(cls, **kwargs):
        """ Create and return an approval backed by a new Stamp instance """
        approval = cls(**kwargs)
        approval.save()
        return approval

    # Approval instance behaviours

    def __init__(self, stamp=None):
        """
        Construct an Approval instance backed by a cls.stampModel(), which must have a relation to self
        """
        self.stamp = stamp or self.get_new_stamp()
        if not self.stamp.approval_id == self.id:
            raise ImproperlyConfigured('Approval Type {self} does not match Stamp Model {id}.'.format(
                self=self, id=self.stamp.approval_id))

    @property
    def stamp_model(self):
        """ return the signoff model for this type """
        return self.get_stampModel()

    def get_new_stamp(self):
        """ Get a new, unsaved stamp instance for this approval type """
        Stamp = self.stamp_model
        return Stamp(approval_id=self.id)

    def __str__(self):
        return str(self.stamp)

    def __eq__(self, other):
        return self.id == other.id and self.stamp == other.stamp

    @property
    def signoffs(self):
        """
        Return an ApprovalSignoffsManager for access to this approval's signoff set
        Default implementation returns manager for signoffs backed by stamp's signet_set manager.
        Concrete Approval Types may inject a custom signoffsManager for custom set of signoffs.
        """
        return self.signoffsManager(self.stamp)

    def has_signed(self, user):
        """ Return True iff given user is a signatory on this approval's set of signoffs """
        return any(s.user == user for s in self.signatories.all())

    def can_approve(self):
        """ return True iff this approval may be approved (regardless of completing signoffs!) """
        return not self.is_approved()

    def ready_to_approve(self):
        """ return True iff this approval's signing order is complete and ready to be approved """
        return self.can_approve() and self.is_complete()

    def approve_if_ready(self):
        """ Approve and save this approval is it meets all ready conditions """
        if self.ready_to_approve():
            self.approve()

    def approve(self, commit=True, **kwargs):
        """
        Approve this stamp. No permissions or signoff logic involved here - just force into approved state!
        If not self.can_approve() raises PermissionDenied
        kwargs passed directly to save() - use commit=False to approve without saving
        """
        if self.can_approve():
            self.stamp.approve()
            if commit:
                self.save(**kwargs)
        else:
            raise PermissionDenied('Attempt to approve approved approval {self}'.format(self=self))

    def can_revoke(self, user):
        """ return True iff this approval can be revoked by given user """
        return self.is_approved() and self.is_permitted_revoker(user)

    def revoke(self, user, reason=''):
        """ Revoke this approval for user if they have permission, otherwise raise PermissionDenied """
        if not self.is_approved():
            raise PermissionDenied('Attempt to revoke unapproved approval {a}'.format(a=self))
        if not self.can_revoke(user):
            raise PermissionDenied(
                'User {u} does not have permission to revoke approval {a}'.format(u=user, a=self))

        return self.revoke_method(user, reason)

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
        return len(self.signatories) > 0

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

    def is_complete(self):
        """
        Is this approval process complete and ready to be approved?
        Default implementation returns False if no signing order, True if the signing order is complete.
        Concrete Approval Types can override this method to customize conditions under which this approval is complete.
        """
        return self.signing_order and self.signing_order.match.is_complete

    def next_signoffs(self, for_user=None):
        """
        Return list of next signoff instance(s) required in this approval process.
        Default impl returns next signoffs from the approval's signing order or [] if no signing order is available.
        Concrete Approval Types can override this with custom business logic to provide signing order automation.
        """
        signoff_types = self.signing_order.match.next if self.signing_order else []
        return [
            signoff(stamp=self.stamp, user=for_user) for signoff in signoff_types
            if (for_user is None or signoff.is_permitted_signer(for_user))
        ]

    def can_sign(self, user):
        """ return True iff the given user can sign any of the next signoffs required on this approval """
        return not self.is_approved() and len(self.next_signoffs(for_user=user)) > 0


class BaseApproval(AbstractApproval):
    """
    A base Approval Type to be used as base class or to register concrete Approval Types
    Concrete Types will require a concrete Stamp Model to back the approval.
    """
    id = 'signoffs.base-approval'
    stampModel = None
