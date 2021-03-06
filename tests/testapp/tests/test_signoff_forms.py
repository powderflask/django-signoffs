"""
App-dependent tests for signoff forms - requires models that can be saved, etc.
"""
from django.core import exceptions
from django.test import TestCase
from signoffs.forms import signoff_form_factory
from signoffs.core.tests import fixtures

from testapp import models, signoffs

consent_signoff = signoffs.consent_signoff
SignoffForm = signoff_form_factory(signoff_type=consent_signoff)

ReportSignoffForm = signoff_form_factory(signoff_type=signoffs.report_signoff)


class SignoffFormWithUserTests(TestCase):
    def get_form(self, data=None, **kwargs):
        data = data or dict(
            signoff='True',
            signoff_id=consent_signoff.id
        )
        return SignoffForm(data=data, **kwargs)

    def test_save(self):
        u = fixtures.get_user(perms=('can_sign',))
        bf = self.get_form(user=u)
        v = bf.save()
        self.assertTrue(v.is_signed)
        self.assertEqual(v.id, consent_signoff.id)
        self.assertEqual(v.signet.user, u)
        self.assertEqual(v.signet.sigil, u.get_full_name())

    def test_invalid_save(self):
        u = fixtures.get_user(username='NoCanDoBoo')
        bf = self.get_form(user=u)
        self.assertFalse(bf.is_valid())
        with self.assertRaises(ValueError):
            bf.save()

    def test_save_no_perm(self):
        u = fixtures.get_user(username='NoCanDoBoo')
        bf = self.get_form()
        self.assertTrue(bf.is_valid())
        with self.assertRaises(exceptions.PermissionDenied):
            bf.save()  # no user
        with self.assertRaises(exceptions.PermissionDenied):
            bf.save(user=u)  # unpermitted user


class SignoffFormWithRelationTests(TestCase):
    def get_form(self, data=None, **kwargs):
        data = data or dict(
            signoff='True',
            signoff_id=signoffs.report_signoff.id
        )
        return ReportSignoffForm(data=data, **kwargs)

    def test_save_with_relation(self):
        u = fixtures.get_user(perms=('can_review',))
        r = models.Report.objects.create(contents="Awesome report contents.")
        bf = self.get_form()
        self.assertTrue(bf.is_valid())
        v = bf.save(user=u, report=r)
        signet = models.ReportSignet.objects.select_related('report').get(pk=v.signet.pk)
        self.assertEqual(v.signet.report, r)
        report = models.Report.objects.prefetch_related('signatories').get(pk=r.pk)
        self.assertEqual(report.signatories.count(), 1)
        self.assertEqual(report.signatories.first(), signet)
