#!/usr/bin/env zeek

# Copyright (c) 2025 Battelle Energy Alliance, LLC.  All rights reserved.

export {
  redef extractor_always_extract_unknown = F;

  redef extractor_mime_to_ext_map : table[string] of string = {
    ["application/binary"]= "bin",
    ["application/ecmascript"]= "es",
    ["application/hta"]= "hta",
    ["application/java-archive"]= "jar",
    ["application/java-serialized-object"]= "ser",
    ["application/java-vm"]= "class",
    ["application/javascript"]= "js",
    ["application/ms-vsi"]= "vsi",
    ["application/msaccess"]= "accdb",
    ["application/msaccess.addin"]= "accda",
    ["application/msaccess.cab"]= "accdc",
    ["application/msaccess.ftemplate"]= "accft",
    ["application/msaccess.runtime"]= "accdr",
    ["application/msaccess.webapplication"]= "accdw",
    ["application/msexcel"]= "xls",
    ["application/mspowerpoint"]= "ppt",
    ["application/msword"]= "doc",
    ["application/octet-stream"]= "bin",
    ["application/pdf"]= "pdf",
    ["application/PowerShell"]= "psc1",
    ["application/rtf"]= "rtf",
    ["application/vnd.apple.installer+xml"]= "mpkg",
    ["application/vnd.microsoft.portable-executable"]= "exe",
    ["application/vnd.ms-cab-compressed"]= "cab",
    ["application/vnd.ms-excel"]= "xls",
    ["application/vnd.ms-excel.addin.macroEnabled.12"]= "xlam",
    ["application/vnd.ms-excel.addin.macroenabled.12"]= "xlam",
    ["application/vnd.ms-excel.sheet.binary.macroEnabled.12"]= "xlsb",
    ["application/vnd.ms-excel.sheet.binary.macroenabled.12"]= "xlsb",
    ["application/vnd.ms-excel.sheet.macroEnabled.12"]= "xlsm",
    ["application/vnd.ms-excel.sheet.macroenabled.12"]= "xlsm",
    ["application/vnd.ms-excel.template.macroEnabled.12"]= "xltm",
    ["application/vnd.ms-excel.template.macroenabled.12"]= "xltm",
    ["application/vnd.ms-office.calx"]= "calx",
    ["application/vnd.ms-officetheme"]= "thmx",
    ["application/vnd.ms-powerpoint"]= "ppt",
    ["application/vnd.ms-powerpoint.addin.macroEnabled.12"]= "ppam",
    ["application/vnd.ms-powerpoint.addin.macroenabled.12"]= "ppam",
    ["application/vnd.ms-powerpoint.presentation.macroEnabled.12"]= "pptm",
    ["application/vnd.ms-powerpoint.presentation.macroenabled.12"]= "pptm",
    ["application/vnd.ms-powerpoint.slide.macroEnabled.12"]= "sldm",
    ["application/vnd.ms-powerpoint.slide.macroenabled.12"]= "sldm",
    ["application/vnd.ms-powerpoint.slideshow.macroEnabled.12"]= "ppsm",
    ["application/vnd.ms-powerpoint.slideshow.macroenabled.12"]= "ppsm",
    ["application/vnd.ms-powerpoint.template.macroEnabled.12"]= "potm",
    ["application/vnd.ms-powerpoint.template.macroenabled.12"]= "potm",
    ["application/vnd.ms-word.document.macroEnabled.12"]= "docm",
    ["application/vnd.ms-word.document.macroenabled.12"]= "docm",
    ["application/vnd.ms-word.template.macroEnabled.12"]= "dotm",
    ["application/vnd.ms-word.template.macroenabled.12"]= "dotm",
    ["application/vnd.openofficeorg.extension"]= "oxt",
    ["application/vnd.openxmlformats-officedocument.presentationml.presentation"]= "pptx",
    ["application/vnd.openxmlformats-officedocument.presentationml.slide"]= "sldx",
    ["application/vnd.openxmlformats-officedocument.presentationml.slideshow"]= "ppsx",
    ["application/vnd.openxmlformats-officedocument.presentationml.template"]= "potx",
    ["application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"]= "xlsx",
    ["application/vnd.openxmlformats-officedocument.spreadsheetml.template"]= "xltx",
    ["application/vnd.openxmlformats-officedocument.wordprocessingml.document"]= "docx",
    ["application/vnd.openxmlformats-officedocument.wordprocessingml.template"]= "dotx",
    ["application/windows-library+xml"]= "library-ms",
    ["application/x-7z-compressed"]= "7z",
    ["application/x-ace-compressed"]= "ace",
    ["application/x-apple-diskimage"]= "dmg",
    ["application/x-bzip"]= "bz",
    ["application/x-bzip2"]= "bz2",
    ["application/x-cfs-compressed"]= "cfs",
    ["application/x-compress"]= "z",
    ["application/x-compressed"]= "tgz",
    ["application/x-cpio"]= "cpio",
    ["application/x-csh"]= "csh",
    ["application/x-dgc-compressed"]= "dgc",
    ["application/x-dosexec"]= "exe",
    ["application/x-elf"]= "elf",
    ["application/x-executable"]= "exe",
    ["application/x-gca-compressed"]= "gca",
    ["application/x-gtar"]= "gtar",
    ["application/x-gzip"]= "gz",
    ["application/x-install-instructions"]= "install",
    ["application/x-lzh-compressed"]= "lzh",
    ["application/x-ms-application"]= "application",
    ["application/x-ms-evtx"]= "evtx",
    ["application/x-ms-installer"]= "msi",
    ["application/x-ms-shortcut"]= "lnk",
    ["application/x-msdos-program"]= "exe",
    ["application/x-msdownload"]= "exe",
    ["application/x-pe-app-32bit-i386"]= "exe",
    ["application/x-perl"]= "pl",
    ["application/x-python"]= "py",
    ["application/x-rar-compressed"]= "rar",
    ["application/x-sh"]= "sh",
    ["application/x-shockwave-flash"]= "swf",
    ["application/x-zip-compressed"]= "zip",
    ["application/zip"]= "zip",
    ["text/javascript"]= "js",
    ["text/jscript"]= "jsx",
    ["text/rtf"]= "rtf",
    ["text/vbscript"]= "vbs"
  } &default="dat";

}
