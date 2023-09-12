"""
    Test fixture factories for signoff models
"""
import uuid
from functools import partial

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType

User = get_user_model()
auth_content_type = partial(ContentType.objects.get_for_model, User)


def get_perm(codename, name=None, content_type=None):
    """Get or create and return a permission with given codename"""
    name = name or codename.title()
    content_type = content_type or auth_content_type()
    perm, _ = Permission.objects.get_or_create(
        codename=codename,
        name=name,
        content_type=content_type,
    )
    return perm


def revoke_all_permissions(user):
    user.user_permissions.clear()


def revoke_permissions(user, *perms, content_type=None):
    content_type = content_type or auth_content_type()
    for perm in perms:
        if type(perm) is str:
            perm = get_perm(perm, content_type=content_type)
        user.user_permissions.remove(perm)


def grant_permissions(user, *perms, content_type=None):
    content_type = content_type or auth_content_type()
    for perm in perms:
        if type(perm) is str:
            perm = get_perm(perm, content_type=content_type)
        user.user_permissions.add(perm)


def get_user(
    first_name="Big",
    last_name="Bird",
    email="bigbird@example.com",
    username=None,
    password="password",
    perms=(),
    **kwargs,
):
    """
    Return a user object with given attributes and set of permissions
    """
    username = (
        username or str(uuid.uuid1())[:-10]
    )  # unique username if caller doesn't care
    user, created = User.objects.get_or_create(
        username=username,
        first_name=first_name,
        last_name=last_name,
        email=email,
        **kwargs,
    )
    if created:
        user.set_password(password)
        user.save()
    else:
        revoke_all_permissions(user)
    grant_permissions(user, *perms)
    # Add a few convenience methods to user object
    user.grant_permission = grant_permissions.__get__(user)
    user.revoke_permission = revoke_permissions.__get__(user)
    user.revoke_all_permissions = revoke_all_permissions.__get__(user)
    return user
