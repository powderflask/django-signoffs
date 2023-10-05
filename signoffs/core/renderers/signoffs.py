"""
    Objects that know how to render other Signoffs / Signets into HTML
"""
from django.template.loader import render_to_string

from signoffs.core import utils

from . import helpers


class SignoffInstanceRenderer:
    """Renderer for a Signoff instance"""

    signet_template = "signoffs/signets/signet.html"
    signoff_form_template = "signoffs/signets/signoff_form.html"

    # default template context values - can be overridden with context variables or template tag kwargs,
    #    or override defaults by subclassing, or by passing overrides dict to init.
    signet_context = dict(
        show_revoke=True,
        timestamp_label="Date",
        with_signature_line=False,
        signature_line_label="Signature",
    )

    form_context = dict(
        show_form=True,
        help_text="Check box and Sign to add your consent.",
        submit_label="Sign",
        signoff_form=None,
        csrf_token=None,
    )

    pass_thru_context = (
        "request",
        "csrf_token",
        "request_user",
    )  # variables passed through to template from parent context

    def __init__(
        self,
        signoff_instance,
        signet_template=None,
        signet_context=None,
        signoff_form_template=None,
        form_context=None,
    ):
        """A renderer instance for given signoff_type, optionally override class templates"""
        self.signoff = signoff_instance
        self.signet_template = signet_template or self.signet_template
        # Force request into context so it is available from context being rendered in
        self.signet_context = {
            **self.signet_context,
            **(signet_context or {}),
            **{v: None for v in self.pass_thru_context},
        }
        # + for Signoff Form:
        self.signoff_form_template = signoff_form_template or self.signoff_form_template
        self.form_context = {
            **self.form_context,
            **(form_context or {}),
            **{v: None for v in self.pass_thru_context},
        }

    def __call__(self, request_user=None, context=None, **kwargs):
        """Return a string containing a rendered version of this signoff, optionally tailored for requesting user."""
        return (
            self.signet(request_user, context, **kwargs)
            if self.signoff.is_signed()
            else self.form(request_user, context, **kwargs)
        )

    def signet(self, request_user=None, context=None, **kwargs):
        """Return a string containing the rendered Signet for given user, if it is signed, empty string otherwise"""
        context = context or {}
        request_user = helpers.resolve_request_user(request_user, context, **kwargs)
        show_revoke = kwargs.pop(
            "show_revoke", self.signet_context.get("show_revoke", True)
        )
        signet_template = kwargs.pop("signet_template", self.signet_template)
        return (
            render_to_string(
                signet_template,
                helpers.resolve_dicts(
                    defaults=self.signet_context,
                    overrides=context,
                    signoff=self.signoff,
                    request_user=request_user,
                    is_revokable=show_revoke
                    and request_user
                    and self.signoff.can_revoke(request_user),
                    **kwargs,
                ),
            )
            if self.signoff.is_signed()
            else ""
        )

    def form(self, request_user=None, context=None, **kwargs):
        """Return a string containing the rendered Signet Form, if it can be signed, empty string otherwise"""
        context = context or {}
        request_user = helpers.resolve_request_user(request_user, context, **kwargs)
        show_form = kwargs.pop("show_form", self.form_context.get("show_form", True))
        form_template = kwargs.pop("signoff_form_template", self.signoff_form_template)
        return (
            render_to_string(
                form_template,
                self.resolve_form_context(
                    overrides=context,
                    signoff=self.signoff,
                    request_user=request_user,
                    is_signable=show_form
                    and request_user
                    and self.signoff.can_sign(request_user),
                    **kwargs,
                ),
            )
            if request_user and self.signoff.can_sign(request_user)
            else ""
        )

    def resolve_form_context(self, overrides, **kwargs):
        """return single context dictionary suitable for rendering signet form"""
        form_context = self.form_context.copy()
        default_label = form_context.pop("label", self.signoff.label)
        default_help_text = form_context.pop("help_text", None)
        form_class = self.signoff.forms.get_signoff_form_class(
            signoff_field_kwargs=dict(
                label=kwargs.get("label", default_label),
                help_text=kwargs.get("help_text", default_help_text),
            )
        )
        form_context.update(dict(signoff_form=form_class(instance=self.signoff)))
        form_context.update(
            helpers.filter_dict(overrides, self.form_context.keys())
        )  # overrides from context
        form_context.update(kwargs)  # kwargs override all
        return form_context


class SignoffRenderer(utils.service(SignoffInstanceRenderer)):
    """
    A descriptor class that "injects" a `SignoffInstanceRenderer` instance into a Signoff instance.

    To inject custom rendering services:
      - provide a custom service_class:  `render=SignoffRenderer(service_class=MyInstanceRenderer)`
      - OR specialize class attributes:
        `MyRenderer = utils.service(SignoffInstanceRenderer, signet_template='my.tmpl.html')`
      - OR both... `MyRenderer = utils.service(MyInstanceRenderer)`
    """
