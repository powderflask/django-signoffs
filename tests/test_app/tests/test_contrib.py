"""
App-independent tests for contrib models
"""
from django.test import TestCase

from signoffs import models, signoffs
from signoffs.core.tests import fixtures

simple = signoffs.SimpleSignoff.register(id="test.contrib.simple")
revokable = signoffs.RevokableSignoff.register(id="test.contrib.revokable")
irrevokable = signoffs.IrrevokableSignoff.register(id="test.contrib.irrevokable")


class ContribSignoffTypeTests(TestCase):
    def setUp(self):
        super().setUp()
        self.user = fixtures.get_user(
            username="anyone"
        )  # A user with no specific permissions

    def test_simple_signoff(self):
        signoff = simple()
        self.assertEqual(signoff.signet_model, models.Signet)
        self.assertIsNone(signoff.revoke_model)
        self.assertTrue(signoff.is_permitted_signer(self.user))
        self.assertTrue(signoff.is_permitted_revoker(self.user))
        signet = signoff.signet
        self.assertEqual(signet.signoff_type, type(signoff))
        self.assertEqual(signet.signoff, signoff)
        # save and revoke
        signoff = signoff.sign(user=self.user)
        self.assertTrue(signoff.can_revoke(self.user))

    def test_revokable_signoff(self):
        signoff = revokable()
        self.assertEqual(signoff.signet_model, models.Signet)
        self.assertEqual(signoff.revoke_model, models.RevokedSignet)
        self.assertTrue(signoff.is_permitted_signer(self.user))
        self.assertTrue(signoff.is_permitted_revoker(self.user))
        signet = signoff.signet
        self.assertEqual(signet.signoff_type, type(signoff))
        self.assertEqual(signet.signoff, signoff)
        # save and revoke
        signoff = signoff.sign(user=self.user)
        self.assertTrue(signoff.can_revoke(self.user))

    def test_irrevokable_signoff(self):
        signoff = irrevokable()
        self.assertEqual(signoff.signet_model, models.Signet)
        self.assertIsNone(signoff.revoke_model)
        self.assertTrue(signoff.is_permitted_signer(self.user))
        self.assertFalse(signoff.is_permitted_revoker(self.user))
        signet = signoff.signet
        self.assertEqual(signet.signoff_type, type(signoff))
        self.assertEqual(signet.signoff, signoff)
        # save and revoke
        signoff = signoff.sign(user=self.user)
        self.assertFalse(signoff.can_revoke(self.user))
