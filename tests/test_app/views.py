"""
    Views for demonstrating and testing templates, templatetags, and rendering logic

    TODO: extend these views so they can be used to drive an approval process.
        add post form handling logic, etc.
"""
from django.views import generic

from signoffs.shortcuts import get_approval_stamp_or_404, get_signet_or_404


class SignoffDetailView(generic.DetailView):
    template_name = "test_app/signets/detail_view.html"

    def get_object(self, queryset=None):
        """Return the signet instance for the given signoff type"""
        return get_signet_or_404(self.kwargs["signoff_id"], self.kwargs["pk"])

    def get_context_data(self, **kwargs):
        return super().get_context_data(
            signed_signoff=self.object.signoff,
            unsigned_signoff=type(self.object.signoff)(),
            **kwargs,
        )


class ApprovalDetailView(generic.DetailView):
    template_name = "test_app/approvals/detail_view.html"

    def get_object(self, queryset=None):
        """Return the signet instance for the given signoff type"""
        return get_approval_stamp_or_404(self.kwargs["approval_id"], self.kwargs["pk"])

    def get_context_data(self, **kwargs):
        return super().get_context_data(approval=self.object.approval, **kwargs)
