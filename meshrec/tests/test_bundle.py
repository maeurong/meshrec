"""Il bundle macOS e i launcher: forma, non esecuzione."""

from __future__ import annotations

import plistlib
import stat
import tomllib
from pathlib import Path

RADICE = Path(__file__).resolve().parent.parent
BUNDLE = RADICE / "MeshRec.app" / "Contents"


def test_il_bundle_ha_plist_eseguibile_e_icona():
    plist = plistlib.loads((BUNDLE / "Info.plist").read_bytes())
    assert plist["CFBundleName"] == "MeshRec"
    assert plist["CFBundleExecutable"] == "MeshRec"
    assert plist["CFBundleIconFile"] == "icona"
    assert plist["CFBundleIdentifier"] == "it.meshrec.app"
    assert plist["CFBundlePackageType"] == "APPL"
    eseguibile = BUNDLE / "MacOS" / "MeshRec"
    assert eseguibile.stat().st_mode & stat.S_IXUSR
    assert (BUNDLE / "Resources" / "icona.icns").is_file()


def test_lo_script_del_bundle_lancia_serve_dalla_cartella_del_programma():
    testo = (BUNDLE / "MacOS" / "MeshRec").read_text(encoding="utf-8")
    assert testo.startswith("#!/bin/sh")
    assert 'uv run meshrec serve "$@"' in testo
    assert "../../.." in testo  # risale dal bundle alla cartella meshrec/
    assert "display dialog" in testo  # gli errori si vedono anche senza Terminale


def test_il_command_non_esiste_piu():
    assert not (RADICE / "MeshRec.command").exists()


def test_il_collegamento_windows_punta_al_bat_con_l_icona():
    testo = (RADICE / "crea-collegamento.ps1").read_text(encoding="utf-8")
    assert "MeshRec.bat" in testo
    assert "icona.ico" in testo
    assert "WScript.Shell" in testo


def test_lo_script_del_bundle_avvisa_se_spostato_fuori_dal_progetto():
    """Punto 5 fix wave: bundle spostato fuori da meshrec/ -> dialogo che lo
    dice, non un errore muto di uv."""
    testo = (BUNDLE / "MacOS" / "MeshRec").read_text(encoding="utf-8")
    assert "pyproject.toml" in testo


def test_la_versione_del_plist_segue_pyproject():
    """Punto 6 fix wave: se pyproject.toml cambia versione e il plist non
    segue, questo test diventa rosso."""
    plist = plistlib.loads((BUNDLE / "Info.plist").read_bytes())
    versione = tomllib.loads((RADICE / "pyproject.toml").read_text(encoding="utf-8"))["project"]["version"]
    assert plist["CFBundleShortVersionString"] == versione
    assert plist["CFBundleVersion"] == versione


def test_lo_script_del_bundle_scrive_il_codice_d_uscita_nel_log():
    """Il dialogo dice solo «si e' fermato con un errore»: il numero che
    distingue un'uscita ordinata (1) da una morte per segnale (134/139) andava
    perso con l'`if ! uv run ...`. Senza, la prossima diagnosi e' inventata."""
    testo = (BUNDLE / "MacOS" / "MeshRec").read_text(encoding="utf-8")
    assert "codice=$?" in testo
    assert "uscito con codice $codice" in testo
    assert 'exit "$codice"' in testo  # il bundle non maschera l'uscita con 1


def _lancia_il_bundle_con_uscita(tmp_path, codice):
    """Esegue lo script vero del bundle con un `uv` finto che esce con `codice`
    e un `osascript` finto che registra il testo del dialogo."""
    import os
    import subprocess

    finti = tmp_path / ".local" / "bin"
    finti.mkdir(parents=True)
    (finti / "uv").write_text(f"#!/bin/sh\nexit {codice}\n")
    (finti / "osascript").write_text(f'#!/bin/sh\nprintf "%s" "$2" > "{tmp_path}/dialogo"\n')
    for f in finti.iterdir():
        f.chmod(0o755)
    esito = subprocess.run(
        ["/bin/sh", str(BUNDLE / "MacOS" / "MeshRec")],
        env={**os.environ, "HOME": str(tmp_path)},
        capture_output=True, text=True, timeout=30,
    )
    dialogo = tmp_path / "dialogo"
    log = tmp_path / "Library" / "Logs" / "MeshRec.log"
    return (
        esito.returncode,
        dialogo.read_text(encoding="utf-8") if dialogo.exists() else None,
        log.read_text(encoding="utf-8") if log.exists() else "",
    )


def test_il_dialogo_distingue_chi_ha_chiuso_meshrec(tmp_path):
    """Il 12/09/2026 un `pkill` esterno ha chiuso la finestra e il dialogo diceva
    «si e' fermato con un errore»: la diagnosi e' partita dal programma, che non
    c'entrava. Segnale mandato da fuori, crash e errore del programma sono tre
    cose diverse, e il dialogo le dice diverse."""
    casi = {
        143: "puoi riaprirlo normalmente",
        137: "chiuso da un altro processo",
        129: "chiuso da un altro processo",
        139: "si è chiuso di colpo per un errore interno",
        134: "si è chiuso di colpo per un errore interno",
        1: "si è fermato con un errore",
    }
    for codice, attesa in casi.items():
        cartella = tmp_path / str(codice)
        uscita, dialogo, log = _lancia_il_bundle_con_uscita(cartella, codice)
        assert uscita == codice
        assert dialogo is not None and attesa in dialogo, (codice, dialogo)
        assert f"uscito con codice {codice}" in log


def test_un_uscita_pulita_non_apre_dialoghi(tmp_path):
    uscita, dialogo, log = _lancia_il_bundle_con_uscita(tmp_path, 0)
    assert uscita == 0
    assert dialogo is None
    assert "uscito con codice" not in log
