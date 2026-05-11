"""Config file for the stock screener app."""
import datetime
import os
from pathlib import Path
from typing import Any

from platformdirs import user_data_dir
from pydantic import Field

from core.configuration.config_base import Configurable, SystemSettings

class Config(SystemSettings):
    name: str = "Stock Screener CLI config"
    description: str = "Configuration for the Stock Screener CLI app."
    ########################
    # Application Settings #
    ########################
    use_history: bool = False
    filters: tuple = ()
    scrape_link: str = ""
    history_dir: Path = Field(default_factory=lambda: Path(user_data_dir("fincli", appauthor=False)) / "local_history")
    @staticmethod
    def file_path(file_name: str) -> str:
        """Return the path to the file."""
        date = datetime.datetime.now().strftime('%Y-%m-%d_%H-%M')
        return os.path.join(os.getcwd(), f'workspace_output/{file_name}_{date}.csv')


#For late use if needed to define a strongly typed config builder.
class ConfigBuilder(Configurable[Config]):
    """Configuration builder class."""
    default_settings = Config()

    @classmethod
    def build_config_from_env(cls) -> Config:
        """Build the configuration."""
        config_dict: dict[str, Any] = {
            "use_history": os.getenv("USE_HISTORY", default=cls.default_settings.use_history),
        }

        return Config(**config_dict)