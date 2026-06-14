import yaml
import os
from typing import Dict, Any
from pathlib import Path


class YAMLConfig:
    _instance = None
    _config: Dict[str, Any] = {}

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._load_config()
        return cls._instance

    def _load_config(self) -> None:
        config_path = Path(__file__).parent / "config.yaml"
        if config_path.exists():
            with open(config_path, "r", encoding="utf-8") as f:
                self._config = yaml.safe_load(f) or {}
        else:
            self._config = {}

    def get(self, section: str, key: str = None, default: Any = None) -> Any:
        section_data = self._config.get(section, {})
        if key is None:
            return section_data if section_data != {} else default
        return section_data.get(key, default)

    def reload(self) -> None:
        self._load_config()


yaml_config = YAMLConfig()
