"""Project-owned qlib initialization, including an ignored local recorder root."""

import qlib
from qlib.config import REG_CN

from shaiwei.config import PROJECT_ROOT, Settings


def initialize_qlib(settings: Settings) -> None:
    recorder_root = PROJECT_ROOT / "logs" / "mlruns"
    qlib.init(
        provider_uri=str(settings.runtime.data_root / "qlib_bin"),
        region=REG_CN,
        exp_manager={
            "class": "MLflowExpManager",
            "module_path": "qlib.workflow.expm",
            "kwargs": {
                "uri": recorder_root.resolve().as_uri(),
                "default_exp_name": "shaiwei-stage0",
            },
        },
    )
