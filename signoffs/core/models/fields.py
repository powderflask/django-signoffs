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
    def __init__(self, signoff_type, signet_name):
        """ Manage a OneToOne Signet field  with signet_name using the given Signoff Type or signoff id """
        self._signoff_type = signoff_type
        self.signet_name = signet_name

    @property
    def base_signoff_type(self):
        return registry.get_signoff_type(self._signoff_type)

    def __get__(self, instance, owner=None):

        class RelatedSignoff(self.base_signoff_type):
            signet_name = self.signet_name
            """ A Signoff that is aware of a "reverse" one-to-one relation to the instance object """
            def save(self, *args, **kwargs):
                """ Save the related signet and then the instance relation """
                signoff = super().save(*args, **kwargs)
                setattr(instance, self.signet_name, signoff.signet)
                instance.save()
                return signoff

        if not instance:
            return RelatedSignoff
        else:
            return RelatedSignoff(signet=getattr(instance, self.signet_name))


class SignoffOneToOneField(models.OneToOneField):
    """
    A forward One-to-One relation to a single Signoff, backed by a OneToOneField to the Signoff's Signet model.
    Injects a RelatedSignoffDescriptor that provides signoff services for managing the OneToOne Signet relation.
    Access to the underlying OneToOneField is available on the model via signet_field_name or RelatedSignoffDescriptor

    In the example::

        from signoffs.signoffs import SimpleSignoff

        applicant_signoff = SimpleSignoff.register('myapp.signoff.applicant', ...)

        class Application(models.Model):
            # ...
            applicant_signoff = SignoffOneToOneField(applicant_signoff.signetModel, on_delete=models.SET_NULL,
                                             signoff_type=applicant_signoff,
                                             null=True, related_name='application')


    ``Application.applicant_signoff_signet`` is a "normal" One-to-One relation to the Signet model
    ``Application().applicant_signoff_signet`` is a Signet instance or None (if signoff is not  signed)

    ``Application.applicant_signoff`` is a RelatedSignoffDescriptor that ultimately injects a Signoff instance
    ``Application().applicant_signoff`` is a Signoff instance of the given signoff_type backed by the OneToOne Signet
            relation.  This Signoff will update the application's OneToOne relation whenever it is save()'ed

    """
    signoff_descriptor_class = RelatedSignoffDescriptor
    signet_field_suffix = '_signet' # suffix for name of actual one-to-one relational field to the Signet model

    def __init__(self, to, on_delete, signoff_type, signet_field_name=None, **kwargs):

        """
        In practice, use SignoffField convenience function to instantiate a SignoffOneToOneField instance.
        signoff_type is a Signoff Type with a signetModel == to
        Name to use for backing OneToOne field on model will be signet_field_name, default name is: '{fld}_signet'
        "to" MUST match signoff_type.signetModel
        null=True, on_delete=SET_NULL make sensible defaults for a Signet relation since presence/absence is semantic;
            think twice before using other values!
        reverse related_name from Signet generally not so useful, consider disabling with '+'
        """
        self.signoff_type = signoff_type
        self.signet_field_name = signet_field_name
        self._validate_related_model(to, self.signoff_type)
        super().__init__(to, on_delete, **kwargs)

    def _validate_related_model(self, to, signoff_type):
        """ Raises ImproperlyConfigured if the to model relation is not same as the signoff_type Signet model """
        if isinstance(signoff_type, str) and signoff_type not in registry.signoffs:
            # allow signoff_type to be deferred so field can be defined before signoff is registered,
            # but then no way to validate b/c can't get the related signetModel.  Cross fingers?
            return

        signoff_type = registry.get_signoff_type(signoff_type)
        signet = signoff_type.get_signetModel()
        signet, related = (signet._meta.label_lower, to.lower()) if isinstance(to, str) else (signet, to)
        if related != signet:
            raise ImproperlyConfigured(
                'SignoffOneToOneField "to" model {m} must match the signoff_type SignetModel {s} '
                '- use convenience method "SignoffField" to handle this.'.format(
                    m=to, s=signoff_type.get_signetModel())
            )

    def _get_signet_field_name(self, base_name):
        """ This is a bit hacky - build a default field name for related signet, but needs to be idempotent """
        return self.signet_field_name if self.signet_field_name \
            else base_name if base_name.endswith(self.signet_field_suffix) \
            else '{base}{suffix}'.format(base=base_name, suffix=self.signet_field_suffix)

    def contribute_to_class(self, cls, name, private_only=False, **kwargs):
        """ Contributes 2 items to the cls - this OneToOneField for Signet + a RelatedSignoffDescriptor """
        signet_name = self._get_signet_field_name(name)
        super().contribute_to_class(cls, signet_name, private_only=private_only, **kwargs)
        setattr(cls, name, self.signoff_descriptor_class(self.signoff_type, signet_name))

    def deconstruct(self):
        name, path, args, kwargs = super().deconstruct()
        kwargs['signoff_type'] = self.signoff_type if isinstance(self.signoff_type, str) else self.signoff_type.id
        kwargs['signet_field_name'] = self.signet_field_name
        return name, path, args, kwargs


def SignoffField(signoff_type, signet_field_name=None,
                 on_delete=models.SET_NULL, null=True, related_name='+', **kwargs):
    """
    Convenience method for constructing a sensible SignoffOneToOneField from minimal inputs.
    signoff_type may be a Signoff Type or a registered(!) signoff id
    See SignoffOneToOneField for default values rationale; kwargs are passed through to OneToOneField

    In the example given for SignoffOneToOneField::

        class Application(models.Model):
            # ...
            applicant_signoff = SignoffField(signoff_type='myapp.signoff.applicant', related_name='application')
    """
    try:
        signoff_type = registry.get_signoff_type(signoff_type)
    except ImproperlyConfigured:
        raise ImproperlyConfigured(
            'SignoffField: signoff_type {s} must be registered before it can be used to form a relation. '
            '"SignoffOneToOneField" can be used to form relation to Signet Model with a deferred signoff id.'.format(
                s=signoff_type)
        )
    # Intentionally using raw .signetModel, (possibly a str: 'app_label.model_name'), so use can avoid circular imports
    return SignoffOneToOneField(signoff_type.signetModel, on_delete=on_delete,
                                signoff_type=signoff_type, signet_field_name=signet_field_name,
                                null=null, related_name=related_name, **kwargs)


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
        (which may be None, i.e. uninitiated Approval)
    """
    def __init__(self, approval_type, stamp_name, callback_manager):
        """ Manage a OneToOne Stamp field  with stamp_name using the given Approval Type or approval id """
        self._approval_type = approval_type
        self.stamp_name = stamp_name
        self.callbacks = callback_manager

    @property
    def base_approval_type(self):
        return registry.get_approval_type(self._approval_type)

    def __get__(self, instance, owner=None):

        class BaseRelatedApproval(self.callbacks.decorate_approval(instance, self.base_approval_type)):
            """ An Approval that is aware of a "reverse" one-to-one relation to the instance object """
            stamp_name = self.stamp_name
            _callbacks = self.callbacks

            def save(self, *args, **kwargs):
                """ Save the related stamp and then the instance relation """
                approval = super().save(*args, **kwargs)
                if not getattr(instance, self.stamp_name) == approval.stamp:
                    setattr(instance, self.stamp_name, approval.stamp)
                    instance.save()
                return approval

        RelatedApproval = type('Related{}'.format(self.base_approval_type.__name__), (BaseRelatedApproval,), {})

        if not instance:
            return self.base_approval_type
        else:
            stamp = getattr(instance, self.stamp_name)
            approval = RelatedApproval(stamp=stamp)
            if not stamp:
                approval.save()
            return approval


class ApprovalOneToOneField(models.OneToOneField):
    """
    A forward One-to-One relation to a single Approval, backed by a OneToOneField to the Approval's Stamp model.
    Injects a RelatedApprovalDescriptor that provides approval services for managing the OneToOne Stamp relation.
    Access to the underlying OneToOneField is available on the model via stamp_field_name or RelatedApprovalDescriptor

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

        class Application(models.Model):
            # ...
            approval = ApprovalOneToOneField(ApplicationApproval.stampModel, on_delete=models.SET_NULL,
                                             approval_type=ApplicationApproval
                                             null=True, related_name='application')


    ``Application.approval_stamp`` is a "normal" One-to-One relation to the backing Stamp model
    ``Application().approval_stamp`` is a Stamp instance or None (if approval is not initiated)

    ``Application.approval`` is a RelatedApprovalDescriptor that ultimately injects an ApplicationApproval instance
    ``Application().approval`` is an ApplicationApproval instance, backed by the OneToOne Stamp relation.
            This Approval will update the application's OneToOne relation whenever it is save()'ed

    """
    approval_descriptor_class = RelatedApprovalDescriptor
    callback_manager_class = ApprovalCallbacksManager
    stamp_field_suffix = '_stamp' # suffix for name of actual one-to-one relational field to the underlying Stamp model

    def __init__(self, to, on_delete, approval_type, stamp_field_name=None, **kwargs):

        """
        In practice, use ApprovalField convenience function to instantiate an ApprovalOneToOneField instance.
        approval_type is an Approval Type with a stampModel == to
        Name to use for backing OneToOne field on model will be stamp_field_name, default name is: '{fld}_stamp'
        "to" MUST match approval_type.stampModel
        null=True, on_delete=SET_NULL make sensible defaults for a Stamp relation since presence/absence is semantic;
            think twice before using other values!
        reverse related_name from Stamp generally not so useful, consider disabling with '+'
        """
        self.approval_type = approval_type
        self.stamp_field_name = stamp_field_name
        self.callback = self.callback_manager_class()
        self._validate_related_model(to, self.approval_type)
        super().__init__(to, on_delete, **kwargs)

    def _validate_related_model(self, to, approval_type):
        """ Raises ImproperlyConfigured if the to model relation is not same as the approval_type Signet model """
        if isinstance(approval_type, str) and approval_type not in registry.approvals:
            # allow approval_type to be deferred so field can be defined before approval is registered,
            # but then no way to validate b/c can't get the related stampModel.  Cross fingers?
            return

        approval_type = registry.get_approval_type(approval_type)
        stamp = approval_type.get_stampModel()
        stamp, related = (stamp._meta.label_lower, to.lower()) if isinstance(to, str) else (stamp, to)
        if related != stamp:
            raise ImproperlyConfigured(
                'ApprovalOneToOneField "to" model {m} must match the approval_type Stamp Model {p} '
                '- use convenience method "ApprovalField" to handle this.'.format(
                    m=to, p=approval_type.get_stampModel())
            )
        # TODO: also validate that stamp has a 'signatories' relation and, ideally, all signing_order terms
        #       have a relation to stamp.

    def _get_stamp_field_name(self, base_name):
        """ This is a bit hacky - build a default field name for related stamp, but needs to be idempotent """
        return self.stamp_field_name if self.stamp_field_name \
            else base_name if base_name.endswith(self.stamp_field_suffix) \
            else '{base}{suffix}'.format(base=base_name, suffix=self.stamp_field_suffix)

    def contribute_to_class(self, cls, name, private_only=False, **kwargs):
        """ Contributes 2 items to the cls - this OneToOneField for Stamp + a RelatedApprovalDescriptor """
        stamp_name = self._get_stamp_field_name(name)
        super().contribute_to_class(cls, stamp_name, private_only=private_only, **kwargs)
        setattr(cls, name, self.approval_descriptor_class(self.approval_type, stamp_name, self.callback))

    def deconstruct(self):
        name, path, args, kwargs = super().deconstruct()
        kwargs['approval_type'] = self.approval_type if isinstance(self.approval_type, str) else self.approval_type.id
        kwargs['stamp_field_name'] = self.stamp_field_name
        return name, path, args, kwargs


def ApprovalField(approval_type, stamp_field_name=None,
                  on_delete=models.SET_NULL, null=True, related_name='+', **kwargs):
    """
    Convenience method for constructing a sensible ApprovalOneToOneField from minimal inputs.
    approval_type may be an Approval Type or a registered(!) approval id.
    See ApprovalOneToOneField for default values rationale; kwargs are passed through to OneToOneField

    In the example given for ApprovalOneToOneField::

        class Application(models.Model):
            # ...
            approval = ApprovalField(approval_type='myapp.application_approval', related_name='application')
    """
    try:
        approval_type = registry.get_approval_type(approval_type)
    except ImproperlyConfigured:
        raise ImproperlyConfigured(
            'ApprovalField: approval_type {a} must be registered before it can be used to form a relation. '
            '"ApprovalOneToOneField" can be used to form relation to Stamp Model with a deferred approval id.'.format(
                a=approval_type)
        )
    # Intentionally using raw .stampModel, (possibly 'app_label.model_name' str), so use can avoid circular imports
    return ApprovalOneToOneField(approval_type.stampModel, on_delete=on_delete,
                                 approval_type=approval_type, stamp_field_name=stamp_field_name,
                                 null=null, related_name=related_name, **kwargs)


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
