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


# TODO: extend these tests to exercise signoffset and signofffield, verify sigil field, revoke logic, etc.
#       test revoking a SignoffField - does this break DB constraint?
