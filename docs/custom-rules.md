# <a name="CustomRulesAndScripts"></a>Custom Rules, Scripts and Plugins

* [Arkime](#Arkime)
* [Suricata](#Suricata)
* [Zeek](#Zeek)
* [YARA](#YARA)
* [NetBox Plugins](#NetBox)
* [Other Customizations](#Other)

Much of Malcolm's behavior can be adjusted through [environment variable files](malcolm-config.md#MalcolmConfigEnvVars). However, some components allow further customization through the use of custom scripts, configuration files, and rules.

## <a name="Arkime"></a>Arkime

### Rules

[Arkime rules](https://arkime.com/rulesformat) "allow you to specify actions to perform when criteria are met with certain fields or state."

Arkime rules files (with the `*.yml` or `*.yaml` extension) may be placed in the `./arkime/rules/` subdirectory in the Malcolm installation directory. These new rules files can applied by restarting Malcolm, or this can be done manually without completely restarting Malcolm by running the following command from the Malcolm installation directory:

```
./scripts/restart -s arkime arkime-live
```

Malcolm comes with [a few Arkime rules]({{ site.github.repository_url }}/blob/{{ site.github.build_revision }}/arkime/rules/) included by default. More sample Arkime rules can be found on the [Arkime web site](https://arkime.com/rules).

On [Hedgehog Linux](hedgehog.md), the Arkime rules [directory]({{ site.github.repository_url }}/blob/{{ site.github.build_revision }}/hedgehog-iso/interface/sensor_ctl/arkime/rules/) is `/opt/sensor/sensor_ctl/arkime/rules`. New rules can be applied by restarting capture processes:

```
/opt/sensor/sensor_ctl/shutdown && sleep 30 && /opt/sensor/sensor_ctl/supervisor.sh
```

### Lua Plugin

Arkime's [Lua plugin](https://arkime.com/settings#lua) allows sessions to be modified via simple Lua scripts. See the [Arkime Lua plugin documentation](https://github.com/arkime/arkime/tree/main/capture/plugins/lua) for more information and [example scripts](https://github.com/arkime/arkime/tree/main/capture/plugins/lua/samples).

Lua files for the Arkime Lua plugin (with the `*.lua` extension) may be placed in the `./arkime/lua/` subdirectory in the Malcolm installation directory. These new scripts can applied by restarting Malcolm, or this can be done manually without completely restarting Malcolm by running the following command from the Malcolm installation directory:

```
./scripts/restart -s arkime arkime-live
```

On [Hedgehog Linux](hedgehog.md), the Arkime Lua directory is `/opt/sensor/sensor_ctl/arkime/lua`. New scripts can be applied by restarting capture processes:

```
/opt/sensor/sensor_ctl/shutdown && sleep 30 && /opt/sensor/sensor_ctl/supervisor.sh
```

## <a name="Suricata"></a>Suricata

### Rules

In addition to the [default Suricata ruleset](https://github.com/OISF/suricata/tree/master/rules) and [Emerging Threads Open ruleset](https://rules.emergingthreats.net/open/), users may provide custom rules files for use by Suricata in Malcolm.

Suricata rules files (with the `*.rules` extension) may be placed in the `./suricata/rules/` subdirectory in the Malcolm installation directory. These new rules files will be picked up immediately for subsequent [PCAP upload](upload.md#Upload), and for [live analysis](live-analysis.md#LocalPCAP) will be applied by restarting Malcolm. This can also be done manually without interrupting the Suricata processes by running the following commands from the Malcolm installation directory.

First, for the `suricata-live` container:

```bash
$ docker compose exec -u $(id -u) suricata-live bash -c 'suricata_config_populate.py --suricata /usr/bin/suricata-offline && kill -USR2 $(pidof suricata)'
```

Then, for the `suricata` container:

```bash
$ docker compose exec -u $(id -u) suricata bash -c 'suricata_config_populate.py --suricata /usr/bin/suricata-offline && kill -USR2 $(pidof suricata-offline)'
```

Alternately, both Suricata services could be completely restarted with `./scripts/restart -s suricata suricata-live`.

For [Kubernetes deployments of Malcolm](kubernetes.md#Kubernetes), recreating the `suricata-offline-custom-rules-volume` and `suricata-live-custom-rules-volume` configMaps used by the [`suricata`]({{ site.github.repository_url }}/blob/{{ site.github.build_revision }}/kubernetes/11-suricata.yml) and [`suricata-live`]({{ site.github.repository_url }}/blob/{{ site.github.build_revision }}/kubernetes/22-suricata-live.yml) containers, respectively, and restarting those containers, will cause changes to custom rules files to be applied.

If the `SURICATA_CUSTOM_RULES_ONLY` [environment variable](malcolm-config.md#MalcolmConfigEnvVars) is set to `true`, Malcolm will bypass the default Suricata rulesets and use only the user-defined rules.

On [Hedgehog Linux](hedgehog.md), the Suricata custom rules directory is `/opt/sensor/sensor_ctl/suricata/rules/`, and the `SURICATA_CUSTOM_RULES_ONLY` environment variable can be found in [`/opt/sensor/sensor_ctl/control_vars.conf`]({{ site.github.repository_url }}/blob/{{ site.github.build_revision }}/hedgehog-iso/interface/sensor_ctl/control_vars.conf). New rules can be applied by restarting capture processes:

```
/opt/sensor/sensor_ctl/shutdown && sleep 30 && /opt/sensor/sensor_ctl/supervisor.sh
```

### Configuration

Suricata uses the [YAML format for configuration](https://docs.suricata.io/en/latest/configuration/suricata-yaml.html), and the main `suricata.yaml` file is generated by Malcolm [dynamically at runtime]({{ site.github.repository_url }}/blob/{{ site.github.build_revision }}/shared/bin/suricata_config_populate.py).

The contents of the `suricata.yaml` file can be adjusted via [environment variables](malcolm-config.md#MalcolmConfigEnvVars) found in [`suricata.env`]({{ site.github.repository_url }}/blob/{{ site.github.build_revision }}/config/suricata.env.example).

For more control of the Suricata configuration, Suricata allows other configuration YAML files to be [included](https://docs.suricata.io/en/latest/configuration/includes.html), allowing the configuration to be broken into multiple files.

Malcolm users may place additional Suricata configuration files (with the `.yaml` file extension) in the `./suricata/include-configs/` subdirectory in the Malcolm installation directory. When Malcolm creates the `suricata.yaml` file these additional files will be added at the end in an `include:` section.

To apply new `.yaml` files immediately without restarting Malcolm's Suricata containers, users may run the following commands from the Malcolm installation directory:

```
docker compose exec suricata /usr/local/bin/docker_entrypoint.sh true
```

```
docker compose exec suricata-live /usr/local/bin/docker_entrypoint.sh true
```

```
docker compose exec suricata-live supervisorctl restart live-suricata
```

On [Hedgehog Linux](hedgehog.md), the Suricata custom configuration directory is `/opt/sensor/sensor_ctl/suricata/include-configs/`. New configuration can be applied by restarting capture processes:

```
/opt/sensor/sensor_ctl/shutdown && sleep 30 && /opt/sensor/sensor_ctl/supervisor.sh
```

## <a name="Zeek"></a>Zeek

Some aspects of Malcolm's instance of Zeek's [local site policy]({{ site.github.repository_url }}/blob/{{ site.github.build_revision }}/zeek/config/local.zeek) can be adjusted via [environment variables](malcolm-config.md#MalcolmConfigEnvVars) found in [`zeek.env`]({{ site.github.repository_url }}/blob/{{ site.github.build_revision }}/config/zeek.env.example).

For more control of Zeek's behavior, Malcolm's users may place Zeek files in the `./zeek/custom/` subdirectory in the Malcolm installation directory. The organization of this directory is left entirely up to the user: in other words, users placing files there will also need to create a `__load__.zeek` file there to [tell Zeek](https://docs.zeek.org/en/master/quickstart.html#telling-zeek-which-scripts-to-load) what to load from that directory.

These new files should be picked up immediately for subsequent [PCAP upload](upload.md#Upload), and for [live analysis](live-analysis.md#LocalPCAP) they will take effect upon restarting Malcolm, or without restarting Malcolm by running the following command from the Malcolm installation directory:

```
docker compose exec zeek-live supervisorctl restart live-zeek
```

On [Hedgehog Linux](hedgehog.md), the Zeek custom scripts directory is `/opt/sensor/sensor_ctl/zeek/custom/`. New configuration can be applied by restarting capture processes:

```
/opt/sensor/sensor_ctl/shutdown && sleep 30 && /opt/sensor/sensor_ctl/supervisor.sh
```

## <a name="YARA"></a>YARA

[Custom rules](https://yara.readthedocs.io/en/stable/writingrules.html) files for [YARA](https://github.com/VirusTotal/yara) (with either the `*.yara` or `*.yar` file extension) may be placed in the `./yara/rules/` subdirectory in the Malcolm installation directory.

New rules files will take effect by either restarting Malcolm (specifically the `file-monitor` container) or when the automatic rule update runs (if automatic rule updates are enabled). This can also be done manually without restarting Malcolm by running the following commands from the Malcolm installation directory:

```
docker compose exec file-monitor /usr/local/bin/yara_rules_setup.sh
```

```
docker compose exec file-monitor supervisorctl restart yara
```

If the `EXTRACTED_FILE_YARA_CUSTOM_ONLY` [environment variable](malcolm-config.md#MalcolmConfigEnvVars) is set to `true`, Malcolm will bypass the default Yara rulesets ([Neo23x0/signature-base](https://github.com/Neo23x0/signature-base), [reversinglabs/reversinglabs-yara-rules](https://github.com/reversinglabs/reversinglabs-yara-rules), and [bartblaze/Yara-rules](https://github.com/bartblaze/Yara-rules)) and use only user-defined rules in `./yara/rules`.

On [Hedgehog Linux](hedgehog.md), the Yara custom rules directory is `/opt/yara-rules/`, and the `EXTRACTED_FILE_YARA_CUSTOM_ONLY` environment variable can be found in [`/opt/sensor/sensor_ctl/control_vars.conf`]({{ site.github.repository_url }}/blob/{{ site.github.build_revision }}/hedgehog-iso/interface/sensor_ctl/control_vars.conf). New rules can be applied by restarting the Yara file scanning process:

```
/opt/sensor/sensor_ctl/restart zeek:yara
```

## <a name="NetBox"></a>NetBox Plugins

NetBox's functionality can be extended with plugins that can provide "[new data models, integrations, and more](https://netboxlabs.com/netbox-plugins/)" (see also the [NetBox Wiki](https://github.com/netbox-community/netbox/wiki/Plugins)).

When Malcolm's NetBox container [starts up]({{ site.github.repository_url }}/blob/{{ site.github.build_revision }}/netbox/scripts/netbox_install_plugins.py), it installs (using [pip](https://packaging.python.org/en/latest/guides/tool-recommendations/#installing-packages)) any NetBox plugins that have [cloned](https://docs.github.com/en/repositories/creating-and-managing-repositories/cloning-a-repository) or [downloaded and extracted](https://docs.github.com/en/repositories/working-with-files/using-files/downloading-source-code-archives) into subdirectories in `./netbox/custom-plugins/` in the Malcolm installation directory. In instances where Malcolm is being run in an offline/airgapped configuration, the plugins' additional dependencies must also be present under `./netbox/custom-plugins/requirements/`, where they will be automatically installed first.

The following warning is quoted from the [NetBox documentation](https://netboxlabs.com/docs/netbox/en/stable/configuration/plugins/):

> Plugins extend NetBox by allowing external code to run with the same access and privileges as NetBox itself. Only install plugins from trusted sources. The NetBox maintainers make absolutely no guarantees about the integrity or security of your installation with plugins enabled.

## <a name="Other"></a>Other Customizations

There are other areas of Malcolm that can be modified and customized to fit users' needs. Please see these other sections of the documentation for more information.

* [Building your own visualizations and dashboards](dashboards.md#BuildDashboard)
* [Customizing event severity scoring](severity.md#SeverityConfig)
* [Zeek Intelligence Framework](zeek-intel.md#ZeekIntel)
* Populating the NetBox inventory [Manually](asset-interaction-analysis.md#NetBoxPopManual) or through [Preloading](asset-interaction-analysis.md#NetBoxPreload)
* [Modifying or Contributing to Malcolm](contributing-guide.md#Contributing)
