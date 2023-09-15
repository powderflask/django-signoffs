"""
    An Approval manages logic and state for a sequence of one or more Signoffs.

    Approval Types are registered subclasses of AbstractApproval
     - they define the behaviour for an Approval.

    Persistence layer for `Approval` state is provided by a `Stamp` model (think "Stamp of Approval" or TimeStamp)
     - one concrete `Stamp` model can back any number of Approval Types
     - an `Approval` provides the business and presentation logic for a `Stamp` instance.
"""
from typing import Callable, Optional, Type, Union

from django.apps import apps
from django.core.exceptions import ImproperlyConfigured, PermissionDenied
from django.db import transaction
from django.utils.text import slugify

from signoffs.core import models, utils
from signoffs.core.models import managers
from signoffs.core.renderers import ApprovalRenderer
from signoffs.core.signing_order import SigningOrder
from signoffs.core.status import ApprovalStatus
from signoffs.core.urls import ApprovalUrlsManager

# type name shorts
opt_str = Union[bool, Optional[str]]
stamp_type = Union[str, Type[models.AbstractApprovalStamp]]


# The business logic for revoking an approval may be dependent on context that can't be encoded in an Approval
# Application logic may also need a way to revoke approvals without triggering Approval permission or signal logic.
# revoke_approval provides the default implementation for basic revoke business logic.
# Implementors can override the behaviour of Approval.revoke() by either overriding the class method or by injecting
#      a function with the same signature as the default implementation provided here...


def revoke_approval(approval, user, reason=""):
    """
    Force revoke the given approval for user regardless of permissions or approval state!

    Default implementation revokes ALL related signets on behalf of the user
      - a user with permission to revoke an approval must have permission to revoke all signoffs within!
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
    revoke_perm: opt_str = ""  # e.g. 'approvals.delete_stamp'
    revoke_method: Callable = revoke_approval  # revoke approval algorithm

    def __init__(self, revoke_perm=None, revoke_method=None):
        """Override default actions, or leave parameter None to use class default"""
        self.revoke_perm = revoke_perm if revoke_perm is not None else self.revoke_perm
        self.revoke_method = (
            revoke_method or type(self).revoke_method
        )  # don't bind revoke_method to self here

    # Approve Actions / Rules

    def is_signable(self, approval, by_user=None):
        """
        Return True iff this approval is in a state it could be signed by the given user

        :::{important}
         - this is approval-level logic only -- keep signoff-level rules in signoff.can_sign
         - does not determine if there is a signoff available to be signed, only about the state of this approval!
         - use can_sign to determine if there are any actual signoffs available to the user to be signed.
        :::
        """
        return not approval.is_approved()

    def can_sign(self, approval, user, signoff=None):
        """
        Return True iff the given user can sign given signoff on this approval,
            or any of the next signoffs in its signing order
        """
        avaialable = approval.next_signoffs(for_user=user)
        return signoff in avaialable if signoff else len(avaialable) > 0

    def ready_to_approve(self, approval):
        """Return True iff the approval's signing order is complete and ready to be approved"""
        return not approval.is_approved() and approval.is_complete()

    def approve_if_ready(self, approval, commit=True):
        """Approve and save the approval is it meets all ready conditions"""
        if self.ready_to_approve(approval):
            self.approve(approval, commit)

    def approve(self, approval, commit=True, **kwargs):
        """
        Approve the approval and save it's Stamp.

        No permissions or signoff completion logic involved here - just force into approved state!
         - Prefer to use `approve_if_ready` to enforce business rules.
        `kwargs` passed directly to save() - use commit=False to approve without saving
        """
        approval.stamp.approve()
        if commit:
            approval.save(**kwargs)

    # Revoke Actions / Rules

    def is_revokable(self, approval, by_user=None):
        """
        Return True iff this approval is in a state it could be revoked by the given user

        :::{important}
         - this is approval-level logic only -- keep signoff-level rules in signoff.can_revoke
         - does not determine if there is a signoff available to be revoked, only about the state of this approval!
         - use can_revoke to determine if the approval is actually available to the user to be revoked.
        :::
        """
        return approval.is_approved()

    def is_permitted_revoker(self, approval_type, user):
        """return True iff user has permission to revoke approvals of given Type"""
        revoke_perm = self.revoke_perm
        return (
            False
            if self.revoke_perm is False
            else user.has_perm(revoke_perm)
            if revoke_perm
            else True
        )

    def can_revoke(self, approval, user):
        """Return True iff the approval can be revoked by given user"""
        # Note: assumes a user with permission to revoke an approval would also have permission to revoke all signoffs within.
        # Note: code duplicated in process.BasicApprovalProcess so function can be overriden with approval process logic here.
        return self.is_revokable(approval, user) and self.is_permitted_revoker(
            type(approval), user
        )

    def revoke_if_permitted(self, approval, user, reason=""):
        """
        Revoke and save the approval if it meets all conditions for revocation.

        :raises PermissionDenied: if not
        """
        if not self.can_revoke(approval, user):
            raise PermissionDenied(
                f"User {user} does not have permission to revoke approval {self}"
            )

        return self.revoke(approval, user, reason)

    def revoke(self, approval, user, reason=""):
        """
        Revoke the approval and save it's Stamp.

        No permissions or completion logic involved here - just force into revoked state!
        Prefer to use `revoke_if_permitted` to enforce business rules.
        """
        return self.revoke_method(approval, user, reason)

    def can_revoke_signoff(self, approval, signoff):
        """
        Return True iff the given signoff can be revoked from this approval

        :::{note}
        in many use-cases, it will only make sense to revoke the last signoff collected, but that's custom logic!
        The simple generic rule is that signoffs can only be revoked from unapproved approvals
        """
        return not approval.is_approved() and signoff in approval.signoffs.all()


class ApprovalLogic(DefaultApprovalBusinessLogic):
    """ Public API: Alias for `DefaultApprovalBusinessLogic """


class AbstractApproval:
    """
    Defines the semantics for Approving something using a sequence of one or more `Signoffs`

    Defines the business and presentation logic for completing such an approval:
     - what is it for, how is it labelled, what signoffs need to be  collected, in what sequence, etc.
     - default meta-data values can be overridden by subclasses or passed to `.register()` factory

    Uses a `SigningOrder` to define the sequence of Signgoffs requrired.
     - default signing order is sequencial, ordered alphabetically,
       based on `SignoffFields` / attribute defined on the `Approval`
    :::{tip}
    - most Approvals will override `SigningOrder`
    - use ordering API on Approval instance over accessing signing_order directly!
    :::

    An Approval Type (class) defines the implementation for a specific type of approval.
     - define and register new Approval Types with factory method:: `BaseApproval.register(...)`

    The data for an `Approval` instance is backed and persisted by an `ApprovalStamp` and its related `Signets`.

    Approval Types are pure-code objects, not stored in DB, as they define application logic, not application data.
     - they are registered in the `signoffs.registry.approvals` where they can be retrieved by `id`

    :::{caution}
    `Stamp` records are stored in DB with a reference to `Approval.id`
    Be cautions not to change or delete id's that are in-use.
    :::
    """

    # id must be unique per type class, but human-legible / meaningful - dotted path recommended e.g. 'myapp.approval'
    id: str = "approval.abstract"
    """unique identifier for type - used like FK, don't mess with these!"""

    # stampModel is required - every Approval Type must supply a concrete Stamp model to provide persistence layer
    stampModel: stamp_type = None  # concrete Model or 'app.model' string - REQUIRED

    # Manager for the entire collection of signoffs related to an Approval instance
    signoffsManager: type = managers.StampSignoffsManager  # injectable Manager class
    # Optional Signing Order Manager drives ordering API to determine "next" signoff available to a given user.
    signing_order: SigningOrder = None  # sequencing logic for approval's signoffs

    # Approval business logic, actions, and permissions
    logic: ApprovalLogic = ApprovalLogic()

    # Accessor for approval status info
    status: ApprovalStatus = ApprovalStatus()

    # Define visual representation for approvals of this Type. Label is a rendering detail, but common override.
    label: str = ""  # Label for the Approval empty string for no label
    render: ApprovalRenderer = ApprovalRenderer()  # presentation logic service
    urls: ApprovalUrlsManager = ApprovalUrlsManager()  # service to provide endpoints

    # Registration for Approval Types (aka subclass factory)

    @classmethod
    def register(cls, id, **kwargs):
        """
        Create, register, and return a new subclass of cls with overrides for given kwargs attributes

        Standard mechanism to define new Approval Types, typically in `my_app/models.py` or `my_app/approvals.py`
        Usage:
        ```
        MyApproval = AbstractApproval.register('my_appproval_type', label='Approve it!', ...)
        ```
        """
        from signoffs import registry

        class_name = utils.id_to_camel(id)
        kwargs["id"] = id
        approval_type = type(class_name, (cls,), kwargs)
        registry.approvals.register(approval_type)
        return approval_type

    @classmethod
    def validate(cls):
        """Run any class validation that must pass before class can be registered.  Invoked by registry."""
        if cls.stampModel is None:
            raise ImproperlyConfigured(
                f"Approval Type {cls.id} must specify a Stamp Model."
            )
        return True

    # Approval Type accessors

    @classmethod
    def get_stampModel(cls):
        """Always use this accessor as the stampModel attribute may be an "app.Model" label"""
        if not cls.stampModel:
            raise ImproperlyConfigured(
                f"No Stamp Model associated with Approval {cls}."
            )
        if isinstance(cls.stampModel, str):
            cls.stampModel = apps.get_model(cls.stampModel)
        return cls.stampModel

    @classmethod
    def get_stamp_queryset(cls, prefetch=("signatories",)):
        """Return a base (unfiltered) queryset of ALL Stamps for this Approval Type"""
        return (
            cls.get_stampModel()
            .objects.filter(approval_id=cls.id)
            .prefetch_related(*prefetch)
            .all()
        )

    # Approval Type behaviours

    @classmethod
    def create(cls, **kwargs):
        """Create and return an approval backed by a new Stamp instance"""
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
            raise ImproperlyConfigured(
                f"Approval Type {self} does not match Stamp Model {self.stamp.approval_id}."
            )

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
        """A slugified version of the signoff id, for places where a unique identifier slug is required"""
        return slugify(self.id)

    @property
    def stamp_model(self):
        """return the signoff model for this type"""
        return self.get_stampModel()

    def get_new_stamp(self, **kwargs):
        """Get a new, unsaved stamp instance for this approval type"""
        Stamp = self.stamp_model
        return Stamp(approval_id=self.id, **kwargs)

    def __str__(self):
        return str(self.stamp)

    def __eq__(self, other):
        return (
            isinstance(other, AbstractApproval)
            and self.id == other.id
            and self.stamp == other.stamp
        )

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
        """Return True iff this approval has at least one signoff"""
        return self.signoffs.exists()

    def has_signed(self, user):
        """Return True iff given user is a signatory on this approval's set of signoffs"""
        return any(s.user == user for s in self.signatories.all())

    # Approval Business Logic Delegation

    def can_sign(self, user, signoff=None):
        """
        return True iff the given user can sign given signoff on this approval,
            or any of the next signoffs in its signing order
        """
        return self.logic.can_sign(self, user, signoff)

    def ready_to_approve(self):
        """Return True iff this approval's signing order is complete and ready to be approved"""
        return self.logic.ready_to_approve(self)

    def approve_if_ready(self, commit=True):
        """Approve and save this approval is it meets all ready conditions"""
        return self.logic.approve_if_ready(self, commit)

    def approve(self, commit=True, **kwargs):
        """
        Approve this stamp. No permissions or signoff logic involved here - just force into approved state!
        Raises PermissionDenied if self.is_approved() -- can't approval an approved approval :-P
        kwargs passed directly to save() - use commit=False to approve without saving
        """
        return self.logic.approve(self, commit=commit, **kwargs)

    @classmethod
    def is_permitted_revoker(cls, user):
        """Return True iff user has permission to revoke approvals of this type"""
        return cls.logic.is_permitted_revoker(cls, user)

    def can_revoke(self, user):
        """Return True iff this approval can be revoked by given user"""
        return self.logic.can_revoke(self, user)

    def revoke_if_permitted(self, user, **kwargs):
        """Revoke and save the approval is it meets all conditions for revocation"""
        return self.logic.revoke_if_permitted(self, user, **kwargs)

    def revoke(self, user, **kwargs):
        """Revoke this approval regardless of permissions or approval state - careful!"""
        return self.logic.revoke(self, user, **kwargs)

    def can_revoke_signoff(self, signoff):
        """Return True iff the given signoff can be revoked from this approval"""
        return self.logic.can_revoke_signoff(self, signoff)

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
        """Return the timestamp approval was granted, None otherwise"""
        return self.stamp.timestamp if self.is_approved() else None

    def has_signatories(self):
        """Return True iff this approval has any signatories"""
        return len(self.signatories.all()) > 0

    def is_approved(self):
        """Return True iff this Approval is in an approved state"""
        return self.stamp.is_approved()

    def save(self, *args, **kwargs):
        """Attempt to save the Stamp of Approval, with the provided given associated data"""
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
        return bool(self.signing_order and self.signing_order.is_complete())

    def next_signoff_types(self, for_user=None):
        """
        Return list of next signoff type(s) (Signoff Type) required in this approval process.
        Default impl returns next signoffs from the approval's signing order or [] if no signing order is available.
        Concrete Approval Types can override this with custom business logic to provide signing order automation.
        """
        signoff_types = self.signing_order.next_signoffs() if self.signing_order else []
        return [
            signoff
            for signoff in signoff_types
            if (for_user is None or signoff.is_permitted_signer(for_user))
        ]

    def next_signoffs(self, for_user=None):
        """
        Return list of next signoff instance(s) required in this approval process.
        If a user object is supplied, filter out instances not available to that user.
        Most applications will define custom business logic for ordering signoffs, restricting duplicate signs, etc.
            - ideally, use ApprovalLogic and SigningOrder to handle these, but this gives total control!
        """
        if not self.logic.is_signable(self, for_user):
            return []
        signoffs = (
            signoff(stamp=self.stamp, subject=self, user=for_user)
            for signoff in self.next_signoff_types(for_user)
        )
        return [s for s in signoffs if for_user is None or s.can_sign(for_user)]

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

    id = "signoffs.base-approval"
    stampModel = None


__all__ =[
    'revoke_approval', 'AbstractApproval', 'BaseApproval', 'DefaultApprovalBusinessLogic', 'ApprovalLogic'
]