"""
App-independent tests for Approval model descriptors - no app logic
"""
from django.test import TestCase

from .models import Stamp, LeaveApproval, LeaveRequest


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

    # def test_approvalset(self):
    #     lr = LeaveRequest()
    #     # ManyToOne reverse relation
    #     self.assertEqual(lr.hr_signoffs.count(), 0)
    #
    # def test_approvalset_integrity_checks(self):
    #     m = InvalidModel()
    #     with self.assertRaises(exceptions.ImproperlyConfigured):
    #         m.invalid_signet.count()
    #     with self.assertRaises(exceptions.ImproperlyConfigured):
    #         m.invalid_relation.count()


# TODO: need logic to get next signoff, etc.
# class ApprovalRelationTests(TestCase):
#     @classmethod
#     def setUpTestData(cls):
#         cls.u1 = fixtures.get_user()
#         cls.u2 = fixtures.get_user()
#         cls.u3 = fixtures.get_user()
#         lr = LeaveRequest.objects.create()
#         lr.employee_signoff.sign(cls.u1).save()
#         cls.hr_signoffs = (
#             lr.hr_signoffs.create(user=cls.u1),
#             lr.hr_signoffs.create(user=cls.u2),
#         )
#         lr.mngmt_signoffs.create(user=cls.u3),
#         cls.lr = lr
#
#     def test_approvalfield(self):
#         with self.assertNumQueries(1):
#             lr = LeaveRequest.objects.select_related('employee_signoff_signet').get(pk=self.lr.pk)
#             # OneToOne forward relation
#             self.assertTrue(lr.employee_signoff.is_signed())
#
#     def test_approvalset_manager(self):
#         with self.assertNumQueries(2):
#             lr = LeaveRequest.objects.prefetch_related('signatories').get(pk=self.lr.pk)
#             # ManyToOne reverse relation
#             self.assertTrue(lr.hr_signoffs.exists())
#             self.assertEqual(lr.hr_signoffs.count(), 2)
#             self.assertTrue(all(s.is_signed() for s in lr.hr_signoffs.all()) )
#
#     def test_approvalset_queries(self):
#         with self.assertNumQueries(2):
#             lr = LeaveRequest.objects.prefetch_related('signatories').get(pk=self.lr.pk)
#             # Earliest / Latest
#             self.assertEqual(lr.hr_signoffs.earliest(), self.hr_signoffs[0])
#             self.assertEqual(lr.hr_signoffs.latest(), self.hr_signoffs[-1])
#
#     def test_approvalset_signatories(self):
#         with self.assertNumQueries(3):
#             lr = LeaveRequest.objects.prefetch_related('signatories__user').get(pk=self.lr.pk)
#             self.assertTrue(lr.hr_signoffs.can_sign(self.u3))
#             self.assertFalse(lr.hr_signoffs.can_sign(AnonymousUser()))
#             self.assertTrue(lr.hr_signoffs.has_signed(self.u1))
#             self.assertFalse(lr.hr_signoffs.has_signed(self.u3))
#
#     def test_approvalset_form(self):
#         lr = LeaveRequest.objects.prefetch_related('signatories').get(pk=self.lr.pk)
#         form = lr.hr_signoffs.get_form_class()
#         self.assertTrue(issubclass(form, AbstractApprovalForm))
#         self.assertEqual(form()['signoff_id'].initial, hr_signoff_type.id)
#
#     def test_approvalset_revoked(self):
#         u = fixtures.get_user()
#         lr = LeaveRequest.objects.prefetch_related('signatories').get(pk=self.lr.pk)
#         n_revokes = 3
#         for i in range(n_revokes):
#             so = lr.hr_signoffs.create(user=u)
#             so.revoke(user=u, reason='just because')
#         with self.assertNumQueries(2):
#             lr = LeaveRequest.objects.get(pk=self.l.pk)
#             revoked = lr.hr_signoffs.revoked()
#             self.assertEqual(len(revoked), n_revokes)
#             self.assertTrue(all(s.revoked.user == u for s in revoked) )


# DEV Testing only - delete me

# class DevTests(TestCase):
#
#     def dont_test_it(self):
#         l = LeaveRequest.objects.create()
#         print([
#             (f.related_model, f.model) for f in hr_signoff_type.get_signetModel()._meta.fields
#                 if isinstance(f, models.ForeignKey) and
#                    not issubclass(f.related_model, AbstractSignet) and
#                    f.name != 'user'
#         ])
#
#         self.assertTrue(False)
