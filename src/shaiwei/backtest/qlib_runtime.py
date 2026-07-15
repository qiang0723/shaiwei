"""Project-owned qlib initialization, including an ignored local recorder root."""

import qlib
from qlib.config import REG_CN

from shaiwei.config import PROJECT_ROOT, Settings


def initialize_qlib(settings: Settings) -> None:
    recorder_db = (PROJECT_ROOT / "logs" / "mlflow.db").resolve()
    recorder_db.parent.mkdir(parents=True, exist_ok=True)
    qlib.init(
        provider_uri=str(settings.runtime.data_root / "qlib_bin"),
        region=REG_CN,
        exp_manager={
            "class": "MLflowExpManager",
            "module_path": "qlib.workflow.expm",
            "kwargs": {
                # MLflow 3.14 rejects new filesystem tracking stores.  SQLite
                # remains local/reproducible while supporting current MLflow.
                "uri": f"sqlite:///{recorder_db}",
                "default_exp_name": "shaiwei-stage0",
            },
        },
    )
