# <a name="InstallationExample"></a>Installation example using Ubuntu 24.04 LTS

Here's a step-by-step example of getting [Malcolm from GitHub]({{ site.github.repository_url }}/tree/{{ site.github.build_revision }}), configuring the local system and the Malcolm instance, and running it on a system running Ubuntu Linux. Installing Malcolm may require some variation depending on individual system configuration, but this should be a good starting point.

For a more in-depth guide convering installing both Malcolm and a [Hedgehog Linux](hedgehog.md) sensor using the [Malcolm installer ISO](malcolm-iso.md#ISO) and [Hedgehog Linux installer ISO](hedgehog-installation.md#HedgehogInstallation), see **[End-to-end Malcolm and Hedgehog Linux ISO Installation](malcolm-hedgehog-e2e-iso-install.md#InstallationExample)**.

The commands in this example should be executed as a non-root user except where clearly indicated with the use of `sudo`.

Malcolm can be installed from a git [working copy of the source code](development.md#Build) or the from [pre-packaged installation files](development.md#Packager) downloaded as artifacts from the [latest Malcolm release]({{ site.github.repository_url }}/releases/latest). The instructions for both methods are mostly the same, so both will shown here while indicating where the processes differ.

To install Malcolm from the latest Malcolm release artifacts, browse to the [Malcolm releases page on GitHub]({{ site.github.repository_url }}/releases/latest) and download the `malcolm_YYYYMMDD_HHNNSS_xxxxxxx_docker_install.zip` file, then navigate to the downloads directory and extract it. If your distribution does not have the `unzip` utility, you may need to install it with `sudo apt install unzip`.
```
user@host:~$ cd Downloads/
user@host:~/Downloads$ ls
malcolm_20250117_115650_d1867453_docker_install.zip
user@host:~/Downloads$ unzip malcolm_20250117_115650_d1867453_docker_install.zip
Archive:  malcolm_20250117_115650_d1867453_docker_install.zip
  inflating: install.py
  inflating: malcolm_20250117_115650_d1867453.README.txt
  inflating: malcolm_20250117_115650_d1867453.tar.gz
  inflating: malcolm_common.py
  inflating: malcolm_kubernetes.py
  inflating: malcolm_utils.py
```

If obtaining Malcolm using `git` instead, run the following command to clone Malcolm into a local working copy:
```
user@host:~$ git clone {{ site.github.repository_url }}
Cloning into 'Malcolm'...
remote: Enumerating objects: 45827, done.
remote: Counting objects: 100% (648/648), done.
remote: Compressing objects: 100% (190/190), done.
remote: Total 45827 (delta 538), reused 470 (delta 457), pack-reused 45179 (from 3)
Receiving objects: 100% (45827/45827), 186.07 MiB | 8.59 MiB/s, done.
Resolving deltas: 100% (33914/33914), done.
user@host:~$ cd Malcolm/
```

Next, use `sudo` to run the `install.py` script to configure the system. Replace `user` in this example with the local account username, and follow the prompts. Most questions have defaults that can be accepted by pressing the `Enter` key. Depending on whether Malcolm is being installed from the release artifacts (`install.py` just having been extracted from the `.zip` file) or inside of a git working copy (where it can be found in the `scripts` subdirectory), the questions below will be slightly different, but for the most part are the same.
```
user@host:~/Malcolm$ sudo ./scripts/install.py
1: docker
2: podman
Select container runtime engine (docker): 1
Installing required packages: ['apache2-utils', 'make', 'openssl', 'python3-dialog', 'python3-dotenv', 'python3-requests', 'python3-ruamel.yaml', 'xz-utils']

"docker info" failed, attempt to install Docker? (Y / n): y

Attempt to install Docker using official repositories? (Y / n): y
Installing required packages: ['apt-transport-https', 'ca-certificates', 'curl', 'gnupg-agent', 'software-properties-common']
Installing docker packages: ['docker-ce', 'docker-ce-cli', 'docker-compose-plugin', 'containerd.io']
Installation of docker packages apparently succeeded

Add a non-root user to the "docker" group?: y   

Enter user account: user

Add another non-root user to the "docker" group?: n

fs.file-max increases allowed maximum for file handles
fs.file-max= appears to be missing from /etc/sysctl.conf, append it? (Y / n): y

fs.inotify.max_user_watches increases allowed maximum for monitored files
fs.inotify.max_user_watches= appears to be missing from /etc/sysctl.conf, append it? (Y / n): y

fs.inotify.max_queued_events increases queue size for monitored files
fs.inotify.max_queued_events= appears to be missing from /etc/sysctl.conf, append it? (Y / n): y

fs.inotify.max_user_instances increases allowed maximum monitor file watchers
fs.inotify.max_user_instances= appears to be missing from /etc/sysctl.conf, append it? (Y / n): y

vm.max_map_count increases allowed maximum for memory segments
vm.max_map_count= appears to be missing from /etc/sysctl.conf, append it? (Y / n): y

net.core.somaxconn increases allowed maximum for socket connections
net.core.somaxconn= appears to be missing from /etc/sysctl.conf, append it? (Y / n): y

vm.swappiness adjusts the preference of the system to swap vs. drop runtime memory pages
vm.swappiness= appears to be missing from /etc/sysctl.conf, append it? (Y / n): y

vm.dirty_background_ratio defines the percentage of system memory fillable with "dirty" pages before flushing
vm.dirty_background_ratio= appears to be missing from /etc/sysctl.conf, append it? (Y / n): y

vm.dirty_ratio defines the maximum percentage of dirty system memory before committing everything
vm.dirty_ratio= appears to be missing from /etc/sysctl.conf, append it? (Y / n): y

net.ipv4.tcp_retries2 defines the maximum number of TCP retransmissions
net.ipv4.tcp_retries2= appears to be missing from /etc/sysctl.conf, append it? (Y / n): y

/etc/security/limits.d/limits.conf increases the allowed maximums for file handles and memlocked segments
/etc/security/limits.d/limits.conf does not exist, create it? (Y / n): y

cgroup parameters appear to be missing from /etc/default/grub, set them? (Y / n): y
```

If Malcolm is being installed from the downloaded release artifacts, the script will ask whether the user would like to extract the contents of the tarball and to specify the installation directory and Malcolm configuration will continue:
```
Extract Malcolm runtime files from /home/user/Downloads/malcolm_20250117_115650_d1867453.tar.gz (Y / n): y

Enter installation path for Malcolm [/home/user/Downloads/malcolm]: /home/user/Malcolm
Malcolm runtime files extracted to /home/user/Malcolm
```

Now that any necessary system configuration changes have been made, the local Malcolm instance will be configured. For a more in-depth treatment of each of these configuration questions, see the **Configuration** section in **[End-to-end Malcolm and Hedgehog Linux ISO Installation](malcolm-hedgehog-e2e-iso-install.md#MalcolmConfig)**.
```
1: docker
2: podman
Select container runtime engine (docker): 1

Malcolm processes will run as UID 1000 and GID 1000. Is this OK? (Y / n): y

Run with Malcolm (all containers) or Hedgehog (capture only) profile? (Y (Malcolm) / n (Hedgehog)): y

Should Malcolm use and maintain its own OpenSearch instance? (Y / n): y

Compress local OpenSearch index snapshots? (y / N): n

Forward Logstash logs to a secondary remote document store? (y / N): n

Setting 16g for OpenSearch and 2500m for Logstash. Is this OK? (Y / n): y

Setting 3 workers for Logstash pipelines. Is this OK? (Y / n): y

Restart Malcolm upon system or container daemon restart? (y / N): y
1: no
2: on-failure
3: always
4: unless-stopped
Select Malcolm restart behavior (unless-stopped): 4

Require encrypted HTTPS connections? (Y / n): y

Will Malcolm be running behind another reverse proxy (Traefik, Caddy, etc.)? (y / N): n

Specify external container network name (or leave blank for default networking) (): 

1: Basic
2: Lightweight Directory Access Protocol (LDAP)
3: None
Select authentication method (Basic): 1

Store PCAP, log and index files in /home/user/Malcolm? (Y / n): y

Enable index management policies (ILM/ISM) in Arkime? (y / N): n

Should Malcolm delete the oldest database indices and capture artifacts based on available storage? (y / N): n

Automatically analyze all PCAP files with Arkime? (Y / n): y

Automatically analyze all PCAP files with Suricata? (Y / n): y

Download updated Suricata signatures periodically? (y / N): n

Automatically analyze all PCAP files with Zeek? (Y / n): y

Is Malcolm being used to monitor an Operational Technology/Industrial Control Systems (OT/ICS) network? (y / N): n

Perform reverse DNS lookup locally for source and destination IP addresses in logs? (y / N): n

Perform hardware vendor OUI lookups for MAC addresses? (Y / n): y

Perform string randomness scoring on some fields? (Y / n): y

1: no
2: yes
3: customize
Should Malcolm accept logs and metrics from a Hedgehog Linux sensor or other forwarder? (no): 2

Enable file extraction with Zeek? (Y / n): y
1: none - No file extraction
2: known - Extract recognized MIME types
3: mapped - Extract MIME types for which file extensions are known
4: all - Extract all files
5: interesting - Extract MIME types of common attack vectors
6: notcommtxt - Extract all except common plain text files
Select file extraction behavior (none): 5

1: quarantined
2: all
3: none
Select file preservation behavior (quarantined): 1

Expose web interface for downloading preserved files? (y / N): y

ZIP downloaded preserved files? (y / N): y

Enter ZIP archive password for downloaded preserved files (or leave blank for unprotected): infected

Scan extracted files with ClamAV? (y / N): y

Scan extracted files with Yara? (y / N): y

Scan extracted PE files with Capa? (y / N): y

Lookup extracted file hashes with VirusTotal? (y / N): n

Download updated file scanner signatures periodically? (Y / n): n

Configure pulling from threat intelligence feeds for Zeek intelligence framework? (y / N): n

Should Malcolm run and maintain an instance of NetBox, an infrastructure resource modeling tool? (y / N): n

1: no
2: yes
3: customize
Should Malcolm capture live network traffic? 2

Specify capture interface(s) (comma-separated): eth0

Enable dark mode for OpenSearch Dashboards? (Y / n): y

Pull Malcolm images (y / N): y

Malcolm has been installed to /home/user/Malcolm. See README.md for more information.
Scripts for starting and stopping Malcolm and changing authentication-related settings can be found in /home/user/Malcolm/scripts.
```

At this point it is recommended to **reboot the system** so that the new system settings can be applied. After rebooting, log back in and return to the directory to which Malcolm was installed (or where the git working copy was cloned).

The next step is to [set up authentication](authsetup.md#AuthSetup) and generate some unique self-signed TLS certificates. Users may choose another username instead of `analyst` to log in to the Malcolm web interface.
```
user@host:~/Malcolm$ ./scripts/auth_setup 

Store administrator username/password for local Malcolm access? (Y / n): y

Administrator username: analyst
analyst password:
analyst password (again):

Additional local accounts can be created at https://localhost/auth/ when Malcolm is running

Configure remote primary or secondary OpenSearch/Elasticsearch instance? (y / N): n

Store username/password for OpenSearch Alerting email sender account? (y / N): n

(Re)generate internal passwords for NetBox (Y / n): y

Store password hash secret for Arkime viewer cluster? (y / N): n
```

Users planning to install and configure sensor devices running [Hedgehog Linux](hedgehog.md) must perform an additional step to allow communication between a Malcolm instance and an installation of Hedgehog Linux. In order for a sensor running Hedgehog Linux to securely communicate with Malcolm, it needs a copy of the client certificates generated when "(Re)generate self-signed certificates for a remote log forwarder" was selected above. The certificate authority, certificate, and key files to be copied to and used by the remote log forwarder are located in Malcolm's `filebeat/certs/` directory; these certificates should be copied to the `/opt/sensor/sensor_ctl/logstash-client-certificates` directory on the Hedgehog Linux sensor.

As an alternative to manually copying the files to the sensor, Malcolm can facilitate the secure transfer of these certificates using [`croc`](https://github.com/schollz/croc), an open-source tool for secure file transfer between two computers. Malcolm does not automatically download and install `croc`, but it may be downloaded from its [releases page on GitHub](https://github.com/schollz/croc/releases) or [installed from the command line](https://github.com/schollz/croc#install). If `croc` exists in the `PATH` on the Malcolm system, the `auth_setup` script will prompt to "Transfer self-signed client certificates to a remote log forwarder." Users can follow the steps outlined in the **[End-to-end Malcolm and Hedgehog Linux ISO Installation](malcolm-hedgehog-e2e-iso-install.md#InstallationExample)** (see [the Malcolm portion](malcolm-hedgehog-e2e-iso-install.md#MalcolmAuthSetup) and [the sensor portion](malcolm-hedgehog-e2e-iso-install.md##HedgehogGetCerts) of those instructions) to copy the certificates to the sensor.

In this example, rather than [building Malcolm from scratch](development.md#Build), images may be pulled from [GitHub](https://github.com/orgs/idaholab/packages?repo_name=Malcolm):
```
user@host:~/Malcolm$ docker compose --profile malcolm pull
[+] Pulling 23/23
 ✔ suricata Skipped - Image is already being pulled by suricata-live
 ✔ netbox-redis Skipped - Image is already being pulled by netbox-redis-cache
 ✔ arkime-live Skipped - Image is already being pulled by arkime
 ✔ zeek-live Skipped - Image is already being pulled by zeek
 ✔ opensearch Pulled
 ✔ dashboards-helper Pulled
 ✔ pcap-capture Pulled
 ✔ netbox Pulled
 ✔ filebeat Pulled
 ✔ netbox-redis-cache Pulled
 ✔ upload Pulled
 ✔ api Pulled
 ✔ netbox-postgres Pulled
 ✔ file-monitor Pulled
 ✔ nginx-proxy Pulled
 ✔ htadmin Pulled
 ✔ freq Pulled
 ✔ logstash Pulled
 ✔ dashboards Pulled
 ✔ suricata-live Pulled
 ✔ pcap-monitor Pulled
 ✔ arkime Pulled
 ✔ zeek Pulled

user@host:~/Malcolm$ docker images
REPOSITORY                                                     TAG               IMAGE ID       CREATED      SIZE
ghcr.io/idaholab/malcolm/nginx-proxy         25.01.0   ee2dac715efc   4 weeks ago   157MB
ghcr.io/idaholab/malcolm/dashboards          25.01.0   a35265cbde35   4 weeks ago   1.55GB
ghcr.io/idaholab/malcolm/dashboards-helper   25.01.0   7ca0c53c745f   4 weeks ago   253MB
ghcr.io/idaholab/malcolm/logstash-oss        25.01.0   ef10cbc5053f   4 weeks ago   1.57GB
ghcr.io/idaholab/malcolm/arkime              25.01.0   8c6bc6d79e1b   4 weeks ago   835MB
ghcr.io/idaholab/malcolm/zeek                25.01.0   1ccdbea08109   4 weeks ago   1.35GB
ghcr.io/idaholab/malcolm/filebeat-oss        25.01.0   6e08f4a8621e   4 weeks ago   433MB
ghcr.io/idaholab/malcolm/netbox              25.01.0   8dcbc152a9b9   4 weeks ago   1.78GB
ghcr.io/idaholab/malcolm/suricata            25.01.0   0c40ac0d8005   5 weeks ago   353MB
ghcr.io/idaholab/malcolm/opensearch          25.01.0   b66dd0922d21   5 weeks ago   1.54GB
ghcr.io/idaholab/malcolm/pcap-capture        25.01.0   830b7d682693   5 weeks ago   139MB
ghcr.io/idaholab/malcolm/file-monitor        25.01.0   daef959d2db4   5 weeks ago   723MB
ghcr.io/idaholab/malcolm/htadmin             25.01.0   098e5a4d1974   5 weeks ago   247MB
ghcr.io/idaholab/malcolm/postgresql          25.01.0   11fd6170d5d5   5 weeks ago   335MB
ghcr.io/idaholab/malcolm/api                 25.01.0   ed92d05a5485   5 weeks ago   165MB
ghcr.io/idaholab/malcolm/redis               25.01.0   f876b484bf9d   5 weeks ago   51.1MB
ghcr.io/idaholab/malcolm/file-upload         25.01.0   40468de667cf   5 weeks ago   250MB
ghcr.io/idaholab/malcolm/freq                25.01.0   7a64594a7c6b   5 weeks ago   155MB
ghcr.io/idaholab/malcolm/pcap-monitor        25.01.0   ff3fa6dec5da   5 weeks ago   178MB
```

Finally, start Malcolm. When Malcolm starts it will stream informational and debug messages to the console until it has completed initializing.
```
user@host:~/Malcolm$ ./scripts/start
Malcolm services can be accessed at https://localhost/
------------------------------------------------------------------------------

NAME                           COMMAND                  SERVICE              STATUS               PORTS
malcolm-api-1                  "/usr/local/bin/dock…"   api                  running (starting)   …
malcolm-arkime-1               "/usr/local/bin/dock…"   arkime               running (starting)   …
malcolm-dashboards-1           "/usr/local/bin/dock…"   dashboards           running (starting)   …
malcolm-dashboards-helper-1    "/usr/local/bin/dock…"   dashboards-helper    running (starting)   …
malcolm-file-monitor-1         "/usr/local/bin/dock…"   file-monitor         running (starting)   …
malcolm-filebeat-1             "/usr/local/bin/dock…"   filebeat             running (starting)   …
malcolm-freq-1                 "/usr/local/bin/dock…"   freq                 running (starting)   …
malcolm-htadmin-1              "/usr/local/bin/dock…"   htadmin              running (starting)   …
malcolm-logstash-1             "/usr/local/bin/dock…"   logstash             running (starting)   …
malcolm-netbox-1               "/usr/bin/tini -- /u…"   netbox               running (starting)   …
malcolm-netbox-postgres-1      "/usr/bin/docker-uid…"   netbox-postgres      running (starting)   …
malcolm-redis-1                "/sbin/tini -- /usr/…"   redis                running (starting)   …
malcolm-redis-cache-1          "/sbin/tini -- /usr/…"   redis-cache          running (starting)   …
malcolm-nginx-proxy-1          "/usr/local/bin/dock…"   nginx-proxy          running (starting)   …
malcolm-opensearch-1           "/usr/local/bin/dock…"   opensearch           running (starting)   …
malcolm-pcap-capture-1         "/usr/local/bin/dock…"   pcap-capture         running              …
malcolm-pcap-monitor-1         "/usr/local/bin/dock…"   pcap-monitor         running (starting)   …
malcolm-suricata-1             "/usr/local/bin/dock…"   suricata             running (starting)   …
malcolm-suricata-live-1        "/usr/local/bin/dock…"   suricata-live        running              …
malcolm-upload-1               "/usr/local/bin/dock…"   upload               running (starting)   …
malcolm-zeek-1                 "/usr/local/bin/dock…"   zeek                 running (starting)   …
malcolm-zeek-live-1            "/usr/local/bin/dock…"   zeek-live            running              …
…
```

It will take several minutes for all of Malcolm's components to start up. Logstash will take the longest, probably 3 to 5 minutes. Users will know Logstash is fully ready when you see Logstash spit out a bunch of starting up messages, ending with this:
```
…
malcolm-logstash-1  | [2022-07-27T20:27:52,056][INFO ][logstash.agent           ] Pipelines running {:count=>6, :running_pipelines=>[:"malcolm-input", :"malcolm-output", :"malcolm-beats", :"malcolm-suricata", :"malcolm-enrichment", :"malcolm-zeek"], :non_running_pipelines=>[]}
…
```

The [Malcolm user interfaces](quickstart.md#UserInterfaceURLs) may be accessed via a web browser.

![Malcolm Landing Page](./images/screenshots/malcolm_landing_page.png)