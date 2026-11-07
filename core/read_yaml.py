import yaml

CONFIG_FILE_PATH = "config/config.yaml"


def read_yaml():
    try:
        with open(CONFIG_FILE_PATH) as yam:
            config = yaml.safe_load(yam)
            return config
    except Exception as e:
        raise
