from extras.plugins import PluginConfig

class MalcolmConfig(PluginConfig):
    name = 'malcolm'
    verbose_name = 'Malcolm'
    description = 'An example NetBox plugin'
    version = '0.1'
    base_url = 'malcolm'
    required_settings = []

config = MalcolmConfig
