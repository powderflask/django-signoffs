"""
    Simplify rendering signoff objects in templates
"""
from django import template

register = template.Library()


@register.filter
def can_revoke(signoff_or_approval_instance, user):
    """Returns True if the signoff_or_approval_instance can be revoked by the given user (in theory)"""
    return signoff_or_approval_instance.can_revoke(user)


@register.filter
def next_signoffs_for_user(approval_instance, user):
    """Returns list of next signoffs available for signing by user"""
    return approval_instance.next_signoffs(for_user=user)


@register.filter
def next_signoff_for_user(approval_instance, user):
    """Returns the next signoffs avaialble for signing by user"""
    return approval_instance.get_next_signoff(for_user=user)


@register.simple_tag(takes_context=True)
def render_signoff(context, signoff_instance, action="__call__", **kwargs):
    """
    Render the signoff_instance using the given method (action) of its renderer.

    kwargs are passed to action method
    """
    method = getattr(signoff_instance.render, action, signoff_instance.render.__call__)
    return method(**kwargs, context=context)


def _get_request_user(context, **kwargs):
    """return user object from context or kwargs, or None"""
    # Only need the request.user, so don't require a request object, but often convenient to use one  ** sigh **
    request_user = kwargs.get(
        "request_user", context.get("request_user", context.get("user", None))
    )
    request = kwargs.get("request", context.get("request", None))
    return request_user or (request.user if request else None)


@register.simple_tag(takes_context=True)
def render_approval_signoff(
    context, approval, signoff_instance, action="__call__", **kwargs
):
    """
    Render the signoff_instance within context of approval using the given method (action) of its renderer.

    kwargs are passed to action method
    """
    user = _get_request_user(context, **kwargs)
    if not approval.can_revoke_signoff(signoff_instance, user):
        kwargs["show_revoke"] = False
    if not approval.can_sign(user, signoff_instance):
        kwargs["show_form"] = False
    return render_signoff(context, signoff_instance, action=action, **kwargs)


@register.simple_tag(takes_context=True)
def render_approval(context, approval_instance, **kwargs):
    """
    Render the approval_instance

    kwargs are passed to renderer.render method
    """
    return approval_instance.render(**kwargs, context=context)


@register.simple_tag(takes_context=True)
def render_process_approval(context, approval_process, approval_instance, **kwargs):
    """
    Render the approval_instance within context of approval_process.

    kwargs are passed to render method
    """
    if not approval_process.is_revokable_approval(approval_instance):
        kwargs["show_revoke"] = False
    if not approval_process.is_signable_approval(approval_instance):
        kwargs["render_signoff_forms"] = False
    return approval_instance.render(**kwargs, context=context)


@register.simple_tag(takes_context=True)
def render_approval_process(context, approval_process, **kwargs):
    """
    Render the approval_process

    kwargs are passed to render method
    """
    return approval_process.render(**kwargs, context=context)
