from django.shortcuts import render
from django.views.generic import View
from . import forms, models, tables
from netbox.views import generic

class FileHashView(generic.ObjectView):
    queryset = models.FileHash.objects.all()

class FileHashListView(generic.ObjectListView):
    queryset = models.FileHash.objects.all()
    table = tables.FileHashTable

class FileHashEditView(generic.ObjectEditView):
    queryset = models.FileHash.objects.all()

class FileHashDeleteView(generic.ObjectDeleteView):
    queryset = models.FileHash.objects.all()

class SoftwareInstallationView(generic.ObjectView):
    queryset = models.SoftwareInstallation.objects.all()

class SoftwareInstallationListView(generic.ObjectListView):
    queryset = models.SoftwareInstallation.objects.all()
    table = tables.SoftwareInstallationTable

class SoftwareInstallationEditView(generic.ObjectEditView):
    queryset = models.SoftwareInstallation.objects.all()
    form = forms.SoftwareInstallationForm

class SoftwareInstallationDeleteView(generic.ObjectDeleteView):
    queryset = models.SoftwareInstallation.objects.all()