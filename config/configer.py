from pathlib import Path
import yaml
import os

current_path = os.path.dirname(__file__)

with open(current_path + "/config.yaml", 'rb') as f:
    configs = yaml.safe_load(f)
