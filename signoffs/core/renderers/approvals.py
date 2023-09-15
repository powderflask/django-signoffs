"""
    Objects that know how to render Approvals / Stamps into HTML
"""
from django.template.loader import render_to_string

from signoffs.core import utils


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
    )  # variables passed through to tempalate from parent context

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
        request_user = self.resolve_request_user(request_user, context, **kwargs)
        show_revoke = kwargs.pop(
            "show_revoke", self.approval_context.get("show_revoke", True)
        )
        return render_to_string(
            self.approval_template,
            self.resolve_approval_context(
                context,
                approval=self.approval,
                request_user=request_user,
                is_revokable=show_revoke
                and request_user
                and self.approval.can_revoke(request_user),
                **kwargs,
            ),
        )

    # Helper methods: resolve 3 potential sources for approval context: defaults, context object, kwargs

    @staticmethod
    def resolve_request_user(request_user, context, **kwargs):
        """return user object either from request user or context.request.user or None"""
        # Only need the request.user, so don't require a request object, but often convenient to use one  ** sigh **
        request_user = request_user or kwargs.get(
            "request_user", context.get("request_user", None)
        )
        request = kwargs.get("request", context.get("request", None))
        return request_user or (request.user if request else None)

    @staticmethod
    def get_context_for(keys, context):
        """Return a dict of context values for just the set of keys"""
        context = context or {}
        return {k: context.get(k) for k in keys if k in context}

    def resolve_approval_context(self, context, **kwargs):
        """return single context dictionary suitable for rendering a Stamp of Approval"""
        approval_context = self.approval_context.copy()  # defaults: lowest precedence
        approval_context.update(
            self.get_context_for(self.approval_context.keys(), context)
        )  # overrides from context
        approval_context.update(kwargs)  # kwargs take precedence
        return approval_context


class ApprovalRenderer(utils.service(ApprovalInstanceRenderer)):
    """
    A descriptor class that "injects" a `ApprovalInstanceRenderer` instance into a Approval instance.

    To inject custom rendering services:
      - provide a custom service_class:  `render=ApprovalRenderer(service_class=MyInstanceRenderer)`
      - OR specialize class attributes:
        `MyRenderer = utils.service(ApprovalInstanceRenderer, signet_template='my.tmpl.html')`
      - OR both... `MyRenderer = utils.service(MyInstanceRenderer)`
    """
