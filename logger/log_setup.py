import logging
import os
from logging import config
from pathlib import Path

import yaml

current_path, _ = os.path.split(os.path.abspath(__file__))

with open(Path(os.path.join(current_path, "logging_config.yml")), "r", encoding="utf8") as f:
    logging_config = yaml.safe_load(f)
logging.config.dictConfig(logging_config)
