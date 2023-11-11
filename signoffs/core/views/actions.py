"""
A `RequestActions` object is a facade that presents a simplified interface for handling requests to
sign and revoke signoff objects.

There are just a couple "actions" that can be taken with a signoff
  - it gets signed, it gets revoked, that's about it.
But these simple actions often initiate a cascade of notifications and/or state transitions.
The cascade of actions taken during a signoff request will be application dependent to some degree, so the
`RequestActions` classes are designed to be open for extension.

A `RequestActionsProtocol` is an API that a generic signoff- or approval-processing view
can use to handle a request.
Concrete `Actions` encapsulate the business logic for requests made for a particular signoff or approval process.
Thus, they provide reusable, extensible, composable View logic, outside the Views hierarchy.

:::{tip}
For best cohesion: the `Signoff.logic` and `Approval.logic` objects implement all business rules
while an `Action` object just orchestrates them - resist temptation to encode business rules in Actions!
:::

The protocols, default implementations, and actions provided here are sufficient to handle a range of basic use-cases.
They are not intended to be exhaustive - consider them as a skeleton to demonstrate how a signoff request might
typically be handled.
"""
from __future__ import annotations

from dataclasses import dataclass
from functools import partial
from typing import Callable, Protocol

from django.contrib.auth import get_user_model
from django.core.exceptions import ImproperlyConfigured
from django.db import transaction

import signoffs.registry
from signoffs.approvals import AbstractApproval
from signoffs.process import ApprovalsProcess
from signoffs.signoffs import AbstractSignoff

User = get_user_model()

##################
#  SIGNOFF ACTIONS
##################


class SignoffValidator(Protocol):
    """Basic API to validate a signoff request for a specific user"""

    user: User

    def is_valid_signoff_request(self, signoff: AbstractSignoff) -> bool:
        """Return True iff signoff can be signed by user."""
        ...

    def is_valid_revoke_request(self, signoff: AbstractSignoff) -> bool:
        """Return True iff signoff can be revoked by user."""
        ...


@dataclass
class BasicSignoffValidator:
    """
    Default Signoff request permissions validation logic

    Implements`SignoffValidator` Protocol
    """

    user: User
    verify_signet: Callable[[AbstractSignoff], bool] = lambda signoff: True
    """Optional function to validate request data against a signoff, or None to skip"""

    def is_valid_signoff_request(self, signoff: AbstractSignoff) -> bool:
        """Return True iff signoff can be signed by user."""
        return signoff.can_sign(self.user)

    def is_valid_revoke_request(self, signoff: AbstractSignoff) -> bool:
        """Return True iff signoff can be revoked by user."""
        return signoff.can_revoke(self.user) and self.verify_signet(signoff)


class SignoffCommitter(Protocol):
    """Basic API to commit a signoff request to DB for a specific user"""

    user: User

    def sign(self, signoff: AbstractSignoff):
        """Sign and commit the signoff for given user - no validation, just do it!"""
        ...

    def revoke(self, signoff: AbstractSignoff):
        """Revoke the signoff for given user and commit changes to DB - no validation, just do it!"""
        ...


@dataclass
class BasicSignoffCommitter:
    """
    Default Signoff request commit logic

    Implements `SignoffCommitter` Protocol
    """

    user: User
    """The user who is signing the signoff"""
    post_signoff_hook: Callable[[AbstractSignoff], None] = lambda s: None
    """A function that takes the signed signoff as argument, called in atomic transaction after signing"""
    post_revoke_hook: Callable[[AbstractSignoff], None] = lambda s: None
    """A function that takes the revoked signoff as argument, called in atomic transaction after revoking"""

    def sign(self, signoff: AbstractSignoff):
        """Sign and commit the signoff for given user - no validation, just do it!"""
        with transaction.atomic():
            signoff.sign(self.user)
            self.post_signoff_hook(signoff)

    def revoke(self, signoff: AbstractSignoff):
        """Revoke the signoff for given user and commit changes to DB - no validation, just do it!"""
        with transaction.atomic():
            signoff.revoke(self.user)
            self.post_revoke_hook(signoff)


class SignoffRequestFormHandler(Protocol):
    """Basic API to provision and validate forms from signoff request data"""

    data: dict

    def get_signoff_form(self):
        """Return the signoff form bound to data or None if no valid signoff form could be constructed"""
        ...

    def get_signed_signoff(self, user: User) -> AbstractSignoff:
        """Validate data against signoff form, return signed but unsaved signoff or None if form doesn't validate"""
        ...

    def get_revoke_form(self):
        """Return a revoke form bound to data or None if no valid signoff form could be constructed"""
        ...

    def get_revoked_signoff(self, user: User) -> AbstractSignoff:
        """Validate data against revoke form, return unrevoked signoff or None if form doesn't validate"""
        ...


@dataclass
class BasicSignoffFormHandler:
    """
    Provision and validate a signoff form from a data source

    Implements `SignoffRequestFormHandler` Protocol
    """

    data: dict
    """GET or POST data dictionary"""
    signoff_subject: object = None
    """optional subject of the signoff - signoff.subject set if provided"""
    signoff_id_key: str = "signoff_id"
    """default name of data key (i.e., form field) for retrieving signoff_id from data dict"""

    def get_signoff_type(self):
        """Return the signoff type indicated by `data[signoff_id_key]`, or None"""
        signoff_id = self.data.get(self.signoff_id_key, None)
        try:
            return signoffs.registry.get_signoff_type(signoff_id)
        except ImproperlyConfigured:  # invalid signoff_id in the data
            return None

    def get_signoff_form(self):
        """Return the signoff form bound to data or None if no valid signoff form could be constructed"""
        signoff_type = self.get_signoff_type()
        return signoff_type.forms.get_signoff_form(self.data) if signoff_type else None

    def get_signed_signoff(self, user):
        """Validate data against signoff form, return signed but unsaved signoff or None if form doesn't validate"""
        signoff_form = self.get_signoff_form()
        if not signoff_form or not signoff_form.is_valid():
            return None
        signoff = signoff_form.sign(user=user, commit=False)
        if signoff and self.signoff_subject:
            signoff.subject = self.signoff_subject
        return signoff

    def get_revoke_form(self):
        """Return a revoke form bound to data or None if no valid signoff form could be constructed"""
        signoff_type = self.get_signoff_type()
        return signoff_type.forms.get_revoke_form(self.data) if signoff_type else None

    def get_revoked_signoff(self, user):
        """Validate data against revoke form, return revoked signoff or None if form doesn't validate"""
        revoke_form = self.get_revoke_form()
        if not revoke_form or not revoke_form.is_valid():
            return None
        return revoke_form.revoke(user=user, commit=False)


class SignoffRequestActions(Protocol):
    """Basic API to process a signoff request"""

    signoff: AbstractSignoff

    def sign_signoff(self, commit=True):
        """Handle request to sign the signoff, return True iff signoff was signed"""
        ...

    def revoke_signoff(self, commit=True):
        """Handle request to revoke the signoff, return True iff signoff was revoked"""
        ...


def verify_consistent_signet_id(signoff, request_signet_id=None) -> bool:
    """As an extra data integrity check, revoke URL's may also contain the signet_id - verify it matches"""
    return (request_signet_id == signoff.signet.pk) if request_signet_id else True


def get_verify_signet(kwargs, signet_id_key="signet_id"):
    """Helper to return a `verify_signet` function with correct signature for use with `BasicSignoffValidator`"""
    return partial(
        verify_consistent_signet_id, request_signet_id=kwargs.get(signet_id_key, None)
    )


class BasicUserSignoffActions:
    """
    Concrete SignoffRequestActions to handle simple signoff requests that don't trigger any follow-up actions

    An extensible base class for extending this simple case that
    implements `SignoffRequestActions` Protocol
    Facade: delegation to signoff's `forms` and business `logic`
    """

    form_handler_class: SignoffRequestFormHandler = BasicSignoffFormHandler
    validator_class: SignoffValidator = BasicSignoffValidator
    committer_class: SignoffCommitter = BasicSignoffCommitter

    def __init__(
        self,
        user: User,
        data: dict,
        form_handler: SignoffRequestFormHandler = None,
        validator: SignoffValidator = None,
        committer: SignoffCommitter = None,
        **kwargs,
    ):
        """
        Define actions available to the given user based on request data

        :param user: typically the request.user
        :param dict data: a dict-like object, typically with the GET or POST data from the request
        :param kwargs: extra kwargs, typically view.kwargs, for validating and provisioning objects
        """
        self.user = user
        self.data = data
        self.forms = form_handler or self.form_handler_class(data)
        self.validator = validator or self.validator_class(
            user=user, verify_signet=get_verify_signet(kwargs)
        )
        self.committer = committer or self.committer_class(user=user)
        self.kwargs = kwargs
        self.signoff = None  # populated by calling sign_ or revoke_signoff

    def verify_consistent_signet_id(self, signoff) -> bool:
        """As an extra data integrity check, revoke URL's may also contain the signet_id - check it matches"""
        signet_id = self.kwargs.get("signet_id", None)
        return (signet_id == signoff.signet.pk) if signet_id else True

    # "Template Method" hooks: to extend / override sign_signoff without duplicating core algorithm

    def signoff_success(self, signoff):
        """Return value for successful signoff."""
        return True

    def signoff_failed(self, signoff):
        """Return value for failed signoff."""
        return False

    # Core algorithm:  Provision a signoff form, validate, and attempt to sign it.

    def sign_signoff(self, commit=True):
        """
        Handle request to sign a signoff form defined in `data`, return True iff signoff was signed

        :param bool commit: False to validate the form and sign self.signoff, but not commit signet to DB.
        """
        self.signoff = self.forms.get_signed_signoff(self.user)
        if self.signoff and self.validator.is_valid_signoff_request(self.signoff):
            if commit:
                self.committer.sign(self.signoff)
            return self.signoff_success(self.signoff)
        return self.signoff_failed(self.signoff)

    # "Template Method" hooks: to extend / override revoke_signoff without duplicating core algorithm

    def revoke_success(self, signoff):
        """Return value for successful revoke."""
        return True

    def revoke_failed(self, signoff):
        """Return value for failed revoke."""
        return False

    # Core algorithm:  Provision a revoke form, validate, and attempt to revoke the signet.

    def revoke_signoff(self, commit=True):
        """
        Handle request to revoke given signoff, return True iff signoff was revoked

        :param bool commit: False to validate the form, but not actually revoke the signet and commit to DB.

        :::{note}
        `commit=False` means "perform validation and return what would have happened, but do not actually revoke"
        There is no way to "revoke" a signoff without committing the change.  Call again to do the actual revoke.
        :::
        """
        self.signoff = self.forms.get_revoked_signoff(self.user)

        if self.signoff and self.validator.is_valid_revoke_request(self.signoff):
            if commit:
                self.committer.revoke(self.signoff)
            return self.revoke_success(self.signoff)
        return self.revoke_failed(self.signoff)


##################
# APPROVAL ACTIONS
##################


class ApprovalSignoffValidator(BasicSignoffValidator):
    """
    Default permissions validation logic for requests to Signoff on an Approval

    Implements`SignoffValidator` Protocol
    """

    def __init__(
        self,
        user: User,
        approval: AbstractApproval,
        verify_signet: Callable[[AbstractSignoff], bool] = lambda signoff: True,
        verify_stamp: Callable[[AbstractSignoff], bool] = lambda signoff: True,
    ):
        """
        Initialize validator for signoffs on the given approval.

        :param AbstractApproval approval: that approval for which to validate signoff requests
        :param Callable verify_signet: Optional function to validate request data against a signoff, or None to skip
        :param Callable verify_stamp: Optional function to validate request data, or None to skip
        """
        super().__init__(user=user, verify_signet=verify_signet)
        self.approval = approval
        self.verify_stamp = verify_stamp

    def is_valid_signoff_request(self, signoff: AbstractSignoff) -> bool:
        """Return True iff signoff can be signed by user."""
        return (
            super().is_valid_signoff_request(signoff)
            and self.verify_stamp(signoff)
            and self.approval.can_sign(self.user, signoff)
        )

    def is_valid_revoke_request(self, signoff: AbstractSignoff) -> bool:
        """Return True iff signoff can be revoked by user."""
        return (
            super().is_valid_revoke_request(signoff)
            and self.verify_stamp(signoff)
            and self.approval.can_revoke_signoff(signoff, self.user)
        )


class ApprovalRequestActions(Protocol):
    """Basic API to process an approval request"""

    signoff: AbstractSignoff
    approval: AbstractApproval

    def approve(self, commit=True):
        """Handle request to approve the approval, return True iff it was approved."""
        ...

    def revoke_approval(self, commit=True):
        """Handle request to revoke approval, return True iff approval was revoked"""
        ...


def verify_consistent_stamp_id(approval, signoff=None, request_stamp_id=None):
    """
    Return True iff data relations for approval, signoff, and request are self-consistent

    Validates that signoff.stamp, if it exists, is same object as approval.stamp, and optionally a stamp_id from request
    """
    if not approval:
        return False
    signoff_stamp_id = getattr(signoff.signet, "stamp_id", None) if signoff else None
    return approval.stamp.id == (
        request_stamp_id or approval.stamp.id
    ) and approval.stamp.id == (signoff_stamp_id or approval.stamp.id)


def get_verify_stamp(approval, kwargs, stamp_id_key="stamp_id"):
    """Helper to return a `verify_stamp` function with correct signature for use with `ApprovalSignoffValidator`"""
    return partial(
        verify_consistent_stamp_id,
        approval,
        request_stamp_id=kwargs.get(stamp_id_key, None),
    )


class BasicUserApprovalActions:
    """
    Concrete implementation that handles simple approvals that don't trigger any follow-up actions

    An extensible base class for extending this simple case that...
    provides a default post_signoff_hook to approve approval when ready and adds it to default committer
    provides a stub for post_revoke_hook adds it to default committer
    implements `SignoffRequestActions` and `ApprovalRequestActions` Protocols
    Facade: delegation & orchestration of signoff_actions_class, and signoff & approval business logic.
    """

    validator_class: SignoffValidator = ApprovalSignoffValidator
    """Default `validator` uses get_verify_signet and get_verify_stamp as verifiers"""
    committer_class: SignoffCommitter = BasicSignoffCommitter
    """Default `committer` defines post_signoff_hook that calls `self.approve()` to update approval state

       Override `approve()` method if you just need to extend the post_signoff_hook action
    """
    signoff_actions_class = BasicUserSignoffActions
    """Default `signoff_actions` is constructed from the other components."""

    def __init__(
        self,
        user,
        data,
        approval,
        signoff_actions: SignoffRequestActions = None,
        validator: SignoffValidator = None,
        committer: SignoffCommitter = None,
        **kwargs,
    ):
        """
        Define actions available to the given user on the given approval based on request data

        :param user: typically the `request.user`
        :param dict data: a dict-like object, typically with the GET or POST data from the request
        :param AbstractApproval approval: the `Approval` that the signoff/revoke actions are applied to.
        :param SignoffRequestActions signoff_actions: object used to sign approvals, or None to use class default
        :param kwargs: additional parameters passed through to `signoff_actions_class` initializer
        """
        self.user = user
        self.data = data
        self.approval = approval
        self.verify_stamp = get_verify_stamp(approval, kwargs)
        self.validator = validator or self.validator_class(
            user,
            approval,
            verify_signet=get_verify_signet(kwargs),
            verify_stamp=self.verify_stamp,
        )
        committer = committer or self.committer_class(
            user,
            post_signoff_hook=self.process_signoff,
            post_revoke_hook=self.process_revoked_signoff,
        )
        forms = self.signoff_actions_class.form_handler_class(
            self.data, signoff_subject=self.approval
        )
        self.signoff_actions = signoff_actions or self.signoff_actions_class(
            user,
            data,
            form_handler=forms,
            validator=self.validator,
            committer=committer,
            **kwargs,
        )
        self.kwargs = kwargs

    @property
    def signoff(self):
        """Populated by calling sign_ or revoke_signoff"""
        signoff = self.signoff_actions.signoff
        # override the signoff.subject with approval, which might be bound to a higher-level subject,
        #   like an approval_process.  But don't alter the approval type - validation will catch inconsistencies.
        if signoff and (not signoff.subject or signoff.subject == self.approval):
            signoff.subject = self.approval
        return signoff

    @property
    def forms(self):
        """Access to signoff actions form handler object"""
        return self.signoff_actions.forms

    # SignoffRequestActions Protocol - delegate to signoff_actions using approval-level validation and commit logic

    def sign_signoff(self, commit=True):
        """
        Handle request to sign a signoff form for the approval, return True iff signoff succeeded

        :param bool commit: False to validate the form and sign self.signoff, but not commit signet to DB.
        """
        return self.signoff_actions.sign_signoff(commit=commit)

    def revoke_signoff(self, commit=True):
        """
        Handle request to revoke a signoff from this approval, return True iff revoke succeeded

        :param bool commit: False to validate the form, but not actually revoke signet and commit to DB.

        :::{note}
        `commit=False` means "perform validation and return what would have happened, but do not actually revoke"
        There is no way to "revoke" a signoff without committing the change.  Call again to do the actual revoke.
        :::
        """
        return self.signoff_actions.revoke_signoff(commit=commit)

    # ApprovalActions Protocol

    def process_signoff(self, signoff):
        """Trigger an approval if the signoff completed approval's signing order"""
        if self.approval.ready_to_approve():
            self.approve()

    def is_valid_approve_request(self):
        """Return True iff the approval is complete and ready to be approved"""
        return self.verify_stamp() and self.approval.ready_to_approve()

    def approve(self, commit=True):
        """
        Handle request to approve the approval, return True iff it was approved.
        """
        if not self.is_valid_approve_request():
            return False
        self.approval.approve(commit=commit)
        return self.approval.is_approved()

    def process_revoked_signoff(self, signoff):
        """Take additional approval-related actions when given signoff has been revoked"""
        pass

    def is_valid_approval_revoke_request(self):
        """Return True iff user is allowed to revoke the given approval"""
        return self.verify_stamp() and self.approval.can_revoke(self.user)

    def revoke_approval(self, commit=True):
        """
        Handle request to revoke the approval, return True iff approval was revoked.

        :::{note}
        `commit=False` means "perform validation and return what would have happened, but do not actually revoke"
        There is no way to "revoke" approval signoffs without committing the change.  Call again to do the actual revoke.
        :::
        """
        if not self.is_valid_approval_revoke_request():
            return False
        if commit:
            self.approval.revoke(self.user)
        return True


##########################
# APPROVAL PROCESS ACTIONS
##########################


class ApprovalProcessSignoffValidator(ApprovalSignoffValidator):
    """
    Default permissions validation logic for requests to Signoff on an Approval Process

    Implements`SignoffValidator` Protocol
    """

    def __init__(
        self,
        user: User,
        approval: AbstractApproval,
        approval_process: ApprovalsProcess,
        verify_signet: Callable[[AbstractSignoff], bool] = lambda signoff: True,
        verify_stamp: Callable[[AbstractSignoff], bool] = lambda signoff: True,
    ):
        """
        Initialize validator for signoffs on the given approval process.

        :param AbstractApproval approval: that approval for which to validate signoff requests
        :param Callable verify_signet: Optional function to validate request data against a signoff, or None to skip
        :param Callable verify_stamp: Optional function to validate request data, or None to skip

        Adds validation that the stamp being signed is one of the approval_process approval stamps.
        """
        super().__init__(
            user=user,
            approval=approval,
            verify_signet=verify_signet,
            verify_stamp=verify_stamp,
        )
        self.approval_process = approval_process

    def is_valid_signoff_request(self, signoff: AbstractSignoff) -> bool:
        """Return True iff signoff can be signed by user."""
        return super().is_valid_signoff_request(
            signoff
        ) and self.approval_process.user_can_proceed(self.approval, self.user)


def verify_consistent_process_stamp_id(
    approval_process, approval, signoff=None, request_stamp_id=None
):
    """
    Return True iff data relations for approval process, signoff, and request are self-consistent

    Validates that signoff.stamp, if it exists, is same object as approval.stamp, and optionally a stamp_id from request
    """
    return verify_consistent_stamp_id(approval, signoff, request_stamp_id) and (
        approval_process.contains_stamp(request_stamp_id) if request_stamp_id else True
    )


def get_verify_process_stamp(
    approval_process, approval, kwargs, stamp_id_key="stamp_id"
):
    """Helper to return a `verify_stamp` function with correct signature for use with `ApprovalSignoffValidator`"""
    return partial(
        verify_consistent_process_stamp_id,
        approval_process,
        approval,
        request_stamp_id=kwargs.get(stamp_id_key, None),
    )


class ApprovalProcessUserActions(BasicUserApprovalActions):
    """
    Concrete implementation that handles approval actions on an Approval Process model.

    An extensible base class for extending this case that
    implements SignoffRequestActions and ApprovalRequestActions Protocols
    Facade: delegation & orchestration of signoff_actions_class, and signoff & approval business logic and
            a `signoffs.process.ApprovalProcess` object for sequencing and permissions logic
    """

    validator_class: SignoffValidator = ApprovalProcessSignoffValidator

    def __init__(
        self,
        user,
        data,
        approval_process,
        approval,
        signoff_actions: SignoffRequestActions = None,
        validator: SignoffValidator = None,
        committer: SignoffCommitter = None,
        **kwargs,
    ):
        """
        Define actions available to the given user on the given approval_process based on request data

        :param user: typically the `request.user`
        :param dict data: a dict-like object, typically with the GET or POST data from the request
        :param approval_process: the `ApprovalProcess` that the signoff/revoke actions are applied to.
        :param approval: the `Approval` to apply signoff/revoke actions to or none to use `next_available_approval`.
        :param signoff_actions: a `SignoffRequestActions` object used to sign approvals, or None to use class default
        :param kwargs: additional parameters passed through to `BasicUserApprovalActions` initializer
        """
        self.approval_process = approval_process
        self.approval = approval
        if approval and not self.approval.subject:
            self.approval.subject = self.approval_process.process_model
        validator = validator or self.validator_class(
            user,
            self.approval,
            approval_process,
            verify_signet=get_verify_signet(kwargs),
            verify_stamp=get_verify_process_stamp(
                self.approval_process, self.approval, kwargs
            ),
        )
        super().__init__(
            user,
            data,
            self.approval,
            signoff_actions,
            validator=validator,
            committer=committer,
            **kwargs,
        )

    def is_valid_approve_request(self):
        """Return True iff the approval transition can be completed by user"""
        return self.verify_stamp() and self.approval_process.can_do_approve_transition(
            self.approval, self.user
        )

    def approve(self, commit=True):
        """
        Handle request to make approval transition, return True iff transition was made.

        :::{note}
        `commit=False` likely has no practical value, it is required for Protocol and possible future extensions
        Because transitions are not idempotent.  Call again to do the actual approval.
        :::
        """
        if not self.is_valid_approve_request():
            return False
        return (
            self.approval_process.try_approve_transition(self.approval, self.user)
            if commit
            else True
        )

    def is_valid_approval_revoke_request(self):
        """Return True iff revoke transition for the approval is available to user"""
        return self.verify_stamp() and self.approval_process.can_do_revoke_transition(
            self.approval, self.user
        )

    def revoke_approval(self, commit=True):
        """
        Handle request to make revoke approval transition, return True iff trnasition was made.

        :::{note}
        `commit=False` likely has no practical value, it is required for Protocol and possible future extensions
        Because transitions are not idempotent.  Call again to do the actual revoke.
        :::
        """
        if not self.is_valid_approval_revoke_request():
            return False
        return (
            self.approval_process.try_revoke_transition(self.approval, self.user)
            if commit
            else True
        )
