import json
import os
from pathlib import Path

from config.config import Config
from ..converters.json import json_to_tuples


def build_config(
    use_history: bool = False,
    filters: str = ""
) -> Config:
    """Create the configuration."""
    config = Config()

    history_dir_env = os.getenv("HISTORY_DIR")
    if history_dir_env:
        config.history_dir = Path(history_dir_env)

    if use_history:
        config.use_history = use_history
        
        filepath = config.history_dir / 'filter_history.json'
        with open(filepath, 'r') as f:
            filters = json.load(f)
            config.filters = tuple(filters.items())
    
    if filters != "" and not use_history:
        config.filters = json_to_tuples(filters)

    return config
