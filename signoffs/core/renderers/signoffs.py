"""
    Objects that know how to render other Signoffs / Signets into HTML
"""
from django.template.loader import render_to_string


class SignoffInstanceRenderer:
    """ Renderer for a Signoff instance """
    signet_template = 'signoffs/signets/signet.html'
    signoff_form_template = 'signoffs/signets/signoff_form.html'

    # default template context values - can be overridden with kwargs or context entries
    # subclasses can override these defaults, but each dict should define full-suite of variables, None for no default.
    signet_context = dict(
        show_revoke=True,
        timestamp_label='Date',
        with_signature_line=False,
        signature_line_label='Signature',
    )

    form_context = dict(
        help_text='Check box and Sign to add your consent.',
        submit_label='Sign',
        signoff_form=None,
        csrf_token=None,
    )

    pass_thru_context = ('request', 'csrf_token', ) # variables passed through to tempalate from parent context, if avail.

    def __init__(self, signoff_instance,
                 signet_template=None, signet_context=None,
                 signoff_form_template=None, form_context=None):
        """ A renderer instance for given signoff_type, optionally override class templates """
        self.signoff = signoff_instance
        self.signet_template = signet_template or self.signet_template
        # Force request into context so it is available from context being rendered in
        self.signet_context = {
            **self.signet_context,
            **(signet_context or {}),
            **{v: None for v in self.pass_thru_context}
        }
        # + for Signoff Form:
        self.signoff_form_template = signoff_form_template or self.signoff_form_template
        self.form_context = {
            **self.form_context,
            **(form_context or {}),
            **{v: None for v in self.pass_thru_context}
        }

    def __call__(self, request_user=None, context=None, **kwargs):
        """ Return a string containing a rendered version of this signoff, optionally tailored for requesting user. """
        return self.signet(request_user, context, **kwargs) \
            if self.signoff.is_signed() else self.form(request_user, context, **kwargs)

    def signet(self, request_user=None, context=None, **kwargs):
        """ Return a string containing the rendered Signet for given user, if it is signed, empty string otherwise """
        request_user = self.resolve_request_user(request_user, context)
        show_revoke = kwargs.pop('show_revoke', self.signet_context.get('show_revoke', True))
        return render_to_string(self.signet_template, self.resolve_signet_context(
            context,
            signoff=self.signoff,
            is_revokable=show_revoke and request_user and self.signoff.can_revoke(request_user),
            **kwargs
        )) if self.signoff.is_signed() else ''

    def form(self, request_user=None, context=None, **kwargs):
        """ Return a string containing the rendered Signet Form, if it is not signed, empty string otherwise """
        request_user = self.resolve_request_user(request_user, context)
        return render_to_string(self.signoff_form_template, self.resolve_form_context(
            context,
            signoff=self.signoff,
            **kwargs
        )) if not request_user or self.signoff.can_sign(request_user) else ''

    # Helper methods: resolve 3 potential sources for signoff context: defaults, context object, kwargs

    @staticmethod
    def resolve_request_user(request_user, context):
        """ return user object either from request user or context.request.user or None """
        context = context or {}
        request = context.get('request', None)
        return request_user or request.user if request else None

    @staticmethod
    def get_context_for(keys, context):
        """ return a dict of context values for just the set of keys """
        context = context or {}
        return {k: context.get(k) for k in keys if k in context}

    def resolve_signet_context(self, context, **kwargs):
        """ return single context dictionary suitable for rendering signet """
        signet_context = self.signet_context.copy()   # defaults: lowest precedence
        signet_context.update(self.get_context_for(self.signet_context.keys(), context))  # overrides from context
        signet_context.update(kwargs)                 # kwargs take precedence
        return signet_context

    def resolve_form_context(self, context, **kwargs):
        """ return single context dictionary suitable for rendering signet form """
        form_context = self.form_context.copy()
        default_label = form_context.pop('label', None)
        default_help_text = form_context.pop('help_text', None)
        form_class = self.signoff.get_form_class(
            signoff_field_kwargs=dict(
                label=kwargs.get('label', default_label),
                help_text=kwargs.get('help_text', default_help_text),
            )
        )
        form_context.update(dict(signoff_form=form_class()))
        form_context.update(self.get_context_for(self.form_context.keys(), context))  # overrides from context
        form_context.update(kwargs)  # kwargs override all
        return form_context


class SignoffRenderer:
    """ A descriptor that "injects" a SignoffInstanceRenderer into a Signoff instance. """

    instance_renderer = SignoffInstanceRenderer

    def __init__(self, instance_renderer=None, **kwargs):
        """
        Inject an instance_renderer object into Signoff instances
        kwargs are passed through to instance_renderer constructor
        """
        self.instance_renderer = instance_renderer or self.instance_renderer
        self.instance_renderer_kwargs = kwargs
        self.attr_name = ''   # set by __set_name__

    def __set_name__(self, owner, name):
        self.attr_name = name

    def __get__(self, instance, owner):
        if instance is None:
            return self.instance_renderer
        else:
            r = self.instance_renderer(signoff_instance=instance, **self.instance_renderer_kwargs)
            setattr(instance, self.attr_name, r)
            return r
