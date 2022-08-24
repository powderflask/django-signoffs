from django.urls import path, include
from django.contrib import admin

from . import views

urlpatterns = [
    path('', views.index, name='index'),
    path('content/<int:content_id>', views.content, name='content'),
    path('content/sign/<int:content_id>', views.sign_content, name='sign_content'),
    path('bikeracks/', views.bikeracks, name='bikeracks'),
    path('bikeracks/sign/<int:rack_id>', views.sign_bikerack, name='sign_bikerack'),
    path('bikeracks/requests/new/', views.request_new_bikerack, name='request_new_bikerack'),
    path('bikeracks/requests/pending/', views.pending_bikerack_requests, name='pending_bikerack_requests'),
    path('bikeracks/requests/approved/', views.approved_bikerack_requests, name='approved_bikerack_requests'),    
    path('bikeracks/requests/sign/<int:req_id>', views.sign_bikerack_requests, name='sign_bikerack_requests'),    
    path('admin/', admin.site.urls),
    path('accounts/', include('django.contrib.auth.urls')),
]
