"""
    All Behavioural "Types" are loaded in a global registry to they can be accessed anywhere.
"""

from django.core.exceptions import ImproperlyConfigured
from persisting_theory import Registry


class ObjectRegistry(Registry):
    """Generic base class for efficiently registering a bunch of objects that have an id attribute to use as name"""

    object_type = object
    name_attr = "id"

    def validate(self, data):
        """Return True iff the data can is a unique, vaild candidate for storage in this registry"""
        class_validator = getattr(data, "validate", lambda: True)
        return (
            issubclass(data, self.object_type)
            and not getattr(data, self.name_attr) in self
            and class_validator()
        )

    def prepare_name(self, data, name=None):
        """Name (key) in registry will ordinarily be data.id, but can be overridden"""
        return name or getattr(data, self.name_attr)

    def register(self, *data, name=None, **kwargs):
        """Allow for multiple objects to be registered at once, name is ignored, obj.name_attr used instead"""
        for obj in data:
            super().register(obj, **kwargs)


class SignoffTypes(ObjectRegistry):
    """Keep a reference to all Signoff Types"""

    look_into = "signoffs"

    @property
    def object_type(self):
        """defer dependency to prevent cyclical imports"""
        import signoffs.core.signoffs

        return signoffs.core.signoffs.AbstractSignoff


signoffs = SignoffTypes()
"""Singleton - the Signoff Types registry. `(see persisting_theory.Registry)`"""


def get_signoff_type(signoff_id_or_type):
    """
    Return a registered Signoff Type or raise ImproperlyConfigured if no such type was registered.
    Convenience function accepts either a Type or an id, and checks for existence.
    """
    signoff_type = (
        signoffs.get(signoff_id_or_type)
        if isinstance(signoff_id_or_type, str)
        else signoff_id_or_type
    )
    if signoff_type is None:
        raise ImproperlyConfigured(
            f"Signoff Type {signoff_type} must be registered before it can be used."
        )
    return signoff_type


class ApprovalTypes(ObjectRegistry):
    """Keep a reference to all Approval Types"""

    look_into = "approvals"

    @property
    def object_type(self):
        """defer dependency to prevent cyclical imports"""
        import signoffs.core.approvals

        return signoffs.core.approvals.AbstractApproval


approvals = ApprovalTypes()
"""Singleton - the Approval Types registry. `(see persisting_theory.Registry)`"""


def get_approval_type(approval_id_or_type):
    """
    Return a registered Approval Type or raise ImproperlyConfigured if not such type was registered.
    Convenience function accepts either a Type or an id, and checks for existence.
    """
    approval_type = (
        approvals.get(approval_id_or_type)
        if isinstance(approval_id_or_type, str)
        else approval_id_or_type
    )
    if approval_type is None:
        raise ImproperlyConfigured(
            f"Approval Type {approval_id_or_type} must be registered before it can be used."
        )
    return approval_type


def get_approval_id(approval_id_or_type):
    """
    Return the str approval.id for an approval, approval_type, or approval_id object.
    """
    return (
        approval_id_or_type
        if isinstance(approval_id_or_type, str)
        else approval_id_or_type.id
    )


# Class decorator to simplify registering a base Type class


def register(id, **kwargs):
    """
    Return a class decorator to register a "Type" for the given (e.g., Signoff or Approval) class with the given id

    class to be registered MUST have a "register(id, **kwargs)" method
    The decorator returns the registered class in place of the decorated class

    Usage::

        @register(id='myapp.approval')
        class MyApproval(BaseApproval):
            # ...
    """

    def decorator(cls):
        return cls.register(id=id, **kwargs)

    return decorator


__all__ = ["signoffs", "approvals", "register"]
