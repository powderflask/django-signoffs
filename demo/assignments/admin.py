from django.contrib import admin

from signoffs.models import Stamp

from .models import Assignment

admin.site.register(Assignment)
admin.site.register(Stamp)
