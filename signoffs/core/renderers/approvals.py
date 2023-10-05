"""
    Objects that know how to render Approvals / Stamps into HTML
"""
from django.template.loader import render_to_string

from signoffs.core import utils

from . import helpers


class ApprovalInstanceRenderer:
    """Renderer for a Approval instance"""

    approval_template = "signoffs/approvals/approval.html"

    # default template context values - can be overridden with context variables or template tag kwargs,
    #    or override defaults by subclassing, or by passing overrides dict to init.
    approval_context = dict(
        show_revoke=True,
        show_status_msg=True,
        render_signoff_forms=True,
    )

    pass_thru_context = (
        "request",
        "csrf_token",
        "request_user",
    )  # variables passed through to template from parent context

    def __init__(
        self, approval_instance, approval_template=None, approval_context=None
    ):
        """A renderer instance for given approval_type, optionally override class templates"""
        self.approval = approval_instance
        self.approval_template = approval_template or self.approval_template
        # Force request into context so it is available from context being rendered in
        self.approval_context = {
            **self.approval_context,
            **(approval_context or {}),
            **{v: None for v in self.pass_thru_context},
        }

    def __call__(self, request_user=None, context=None, **kwargs):
        """Return a string containing a rendered version of this approval, optionally tailored for requesting user."""
        context = context or {}
        request_user = helpers.resolve_request_user(request_user, context, **kwargs)
        show_revoke = kwargs.pop(
            "show_revoke", self.approval_context.get("show_revoke", True)
        )
        return render_to_string(
            self.approval_template,
            helpers.resolve_dicts(
                defaults=self.approval_context,
                overrides=context,
                approval=self.approval,
                request_user=request_user,
                is_revokable=show_revoke
                and request_user
                and self.approval.can_revoke(request_user),
                **kwargs,
            ),
        )


class ApprovalRenderer(utils.service(ApprovalInstanceRenderer)):
    """
    A descriptor class that "injects" a `ApprovalInstanceRenderer` instance into a Approval instance.

    To inject custom rendering services:
      - provide a custom service_class:  `render=ApprovalRenderer(service_class=MyInstanceRenderer)`
      - OR specialize class attributes:
        `MyRenderer = utils.service(ApprovalInstanceRenderer, approval_template='my.tmpl.html')`
      - OR both... `MyRenderer = utils.service(MyInstanceRenderer)`
    """
