from netbox.forms import NetBoxModelForm
from .models import FileHash, SoftwareInstallation

class FileHashForm(NetBoxModelForm):
    class Meta:
        model = FileHash
        fields = ('FileName', 'FileHash', 'HashAlgorithm')

class SoftwareInstallationForm(NetBoxModelForm):
    class Meta:
        model = SoftwareInstallation
        fields = ('Name', 'Manufacturer', 'Version', 'PatchNumber', 'CPE', 'ModelNumber', 'PackageURL', 'SBOM_URL', 'SerialNumber', 'SKU', 'URI_Namespace', 'URI')