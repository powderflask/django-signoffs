"""
    Custom model fields and relation descriptors
"""
from functools import cached_property
from typing import Union, Type

from django.core.exceptions import ImproperlyConfigured
from django.db import models

from signoffs import registry
from signoffs.core.models import AbstractSignet, AbstractApprovalStamp
from signoffs.core.models.managers import SignoffSetManager, SignoffSingleManager, ApprovalSetManager
from signoffs.core.signoffs import AbstractSignoff
from signoffs.core.approvals import AbstractApproval
from signoffs.core.utils import Accessor


# OneToOne "forward" relation from arbitrary model to a single Signoff


class RelatedSignoffDescriptor:
    """
    Descriptor that provides a Signoff backed by a OneToOneField to a Signet model,
        with services to manage the relation on the defining model.
    Class access yields the Signoff Type class.
    Instance access yields a Signoff instance wrapping the related Signet object
        (which may be None, i.e. unsigned Signoff)
    """
    def __init__(self, signoff_type, signet_field):
        """ Manage a OneToOne signet_field using the given Signoff Type (or signoff id str) """
        self._signoff_type = signoff_type
        self.signet_field = signet_field

    def _validate_related_model(self, signet_field, signoff_type):
        """ Raises ImproperlyConfigured if the signet_field model relation is not same as the signoff_type Signet model """
        if isinstance(signoff_type, str) and signoff_type not in registry.signoffs:
            # allow signoff_type to be deferred so field can be defined before signoff is registered,
            # but then no way to validate b/c can't get the related signetModel.  Cross fingers?
            return

        signoff_type = registry.get_signoff_type(signoff_type)
        signet_model = signoff_type.get_signetModel()
        related = signet_field.remote_field.model
        # Related could be a model class or a str - handle either case...
        signet = signet_model._meta.label_lower if isinstance(related, str) else signet_model
        if related != signet:
            raise ImproperlyConfigured(
                'signet_field "to" model {r} must match the signoff_type Signet model {s} '
                '- use convenience method "SignoffField" to handle this.'.format(r=related, s=signet)
            )

    def __get__(self, instance, owner=None):
        base_signoff_type = registry.get_signoff_type(self._signoff_type)

        class RelatedSignoff(base_signoff_type):
            signet_field = self.signet_field
            """ A Signoff that is aware of a "reverse" one-to-one relation to the instance object """
            def save(self, *args, **kwargs):
                """ Save the related signet and then the instance relation """
                signoff = super().save(*args, **kwargs)
                setattr(instance, self.signet_field.name, signoff.signet)
                instance.save()
                return signoff

        if not instance:
            return RelatedSignoff
        else:
            return RelatedSignoff(signet=getattr(instance, self.signet_field.name))


def SignoffField(signoff_type, on_delete=models.SET_NULL, null=True, related_name='+', **kwargs):
    """
    Convenience method for constructing from minimal inputs:
        (1) a sensible OneToOneField(signoff_type.stampModel); and
        (2) an RelatedApprovalDescriptor(signoff_type)
    signoff_type may be an Approval Type or a registered(!) signoff id.
    Default parameter rationale:
        null=True, on_delete=SET_NULL make sensible defaults for a Signet relation since presence/absence is semantic;
            think twice before using other values!
        reverse related_name from Signet generally not so useful, consider disabling with '+'

    In the example::

        from signoffs.signoffs import SimpleSignoff

        applicant_signoff = SimpleSignoff.register('myapp.signoff.applicant', ...)

        # the verbose / explicit way...
        class Application(models.Model):
            # ...
            applicant_signet = OneToOneField(applicant_signoff.signetModel, on_delete=models.SET_NULL,
                                             signoff_type=applicant_signoff,
                                             null=True, )
            applicant_signoff = RelatedSignoffDescriptor(applicant_signoff, applicant_signet)

        # the concise convenient way...
        class Application(models.Model):
            # ...
            applicant_signoff, applicant_signet = SignoffField(applicant_signoff)

    In either case above:
        ``Application.applicant_signet`` is a "normal" One-to-One relation to the Signet model
        ``Application().applicant_signet`` is a Signet instance or None (if signoff is not  signed)

        ``Application.applicant_signoff`` is a RelatedSignoffDescriptor that ultimately injects a Signoff instance
        ``Application().applicant_signoff`` is a Signoff instance of the given signoff_type backed by the applicant_signet
                relation.  This Signoff will update the instance's applicant_signet relation whenever it is save()'ed
    """
    try:
        signoff_type = registry.get_signoff_type(signoff_type)
    except ImproperlyConfigured:
        raise ImproperlyConfigured(
            'SignoffField: signoff_type {s} must be registered before it can be used to form a relation. '
            'OneToOneField + RelatedSignoff can form relation to Signet Model with a deferred signoff id.'.format(
                s=signoff_type)
        )
    # Intentionally using raw .signetModel, (possibly a str: 'app_label.model_name'), so use can avoid circular imports
    signet_field = models.OneToOneField(signoff_type.signetModel, on_delete=on_delete,
                                        null=null, related_name=related_name, **kwargs)
    signoff = RelatedSignoffDescriptor(signoff_type, signet_field)
    return signoff, signet_field


# ManyToOne "reverse" relation from a model instance to the set of Signoff that refer to it.


class SignoffSet:
    """
    A descriptor that injects a "reverse relation" manager, filtered for the specific Signoff type.
    The signoff_type MUST be backed by a Signet with a FK relation to the owning model
    signet_set_accessor is a string with a path to the reverse relation manager on the owning model
        - it may use '__' to travese relations and include method calls e.g.,  'my_signet_manager__get_signet_set'

    In the example::

        class VacationSignet(AbstractSignet):
            vacation = models.ForeignKey(Vacation, on_delete=models.CASCADE, related_name='signatories')

        class Vacation(models.Model):
            employee = models.CharField(max_length=128)
            # ...
            hr_signoffs = SignoffSet('testapp.hr_signoff')
            mngr_signoffs = SignoffSet('testapp.mngr_signoff')


    ``Vacation.signatories`` is the "normal" ``ReverseManyToOneDescriptor`` instance to access the related Signets.
    ``Vacation.hr_signoffs`` and ``Vacation.mngr_signoffs`` are 2 distinct Signoff Types (Signoff sub-classes), while
    ``Vacation().hr_signoffs`` and ``Vacation().mngr_signoffs``  are SignoffSetManager instances
            used to access the set of signoffs of that particular type, backed by the vacation instance.signatories.

    See managers.SignoffSetManager for access API.
    """

    signoff_set_manager = SignoffSetManager

    def __init__(self, signoff_type: Union[str, Type[AbstractSignoff]] = None,
                 signet_set_accessor='signatories',
                 signoff_set_manager=None, **kwargs):
        """
        Inject a Signoff; kwargs passed directly through to AbstractSignoff.__init__
        id defaults to the descriptor name if not specified
        """
        self._signoff_type = signoff_type
        self.signet_set_accessor = Accessor(signet_set_accessor)
        self.signoff_set_manager = signoff_set_manager or self.signoff_set_manager
        self.accessor_field_name = ''  # set by __set_name__
        self.kwargs = kwargs

    def __set_name__(self, owner, name):
        """ Grab the field named used by owning class to refer to this descriptor """
        self.accessor_field_name = name

    @staticmethod
    def _is_valid_signoff_type(signoff_type):
        return signoff_type is not None and \
               issubclass(signoff_type, AbstractSignoff) and \
               issubclass(signoff_type.get_signetModel(), AbstractSignet) and \
               signoff_type.has_object_relation()

    @cached_property
    def signoff_type(self):
        signoff_type = registry.get_signoff_type(self._signoff_type)
        if self._is_valid_signoff_type(signoff_type):
            return signoff_type
        else:
            raise ImproperlyConfigured(
                'SignoffSet: Signoff Type {type} must have a Signet with a relation'.format(type=signoff_type)
            )

    def signet_set_owner(self, instance):
        signet_set_owner, _ = self.signet_set_accessor.penultimate(instance)
        return signet_set_owner or instance

    def _validate_related_manager(self, instance):
        """ Raises ImproperlyConfigured if the signet_set_accessor is not a relation to a Signet Manager or queryset """
        try:
            signet_set = self.signet_set_accessor.resolve(instance)
            signet_model = self.signoff_type.get_signetModel()
        except AttributeError:
            raise ImproperlyConfigured(
                'SignoffSet.signet_set_accessor "{s}" does not exist on related model {m}.'.format(
                    s=self.signet_set_accessor, m=type(instance)))

        signet_set_owner = self.signet_set_owner(instance)
        related_models = [ro.related_model for ro in signet_set_owner._meta.related_objects]
        if signet_set.model not in related_models or signet_set.model is not signet_model:
            raise ImproperlyConfigured(
                'SignoffSet.signet_set_accessor "{s}" must be a related {sm} to {m}.'.format(
                    s=self.signet_set_accessor, sm=signet_model, m=type(instance)))

    def get_signoffs_manager(self, instance):
        """ Return a signoff_set_manager for signet set instance.signet_set_accessor """
        self._validate_related_manager(instance)
        signet_set = self.signet_set_accessor.resolve(instance)
        signet_set_owner = self.signet_set_owner(instance)
        return self.signoff_set_manager(self.signoff_type, signet_set, signet_set_owner)

    def __get__(self, instance, owner=None):
        """
        Use the enclosing instance to construct and return a SignoffSetManager instance,
          and replace descriptor with that object
        """
        if instance is None:  # class access - provide access to the Signoff Type itself
            return self.signoff_type
        else:  # on instance, replace descriptor with related signoff manager.  Voilà!
            signoffs_manager = self.get_signoffs_manager(instance)
            setattr(instance, self.accessor_field_name, signoffs_manager)
            return signoffs_manager


def SignoffSingle(*args, **kwargs):
    """ A thin wrapper for SignoffSet that configures the correct SignoffSetManager for a single signoff """
    default_kwargs = dict(
        signoff_set_manager=SignoffSingleManager,
    )
    default_kwargs.update(kwargs)
    return SignoffSet(*args, **default_kwargs)


def ApprovalSignoffSet(*args, **kwargs):
    """ A thin wrapper for SignoffSet that configures the correct signet_set_accessor for Approvals """
    default_kwargs = dict(
        signet_set_accessor='stamp__signatories',
    )
    default_kwargs.update(kwargs)
    return SignoffSet(*args, **default_kwargs)


def ApprovalSignoffSingle(*args, **kwargs):
    """ A thin wrapper for SignoffSet that configures the correct signet_set_accessor for a single Approval signoff """
    default_kwargs = dict(
        signoff_set_manager=SignoffSingleManager,
        signet_set_accessor='stamp__signatories',
    )
    default_kwargs.update(kwargs)
    return SignoffSet(*args, **default_kwargs)


# OneToOne "forward" relation from arbitrary model to a single Approval


class ApprovalCallbacksManager:
    """
    Register set of callback functions that may be used to decorate the methods of an Approval Type
    Callbacks take 2 parameters - the object passed to decorate_approval (typically self) and the approval instance
    """
    def __init__(self):
        self.callbacks = {}

    def on_approval(self, callback):
        """ Register a callback to be called after an Approval's "approve" method is complete """
        self.callbacks['post_approval'] = callback
        return callback

    def on_revoke(self, callback):
        """ Register a callback to be called after an Approval's "revoke" method is complete """
        self.callbacks['post_revoke'] = callback
        return callback

    def decorate_approval(self, obj, approval_type):
        """ Return a copy of given Approval Type, but with approve / revoke methods decorated with callbacks """
        callbacks = self.callbacks

        class DecoratedApproval(approval_type):
            if 'post_approval' in callbacks:
                def approve(self, *args, **kwargs):
                    """ Approve approval and invoke callback  """
                    super().approve(*args, **kwargs)
                    callbacks['post_approval'](obj, self)

            if 'post_revoke' in callbacks:
                def revoke(self, *args, **kwargs):
                    """ Revoke approval and invoke callback """
                    super().revoke(*args, **kwargs)
                    callbacks['post_revoke'](obj, self)

        return type('Decorated{}'.format(approval_type.__name__), (DecoratedApproval,), {})


class RelatedApprovalDescriptor:
    """
    Descriptor that provides an Approval backed by a OneToOneField to a Stamp model,
        with services to manage the relation on the defining model.
    Class access yields the Approval Type class.
    Instance access yields an Approval instance wrapping the related Stamp object
        (which will be created if it doesn't yet exist, i.e. uninitiated Approval)
    """
    callback_manager_class = ApprovalCallbacksManager

    def __init__(self, approval_type, stamp_field, callback_manager=None):
        """ Manage a OneToOne Stamp field  using the given Approval Type or approval id """
        self.approval_type = approval_type
        self.stamp_field = stamp_field
        # callback manager provides a means to configure callbacks on approval events (like approve and revoke)
        self.callback = callback_manager or self.callback_manager_class()

    def _validate_related_model(self, stamp_field, approval_type):
        """ Raises ImproperlyConfigured if the stamp_field model relation is not same as the approval_type Stamp model """
        if isinstance(approval_type, str) and approval_type not in registry.approvals:
            # allow approval_type to be deferred so field can be defined before approval is registered,
            # but then no way to validate b/c can't get the related stampModel.  Cross fingers?
            return

        approval_type = registry.get_approval_type(approval_type)
        stamp_model = approval_type.get_stampModel()
        related = stamp_field.remote_field.model
        # Related could be a model class or a str - handle either case...
        stamp = stamp_model._meta.label_lower if isinstance(related, str) else stamp_model
        if related != stamp:
            raise ImproperlyConfigured(
                'stamp_field "to" model {r} must match the approval_type Stamp model {s} '
                '- use convenience method "ApprovalField" to handle this.'.format(r=related, s=stamp)
            )

    def __get__(self, instance, owner=None):
        """ Return an approval obj. wrapping the stamp_field on instance access, or the approval_type """
        # Can't validate until models are fully loaded :-/
        self._validate_related_model(self.stamp_field, self.approval_type)

        base_approval_type = registry.get_approval_type(self.approval_type)
        approval_with_callbacks = self.callback.decorate_approval(instance, base_approval_type)

        class BaseRelatedApproval(approval_with_callbacks):
            """ An Approval that is aware of a "reverse" one-to-one relation to the instance object """
            stamp_field = self.stamp_field
            _callbacks = self.callback

            def save(self, *args, **kwargs):
                """ Save the related stamp and then the instance relation """
                approval = super().save(*args, **kwargs)
                if not getattr(instance, self.stamp_field.name) == approval.stamp:
                    setattr(instance, self.stamp_field.name, approval.stamp)
                    instance.save()
                return approval

        RelatedApproval = type('Related{}'.format(base_approval_type.__name__), (BaseRelatedApproval,), {})

        if not instance:
            return base_approval_type
        else:
            stamp = getattr(instance, self.stamp_field.name)
            approval = RelatedApproval(stamp=stamp)
            if not stamp:
                approval.save()
            return approval


def ApprovalField(approval_type, on_delete=models.SET_NULL, null=True, related_name='+', **kwargs):
    """
    Convenience method for constructing from minimal inputs:
        (1) a sensible OneToOneField(approval_type.stampModel); and
        (2) an RelatedApprovalDescriptor(approval_type)
    approval_type may be an Approval Type or a registered(!) approval id.
    Default parameter rationale:
        null=True, on_delete=SET_NULL make sensible defaults for a Stamp relation since presence/absence is semantic;
            think twice before using other values!
        reverse related_name from Stamp generally not so useful, consider disabling with '+'

    In the example::

        from signoffs.approvals import ApprovalSignoff
        from signoffs.models import ApprovalSignet, Stamp

        @register(id=myapp.application_approval)
        class ApplicationApproval(ApprovalSignoff):
            stampModel = Stamp
            S = ApprovalSignoff

            reg_signoff = S.register('application.approval.signoff.registration', ...)
            deposit_signoff = S.register('application.approval.signoff.deposit', ...)
            final_approval = S.register('application.approval.signoff.final', ...)

            signing_order = SigningOrder(
                pm.InSeries(
                    pm.InParallel(
                        ret_signoff,
                        deposit_signoff,
                    )
                    final_approval,
                )
            )

        # The verbose way:
        class Application(models.Model):
            # ...
            approval_stamp = OneToOneField(ApplicationApproval.stampModel, on_delete=models.SET_NULL, null=True)
            approval = RelatedApprovalDescriptor(ApplicationApproval, approval_stamp)

        # The convenient way:
        class Application(models.Model):
            # ...
            approval, approval_stamp = ApprovalField(ApplicationApproval)

    In both cases above:
        ``Application.approval_stamp`` is a "normal" One-to-One relation to the backing Stamp model
        ``Application().approval_stamp`` is a Stamp instance or None (if approval is not initiated)

        ``Application.approval`` is a RelatedApprovalDescriptor that ultimately injects an ApplicationApproval instance
        ``Application().approval`` is an ApplicationApproval instance, backed by the OneToOne approval_stamp relation.
                This approval will update the application's OneToOne relation whenever it is save()'ed
    """
    try:
        approval_type = registry.get_approval_type(approval_type)
    except ImproperlyConfigured:
        raise ImproperlyConfigured(
            'ApprovalField: approval_type {a} must be registered before it can be used to form a relation. '
            'A OneToOneField + RelatedApproval can be used to form this relation with a deferred approval id.'.format(
                a=approval_type)
        )
    # Intentionally using raw .stampModel, (possibly 'app_label.model_name' str), so use can avoid circular imports
    stamp_field = models.OneToOneField(approval_type.stampModel, on_delete=on_delete,
                                       null=null, related_name=related_name, **kwargs)
    approval = RelatedApprovalDescriptor(approval_type, stamp_field)
    return approval, stamp_field


# ManyToOne "reverse" relation from a model instance to the set of Approvals that refer to it.
# EXPERIMENTAL: not entirely clear why one would have a set of approvals of one type for same object?
#               would an "approved" object ever need another "approval"?  Maybe like for Building permits?
#               TODO: the Implementation below should work, but requires test cases before use.


class ApprovalSet:
    """
    A descriptor that injects a "reverse relation" manager, filtered for the specific Approval Type.
    The approval_type MUST be backed by a Stamp with a FK relation to the owning model

    In the example::

        class BuildingPermit(AbstractApprovalStamp):
            building = ForeignKey('Building', related_name='permits')

        @register(id='myapp.building_approval')
        class ConstructionApproval(BaseApproval):
            stampModel = BuildingPermit
            S = ApprovalSignoff

            planning_signoff = S.register('building.approval.signoff.planning', ...)
            electrical_signoff = S.register('building.approval.signoff.electrical', ...)
            plumbing_signoff = S.register('building.approval.signoff.plumbing', ...)
            inspection_signoff = S.register('building.approval.signoff.inspection', ...)
            final_approval = S.register('building.approval.signoff.final', ...)

            signing_order = SigningOrder(
                InSeries(
                    planning_signoff,
                    InParallel(
                        electrical_signoff,
                        plumbing_signoff,
                    )
                    AtLeastN(inspection_signoff, 1),
                    final_approval,
                )
            )

        class Building(Model):
            approvals = ApprovalSet(ConstructionApproval, stamp_set_accessor='permits')


    ``BuildingPermit.signatories`` is a "normal" ``ReverseManyToOneDescriptor`` instance to access the related Signets.
    ``ConstructionApproval().signing_order`` defines a SigningOrderManager to match pattern with the stamp's signets.
    ``Building().approvals`` is an ApprovalSetManager instance providing a unified API for accessing the set
            of approvals, backed by building instance.permits.

    See ApprovalSetManager for access API.
    """
    def __init__(self, approval_type: Union[str, Type[AbstractApproval]] = None,
                 stamp_set_accessor='stamp_set', **kwargs):
        """
        Inject ApprovalSetManager; kwargs passed directly through to ApprovalSetManager.__init__
        approval_type may be an Approval Type class or a registered approval id
        """
        self._approval_type = approval_type
        self.stamp_set_accessor = stamp_set_accessor
        self.accessor_field_name = ''  # set by __set_name__
        self.kwargs = kwargs

    def __set_name__(self, owner, name):
        """ Grab the field named used by owning class to refer to this descriptor """
        self.accessor_field_name = name

    @staticmethod
    def _is_valid_approval_type(approval_type):
        # noinspection PyTypeChecker
        return approval_type is not None and \
               issubclass(approval_type, AbstractApproval) and \
               issubclass(approval_type.get_stampModel(), AbstractApprovalStamp) and \
               approval_type.has_object_relation()

    @cached_property
    def approval_type(self):
        approval_type = registry.get_approval_type(self._approval_type)
        if self._is_valid_approval_type(approval_type):
            return approval_type
        else:
            raise ImproperlyConfigured(
                'ApprovalField - Approval Type {type} must have a Stamp with a relation'.format(type=approval_type)
            )

    def _validate_related_manager(self, instance):
        """ Raises ImproperlyConfigured if the stamp_set_accessor is not a relation to a Stamp Manager or queryset """
        try:
            stamp_set = getattr(instance, self.stamp_set_accessor)
            stamp_model = self.approval_type.get_stampModel()
        except AttributeError:
            raise ImproperlyConfigured(
                'ApprovalSet.stamp_set_accessor "{p}" does not exist on related model {m}.'.format(
                    p=self.stamp_set_accessor, m=type(instance)))
        related_models = [ro.related_model for ro in instance._meta.related_objects]
        if stamp_set.model not in related_models or stamp_set.model is not stamp_model:
            raise ImproperlyConfigured(
                'ApprovalSet.stamp_set_accessor "{p}" must be a related {pm} to {m}.'.format(
                    p=self.stamp_set_accessor, pm=stamp_model, m=type(instance)))

    def __get__(self, instance, owner=None):
        """
        Use the enclosing instance to construct a ApprovalSetManager instance,
          then replace descriptor with that object
        """
        if instance is None:  # class access - provide access to the Approval Type itself
            return self.approval_type
        else:  # on instance, replace descriptor with related signoff manager.  Voilà!
            approval_set = getattr(instance, self.stamp_set_accessor)
            approval_manager = ApprovalSetManager(self.approval_type, approval_set)
            setattr(instance, self.accessor_field_name, approval_manager)
            return approval_manager
