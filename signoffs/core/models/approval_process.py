"""
An Approval Process defines the business logic for progressing through a sequence of Approvals.
The basic AbstractApprovalProcess leaves it to app logic to order approvals - through introspection the approvals
    are ordered in alphabetical order (by attribute name) - but probably shouldn't build app logic around that.

The AbstractFsmApprovalProcess uses a Finite State Machine (provided by django-fsm integration) to define
    the ordering of approval.  Approvals become "available" when their state transition would be permitted.
    Generally, approvals are used to drive the state transitions, which are handled by django-fsm.
"""
import inspect
from functools import cached_property

from django.db import models
from django.core.exceptions import ImproperlyConfigured

from signoffs.core import approvals


class ApprovalTransitionSequence(dict):
    """
    Services for sequencing Approvals and mapping approval fields onto a state transition method.
    This sequencing allows an optional linear ordering, or for app logic to define the ordering.
    Without an explicit ordering, ordering is based on introspection for declared Approvals,
        which come ordered alphabetically NOT in the order in which they are declared (ugh).
    """
    def __init__(self, obj, ordering=None):
        """
        Define an approval sequence for all Approvals declared on given object
        Optionally ordered by an iterable of Approval Types, Fields, or field names.
        """
        approval_items = self._get_ordered_items(obj, ordering)
        super().__init__((name, getattr(obj, name)) for name, _ in approval_items)  # bound instance approvals!
        self.instance = obj
        self.is_ordered = bool(ordering)

    @classmethod
    def _get_approval_members(cls, obj):
        """ Return a list of 2-tuples (name, approval type) for Approval Types / Fields defined on type(obj) """
        def is_approval_field(attr):
            return (
                type(attr) is type and
                issubclass(attr, approvals.AbstractApproval)
            )

        return inspect.getmembers(obj.__class__, predicate=is_approval_field)

    def _get_ordered_items(self, obj, ordering):
        """
        Return an iterable of 2-tuples, (name, approval type), one for each approval, ordered by ordering, if given.
        Raise ImproperlyConfigured if an ordering is provided but does not match the approvals bound to object
        """
        approval_members = self._get_approval_members(obj)
        if not ordering:
            return approval_members  # no ordering - approvals will be in alphabetic-order by attr name

        lookup = {name: approval for name, approval in approval_members}
        approval_order = []
        for a in ordering:
            approval = lookup.get(a) if isinstance(a, str) else \
                a.approval_type if hasattr(a, 'approval_type') else a
            approval_order.append(approval)

        if set(approval_order) != set(a[1] for a in approval_members):
            raise ImproperlyConfigured(
                'Ordering {order} is inconsistent with approvals {approvals} declared on {obj}'.format(
                    order=approval_order, approvals=approval_members, obj=obj
                )
            )
        name = {approval: name for name, approval in approval_members}
        return ((name[approval], approval) for approval in approval_order)

    def _get_approval(self, approval):
        """ Lookup that bound approval by name if approval is a string, otherwise just return approval """
        return self[approval] if isinstance(approval, str) else approval

    def _get_callback_transition(self, approval, callback_name):
        """ Return the bound transition method that will be triggered by approval.<callback_name> callback, or None """
        approval = self._get_approval(approval)
        transition = approval._callbacks.callbacks.get(callback_name,None) if hasattr(approval, '_callbacks') else None
        return transition.__get__(self.instance) if inspect.isfunction(transition) else None

    def _on_callback_transitions(self, callback_name, by_name=True):
        """
        Return a dict mapping each approval (or its name) to its bound <callback_name> callback
            optionally in sequence ordering
        """
        return {
            (name if by_name else a): self._get_callback_transition(a, callback_name)
            for name, a in self.items() if hasattr(a, '_callbacks')
        }

    def on_approval_transition(self, approval):
        """ Return the bound transition method that will be triggered by approval.on_approval callback, or None """
        return self._get_callback_transition(approval, 'post_approval')

    def on_approval_transitions(self, by_name=True):
        """ Return a dict mapping each approval (or its name) to its bound on_approve callback """
        return self._on_callback_transitions('post_approval', by_name)

    def on_revoke_transition(self, approval):
        """ Return the bound transition method that will be triggered by approval.on_revoke callback, or None """
        return self._get_callback_transition(approval, 'post_revoke')

    def on_revoke_transitions(self, by_name=True):
        """ Return a dict mapping each approval (or its name) to its bound on_revoke callback """
        return self._on_callback_transitions('post_revoke', by_name)

    def get_all_approvals(self):
        """ Return list of all Approvals in this sequence. """
        return list(self.values())

    def get_approved_approvals(self):
        """ Return list of all approved Approvals in this sequence. """
        return [a for a in self.get_all_approvals() if a.is_approved()]

    def get_unapproved_approvals(self):
        """ Return list of all un-approved Approvals in this. """
        return [a for a in self.get_all_approvals() if not a.is_approved()]

    def can_proceed(self, approval):
        """ Return True if the transition triggered by given approval (or approval name) can proceed """
        approval = self._get_approval(approval)
        # proceed on any unapproved approvals if this sequence is unordered, otherwise only on the next approval in seq.
        return not approval.is_approved() and (
            not self.is_ordered or approval == self.get_unapproved_approvals()[0]
        )

    def get_available_approvals(self):
        """ Return list of approvals that can proceed based on available state transitions """
        return [approval for approval in self.values() if self.can_proceed(approval)]

    def can_revoke(self, approval):
        """ Return True if the transition triggered by revoking approval (or approval name) can proceed """
        approval = self._get_approval(approval)
        # revoke any approved approvals if this sequence is unordered, otherwise only on the previous approval in seq.
        return approval.is_approved() and (
            not self.is_ordered or approval == self.get_approved_approvals()[-1]
        )

    def get_revokable_approvals(self):
        """ Return list of approvals that can be revoked based on available state transitions """
        return [approval for approval in self.values() if self.can_revoke(approval)]


class AbstractApprovalProcess(models.Model):
    """
    Abstract Model Mixin defining access to set of ApprovalFields that generally drive state transitions
    This ApprovalProcess provides an ordering for Approvals declared on the model.
    Explicitly override approval_ordering with a list or tuple of Approvals, otherwise approvals are treated as
        unordered, and returned in alphabetical order (by attribute name - ugh!)
    """
    approval_sequence_class = ApprovalTransitionSequence
    approval_ordering = None

    class Meta:
        abstract = True

    @cached_property
    def approval_sequence(self):
        """ Return an object representing the sequence of ApprovalFields defined for this ApprovalProcess """
        return self.approval_sequence_class(self, self.approval_ordering)

    # Delegate to ApprovalTransitionSequence

    def get_all_approvals(self):
        """ Return all Approvals defined by ApprovalFields on this model. """
        return self.approval_sequence.get_all_approvals()

    def get_approved_approvals(self):
        """ Return all approved Approvals defined by ApprovalFields on this model. """
        return self.approval_sequence.get_approved_approvals()

    def get_unapproved_approvals(self):
        """ Return all un-approved Approvals defined by ApprovalFields on this model. """
        return self.approval_sequence.get_unapproved_approvals()

    def can_proceed(self, approval):
        """ Return True if the transition triggered by given approval (or approval name) can proceed """
        return self.approval_sequence.can_proceed(approval)

    def can_revoke(self, approval):
        """ Return True if the transition triggered by revoking the given approval (or approval name) can proceed """
        return self.approval_sequence.can_revoke(approval)

    def get_available_approvals(self):
        """ Return list with the next approval(s) available for signing """
        return self.approval_sequence.get_available_approvals()

    def get_next_available_approval(self):
        """ Return the next approval available for signing """
        try:
            return self.get_available_approvals()[0]
        except IndexError:
            return None

    def get_revokable_approvals(self):
        """ Return list with any approval(s) available for revoking """
        return self.approval_sequence.get_revokable_approvals()

    def get_next_revokable_approval(self):
        """ Return the next approval available for revoking """
        try:
            return self.get_revokable_approvals()[0]
        except IndexError:
            return None


class FsmApprovalTransitionSequence(ApprovalTransitionSequence):
    """
    An Approval Sequence that manages approvals configured to trigger django-fsm transition methods
    Dependency django-fsm must be installed
    """

    def can_proceed(self, approval, check_conditions=True):
        """ Return True if the transition triggered by given approval (or approval name) can proceed """
        import django_fsm
        approval = self._get_approval(approval)
        transition = self.on_approval_transition(approval)
        return (super().can_proceed(approval) and
                django_fsm.can_proceed(transition, check_conditions=check_conditions)) if transition else False

    def can_revoke(self, approval, check_conditions=True):
        """ Return True if the transition triggered by revoking approval (or approval name) can proceed """
        import django_fsm
        approval = self._get_approval(approval)
        transition = self.on_revoke_transition(approval)
        return (super().can_revoke(approval) and
                django_fsm.can_proceed(transition, check_conditions=check_conditions)) if transition else False

    def has_approval_transition_perm(self, approval, user):
        """ Returns True iff model in state allows transition from given approval by given user """
        import django_fsm
        transition = self.on_approval_transition(approval)
        return django_fsm.has_transition_perm(transition, user) if transition else True

    def has_revoke_transition_perm(self, approval, user):
        """ Returns True iff model in state allows transition for revoking given approval by given user """
        import django_fsm
        transition = self.on_revoke_transition(approval)
        return django_fsm.has_transition_perm(transition, user) if transition else True

    def user_can_proceed(self, user, approval, check_conditions=True):
        """ Return True if the user can proceed with the transition triggered by given approval (or approval name) """
        return (self.can_proceed(approval, check_conditions=check_conditions) and
                self.has_approval_transition_perm(approval, user))

    def user_can_revoke(self, user, approval, check_conditions=True):
        """ Return True if the user can proceed with transition triggered by revoking approval (or approval name) """
        return (self.can_revoke(approval, check_conditions=check_conditions) and
                self.has_revoke_transition_perm(approval, user))


class AbstractFsmApprovalProcess(AbstractApprovalProcess):
    """
    django-fsm integration with Approval Process
    Assumes approvals drive state changes managed by fsm transitions.
    Allows automation of Approval Process by following allowable state transitions defined by FSM.
    """
    approval_sequence_class = FsmApprovalTransitionSequence

    class Meta:
        abstract = True

    # Delegate to FsmApprovalTransitionSequence

    def has_approval_transition_perm(self, approval, user):
        """ Returns True iff model in state allows transition from given approval by given user """
        return self.approval_sequence.has_approval_transition_perm(approval, user)

    def has_revoke_transition_perm(self, approval, user):
        """ Returns True iff model in state allows transition for revoking given approval by given user """
        return self.approval_sequence.has_revoke_transition_perm(approval, user)

    def user_can_proceed(self, user, approval, check_conditions=True):
        """ Return True if the user can proceed with the transition triggered by given approval (or approval name) """
        return self.approval_sequence.user_can_proceed(user, approval, check_conditions=check_conditions)

    def user_can_revoke(self, user, approval, check_conditions=True):
        """ Return True if the user can proceed with transition triggered by revoking approval (or approval name) """
        return self.approval_sequence.user_can_revoke(user, approval, check_conditions=check_conditions)
