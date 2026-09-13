"""Dopo gmsh, i sottoprocessi trovano ancora i loro eseguibili.

Su Windows `gmsh.initialize()` riscrive il PATH nativo del processo troncandolo
(misurato in CI: 2865 -> 306 caratteri) mentre `os.environ` resta intatto.
L'oracolo e' un figlio con percorso assoluto: legge l'ambiente nativo che il
padre gli passa, non la copia Python del padre.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys

import numpy as np
import pytest

from meshrec.core import hexa
from meshrec.core.config import ModelConfig

RETTANGOLO = np.array([[0.0, 0.0], [200.0, 0.0], [200.0, 140.0], [0.0, 140.0]])


def _path_del_figlio() -> str:
    return subprocess.run(
        [sys.executable, "-c", "import os, sys; sys.stdout.write(os.environ.get('PATH', ''))"],
        capture_output=True, text=True, check=True,
    ).stdout


@pytest.fixture
def path_lungo(monkeypatch):
    """PATH oltre i 2047 caratteri, come quello del runner Windows."""
    cartelle = [os.environ.get("PATH", "")] + [
        os.path.join(os.sep, "cartella-inesistente", f"{i:03d}") for i in range(120)
    ]
    monkeypatch.setenv("PATH", os.pathsep.join(cartelle))
    assert len(os.environ["PATH"]) > 2047
    return os.environ["PATH"]


def test_dopo_due_mesh_prisma_il_path_nativo_e_intero_e_git_parte(path_lungo):
    for _ in range(2):
        hexa.mesh_prisma(RETTANGOLO, np.zeros(3), np.array([0.0, 0.0, 1.0]), 1500.0, ModelConfig())
        figlio = _path_del_figlio()
        # sonda temporanea: via prima della fine del fix
        print(f"SONDA PATH os.environ={len(path_lungo)} nativo={len(figlio)}")
        assert figlio.startswith(path_lungo), f"PATH nativo {len(figlio)} caratteri, atteso {len(path_lungo)}"
        if shutil.which("git") is not None:
            assert subprocess.run(["git", "--version"], capture_output=True).returncode == 0
