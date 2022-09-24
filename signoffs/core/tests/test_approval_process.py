"""
App-independent Approval Process INTEGRATION  tests
"""
from django.test import TestCase
from django.db import models
from django_fsm import FSMField, transition

import signoffs.core.signing_order as so
from signoffs.registry import register
from signoffs.core import process as signoffs_process
from signoffs.core.models.fields import ApprovalField, ApprovalSignoffSingle

from .models import ApprovalSignoff, AbstractLeaveApproval
from . import fixtures


@register(id='test.process_approval.leave_application')
class LeaveApplication(AbstractLeaveApproval):
    label = 'Apply for Leave of Absence'

    employee_signoff = ApprovalSignoffSingle(
        ApprovalSignoff.register(id='test.process_approval.leave.employee_signoff')
    )

    def is_complete(self):
        """ Customize logic for determining if Approval signoffs are complete and ready to be approved. """
        return self.employee_signoff.get().is_signed()

    def sign_application(self, user):
        if self.employee_signoff.can_sign(user):
            self.employee_signoff.create(user=user)


class ApprovalSignoffSingleTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.employee = fixtures.get_user(first_name='Employee')

    def test_signoff_single(self):
        approval = LeaveApplication()
        self.assertFalse(approval.employee_signoff.exists())
        self.assertTrue(approval.employee_signoff.can_sign(self.employee))
        approval.sign_application(user=self.employee)
        self.assertTrue(approval.employee_signoff.exists())
        self.assertFalse(approval.employee_signoff.can_sign(self.employee))
        # None oof these do anything
        approval.sign_application(user=self.employee)
        approval.sign_application(user=self.employee)
        self.assertFalse(approval.employee_signoff.can_sign(self.employee))
        self.assertEqual(approval.employee_signoff.count(), 1)


@register(id='test.process_approval.leave_approval')
class LeaveApproval(AbstractLeaveApproval):
    label = 'Approve Leave of Absence'

    hr_signoff_type = ApprovalSignoff.register(id='test.process_approval.leave.hr_signoff')
    mngmt_signoff_type = ApprovalSignoff.register(id='test.process_approval.leave.mngmt_signoff')

    signing_order = so.SigningOrder(
        so.AtLeastN(hr_signoff_type, n=1),
        mngmt_signoff_type
    )

    def sign_approval(self, user):
        next = self.next_signoffs(for_user=user)
        if next and not self.is_approved() and not self.has_signed(user):
            next[-1].sign(user)  # Arbitrarily approve "most nextest" signoff on the approval


#  SIMPLE TEST CASES


class SimpleApprovalProcess(models.Model):
    """ An Approval Process model where transitions and approval sequencing are handled by app logic - no ordering """

    class States(models.TextChoices):
        INITIATED = 'Initiated'
        APPLIED = 'Applied'
        APPROVED = 'Approved'

    state = 'Initiated'

    apply, apply_stamp = ApprovalField(LeaveApplication)
    approve, approve_stamp = ApprovalField(LeaveApproval)

    actions = signoffs_process.ApprovalActions()  # optionally list approvals in order, default is order they are registered below

    @actions.register_approve_transition(apply)
    def application_made(self, approval):
        self.state = self.States.APPLIED
        print("Application made!", self.state, self.apply)

    @actions.register_approve_transition(approve)
    def leave_approved(self, approval):
        self.state = self.States.APPROVED
        print("Leave is approved!", self.state, self.approve)


class SimpleApprovalProcessTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.employee = fixtures.get_user(first_name='Employee')
        cls.hr = fixtures.get_user(first_name='HR')
        cls.mngr = fixtures.get_user(first_name="Manager")

    def test_approve_transitions_sequence(self):
        process = SimpleApprovalProcess()
        self.assertListEqual([process.application_made, process.leave_approved],
                             [process.actions.bound_approve_transition(a) for a in process.actions.get_all_approvals()]
                             )

    def test_get_all_approvals(self):
        process = SimpleApprovalProcess()
        self.assertListEqual(process.actions.get_all_approvals(), [process.apply, process.approve])

    def test_get_approved_approvals(self):
        process = SimpleApprovalProcess()
        self.assertListEqual(process.actions.get_approved_approvals(), [])
        self.assertListEqual(process.actions.get_unapproved_approvals(), [process.apply, process.approve])
        process.apply.approve()
        self.assertListEqual(process.actions.get_approved_approvals(), [process.apply])
        self.assertListEqual(process.actions.get_unapproved_approvals(), [process.approve])
        process.approve.approve()
        self.assertListEqual(process.actions.get_approved_approvals(), [process.apply, process.approve])
        self.assertListEqual(process.actions.get_unapproved_approvals(), [])

    def test_get_available_approvals(self):
        process = SimpleApprovalProcess()
        self.assertListEqual(process.actions.get_available_approvals(), [process.apply])
        process.apply.approve()
        self.assertListEqual(process.actions.get_available_approvals(), [process.approve])
        process.approve.approve()
        self.assertListEqual(process.actions.get_available_approvals(), [])

    def test_approval_actions(self):
        process = SimpleApprovalProcess()
        self.assertEqual(process.state, process.States.INITIATED)
        process.apply.sign_application(user=self.employee)
        self.assertTrue(process.actions.try_approve_transition(process.apply, self.employee))
        self.assertEqual(process.state, process.States.APPLIED)
        process.approve.sign_approval(user=self.hr)
        self.assertFalse(process.actions.try_approve_transition(process.approve, self.hr))
        self.assertEqual(process.state, process.States.APPLIED)
        process.approve.sign_approval(user=self.mngr)
        self.assertTrue(process.actions.try_approve_transition(process.approve, self.mngr))
        self.assertEqual(process.state, process.States.APPROVED)


#  ORDERED TEST CASES


class OrderedApprovalProcess(models.Model):
    """ An Approval Process model where transitions and approval sequencing are defined with linear ordering """

    class States(models.TextChoices):
        INITIATED = 'Initiated'
        APPLIED = 'Applied'
        APPROVED = 'Approved'

    state = 'Initiated'

    zapply, zapply_stamp = ApprovalField(LeaveApplication)
    approve, approve_stamp = ApprovalField(LeaveApproval)

    actions = signoffs_process.ApprovalActions(zapply, approve)  # list approvals in order so code order doesn't matter

    @actions.register_approve_transition(approve)
    def leave_approved(self, approval):
        self.state = self.States.APPROVED
        print("Leave is approved!", self.state, self.approve)

    @actions.register_approve_transition(zapply)
    def application_made(self, approval):
        self.state = self.States.APPLIED
        print("Application made!", self.state, self.zapply)


class OrderedApprovalProcessTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.employee = fixtures.get_user(first_name='Employee')
        cls.hr = fixtures.get_user(first_name='HR')
        cls.mngr = fixtures.get_user(first_name="Manager")

    def test_approval_sequence(self):
        process = OrderedApprovalProcess()
        self.assertListEqual([process.application_made, process.leave_approved],
                             [process.actions.bound_approve_transition(a) for a in process.actions.get_all_approvals()]
                             )

    def test_get_all_approvals(self):
        process = OrderedApprovalProcess()
        self.assertListEqual(process.actions.get_all_approvals(), [process.zapply, process.approve])

    def test_approval_ordering(self):
        process = OrderedApprovalProcess()
        self.assertListEqual(process.actions.get_available_approvals(), [process.zapply, ])
        self.assertEqual(process.actions.get_next_available_approval(), process.zapply)
        self.assertTrue(process.actions.can_proceed(process.zapply))
        self.assertFalse(process.actions.can_proceed(process.approve))
        process.zapply.approve()

        self.assertListEqual(process.actions.get_available_approvals(), [process.approve, ])
        self.assertEqual(process.actions.get_next_available_approval(), process.approve)
        self.assertFalse(process.actions.can_proceed(process.zapply))
        self.assertTrue(process.actions.can_proceed(process.approve))
        process.approve.approve()

        self.assertListEqual(process.actions.get_available_approvals(), [])
        self.assertEqual(process.actions.get_next_available_approval(), None)
        self.assertFalse(process.actions.can_proceed(process.zapply))
        self.assertFalse(process.actions.can_proceed(process.approve))

    def test_approval_actions(self):
        process = OrderedApprovalProcess()
        self.assertEqual(process.state, process.States.INITIATED)
        process.zapply.sign_application(user=self.employee)
        self.assertTrue(process.actions.try_approve_transition(process.zapply, self.employee))
        self.assertEqual(process.state, process.States.APPLIED)
        process.approve.sign_approval(user=self.hr)
        self.assertFalse(process.actions.try_approve_transition(process.approve, self.hr))
        self.assertEqual(process.state, process.States.APPLIED)
        process.approve.sign_approval(user=self.mngr)
        self.assertTrue(process.actions.try_approve_transition(process.approve, self.mngr))
        self.assertEqual(process.state, process.States.APPROVED)


# FSM Test Cases  TODO: add revoke transitions, transition conditions & permissions

class FsmLeaveApprovalProcess(models.Model):
    """ A process Model where state transitions and approval sequencing are ordered using fsm """

    class States(models.TextChoices):
        INITIATED = 'Initiated'
        APPLIED = 'Applied'
        APPROVED = 'Approved'

    state = FSMField(choices=States.choices, default=States.INITIATED)

    apply, apply_stamp = ApprovalField(LeaveApplication)
    approve, approve_stamp = ApprovalField(LeaveApproval)

    actions = signoffs_process.FsmApprovalActions()  # adds FSM transition logic to approval actions

    @actions.register_approve_transition(apply)
    @transition(field=state, source=States.INITIATED, target=States.APPLIED)
    def application_made(self, approval):
        print("Application made!", self.state, self.apply)

    @actions.register_approve_transition(approve)
    @transition(field=state, source=States.APPLIED, target=States.APPROVED)
    def leave_approved(self, approval):
        print("Leave is approved!", self.state, self.approve)


class FsmApprovalProcessTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.employee = fixtures.get_user(first_name='Employee')
        cls.hr = fixtures.get_user(first_name='HR')
        cls.mngr = fixtures.get_user(first_name="Manager")

    def test_fsm_approval_sequence(self):
        process = FsmLeaveApprovalProcess()
        self.assertListEqual([process.application_made, process.leave_approved],
                             [process.actions.bound_approve_transition(a) for a in process.actions.get_all_approvals()]
                             )

    def test_fsm_get_available_approvals(self):
        process = FsmLeaveApprovalProcess()
        self.assertListEqual(process.actions.get_available_approvals(), [process.apply, ])
        process.apply.sign_application(user=self.employee)
        process.actions.try_approve_transition(process.apply, user=self.employee)

        self.assertListEqual(process.actions.get_available_approvals(), [process.approve, ])
        process.approve.sign_approval(user=self.hr)
        process.approve.sign_approval(user=self.mngr)
        process.actions.try_approve_transition(process.approve, user=self.mngr)
        self.assertListEqual(process.actions.get_available_approvals(), [])

    def test_fsm_approval_sequencing(self):
        process = FsmLeaveApprovalProcess()
        self.assertEqual(process.state, process.States.INITIATED)
        self.assertTrue(process.actions.can_proceed(process.apply))
        self.assertFalse(process.actions.can_proceed(process.approve))

        process.apply.sign_application(user=self.employee)
        self.assertTrue(process.actions.try_approve_transition(process.apply, user=self.employee))
        self.assertEqual(process.state, process.States.APPLIED)
        self.assertFalse(process.actions.can_proceed(process.apply))
        self.assertTrue(process.actions.can_proceed(process.approve))

        process.approve.sign_approval(user=self.hr)
        self.assertFalse(process.actions.try_approve_transition(process.approve, user=self.hr))
        self.assertEqual(process.state, process.States.APPLIED)
        self.assertFalse(process.actions.can_proceed(process.apply))
        self.assertTrue(process.actions.can_proceed(process.approve))

        process.approve.sign_approval(user=self.hr)
        self.assertFalse(process.actions.try_approve_transition(process.approve, user=self.hr))
        self.assertEqual(process.state, process.States.APPLIED)
        self.assertFalse(process.actions.can_proceed(process.apply))
        self.assertTrue(process.actions.can_proceed(process.approve))

        process.approve.sign_approval(user=self.mngr)
        self.assertTrue(process.actions.try_approve_transition(process.approve, user=self.mngr))
        self.assertEqual(process.state, process.States.APPROVED)
        self.assertFalse(process.actions.can_proceed(process.apply))
        self.assertFalse(process.actions.can_proceed(process.approve))
