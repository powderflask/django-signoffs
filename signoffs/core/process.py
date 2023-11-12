"""
    Classes, Descriptors, and decorators for coordinating state transitions driven by an Approval Process
    Used to manage a multi-state approval process where state transitions are triggered by Approvals.
    Core responsibility: ensure integrity / consistency of approval state and state transitions

    A "transition" is just a method on your process model that manages a single state transition.
    An "approval transition" is a transition that is dependent on an Approval being approved or revoked.

    Transitions handle side-effects.  Generally, decorators, like django_fsm.transition, are used to perform
        any state transitions (like approvals or revokes), and like django_fsm, these state changes must be
        saved to the DB as a separate step after a successful transition is made.
        See convenience methods BasicApprovalProcess.try_*_transition for examples of how to correctly compelte a transition.

    django-fsm integration:
        - FSMApprovalProcess enforces FSM logic withing the BasicApprovalProcess API
        - FSMApprovalProcessDescriptor provides a declarative syntax for defining an FSM Approval Process
"""
import inspect
from collections import defaultdict
from dataclasses import dataclass, field
from functools import wraps
from typing import Any, Callable, Dict

from django.core.exceptions import ImproperlyConfigured
from django.db import models, transaction

from signoffs import registry
from signoffs.core import approvals, renderers


@dataclass
class ApprovalTransition:
    """
    Associate an Approval Type with callables representing transitions to take when approval actions are performed.
    When used with  BasicApprovalProcess, transition callables must take 2 arguments:
        - process_model instance (usually named self on callable)
        - approval instance (the approval that is driving the transition
    """

    approval_id: str = None
    approve: Callable = None
    revoke: Callable = None

    @property
    def approve_name(self):
        return self.approve.__name__ if self.approve else ""

    @property
    def revoke_name(self):
        return self.revoke.__name__ if self.revoke else ""


@dataclass
class ApprovalTransitionRegistry:
    """A registry associating Approval Types with the transition function that implement approval actions"""

    transitions: Dict = field(default_factory=lambda: defaultdict(ApprovalTransition))

    def __iter__(self):
        return iter(self.transitions.values())

    def add_approval(self, approval_type):
        """Add given approval_type (or approval instance, or str id) to registry with no transitions (yet)"""
        approval_id = registry.get_approval_id(approval_type)

        if approval_id not in self.transitions:
            self.transitions[approval_id] = ApprovalTransition(approval_id=approval_id)

    def add_approve_transition(self, approval_type, transition):
        """Add a transition function that approves the given approval_type (or approval instance, or str id)"""
        approval_id = registry.get_approval_id(approval_type)

        t = self.transitions[approval_id]
        t.approval_id = approval_id  # in case this is a new entry
        t.approve = transition

    def add_revoke_transition(self, approval_type, transition):
        """Add a transition that revokes for given approval_type (or approval instance, or str id)"""
        approval_id = registry.get_approval_id(approval_type)

        t = self.transitions[approval_id]
        t.approval_id = approval_id  # in case this is a new entry
        t.revoke = transition

    def get(self, approval_type):
        """Return the Approval Transition associated with the given approval_type (or ...), or None"""
        approval_id = registry.get_approval_id(approval_type)
        # directly accesing self.transitions.approval_id would create a default entry!
        return self.transitions.get(approval_id, None)

    def approval_order(self):
        """Return a list of approval id's, in the order they were added to the registry"""
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
        super().__init__(
            (name, getattr(obj, name)) for name, _ in approval_items
        )  # bound instance approvals!
        self.instance = obj
        self.is_ordered = bool(ordering)

    @classmethod
    def _get_approval_members(cls, obj):
        """Return a list of 2-tuples (name, approval type) for Approval Types / Fields defined on type(obj)"""

        def is_approval_field(attr):
            return type(attr) is type and issubclass(attr, approvals.AbstractApproval)

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
            a.approval_type
            if hasattr(a, "approval_type")
            else registry.get_approval_type(a)
            for a in ordering
        ]

        if not set(a.id for a in approval_order).issubset(
            set(a[1].id for a in approval_members)
        ):
            raise ImproperlyConfigured(
                f"Ordering {approval_order} is inconsistent with approvals {approval_members} declared on {obj}"
            )
        name = {approval: name for name, approval in approval_members}
        return ((name[approval], approval) for approval in approval_order)


@dataclass
class AbstractPersistTransition:
    """
    Callable to save objects modified by a transition to the DB (and/or perform other follow-up actions)
    BasicApprovalProcess.try_*_transition methods call it on successful transition.
    A transition fn decorated with BasicApprovalProcess.do_approval or .do_revoke will return an appropriate PersistTransition object.
    """

    instance: models.Model
    approval: approvals.AbstractApproval
    result: Any

    def __call__(self, *args, **kwargs):
        """Do whatever is needed to persist transition"""
        raise NotImplementedError


class TransactionSave(AbstractPersistTransition):
    """Callable to save modified objects in a transaction to maintain data integrity"""

    def __call__(self, *args, **kwargs):
        """Save the transitioned instance and the approved approval in a transaction"""
        with transaction.atomic():  # Do both the approval and state transition together, or do neither.
            self.approval.save()
            self.instance.save()


@dataclass
class TransactionRevoke(AbstractPersistTransition):
    """Callable to revoke the approval and save modified objects in a transaction to maintain data integrity"""

    def __call__(self, user, *args, **kwargs):
        """Save the transitioned instance and revoke the approval for given user in a transaction"""
        with transaction.atomic():  # Do both the revoke and state transition together, or do neither.
            self.approval.revoke(user=user)
            self.instance.save()


# TODO: define ApprovalProcess Protocol


class BasicApprovalProcess:
    """
    Associate approval actions in a multi-approval process with functions (transitions) that trigger those actions
    Ensure actions preserve integrity of approval process state, keeping approval state and process state in sync.
    Most usefully defined on an Approval Process Model class using the ApprovalProcessDescriptor,
        which provides decorators to define and register the transitions.
    """

    approval_sequence_class = BoundApprovalSequence
    transition_save_class = TransactionSave
    transition_revoke_class = TransactionRevoke

    render: renderers.ApprovalProcessRenderer = (
        renderers.ApprovalProcessRenderer()
    )  # presentation logic service

    def __init__(self, process_model, transition_registry, approval_sequence=None):
        """
        Associate the transition registry with the approval process_model instance on which the transitions are defined.
        Process model is a class that typically defines a set of ApprovalField's and transition functions.
        Transition callables in the registry should be methods on the approval process_model, and
            take 2 positional arguments, e.g., make_transition(self, approval)
        """
        self.process_model = process_model
        self.registry = transition_registry
        self._validate_registry()
        self.seq = approval_sequence or self.approval_sequence_class(
            process_model, ordering=self.registry.approval_order()
        )
        assert self.seq.is_ordered  # Actions always have ordered sequence

    def _validate_registry(self):
        """Each transition must be a callable method on the approval process instance."""
        for transition in self.registry:
            for action in (
                a for a in (transition.approve, transition.revoke) if a is not None
            ):
                if not (
                    hasattr(self.process_model, action.__name__) and callable(action)
                ):
                    raise ImproperlyConfigured(
                        "Transitions must be callable methods on the Approval Process object:"
                        f" {self.process_model}.{action.__name__} does not exist or is not callable."
                    )

    # access to approval transition sequencing

    def __iter__(self):
        return iter(self.get_all_approvals())

    def get_all_approvals(self):
        """Return list of all Approval instances defined in this sequence for the process_model"""
        return list(self.seq.values())

    def get_approved_approvals(self):
        """Return list of all approved Approvals in this sequence."""
        return [a for a in self.seq.values() if a.is_approved()]

    def get_unapproved_approvals(self):
        """Return list of all un-approved Approvals in this."""
        return [a for a in self.seq.values() if not a.is_approved()]

    def get_next_approval(self):
        """Return the "next" approval in sequence ready for signing - sensible only for ordered approvals"""
        approvals = self.get_unapproved_approvals()
        return approvals[0] if approvals else None

    def next_approval_is_signed(self):
        """Return True iff the "next" approval in sequence has at least one signatory"""
        approval = self.get_next_approval()
        return approval.is_signed() if approval else False

    def get_previous_approval(self):
        """Return the "last" approval in sequence that was approved - sensible only for ordered approvals"""
        approvals = self.get_approved_approvals()
        return approvals[-1] if approvals else None

    def get_available_approvals(self):
        """Return list of approvals that can proceed based on available state transitions"""
        return [
            approval for approval in self.seq.values() if self.can_proceed(approval)
        ]

    def get_next_available_approval(self):
        """Return the next approval available for signing"""
        try:
            return self.get_available_approvals()[0]
        except IndexError:
            return None

    def is_signable_approval(self, approval):
        """Return True iff the given approval is signable within the process"""
        return approval in self.get_available_approvals()

    def get_revokable_approvals(self):
        """Return list of approvals that can be revoked based on available state transitions"""
        return [
            approval for approval in self.seq.values() if self.is_revokable(approval)
        ]

    def get_next_revokable_approval(self):
        """Return the next approval available for revoking"""
        try:
            return self.get_revokable_approvals()[0]
        except IndexError:
            return None

    def is_revokable_approval(self, approval):
        """Return True iff the given approval is revokable within the process"""
        return approval in self.get_revokable_approvals()

    def contains_stamp(self, stamp_id):
        """Return True iff the given stamp pk is among those that are part of this approval process"""
        return stamp_id in (a.stamp.pk for a in self.get_all_approvals())

    # access to bound transition methods

    def bound_approve_transition(self, approval_type):
        """Return the associated approve transition as a bound method of process_model, or None"""
        t = self.registry.get(approval_type)
        has_transtion = t is not None and t.approve is not None
        return getattr(self.process_model, t.approve_name) if has_transtion else None

    def bound_revoke_transition(self, approval_type):
        """Return the associated revoke transition as a bound method of process_model, or None"""
        t = self.registry.get(approval_type)
        has_transtion = t is not None and t.revoke is not None
        return getattr(self.process_model, t.revoke_name) if has_transtion else None

    # encapsulated transition logic : conditions and processes for coordinating approval and state transitions

    # Approve transition logic:

    def can_proceed(self, approval, **kwargs):
        """
        Return True iff signoff on the approval can proceed
            -- is it next in sequence, available for signing, etc.
        """
        # proceed on any unapproved approvals if this sequence is unordered, otherwise only on the next approval in seq.
        return not approval.is_approved() and approval == self.get_next_approval()

    def has_approval_transition_perm(self, approval, user, **kwargs):
        """Returns True iff model in state allows transition from given approval by given user"""
        return True  # no special permissions associated with approve actions for non-FSM transitions

    def user_can_proceed(self, approval, user, **kwargs):
        """Return True if the user can proceed with signing the given approval (or approval name)"""
        return self.can_proceed(
            approval, **kwargs
        ) and self.has_approval_transition_perm(approval, user, **kwargs)

    def can_do_approve_transition(self, approval, user, **kwargs):
        """Return True iff all conditions are met for user to proceed with approval and make transition"""
        # possible there is a transition or not - either way, we can move ahead as non-FSM transitions have no perms.
        # don't call approval.ready_to_approve to avoid potential recursion.  Duplicate code instead :-(
        return approval.ready_to_approve() and self.user_can_proceed(
            approval, user, **kwargs
        )

    # Revoke transition logic:

    def is_revokable(self, approval, **kwargs):
        """Return True if the approval can be revoked"""
        # default behaviour: can revoke the latest approved approval in seq. iff the next approval has no signoffs
        return approval.is_revokable() and (
            approval == self.get_previous_approval()
            and not self.next_approval_is_signed()
        )

    def has_revoke_transition_perm(self, approval, user, **kwargs):
        """Returns True iff model state allows transition revoking given approval by given user"""
        return approval.is_permitted_revoker(user)

    def user_can_revoke(self, approval, user, **kwargs):
        """Return True iff user can proceed with revoke transition triggered by given approval (or approval name)"""
        return self.is_revokable(
            approval, **kwargs
        ) and self.has_revoke_transition_perm(approval, user, **kwargs)

    def can_do_revoke_transition(self, approval, user, **kwargs):
        """Return True iff all conditions are met for user to proceed with revoking approval and make transition"""
        # possible there is a transition or not - either way, we can more ahead as non-FSM transitions have no perms.
        return self.user_can_revoke(approval, user, **kwargs)

    # Approval Transition Decorators

    @classmethod
    def do_approval(cls, transition_method):
        """
        Wrap transition_method with do_approval decorator that also
            returns a transition_save_class object to handle follow-up persistence logic
        """

        @wraps(transition_method)
        def _return_save_callable(instance, approval, *args, **kwargs):
            """Complete the transition & approval, return a callable to complete the follow-up state change saves"""
            result = transition_method(instance, approval, *args, **kwargs)
            approval.approve(commit=False)
            return cls.transition_save_class(instance, approval, result)

        return _return_save_callable

    @classmethod
    def do_revoke(cls, transition_method):
        """
        Wrap transition_method so it returns a  transition_revoke_class object to handle any follow-up persistence logic
        """

        @wraps(transition_method)
        def _return_revoke_callable(instance, approval, *args, **kwargs):
            """Complete the transition and return a callable to handle the revoke and state change saves"""
            result = transition_method(instance, approval, *args, **kwargs)
            return cls.transition_revoke_class(instance, approval, result)

        return _return_revoke_callable

    # Approval Transition Actions: attempt to do the transitions

    def try_approve_transition(self, approval, user):
        """
        Trigger the associated state transition to approve the given approval instance, for the given user, if possible
        Convenience method to wrap up 3 steps commonly done together:
            1) determine if the approval is ready to be approved and any associated state transition can be made;
            2) trigger the transition that makes the approval
            3) save the approval and any process_model state changes using this process's transition save object
        Transition function should return a transition_save_class callable to save all objects modified by transition
        Return True if the approval and state transition occurred, False otherwise.
        """
        if not self.can_do_approve_transition(approval, user):
            return False
        # Trigger the transition function that approves the approval
        transition = self.bound_approve_transition(approval)
        save = transition(approval)
        if isinstance(save, self.transition_save_class):
            save()
        else:
            save = self.transition_save_class(self.process_model, approval, save)
            save()
        return True

    def try_revoke_transition(self, approval, user):
        """
        Trigger the associated state transition to revoke the given approval instance, for the given user, if possible
        Convenience method to wrap up 3 steps commonly done together:
            1) determine if the approval can be revoked by user and any associated state transition can be made;
            2) trigger the transition that goes with revoking the approval
            3) revoke the approval and save any process_model state changes, using this process's transition revoke
        Transition function should return a transition_revoke_class callable to save all objects modified by transition
        Return True if the revoke and state transition occurred, False otherwise.
        """
        if not self.can_do_revoke_transition(approval, user):
            return False
        # Trigger the transition function that revokes the approval
        transition = self.bound_revoke_transition(approval)
        revoke = transition(approval)
        if isinstance(revoke, self.transition_revoke_class):
            revoke(user)
        else:
            revoke = self.transition_revoke_class(self.process_model, approval, revoke)
            revoke(user)
        return True


class FsmApprovalProcess(BasicApprovalProcess):
    """
    An ApprovalProcss that associate approval actions (approve & revoke)
        with FSM state transitions (@transition decorated functions).
    Most usefully defined on an Approval Process Model class using the FsmApprovalProcessDescriptor,
        which provides decorators to define and register the approval actions on FSM transitions.
    Assumes that all transitions are FSM transitions and all are registered - will not proceed otherwise.
    """

    # Approve FSM transition logic:

    def can_proceed(self, approval, check_conditions=True, **kwargs):
        """Return True if signoffs on this approval can proceed -- including that it's transition can proceed"""
        import django_fsm

        transition = self.bound_approve_transition(approval)
        fsm_can_proceed = (
            django_fsm.can_proceed(transition, check_conditions=check_conditions)
            if transition
            else True
        )
        return super().can_proceed(approval) and fsm_can_proceed

    def has_approval_transition_perm(self, approval, user, **kwargs):
        """Returns True iff model in state allows transition from given approval by given user"""
        import django_fsm

        transition = self.bound_approve_transition(approval)
        fsm_has_transition_perm = (
            django_fsm.has_transition_perm(transition, user) if transition else True
        )
        return (
            super().has_approval_transition_perm(approval, user, **kwargs)
            and fsm_has_transition_perm
        )

    def can_do_approve_transition(self, approval, user, **kwargs):
        """Return True iff all conditions are met for user to proceed with approval and make transition"""
        import django_fsm

        transition = self.bound_approve_transition(approval)
        fsm_can_proceed = (
            (
                django_fsm.can_proceed(transition)
                and django_fsm.has_transition_perm(transition, user)
            )
            if transition
            else True
        )
        return (
            super().can_do_approve_transition(approval, user, **kwargs)
            and fsm_can_proceed
        )

    # Revoke FSM transition logic:

    def is_revokable(self, approval, check_conditions=True, **kwargs):
        """Return True if the transition triggered by revoking approval (or approval name) can proceed"""
        import django_fsm

        transition = self.bound_revoke_transition(approval)
        fsm_can_proceed = (
            django_fsm.can_proceed(transition, check_conditions=check_conditions)
            if transition
            else False
        )
        return super().is_revokable(approval, **kwargs) and fsm_can_proceed

    def has_revoke_transition_perm(self, approval, user, **kwargs):
        """Returns True iff model in state allows transition for revoking given approval by given user"""
        import django_fsm

        transition = self.bound_revoke_transition(approval)
        fsm_has_transition_perm = (
            django_fsm.has_transition_perm(transition, user) if transition else False
        )
        return (
            super().has_revoke_transition_perm(approval, user, **kwargs)
            and fsm_has_transition_perm
        )

    def can_do_revoke_transition(self, approval, user, **kwargs):
        """Return True iff all conditions are met for user to proceed with revoke and make transition"""
        import django_fsm

        transition = self.bound_revoke_transition(approval)
        fsm_can_proceed = (
            (
                django_fsm.can_proceed(transition)
                and django_fsm.has_transition_perm(transition, user)
            )
            if transition
            else False
        )
        return (
            super().can_do_revoke_transition(approval, user, **kwargs)
            and fsm_can_proceed
        )


class ApprovalProcessDescriptor:
    """
    Descriptor provides a set of decorators to conveniently load a transition registry,
     and inject an ApprovalsProcess object that manages it in place of the descriptor attribute.
    """

    transition_registry_class = ApprovalTransitionRegistry
    approval_process_class = BasicApprovalProcess

    def __init__(
        self, *approval_sequence, transition_registry=None, approval_process_class=None
    ):
        """
        Optionally: define a linear approval sequence - default is sequenced by order approvals are registered
        Optionally: override the registry and process classes to use if the defaults are not suitable
        """
        self.registry = (
            transition_registry()
            if transition_registry
            else self.transition_registry_class()
        )
        self.approval_process_class = (
            approval_process_class or self.approval_process_class
        )
        # This allows one to explicitly set the approval sequence rather than relying on order of transition functions
        for a in approval_sequence:
            self.registry.add_approval(self._get_approval_id(a))

    @staticmethod
    def _get_approval_id(approval_descriptor_or_type):
        """ "approval_type" may be a string approval id, an actual ApprovalType, or an ApprovalDescriptor"""
        return (
            approval_descriptor_or_type
            if isinstance(approval_descriptor_or_type, str)
            else getattr(
                approval_descriptor_or_type,
                "approval_type",
                approval_descriptor_or_type,
            ).id
        )

    # Approve transition decorators
    # Typical usage (order matters!) (but don't actually do this... see convenience decorators below):
    #   @process.register_approve_transition(my_approval)
    #   @transition(my_state_variable, source=STATE1, target=STATE2, ...)  # optional FSM transition decorator
    #   @process.do_approval
    #   def approve_the_thing(self, approval, ...):
    #       ... other side-effects that should occur when the approval is approved
    #   ...
    #   if thing.process.can_do_approval_transition(approval_insance, user):
    #       save = thing.approve_the_thing(approval_instance)
    #       save()    # saves the approval and the thing in a DB transaction

    def register_approve_transition(self, approval_descriptor_or_type):
        """
        Return a decorator that simply adds the decorated function to the approval_process registry as the
        method to call to approve the given approval_type or ApprovalField descriptor
        """

        def register(transition_method):
            approval_type = self._get_approval_id(approval_descriptor_or_type)
            self.registry.add_approve_transition(approval_type, transition_method)
            return transition_method

        return register

    def do_approval(self, transition_method):
        """delegate"""
        return self.approval_process_class.do_approval(transition_method)

    def register_and_do_approval(self, approval_descriptor_or_type):
        """
        Convenience method to encapsulate register_approve_transition and do_approval
        Return a decorator that wraps fn with do_approval and registers the decorated fn
        See self.do_approval and self.register_approval_method
        Usage:
            @process.register_and_do_approval(my_approval)
            def approve_the_thing(self, approval, ...):
                ... other side-effects that should occur when the approval is approved
            ...
            thing.process.try_approve_transition(approval_instance, user)
        """
        register = self.register_approve_transition(approval_descriptor_or_type)

        def approval_transition_decorator(transition_method):
            """Decorate & register a transition_method with logic to complete approval"""
            return register(self.do_approval(transition_method))

        return approval_transition_decorator

    # Revoke transition decorators
    # Typical usage (order matters!) (but don't actually do this... see convenience decorators below):
    #   @process.register_revoke_transition(my_approval)
    #   @transition(my_state_variable, source=STATE2, target=STATE1, ...)  # optional FSM transition decorator
    #   @process.do_revoke
    #   def revoke_the_thing(self, approval, ...):
    #       ... other side-effects that should occur when the approval is revoked
    #   ...
    #   if thing.process.can_do_revoke_transition(approval_instance, user)
    #       revoke = thing.revoke_the_thing(approval_instance)
    #       revoke(request.user)    # revokes the approval and saves the thing in a DB transaction

    def register_revoke_transition(self, approval_descriptor_or_type):
        """
        Return a decorator that simply adds the decorated function to the approval_process registry as the
        method to call to revoke the given approval_type or ApprovalField descriptor
        """

        def register(transition_method):
            approval_type = self._get_approval_id(approval_descriptor_or_type)
            self.registry.add_revoke_transition(approval_type, transition_method)
            return transition_method

        return register

    def do_revoke(self, transition_method):
        """delegate"""
        return self.approval_process_class.do_revoke(transition_method)

    def register_and_do_revoke(self, approval_descriptor_or_type):
        """
        Convenience method to encapsulate register_revoke_transition and do_revoke
        Return a decorator that wraps fn with do_revoke and registers the decorated fn
        See self.do_revoke and self.register_revoke_method
        Usage:
            @process.register_and_do_revoke(my_approval)
            def revoke_the_thing(self, approval, ...):
                ... other side-effects that should occur when the approval is approved
            ...
            thing.process.try_revoke_transition(approval_instance, user)
        """
        register = self.register_revoke_transition(approval_descriptor_or_type)

        def revoke_transition_decorator(transition_method):
            """Decorate & register a transition_method w/ logic to revoke approval"""
            return register(self.do_revoke(transition_method))

        return revoke_transition_decorator

    def __set_name__(self, owner, name):
        """Grab the field name used by owning class to refer to this descriptor"""
        self.accessor_attr = name

    def __get__(self, instance, owner=None):
        """Return an ApprovalsProcess object to manage the transition registry for the given instance"""
        if not instance:
            return self
        else:
            approval_process = self.approval_process_class(
                process_model=instance, transition_registry=self.registry
            )
            setattr(instance, self.accessor_attr, approval_process)
            return approval_process


ApprovalsProcess = ApprovalProcessDescriptor  # A nicer name


class FsmApprovalProcessDescriptor(ApprovalProcessDescriptor):
    """Uses FSM Approval Actions to manage FSM state transitions"""

    approval_process_class = FsmApprovalProcess

    def approval_transition(
        self,
        approval_descriptor_or_type,
        field,
        source="*",
        target=None,
        on_error=None,
        conditions=None,
        permission=None,
        custom=None,
    ):
        """
        Convenience method to encapsulate registering and FSM transition that also completes an approval
        Return a decorator that wraps fn with both an FSM transition and do_approval, and registers the decorated fn
        All parameters except first positional are simply passed through to django_fsm.transition
        See django.fsm.transition, self.do_approval, and self.register_approval_method
        Usage:
            @process.approval_transition(my_approval, my_state_variable, source=STATE1, target=STATE2, ...)
            def approve_the_thing(self, approval, ...):
                ... other side-effects that should occur when the approval is approved
            ...
            thing.process.try_approve_transition(approval_instance, user)
        """
        import django_fsm

        register = self.register_approve_transition(approval_descriptor_or_type)
        fsm_decorator = django_fsm.transition(
            field,
            source,
            target,
            on_error=on_error,
            conditions=conditions or [],
            permission=permission,
            custom=custom or {},
        )

        def approval_transition_decorator(transition_method):
            """Decorate & register a transition_method with the fsm_decorator + logic to complete approval"""
            return register(self.do_approval(fsm_decorator(transition_method)))

        return approval_transition_decorator

    def revoke_transition(
        self,
        approval_descriptor_or_type,
        field,
        source="*",
        target=None,
        on_error=None,
        conditions=None,
        permission=None,
        custom=None,
    ):
        """
        Convenience method to encapsulate registering and FSM transition that also revokes an approval
        Return a decorator that wraps fn with both an FSM transition and do_revokde, and registers the decorated fn
        All parameters except first positional are simply passed through to django_fsm.transition
        See django.fsm.transition, self.do_revoke, and self.register_revoke_method
        Usage:
            @process.revoke_transition(my_approval, my_state_variable, source=STATE1, target=STATE2, ...)
            def revoke_the_thing(self, approval, ...):
                ... other side-effects that should occur when the approval is revoked
            ...
            thing.process.try_revoke_transition(approval_instance, user)
        """
        import django_fsm

        register = self.register_revoke_transition(approval_descriptor_or_type)
        fsm_decorator = django_fsm.transition(
            field,
            source,
            target,
            on_error=on_error,
            conditions=conditions or [],
            permission=permission,
            custom=custom or {},
        )

        def revoke_transition_decorator(transition_method):
            """Decorate & register a transition_method with the fsm_decorator + logic to complete approval"""
            return register(self.do_revoke(fsm_decorator(transition_method)))

        return revoke_transition_decorator


FsmApprovalsProcess = FsmApprovalProcessDescriptor  # A nicer name


def user_can_revoke_approval(approval_descriptor):
    """
    Return a callable suitable to pass as permission argument to `fsm.transition`

    Specifically intended for use within an `FsmApprovalsProcess` where a `RelatedApprovalDescriptor`,
    usually obtained from an `ApprovalField` is required to check the permission  for a `transition`

    :param approval_descriptor: a descriptor for an Approval that will be used to define the permission
        for an FSM transition defined in the same class.

    Usage:
    ```
        class MyProcess(models.Model):
            ...
            my_approval, my_approval_stamp = ApprovalField(.....)
            ...
            @fsm.transition(..., permission=user_can_revoke_approval(my_approval))
            def approve_it(self, approval):
                ...
    ```
    """

    def has_revoke_perm(instance, user):
        """Determine if the user has permission to revoke instance.approval"""
        approval = approval_descriptor.__get__(instance, type(instance))
        return approval.can_revoke(user)

    return has_revoke_perm


__all__ = [
    "ApprovalsProcess",
    "FsmApprovalsProcess",
    "user_can_revoke_approval",
]
