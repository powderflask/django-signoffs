"""
Test App - tests for shortcuts
"""
from django.test import TestCase

from signoffs import shortcuts
from signoffs.core.tests import fixtures
from tests.test_app import models, signoffs


class ShortcutTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = fixtures.get_user()
        cls.signoff = signoffs.agree_signoff.create(cls.user)
        cls.approval = models.SimpleApproval.create()

    def test_get_signet_or_404(self):
        signet = shortcuts.get_signet_or_404(self.signoff.id, self.signoff.signet.pk)
        self.assertEqual(signet, self.signoff.signet)

    def test_get_signoff_or_404(self):
        so = shortcuts.get_signoff_or_404(self.signoff.id, self.signoff.signet.pk)
        self.assertEqual(so, self.signoff)

    def test_get_approval_stamp_or_404(self):
        stamp = shortcuts.get_approval_stamp_or_404(
            self.approval.id, self.approval.stamp.pk
        )
        self.assertEqual(stamp, self.approval.stamp)

    def test_get_approval_or_404(self):
        approval = shortcuts.get_approval_or_404(
            self.approval.id, self.approval.stamp.pk
        )
        self.assertEqual(approval, self.approval)
