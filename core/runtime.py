from __future__ import annotations

import os
import sys
from pathlib import Path


def relaunch_in_project_venv(project_root: Path) -> None:
    """Relanza el comando con la .venv local cuando se usó otro Python."""
    executable_name = "python.exe" if os.name == "nt" else "python"
    relative = Path("Scripts") / executable_name if os.name == "nt" else Path("bin") / executable_name
    venv_python = project_root / ".venv" / relative
    if not venv_python.exists():
        return
    try:
        already_using_venv = Path(sys.executable).resolve() == venv_python.resolve()
    except OSError:
        already_using_venv = False
    if already_using_venv:
        return
    print(f"[env] usando entorno virtual: {venv_python}", flush=True)
    os.execv(str(venv_python), [str(venv_python), *sys.argv])

