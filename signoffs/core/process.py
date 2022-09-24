"""
    Classes, Descriptors, and decorators for automating state transitions driven by an Approval Process
    Used to manage a multi-state approval process where approvals drive state transitions.
    django-fsm integration:
    - designed to work seamlessly with AbstractFsmApprovalProcess
"""
import inspect

from collections import defaultdict
from dataclasses import dataclass, field
from typing import Callable, Dict
from django.core.exceptions import ImproperlyConfigured
from django.db import transaction

from signoffs import registry
from signoffs.core import approvals


@dataclass
class ApprovalTransition:
    """
    Associate an Approval Type with callables representing transitions to take when approval actions are performed.
    When used with  ApprovalActionsRegistry, transition callables must take 2 arguments:
        - approval_process instance (usually named self on callable)
        - approval instance (the approval that is driving the transition
    """
    approval_id: str = None
    approve: Callable = None
    revoke: Callable = None

    @property
    def approve_name(self):
        return self.approve.__name__ if self.approve else ''

    @property
    def revoke_name(self):
        return self.revoke.__name__ if self.revoke else ''


@dataclass
class ApprovalTransitionRegistry:
    """ A registry associating Approval Types with the transitions that follow from approval actions """
    transitions: Dict = field(default_factory=lambda : defaultdict(ApprovalTransition))

    def __iter__(self):
        return iter(self.transitions.values())

    def add_approval(self, approval_type):
        """ Add given approval_type (or approval instance, or str id) to registry with no transitions (yet) """
        approval_id = registry.get_approval_id(approval_type)

        if approval_id not in self.transitions:
            self.transitions[approval_id] = ApprovalTransition(approval_id=approval_id)

    def add_approve_transition(self, approval_type, transition):
        """ Add a transition on approval for given approval_type (or approval instance, or str id) """
        approval_id = registry.get_approval_id(approval_type)

        t = self.transitions[approval_id]
        t.approval_id = approval_id  # in case this is a new entry
        t.approve = transition

    def add_revoke_transition(self, approval_type, transition):
        """ Add a transition on revoke for given approval_type (or approval instance, or str id) """
        approval_id = registry.get_approval_id(approval_type)

        t = self.transitions[approval_id]
        t.approval_id = approval_id  # in case this is a new entry
        t.revoke = transition

    def get(self, approval_type):
        """ Return the Approval Transition associated with the given approval_type (or ...), or None """
        approval_id = registry.get_approval_id(approval_type)
        return self.transitions.get(approval_id, None)   # use get here so access doesn't create a default entry!

    def approval_order(self):
        """ Return a list of approval id's, in the order they were added to the registry """
        return list(self.transitions.keys())


class BoundApprovalSequence(dict):
    """
    An (ordered) dictionary of Approval instances bound to an object, like an Approval Process, keyed by attribute name.
    Designed to work the approvals declared using an ApprovalField or RelatedApprovalDescriptor - for use in other
      cases, be sure type(obj) declares ApprovalType using same attribute name as approval instance on obj.
    Sequenced by an optional linear ordering, or left to app logic to define the ordering.
    Without an explicit ordering, ordering is based on introspection for declared Approvals,
        which come ordered alphabetically NOT in the order in which they are declared (ugh).
    """
    def __init__(self, obj, ordering):
        """
        Define the linear approval sequence as a list of Approval instances bound given object
        Ordering may by an iterable of Approval Types, Fields, or field names.
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
        # MUST inspect obj Type - accessing obj members evaluates descriptors, potentially causing inf. recursion.
        return inspect.getmembers(type(obj), predicate=is_approval_field)

    def _get_ordered_items(self, obj, ordering):
        """
        Return an iterable of 2-tuples, (name, approval type), one for each approval, ordered by ordering, if given.
        Raise ImproperlyConfigured if an ordering is provided but does not match the approvals bound to object
        """
        approval_members = self._get_approval_members(obj)
        if not ordering:
            return approval_members  # no ordering - approvals will be in alphabetic-order by attr name

        approval_order = [
            a.approval_type if hasattr(a, 'approval_type') else registry.get_approval_type(a)
                for a in ordering
        ]

        if set(approval_order) != set(a[1] for a in approval_members):
            raise ImproperlyConfigured(
                'Ordering {order} is inconsistent with approvals {approvals} declared on {obj}'.format(
                    order=approval_order, approvals=approval_members, obj=obj
                )
            )
        name = {approval: name for name, approval in approval_members}
        return ((name[approval], approval) for approval in approval_order)


class ApprovalActionsRegistry:
    """
    Associate approvals in an multi-approval process with functions (transitions) for approve and revoke actions
    Ensure actions preserve integrity of approval process state, keeping approval state and process state in sync.
    Most usefully defined on an ApprovalProcess class using the ApprovalActionsDescriptor,
        which provides decorators to define the transition registry.
    """
    def __init__(self, approval_process, transition_registry):
        """
        Associate the transition registry with the approval_process instance on which the approval actions will occur.
        Transition callables in the registry should be methods on the approval process, and
            take 2 arguments, e.g., make_transition(self, approval)
        """
        self.approval_process = approval_process
        self.registry = transition_registry
        self._validate_registry()
        self.seq = BoundApprovalSequence(approval_process, ordering=self.registry.approval_order())
        assert self.seq.is_ordered  # we don't have to ever check - Actions always have an ordered sequence of approvals

    def _validate_registry(self):
        """ Each transition must be a callable method on the approval process instance. """
        for transition in self.registry:
            for action in (a for a in (transition.approve, transition.revoke) if a is not None):
                if not (hasattr(self.approval_process, action.__name__) and
                        callable(action)):
                    raise ImproperlyConfigured(
                        'Transitions must be callable methods on the Approval Process object:'
                        f' {self.approval_process}.{action.__name__} does not exist or is not callable.'
                    )

    # access to approval transition sequencing

    def get_all_approvals(self):
        """ Return list of all Approval instances defined in this sequence for the approval_process """
        return list(self.seq.values())

    def get_approved_approvals(self):
        """ Return list of all approved Approvals in this sequence. """
        return [a for a in self.seq.values() if a.is_approved()]

    def get_unapproved_approvals(self):
        """ Return list of all un-approved Approvals in this. """
        return [a for a in self.seq.values() if not a.is_approved()]

    def get_next_approval(self):
        """ Return the "next" approval in sequence ready for signing - sensible only for ordered approvals """
        approvals = self.get_unapproved_approvals()
        return approvals[0] if approvals else None

    def next_approval_is_signed(self):
        """ Return True iff the "next" approval in sequence has at least one signatory """
        approval = self.get_next_approval()
        return approval.is_signed() if approval else False

    def get_previous_approval(self):
        """ Return the "last" approval in sequence that was approved - sensible only for ordered approvals """
        approvals = self.get_approved_approvals()
        return approvals[-1] if approvals else None

    def get_available_approvals(self):
        """ Return list of approvals that can proceed based on available state transitions """
        return [approval for approval in self.seq.values() if self.can_proceed(approval)]

    def get_next_available_approval(self):
        """ Return the next approval available for signing """
        try:
            return self.get_available_approvals()[0]
        except IndexError:
            return None

    def get_revokable_approvals(self):
        """ Return list of approvals that can be revoked based on available state transitions """
        return [approval for approval in self.seq.values() if self.can_revoke(approval)]

    def get_next_revokable_approval(self):
        """ Return the next approval available for revoking """
        try:
            return self.get_revokable_approvals()[0]
        except IndexError:
            return None

    # access to bound transition methods

    def bound_approve_transition(self, approval_type):
        """ Return the associated approve transition as a bound method of approval_process, or None"""
        t = self.registry.get(approval_type)
        return getattr(self.approval_process, t.approve_name) if t.approve is not None else None

    def bound_revoke_transition(self, approval_type):
        """ Return the associated revoke transition as a bound method of approval_process, or None"""
        t = self.registry.get(approval_type)
        return getattr(self.approval_process, t.revoke_name) if t.revoke is not None else None

    # encapsulated transition logic : conditions and processes for proceeding with transitions

    # Approve transition logic:

    def can_proceed(self, approval, **kwargs):
        """ Return True if signoffs on the approval can proceed -- is it next in sequence, available for signing, etc. """
        # proceed on any unapproved approvals if this sequence is unordered, otherwise only on the next approval in seq.
        return (
            not approval.is_approved() and
            approval == self.get_next_approval()
        )

    def has_approval_transition_perm(self, approval, user, **kwargs):
        """ Returns True iff model in state allows transition from given approval by given user """
        return True  # no special user permissions associated with non-FSM transitions

    def user_can_proceed(self, approval, user, **kwargs):
        """ Return True if the user can proceed with the transition triggered by given approval (or approval name) """
        return (
            self.can_proceed(approval, **kwargs) and
            self.has_approval_transition_perm(approval, user, **kwargs)
        )

    def can_do_approve_transition(self, approval, user, **kwargs):
        """ Return True iff all conditions are met for user to proceed with approval and make transition """
        # possible there is a transition or not - either way, we can more ahead as non-FSM transitions have no perms.
        return (
            approval.ready_to_approve() and
            self.has_approval_transition_perm(approval, user, **kwargs)
        )

    # Revoke transition logic:

    def can_revoke(self, approval, **kwargs):
        """ Return True if the transition triggered by revoking approval can proceed """
        # revoke the last approved in seq. if the active approval has no signoffs
        return approval.is_approved() and (
                approval == self.get_previous_approval() and
                not self.next_approval_is_signed()
        )

    def has_revoke_transition_perm(self, approval, user, **kwargs):
        """ Returns True iff model in state allows transition for revoking given approval by given user """
        return approval.can_revoke(user)

    def user_can_revoke(self, approval, user, **kwargs):
        """ Return True iff user can proceed with revoke transition triggered by given approval (or approval name) """
        return (
            self.can_revoke(approval, **kwargs) and
            self.has_revoke_transition_perm(approval, user, **kwargs)
        )

    def can_do_revoke_transition(self, approval, user, **kwargs):
        """ Return True iff all conditions are met for user to proceed with revoking approval and make transition """
        # possible there is a transition or not - either way, we can more ahead as non-FSM transitions have no perms.
        return (
            self.user_can_revoke(approval, user) and
            self.has_revoke_transition_perm(approval, user, **kwargs)
        )

    # Approval Actions: attempt to do the transitions

    def try_approve_transition(self, approval, user):
        """
        Approve the given approval instance, for the given user, if possible, and trigger the associated state transition
        Return True if the approval and state transition occurred, False otherwise.
        """
        if not self.can_do_approve_transition(approval, user):
            return False
        # Approval and associated transition are ready to go - do it and commit changes to DB
        approval.approve(commit=False)
        transition = self.bound_approve_transition(approval)
        transition(approval)
        with transaction.atomic():  # We want to do both the approval and state transition together, or do neither.
            approval.save()
            self.approval_process.save()
        return True

    def try_revoke_transition(self, approval, user):
        """
        Revoke the given approval instance, for the given user, if possible, and trigger the associated state transition
        Return True if the approval and state transition occurred, False otherwise.
        """
        if not self.can_do_revoke_transition(approval, user):
            return False
        # Approval and associated transition are ready to go - do it and commit changes to DB.
        with transaction.atomic(): # We want to do both the revoke and state transition together, or do neither.
            approval.revoke(user=user) #, commit=False)  # TODO: does it makes sense to allow defer commit on revoke?
            transition = self.bound_revoke_transition(approval)
            transition(approval)
            self.approval_process.save()
        return True


class FsmApprovalActionsRegistry(ApprovalActionsRegistry):
    """
    Associate approval actions (approve & revoke) with FSM state transitions (@transition decorated functions).
    Most usefully defined on an ApprovalProcess class using the FsmApprovalActionsDescriptor,
        which provides decorators to define the transition registry.
    Assumes that all transitions are FSM transitions and all are registered - will not proceed otherwise.
    """
    # TODO: consider adding a validation step to ensure every transition is a registered @transition (hasattr(???))

    # Approve FSM transition logic:

    def can_proceed(self, approval, check_conditions=True, **kwargs):
        """ Return True if signoffs on this approval can proceed -- including that it's transition can proceed """
        import django_fsm
        transition = self.bound_approve_transition(approval)
        fsm_can_proceed = django_fsm.can_proceed(transition, check_conditions=check_conditions) if transition else False
        return super().can_proceed(approval) and fsm_can_proceed

    def has_approval_transition_perm(self, approval, user, **kwargs):
        """ Returns True iff model in state allows transition from given approval by given user """
        import django_fsm
        transition = self.bound_approve_transition(approval)
        fsm_has_transition_perm = django_fsm.has_transition_perm(transition, user) if transition else False
        return super().has_approval_transition_perm(approval, user, **kwargs) and fsm_has_transition_perm

    def can_do_approve_transition(self, approval, user, **kwargs):
        """ Return True iff all conditions are met for user to proceed with approval and make transition """
        import django_fsm
        transition = self.bound_approve_transition(approval)
        fsm_can_proceed = (
            django_fsm.can_proceed(transition) and
            django_fsm.has_transition_perm(transition, user)
        ) if transition else False
        return super().can_do_approve_transition(approval, user, **kwargs) and fsm_can_proceed

    # Revoke transition logic:

    def can_revoke(self, approval, check_conditions=True, **kwargs):
        """ Return True if the transition triggered by revoking approval (or approval name) can proceed """
        import django_fsm
        transition = self.bound_revoke_transition(approval)
        fsm_can_proceed = django_fsm.can_proceed(transition, check_conditions=check_conditions) if transition else False
        return super().can_revoke(approval, **kwargs) and fsm_can_proceed


    def has_revoke_transition_perm(self, approval, user, **kwargs):
        """ Returns True iff model in state allows transition for revoking given approval by given user """
        import django_fsm
        transition = self.bound_revoke_transition(approval)
        fsm_has_transition_perm = django_fsm.has_transition_perm(transition, user) if transition else False
        return super().has_revoke_transition_perm(approval, user, **kwargs) and fsm_has_transition_perm

    def can_do_revoke_transition(self, approval, user, **kwargs):
        """ Return True iff all conditions are met for user to proceed with revoke and make transition """
        import django_fsm
        transition = self.bound_revoke_transition(approval)
        fsm_can_proceed = (
            django_fsm.can_proceed(transition) and
            django_fsm.has_transition_perm(transition, user)
        ) if transition else False
        return super().can_do_revoke_transition(approval, user, **kwargs) and fsm_can_proceed


class ApprovalActionsDescriptor:
    """
    Descriptor provides a set of decorators to conveniently load a transition registry,
     and inject an ApprovalActions object that manages it in place of the descriptor attribute.
    """

    transition_registry_class = ApprovalTransitionRegistry
    approval_actions_class = ApprovalActionsRegistry

    def __init__(self, *approval_sequence, transition_registry=None, approval_actions=None):
        """
        Optionally: define a linear approval sequence - default is sequenced by order approvals are registered
        Optionally: override the registry and actions classes to use if the defaults are not suitable
        """
        self.registry = transition_registry() if transition_registry else self.transition_registry_class()
        self.approval_actions = approval_actions or self.approval_actions_class
        # This allows one to explicitly set the approval sequence rather than relying on order of transition functions
        for a in approval_sequence:
            self.registry.add_approval(self._get_approval_id(a))

    @staticmethod
    def _get_approval_id(approval_descriptor_or_type):
        """ "approval_type" may be a string approval id, an actual ApprovalType, or an ApprovalDescriptor """
        return approval_descriptor_or_type if isinstance(approval_descriptor_or_type, str) else \
            getattr(approval_descriptor_or_type, 'approval_type', approval_descriptor_or_type).id

    def register_approve_transition(self, approval_descriptor_or_type):
        """
        Return a decorator that adds the decorated function to the approval_actions registry for
        approving the approval_type or ApprovalField descriptor
        """
        def decorator(transition_method):
            approval_type = self._get_approval_id(approval_descriptor_or_type)
            self.registry.add_approve_transition(approval_type, transition_method)
            return transition_method
        return decorator

    def register_revoke_transition(self, approval_descriptor_or_type):
        """
        Return a decorator that adds the decorated function to the approval_actions registry for
        revoking the approval_type or ApprovalField descriptor
        """
        def decorator(transition_method):
            approval_type = self._get_approval_id(approval_descriptor_or_type)
            self.registry.add_revoke_transition(approval_type, transition_method)
            return transition_method
        return decorator

    def __set_name__(self, owner, name):
        """ Grab the field name used by owning class to refer to this descriptor """
        self.accessor_attr = name

    def __get__(self, instance, owner=None):
        """ Return an ApprovalActions object to manage the transition registry for the given instance """
        if not instance:
            return self
        else:
            actions = self.approval_actions(approval_process=instance, transition_registry=self.registry)
            setattr(instance, self.accessor_attr, actions)
            return actions


ApprovalActions = ApprovalActionsDescriptor   # A nicer name


class FsmApprovalActionsDescriptor(ApprovalActionsDescriptor):
    """ Uses FSM Approval Actions to manage FSM state transitions """
    approval_actions_class = FsmApprovalActionsRegistry


FsmApprovalActions = FsmApprovalActionsDescriptor   # A nicer name
