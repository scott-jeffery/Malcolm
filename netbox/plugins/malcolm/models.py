from django.contrib.postgres.fields import ArrayField
from django.db import models
from netbox.models import NetBoxModel

class FileHash(NetBoxModel):
    FileName = models.CharField(max_length=100)
    FileHash = models.CharField(max_length=100)
    HashAlgorithm = models.CharField(max_length=100)

class SoftwareInstallation(NetBoxModel):
    Name = models.CharField(max_length=300)
    Manufacturer = models.CharField(max_length=300)
    Version = models.CharField(max_length=100)
    PatchNumber = models.CharField(max_length=100)

class ProductIdentificationHelpers(NetBoxModel):
    CPE = models.CharField(max_length=100)
    ModelNumber = models.CharField(max_length=100)
    PackageURL = models.CharField(max_length=300)
    SBOM_URL = models.CharField(max_length=300)
    SerialNumber = models.CharField(max_length=300)
    SKU = models.CharField(max_length=300)
    URI_Namespace = models.CharField(max_length=300)
    URI = models.CharField(max_length=300)
    FileHashes = ArrayField(models.CharField(max_length=300))