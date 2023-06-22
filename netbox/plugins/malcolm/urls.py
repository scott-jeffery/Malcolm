from django.urls import path
from . import models, views

urlpatterns = (
    path('file-hash/', views.FileHashListView.as_view(), name='filehash_list'),
    path('file-hash/add/', views.FileHashEditView.as_view(), name='filehash_add'),
    path('file-hash/<int:pk>/', views.FileHashView.as_view(), name='filehash'),
    path('file-hash/<int:pk>/edit/', views.FileHashEditView.as_view(), name='filehash_edit'),
    path('file-hash/<int:pk>/delete/', views.FileHashDeleteView.as_view(), name='filehash_delete'),

    path('software/', views.SoftwareInstallationListView.as_view(), name='software_list'),
    path('software/add/', views.SoftwareInstallationEditView.as_view(), name='software_add'),
    path('software/<int:pk>/', views.SoftwareInstallationView.as_view(), name='software'),
    path('software/<int:pk>/edit/', views.SoftwareInstallationEditView.as_view(), name='software_edit'),
    path('software/<int:pk>/delete/', views.SoftwareInstallationDeleteView.as_view(), name='software_delete')
)