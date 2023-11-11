"""
App-independent tests for view.actions - no app logic
"""
from unittest.mock import Mock

import django_fsm as fsm
from django.db.models import Model, TextChoices
from django.test import TestCase

import signoffs.core.signing_order as so
from signoffs.core import process as signoffs_process
from signoffs.core.approvals import BaseApproval
from signoffs.registry import register
from signoffs.signoffs import SignoffLogic
from signoffs.views import actions

from ..models.fields import ApprovalField
from . import fixtures, models


class ActionsTestsSignoff(models.BasicSignoff):
    signetModel = models.Signet
    label = "Consent?"


signoff_type = ActionsTestsSignoff.register(
    id="test.actions_signoff", logic=SignoffLogic(perm="auth.add_signoff")
)


class ActionsSignoffFormTests(TestCase):
    def setUp(self):
        self.user = fixtures.get_user(perms=("add_signoff",))
        self.data = dict(
            signoff_id=signoff_type.id,
            signed_off="on",
        )

    def get_signoff_form(self, data=None):
        """Return a signoff form instance bound to class self.data"""
        data = data or self.data
        a = actions.BasicUserSignoffActions(self.user, data)
        return a.forms.get_signoff_form()

    def test_create(self):
        self.assertTrue(
            type(self.get_signoff_form()), signoff_type.forms.get_signoff_form_class()
        )

    def test_is_signed_off(self):
        bf = self.get_signoff_form()
        self.assertTrue(bf.is_valid())
        self.assertTrue(bf.is_signed_off())

    def test_not_signed_off(self):
        bf = self.get_signoff_form(data=dict(signoff_id=signoff_type.id))
        self.assertTrue(bf.is_valid())
        self.assertFalse(bf.is_signed_off())

    def test_invalid_signoff(self):
        bf = self.get_signoff_form(
            data=dict(signed_off="True", signoff_id="invalid.type")
        )
        self.assertIsNone(bf)

    def test_invalid_data(self):
        bf = self.get_signoff_form(data=dict(signed_off="True"))
        self.assertIsNone(bf)


class SignoffCommitterTests(TestCase):
    def setUp(self):
        self.user = fixtures.get_user(perms=("add_signoff",))
        self.signoff = signoff_type()

    def test_create(self):
        committer = actions.BasicSignoffCommitter(self.user)
        self.assertEqual(committer.user, self.user)

    def test_sign(self):
        committer = actions.BasicSignoffCommitter(self.user)
        committer.sign(self.signoff)
        self.assertTrue(self.signoff.is_signed())

    def test_revoke(self):
        self.signoff.sign_if_permitted(self.user)
        committer = actions.BasicSignoffCommitter(self.user)
        committer.revoke(self.signoff)
        self.assertFalse(self.signoff.is_signed())

    def test_post_signoff_hook(self):
        hook = Mock()

        committer = actions.BasicSignoffCommitter(self.user, post_signoff_hook=hook)
        committer.sign(self.signoff)
        self.assertTrue(hook.called)

    def test_post_revoke_hook(self):
        hook = Mock()

        self.signoff.sign_if_permitted(self.user)
        committer = actions.BasicSignoffCommitter(self.user, post_revoke_hook=hook)
        committer.revoke(self.signoff)
        self.assertTrue(hook.called)


class BasicUserSignoffActionsTests(TestCase):
    def setUp(self):
        self.user = fixtures.get_user(perms=("add_signoff",))
        self.data = dict(
            signoff_id=signoff_type.id,
            signed_off="on",
        )

    def test_create(self):
        action = actions.BasicUserSignoffActions(self.user, self.data)
        self.assertEqual(action.forms.get_signoff_type(), signoff_type)

    def test_is_valid_signoff_request(self):
        u = fixtures.get_user()
        u_action = actions.BasicUserSignoffActions(u, self.data)
        self.assertFalse(u_action.validator.is_valid_signoff_request(signoff_type()))

        action = actions.BasicUserSignoffActions(self.user, self.data)
        self.assertTrue(action.validator.is_valid_signoff_request(signoff_type()))

    def test_sign_signoff(self):
        action = actions.BasicUserSignoffActions(self.user, self.data)
        self.assertTrue(action.sign_signoff())
        self.assertTrue(action.signoff.is_signed())

    def test_sign_signoff_no_commit(self):
        action = actions.BasicUserSignoffActions(self.user, self.data)
        self.assertTrue(action.sign_signoff(commit=False))
        self.assertFalse(action.signoff.is_signed())

        action.signoff.save()
        self.assertTrue(action.signoff.is_signed())

    def test_sign_signoff_invalid(self):
        data = dict(signed_off="True", signoff_id="invalid.type")
        d_action = actions.BasicUserSignoffActions(self.user, data)
        self.assertFalse(d_action.sign_signoff())

    def test_unsigned_signoff(self):
        data = dict(signoff_id=signoff_type.id)
        d_action = actions.BasicUserSignoffActions(self.user, data)
        self.assertFalse(d_action.sign_signoff())

    def test_sign_signoff_permission_denied(self):
        u = fixtures.get_user()
        u_action = actions.BasicUserSignoffActions(u, self.data)
        self.assertFalse(u_action.sign_signoff())

    def revoke_data(self):
        """sign a signoff and return data defining its revocation"""
        action = actions.BasicUserSignoffActions(self.user, self.data)
        action.sign_signoff()
        self.assertTrue(action.signoff.is_signed())
        return dict(
            signoff_id=signoff_type.id,
            signet_pk=action.signoff.signet.pk,
        )

    def test_is_valid_revoke_request(self):
        action = actions.BasicUserSignoffActions(self.user, self.data)
        action.sign_signoff()

        u = fixtures.get_user()
        u_action = actions.BasicUserSignoffActions(u, self.revoke_data())
        self.assertFalse(u_action.validator.is_valid_revoke_request(action.signoff))

        r_action = actions.BasicUserSignoffActions(self.user, self.revoke_data())
        self.assertTrue(r_action.validator.is_valid_revoke_request(action.signoff))

    def test_invalid_revoke_request(self):
        action = actions.BasicUserSignoffActions(self.user, self.data)
        action.sign_signoff()

        r_action = actions.BasicUserSignoffActions(
            self.user,
            self.revoke_data(),
            validator=actions.BasicSignoffValidator(
                user=self.user, verify_signet=lambda signoff: False
            ),
        )

        self.assertFalse(r_action.validator.is_valid_revoke_request(action.signoff))

    def test_revoke_signoff(self):
        r_action = actions.BasicUserSignoffActions(self.user, self.revoke_data())
        self.assertTrue(r_action.revoke_signoff(commit=True))
        self.assertFalse(r_action.signoff.is_signed())

    def test_revoke_signoff_no_commit(self):
        r_action = actions.BasicUserSignoffActions(self.user, self.revoke_data())
        self.assertTrue(r_action.revoke_signoff(commit=False))
        self.assertTrue(r_action.signoff.is_signed())

        r_action.revoke_signoff()
        self.assertFalse(r_action.signoff.is_signed())

    def test_revoke_signoff_invalid(self):
        r_data = {**self.revoke_data(), "signet_pk": "invalid.type"}
        r_action = actions.BasicUserSignoffActions(self.user, r_data)
        self.assertFalse(r_action.revoke_signoff())

        r_data = {**self.revoke_data(), "signet_pk": 123}
        r_action = actions.BasicUserSignoffActions(self.user, r_data)
        self.assertFalse(r_action.revoke_signoff())

    def test_revoke_signoff_permission_denied(self):
        u = fixtures.get_user()
        u_action = actions.BasicUserSignoffActions(u, self.revoke_data())
        self.assertFalse(u_action.revoke_signoff())


@register(id="signoffs.test.actions_approval")
class ActionsApproval(BaseApproval):
    stampModel = models.Stamp
    label = "Test Approval"

    first_signoff = models.ApprovalSignoff.register(
        id="test.approval.actions.first", logic=SignoffLogic(perm="auth.add_signoff")
    )
    final_signoff = models.ApprovalSignoff.register(
        id="test.approval.actions.final", logic=SignoffLogic(perm="auth.add_signoff")
    )

    signing_order = so.SigningOrder(first_signoff, final_signoff)


class ApprovalSignoffCommitterTests(TestCase):
    def setUp(self):
        self.user = fixtures.get_user(perms=("add_signoff",))
        self.approval = ActionsApproval.create()
        self.signoff = ActionsApproval.first_signoff(stamp=self.approval.stamp)

    def test_approve_post_signoff_hook(self):
        """Test post_signoff_hook to approve the approval when signing order complete"""
        committer = actions.BasicSignoffCommitter(
            self.user, post_signoff_hook=lambda s: self.approval.approve_if_ready()
        )
        committer.sign(self.approval.first_signoff(stamp=self.approval.stamp))
        committer.sign(self.approval.final_signoff(stamp=self.approval.stamp))
        self.assertTrue(self.approval.is_approved())

    def test_post_signoff_hook(self):
        """Custom post_signoff_hook runs in an atomic transaction to maintain integrity of triggered DB ops"""
        hook = Mock()

        committer = actions.BasicSignoffCommitter(self.user, post_signoff_hook=hook)
        committer.sign(self.approval.first_signoff(stamp=self.approval.stamp))
        committer.sign(self.approval.final_signoff(stamp=self.approval.stamp))
        self.assertFalse(self.approval.is_approved())
        self.assertEqual(hook.call_count, 2)


class BasicUserApprovalActionsTests(TestCase):
    def setUp(self):
        self.user = fixtures.get_user(perms=("add_signoff",))
        self.approval = ActionsApproval.create()

    def get_data(self, signoff=None, stamp=None, signed_off="on"):
        signoff = signoff or self.approval.get_next_signoff(for_user=self.user)
        stamp = stamp or self.approval.stamp
        return dict(
            signoff_id=signoff.id if signoff else self.approval.first_signoff.id,
            signed_off=signed_off,
            stamp=stamp.id,
        )

    def test_create(self):
        action = actions.BasicUserApprovalActions(
            self.user, self.get_data(), self.approval
        )
        self.assertEqual(type(action.signoff_actions), actions.BasicUserSignoffActions)
        self.assertEqual(
            action.signoff_actions.forms.get_signoff_type(), self.approval.first_signoff
        )

    def test_is_valid_approval_signoff_request(self):
        u = fixtures.get_user()
        u_action = actions.BasicUserApprovalActions(u, self.get_data(), self.approval)
        self.assertFalse(
            u_action.validator.is_valid_signoff_request(self.approval.first_signoff())
        )

        action = actions.BasicUserApprovalActions(
            self.user, self.get_data(), self.approval
        )
        self.assertTrue(
            action.validator.is_valid_signoff_request(self.approval.first_signoff())
        )

    def test_sign_signoff(self):
        action = actions.BasicUserApprovalActions(
            self.user, self.get_data(), self.approval
        )
        self.assertTrue(action.sign_signoff())
        self.assertTrue(action.signoff.is_signed())
        self.assertEqual(self.approval.signoffs.count(), 1)

    def test_sign_to_approval(self):
        action = actions.BasicUserApprovalActions(
            self.user, self.get_data(), self.approval
        )
        action.sign_signoff()
        self.assertFalse(self.approval.is_approved())

        action = actions.BasicUserApprovalActions(
            self.user, self.get_data(), self.approval
        )
        action.sign_signoff()
        self.assertTrue(self.approval.is_approved())

    def test_sign_to_approval_manual(self):
        action = actions.BasicUserApprovalActions(
            self.user, self.get_data(), self.approval
        )
        action.sign_signoff()

        action = actions.BasicUserApprovalActions(
            self.user, self.get_data(), self.approval
        )
        action.sign_signoff(commit=False)
        self.assertFalse(self.approval.is_approved())
        action.sign_signoff()
        self.assertTrue(self.approval.is_approved())

    def revoke_data(self, signoff=None):
        """sign a signoff and return data defining its revokation"""
        if not signoff:
            action = actions.BasicUserApprovalActions(
                self.user, self.get_data(), self.approval
            )
            action.sign_signoff()
            self.assertTrue(action.signoff.is_signed())
            signoff = action.signoff
        return dict(
            signoff_id=signoff.id,
            signet_pk=signoff.signet.pk,
            stamp=signoff.signet.stamp_id,
        )

    def test_is_valid_revoke_signoff_request(self):
        action = actions.BasicUserApprovalActions(
            self.user, self.get_data(), self.approval
        )
        action.sign_signoff()
        signoff = action.signoff

        u = fixtures.get_user()
        u_action = actions.BasicUserApprovalActions(
            u, self.revoke_data(signoff=signoff), self.approval
        )
        self.assertFalse(u_action.validator.is_valid_revoke_request(signoff))

        r_action = actions.BasicUserApprovalActions(
            self.user, self.revoke_data(signoff=signoff), self.approval
        )
        self.assertTrue(r_action.validator.is_valid_revoke_request(signoff))

    def test_revoke_signoff(self):
        r_action = actions.BasicUserApprovalActions(
            self.user, self.revoke_data(), self.approval
        )
        self.assertTrue(r_action.revoke_signoff())
        self.assertFalse(r_action.signoff.is_signed())

    def test_revoke_signoff_manual(self):
        action = actions.BasicUserApprovalActions(
            self.user, self.get_data(), self.approval
        )
        action.sign_signoff()
        signoff = action.signoff

        r_action = actions.BasicUserApprovalActions(
            self.user, self.revoke_data(signoff=signoff), self.approval
        )
        self.assertTrue(r_action.revoke_signoff(commit=False))
        self.assertTrue(r_action.signoff.is_signed())
        r_action.revoke_signoff()
        self.assertFalse(r_action.signoff.is_signed())

    def test_approve_request(self):
        action = actions.BasicUserApprovalActions(
            self.user, self.get_data(), self.approval
        )
        action.sign_signoff()
        self.assertFalse(action.is_valid_approve_request())

        action = actions.BasicUserApprovalActions(
            self.user, self.get_data(), self.approval
        )
        action.sign_signoff()
        self.approval.stamp.approved = False
        self.assertTrue(action.is_valid_approve_request())
        action.approve()
        self.assertTrue(self.approval.is_approved())

    def test_revoke_approve_request(self):
        action = actions.BasicUserApprovalActions(
            self.user, self.get_data(), self.approval
        )
        action.sign_signoff()
        self.assertFalse(action.is_valid_approval_revoke_request())
        action = actions.BasicUserApprovalActions(
            self.user, self.get_data(), self.approval
        )
        action.sign_signoff()
        self.assertTrue(self.approval.is_approved())

        self.assertTrue(action.is_valid_approval_revoke_request())
        self.assertTrue(action.revoke_approval())
        self.assertFalse(self.approval.is_approved())
        self.assertEqual(self.approval.signoffs.count(), 0)


class FsmActionsProcessModel(Model):
    """An Approval Process model where transitions and approval sequencing are defined by FSM"""

    class States(TextChoices):
        STATE0 = "Initiated"
        STATE1 = "State 1"
        STATE2 = "State 2"

    state = fsm.FSMField(choices=States.choices, default=States.STATE0)

    approval1, approval1_stamp = ApprovalField(ActionsApproval)
    approval2, approval2_stamp = ApprovalField(
        ActionsApproval.register("signoffs.test.actions_approval2")
    )

    process = signoffs_process.FsmApprovalsProcess()

    # FSM approval state transitions
    @process.approval_transition(
        approval1, state, source=States.STATE0, target=States.STATE1
    )
    def transition1(self, approval):
        pass

    @process.revoke_transition(
        approval1, state, source=States.STATE1, target=States.STATE0
    )
    def revoke1(self, approval):
        pass

    @process.approval_transition(
        approval2, state, source=States.STATE1, target=States.STATE2
    )
    def transition2(self, approval):
        pass

    @process.revoke_transition(
        approval2, state, source=States.STATE2, target=States.STATE1
    )
    def revoke2(self, approval):
        pass

    def sign_and_approve(self, user=None):
        """Helper for testing - attempt to complete signoffs and make next approval transition."""
        user = user or fixtures.get_user(perms=("add_signoff",))
        approval = self.process.get_next_available_approval()
        if not approval:
            return
        while not approval.ready_to_approve():
            signoff = approval.get_next_signoff(for_user=user)
            if not signoff:
                break
            signoff.sign_if_permitted(user)
        self.process.try_approve_transition(approval, user)


class ApprovalProcessUserActionsTests(TestCase):
    def setUp(self):
        self.user = fixtures.get_user(perms=("add_signoff",))
        self.fsm = FsmActionsProcessModel.objects.create()
        self.approval_process = self.fsm.process

    def get_data(self, signoff=None, stamp=None, signed_off="on"):
        approval = self.approval_process.get_next_approval()
        if not approval:
            return {}
        signoff = signoff or approval.get_next_signoff(for_user=self.user)
        stamp = stamp or approval.stamp
        return dict(
            signoff_id=signoff.id if signoff else approval.first_signoff.id,
            signed_off=signed_off,
            stamp=stamp.id,
        )

    def test_create(self):
        action = actions.ApprovalProcessUserActions(
            self.user,
            self.get_data(),
            approval_process=self.approval_process,
            approval=self.approval_process.get_next_available_approval(),
        )
        self.assertEqual(type(action.signoff_actions), actions.BasicUserSignoffActions)
        self.assertEqual(
            action.signoff_actions.forms.get_signoff_type(),
            self.fsm.approval1.first_signoff,
        )

    def test_sign_signoff(self):
        action = actions.ApprovalProcessUserActions(
            self.user,
            self.get_data(),
            approval_process=self.approval_process,
            approval=self.approval_process.get_next_available_approval(),
        )
        self.assertTrue(action.sign_signoff())
        self.assertTrue(action.signoff.is_signed())
        self.assertEqual(action.approval.signoffs.count(), 1)

    def test_sign_to_approval(self):
        action = actions.ApprovalProcessUserActions(
            self.user,
            self.get_data(),
            approval_process=self.approval_process,
            approval=self.approval_process.get_next_available_approval(),
        )
        action.sign_signoff()
        self.assertFalse(action.approval.is_approved())
        self.assertEqual(self.fsm.state, self.fsm.States.STATE0)

        action = actions.ApprovalProcessUserActions(
            self.user,
            self.get_data(),
            approval_process=self.approval_process,
            approval=self.approval_process.get_next_available_approval(),
        )
        action.sign_signoff()
        self.assertTrue(action.approval.is_approved())
        self.assertEqual(self.fsm.state, self.fsm.States.STATE1)

    def test_sign_to_approval2(self):
        self.fsm.sign_and_approve(self.user)
        self.assertEqual(self.fsm.state, self.fsm.States.STATE1)
        action = actions.ApprovalProcessUserActions(
            self.user,
            self.get_data(),
            approval_process=self.approval_process,
            approval=self.approval_process.get_next_available_approval(),
        )
        action.sign_signoff()
        self.assertFalse(action.approval.is_approved())
        self.assertEqual(self.fsm.state, self.fsm.States.STATE1)

        action = actions.ApprovalProcessUserActions(
            self.user,
            self.get_data(),
            approval_process=self.approval_process,
            approval=self.approval_process.get_next_available_approval(),
        )
        action.sign_signoff()
        self.assertTrue(action.approval.is_approved())
        self.assertEqual(self.fsm.state, self.fsm.States.STATE2)

    def revoke_data(self, signoff=None):
        """sign a signoff and return data defining its revokation"""
        if not signoff:
            approval = self.approval_process.get_next_approval()
            if not approval:
                return {}
            signoff = approval.signoffs[-1]
        return dict(
            signoff_id=signoff.id,
            signet_pk=signoff.signet.pk,
            stamp=signoff.signet.stamp_id,
        )

    def test_is_valid_approval_revoke_request(self):
        action = actions.ApprovalProcessUserActions(
            self.user,
            self.get_data(),
            approval_process=self.approval_process,
            approval=self.approval_process.get_next_available_approval(),
        )
        action.sign_signoff()
        r_action = actions.ApprovalProcessUserActions(
            self.user,
            {},
            approval_process=self.approval_process,
            approval=self.approval_process.get_next_available_approval(),
        )
        self.assertFalse(r_action.is_valid_approval_revoke_request())

        self.fsm.sign_and_approve(self.user)
        self.assertEqual(self.fsm.state, self.fsm.States.STATE1)
        r_action = actions.ApprovalProcessUserActions(
            self.user,
            {},
            approval_process=self.approval_process,
            approval=self.approval_process.get_approved_approvals()[-1],
        )
        self.assertTrue(r_action.is_valid_approval_revoke_request())

    def test_revoke_signoff(self):
        action = actions.ApprovalProcessUserActions(
            self.user,
            self.get_data(),
            approval_process=self.approval_process,
            approval=self.approval_process.get_next_available_approval(),
        )
        action.sign_signoff()
        r_action = actions.ApprovalProcessUserActions(
            self.user,
            self.revoke_data(action.signoff),
            approval_process=self.approval_process,
            approval=self.approval_process.get_next_available_approval(),
        )
        self.assertTrue(r_action.revoke_signoff())
        self.assertFalse(r_action.signoff.is_signed())

    def test_approve_request(self):
        self.fsm.sign_and_approve(self.user)
        approval = self.approval_process.get_approved_approvals()[-1]
        approval.stamp.approved = False
        self.fsm.state = self.fsm.States.STATE0
        action = actions.ApprovalProcessUserActions(
            self.user,
            {},
            approval_process=self.approval_process,
            approval=self.approval_process.get_next_available_approval(),
        )
        action.approve()
        self.assertTrue(approval.is_approved())
        self.assertEqual(self.fsm.state, self.fsm.States.STATE1)

    def test_revoke_approve_request(self):
        self.fsm.sign_and_approve(self.user)
        self.fsm.sign_and_approve(self.user)
        self.assertEqual(self.fsm.state, self.fsm.States.STATE2)

        action = actions.ApprovalProcessUserActions(
            self.user,
            {},
            approval_process=self.approval_process,
            approval=self.approval_process.get_approved_approvals()[-1],
        )
        self.assertTrue(action.is_valid_approval_revoke_request())
        self.assertTrue(action.revoke_approval())
        self.assertFalse(action.approval.is_approved())
        self.assertEqual(action.approval.signoffs.count(), 0)
        self.assertEqual(self.fsm.state, self.fsm.States.STATE1)

        action = actions.ApprovalProcessUserActions(
            self.user,
            {},
            approval_process=self.approval_process,
            approval=self.approval_process.get_approved_approvals()[-1],
        )
        self.assertTrue(action.revoke_approval())
        self.assertEqual(self.fsm.state, self.fsm.States.STATE0)
