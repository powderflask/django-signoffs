from django.contrib import admin

from signoffs.contrib.signets.models import RevokedSignet, Signet
from .models import Article, ArticleSignet, Comment, LikeSignet

# Signoffs Models

admin.site.register(Signet)
admin.site.register(RevokedSignet)
admin.site.register(LikeSignet)


# Article Models

admin.site.register(Article)
admin.site.register(ArticleSignet)
admin.site.register(Comment)
