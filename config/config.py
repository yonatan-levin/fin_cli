"""Config file for the stock screener app.

The CSV-destination precedence implemented in `Config.file_path` is the single
chokepoint for Pillar 2 (`docs/features/archive/pipeline-mode-spec.md` §5.2):

    --output PATH  >  --output -  >  FINCLI_OUTPUT_DIR  >  default

`file_path` is intentionally an instance method (not `@staticmethod`) so that
all three precedence tiers can be resolved from one call site without
duplicating the conditional in `run_stock_screener`. Existing callers use
`config.file_path(name)` (instance-call form), which continues to work.
"""

import datetime
import os
from pathlib import Path
from typing import Any

from platformdirs import user_data_dir
from pydantic import Field

from core.configuration.config_base import Configurable, SystemSettings

# Sentinel used by `--output -` to request stdout streaming. Defined as a
# module constant so the literal `"-"` is greppable / renameable across
# `Config.file_path` and `run_stock_screener`'s dispatch site.
STDOUT_SENTINEL = "-"


class Config(SystemSettings):
    name: str = "Stock Screener CLI config"
    description: str = "Configuration for the Stock Screener CLI app."
    ########################
    # Application Settings #
    ########################
    use_history: bool = False
    filters: tuple = ()
    scrape_link: str = ""
    history_dir: Path = Field(
        default_factory=lambda: Path(user_data_dir("fincli", appauthor=False)) / "local_history"
    )
    # Exact CSV destination from `--output PATH` (or `-` for stdout streaming).
    # Empty string means "no caller pin"; precedence falls through to
    # `output_dir` then to the CWD-relative default.
    output_path: str = ""
    # Parent-directory override sourced from the `FINCLI_OUTPUT_DIR` env var
    # in `core.configuration.configurator.build_config`. None means "no env
    # override"; the timestamped basename still applies when set.
    output_dir: Path | None = None

    def file_path(self, file_name: str) -> str:
        """Resolve the CSV output path under the Pillar-2 precedence rules.

        Args:
            file_name: Logical name (e.g., ``"stock_screener"``) used for the
                timestamped default basename. Ignored when ``output_path`` is
                set to a non-sentinel value.

        Returns:
            The absolute or CWD-relative file path the caller should write to.
            Note that the stdout-streaming sentinel (``"-"``) intentionally
            falls through to the timestamped default — the stdout dispatch is
            handled at the orchestrator boundary so callers that hit
            ``file_path`` cannot accidentally produce a file literally named
            ``"-"``.
        """
        if self.output_path and self.output_path != STDOUT_SENTINEL:
            # Caller pinned an exact destination via `--output PATH`. No
            # timestamp is appended; the path is written verbatim.
            return self.output_path

        date = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M")
        basename = f"{file_name}_{date}.csv"

        if self.output_dir is not None:
            # Env-var override: keep the timestamped basename, swap parent dir.
            return str(self.output_dir / basename)

        # Default: CWD-relative `workspace_output/` (today's behavior).
        return os.path.join(os.getcwd(), f"workspace_output/{basename}")


# For late use if needed to define a strongly typed config builder.
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
