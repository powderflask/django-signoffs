"""
App-independent tests for contrib models
"""
from django.core.exceptions import PermissionDenied
from django.test import TestCase

from signoffs import approvals, models
from signoffs import signing_order as so
from signoffs import signoffs
from signoffs.core.tests import fixtures
from signoffs.registry import register

simple = signoffs.SimpleSignoff.register(id="test.contrib.simple")
revokable = signoffs.RevokableSignoff.register(id="test.contrib.revokable")
irrevokable = signoffs.IrrevokableSignoff.register(id="test.contrib.irrevokable")

approval_signoff = approvals.ApprovalSignoff.register(
    id="test.contrib.approval_signoff"
)


@register(id="test.contrib.simple-approval")
class SimpleApproval(approvals.SimpleApproval):
    signing_order = so.SigningOrder(
        so.OneOrMore(approval_signoff),
    )


@register(id="test.contrib.irrevokable-approval")
class IrrevokableApproval(approvals.IrrevokableApproval):
    signing_order = so.SigningOrder(
        so.OneOrMore(approval_signoff),
    )


class ContribSignoffTypeTests(TestCase):
    def setUp(self):
        super().setUp()
        self.user = fixtures.get_user(
            username="anyone"
        )  # A user with no specific permissions

    def test_simple_signoff(self):
        signoff = simple()
        self.assertEqual(signoff.signet_model, models.Signet)
        self.assertIsNone(signoff.revoke_model)
        self.assertTrue(signoff.is_permitted_signer(self.user))
        self.assertTrue(signoff.is_permitted_revoker(self.user))
        signet = signoff.signet
        self.assertEqual(signet.signoff_type, type(signoff))
        self.assertEqual(signet.signoff, signoff)
        # save and revoke
        signoff = signoff.sign(user=self.user)
        self.assertTrue(signoff.can_revoke(self.user))

    def test_revokable_signoff(self):
        signoff = revokable()
        self.assertEqual(signoff.signet_model, models.Signet)
        self.assertEqual(signoff.revoke_model, models.RevokedSignet)
        self.assertTrue(signoff.is_permitted_signer(self.user))
        self.assertTrue(signoff.is_permitted_revoker(self.user))
        signet = signoff.signet
        self.assertEqual(signet.signoff_type, type(signoff))
        self.assertEqual(signet.signoff, signoff)
        # save and revoke
        signoff = signoff.sign(user=self.user)
        self.assertTrue(signoff.can_revoke(self.user))

    def test_irrevokable_signoff(self):
        signoff = irrevokable()
        self.assertEqual(signoff.signet_model, models.Signet)
        self.assertIsNone(signoff.revoke_model)
        self.assertTrue(signoff.is_permitted_signer(self.user))
        self.assertFalse(signoff.is_permitted_revoker(self.user))
        signet = signoff.signet
        self.assertEqual(signet.signoff_type, type(signoff))
        self.assertEqual(signet.signoff, signoff)
        # save and revoke
        signoff = signoff.sign(user=self.user)
        self.assertFalse(signoff.can_revoke(self.user))


class ContribApprovalTypeTests(TestCase):
    def setUp(self):
        super().setUp()
        self.user = fixtures.get_user(
            username="anyone"
        )  # A user with no specific permissions

    def sign_all(self, approval):
        """Complete signatures on approval with self.user, return list of signoffs made"""
        s = []
        next = True
        while not approval.is_complete() and next:
            next = approval.next_signoffs(for_user=self.user)
            s += [so.sign(user=self.user) for so in next]
        return s

    def test_approve_simple_approval(self):
        approval = SimpleApproval.create()
        self.sign_all(approval)
        self.assertTrue(approval.ready_to_approve())
        self.assertFalse(approval.is_approved())
        approval.approve()
        self.assertTrue(approval.is_approved())

    def test_revoke_simple_approval(self):
        approval = SimpleApproval.create()
        self.sign_all(approval)
        approval.approve()
        self.assertTrue(approval.is_approved())
        approval.revoke(self.user)
        self.assertFalse(approval.is_approved())
        self.assertEqual(approval.signoffs.count(), 0)
        self.assertEqual(approval.signatories.count(), 0)

    def test_revoke_irrevokable_approval(self):
        approval = IrrevokableApproval.create()
        self.sign_all(approval)
        approval.approve()

        self.assertFalse(approval.can_revoke(self.user))
        with self.assertRaises(PermissionDenied):
            approval.revoke_if_permitted(self.user)
        self.assertTrue(approval.is_approved())
