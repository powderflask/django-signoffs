"""
App-independent Approval Process INTEGRATION  tests
"""
from django.db import models
from django.test import TestCase
from django_fsm import FSMField, transition

import signoffs.core.signing_order as so
from signoffs.core import process as signoffs_process
from signoffs.core.models.fields import ApprovalField, ApprovalSignoffSingle
from signoffs.registry import register

from . import fixtures
from .models import AbstractLeaveApproval, ApprovalSignoff


@register(id="test.process_approval.leave_application")
class LeaveApplication(AbstractLeaveApproval):
    label = "Apply for Leave of Absence"

    employee_signoff = ApprovalSignoffSingle(
        ApprovalSignoff.register(id="test.process_approval.leave.employee_signoff")
    )

    def is_complete(self):
        """Customize logic for determining if Approval signoffs are complete and ready to be approved."""
        return self.employee_signoff.get().is_signed()

    def sign_application(self, user):
        if self.employee_signoff.can_sign(user):
            self.employee_signoff.create(user=user)


class ApprovalSignoffSingleTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.employee = fixtures.get_user(first_name="Employee")

    def test_signoff_single(self):
        approval = LeaveApplication.create()
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


@register(id="test.process_approval.leave_approval")
class LeaveApproval(AbstractLeaveApproval):
    label = "Approve Leave of Absence"

    hr_signoff_type = ApprovalSignoff.register(
        id="test.process_approval.leave.hr_signoff"
    )
    mngmt_signoff_type = ApprovalSignoff.register(
        id="test.process_approval.leave.mngmt_signoff"
    )

    signing_order = so.SigningOrder(
        so.AtLeastN(hr_signoff_type, n=1), mngmt_signoff_type
    )

    def sign_approval(self, user):
        next = self.next_signoffs(for_user=user)
        if next and not self.is_approved() and not self.has_signed(user):
            next[-1].sign_if_permitted(
                user
            )  # Arbitrarily approve "most nextest" signoff on the approval


#  SIMPLE TEST CASES


class SimpleApprovalProcessModel(models.Model):
    """An Approval Process model where transitions and approval sequencing are handled by app logic - no ordering"""

    class States(models.TextChoices):
        INITIATED = "Initiated"
        APPLIED = "Applied"
        APPROVED = "Approved"

    state = "Initiated"

    apply, apply_stamp = ApprovalField(LeaveApplication)
    approve, approve_stamp = ApprovalField(LeaveApproval)

    process = (
        signoffs_process.ApprovalsProcess()
    )  # optionally list approvals in order, default is order they are registered below

    @process.register_and_do_approval(apply)
    def application_made(self, approval):
        self.state = self.States.APPLIED
        print("Application made!", self.state, self.apply)

    @process.register_and_do_approval(approve)
    def leave_approved(self, approval):
        self.state = self.States.APPROVED
        print("Leave is approved!", self.state, self.approve)


class SimpleApprovalProcessModelTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.employee = fixtures.get_user(first_name="Employee")
        cls.hr = fixtures.get_user(first_name="HR")
        cls.mngr = fixtures.get_user(first_name="Manager")

    def test_approve_transitions_sequence(self):
        model = SimpleApprovalProcessModel()
        self.assertListEqual(
            [model.application_made, model.leave_approved],
            [
                model.process.bound_approve_transition(a)
                for a in model.process.get_all_approvals()
            ],
        )

    def test_get_all_approvals(self):
        model = SimpleApprovalProcessModel()
        self.assertListEqual(
            model.process.get_all_approvals(), [model.apply, model.approve]
        )

    def test_get_approved_approvals(self):
        model = SimpleApprovalProcessModel()
        self.assertListEqual(model.process.get_approved_approvals(), [])
        self.assertListEqual(
            model.process.get_unapproved_approvals(), [model.apply, model.approve]
        )
        model.apply.approve()
        self.assertListEqual(model.process.get_approved_approvals(), [model.apply])
        self.assertListEqual(model.process.get_unapproved_approvals(), [model.approve])
        model.approve.approve()
        self.assertListEqual(
            model.process.get_approved_approvals(), [model.apply, model.approve]
        )
        self.assertListEqual(model.process.get_unapproved_approvals(), [])

    def test_get_available_approvals(self):
        model = SimpleApprovalProcessModel()
        self.assertListEqual(model.process.get_available_approvals(), [model.apply])
        model.apply.approve()
        self.assertListEqual(model.process.get_available_approvals(), [model.approve])
        model.approve.approve()
        self.assertListEqual(model.process.get_available_approvals(), [])

    def test_approval_actions(self):
        model = SimpleApprovalProcessModel()
        self.assertEqual(model.state, model.States.INITIATED)
        model.apply.sign_application(user=self.employee)
        self.assertTrue(
            model.process.try_approve_transition(model.apply, self.employee)
        )
        self.assertEqual(model.state, model.States.APPLIED)
        model.approve.sign_approval(user=self.hr)
        self.assertFalse(model.process.try_approve_transition(model.approve, self.hr))
        self.assertEqual(model.state, model.States.APPLIED)
        model.approve.sign_approval(user=self.mngr)
        self.assertTrue(model.process.try_approve_transition(model.approve, self.mngr))
        self.assertEqual(model.state, model.States.APPROVED)


#  ORDERED TEST CASES


class OrderedApprovalProcessModel(models.Model):
    """An Approval Process model where transitions and approval sequencing are defined with linear ordering"""

    class States(models.TextChoices):
        INITIATED = "Initiated"
        APPLIED = "Applied"
        APPROVED = "Approved"

    state = "Initiated"

    zapply, zapply_stamp = ApprovalField(LeaveApplication)
    approve, approve_stamp = ApprovalField(LeaveApproval)

    process = signoffs_process.ApprovalsProcess(
        zapply, approve
    )  # list approvals in order so code order doesn't matter

    @process.register_and_do_approval(approve)
    def leave_approved(self, approval):
        self.state = self.States.APPROVED
        print("Leave is approved!", self.state, self.approve)

    @process.register_and_do_approval(zapply)
    def application_made(self, approval):
        self.state = self.States.APPLIED
        print("Application made!", self.state, self.zapply)


class OrderedApprovalProcessModelTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.employee = fixtures.get_user(first_name="Employee")
        cls.hr = fixtures.get_user(first_name="HR")
        cls.mngr = fixtures.get_user(first_name="Manager")

    def test_approval_sequence(self):
        model = OrderedApprovalProcessModel()
        self.assertListEqual(
            [model.application_made, model.leave_approved],
            [
                model.process.bound_approve_transition(a)
                for a in model.process.get_all_approvals()
            ],
        )

    def test_get_all_approvals(self):
        model = OrderedApprovalProcessModel()
        self.assertListEqual(
            model.process.get_all_approvals(), [model.zapply, model.approve]
        )

    def test_approval_ordering(self):
        model = OrderedApprovalProcessModel()
        self.assertListEqual(
            model.process.get_available_approvals(),
            [
                model.zapply,
            ],
        )
        self.assertEqual(model.process.get_next_available_approval(), model.zapply)
        self.assertTrue(model.process.can_proceed(model.zapply))
        self.assertFalse(model.process.can_proceed(model.approve))
        model.zapply.approve()

        self.assertListEqual(
            model.process.get_available_approvals(),
            [
                model.approve,
            ],
        )
        self.assertEqual(model.process.get_next_available_approval(), model.approve)
        self.assertFalse(model.process.can_proceed(model.zapply))
        self.assertTrue(model.process.can_proceed(model.approve))
        model.approve.approve()

        self.assertListEqual(model.process.get_available_approvals(), [])
        self.assertEqual(model.process.get_next_available_approval(), None)
        self.assertFalse(model.process.can_proceed(model.zapply))
        self.assertFalse(model.process.can_proceed(model.approve))

    def test_approval_actions(self):
        model = OrderedApprovalProcessModel()
        self.assertEqual(model.state, model.States.INITIATED)
        model.zapply.sign_application(user=self.employee)
        self.assertTrue(
            model.process.try_approve_transition(model.zapply, self.employee)
        )
        self.assertEqual(model.state, model.States.APPLIED)
        model.approve.sign_approval(user=self.hr)
        self.assertFalse(model.process.try_approve_transition(model.approve, self.hr))
        self.assertEqual(model.state, model.States.APPLIED)
        model.approve.sign_approval(user=self.mngr)
        self.assertTrue(model.process.try_approve_transition(model.approve, self.mngr))
        self.assertEqual(model.state, model.States.APPROVED)


# FSM Test Cases  TODO: add revoke transitions, transition conditions & permissions


class FsmLeaveApprovalProcessModel(models.Model):
    """An Approval Process Model where state transitions and approval sequencing are ordered using fsm"""

    class States(models.TextChoices):
        INITIATED = "Initiated"
        APPLIED = "Applied"
        APPROVED = "Approved"

    state = FSMField(choices=States.choices, default=States.INITIATED)

    apply, apply_stamp = ApprovalField(LeaveApplication)
    approve, approve_stamp = ApprovalField(LeaveApproval)

    process = (
        signoffs_process.FsmApprovalsProcess()
    )  # adds FSM transition logic to approvals process

    # Decorate transition the long (but flexible) way...  (* note: decorateor order really matters here!)

    @process.register_approve_transition(apply)
    @transition(field=state, source=States.INITIATED, target=States.APPLIED)
    @process.do_approval
    def application_made(self, approval):
        print("Application made!", self.state, self.apply)

    # or the convenient way

    @process.approval_transition(
        approve, field=state, source=States.APPLIED, target=States.APPROVED
    )
    def leave_approved(self, approval):
        print("Leave is approved!", self.state, self.approve)


class FsmApprovalProcessModelTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.employee = fixtures.get_user(first_name="Employee")
        cls.hr = fixtures.get_user(first_name="HR")
        cls.mngr = fixtures.get_user(first_name="Manager")

    def test_fsm_approval_sequence(self):
        model = FsmLeaveApprovalProcessModel()
        self.assertListEqual(
            [model.application_made, model.leave_approved],
            [
                model.process.bound_approve_transition(a)
                for a in model.process.get_all_approvals()
            ],
        )

    def test_fsm_get_available_approvals(self):
        model = FsmLeaveApprovalProcessModel()
        self.assertListEqual(
            model.process.get_available_approvals(),
            [
                model.apply,
            ],
        )
        model.apply.sign_application(user=self.employee)
        model.process.try_approve_transition(model.apply, user=self.employee)

        self.assertListEqual(
            model.process.get_available_approvals(),
            [
                model.approve,
            ],
        )
        model.approve.sign_approval(user=self.hr)
        model.approve.sign_approval(user=self.mngr)
        model.process.try_approve_transition(model.approve, user=self.mngr)
        self.assertListEqual(model.process.get_available_approvals(), [])

    def test_fsm_approval_sequencing(self):
        model = FsmLeaveApprovalProcessModel()
        self.assertEqual(model.state, model.States.INITIATED)
        self.assertTrue(model.process.can_proceed(model.apply))
        self.assertFalse(model.process.can_proceed(model.approve))

        model.apply.sign_application(user=self.employee)
        self.assertTrue(
            model.process.try_approve_transition(model.apply, user=self.employee)
        )
        self.assertEqual(model.state, model.States.APPLIED)
        self.assertFalse(model.process.can_proceed(model.apply))
        self.assertTrue(model.process.can_proceed(model.approve))

        model.approve.sign_approval(user=self.hr)
        self.assertFalse(
            model.process.try_approve_transition(model.approve, user=self.hr)
        )
        self.assertEqual(model.state, model.States.APPLIED)
        self.assertFalse(model.process.can_proceed(model.apply))
        self.assertTrue(model.process.can_proceed(model.approve))

        model.approve.sign_approval(user=self.hr)
        self.assertFalse(
            model.process.try_approve_transition(model.approve, user=self.hr)
        )
        self.assertEqual(model.state, model.States.APPLIED)
        self.assertFalse(model.process.can_proceed(model.apply))
        self.assertTrue(model.process.can_proceed(model.approve))

        model.approve.sign_approval(user=self.mngr)
        self.assertTrue(
            model.process.try_approve_transition(model.approve, user=self.mngr)
        )
        self.assertEqual(model.state, model.States.APPROVED)
        self.assertFalse(model.process.can_proceed(model.apply))
        self.assertFalse(model.process.can_proceed(model.approve))
