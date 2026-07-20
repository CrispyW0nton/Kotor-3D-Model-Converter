"""Start a passive K2 custom-animation debugger session for the UE probe."""

from __future__ import annotations

import json
import os
from pathlib import Path

from kotor_debugger import start_log_session


HERE = Path(__file__).resolve().parent
GAME_ROOT = os.environ.get(
    "K2_PATH",
    r"C:\Program Files (x86)\Steam\steamapps\common\Knights of the Old Republic II",
)


if __name__ == "__main__":
    metadata = start_log_session(
        game="k2",
        game_root=GAME_ROOT,
        session_label="custom-animation-ue-plcaa",
        wait_for_process=True,
        duration_seconds=2400,
        asset_resrefs=["plcaa", "pmbam", "kpm98_ue", "kpm_ue_a1"],
        session_root=str(HERE / "sessions"),
    )
    print(json.dumps(metadata, indent=2))
