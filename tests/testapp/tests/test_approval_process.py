"""
Test App - tests for approval process models
"""
from django.test import TestCase

from signoffs.core.tests import fixtures
from testapp.models import Building, ConstructionPermittingProcess


class FsmApprovalProcessTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.applicant = fixtures.get_user()
        cls.planner = fixtures.get_user()
        cls.electrician = fixtures.get_user()
        cls.plumber = fixtures.get_user()
        cls.inspector = fixtures.get_user()

    def test_fsm_transition_sequence(self):
        process = ConstructionPermittingProcess(building=Building.objects.create(name='Eiffel Tower'))
        self.assertListEqual([process.applied, process.permitted, process.inspected, process.authorized],
                             [process.actions.bound_approve_transition(a) for a in process.actions.get_all_approvals()]
                             )

    def test_fsm_get_all_approvals(self):
        process = ConstructionPermittingProcess(building=Building.objects.create(name='Eiffel Tower'))
        self.assertListEqual(process.actions.get_all_approvals(),
                             [process.apply, process.permit, process.interim_inspection, process.final_inspection])

    def test_fsm_get_available_approvals(self):
        process = ConstructionPermittingProcess(building=Building.objects.create(name='Hotel California'))
        self.assertListEqual(process.actions.get_available_approvals(), [process.apply, ])
        self.permit_application(process)
        self.assertListEqual(process.actions.get_available_approvals(), [process.permit, ])
        self.permit_approval(process)
        self.assertListEqual(process.actions.get_available_approvals(), [process.interim_inspection, ])
        self.interim_inspection(process)
        self.assertListEqual(process.actions.get_available_approvals(), [process.final_inspection, ])
        self.final_inspection(process)
        self.assertListEqual(process.actions.get_available_approvals(), [])

    # Approval Steps for ConstructionPermittingProcess

    def permit_application(self, process):
        """ move the given process from INITIATED to APPLIED """
        self.assertEqual(process.state, process.States.INITIATED)
        self.assertTrue(process.actions.can_proceed(process.apply))
        self.assertFalse(process.actions.can_proceed(process.interim_inspection))
        self.assertTrue(process.actions.user_can_proceed(user=self.applicant, approval=process.apply))

        next_approval = process.actions.get_next_available_approval()
        self.assertEqual(next_approval, process.apply)

        next_approval.sign_approval(user=self.applicant)
        self.assertTrue(process.actions.try_approve_transition(process.apply, user=self.applicant))
        self.assertTrue(process.apply.is_approved())
        self.assertEqual(process.state, process.States.APPLIED)

    def revoke_application(self, process):
        """ move the given process from APPLIED back to INITIATED """
        self.assertEqual(process.state, process.States.APPLIED)
        self.assertTrue(process.actions.can_revoke(process.apply))
        self.assertFalse(process.actions.can_revoke(process.interim_inspection))
        self.assertTrue(process.actions.user_can_revoke(user=self.applicant, approval=process.apply))

        revoke_approval = process.actions.get_next_revokable_approval()
        self.assertEqual(revoke_approval, process.apply)

        self.assertTrue(process.actions.try_revoke_transition(process.apply, user=self.applicant))
        self.assertFalse(process.apply.is_approved())
        self.assertEqual(process.state, process.States.INITIATED)

    def permit_approval(self, process):
        """ move the given process from APPLIED to PERMITTED """
        self.assertEqual(process.state, process.States.APPLIED)
        self.assertTrue(process.actions.can_proceed(process.permit))
        self.assertFalse(process.actions.can_proceed(process.interim_inspection))

        next_approval = process.actions.get_next_available_approval()
        self.assertEqual(next_approval, process.permit)

        next_approval.sign_approval(user=self.planner)
        self.assertFalse(process.permit.is_approved())
        self.assertEqual(process.state, process.States.APPLIED)

        next_approval = process.actions.get_next_available_approval()
        self.assertEqual(next_approval, process.permit)

        next_approval.sign_approval(user=self.electrician)
        self.assertFalse(process.permit.is_approved())
        self.assertEqual(process.state, process.States.APPLIED)

        next_approval = process.actions.get_next_available_approval()
        self.assertEqual(next_approval, process.permit)

        next_approval.sign_approval(user=self.inspector)
        self.assertTrue(process.actions.try_approve_transition(process.permit, user=self.inspector))
        self.assertTrue(process.permit.is_approved())
        self.assertEqual(process.state, process.States.PERMITTED)

    def interim_inspection(self, process):
        """ move the given process from PERMITTED to INSPECTED """
        self.assertEqual(process.state, process.States.PERMITTED)
        self.assertTrue(process.actions.can_proceed(process.interim_inspection))
        self.assertFalse(process.actions.can_proceed(process.final_inspection))

        next_approval = process.actions.get_next_available_approval()
        self.assertEqual(next_approval, process.interim_inspection)

        next_approval.sign_approval(user=self.electrician)
        self.assertFalse(process.interim_inspection.is_approved())
        self.assertEqual(process.state, process.States.PERMITTED)

        next_approval = process.actions.get_next_available_approval()
        self.assertEqual(next_approval, process.interim_inspection)

        next_approval.sign_approval(user=self.plumber, last=True)  # TODO: remove with permissions or transition restrictions
        self.assertFalse(process.interim_inspection.is_approved())
        self.assertEqual(process.state, process.States.PERMITTED)

        next_approval = process.actions.get_next_available_approval()
        self.assertEqual(next_approval, process.interim_inspection)

        next_approval.sign_approval(user=self.inspector, last=True)  # TODO: remove with permissions or transition restrictions
        self.assertTrue(process.actions.try_approve_transition(process.interim_inspection, user=self.inspector))
        self.assertTrue(process.interim_inspection.is_approved())
        self.assertEqual(process.state, process.States.INSPECTED)

    def final_inspection(self, process):
        """ move the given process from INSPECTED to APPROVED """
        self.assertEqual(process.state, process.States.INSPECTED)
        self.assertTrue(process.actions.can_proceed(process.final_inspection))
        self.assertFalse(process.actions.can_proceed(process.apply))
        self.assertFalse(process.actions.can_proceed(process.permit))
        self.assertFalse(process.actions.can_proceed(process.interim_inspection))

        next_approval = process.actions.get_next_available_approval()
        self.assertEqual(next_approval, process.final_inspection)

        next_approval.sign_approval(user=self.inspector, last=True)  # TODO: remove with permissions or transition restrictions
        self.assertTrue(process.actions.try_approve_transition(process.final_inspection, user=self.inspector))
        self.assertTrue(process.final_inspection.is_approved())
        self.assertEqual(process.state, process.States.APPROVED)

    def test_fsm_approval_sequencing(self):
        process = ConstructionPermittingProcess(building=Building.objects.create(name='Burj Khalifa'))
        self.permit_application(process)
        self.permit_approval(process)
        self.interim_inspection(process)
        self.final_inspection(process)

    def test_fsm_revoke_transition(self):
        process = ConstructionPermittingProcess(building=Building.objects.create(name='Burj Khalifa'))
        self.permit_application(process)
        self.revoke_application(process)
        self.permit_application(process)
        self.revoke_application(process)

