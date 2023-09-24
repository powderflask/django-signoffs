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
Thus, they provide reusable, composable View logic, outside the Views hierarchy.
For best cohesion: the `Signoff.logic` and `Approval.logic` objects implement all business rules
while an `Action` object just orchestrates them - resist temptation to encode business rules in Actions!

The protocols and actions provided here are sufficient to handle a range of basic use-cases.
They are not intended to be exhaustive - consider them as a skeleton to demonstrate how a signoff request might
typically be handled.
"""
from __future__ import annotations

from typing import Protocol

from django.core.exceptions import ImproperlyConfigured
from django.db import transaction

import signoffs.registry
from signoffs.approvals import AbstractApproval
from signoffs.process import ApprovalsProcess
from signoffs.signoffs import AbstractSignoff


##################
#  SIGNOFF ACTIONS
##################


class SignoffRequestActions(Protocol):
    """Basic API to process a signoff request"""
    signoff: AbstractSignoff

    def get_signoff_form(self):
        """Return the signoff form bound to data or None if no valid signoff form could be constructed"""
        ...

    def sign_signoff(self, commit=True):
        """ Handle request to sign the signoff, return True iff signoff was signed """
        ...

    def get_revoke_form(self):
        """Return a revoke form bound to data or None if no valid signoff form could be constructed"""
        ...

    def revoke_signoff(self, commit=True):
        """ Handle request to revoke the signoff, return True iff signoff was revoked """
        ...


class BasicUserSignoffActions:
    """
    Concrete SignoffRequestActions to handle simple signoff requests that don't trigger any follow-up actions

    An extensible base class for extending this simple case that
    implements `SignoffRequestActions` Protocol
    Facade: delegation to signoff's business logic
    """

    signoff_id_key = "signoff_id"
    """default name of data key (i.e., form field) for retrieving signoff_id from data dict"""

    def __init__(self, user, data, signoff_id_key=None, *args, **kwargs):
        """
        Define actions available to the given user based on request data
        :param user: typically the request.user
        :param dict data: a dict-like object, typically with the GET or POST data from the request
        :param signoff_id_key: data key with signoff_id, or None to use class default
        :param args, kwargs: additional parameters for provisioning objects, typically the view args & kwargs
        """
        self.user = user
        self.data = data
        self.signoff_id_key = signoff_id_key or self.signoff_id_key
        self.args = args
        self.kwargs = kwargs
        self.signoff = None  # populated by calling sign_ or revoke_signoff

    # "Template Method" hooks: to extend / override sign_signoff without duplicating core algorithm

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

    def is_valid_signoff_request(self, signoff):
        """Return True iff signoff can be signed."""
        return signoff.can_sign(self.user)

    def signoff_success(self, signoff):
        """Return value for successful signoff."""
        return True

    def signoff_failed(self, signoff, signoff_form):
        """Return value for failed signoff on given signoff_form (which may be None)."""
        return False

    # Core algorithm:  Provision a signoff form, validate, and attempt to sign it.

    def sign_signoff(self, commit=True):
        """ Handle request to sign a signoff form defied in data, return True iff signoff was signed """
        signoff_form = self.get_signoff_form()
        if signoff_form and signoff_form.is_valid():
            self.signoff = signoff_form.sign(user=self.user, commit=False)
            if self.signoff and self.is_valid_signoff_request(self.signoff):
                if commit:
                    self.signoff.sign(self.user)
                return self.signoff_success(self.signoff)
        return self.signoff_failed(self.signoff, signoff_form)

    # "Template Method" hooks: to extend / override revoke_signoff without duplicating core algorithm

    def get_revoke_form(self):
        """Return a revoke form bound to data or None if no valid signoff form could be constructed"""
        signoff_type = self.get_signoff_type()
        return signoff_type.forms.get_revoke_form(self.data) if signoff_type else None

    def verify_signet_id(self, signoff):
        """ As an extra data integrity check, revoke URL's may also contain the signet_id - check it matches """
        signet_id = signoff.signet.pk
        return signet_id == self.kwargs.get('signet_id', signet_id)

    def is_valid_revoke_request(self, signoff):
        """Return True iff signoff can be revoked."""
        return self.verify_signet_id(signoff) and signoff.can_revoke(self.user)

    def revoke_success(self, signoff):
        """Return value for successful revoke."""
        return True

    def revoke_failed(self, signoff):
        """Return value for failed revoke."""
        return False

    # Core algorithm:  Provision a signoff form, validate, and attempt to sign it.

    def revoke_signoff(self, commit=True):
        """
        Handle request to revoke given signoff, return True iff signoff was revoked

        :::{note}
        `commit=False` means "perform validation and return what would have happened, but do not actually revoke"
        There is no way to "revoke" a signoff without committing the change.  Call again to do the actual revoke.
        :::
        """
        revoke_form = self.get_revoke_form()
        if revoke_form and revoke_form.is_valid():
            self.signoff = revoke_form.revoke(user=self.user, commit=False)
            if self.is_valid_revoke_request(self.signoff):
                if commit:
                    self.signoff.revoke(self.user)
                return self.revoke_success(self.signoff)
        return self.revoke_failed(self.signoff)


##################
# APPROVAL ACTIONS
##################


class ApprovalRequestActions(Protocol):
    """Basic API to process an approval request"""

    signoff: AbstractSignoff
    approval: AbstractApproval

    def approve(self, commit=True):
        """Handle request to approve the approval, return True iff it was approved."""
        ...

    def revoke_approval(self, commit=True):
        """ Handle request to revoke approval, return True iff approval was revoked """
        ...


class BasicUserApprovalActions:
    """
    Concrete implementation that handles simple approvals that don't trigger any follow-up actions

    An extensible base class for extending this simple case that
    implements SignoffRequestActions and ApprovalRequestActions Protocols
    Facade: delegation & orchestration of signoff_actions_class, and signoff & approval business logic.
    """
    signoff_actions_class = BasicUserSignoffActions

    def __init__(self, user, data, approval, signoff_actions=None, *args, **kwargs):
        """
        Define actions available to the given user on the given approval based on request data
        :param user: typically the `request.user`
        :param dict data: a dict-like object, typically with the GET or POST data from the request
        :param approval: the `Approval` that the signoff/revoke actions are applied to.
        :param signoff_actions: a `SignoffRequestActions` object used to sign approvals, or None to use class default
        :param args, kwargs: additional parameters for provisioning objects, typically the view args & kwargs
        """
        self.user = user
        self.data = data
        self.approval=approval
        self.signoff_actions = signoff_actions or self.signoff_actions_class(user, data, **kwargs)
        self.args = args
        self.kwargs = kwargs

    # SignoffRequestActions Protocol - delegate to signoff_actions with add'l approval constraints / operations

    @property
    def signoff(self):
        """Populated by calling sign_ or revoke_signoff"""
        signoff = self.signoff_actions.signoff
        # override the signoff.subject with approval, which might be bound to a higher-level subject,
        #   like an approval_process.  But don't alter the approval type - validation catches inconsistencies.
        if signoff and (not signoff.subject or signoff.subject == self.approval):
            signoff.subject = self.approval
        return signoff

    def validate_relations(self, signoff=None):
        """
        Return True if data relations for all objects are self-consistent

        This is a hook for subclasses to provide additional data validation logic
        Default logic validates that signoff.stamp, if it exists, is same object as approval.stamp
        """
        if not self.approval:
            return False
        stamp_id = self.approval.stamp.id
        signoff_stamp_id = getattr(signoff.signet, 'stamp_id', stamp_id) if signoff else None
        return (
            stamp_id == self.kwargs.get('stamp_id', stamp_id) and
            stamp_id == (signoff_stamp_id or stamp_id)
        )

    def is_valid_approval_signoff_request(self, signoff):
        """ Return True iff user is allowed to sign the given signoff on the given approval """
        return self.validate_relations(signoff) and self.approval.can_sign(self.user, signoff)

    def get_signoff_form(self):
        """Return the signoff form bound to data or None if no valid signoff form could be constructed"""
        return self.signoff_actions.get_signoff_form()

    def sign_signoff(self, commit=True):
        """
        Handle request to sign a signoff form for the approval, return True iff signoff succeeded

        Approve the approval, if it is ready following the signoff save.
        :::{caution}
        Potential sync. issue here if approval has cached / prefetched signoffs - don't do that!
        :::
        """
        signed = self.signoff_actions.sign_signoff(commit=False)
        if not signed or not self.is_valid_approval_signoff_request(self.signoff):
            return False

        if commit:
            with transaction.atomic():
                self.signoff.save()
                self.approve()
        return True

    def is_valid_revoke_signoff_request(self, signoff):
        """Return True iff signoff on this approval can be revoked."""
        return self.validate_relations(signoff) and self.approval.can_revoke_signoff(signoff, self.user)

    def get_revoke_form(self):
        """Return a revoke form bound to data or None if no valid signoff form could be constructed"""
        return self.signoff_actions.get_revoke_form()

    def revoke_signoff(self, commit=True):
        """
        Handle request to revoke a signoff from this approval, return True iff revoke succeeded

        :::{note}
        `commit=False` means "perform validation and return what would have happened, but do not actually revoke"
        There is no way to "revoke" a signoff without committing the change.  Call again to do the actual revoke.
        :::
        """
        revoked = self.signoff_actions.revoke_signoff(commit=False)
        if not revoked or not self.is_valid_revoke_signoff_request(self.signoff):
            return False
        if commit:
            self.signoff_actions.revoke_signoff()
        return True

    # ApprovalActions Protocol

    def is_valid_approve_request(self):
        """ Return True iff the approval is complete and ready to be approved """
        return self.validate_relations() and self.approval.ready_to_approve()

    def approve(self, commit=True):
        """
        Handle request to approve the approval, return True iff it was approved.
        """
        if not self.is_valid_approve_request():
            return False
        self.approval.approve(commit=commit)
        return self.approval.is_approved()

    def is_valid_approval_revoke_request(self):
        """ Return True iff user is allowed to revoke the given approval """
        return self.validate_relations() and self.approval.can_revoke(self.user)

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


class ApprovalProcessUserActions(BasicUserApprovalActions):
    """
    Concrete implementation that handles approval actions on an Approval Process model.

    An extensible base class for extending this case that
    implements SignoffRequestActions and ApprovalRequestActions Protocols
    Facade: delegation & orchestration of signoff_actions_class, and signoff & approval business logic and
            a `signoffs.process.ApprovalProcess` object for sequencing and permissions logic
    """

    def __init__(self, user, data, approval_process, approval=None, signoff_actions=None, *args, **kwargs):
        """
        Define actions available to the given user on the given approval_process based on request data
        :param user: typically the `request.user`
        :param dict data: a dict-like object, typically with the GET or POST data from the request
        :param approval_process: the `ApprovalProcess` that the signoff/revoke actions are applied to.
        :param approval: the `Approval` to apply signoff/revoke actions to or none to use `next_available_approval`.
        :param signoff_actions: a `SignoffRequestActions` object used to sign approvals, or None to use class default
        :param args, kwargs: additional parameters for provisioning objects, typically the view args & kwargs
        """
        self.approval_process = approval_process
        self.approval = approval or self.approval_process.get_next_available_approval()
        if not self.approval.subject:
            self.approval.subject = self.approval_process.process_model
        super().__init__(user, data, self.approval, signoff_actions, *args, **kwargs)

    def is_valid_approve_request(self):
        """ Return True iff the approval transition can be completed by user """
        return self.validate_relations() and self.approval_process.can_do_approve_transition(self.approval, self.user)

    def approve(self, commit=True):
        """
        Handle request to make approval transition, return True iff transition was made.

        :::{note}
        `commit=False` likely has no practical value, it is required for Protocol and possible future extensions
        Because transistions are not idemponent.  Call again to do the actual approval.
        :::
        """
        if not self.is_valid_approve_request():
            return False
        return self.approval_process.try_approve_transition(self.approval, self.user) if commit else True

    def is_valid_approval_revoke_request(self):
        """Return True iff revoke transition for the approval is available to user"""
        return self.validate_relations() and self.approval_process.can_do_revoke_transition(self.approval, self.user)

    def revoke_approval(self, commit=True):
        """
        Handle request to make revoke approval transition, return True iff trnasition was made.

        :::{note}
        `commit=False` likely has no practical value, it is required for Protocol and possible future extensions
        Because transistions are not idemponent.  Call again to do the actual revoke.
        :::
        """
        if not self.is_valid_approval_revoke_request():
            return False
        return self.approval_process.try_revoke_transition(self.approval, self.user) if commit else True
