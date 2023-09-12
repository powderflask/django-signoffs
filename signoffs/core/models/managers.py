"""
    Custom object and query managers.
"""
from signoffs import registry


class QuerySetApiMixin:
    """
    Delegates common methods to a query manager or queryset to emulate a queryset-like API,
        without making extra queries where possible.  Assumes a small number of instances on the queryset
    """

    qs = None  # queryset or query manager, to be defined on mixed-in instance

    def all(self):
        """Return list of objects in this set, ordered chronologically"""
        return self.qs.all()

    def count(self):
        """Return the number of objects in the qs"""
        return len(self.all())

    def exists(self):
        """Rerturn True iff at least one Object exists in this set"""
        return bool(self.all())

    def earliest(self):
        """Return the first object from this set, or None if not self.exists()"""
        all = self.all()
        return all[0] if all else None

    def latest(self):
        """Return most recent object from this set, or None if not self.exists()"""
        all = self.all()
        return all[-1] if all else None


# Signoff / Signet Sets


class SignetSetApiMixin(QuerySetApiMixin):
    """Delegates common methods to a signet_set manager or queryset"""

    signet_set = None  # Signet qs or manager, to be defined on mixed-in instance

    @property
    def qs(self):
        return self.signet_set


class SignoffSetManager(SignetSetApiMixin):
    """
    Manage a set of Signoff objects backed by a signet manager or queryset.
    May be used, for example, on the reverse side of a many-to-one relation formed by a Signet with a FK.

    For example::

        signets = Signets.objects.filter(user=bob)
        bobs_report_signoffs = SignoffSetManager('myapp.signoffs.report', signets)

    For "reverse" access from a signet-related object, use a SignoffSet field to define the reverse manager.

    The API is modelled on django's related object managers, with familiar operations that work roughly equivalently.
    """

    def __init__(self, signoff_type, signet_set, signet_set_owner=None):
        """
        Manage the signet_set (query manager or queryset), filtered for the given Signoff Type
        If an approval instance is supplied, signets in this set are created with a reference to the approval's stamp.
        """
        self.signoff_type = registry.get_signoff_type(signoff_type)
        self.signet_set = signet_set
        self.signet_set_owner = signet_set_owner

    # Customize queryset emulation provided by Signets Set API Mixin
    def all(self):
        """Return list of signoffs in this set, ordered chronologically"""
        return super().all().signoffs(signoff_id=self.signoff_type.id)

    def _pre_save_owner(self):
        """Bit of a hack - if signet_set_owner is an unsaved model, save it before saving related signets"""
        try:
            if self.signet_set_owner._meta.model and not self.signet_set_owner.pk:
                self.signet_set_owner.save()
        except AttributeError:
            pass

    def create(self, user, **kwargs):
        """Create and return a new Signoff in this set"""
        self._pre_save_owner()
        signet = self.signet_set.create(
            signoff_id=self.signoff_type.id, user=user, **kwargs
        )
        return self.signoff_type(signet)

    # signoff delegate / aggregate methods

    def can_sign(self, user):
        """Return True iff given user would be allowed to sign (create) a new signoff in this set"""
        return self.signoff_type().can_sign(user)

    def has_signed(self, user):
        """Return True iff given user is a signatory in this set of signoffs"""
        return any(s.signatory == user for s in self.all())

    @property
    def forms(self):
        """
        Return the forms manager for adding a new signoff to this set or revoking a signoff in this set.
        """
        return self.signoff_type.forms

    # related querysets

    def revoked(self):
        """
        Returns a queryset of revoked signets related to the manager's instance.
        related 'revoked' and 'revoked.user' objects are selected, assuming why else get the revoked signoffs
        """
        return (
            self.signoff_type.get_revoked_signets_queryset()
            .filter(**self.signet_set.core_filters)
            .select_related("revoked__user")
        )


class SignoffSingleManager(SignoffSetManager):
    """
    A SignoffSetManager that attempts to limit the number of related signets to one
        and provide simplified API for dealing with the single signoff.
    Why?
        b/c it is convenient to manage all signoffs, e.g., on an Approval, backed by one Signet model.
        If every Signoff is a single, then a set of SignoffFields is well-suited to the task.
        But if any Signoff may be a series, then it is convenient to model all as SignoffSets.
        This class helps clarify that a specific reverse Many2One relation is being modeled as a OneToOne.
    Caveats
        Can't really prevent multiple signoffs being added via non-API access.  That's up to the application programmer.
    """

    def get(self):
        """Get this signoff"""
        return self.all()[0] if self.exists() else self.signoff_type()

    def create(self, user, **kwargs):
        """Create and return the new Signoff. Raise ??? if self.exists()"""
        if self.exists():
            raise Exception  # TODO: what exception here???
        return super().create(user, **kwargs)

    def can_sign(self, user):
        """Return True iff given user would be allowed to sign (create) a new signoff in this set"""
        return not self.exists() and super().can_sign(user)


class StampSignoffsManager(SignetSetApiMixin):
    """
    Manage the entire set of signoffs related to a Stamp of Approval via reverse signet_set manager.
    Note that a single Stamp manages one set of Signets that may be of various Signoff Types
        -  recommend using a SignoffSetManager instead, unless access to entire set of signoffs is needed.
    Provides a unified API for accessing a single Stamp instance's related signoffs and signets.

    For example::

        stamp = ProjectStamp.objects.filter(project_id='bob').first()
        bobs_project_signoffs = StampSignoffsManager(stamp)

    The API is modelled on django's related object managers, with familiar operations that work roughly equivalently.
    """

    def __init__(self, stamp, subject=None):
        """Manage the given Approval instance and all of its related data"""
        self.stamp = stamp
        self.subject = subject

    @property
    def signet_set(self):
        """required for SignetSetApiMixin"""
        return self.stamp.signatories

    # Customize queryset emulation provided by Signets Set API Mixin
    def all(self):
        """Return list of signoffs in this approval, ordered chronologically"""
        return super().all().signoffs(subject=self.subject)


# Approval / Stamp Sets


class ApprovalStampSetApiMixin(QuerySetApiMixin):
    """Delegates common methods to a stamp_set manager or queryset"""

    stamp_set = (
        None  # Stamp queryset or query manager, to be defined on mixed-in instance
    )

    @property
    def qs(self):
        return self.stamp_set


class ApprovalSetManager(ApprovalStampSetApiMixin):
    """
    Manage a set of Approval objects backed by a Stamp manager or queryset.
    May be used, for example, on the reverse side of a many-to-one relation formed by a Stamp with a FK.
    Provides a unified API for accessing Approval instances, and related SigningOrder, Stamp, signoffs, and signets.

    For example::

        stamps = Stamp.objects.filter(user=bob)
        bobs_report_approvals = ApprovalSetManager('myapp.approvals.report', stamps)

    For "reverse" access from a stamp-related object, use an ApprovalSet field to define the reverse manager.

    The API is modelled on django's related object managers, with familiar operations that work roughly equivalently.
    """

    def __init__(self, approval_type, stamp_set, subject=None):
        """Manage the stamp_set (query manager or queryset), filtered for the given Signoff Type"""
        self.approval_type = registry.get_approval_type(approval_type)
        self.stamp_set = stamp_set
        self.subject = subject

    # Customize queryset emulation provided by Stamp Set API Mixin
    def all(self):
        """Return list of approvals in this set, ordered chronologically"""
        return (
            super()
            .all()
            .approvals(approval_id=self.approval_type.id, subject=self.subject)
        )

    def create(self, **kwargs):
        """Create and return a new Approval in this set"""
        stamp = self.stamp_set.create(approval_id=self.approval_type.id, **kwargs)
        return self.approval_type(stamp, subject=self.subject)
