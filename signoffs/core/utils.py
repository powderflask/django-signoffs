"""
Utility functions and classes
"""
import re

from django.core.exceptions import FieldDoesNotExist

split_caps_run = re.compile(r"(.)([A-Z][a-z]+)")
to_snake_case = re.compile(r"([a-z0-9])([A-Z])")
id_separators = re.compile(r"[_\-.]")


def camel_to_snake(name):
    """Convert CamelCaseName to snake_case_name"""
    # based on: https://stackoverflow.com/a/1176023/1993525
    name = split_caps_run.sub(r"\1_\2", name)
    return to_snake_case.sub(r"\1_\2", name).lower()


def id_to_camel(name):
    """Convert arbitrary identifier using dot or snake notation into CamelCase"""
    return "".join(el[:1].capitalize() + el[1:] for el in re.split(id_separators, name))


class Accessor(str):
    """
    A string describing a path from one object to another via attributes accesses.

    Relations are separated by a ``__`` character.

    Shamelessly adapted from the amazing django_tables2 https://pypi.org/project/django-tables2/
    """

    SEPARATOR = "__"

    ALTERS_DATA_ERROR_FMT = "Refusing to call {method}() because `.alters_data = True`"
    LOOKUP_ERROR_FMT = "Failed lookup for attribute [{attr}] in {obj}, when resolving the accessor `{accessor}`"

    def resolve(self, obj, safe=True, quiet=False):
        """
        Return an attribute described by the accessor by traversing the attributes of object

        Callable objects are called, and their result is used, before proceeding with the resolving.
        Usage:
        ```
            >>> from django.contrib.auth.models import User
            >>> user = User(first_name='Brad')
            >>> x = Accessor("user__first_name")
            >>> x.resolve(user)
            "Brad"
        ```

        :param obj: The root object to traverse.
        :param bool safe: Don't call anything with `alters_data = True`
        :param bool quiet: Smother all exceptions and instead return `None`
        :return: resolved target object

        :raises TypeError, AttributeError, KeyError, ValueError: (unless `quiet` == `True`)
        """

        def traverse(current, bit):
            """Traverse to current.bit and return the result or raise ValueError if no such relation"""
            try:
                return getattr(current, bit)
            except AttributeError:
                raise ValueError(
                    self.LOOKUP_ERROR_FMT.format(attr=bit, obj=current, accessor=self)
                )

        def check_safe(item):
            """Raise ValueError if item is callable and item.alters_data but safe==True"""
            if callable(current) and safe and getattr(current, "alters_data", False):
                raise ValueError(
                    self.ALTERS_DATA_ERROR_FMT.format(method=repr(current))
                )

        # Short-circuit if the object has an attribute with the exact name of the accessor,
        try:
            return None if self == "" else getattr(obj, self)
        except AttributeError:
            try:
                current = obj
                for bit in self.bits:
                    current = traverse(current, bit)
                    check_safe(current)
                    # Important that we break in None case; otherwise a relationship spanning
                    #  a null-key will raise an exception in the next iteration, instead of defaulting.
                    if current is None:
                        break
                return current
            except Exception:
                if not quiet:
                    raise

    @property
    def bits(self):
        return self.split(self.SEPARATOR) if self != "" else ()

    def get_field(self, model):
        """
        Return the django model field for model in context, following relations.
        """
        if not hasattr(model, "_meta"):
            return

        field = None
        for bit in self.bits:
            try:
                field = model._meta.get_field(bit)
            except FieldDoesNotExist:
                break

            if hasattr(field, "remote_field"):
                rel = getattr(field, "remote_field", None)
                model = getattr(rel, "model", model)

        return field

    def penultimate_accessor(self):
        """
        Split off the right-most separator.

        :return: a 2-tuple (the Accessor for the left part, the remainder right-part)

        Usage:
        ```
            >>> Accessor("user__profile__title").penultimate_accessor()
            'user__profile', 'title'
        ```
        """
        path, _, remainder = self.rpartition(self.SEPARATOR)
        return Accessor(path), remainder

    def penultimate(self, obj, quiet=True):
        """
        Split the accessor on the right-most separator ('__'),

        :return: a 2-tuple (the resolved left part, the remainder right-part)

        Usage:
        ```
            >>> Accessor("user__profile__title").penultimate(user)
            <Profile object>, 'title'
        ```
        """
        accessor, remainder = self.penultimate_accessor()
        return accessor.resolve(obj, quiet=quiet), remainder


class ServiceDescriptor:
    """
    A descriptor used to "inject" instances of a "service" class into its owner's instances.

    A "service" provides services or strategies to its owner, but needs the owner instance to do its own work.
    Construction of the owner instance may not be under direct control, so service instantiation must be automated.
    Service class must expect owner instance as first positional parameter of its constructor.
    """

    service_class = None

    def __init__(self, service_class=None, **kwargs):
        """
        Inject `service_class` instance into the instance of the descriptor's owner class

        first positional arg for `service_class` initializer must be an instance of owner class
        `kwargs` are passed through to the `service_class` initializer
        """
        self.service_class = service_class or self.service_class
        self.service_class_kwargs = kwargs
        self.attr_name = ""  # set by __set_name__

    def __set_name__(self, owner, name):
        self.attr_name = name

    def __get__(self, instance, owner):
        if instance is None:
            return self.service_class
        else:
            service_obj = self.service_class(instance, **self.service_class_kwargs)
            setattr(instance, self.attr_name, service_obj)
            return service_obj


def service(service_class, **kwargs):
    """
    Factory to return specialized service descriptors.

    :return: a `ServiceDescriptor` for a specialized subclass of `service_class`, that has `kwargs` as class attributes

    Usage:
    ```
        >>> class Service:
        ...     service_type = 'generic'
        ...     def __init__(self, owner, extra=None):
        ...         self.owner = owner
        ...         self.extra = extra
        ...     def __str__(self):
        ...         extra = f' with {self.extra}' if self.extra else ''
        ...         return f'A {self.service_type} service for {self.owner}{extra}'
        ... class Owner:
        ...     a_service = service(Service, service_type='special')(extra="whazoo")
        ...     def __str__(self):
        ...         return 'Owner'
        ... o = Owner()
        ... assert str(o.a_service) == "A special service for Owner with whazoo"
    ```
    """
    specialized_service = type(service_class.__name__, (service_class,), kwargs)

    descriptor_name = f"{service_class.__name__}Service"
    descriptor = type(
        descriptor_name, (ServiceDescriptor,), dict(service_class=specialized_service)
    )
    return descriptor


class ClassServiceDescriptor:
    """
    A descriptor used to "inject" instances of a "service" class onto its owner class.

    This is analogous to `ServiceDescriptor` but service instance is available on owner class
    First positional parameter of `service_class` class must be an owner class (type not instance!)
    """

    service_class = None

    def __init__(self, service_class=None, **kwargs):
        """
        Inject `service_class` instance, initialized with owner class, into the descriptor's owner class

        first positional arg for `service_class` initializer must be an owner class type
        `kwargs` are passed through to the `service_class` initializer
        """
        self.service_class = service_class or self.service_class
        self.service_class_kwargs = kwargs
        self.attr_name = ""  # set by __set_name__

    def __set_name__(self, owner, name):
        self.attr_name = name

    def __get__(self, instance, owner):
        service_obj = self.service_class(owner, **self.service_class_kwargs)
        setattr(owner, self.attr_name, service_obj)
        return service_obj


def class_service(service_class, **kwargs):
    """
    Factory to return specialized class service descriptors.

    :return: a `ClassServiceDescriptor` for a specialized subclass of `service_class`,
    that has `kwargs` as class attributes
    """
    specialized_service = type(service_class.__name__, (service_class,), kwargs)

    descriptor_name = f"{service_class.__name__}ClassService"
    descriptor = type(
        descriptor_name,
        (ClassServiceDescriptor,),
        dict(service_class=specialized_service),
    )
    return descriptor


__all__ = [
    "service",
    "ServiceDescriptor",
    "class_service",
    "ClassServiceDescriptor",
]
