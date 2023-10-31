"""
A `Signet` is a relation between a user and a timestamp.
A concrete `Signet` may have other information about, or perhaps a relation to, the thing being signed off.

A `Signet` records a one-time action that can generally only be completed by a `User` with permission.
The presence of a `Signet` record provides evidence that a particular someone signed off on a particular something.
A `Signet` is not intended to be edited.  Create them, revoke them, re-create them.  Don't edit and re-save them.
To revoke a `Signet`, we can simply delete the `Signet` record.
To maintain a "blame" history, we can instead record who and when the signet was revoked with a `RevokedSignet`.
"""
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from django.core.exceptions import (
    FieldError,
    ImproperlyConfigured,
    PermissionDenied,
    ValidationError,
)
from django.db import models
from django.utils import timezone

from signoffs import settings


class SignetQuerySet(models.QuerySet):
    """
    Custom queries for signets
    """

    def active(self):
        """Filter out revoked signets"""
        try:
            return self.filter(revoked=None)
        except FieldError:  # caveat: not every signet model has a related revoke model.
            return self

    def revoked(self):
        """Return only revoked signets"""
        try:
            return self.exclude(revoked=None)
        except FieldError:  # no related manager  --> no revoked signets
            return self.none()

    def with_user(self):
        """Select the related signing User"""
        return self.select_related("user")

    def with_revoked_receipt(self):
        """Select related 'revoked' records"""
        try:
            return self.select_related("revoked")
        except FieldError:  # no related manager  --> no revoked signets
            return self

    def signoffs(self, signoff_id=None, subject=None):
        """
        Returns list of signoff objects, one for each signet in queryset,
            optionally filtered for specific signoff type - filtering done in-memory for performance.
        """
        return [
            signet.get_signoff(subject=subject)
            for signet in self
            if signoff_id is None or signet.signoff_id == signoff_id
        ]


BaseSignetManager = models.Manager.from_queryset(SignetQuerySet)


class ActiveSignetManager(BaseSignetManager):
    """Filters out revoked signets from queryset - should be the default manager"""

    def get_queryset(self):
        return super().get_queryset().active()


class RevokedSignetManager(BaseSignetManager):
    """Filters out un-revoked signets from queryset (only revoked signets returned"""

    def get_queryset(self):
        return super().get_queryset().revoked()


def validate_signoff_id(value):
    """Raise ValidationError if value is not a registered Signoff Type ID"""
    from signoffs import registry

    if value is None or value not in registry.signoffs:
        raise ValidationError(f"Invalid or unregistered signoff {value}")


def get_signet_defaults(signet):
    """
    Return a dictionary of default values for fields the given signet -
        this is the default implementation for settings.SIGNOFFS_SIGNET_DEFAULTS setting.
    Called just before signet is saved - signet is guaranteed to have a valid user object.
    Dictionary keys must match signet model field names - only editable fields of signet may have defaults.
    Only fields with no value will be set to its default value.
    """
    return {
        "sigil": signet.user.get_full_name() or signet.user.username,
        "sigil_label": signet._meta.get_field("sigil").verbose_name,
    }


class AbstractSignet(models.Model):
    """
    Abstract base class for all Signet models
    A Signet is the model for a single "signature" or a user's personal "seal" or "sigil"
    Persistence layer for a signoff: who, when, what (what is supplied by concrete class, e.g., with a FK to other model)
    Note: user relation is required for signing - enforced by app logic rather than at DB level so that...
    SET_NULL on_delete for user field is sensible for use-cases where signoff should persist even after user is deleted.
       For other on_delete behaviours, concrete RevokedSignet classes will need to override the user relation.
    """

    signoff_id = models.CharField(
        max_length=100,
        null=False,
        validators=[validate_signoff_id],
        verbose_name="Signoff Type",
    )
    user = models.ForeignKey(
        get_user_model(), on_delete=models.SET_NULL, null=True, related_name="+"
    )
    sigil = models.CharField(max_length=256, null=False, verbose_name="Signed By")
    sigil_label = models.CharField(
        max_length=256, null=True
    )  # optional label, e.g., signatory's title or role
    timestamp = models.DateTimeField(default=timezone.now, editable=False, null=False)

    class Meta:
        abstract = True
        ordering = [
            "timestamp",
        ]  # chronological order

    objects = ActiveSignetManager()  # default manager excludes revoked signets.
    revoked_signets = RevokedSignetManager()
    all_signets = (
        BaseSignetManager()
    )  # only use this manager if you want to include signed and revoked signets!

    read_only_fields = (
        "signoff_id",
        "timestamp",
    )  # fields managed in code cannot be manipulated

    def __str__(self):
        return (
            f"{self.signoff_id} by {self.user} at {self.timestamp}"
            if self.is_signed()
            else f"{self.signoff_id} (unsigned)"
        )

    @property
    def signoff_type(self):
        """Return the Signoff Type (class) that governs this signet"""
        from signoffs.registry import signoffs

        signoff_type = signoffs.get(self.signoff_id)
        if not signoff_type:
            raise ImproperlyConfigured(
                f"""Signoff type {signoff_type} not registered.
            See AUTODISCOVER settings to discover signoff types when django loads."""
            )
        return signoff_type

    def get_signoff(self, subject=None):
        """Return a Signoff instance for this signet"""
        return self.signoff_type(signet=self, subject=subject)

    @property
    def signoff(self):
        """The Signoff instance for this signet"""
        return self.get_signoff()

    @property
    def signatory(self):
        """Return the user who signed, or AnonymousUser if signed but no signatory, None if not yet signed"""
        return self.user if self.user else AnonymousUser() if self.is_signed() else None

    def sign(self, user):
        """Sign unsigned signet for given user. If self.is_signed() raises PermissionDenied"""
        if not self.is_signed():
            self.user = user
        else:
            raise PermissionDenied(f"Attempt to sign signed Signet {self}")

    def has_user(self):
        """Return True iff this signet has a user-relation"""
        return self.user_id is not None

    def is_signed(self):
        """Return True if this Signet has a persistent representation"""
        return self.id is not None

    def is_revoked(self):
        """Return True if this Signet has been revoked - Performance: .with_revoked_receipt() to avoid extra query"""
        return hasattr(self, "revoked")

    def has_valid_signoff(self):
        """Return True iff this Signet has a valid signoff_id"""
        from signoffs import registry

        return self.signoff_id is not None and self.signoff_id in registry.signoffs

    def can_save(self):
        """Return True iff this signet is data-complete and ready to be saved, but has not been saved before"""
        return not self.is_signed() and self.has_user() and self.has_valid_signoff()

    def update(self, defaults=False, **attrs):
        """Update instance model fields with any attrs that match by name, optionally setting only unset fields"""
        for fld in filter(lambda fld: fld not in self.read_only_fields, attrs):
            if not defaults or not getattr(self, fld, None):
                setattr(self, fld, attrs[fld])
        return self

    def get_signet_defaults(self):
        """Return dict of default field values for this signet - signet MUST have user relation!"""
        defaults = settings.SIGNOFFS_SIGNET_DEFAULTS
        return (
            get_signet_defaults(self)
            if defaults is None
            else defaults(self)
            if callable(defaults)
            else defaults
        )  # otherwise, defaults must be a dict-like object

    def set_signet_defaults(self):
        """Set default field values for this signet - signet MUST have user relation!"""
        return self.update(defaults=True, **self.get_signet_defaults())

    def validate_save(self):
        """Raise ValidationError if this Signet cannot be saved, otherwise just pass."""
        self.full_clean()
        if self.is_signed():
            raise PermissionDenied(f"Unable to re-save previously signed Signet {self}")
        elif not self.can_save():
            raise PermissionDenied(f"Unable to save Signet {self}")

    def save(self, *args, **kwargs):
        """Add a 'sigil' label if there is not one & check user has permission to save this signet"""
        self.set_signet_defaults()
        self.validate_save()
        return super().save(*args, **kwargs)

    @classmethod
    def has_object_relation(cls):
        """Return True iff this Signet class has a FK relation to some object other than user"""
        relations = [
            f
            for f in cls._meta.fields
            if isinstance(f, models.ForeignKey)
            and not issubclass(f.related_model, AbstractSignet)
            and f.name != "user"
        ]
        return bool(relations)


class AbstractRevokedSignet(models.Model):
    """
    Abstract base class for all Signet Revocation models
    A Revoked Signet is a record of a signet that was removed.  Only needed if a record of revoked signets is required.
    Persistence layer for revoked signet: who, when, what (what is an app-relative concrete Signet model)
    Note: user relation is required for signing - enforced by app logic rather than at DB level - see AbstractSignet
    """

    # noinspection PyUnresolvedReferences
    signet = models.OneToOneField(
        "Signet", on_delete=models.CASCADE, related_name="revoked"
    )
    user = models.ForeignKey(
        get_user_model(),
        on_delete=models.SET_NULL,
        null=True,
        verbose_name="Revoked by",
        related_name="+",
    )
    reason = models.TextField(blank=True, null=True)
    timestamp = models.DateTimeField(
        default=timezone.now, editable=False, null=False, verbose_name="Revoked at"
    )

    class Meta:
        abstract = True

    def __str__(self):
        return f"Revoked {getattr(self.signet, 'signoff_id', '')} by {self.user} at {self.timestamp}"
