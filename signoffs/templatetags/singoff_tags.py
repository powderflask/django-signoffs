"""
    Simplify rendering signoff objects in templates
"""
from django import template

register = template.Library()


@register.filter
def can_revoke(signoff_or_approval_instance, user):
    """ Returns True if the signoff_or_approval_instance can be revoked by the given user (in theory) """
    return signoff_or_approval_instance.can_revoke(user)


@register.simple_tag(takes_context=True)
def render_signoff(context, signoff_instance, action='__call__', **kwargs):
    """
    Render the signoff_instance using the given method (action) of its renderer.
    kwargs are passed to action method
    """
    method = getattr(signoff_instance.render, action, signoff_instance.render.__call__)
    return method(**kwargs, context=context)


@register.simple_tag(takes_context=True)
def render_approval(context, approval_instance, **kwargs):
    """
    Render the approval_instance.render.
    kwargs are passed to renderer
    """
    return approval_instance.render(**kwargs, context=context)
