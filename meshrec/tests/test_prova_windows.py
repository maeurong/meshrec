"""La prova guidata della finestra su Windows (`prova-windows.ps1`).

Forma ovunque; logica solo su Windows, dove esiste il PowerShell 5.1 che Mario
usa con «Esegui con PowerShell». Le funzioni dello script si caricano con il
dot-source, che salta il percorso interattivo.
"""

from __future__ import annotations

import base64
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

RADICE = Path(__file__).resolve().parent.parent
SCRIPT = RADICE / "prova-windows.ps1"
DOCUMENTO = RADICE.parent / "docs" / "prove" / "2026-09-finestra-windows.md"
VOCI = ("viewport", "sfoglia", "citare", "chiusura", "browser", "collegamento")

solo_windows = pytest.mark.skipif(
    sys.platform != "win32", reason="serve il PowerShell 5.1 di Windows"
)


def _powershell(comando: str, **kwargs) -> subprocess.CompletedProcess:
    esegui = shutil.which("powershell")
    assert esegui, "powershell.exe assente su Windows"
    return subprocess.run(
        [esegui, "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass",
         "-Command", "[Console]::OutputEncoding = [Text.Encoding]::UTF8; " + comando],
        capture_output=True, stdin=subprocess.DEVNULL, timeout=120, **kwargs,
    )


def _funzioni(corpo: str) -> subprocess.CompletedProcess:
    return _powershell(f". '{SCRIPT}'; {corpo}")


def test_lo_script_esiste_con_il_bom_utf8():
    # PowerShell 5.1 legge un file senza BOM come ANSI e rovina gli accenti.
    assert SCRIPT.read_bytes().startswith(b"\xef\xbb\xbf")


def test_lo_script_e_il_documento_nominano_le_sei_voci():
    script = SCRIPT.read_text(encoding="utf-8-sig")
    documento = DOCUMENTO.read_text(encoding="utf-8")
    for voce in VOCI:
        assert f"'{voce}'" in script, voce
        assert documento.count(f"<!-- {voce} -->") == 1, voce
    voci_del_documento = re.findall(r"^- \[.\].*$", documento, re.M)
    assert not any("WebView2" in r for r in voci_del_documento)


def test_la_porta_di_prova_del_browser_non_e_quella_di_mario():
    script = SCRIPT.read_text(encoding="utf-8-sig")
    trovata = re.search(r"\$portaBrowser\s*=\s*Get-PortaLibera\s+(\d+)", script)
    assert trovata, "manca l'assegnazione di $portaBrowser"
    assert trovata.group(1) != "8765"


@solo_windows
def test_il_parser_di_powershell_accetta_lo_script():
    esito = _powershell(
        "$errori = $null; "
        f"[void][System.Management.Automation.Language.Parser]::ParseFile('{SCRIPT}', [ref]$null, [ref]$errori); "
        "$errori | ForEach-Object { $_.ToString() }; exit $errori.Count"
    )
    assert esito.returncode == 0, esito.stdout.decode("utf-8", "replace")


@solo_windows
def test_porta_occupata_ne_sceglie_un_altra_e_lo_dice():
    esito = _funzioni(
        "$l = [System.Net.Sockets.TcpListener]::new([System.Net.IPAddress]::Loopback, 0); $l.Start(); "
        "$occupata = $l.LocalEndpoint.Port; "
        "$scelta = Get-PortaLibera $occupata; "
        "$libera = Test-PortaLibera $scelta; $l.Stop(); "
        "@{occupata=$occupata; scelta=$scelta; libera=$libera} | ConvertTo-Json -Compress"
    )
    uscita = esito.stdout.decode("utf-8")
    assert esito.returncode == 0, uscita + esito.stderr.decode("utf-8", "replace")
    dati = json.loads(uscita.strip().splitlines()[-1])
    assert dati["scelta"] != dati["occupata"]
    assert dati["libera"] is True
    assert "occupata" in uscita


@solo_windows
def test_uv_assente_esce_con_il_link_senza_toccare_il_documento():
    prima = DOCUMENTO.read_bytes()
    sistema = os.environ["SystemRoot"]
    ambiente = {**os.environ, "PATH": f"{sistema}\\System32;{sistema}\\System32\\WindowsPowerShell\\v1.0"}
    esito = subprocess.run(
        [f"{sistema}\\System32\\WindowsPowerShell\\v1.0\\powershell.exe", "-NoProfile",
         "-ExecutionPolicy", "Bypass", "-File", str(SCRIPT)],
        capture_output=True, stdin=subprocess.DEVNULL, env=ambiente, timeout=60,
    )
    assert esito.returncode != 0
    assert b"https://docs.astral.sh/uv/" in esito.stdout
    assert DOCUMENTO.read_bytes() == prima


@solo_windows
def test_meshrec_mai_in_ascolto_la_chiusura_e_non_riuscita_con_il_motivo():
    esito = _funzioni(
        "$l = [System.Net.Sockets.TcpListener]::new([System.Net.IPAddress]::Loopback, 0); $l.Start(); "
        "$porta = $l.LocalEndpoint.Port; $l.Stop(); "
        "$t = [Diagnostics.Stopwatch]::StartNew(); $ok = Wait-Ascolto $porta 2 $null; "
        "@{ok=$ok; secondi=$t.Elapsed.TotalSeconds} | ConvertTo-Json -Compress"
    )
    dati = json.loads(esito.stdout.decode("utf-8").strip().splitlines()[-1])
    assert dati["ok"] is False
    assert dati["secondi"] < 10


def _aggiorna(esiti_ps: str, testo: str) -> str:
    # Il testo va e torna in base64: niente file temporanei, niente code page.
    codificato = base64.b64encode(testo.encode("utf-8")).decode("ascii")
    esito = _funzioni(
        f"$testo = [Text.Encoding]::UTF8.GetString([Convert]::FromBase64String('{codificato}')); "
        f"$esiti = {esiti_ps}; "
        "$nuovo = Update-Documento $testo $esiti '13/09/2026' 'Ultima prova guidata: 13/09/2026'; "
        "[Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($nuovo))"
    )
    assert esito.returncode == 0, esito.stderr.decode("utf-8", "replace")
    return base64.b64decode(esito.stdout.decode("ascii").strip().splitlines()[-1]).decode("utf-8")


@solo_windows
def test_le_spunte_vecchie_restano_e_si_aggiornano_solo_le_voci_provate():
    testo = DOCUMENTO.read_text(encoding="utf-8")
    nuovo = _aggiorna("@{ viewport = @{ Ok = $true; Motivo = '' } }", testo)
    vecchie = [r for r in testo.splitlines() if "<!-- viewport -->" not in r and not r.startswith("Ultima prova")]
    nuove = [r for r in nuovo.splitlines() if "<!-- viewport -->" not in r and not r.startswith("Ultima prova")]
    assert vecchie == nuove
    assert sum(r.startswith("- [x]") for r in testo.splitlines()) + 1 == sum(
        r.startswith("- [x]") for r in nuovo.splitlines()
    )
    riga = next(r for r in nuovo.splitlines() if "<!-- viewport -->" in r)
    assert riga.startswith("- [x]") and "prova-windows.ps1" in riga and "13/09/2026" in riga
    assert "Ultima prova guidata: 13/09/2026" in nuovo


@solo_windows
def test_le_voci_senza_risposta_restano_non_spuntate_e_il_resto_si_scrive():
    testo = DOCUMENTO.read_text(encoding="utf-8")
    nuovo = _aggiorna(
        "@{ sfoglia = @{ Ok = $null; Motivo = 'finestra già chiusa' }; "
        "chiusura = @{ Ok = $false; Motivo = 'MeshRec non si è messo in ascolto entro 60 s' }; "
        "collegamento = @{ Ok = $true; Motivo = '' } }",
        testo,
    )
    righe = {v: next(r for r in nuovo.splitlines() if f"<!-- {v} -->" in r) for v in VOCI}
    assert righe["sfoglia"].startswith("- [ ]") and "non risposto" in righe["sfoglia"]
    assert righe["chiusura"].startswith("- [ ]") and "non riuscito" in righe["chiusura"]
    assert "entro 60 s" in righe["chiusura"]
    assert righe["collegamento"].startswith("- [x]")
