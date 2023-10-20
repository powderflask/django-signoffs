"""
App-dependent tests for signoff models
"""
from django.test import TestCase

from signoffs.core.tests import fixtures
from signoffs.signoffs import SignoffLogic
from tests.test_app import models, signoffs


class SignoffTests(TestCase):
    def test_default_sigil(self):
        u = fixtures.get_user()
        o = models.Signet(signoff_id="test_app.agree", user=u)
        o.save()
        self.assertEqual(o.sigil, u.get_full_name())

    def test_custom_sigil(self):
        u = fixtures.get_user()
        o = models.Signet(signoff_id="test_app.agree", user=u, sigil="Bugs Bunny")
        o.save()
        self.assertEqual(o.sigil, "Bugs Bunny")


class SignoffTypePermissionTests(TestCase):
    def test_can_sign_no_perm(self):
        s = signoffs.agree_signoff
        u = fixtures.get_user()
        self.assertTrue(s.is_permitted_signer(u))

    def test_can_sign_perm(self):
        perm = fixtures.get_perm("can_sign")
        s = signoffs.agree_signoff
        u = fixtures.get_user(perms=(perm,))
        self.assertTrue(s.is_permitted_signer(u))

    def test_cant_sign_without_permission(self):
        perm = fixtures.get_perm("no_signie")
        s = signoffs.TestSignoff.register(
            id="test3.signoff", logic=SignoffLogic(perm="auth.can_sign")
        )
        u = fixtures.get_user(perms=(perm,))
        self.assertFalse(s.is_permitted_signer(u))

    def test_can_revoke_no_perm(self):
        s = signoffs.TestSignoff.register(
            id="test4.signoff", logic=SignoffLogic(perm=None)
        )
        u = fixtures.get_user()
        self.assertTrue(s.is_permitted_revoker(u))

    def test_can_revoke_with_perm(self):
        perm = fixtures.get_perm("can_sign")
        revoke = fixtures.get_perm("can_revoke")
        s = signoffs.TestSignoff.register(
            id="test5.signoff", logic=SignoffLogic(perm="auth.can_sign")
        )
        u = fixtures.get_user(perms=(perm, revoke))
        self.assertTrue(s.is_permitted_revoker(u))
        s2 = signoffs.TestSignoff.register(
            id="test5.signoff2",
            logic=SignoffLogic(perm="auth.can_sign", revoke_perm="auth.can_revoke"),
        )
        self.assertTrue(s2.is_permitted_revoker(u))

    def test_cant_revoke_without_permission(self):
        not_perm = fixtures.get_perm("no_signie")
        s = signoffs.TestSignoff.register(
            id="test6.signoff", logic=SignoffLogic(perm="auth.can_sign")
        )
        u = fixtures.get_user(perms=(not_perm,))
        self.assertFalse(s.is_permitted_revoker(u))
        perm = fixtures.get_perm("can_sign")
        u2 = fixtures.get_user(
            perms=(
                not_perm,
                perm,
            )
        )
        self.assertTrue(s.is_permitted_revoker(u2))
        s2 = signoffs.TestSignoff.register(
            id="test6.signoff2",
            logic=SignoffLogic(perm="auth.can_sign", revoke_perm="auth.can_revoke"),
        )
        self.assertFalse(s2.is_permitted_revoker(u2))


class SignoffPermissionTests(TestCase):
    def test_can_sign_no_perm(self):
        u = fixtures.get_user()
        o = models.Signet(signoff_id="test_app.agree", user=u)
        self.assertTrue(o.can_save())

    def test_can_sign_perm(self):
        perm = fixtures.get_perm("can_sign")
        u = fixtures.get_user(perms=(perm,))
        o = models.Signet(signoff_id="test_app.consent", user=u)
        self.assertTrue(o.can_save())

    def test_cant_sign_without_permission(self):
        perm = fixtures.get_perm("no_signie")
        u = fixtures.get_user(perms=(perm,))
        signoff = signoffs.consent_signoff(user=u)
        self.assertFalse(signoff.can_save())

    def test_can_revoke_no_perm(self):
        u = fixtures.get_user()
        signoff = signoffs.agree_signoff(user=u)
        self.assertTrue(signoff.can_save())

    def test_can_revoke_with_perm(self):
        u = fixtures.get_user(perms=("can_sign", "can_revoke", "can_accept"))
        signoff = signoffs.consent_signoff(user=u).save()
        self.assertTrue(signoff.can_revoke(u))
        signoff2 = signoffs.agree_signoff(user=u).save()
        self.assertTrue(signoff2.can_revoke(u))

    def test_cant_revoke_without_permission(self):
        u = fixtures.get_user(perms=("no_signie",))
        signoff = signoffs.consent_signoff(user=u)
        self.assertFalse(signoff.can_revoke(u))
        perm = fixtures.get_perm("can_sign")
        u2 = fixtures.get_user(
            perms=(
                "no_signie",
                perm,
            )
        )
        signoff2 = signoffs.consent_signoff(user=u2)
        self.assertTrue(signoff2.can_save())
        self.assertFalse(signoff2.can_revoke(u2))


class SignoffRevokeTests(TestCase):
    def test_revoke_no_model(self):
        u = fixtures.get_user()
        signoff = signoffs.agree_signoff(user=u)
        signoff.save()
        signoff.revoke(u, reason="why not")
        self.assertEqual(models.Signet.all_signets.count(), 0)

    def test_revoke_with_model(self):
        perm = fixtures.get_perm("can_review")
        u = fixtures.get_user(perms=(perm,))
        r = models.Report.objects.create(contents="Awesomeness in textual form.")
        signoff = r.signoffs.create(user=u)
        signoff.revoke(u, reason="why not")
        self.assertEqual(models.ReportSignet.all_signets.count(), 1)
        self.assertEqual(models.ReportSignet.objects.count(), 0)
        self.assertEqual(models.RevokeReportSignet.objects.count(), 1)
        revoked = models.RevokeReportSignet.objects.select_related("signet").get(
            signet=signoff.signet
        )
        self.assertEqual(revoked.signet, signoff.signet)


class SignoffRelationsTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        perm = fixtures.get_perm("can_review")
        u = fixtures.get_user(perms=(perm,))
        r = models.Report.objects.create(contents="Awesomeness in textual form.")
        so = r.signoffs.create(user=u)
        so2 = r.signoffs.create(user=u)
        cls.signets = [so.signet, so2.signet]
        cls.u = u
        cls.r = r

    def test_signet_set(self):
        self.assertEqual(self.r.signatories.all().count(), len(self.signets))
        self.assertQuerysetEqual(self.r.signatories.order_by("pk"), self.signets)

    def test_signoff_set(self):
        self.assertEqual(self.r.signoffs.count(), len(self.signets))
        self.assertSetEqual(
            {so.signet for so in self.r.signoffs.all()}, set(self.signets)
        )

    def test_signet_set_revoke(self):
        signoff = self.signets[0].signoff
        signoff.revoke(self.u, reason="why not")
        self.assertEqual(self.r.signatories.all().count(), len(self.signets) - 1)
        self.assertEqual(self.r.signatories.all().first(), self.signets[1])
        # Check the revoked instance
        self.assertEqual(signoff.signet.revoked.user, self.u)
        self.assertEqual(signoff.signet.revoked.signet, signoff.signet)
        # but the signet is still there, just not visible b/c it's been revoked.
        self.assertEqual(self.r.signatories(manager="revoked_signets").count(), 1)
        self.assertEqual(
            models.ReportSignet.all_signets.filter(report=self.r).count(),
            len(self.signets),
        )

    def test_revoked_signoff_set(self):
        n_revoked = 3
        for _ in range(n_revoked):
            so = self.r.signoffs.create(self.u)
            so.revoke(self.u, reason="just because")
        self.assertEqual(self.r.signoffs.count(), len(self.signets))
        revoked = self.r.signoffs.revoked()
        self.assertEqual(len(revoked), n_revoked)
        self.assertTrue(all(signet.is_signed() for signet in revoked))
        self.assertTrue(all(signet.is_revoked() for signet in revoked))
        self.assertTrue(all(signet.revoked.user == self.u for signet in revoked))
