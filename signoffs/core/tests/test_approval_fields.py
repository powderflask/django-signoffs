"""
App-independent tests for Approval model descriptors - no app logic
"""
from django.contrib.auth.models import AnonymousUser
from django.test import TestCase

from . import fixtures
from .models import LeaveApproval, LeaveRequest, Stamp


class SimpleApprovalRelationTests(TestCase):
    def test_approvalfield_relations(self):
        lr = LeaveRequest()
        self.assertEqual(LeaveRequest.approval.id, LeaveApproval.id)
        self.assertEqual(type(lr.approval.stamp), LeaveApproval.get_stampModel())
        # ApprovalField descriptor creates stamp on first access to ensure subsequent signoff relations can be saved.
        self.assertIsNotNone(lr.approval_stamp)

    def test_approvalfield(self):
        lr = LeaveRequest()
        # OneToOne forward relation
        self.assertTrue(isinstance(lr.approval, LeaveApproval))
        self.assertEqual(lr.approval.stamp_model, Stamp)
        self.assertFalse(lr.approval.is_approved())


class ApprovalRelationTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.u1 = fixtures.get_user()
        cls.u2 = fixtures.get_user()
        cls.u3 = fixtures.get_user()
        lr = LeaveRequest.objects.create()
        lr.employee_signoff.sign_if_permitted(cls.u1)
        cls.hr_signoffs = (
            lr.hr_signoffs.create(user=cls.u1),
            lr.hr_signoffs.create(user=cls.u2),
        )
        lr.mngmt_signoffs.create(user=cls.u3),
        lr.approval.get_next_signoff(cls.u1).sign_if_permitted(
            cls.u1
        )  # touching approval field is enough to create the approval relation
        lr.approval.get_next_signoff(cls.u2).sign_if_permitted(cls.u2)
        lr.save()
        cls.lr = lr

    def test_approvalfield(self):
        with self.assertNumQueries(1):
            lr = LeaveRequest.objects.select_related("approval_stamp").get(
                pk=self.lr.pk
            )
            # OneToOne forward relation
            self.assertFalse(lr.approval.is_approved())

    def test_approval_signatories(self):
        with self.assertNumQueries(3):
            lr = (
                LeaveRequest.objects.select_related("approval_stamp")
                .prefetch_related("approval_stamp__signatories__user")
                .get(pk=self.lr.pk)
            )
            self.assertTrue(lr.approval.can_sign(self.u3))
            self.assertFalse(lr.approval.can_sign(AnonymousUser()))
            self.assertTrue(lr.approval.has_signed(self.u1))
            self.assertFalse(lr.approval.has_signed(self.u3))
            self.assertTrue(lr.approval.can_sign(self.u3))

    def test_approval_revoke(self):
        u = fixtures.get_user()
        lr = LeaveRequest.objects.select_related("approval_stamp").get(pk=self.lr.pk)
        lr.approval.approve()
        lr = LeaveRequest.objects.select_related("approval_stamp").get(pk=self.lr.pk)
        self.assertTrue(lr.approval.is_approved())
        lr.approval.revoke_if_permitted(u)
        lr = (
            LeaveRequest.objects.select_related("approval_stamp")
            .prefetch_related("approval_stamp__signatories")
            .get(pk=self.lr.pk)
        )
        self.assertFalse(lr.approval.is_approved())
        self.assertFalse(lr.approval.has_signatories())
