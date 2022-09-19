"""
    Objects that know how to assess the status of an Approval
"""
from django.template.loader import render_to_string


class ApprovalInstanceStatus:
    """ Access status info about an Approval instance """

    def __init__(self, approval_instance, **kwargs):
        """ A status instance for given approval instance """
        self.approval = approval_instance

    # Note: there is an intermediate state in which a pre-condition to approval is not yet met,
    #       so the approval is not yet "awaiting".  Controlled at approval-process level, not available on approval.
    def get_status(self):
        """ Return a short status indicator, e.g., for use as a CSS class, dictionary key, etc. """
        return 'complete' if self.approval.is_approved() else 'awaiting'

    def get_label(self):
        """ Return a string with a pithy label indicating the status of the approval. """
        return "Approval Complete" if self.approval.is_approved() else "Awaiting Approval"

    def get_css_class(self):
        """ Return a CSS class used, e.g., to style the approval label in templates """
        return 'success' if self.approval.is_approved() else 'warning'


class ApprovalStatus:
    """ A descriptor that "injects" a ApprovalInstanceStatus into a Approval instance. """

    instance_renderer = ApprovalInstanceStatus

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
