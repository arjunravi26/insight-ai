import yaml
from pathlib import Path

# CONFIG_FILE_PATH = "config/config.yaml"
BASE_DIR = Path(__file__).resolve().parents[1]
CONFIG_FILE_PATH = BASE_DIR / "config" / "config.yaml"


def read_yaml():
    try:
        with open(CONFIG_FILE_PATH) as yam:
            config = yaml.safe_load(yam)
            return config
    except Exception as e:
        raise
