"""
App-dependent tests for signoff model fields and relation descriptors
"""
from django.test import TestCase

from signoffs.core.tests import fixtures
from tests.test_app import models, signoffs


class SignoffSetTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.employee = fixtures.get_user()
        cls.hr1 = fixtures.get_user(
            first_name="Herman",
            last_name="Roy",
            username="hr1",
            perms=("can_approve_hr",),
        )
        cls.hr2 = fixtures.get_user(
            first_name="Hillary",
            last_name="Rice",
            username="hr2",
            perms=("can_approve_hr",),
        )
        cls.vacation = models.Vacation.objects.create(employee="Bob")
        # Signets can be added via the class...
        s1 = models.Vacation.signoffset.create(user=cls.hr1, vacation=cls.vacation)
        # or directly on the related instance
        s2 = cls.vacation.signoffset.create(user=cls.hr2)
        cls.signoffs = [s1, s2]
        cls.signets = [s.signet for s in cls.signoffs]

    def test_signoffset(self):
        self.assertEqual(models.Vacation.signoffset, signoffs.hr_signoff)
        self.assertListEqual(self.vacation.signoffset.all(), self.signoffs)

    def test_signoff_field(self):
        self.assertTrue(self.vacation.employee_signoff.matches(signoffs.agree_signoff))

    def test_signoff_field_form(self):
        v, _ = models.Vacation.objects.get_or_create(employee_signet__user=self.employee)
        form = v.employee_signoff.forms.get_signoff_form(
            data={"signed_off": "on", "signoff_id": "test_app.agree"}
        )
        self.assertTrue(form.is_valid())
        self.assertTrue(form.is_signed_off())
        v.employee_signet = form.sign(user=self.employee, commit=True)
        signoff = v.employee_signet.signoff
        self.assertTrue(signoff.is_signed())
        self.assertEqual(signoff.signatory, self.employee)
        # Must save Vacation instance to persist the FK relation!
        v.save()
        _, created = models.Vacation.objects.get_or_create(employee_signet__user=self.employee)
        self.assertFalse(created)

    def test_signoff_field_form_signed(self):
        v, _ = models.Vacation.objects.get_or_create(employee_signet__user=self.employee)
        form = v.employee_signoff.forms.get_signoff_form(
            data={"signed_off": "on", "signoff_id": "test_app.agree"}
        )
        v.employee_signet = form.sign(user=self.employee, commit=True)
        v.save()

        v, created = models.Vacation.objects.get_or_create(employee_signet__user=self.employee)
        self.assertFalse(created)
        self.assertTrue(v.employee_signoff.is_signed())
        self.assertEqual(v.employee_signoff.signatory, self.employee)


# TODO: extend these tests to exercise signoffset and signofffield, verify sigil field, revoke logic, etc.
#       test revoking a SignoffField - does this break DB constraint?
