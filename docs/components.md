# <a name="Components"></a>Components

Malcolm leverages the following excellent open source tools, among others.

* [Arkime](https://arkime.com/) (formerly Moloch) – for PCAP file processing, browsing, searching, analysis, and carving/exporting; Arkime consists of two parts:
    * [capture](https://github.com/arkime/arkime/tree/master/capture) – a tool for traffic capture, as well as offline PCAP parsing and metadata insertion into OpenSearch
    * [viewer](https://github.com/arkime/arkime/tree/master/viewer) - a browser-based interface for data visualization
* [OpenSearch](https://opensearch.org/) - a search and analytics engine for indexing and querying network traffic session metadata 
* [Logstash](https://www.elastic.co/products/logstash) and [Filebeat](https://www.elastic.co/products/beats/filebeat) - for ingesting and parsing [Zeek](https://www.zeek.org) [Log Files](https://docs.zeek.org/en/stable/script-reference/log-files.html) and ingesting them into OpenSearch in a format that Arkime understands in the same way it natively understands PCAP data
* [OpenSearch Dashboards](https://opensearch.org/docs/latest/dashboards/index/) - for creating additional ad-hoc visualizations and dashboards beyond that provided by Arkime viewer
* [Zeek](https://www.zeek.org) - a network analysis framework and IDS
* [Suricata](https://suricata.io/) - an IDS and threat detection engine
* [Yara](https://github.com/VirusTotal/yara) - a tool used to identify and classify malware samples
* [Capa](https://github.com/fireeye/capa) - a tool for detecting capabilities in executable files
* [ClamAV](https://www.clamav.net/) - an antivirus engine for scanning files extracted by Zeek
* [CyberChef](https://github.com/gchq/CyberChef) - a "Swiss Army Knife" data conversion tool 
* [jQuery File Upload](https://github.com/blueimp/jQuery-File-Upload) - for uploading PCAP files and Zeek logs for processing
* Providing application containerization and orchestration for simple, reproducible deployment of Malcolm across environments and coordination of communication between its various components, either of the following may be used:
    - [Docker](https://www.docker.com/)
    - [Podman](https://podman.io/)
        - It should be noted that if rootless Podman is used, Malcolm itself cannot perform [traffic capture on local network interfaces](live-analysis.md#LocalPCAP), although it can accept network traffic metadata forwarded from a [a network sensor appliance](live-analysis.md#Hedgehog).
* [NetBox](https://netbox.dev/) - a suite for modeling and documenting modern networks
* [PostgreSQL](https://www.postgresql.org/) - a relational databased used for storing configuration and state for a few other Malcolm components
* [Redis](https://redis.io/) - an in-memory data store for caching session information for a few Malcolm components
* [Keycloak](https://www.keycloak.org/) - an identity and access management (IAM) tool
* [OpenResty](https://openresty.org/) - a dynamic web platform based on [Nginx](https://nginx.org/) and [LuaJIT](http://luajit.org/) for HTTPS and reverse proxying Malcolm components
* [nginx-auth-ldap](https://github.com/kvspb/nginx-auth-ldap) - an LDAP authentication module for nginx
* [Fluent Bit](https://fluentbit.io/) - for forwarding metrics to Malcolm from [network sensors](live-analysis.md#Hedgehog) (packet capture appliances)
* [Mark Baggett](https://github.com/MarkBaggett)'s [freq](https://github.com/MarkBaggett/freq) - a tool for calculating entropy of strings
* [Florian Roth](https://github.com/Neo23x0)'s [Signature-Base](https://github.com/Neo23x0/signature-base) Yara ruleset
* [Bart Blaze](https://github.com/bartblaze)'s [Yara ruleset](https://github.com/bartblaze/Yara-rules)
* [ReversingLabs'](https://github.com/reversinglabs) [Yara ruleset](https://github.com/reversinglabs/reversinglabs-yara-rules)
* These [Zeek packages]({{ site.github.repository_url }}/blob/{{ site.github.build_revision }}/shared/bin/zeek_install_plugins.sh):
    * some of Amazon.com, Inc.'s [ICS protocol](https://github.com/amzn?q=zeek) analyzers
    * Andrew Klaus's [Sniffpass](https://github.com/cybera/zeek-sniffpass) plugin for detecting cleartext passwords in HTTP POST requests
    * Andrew Klaus's [zeek-httpattacks](https://github.com/precurse/zeek-httpattacks) plugin for detecting noncompliant HTTP requests
    * ICS protocol analyzers for Zeek published by [DHS CISA](https://github.com/cisagov/ICSNPP) and [Idaho National Lab](https://github.com/idaholab/ICSNPP)
    * Many packages developed by [Corelight, Inc.](https://github.com/corelight)
    * FoxIO's [JA4+](https://blog.foxio.io/ja4%2B-network-fingerprinting) network fingerprinting plugin
    * J-Gras' [Zeek::AF_Packet](https://github.com/J-Gras/zeek-af_packet-plugin) plugin
    * Johanna Amann's [CVE-2020-0601](https://github.com/0xxon/cve-2020-0601) ECC certificate validation plugin and [CVE-2020-13777](https://github.com/0xxon/cve-2020-13777) GnuTLS unencrypted session ticket detection plugin
    * Lexi Brent's [EternalSafety](https://github.com/0xl3x1/zeek-EternalSafety) plugin
    * MITRE Cyber Analytics Repository's [Bro/Zeek ATT&CK®-Based Analytics (BZAR)](https://github.com/mitre-attack/car/tree/master/implementations) script
    * [ATT&CK-based Control-system Indicator Detection (ACID)](https://github.com/cisagov/acid) indicators published by DHS and MITRE
    * Salesforce's [gQUIC](https://github.com/salesforce/GQUIC_Protocol_Analyzer) analyzer
    * Zeek's [Spicy](https://github.com/zeek/spicy) plugin framework
* [GeoLite2](https://dev.maxmind.com/geoip/geoip2/geolite2/) - Malcolm includes GeoLite2 data created by [MaxMind](https://www.maxmind.com)

![Malcolm Components](./images/malcolm_components.png)