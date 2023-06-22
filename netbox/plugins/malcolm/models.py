from django.contrib.postgres.fields import ArrayField
from django.db import models
from netbox.models import NetBoxModel
from django.urls import reverse

class FileHash(NetBoxModel):
    FileName = models.CharFieldS(max_length=100)
    FileHash = models.CharField(max_length=100)
    HashAlgorithm = models.CharField(max_length=100)
    def get_absolute_url(self):
        return reverse('plugins:malcolm:filehash', args=[self.pk])

class SoftwareInstallation(NetBoxModel):
    Name = models.CharField(max_length=300, blank=True)
    Manufacturer = models.CharField(max_length=300, blank=True)
    Version = models.CharField(max_length=100, blank=True)
    PatchNumber = models.CharField(max_length=100, blank=True)
    CPE = models.CharField(max_length=100, blank=True)
    ModelNumber = models.CharField(max_length=100, blank=True)
    PackageURL = models.CharField(max_length=300, blank=True)
    SBOM_URL = models.CharField(max_length=300, blank=True)
    SerialNumber = models.CharField(max_length=300, blank=True)
    SKU = models.CharField(max_length=300, blank=True)
    URI_Namespace = models.CharField(max_length=800, blank=True)
    URI = models.CharField(max_length=800, blank=True)
    # FileHashes = ArrayField(models.ForeignKey(to='FileHash', on_delete=models.PROTECT, related_name='file_hashes'))
    def get_absolute_url(self):
        return reverse('plugins:malcolm:softwareintallation', args=[self.pk])