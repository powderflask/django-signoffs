"""
A "Stamp of Approval" is the persistence layer that backs an Approval - the timestamp that seals the Approval.
    - often models the set of related Signets that define the Approval's "Signing Order".
A concrete Stamp may have other information about, or perhaps a relation to, the thing being approved.

A Stamp records status of an Approval, and is often automated by business logic defining when the Approval is complete.
An approved Stamp record provides evidence that a particular Approval was granted and by whom (via signatories).
A Stamp may be granted directly if business rules dictate, but normally is granted via one or more Signets.
Otherwise, a Stamp is not ordinarily edited directly - add and revoke Signets to move it through its signing order.
Once granted, the Stamp persists its "approved" status, regardless of the state of underlying Signets or
    changes to the Approval process.
To revoke a Stamp, we alter the approval status and revoke the Signet(s) used to grant the Approval.
A "blame" history, may be maintained by using a RevokeSignet model on the Approval Type.
"""
from django.core.exceptions import ImproperlyConfigured, ValidationError
from django.db import models
from django.utils import timezone

from .signets import AbstractSignet


class AbstractApprovalSignet(AbstractSignet):
    """A Signet representing one signature on an Approval. The Approval Stamp related_name must be "signatories" """

    stamp = models.ForeignKey(
        "Stamp", on_delete=models.CASCADE, related_name="signatories"
    )

    class Meta(AbstractSignet.Meta):
        abstract = True


class ApprovalStampQuerySet(models.QuerySet):
    """
    Custom queries for Approval Seal
    """

    def approved(self):
        """Filter out unapproved stamps"""
        return self.filter(approved=True)

    def incomplete(self):
        """Return only stamps that are not yet approved"""
        return self.exclude(approved=True)

    def prefetch_signets(self):
        """Prefetch related signets but not the signing users"""
        return self.prefetch_related("signatories")

    def prefetch_signatories(self):
        """Prefetch related signets and their signing users"""
        return self.prefetch_related("signatories__user")

    def approvals(self, approval_id=None, subject=None):
        """
        Returns list of approval objects, one for each seal in queryset,
            optionally filtered for specific approval type - filtering done in-memory for performance.
        """
        return [
            seal.get_approval(subject=subject)
            for seal in self
            if approval_id is None or seal.approval_id == approval_id
        ]


ApprovalStampManager = models.Manager.from_queryset(ApprovalStampQuerySet)


def validate_approval_id(value):
    """Raise ValidationError if value is not a registered Approval Type ID"""
    from signoffs import registry

    if value is None or value not in registry.approvals:
        raise ValidationError(f"Invalid or unregistered approval {value}")


class AbstractApprovalStamp(models.Model):
    """
    Abstract base class for all "Stamp of Approval" models
    A Stamp is the model often on the One side of a Many-To-One relation from an ApprovalSignet
    Persistence layer that timestamps an approval: who, when, what
        (what is supplied by concrete class, e.g., with a FK to other model)
    """

    approval_id = models.CharField(
        max_length=100,
        null=False,
        validators=[validate_approval_id],
        verbose_name="Approval Type",
    )
    approved = models.BooleanField(default=False, verbose_name="Approved")
    # timestamp the approval - updated by approve() method
    timestamp = models.DateTimeField(default=timezone.now, editable=False, null=False)

    class Meta:
        abstract = True
        ordering = [
            "timestamp",
        ]  # chronological order

    objects = ApprovalStampManager()

    read_only_fields = (
        "approval_id",
        "timestamp",
    )  # fields managed in code cannot be manipulated

    def __str__(self):
        return (
            f"{self.approval_id} at {self.timestamp}"
            if self.is_approved()
            else f"{self.approval_id} (incomplete)"
        )

    @property
    def approval_type(self):
        """Return the Approval Type (class) that governs this stamp"""
        from signoffs.registry import approvals

        approval_type = approvals.get(self.approval_id)
        if not approval_type:
            raise ImproperlyConfigured(
                f"""Approval type {approval_type} not registered.
            See AUTODISCOVER settings to discover approval types when django loads."""
            )
        return approval_type

    def get_approval(self, subject=None):
        """Return an Approval instance for this stamp"""
        return self.approval_type(stamp=self, subject=subject)

    @property
    def approval(self):
        """The Approval instance for this stamp"""
        return self.get_approval()

    def is_approved(self):
        """return True if this Stamp is approved and has a persistent representation in DB"""
        return self.approved and self.id is not None

    def approve(self):
        """
        Approve the stamp (but don't commit the change)
        No permissions involved here - just force this stamp into approved state!
        """
        self.approved = True
        self.timestamp = timezone.now()

    def is_user_signatory(self, user):
        """return True iff the given user is a signatory on this stamp"""
        return any(s.user == user for s in self.signatories.all())

    def has_valid_approval(self):
        """return True iff this Stamp has a valid approval_id"""
        from signoffs import registry

        return self.approval_id is not None and self.approval_id in registry.approvals

    def save(self, *args, **kwargs):
        """Validate and save this stamp"""
        self.full_clean()
        return super().save(*args, **kwargs)

    @classmethod
    def has_object_relation(cls):
        """Return True iff this Stamp class has a FK relation to some object other than user"""
        relations = [
            f
            for f in cls._meta.fields
            if isinstance(f, models.ForeignKey)
            and not issubclass(f.related_model, AbstractApprovalStamp)
            and f.name != "user"
        ]
        return bool(relations)
