"""
    Objects that know how to render an Approval Process into HTML
"""
from django.template.loader import render_to_string

from signoffs.core import utils

from . import helpers


class ApprovalProcessInstanceRenderer:
    """Renderer for an ApprovalProcess instance"""

    process_template = "signoffs/process/approval_process.html"

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

    def __init__(self, approval_process, process_template=None, approval_context=None):
        """A renderer instance for given approval_type, optionally override class templates"""
        self.process = approval_process
        self.process_template = process_template or self.process_template
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
        return render_to_string(
            self.process_template,
            helpers.resolve_dicts(
                defaults=self.approval_context,
                overrides=context,
                process=self.process,
                request_user=request_user,
                **kwargs,
            ),
        )


class ApprovalProcessRenderer(utils.service(ApprovalProcessInstanceRenderer)):
    """
    A descriptor class that "injects" a `ApprovalProcessInstanceRenderer` instance into a ApprovalProceess instance.

    To inject custom rendering services:
      - provide a custom service_class:  `render=ApprovalProcessRenderer(service_class=MyInstanceRenderer)`
      - OR specialize class attributes:
        `MyRenderer = utils.service(ApprovalProcessInstanceRenderer, process_template='my.tmpl.html')`
      - OR both... `MyRenderer = utils.service(MyInstanceRenderer)`
    """
