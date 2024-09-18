from django.contrib import admin

from signoffs.models import Stamp, ApprovalSignet
from .models import Assignment

admin.site.register(Assignment)
admin.site.register(ApprovalSignet)
admin.site.register(Stamp)
