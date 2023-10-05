""" Helpers: resolve 3 potential sources for context: defaults, context object, kwargs """


# Helper methods:


def resolve_request_user(request_user, context, **kwargs):
    """return user object either from request user or context.request.user or None"""
    # Only need the request.user, so don't require a request object, but often convenient to use one  ** sigh **
    request_user = request_user or kwargs.get(
        "request_user", context.get("request_user", None)
    )
    request = kwargs.get("request", context.get("request", None))
    return request_user or (request.user if request else None)


def filter_dict(d, keys):
    """Return copy of d filtered by keys"""
    d = d or {}
    return {k: d.get(k) for k in keys if k in d}


def resolve_dicts(defaults, overrides, **kwargs):
    """return a single dictionary, overriding matching keys from overrides and updating with kwargs"""
    context = defaults.copy()  # defaults: lowest precedence
    context.update(filter_dict(overrides, defaults.keys()))  # overrides
    context.update(kwargs)  # kwargs take precedence
    return context
