"""
Test App - tests for approval process models
"""
from django.test import TestCase

from signoffs.core.tests import fixtures
from tests.test_app.models import Building, ConstructionPermittingProcess


class FsmApprovalProcessModelTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.applicant = fixtures.get_user()
        cls.planner = fixtures.get_user()
        cls.electrician = fixtures.get_user()
        cls.plumber = fixtures.get_user()
        cls.inspector = fixtures.get_user()

    def test_fsm_transition_sequence(self):
        model = ConstructionPermittingProcess(
            building=Building.objects.create(name="Eiffel Tower")
        )
        self.assertListEqual(
            [model.applied, model.permitted, model.inspected, model.authorized],
            [
                model.process.bound_approve_transition(a)
                for a in model.process.get_all_approvals()
            ],
        )

    def test_fsm_get_all_approvals(self):
        model = ConstructionPermittingProcess(
            building=Building.objects.create(name="Eiffel Tower")
        )
        self.assertListEqual(
            model.process.get_all_approvals(),
            [
                model.apply,
                model.permit,
                model.interim_inspection,
                model.final_inspection,
            ],
        )

    def test_fsm_get_available_approvals(self):
        model = ConstructionPermittingProcess(
            building=Building.objects.create(name="Hotel California")
        )
        self.assertListEqual(
            model.process.get_available_approvals(),
            [
                model.apply,
            ],
        )
        self.permit_application(model)
        self.assertListEqual(
            model.process.get_available_approvals(),
            [
                model.permit,
            ],
        )
        self.permit_approval(model)
        self.assertListEqual(
            model.process.get_available_approvals(),
            [
                model.interim_inspection,
            ],
        )
        self.interim_inspection(model)
        self.assertListEqual(
            model.process.get_available_approvals(),
            [
                model.final_inspection,
            ],
        )
        self.final_inspection(model)
        self.assertListEqual(model.process.get_available_approvals(), [])

    # Approval Steps for ConstructionPermittingProcess

    def permit_application(self, model):
        """move the given process from INITIATED to APPLIED"""
        self.assertEqual(model.state, model.States.INITIATED)
        self.assertTrue(model.process.can_proceed(model.apply))
        self.assertFalse(model.process.can_proceed(model.interim_inspection))
        self.assertTrue(
            model.process.user_can_proceed(user=self.applicant, approval=model.apply)
        )

        next_approval = model.process.get_next_available_approval()
        self.assertEqual(next_approval, model.apply)

        next_approval.sign_approval(user=self.applicant)
        self.assertTrue(
            model.process.try_approve_transition(model.apply, user=self.applicant)
        )
        self.assertTrue(model.apply.is_approved())
        self.assertEqual(model.state, model.States.APPLIED)

    def revoke_application(self, model):
        """move the given process from APPLIED back to INITIATED"""
        self.assertEqual(model.state, model.States.APPLIED)
        self.assertTrue(model.process.is_revokable(model.apply))
        self.assertFalse(model.process.is_revokable(model.interim_inspection))
        self.assertTrue(
            model.process.user_can_revoke(user=self.applicant, approval=model.apply)
        )

        revoke_approval = model.process.get_next_revokable_approval()
        self.assertEqual(revoke_approval, model.apply)

        self.assertTrue(
            model.process.try_revoke_transition(model.apply, user=self.applicant)
        )
        self.assertFalse(model.apply.is_approved())
        self.assertEqual(model.state, model.States.INITIATED)

    def permit_approval(self, model):
        """move the given process from APPLIED to PERMITTED"""
        self.assertEqual(model.state, model.States.APPLIED)
        self.assertTrue(model.process.can_proceed(model.permit))
        self.assertFalse(model.process.can_proceed(model.interim_inspection))

        next_approval = model.process.get_next_available_approval()
        self.assertEqual(next_approval, model.permit)

        next_approval.sign_approval(user=self.planner)
        self.assertFalse(model.permit.is_approved())
        self.assertEqual(model.state, model.States.APPLIED)

        next_approval = model.process.get_next_available_approval()
        self.assertEqual(next_approval, model.permit)

        next_approval.sign_approval(user=self.electrician)
        self.assertFalse(model.permit.is_approved())
        self.assertEqual(model.state, model.States.APPLIED)

        next_approval = model.process.get_next_available_approval()
        self.assertEqual(next_approval, model.permit)

        next_approval.sign_approval(user=self.inspector)
        self.assertTrue(
            model.process.try_approve_transition(model.permit, user=self.inspector)
        )
        self.assertTrue(model.permit.is_approved())
        self.assertEqual(model.state, model.States.PERMITTED)

    def interim_inspection(self, model):
        """move the given process from PERMITTED to INSPECTED"""
        self.assertEqual(model.state, model.States.PERMITTED)
        self.assertTrue(model.process.can_proceed(model.interim_inspection))
        self.assertFalse(model.process.can_proceed(model.final_inspection))

        next_approval = model.process.get_next_available_approval()
        self.assertEqual(next_approval, model.interim_inspection)

        next_approval.sign_approval(user=self.electrician)
        self.assertFalse(model.interim_inspection.is_approved())
        self.assertEqual(model.state, model.States.PERMITTED)

        next_approval = model.process.get_next_available_approval()
        self.assertEqual(next_approval, model.interim_inspection)

        next_approval.sign_approval(
            user=self.plumber, last=True
        )  # TODO: remove with permissions or transition restrictions
        self.assertFalse(model.interim_inspection.is_approved())
        self.assertEqual(model.state, model.States.PERMITTED)

        next_approval = model.process.get_next_available_approval()
        self.assertEqual(next_approval, model.interim_inspection)

        next_approval.sign_approval(
            user=self.inspector, last=True
        )  # TODO: remove with permissions or transition restrictions
        self.assertTrue(
            model.process.try_approve_transition(
                model.interim_inspection, user=self.inspector
            )
        )
        self.assertTrue(model.interim_inspection.is_approved())
        self.assertEqual(model.state, model.States.INSPECTED)

    def final_inspection(self, model):
        """move the given process from INSPECTED to APPROVED"""
        self.assertEqual(model.state, model.States.INSPECTED)
        self.assertTrue(model.process.can_proceed(model.final_inspection))
        self.assertFalse(model.process.can_proceed(model.apply))
        self.assertFalse(model.process.can_proceed(model.permit))
        self.assertFalse(model.process.can_proceed(model.interim_inspection))

        next_approval = model.process.get_next_available_approval()
        self.assertEqual(next_approval, model.final_inspection)

        next_approval.sign_approval(
            user=self.inspector, last=True
        )  # TODO: remove with permissions or transition restrictions
        self.assertTrue(
            model.process.try_approve_transition(
                model.final_inspection, user=self.inspector
            )
        )
        self.assertTrue(model.final_inspection.is_approved())
        self.assertEqual(model.state, model.States.APPROVED)

    def test_fsm_approval_sequencing(self):
        model = ConstructionPermittingProcess(
            building=Building.objects.create(name="Burj Khalifa")
        )
        self.permit_application(model)
        self.permit_approval(model)
        self.interim_inspection(model)
        self.final_inspection(model)

    def test_fsm_revoke_transition(self):
        model = ConstructionPermittingProcess(
            building=Building.objects.create(name="Burj Khalifa")
        )
        self.permit_application(model)
        self.revoke_application(model)
        self.permit_application(model)
        self.revoke_application(model)
