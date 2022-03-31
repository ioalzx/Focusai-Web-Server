from django.urls import path

from . import views

urlpatterns = [
    path('create_session', views.create_session, name='create_session'),
    path('upload_image', views.upload_image, name='upload_image'),
    path('edit_image', views.edit_image, name='edit_image'),
]