"""
App-independent tests for process models - no app logic
"""
from django.test import TestCase
from django.db import models
from django_fsm import FSMField, transition

import signoffs.core.signing_order as so
from signoffs.registry import register
from signoffs.core.models.approval_process import AbstractApprovalProcess, AbstractFsmApprovalProcess
from signoffs.core.models.fields import ApprovalField, ApprovalSignoffSingle

from .models import ApprovalSignoff, AbstractLeaveApproval
from . import fixtures


@register(id='test.process.leave_application')
class LeaveApplication(AbstractLeaveApproval):
    label = 'Apply for Leave of Absence'

    employee_signoff = ApprovalSignoffSingle(
        ApprovalSignoff.register(id='test.process.leave.employee_signoff')
    )

    def sign_application(self, user):
        if self.employee_signoff.can_sign(user):
            self.employee_signoff.create(user=user)
            self.approve()


class ApprovalSignoffSingleTests(TestCase):
    @classmethod
    def setUpTestData(cls):
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


@register(id='test.process.leave_approval')
class LeaveApproval(AbstractLeaveApproval):
    label = 'Approve Leave of Absence'

    hr_signoff_type = ApprovalSignoff.register(id='test.process.leave.hr_signoff')
    mngmt_signoff_type = ApprovalSignoff.register(id='test.process.leave.mngmt_signoff')

    signing_order = so.SigningOrder(
        so.AtLeastN(hr_signoff_type, n=1),
        mngmt_signoff_type
    )

    def sign_approval(self, user):
        next = self.next_signoffs(for_user=user)
        if next and not self.is_approved() and not self.has_signed(user):
            next[-1].sign(user)  # Arbitrarily approve "most nextest" signoff on the approval
            self.approve_if_ready()


#  SIMPLE TEST CASES


class SimpleApprovalProcess(AbstractApprovalProcess):
    """ An Approval Process model where transitions and approval sequencing are handled by app logic - no ordering """

    class States(models.TextChoices):
        INITIATED = 'Initiated'
        APPLIED = 'Applied'
        APPROVED = 'Approved'

    state = 'Initiated'

    apply, apply_stamp = ApprovalField(LeaveApplication)
    approve, approve_stamp = ApprovalField(LeaveApproval)

    @apply.callback.on_approval
    def application_made(self, approval):
        self.state = self.States.APPLIED
        print("Application made!", self.state, approval)

    @approve.callback.on_approval
    def leave_approved(self, approval):
        self.state = self.States.APPROVED
        print("Leave is approved!", self.state, approval)


class SimpleApprovalProcessTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.employee = fixtures.get_user(first_name='Employee')
        cls.hr = fixtures.get_user(first_name='HR')
        cls.mngr = fixtures.get_user(first_name="Manager")

    def test_approval_sequence(self):
        process = SimpleApprovalProcess()
        seq = process.approval_sequence
        self.assertListEqual([k for k in seq], ['apply', 'approve'])
        self.assertListEqual([('apply', process.application_made), ('approve', process.leave_approved)],
                             [(k, v) for k, v in seq.on_approval_transitions().items()]
                             )

    def test_get_all_approvals(self):
        process = SimpleApprovalProcess()
        self.assertListEqual(process.get_all_approvals(), [process.apply, process.approve])

    def test_get_approved_approvals(self):
        process = SimpleApprovalProcess()
        self.assertListEqual(process.get_approved_approvals(), [])
        self.assertListEqual(process.get_unapproved_approvals(), [process.apply, process.approve])
        process.apply.approve()
        del process.approval_sequence
        self.assertListEqual(process.get_approved_approvals(), [process.apply])
        self.assertListEqual(process.get_unapproved_approvals(), [process.approve])
        process.approve.approve()
        del process.approval_sequence
        self.assertListEqual(process.get_approved_approvals(), [process.apply, process.approve])
        self.assertListEqual(process.get_unapproved_approvals(), [])

    def test_get_available_approvals(self):
        process = SimpleApprovalProcess()
        self.assertListEqual(process.get_available_approvals(), [process.apply, process.approve])
        process.apply.approve()
        del process.approval_sequence
        self.assertListEqual(process.get_available_approvals(), [process.approve])
        process.approve.approve()
        del process.approval_sequence
        self.assertListEqual(process.get_available_approvals(), [])

    def test_approval_callbacks(self):
        process = SimpleApprovalProcess()
        self.assertEqual(process.state, process.States.INITIATED)
        process.apply.sign_application(user=self.employee)
        self.assertEqual(process.state, process.States.APPLIED)
        process.approve.sign_approval(user=self.hr)
        self.assertEqual(process.state, process.States.APPLIED)
        process.approve.sign_approval(user=self.mngr)
        self.assertEqual(process.state, process.States.APPROVED)


#  ORDERED TEST CASES


class OrderedApprovalProcess(AbstractApprovalProcess):
    """ An Approval Process model where transitions and approval sequencing are defined with linear ordering """

    class States(models.TextChoices):
        INITIATED = 'Initiated'
        APPLIED = 'Applied'
        APPROVED = 'Approved'

    state = 'Initiated'

    zapply, zapply_stamp = ApprovalField(LeaveApplication)
    approve, approve_stamp = ApprovalField(LeaveApproval)

    approval_ordering = (zapply, approve)

    @zapply.callback.on_approval
    def application_made(self, approval):
        self.state = self.States.APPLIED
        print("Application made!", self.state, approval)

    @approve.callback.on_approval
    def leave_approved(self, approval):
        self.state = self.States.APPROVED
        print("Leave is approved!", self.state, approval)


class OrderedApprovalProcessTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.employee = fixtures.get_user(first_name='Employee')
        cls.hr = fixtures.get_user(first_name='HR')
        cls.mngr = fixtures.get_user(first_name="Manager")

    def test_approval_sequence(self):
        process = OrderedApprovalProcess()
        seq = process.approval_sequence
        self.assertListEqual([k for k in seq], ['zapply', 'approve'])
        self.assertListEqual([('zapply', process.application_made), ('approve', process.leave_approved)],
                             [(k, v) for k, v in seq.on_approval_transitions().items()]
                             )

    def test_approval_ordering(self):
        process = OrderedApprovalProcess()
        self.assertListEqual(process.get_available_approvals(), [process.zapply, ])
        self.assertEqual(process.get_next_available_approval(), process.zapply)
        self.assertTrue(process.can_proceed(process.zapply))
        self.assertFalse(process.can_proceed(process.approve))
        process.zapply.approve()

        del process.approval_sequence
        self.assertListEqual(process.get_available_approvals(), [process.approve, ])
        self.assertEqual(process.get_next_available_approval(), process.approve)
        self.assertFalse(process.can_proceed(process.zapply))
        self.assertTrue(process.can_proceed(process.approve))
        process.approve.approve()

        del process.approval_sequence
        self.assertListEqual(process.get_available_approvals(), [])
        self.assertEqual(process.get_next_available_approval(), None)
        self.assertFalse(process.can_proceed(process.zapply))
        self.assertFalse(process.can_proceed(process.approve))


# FSM Test Cases

class FsmApprovalProcess(AbstractFsmApprovalProcess):
    """ A process Model where state transitions and approval sequencing are ordered using fsm """

    class States(models.TextChoices):
        INITIATED = 'Initiated'
        APPLIED = 'Applied'
        APPROVED = 'Approved'

    state = FSMField(choices=States.choices, default=States.INITIATED)

    apply, apply_stamp = ApprovalField(LeaveApplication)
    approve, approve_stamp = ApprovalField(LeaveApproval)

    @apply.callback.on_approval
    @transition(field=state, source=States.INITIATED, target=States.APPLIED)
    def application_made(self, approval):
        print("Application made!", self.state, approval)

    @approve.callback.on_approval
    @transition(field=state, source=States.APPLIED, target=States.APPROVED)
    def leave_approved(self, approval):
        print("Leave is approved!", self.state, approval)


class FsmApprovalProcessTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.employee = fixtures.get_user(first_name='Employee')
        cls.hr = fixtures.get_user(first_name='HR')
        cls.mngr = fixtures.get_user(first_name="Manager")

    def test_fsm_approval_sequence(self):
        process = FsmApprovalProcess()
        seq = process.approval_sequence
        self.assertListEqual([k for k in seq], ['apply', 'approve'])
        self.assertListEqual([('apply', process.application_made),
                              ('approve', process.leave_approved)],
                             [(k, v) for k, v in seq.on_approval_transitions().items()]
                             )

    def test_fsm_get_available_approvals(self):
        process = FsmApprovalProcess()
        self.assertListEqual(process.get_available_approvals(), [process.apply, ])
        process.apply.approve()
        del process.approval_sequence
        self.assertListEqual(process.get_available_approvals(), [process.approve, ])
        process.approve.approve()
        del process.approval_sequence

    def test_fsm_approval_sequencing(self):
        process = FsmApprovalProcess()
        self.assertEqual(process.state, process.States.INITIATED)
        self.assertTrue(process.can_proceed('apply'))
        self.assertFalse(process.can_proceed('approve'))

        process.apply.sign_application(user=self.employee)
        self.assertEqual(process.state, process.States.APPLIED)
        self.assertFalse(process.can_proceed('apply'))
        self.assertTrue(process.can_proceed('approve'))

        process.approve.sign_approval(user=self.hr)
        self.assertEqual(process.state, process.States.APPLIED)
        self.assertFalse(process.can_proceed('apply'))
        self.assertTrue(process.can_proceed('approve'))

        process.approve.sign_approval(user=self.hr)
        self.assertEqual(process.state, process.States.APPLIED)
        self.assertFalse(process.can_proceed('apply'))
        self.assertTrue(process.can_proceed('approve'))

        process.approve.sign_approval(user=self.mngr)
        self.assertEqual(process.state, process.States.APPROVED)
        self.assertFalse(process.can_proceed('apply'))
        self.assertFalse(process.can_proceed('approve'))
