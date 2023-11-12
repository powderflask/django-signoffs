"""
Django settings for django-signoffs tests.
"""
import os

ALLOWED_HOSTS = ("127.0.0.1", "localhost")

SECRET_KEY = "django-insecure"
DEBUG = True

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

INSTALLED_APPS = (
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.auth",
    "django.contrib.admin",
    "django.contrib.messages",
    "django_fsm",
    "django.contrib.staticfiles",
    # project apps
    "signoffs",
    "signoffs.contrib.signets",
    "signoffs.contrib.approvals",
    "tests.test_app",
    "demo",
    "demo.article",
    "demo.assignments",
    "demo.registration",
)

MIDDLEWARE = [
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
]

ROOT_URLCONF = "tests.test_app.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": os.path.join(BASE_DIR, "db.sqlite3"),
        "TEST": {
            "NAME": None,  # use in-memory test DB
            "MIGRATE": False,  # Django 3.1+ -- disable migrations, create test DB schema directly from models.
        },
    }
}


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/3.2/howto/static-files/

STATIC_URL = "/static/"

# Default primary key field type
# https://docs.djangoproject.com/en/3.2/ref/settings/#default-auto-field

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

USE_TZ = True  # stifle django 5 deprecation warning
