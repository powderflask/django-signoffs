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

    def test_fsm_approval_sequence(self):
        process = ConstructionPermittingProcess(building=Building.objects.create(name='Eiffel Tower'))
        seq = process.approval_sequence
        # sequence is alphabetical b/c FSM being used to provide actual approval ordering
        self.assertListEqual([k for k in seq], ['apply', 'final_inspection', 'interim_inspection', 'permit'])
        self.assertListEqual([('apply', process.applied),
                              ('final_inspection', process.authorized),
                              ('interim_inspection', process.inspected),
                              ('permit', process.permitted)],
                             [(k, v) for k, v in seq.on_approval_transitions().items()]
                             )

    def test_fsm_get_available_approvals(self):
        process = ConstructionPermittingProcess(building=Building.objects.create(name='Hotel California'))
        self.assertListEqual(process.get_available_approvals(), [process.apply, ])
        process.apply.approve()
        del process.approval_sequence
        self.assertListEqual(process.get_available_approvals(), [process.permit, ])
        process.permit.approve()
        del process.approval_sequence
        self.assertListEqual(process.get_available_approvals(), [process.interim_inspection, ])
        process.interim_inspection.approve()
        del process.approval_sequence
        self.assertListEqual(process.get_available_approvals(), [process.final_inspection, ])
        process.final_inspection.approve()
        del process.approval_sequence
        self.assertListEqual(process.get_available_approvals(), [])

    # Approval Steps for ConstructionPermittingProcess

    def permit_application(self, process):
        """ move the given process from INITIATED to APPLIED """
        self.assertEqual(process.state, process.States.INITIATED)
        self.assertTrue(process.can_proceed('apply'))
        self.assertFalse(process.can_proceed('interim_inspection'))
        self.assertTrue(process.can_user_proceed(user=self.applicant, approval='apply'))

        next_approval = process.get_next_available_approval()
        self.assertEqual(next_approval, process.apply)

        next_approval.sign_approval(user=self.applicant)
        self.assertTrue(process.apply.is_approved())
        self.assertEqual(process.state, process.States.APPLIED)

    def revoke_application(self, process):
        """ move the given process from APPLIED back to INITIATED """
        self.assertEqual(process.state, process.States.APPLIED)
        self.assertTrue(process.can_revoke('apply'))
        self.assertFalse(process.can_revoke('interim_inspection'))
        self.assertTrue(process.can_user_revoke(user=self.applicant, approval='apply'))

        revoke_approval = process.get_next_revokable_approval()
        self.assertEqual(revoke_approval, process.apply)

        revoke_approval.revoke(user=self.applicant)
        self.assertFalse(process.apply.is_approved())
        self.assertEqual(process.state, process.States.INITIATED)

    def permit_approval(self, process):
        """ move the given process from APPLIED to PERMITTED """
        self.assertEqual(process.state, process.States.APPLIED)
        self.assertTrue(process.can_proceed('permit'))
        self.assertFalse(process.can_proceed('interim_inspection'))

        next_approval = process.get_next_available_approval()
        self.assertEqual(next_approval, process.permit)

        next_approval.sign_approval(user=self.planner)
        self.assertFalse(process.permit.is_approved())
        self.assertEqual(process.state, process.States.APPLIED)

        next_approval = process.get_next_available_approval()
        self.assertEqual(next_approval, process.permit)

        next_approval.sign_approval(user=self.electrician)
        self.assertFalse(process.permit.is_approved())
        self.assertEqual(process.state, process.States.APPLIED)

        next_approval = process.get_next_available_approval()
        self.assertEqual(next_approval, process.permit)

        next_approval.sign_approval(user=self.inspector)
        self.assertTrue(process.permit.is_approved())
        self.assertEqual(process.state, process.States.PERMITTED)

    def interim_inspection(self, process):
        """ move the given process from PERMITTED to INSPECTED """
        self.assertEqual(process.state, process.States.PERMITTED)
        self.assertTrue(process.can_proceed('interim_inspection'))
        self.assertFalse(process.can_proceed('final_inspection'))

        next_approval = process.get_next_available_approval()
        self.assertEqual(next_approval, process.interim_inspection)

        next_approval.sign_approval(user=self.electrician)
        self.assertFalse(process.interim_inspection.is_approved())
        self.assertEqual(process.state, process.States.PERMITTED)

        next_approval = process.get_next_available_approval()
        self.assertEqual(next_approval, process.interim_inspection)

        next_approval.sign_approval(user=self.plumber, last=True)  # TODO: remove with permissions or transition restrictions
        self.assertFalse(process.interim_inspection.is_approved())
        self.assertEqual(process.state, process.States.PERMITTED)

        next_approval = process.get_next_available_approval()
        self.assertEqual(next_approval, process.interim_inspection)

        next_approval.sign_approval(user=self.inspector, last=True)  # TODO: remove with permissions or transition restrictions
        self.assertTrue(process.interim_inspection.is_approved())
        self.assertEqual(process.state, process.States.INSPECTED)

    def final_inspection(self, process):
        """ move the given process from INSPECTED to APPROVED """
        self.assertEqual(process.state, process.States.INSPECTED)
        self.assertTrue(process.can_proceed('final_inspection'))
        self.assertFalse(process.can_proceed('apply'))
        self.assertFalse(process.can_proceed('permit'))
        self.assertFalse(process.can_proceed('interim_inspection'))

        next_approval = process.get_next_available_approval()
        self.assertEqual(next_approval, process.final_inspection)

        next_approval.sign_approval(user=self.inspector, last=True)  # TODO: remove with permissions or transition restrictions
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

