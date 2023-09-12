"""
Tests for signoff Types registries
"""
from django.test import SimpleTestCase

from signoffs.registry import signoffs
from tests.test_app import models


class TestSignoffsRegistry(SimpleTestCase):
    def test_signoff_registered(self):
        s = signoffs.get("test_app.agree")
        self.assertEqual(s().signet_model, models.Signet)
        s = signoffs.get("test_app.accept")
        self.assertEqual(s().signet_model, models.ReportSignet)

    def test_signoff_type(self):
        o = models.Signet(signoff_id="test_app.agree")
        self.assertEqual(o.signoff_type, signoffs.get("test_app.agree"))
