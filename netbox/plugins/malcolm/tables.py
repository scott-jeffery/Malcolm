import django_tables2 as tables

from netbox.tables import NetBoxTable, ChoiceFieldColumn
from .models import FileHash, SoftwareInstallation

class FileHashTable(NetBoxTable):
    FileName = tables.Column(
        linkify=True
    )
    class Meta(NetBoxTable.Meta):
        model = FileHash
        fields = ('pk', 'FileName', 'FileHash', 'HashAlgorithm', 'actions')
        default_columns = ('FileName', 'FileHash', 'HashAlgorithm')

class SoftwareInstallationTable(NetBoxTable):
    Name = tables.Column(
        linkify=True
    )
    class Meta(NetBoxTable.Meta):
        model = FileHash
        fields = ('pk', 'Name', 'Manufacturer', 'Version', 'PatchNumber', 'CPE', 'ModelNumber', 'PackageURL', 'SBOM_URL', 'SerialNumber', 'SKU', 'URI_Namespace', 'URI', 'FileHashes', 'actions')
        default_columns = ('Name', 'Manufacturer', 'Version', 'PatchNumber', 'ModelNumber', 'SerialNumber')