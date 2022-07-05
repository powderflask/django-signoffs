"""
Utility functions and classes
"""
import re
from django.core.exceptions import FieldDoesNotExist


split_caps_run = re.compile(r'(.)([A-Z][a-z]+)')
to_snake_case = re.compile(r'([a-z0-9])([A-Z])')
id_separators = re.compile(r'[_\-.]')


def camel_to_snake(name):
    """ Convert CamelCaseName to snake_case_name """
    # based on: https://stackoverflow.com/a/1176023/1993525
    name = split_caps_run.sub(r'\1_\2', name)
    return to_snake_case.sub(r'\1_\2', name).lower()


def id_to_camel(name):
    """ Convert arbitrary identifier using dot or snake notation into CamelCase """
    return ''.join(el[:1].capitalize() + el[1:] for el in re.split(id_separators, name))


class Accessor(str):
    """
    A string describing a path from one object to another via attributes accesses.
    Shamelessly adapted from the amazing django_tables2 https://pypi.org/project/django-tables2/

    Relations are separated by a ``__`` character.
    """
    SEPARATOR = "__"

    ALTERS_DATA_ERROR_FMT = "Refusing to call {method}() because `.alters_data = True`"
    LOOKUP_ERROR_FMT = (
        "Failed lookup for attribute [{attr}] in {obj}, when resolving the accessor `{accessor}`"
    )

    def resolve(self, obj, safe=True, quiet=False):
        """
        Return an attribute described by the accessor by traversing the attributes of object

        Callable objects are called, and their result is used, before proceeding with the resolving.

        Example::
            >>> from django.contrib.auth.models import User
            >>> user = User(first_name='Brad')
            >>> x = Accessor("user__first_name")
            >>> x.resolve(user)
            "Brad"

        Arguments:
            obj : The root object to traverse.
            safe (bool): Don't call anything with `alters_data = True`
            quiet (bool): Smother all exceptions and instead return `None`

        Returns:
            target object

        Raises:
            TypeError`, `AttributeError`, `KeyError`, `ValueError`
            (unless `quiet` == `True`)

        """
        # Short-circuit if the object has an attribute with the exact name of the accessor,
        try:
            return None if self == '' else getattr(obj, self)
        except AttributeError:
            try:
                current = obj
                for bit in self.bits:
                    try:
                        current = getattr(current, bit)
                    except AttributeError:
                        raise ValueError(self.LOOKUP_ERROR_FMT.format(attr=bit, obj=current, accessor=self))

                    if callable(current):
                        if safe and getattr(current, "alters_data", False):
                            raise ValueError(self.ALTERS_DATA_ERROR_FMT.format(method=repr(current)))
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
        return self.split(self.SEPARATOR) if self != '' else ()

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
        Split off the right-most separator and return a 2-tuple with:
            (the Accessor for the left part, the remainder right-part)

        Example::

            >>> Accessor("user__profile__title").penultimate_accessor()
            'user__profile', 'title'
       """
        path, _, remainder = self.rpartition(self.SEPARATOR)
        return Accessor(path), remainder

    def penultimate(self, obj, quiet=True):
        """
        Split the accessor on the right-most separator ('__'), return a 2-tuple with:
         (the resolved left part, the remainder right-part)

        Example::

            >>> Accessor("user__profile__title").penultimate(user)
            <Profile object>, 'title'

        """
        accessor, remainder = self.penultimate_accessor()
        return accessor.resolve(obj, quiet=quiet), remainder
