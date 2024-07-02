"""
App-dependent tests for signoff forms - requires models that can be saved, etc.
"""
from django.core import exceptions
from django.test import TestCase

from signoffs.core.tests import fixtures
from signoffs.forms import signoff_form_factory
from tests.test_app import models, signoffs

consent_signoff = signoffs.consent_signoff
SignoffForm = signoff_form_factory(signoff_type=consent_signoff)

ReportSignoffForm = signoff_form_factory(signoff_type=signoffs.report_signoff)


class SignoffFormWithUserTests(TestCase):
    def get_form(self, data=None, **kwargs):
        data = data or dict(signed_off="True", signoff_id=consent_signoff.id)
        return SignoffForm(data=data, **kwargs)

    def test_save(self):
        u = fixtures.get_user(perms=("can_sign",))
        bf = self.get_form()
        self.assertTrue(bf.is_valid())
        v = bf.sign(user=u)
        self.assertIsInstance(v, models.AbstractSignet)
        self.assertTrue(v.signoff.is_signed())
        self.assertEqual(v.signoff_id, consent_signoff.id)
        self.assertEqual(v.user, u)
        self.assertEqual(v.sigil, u.get_full_name())

    def test_invalid_save(self):
        bf = self.get_form()
        self.assertTrue(
            bf.is_valid()
        )  # form is valid even if user doesn't have permission to save it.
        with self.assertRaises(exceptions.PermissionDenied):
            bf.sign(user=None)

    def test_save_no_perm(self):
        u = fixtures.get_user(username="NoCanDoBoo")
        bf = self.get_form()
        self.assertTrue(bf.is_valid())
        with self.assertRaises(exceptions.PermissionDenied):
            bf.sign(user=None)  # no user
        with self.assertRaises(exceptions.PermissionDenied):
            bf.sign(user=u)  # unpermitted user

    def test_signoff_matches_form(self):
        valid_data = dict(signoff_id=consent_signoff.id, signed_off=['on'])
        invalid_data = dict(signoff_id='test_app.accept', signed_off=['on'])
        s = consent_signoff.get()
        valid_form = s.forms.get_signoff_form(valid_data)
        invalid_form = s.forms.get_signoff_form(invalid_data)
        self.assertTrue(valid_form.is_valid())
        self.assertFalse(invalid_form.is_valid())
        self.assertTrue(isinstance(s, valid_form.signoff_type))
        self.assertFalse(isinstance(signoffs.accept_signoff.get(), invalid_form.signoff_type)) # check form doesn't get signoff_type from signoff_id


class SignoffFormWithRelationTests(TestCase):
    def get_form(self, **kwargs):
        data = dict(signed_off="True", signoff_id=signoffs.report_signoff.id, **kwargs)
        return ReportSignoffForm(data=data)

    def test_save_with_relation(self):
        u = fixtures.get_user(perms=("can_review",))
        r = models.Report.objects.create(contents="Awesome report contents.")
        bf = self.get_form(report=r)
        self.assertTrue(bf.is_valid())
        v = bf.sign(user=u)
        signet = models.ReportSignet.objects.select_related("report").get(
            pk=v.pk
        )
        self.assertEqual(v.report, r)
        report = models.Report.objects.prefetch_related("signatories").get(pk=r.pk)
        self.assertEqual(report.signatories.count(), 1)
        self.assertEqual(report.signatories.first(), signet)
