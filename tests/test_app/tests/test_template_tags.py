"""
App-dependent tests for signoff template tags
"""
from django.template import Context, Template
from django.test import TestCase

from signoffs.approvals import (
    ApprovalInstanceRenderer,
    ApprovalLogic,
    ApprovalSignoff,
    SimpleApproval,
    signing_order,
)
from signoffs.core.renderers import helpers
from signoffs.core.tests import fixtures
from signoffs.signoffs import SignoffInstanceRenderer, SignoffLogic, utils
from tests.test_app import signoffs


class DummySignoffInstanceRenderer(SignoffInstanceRenderer):
    """Dummy renderer with easy-to-test presentation logic"""

    def signet(self, request_user=None, context=None, **kwargs):
        return (
            f"Signed Signet for {self.signoff.id}" if self.signoff.is_signed() else ""
        )

    def form(self, request_user=None, context=None, **kwargs):
        request_user = helpers.resolve_request_user(request_user, context, **kwargs)
        return (
            f"Signoff Form for {self.signoff.id}"
            if request_user and self.signoff.can_sign(request_user)
            else ""
        )


DummySignoffRenderer = utils.service(DummySignoffInstanceRenderer)


class RenderSignoffTagTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        perm = fixtures.get_perm("can_sign")
        cls.user = fixtures.get_user(perms=(perm,))
        fixtures.get_perm("can_revoke")
        cls.signoff_type = signoffs.TestSignoff.register(
            id="test.signoff",
            logic=SignoffLogic(perm="auth.can_sign", revoke_perm="auth.can_revoke"),
            render=DummySignoffRenderer(),
        )

    def signed_signoff(self):
        """Return a signed signoff instance"""
        signoff = self.signoff_type()
        signoff.sign(user=self.user)
        return signoff

    def render_template(self, template, **context):
        """Render test template with context overrides"""
        context = context or {}
        defaults = dict(
            signoff=self.signoff_type(),
            request_user=self.user,
        )
        return template.render(Context({**defaults, **context}))

    def test_render_signoff_form_default(self):
        """Unsigned signoff renders form by default"""
        out = self.render_template(
            Template("{% load signoff_tags %}{% render_signoff signoff %}")
        )
        self.assertEqual(out, f"Signoff Form for {self.signoff_type.id}")

    def test_render_signoff_form_explicit(self):
        out = self.render_template(
            Template(
                "{% load signoff_tags %}{% render_signoff signoff action='form' %}"
            )
        )
        self.assertEqual(out, f"Signoff Form for {self.signoff_type.id}")

    def test_render_signoff_signet_unsigned(self):
        """Test rendering an unsigned Signet"""
        out = self.render_template(
            Template(
                "{% load signoff_tags %}{% render_signoff signoff action='signet' %}"
            )
        )
        self.assertEqual(out, "")

    def test_render_signoff_signet_default(self):
        """Signed signoff renders signet by default"""
        signoff = self.signed_signoff()
        out = self.render_template(
            Template("{% load signoff_tags %}{% render_signoff signoff %}"),
            signoff=signoff,
        )
        self.assertEqual(out, f"Signed Signet for {signoff.id}")

    def test_render_signoff_signet_explicit(self):
        signoff = self.signed_signoff()
        out = self.render_template(
            Template(
                "{% load signoff_tags %}{% render_signoff signoff action='signet' %}"
            ),
            signoff=signoff,
        )
        self.assertEqual(out, f"Signed Signet for {signoff.id}")

    def test_render_signoff_form_signed(self):
        """Test rendering form for a signed Signet"""
        signoff = self.signed_signoff()
        out = self.render_template(
            Template(
                "{% load signoff_tags %}{% render_signoff signoff action='form' %}"
            ),
            signoff=signoff,
        )
        self.assertEqual(out, "")

    def test_render_signoff_signet_custom_template(self):
        """For fine control over signet rendering - pass template name in tag"""
        signoff = signoffs.agree_signoff()
        signoff.sign(user=self.user)
        out = self.render_template(
            Template(
                "{% load signoff_tags %}"
                "{% render_signoff signoff signet_template='testapp/signets/custom_signet.html' %}"
            ),
            signoff=signoff,
        )
        self.assertEqual(out.strip(), f"Signoff signed by {self.user.username}")

    def test_render_signoff_form_custom_template(self):
        """For fine control over signoff form rendering - pass template name in tag"""
        signoff = signoffs.agree_signoff()
        out = self.render_template(
            Template(
                "{% load signoff_tags %}"
                "{% render_signoff signoff signoff_form_template='testapp/signets/custom_signet.html' %}"
            ),
            signoff=signoff,
        )
        self.assertEqual(out.strip(), f"Signoff { signoff.id } Form")

    def test_can_revoke_false(self):
        signoff = self.signed_signoff()
        out = self.render_template(
            Template("{% load signoff_tags %}{{ signoff|can_revoke:request_user }}"),
            signoff=signoff,
        )
        self.assertEqual(out, "False")

    def test_can_revoke_true(self):
        revoke = fixtures.get_perm("can_revoke")
        user = fixtures.get_user(perms=(revoke,))
        signoff = self.signed_signoff()
        out = self.render_template(
            Template("{% load signoff_tags %}{{ signoff|can_revoke:request_user }}"),
            signoff=signoff,
            request_user=user,
        )
        self.assertEqual(out, "True")


class DummyApprovalInstanceRenderer(ApprovalInstanceRenderer):
    """Dummy renderer with easy-to-test presentation logic"""

    def __call__(self, request_user=None, context=None, **kwargs):
        """Return a string containing a rendered version of this approval, optionally tailored for requesting user."""
        return (
            f"Approval {self.approval.id} Approved with {self.approval.signoffs.count()} signoffs"
            if self.approval.is_approved()
            else f"Approval {self.approval.id} with {self.approval.signoffs.count()} signoffs"
        )


DummyApprovalRenderer = utils.service(DummyApprovalInstanceRenderer)


class RenderApprovalTagTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = fixtures.get_user()
        cls.signoff_type = signoff_type = ApprovalSignoff.register(
            id="test.approval.signoff"
        )
        _ = fixtures.get_perm("can_revoke")
        cls.approval_type = SimpleApproval.register(
            id="test.approval",
            logic=ApprovalLogic(revoke_perm="auth.can_revoke"),
            render=DummyApprovalRenderer(),
            signing_order=signing_order.SigningOrder(
                signing_order.OneOrMore(signoff_type)
            ),
        )

    def setUp(self):
        super().setUp()
        self.approval = self.approval_type.create()

    def signed_signoff(self):
        """Return a signed signoff instance on the approval"""
        signoff = self.approval.get_next_signoff(for_user=self.user)
        signoff.sign(user=self.user)
        return signoff

    def render_template(self, template, **context):
        """Render test template with context overrides"""
        context = context or {}
        defaults = dict(
            approval=self.approval,
            request_user=self.user,
        )
        return template.render(Context({**defaults, **context}))

    def test_render_approval_empty(self):
        """Unsigned signoff renders form by default"""
        out = self.render_template(
            Template("{% load signoff_tags %}{% render_approval approval %}")
        )
        self.assertEqual(out, f"Approval {self.approval_type.id} with 0 signoffs")

    def test_render_approval_signed(self):
        """Unsigned signoff renders form by default"""
        for i in range(1, 4):
            self.signed_signoff()
            out = self.render_template(
                Template("{% load signoff_tags %}{% render_approval approval %}")
            )
            self.assertEqual(out, f"Approval {self.approval_type.id} with {i} signoffs")

    def test_render_approval_approved(self):
        """Unsigned signoff renders form by default"""
        self.signed_signoff()
        self.approval.approve()
        out = self.render_template(
            Template("{% load signoff_tags %}{% render_approval approval %}")
        )
        self.assertEqual(
            out, f"Approval {self.approval_type.id} Approved with 1 signoffs"
        )

    def test_can_revoke_false(self):
        self.signed_signoff()
        self.approval.approve()
        out = self.render_template(
            Template("{% load signoff_tags %}{{ approval|can_revoke:request_user }}"),
        )
        self.assertEqual(out, "False")

    def test_can_revoke_true(self):
        revoke = fixtures.get_perm("can_revoke")
        user = fixtures.get_user(perms=(revoke,))
        self.signed_signoff()
        self.approval.approve()
        out = self.render_template(
            Template("{% load signoff_tags %}{{ approval|can_revoke:request_user }}"),
            request_user=user,
        )
        self.assertEqual(out, "True")

    def test_next_signoff_for_user(self):
        out = self.render_template(
            Template(
                "{% load signoff_tags %}{{ approval|next_signoff_for_user:request_user }}"
            ),
        )
        self.assertEqual(out, "test.approval.signoff (unsigned)")

    def test_next_signoffs_for_user(self):
        out = self.render_template(
            Template(
                "{% load signoff_tags %}{{ approval|next_signoffs_for_user:request_user|length }}"
            ),
        )
        self.assertEqual(out, "1")

    def test_next_signoff_for_user_none(self):
        self.signed_signoff()
        self.approval.approve()
        out = self.render_template(
            Template(
                "{% load signoff_tags %}{{ approval|next_signoff_for_user:request_user }}"
            ),
        )
        self.assertEqual(out, "None")

    def test_next_signoffs_for_user_none(self):
        self.signed_signoff()
        self.approval.approve()
        out = self.render_template(
            Template(
                "{% load signoff_tags %}{{ approval|next_signoffs_for_user:request_user|length }}"
            ),
        )
        self.assertEqual(out, "0")
