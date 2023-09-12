from django.urls import converters


class SignoffIdConverter(converters.SlugConverter):
    regex = "[-a-zA-Z0-9_.]+"  # a slug with the dot character


converters.register_converter(SignoffIdConverter, "id")


app_name = "signoffs"


urlpatterns = []
