"""
App-independent tests for Signoff model descriptors - no app logic
"""
from django.contrib.auth.models import AnonymousUser
from django.test import TestCase

from signoffs.core.forms import AbstractSignoffForm

from . import fixtures
from .models import InvalidModel, LeaveRequest, Signet


class SimpleSignoffRelationTests(TestCase):
    def test_signofffield_relations(self):
        lr = LeaveRequest()
        self.assertEqual(
            LeaveRequest.employee_signoff.id, LeaveRequest.employee_signoff_type.id
        )
        self.assertEqual(type(lr.employee_signoff).id, LeaveRequest.employee_signoff.id)
        self.assertEqual(
            type(lr.employee_signoff.signet),
            LeaveRequest.employee_signoff.get_signetModel(),
        )
        self.assertEqual(lr.employee_signet, None)

    def test_signofffield(self):
        lr = LeaveRequest()
        # OneToOne forward relation
        self.assertTrue(
            isinstance(lr.employee_signoff, LeaveRequest.employee_signoff_type)
        )
        self.assertEqual(lr.employee_signoff.signet_model, Signet)
        self.assertFalse(lr.employee_signoff.is_signed())

    def test_signoffset(self):
        lr = LeaveRequest.objects.create()
        # ManyToOne reverse relation
        self.assertEqual(lr.hr_signoffs.count(), 0)

    def test_signoffset_integrity_checks(self):
        m = InvalidModel()
        with self.assertRaises(ValueError):
            m.invalid_signet.count()
        with self.assertRaises(ValueError):
            m.invalid_relation.count()


class SignoffRelationTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        u1 = fixtures.get_user()
        u2 = fixtures.get_user()
        u3 = fixtures.get_user()
        lr = LeaveRequest.objects.create()
        lr.employee_signoff.sign_if_permitted(u1)
        cls.hr_signoffs = (
            lr.hr_signoffs.create(user=u1),
            lr.hr_signoffs.create(user=u2),
        )
        lr.mngmt_signoffs.create(user=u3),
        cls.u1, cls.u2, cls.u3 = u1, u2, u3
        cls.lr = lr

    def test_signofffield(self):
        with self.assertNumQueries(1):
            lr = LeaveRequest.objects.select_related("employee_signet").get(
                pk=self.lr.pk
            )
            # OneToOne forward relation
            self.assertTrue(lr.employee_signoff.is_signed())

    def test_signoffset_manager(self):
        with self.assertNumQueries(2):
            lr = LeaveRequest.objects.prefetch_related("signatories").get(pk=self.lr.pk)
            # ManyToOne reverse relation
            self.assertTrue(lr.hr_signoffs.exists())
            self.assertEqual(lr.hr_signoffs.count(), 2)
        # and 2 more to check if signoffs are revoked b/c need to fetch revoke receipt
        with self.assertNumQueries(2):
            self.assertTrue(all(s.is_signed() for s in lr.hr_signoffs.all()))

    def test_signoffset_queries(self):
        with self.assertNumQueries(2):
            lr = LeaveRequest.objects.prefetch_related("signatories").get(pk=self.lr.pk)
            # Earliest / Latest
            self.assertEqual(lr.hr_signoffs.earliest(), self.hr_signoffs[0])
            self.assertEqual(lr.hr_signoffs.latest(), self.hr_signoffs[-1])

    def test_signoffset_signatories(self):
        with self.assertNumQueries(3):
            lr = LeaveRequest.objects.prefetch_related("signatories__user").get(
                pk=self.lr.pk
            )
            self.assertTrue(lr.hr_signoffs.can_sign(self.u3))
            self.assertFalse(lr.hr_signoffs.can_sign(AnonymousUser()))
            self.assertTrue(lr.hr_signoffs.has_signed(self.u1))
            self.assertFalse(lr.hr_signoffs.has_signed(self.u3))

    def test_signoffset_form(self):
        lr = LeaveRequest.objects.prefetch_related("signatories").get(pk=self.lr.pk)
        form = lr.hr_signoffs.forms.get_signoff_form_class()
        self.assertTrue(issubclass(form, AbstractSignoffForm))
        self.assertEqual(form()["signoff_id"].initial, LeaveRequest.hr_signoff_type.id)

    def test_signoffset_revoked(self):
        u = fixtures.get_user()
        lr = LeaveRequest.objects.prefetch_related("signatories").get(pk=self.lr.pk)
        n_revokes = 3
        for _ in range(n_revokes):
            so = lr.hr_signoffs.create(user=u)
            so.revoke_if_permitted(user=u, reason="just because")
        with self.assertNumQueries(2):
            lr = LeaveRequest.objects.get(pk=self.lr.pk)
            revoked = lr.hr_signoffs.revoked()
            self.assertEqual(len(revoked), n_revokes)
            self.assertTrue(all(s.revoked.user == u for s in revoked))


# DEV Testing only - delete me


# class DevTests(TestCase):
#
#     def dont_test_it(self):
#         lr = LeaveRequest.objects.create()
#         print([
#             (f.related_model, f.model) for f in LeaveRequest.hr_signoff_type.get_signetModel()._meta.fields
#                 if isinstance(f, models.ForeignKey)
#                    and not issubclass(f.related_model, AbstractSignet)
#                    and f.name != 'user'
#         ])
#
#         self.assertTrue(False)
