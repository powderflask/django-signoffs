"""
    Objects that know how to render Approvals / Stamps into HTML
"""
from django.template.loader import render_to_string


class ApprovalInstanceRenderer:
    """ Renderer for a Approval instance """
    approval_template = 'signoffs/approvals/approval.html'

    # default template context values - can be overridden with kwargs or context entries
    # sub-classes can override these defaults, but each dict should define full-suite of variables, None for no default.
    approval_context = dict(
        show_revoke=True,
        show_status_msg=True,
    )

    def __init__(self, approval_instance, approval_template=None, approval_context=None):
        """ A renderer instance for given approval_type, optionally override class templates """
        self.approval = approval_instance
        self.approval_template = approval_template or self.approval_template
        self.approval_context = {**self.approval_context, **(approval_context or {})}

    def __call__(self, request_user=None, context=None, **kwargs):
        """ Return a string containing a rendered version of this approval, optionally tailored for requesting user. """
        request_user = self.resolve_request_user(request_user, context)
        show_revoke = kwargs.pop('show_revoke', self.approval_context.get('show_revoke', True))
        return render_to_string(self.approval_template, self.resolve_approval_context(
            context,
            approval=self.approval,
            is_revokable=show_revoke and request_user and self.approval.can_revoke(request_user),
            **kwargs
        ))

    # Helper methods: resolve 3 potential sources for approval context: defaults, context object, kwargs

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

    def resolve_approval_context(self, context, **kwargs):
        """ return single context dictionary suitable for rendering a Stamp of Approval """
        approval_context = self.approval_context.copy()   # defaults: lowest precedence
        approval_context.update(self.get_context_for(self.approval_context.keys(), context))  # overrides from context
        approval_context.update(kwargs)                 # kwargs take precedence
        return approval_context


class ApprovalRenderer:
    """ A descriptor that "injects" a ApprovalInstanceRenderer into a Approval instance. """

    instance_renderer = ApprovalInstanceRenderer

    def __init__(self, instance_renderer=None, **kwargs):
        """
        Inject an instance_renderer object into Approval instances
        kwargs are passed through to the instance_renderer constructor
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
            r = self.instance_renderer(approval_instance=instance, **self.instance_renderer_kwargs)
            setattr(instance, self.attr_name, r)
            return r
