"""Riga di comando minima: eseguire una configurazione e generarne una di esempio."""

import pydantic
import pytest

import json

from meshrec import cli
from meshrec.core import config, io, synth
from corse_finte import _tre_cartelle_finte


SIZE = (120.0, 60.0, 240.0)


def _config_cubo_su_disco(tmp_path):
    """Configurazione del cubo scritta su disco, come negli altri test di questo file.

    `to_step=12` esplicito: non coincide col predefinito di RunConfig, che dal
    perimetro del prodotto vale 11, e questi test esercitano il comando `run` e la ripresa, non il
    solutore, e non devono dipendere da come quel predefinito cambia -- stessa
    ragione di `_config_cubo` in test_pipeline.py."""
    cloud_path = tmp_path / "box.ply"
    io.write_cloud(cloud_path, synth.sample_box_surface(SIZE, 8.0))
    cfg = config.PipelineConfig(
        input=config.InputConfig(path=cloud_path, spacing_sample=2000),
        downsample=config.DownsampleConfig(voxel_size=8.0),
        surface=config.SurfaceConfig(poisson_depth=7, density_quantile=0.02),
        # Stessa ragione di `_config_cubo` in test_pipeline.py: il predefinito
        # 6.0 e' tarato su un muro vero, e su un pezzo alto 240 mm la banda
        # supererebbe l'altezza nel maglio esaedrico della corsa figlia.
        export=config.ExportConfig(set_tolerance_factor=2.0),
        run=config.RunConfig(out_dir=tmp_path / "out", to_step=12),
    )
    config.save_config(cfg, tmp_path / "config.yaml")
    return tmp_path / "config.yaml"


def test_init_non_esiste_piu(tmp_path, capsys):
    """Ingresso degenere: qualcuno lancia ancora `meshrec init`.

    `init` scriveva una configurazione di esempio col materiale battuto a mano,
    e il materiale e' uscito il 08/09/2026 (PR feat/deck-nudo-analisi): si
    assegna in Abaqus sull'`*ELSET`. Un comando che scrive un blocco che il
    modello rifiuta produrrebbe un file che non si rilegge.

    Il rifiuto e' quello di `argparse` -- sottocomando sconosciuto, uscita 2 --
    e nessun file viene scritto.

    Mutazione che lo uccide: rimettere `add_parser("init", ...)`.
    """
    bersaglio = tmp_path / "config.yaml"

    with pytest.raises(SystemExit) as uscita:
        cli.main(["init", str(bersaglio), "--input", "nuvola.ply"])

    assert uscita.value.code == 2
    assert "invalid choice" in capsys.readouterr().err
    assert not bersaglio.exists()


def test_run_executes_the_pipeline_and_writes_the_deck(tmp_path):
    pytest.importorskip("pymeshfix")
    cloud_path = tmp_path / "box.ply"
    io.write_cloud(cloud_path, synth.sample_box_surface(SIZE, 8.0))
    cfg = config.PipelineConfig(
        input=config.InputConfig(path=cloud_path, spacing_sample=2000),
        downsample=config.DownsampleConfig(voxel_size=8.0),
        surface=config.SurfaceConfig(poisson_depth=7, density_quantile=0.02),
        # to_step=12: il test verifica che il comando run scriva il deck
        # (step 11), non che risolva -- stessa ragione di _config_cubo_su_disco.
        run=config.RunConfig(out_dir=tmp_path / "out", to_step=12),
    )
    config.save_config(cfg, tmp_path / "config.yaml")

    assert cli.main(["run", str(tmp_path / "config.yaml")]) == 0
    assert (tmp_path / "out" / "wall_model.inp").exists()


def test_from_step_overrides_the_configuration(tmp_path, monkeypatch):
    seen = {}

    def fake_run(cfg):
        seen["from_step"] = cfg.run.from_step
        return {}

    # Sul modulo e non su `cli.pipeline`: `cli` importa `pipeline` dentro il
    # ramo che lo usa e non in testa al file, cosi' la riga di comando non
    # muore all'import di open3d prima ancora di leggere gli argomenti.
    monkeypatch.setattr("meshrec.core.pipeline.run", fake_run)
    cfg = config.PipelineConfig(input=config.InputConfig(path="nuvola.ply"))
    config.save_config(cfg, tmp_path / "config.yaml")

    assert cli.main(["run", str(tmp_path / "config.yaml"), "--from-step", "5"]) == 0
    assert seen["from_step"] == 5


def test_a_failing_run_reports_the_error_without_a_traceback(tmp_path, capsys):
    # `out_dir` esplicito: questa corsa parte davvero, e il predefinito
    # `runs/default` e' relativo alla cartella da cui gira la suite -- il banco
    # lasciava `runs/default/` nella radice del repository a ogni giro.
    cfg = config.PipelineConfig(
        input=config.InputConfig(path=tmp_path / "assente.ply"),
        run=config.RunConfig(out_dir=tmp_path / "out"),
    )
    config.save_config(cfg, tmp_path / "config.yaml")

    assert cli.main(["run", str(tmp_path / "config.yaml")]) == 1
    err = capsys.readouterr().err
    assert "nessun punto letto" in err
    assert "Traceback" not in err


def test_from_step_out_of_domain_is_rejected_by_pydantic_not_a_keyerror(tmp_path, capsys):
    """13 e non 10: dal 30/08/2026 il tetto di `from_step` e' 12.

    Il valore era 10 perche' allora era il primo fuori dominio. Ora e' dentro,
    e con 10 questo test misurava un altro guasto -- l'artefatto mancante --
    invece del rifiuto di pydantic che gli da' il nome. Lo step 13 e' il primo
    fuori dominio oggi, e ci resta apposta: e' un'azione, non una ripresa.
    """
    cfg = config.PipelineConfig(input=config.InputConfig(path="nuvola.ply"))
    config.save_config(cfg, tmp_path / "config.yaml")

    assert cli.main(["run", str(tmp_path / "config.yaml"), "--from-step", "13"]) == 1
    err = capsys.readouterr().err
    assert "KeyError" not in err
    assert "from_step" in err


def test_run_config_rejects_an_out_of_domain_assignment(tmp_path):
    cfg = config.PipelineConfig(input=config.InputConfig(path="nuvola.ply"))
    with pytest.raises(pydantic.ValidationError):
        cfg.run.from_step = 999


def test_the_sweep_command_runs_a_two_candidate_grid_on_the_synthetic_cube(tmp_path):
    """Prova end-to-end del motore: griglia, sottoprocessi, registro, fronte.

    Il cubo e' l'unica geometria su cui la catena intera sta dentro la suite.
    Verifica che la catena non si spezzi, non che produca qualcosa di
    sensato: quello si misura sulle due corse reali, fuori dai test.
    """
    import yaml

    from meshrec.core import config, io, synth, sweep

    cloud = tmp_path / "cubo.ply"
    io.write_cloud(cloud, synth.sample_box_surface(size=(100.0, 40.0, 200.0), spacing=4.0))
    base = config.PipelineConfig(
        input=config.InputConfig(path=str(cloud)),
        surface=config.SurfaceConfig(poisson_depth=6),
    )
    base_path = tmp_path / "base.yaml"
    config.save_config(base, base_path)

    experiment = config.ExperimentConfig(
        name="cubo",
        base=base_path,
        axes=[config.AxisSpec(path="tet.min_ratio", values=[2.0])],
        sweep=config.SweepConfig(
            workers=2, runs_root=tmp_path / "runs", registry_root=tmp_path / "experiments"
        ),
    )
    experiment_path = tmp_path / "cubo.yaml"
    experiment_path.write_text(
        yaml.safe_dump(experiment.model_dump(mode="json"), sort_keys=False), encoding="utf-8"
    )

    # Con due soli candidati confrontabili il fronte li contiene entrambi:
    # e' il caso "non discrimina" gia' previsto da check_sweep, atteso qui.
    with pytest.warns(sweep.SweepDiagnosticWarning, match="non discrimina"):
        assert cli.main(["sweep", str(experiment_path)]) == 0

    registry = tmp_path / "experiments" / "cubo" / "registro.jsonl"
    rows = sweep.load_registry(registry)
    assert len(rows) == 2
    assert all(row["outcome"] == "riuscito" for row in rows)
    assert any(row["on_front"] for row in rows)

    assert cli.main(["sweep-verify", str(registry)]) == 0
    assert cli.main(["sweep-report", str(registry), "--out", str(tmp_path / "r.html")]) == 0
    assert (tmp_path / "r.html").exists()


def test_sweep_verify_reports_a_nonzero_exit_when_an_artifact_row_is_stale(tmp_path):
    """sweep-verify deve fermare uno script quando il registro non torna piu' col disco."""
    from meshrec.core import sweep

    out_dir = tmp_path / "run"
    out_dir.mkdir()
    artifact = out_dir / "wall_model.inp"
    artifact.write_text("originale", encoding="utf-8")

    registry = tmp_path / "registro.jsonl"
    sweep.append_row(
        registry,
        {
            "fingerprint": "deadbeef0000",
            "out_dir": str(out_dir),
            "artifacts": {"wall_model.inp": sweep.file_digest(artifact)},
            "artifacts_kept": True,
        },
    )

    # L'artefatto cambia dopo la scrittura della riga: l'impronta non torna piu'.
    artifact.write_text("alterato", encoding="utf-8")

    assert cli.main(["sweep-verify", str(registry)]) == 1


def test_only_step_esegue_soltanto_quello(tmp_path, capsys):
    from meshrec import cli

    percorso = _config_cubo_su_disco(tmp_path)   # helper gia' presente nel file
    assert cli.main(["run", str(percorso), "--only-step", "1"]) == 0
    uscita = json.loads(capsys.readouterr().out)
    assert set(uscita) == {"01_load"}


def test_uno_step_parte_anche_se_il_config_su_disco_e_gia_ristretto(tmp_path):
    """E' il caso del worker: ogni step passa da qui, e la configurazione sul
    disco puo' portare un to_step piu' piccolo dello step che si chiede."""
    percorso = _config_cubo_su_disco(tmp_path)
    cfg = config.load_config(percorso)
    cfg.run.to_step = 1
    config.save_config(cfg, percorso)

    assert cli.main(["run", str(percorso), "--only-step", "1"]) == 0
    assert cli.main(["run", str(percorso), "--from-step", "2", "--to-step", "2"]) == 0


def test_uno_step_parte_anche_se_il_config_su_disco_parte_piu_avanti(tmp_path):
    """L'altro verso dello stesso invariante, trovato usando il pannello.

    Dopo un "esegui da qui in giu'" dallo step 4 la configurazione sul disco
    porta from_step=4. Chiedere poi lo step 1 assegnava to_step=1 su uno stato
    che aveva ancora from_step=4, e la corsa moriva con un ValidationError che
    l'interfaccia non mostrava.
    """
    percorso = _config_cubo_su_disco(tmp_path)
    cfg = config.load_config(percorso)
    cfg.run.to_step = 11
    cfg.run.from_step = 4
    config.save_config(cfg, percorso)

    assert cli.main(["run", str(percorso), "--only-step", "1"]) == 0
    assert cli.main(["run", str(percorso), "--from-step", "1", "--to-step", "1"]) == 0


def test_the_sweep_command_reports_the_thickness_gate_failure(tmp_path, capsys):
    """Il cancello sulla misura di spessore ferma lo sweep prima di partire.

    L'uscita e' 1 e il messaggio del cancello compare su stderr: che dica
    perche' si ferma conta quanto il fatto che si fermi.
    """
    import yaml

    from meshrec.core import config, io, synth

    cloud = tmp_path / "cubo.ply"
    io.write_cloud(cloud, synth.sample_box_surface(size=(100.0, 40.0, 200.0), spacing=4.0))
    base = config.PipelineConfig(
        input=config.InputConfig(path=str(cloud)),
        surface=config.SurfaceConfig(poisson_depth=6),
    )
    base_path = tmp_path / "base.yaml"
    config.save_config(base, base_path)

    experiment = config.ExperimentConfig(
        name="cubo",
        base=base_path,
        axes=[config.AxisSpec(path="tet.min_ratio", values=[2.0])],
        known_thickness=1.0,  # incoerente con il cubo sintetico: scarto oltre il 5%
        sweep=config.SweepConfig(
            workers=2, runs_root=tmp_path / "runs", registry_root=tmp_path / "experiments"
        ),
    )
    experiment_path = tmp_path / "cubo.yaml"
    experiment_path.write_text(
        yaml.safe_dump(experiment.model_dump(mode="json"), sort_keys=False), encoding="utf-8"
    )

    result = cli.main(["sweep", str(experiment_path)])
    err = capsys.readouterr().err
    assert result == 1
    assert "la misura di spessore non riproduce il valore noto" in err


def test_il_comando_wall_ricalcola_il_solo_prior(tmp_path, capsys):
    """Il prior e' un'azione e non una ripresa: legge l'artefatto dello step 2
    gia' sul disco e non rifa' nulla di cio' che sta a monte."""
    import json

    from meshrec.core import pipeline

    percorso = _config_cubo_su_disco(tmp_path)
    cfg = config.load_config(percorso)
    cfg.run.to_step = 2
    config.save_config(cfg, percorso)
    pipeline.run(cfg)

    assert cli.main(["wall", str(percorso)]) == 0

    scritto = json.loads(
        (cfg.run.out_dir / pipeline.WALL_FILENAME).read_text(encoding="utf-8")
    )
    assert "membrature" in scritto
    assert json.loads(capsys.readouterr().out)["regioni_trovate"] == scritto["regioni_trovate"]


def test_il_comando_wall_senza_lo_step_due_dice_che_cosa_manca(tmp_path, capsys):
    """Chi arriva dopo non conosce gli step: l'errore dice quale artefatto
    manca e come ottenerlo, non solo che un file non c'e'."""
    percorso = _config_cubo_su_disco(tmp_path)

    assert cli.main(["wall", str(percorso)]) == 1
    assert "02_segmented.ply" in capsys.readouterr().err


def _corsa_col_deck(tmp_path):
    """Una corsa portata fino al deck, che e' l'ingresso dello step 13."""
    from meshrec.core import pipeline

    percorso = _config_cubo_su_disco(tmp_path)
    cfg = config.load_config(percorso)
    cfg.run.to_step = 11
    config.save_config(cfg, percorso)
    pipeline.run(cfg)
    return percorso


def test_il_comando_model_scrive_la_cartella_col_suffisso_del_tipo(tmp_path):
    """La cartella predefinita e' quella della madre col suffisso: nessuna
    corsa figlia scrive dentro la cartella della madre, che e' il risultato di
    un'altra elaborazione.

    Mutazione che deve morire: in `cli.main`, cambiare
    `madre.with_name(f"{madre.name}-{args.tipo}")` in `madre` (nessun
    suffisso) -- la seconda asserzione noterebbe `modello.json` scritto nella
    cartella della madre.
    """
    from meshrec.core import pipeline

    percorso = _config_cubo_su_disco(tmp_path)
    cfg = config.load_config(percorso)
    pipeline.run(cfg)

    assert cli.main(["model", str(percorso), "--tipo", "primitive"]) == 0

    madre = cfg.run.out_dir
    figlia = madre.with_name(f"{madre.name}-primitive")
    assert (figlia / "wall_model.inp").exists()
    assert not (madre / pipeline.MODEL_FILENAME).exists()


def test_il_comando_model_senza_il_prior_dice_che_cosa_manca(tmp_path, capsys):
    """Gemello di `test_il_comando_wall_senza_lo_step_due_dice_che_cosa_manca`:
    il ramo d'errore del comando `model` non aveva copertura. `genera_modello`
    solleva `FileNotFoundError` ed e' testata direttamente in
    `test_pipeline.py`, ma nulla provava che `cli.main` la catturi ancora, con
    lo stesso codice d'uscita e lo stesso testo su stderr.

    Mutazione che deve morire: nel ramo `model` di `cli.main`, rimuovere il
    `try/except` (o farlo rilanciare invece di stampare e restituire 1) --
    `cli.main` solleverebbe l'eccezione invece di restituire 1, e la prima
    asserzione fallirebbe.
    """
    percorso = _config_cubo_su_disco(tmp_path)

    assert cli.main(["model", str(percorso), "--tipo", "estruso"]) == 1
    assert "12_wall.json" in capsys.readouterr().err


def test_il_comando_compare_scrive_la_pagina_e_nomina_i_modelli_assenti(tmp_path, capsys):
    """Stesso banco di test_report.py: una definizione sola in corse_finte.py,
    perche' tests/ non e' un pacchetto e un import fra file di test per nome
    puntato non risolverebbe."""
    cartelle = _tre_cartelle_finte(tmp_path)[:2]
    uscita = tmp_path / "confronto.html"

    assert cli.main(["compare", *[str(c) for c in cartelle], "--out", str(uscita)]) == 0
    assert "non generato" in uscita.read_text(encoding="utf-8")
    assert str(uscita) in capsys.readouterr().out


from pathlib import Path  # noqa: E402
from typing import NamedTuple  # noqa: E402



def test_la_porta_occupata_si_dice_prima_di_annunciare_l_ascolto(capsys):
    """Il difetto che ha fatto lavorare l'utente per ore sul codice vecchio.

    `serve` stampava «MeshRec in ascolto su ...» e apriva il browser PRIMA che
    uvicorn provasse il bind. Con la porta gia' occupata da un'altra copia
    rimasta viva, l'annuncio era falso e il browser si apriva su quella copia:
    l'utente vedeva l'interfaccia, la usava, e ogni correzione appena
    installata non era in quel processo.

    Il banco occupa davvero la porta con un socket, poi chiama `serve`.
    """
    import socket as _socket

    occupante = _socket.socket(_socket.AF_INET, _socket.SOCK_STREAM)
    occupante.bind(("127.0.0.1", 0))
    porta = occupante.getsockname()[1]
    occupante.listen(1)
    try:
        codice = cli.main(["serve", "--port", str(porta), "--no-browser"])
    finally:
        occupante.close()

    assert codice == 1
    detto = capsys.readouterr().err
    assert f"la porta {porta} è già occupata" in detto
    assert "un'altra copia di MeshRec" in detto
    assert "--port" in detto
    # E soprattutto: non deve aver annunciato un ascolto che non c'e'.
    assert "in ascolto" not in detto


def test_un_errore_che_il_programma_non_ha_previsto_porta_la_propria_traccia(tmp_path, capsys):
    """Una riga sola non basta per un guasto che nessuno ha scritto.

    Misurato il 30/08/2026: `UnicodeDecodeError: 'utf-8' codec can't decode
    byte 0xe0 in position 79` e' arrivato all'utente senza dire quale file
    stesse leggendo. Senza la traccia non era diagnosticabile.

    Un `ValueError` resta invece una riga sola: e' il modo in cui questo
    programma parla all'operatore, e la traccia sopra lo seppellirebbe.
    """
    configurazione = tmp_path / "config.yaml"
    configurazione.write_bytes(b"input:\n  path: nuvola.ply\n  scale: 1.0\n")

    def esplode(_cfg):
        raise UnicodeDecodeError("utf-8", b"\xe0", 0, 1, "invalid continuation byte")

    import meshrec.core.pipeline as _pipeline

    originale = _pipeline.run
    _pipeline.run = esplode
    try:
        codice = cli.main(["run", str(configurazione)])
    finally:
        _pipeline.run = originale

    assert codice == 1
    detto = capsys.readouterr().err
    assert "UnicodeDecodeError" in detto
    assert "Traceback" in detto, "senza la traccia l'errore non dice che cosa leggeva"


def test_un_errore_scritto_dal_programma_resta_una_riga_sola(tmp_path, capsys):
    """La controprova: senza, basterebbe stampare sempre la traccia."""
    configurazione = tmp_path / "config.yaml"
    configurazione.write_bytes(b"input:\n  path: nuvola.ply\n  scale: 1.0\n")

    def rifiuta(_cfg):
        raise ValueError("la nuvola non ha punti: controlla input.path")

    import meshrec.core.pipeline as _pipeline

    originale = _pipeline.run
    _pipeline.run = rifiuta
    try:
        codice = cli.main(["run", str(configurazione)])
    finally:
        _pipeline.run = originale

    assert codice == 1
    detto = capsys.readouterr().err
    assert "controlla input.path" in detto
    assert "Traceback" not in detto


def _porta_libera():
    """Bind su 0, leggi la porta, chiudi: stessa forma di test_la_porta_occupata..."""
    import socket as _socket

    libera = _socket.socket(_socket.AF_INET, _socket.SOCK_STREAM)
    libera.bind(("127.0.0.1", 0))
    porta = libera.getsockname()[1]
    libera.close()
    return porta


def _server_finto(monkeypatch):
    """uvicorn.Server finto: «parte» subito e registra should_exit."""
    import uvicorn

    stato = {"should_exit": False, "serviti": 0}

    class Server:
        def __init__(self, config):
            self.config = config
            stato["config"] = config
            self.started = True

        @property
        def should_exit(self):
            return stato["should_exit"]

        @should_exit.setter
        def should_exit(self, valore):
            stato["should_exit"] = valore

        def run(self):
            stato["serviti"] += 1
            while not stato["should_exit"]:
                import time

                time.sleep(0.01)

    monkeypatch.setattr(uvicorn, "Server", Server)
    return stato


def test_serve_apre_la_finestra_e_ferma_il_server_quando_si_chiude(monkeypatch, capsys):
    from meshrec.app import finestra

    stato = _server_finto(monkeypatch)
    chiamate = []

    def apri(indirizzo, *, cache, porta, forza_browser=False, avvisa=None):
        chiamate.append((indirizzo, forza_browser))
        return "finestra"

    monkeypatch.setattr(finestra, "apri", apri)
    codice = cli.main(["serve", "--port", str(_porta_libera())])
    assert codice == 0
    assert stato["serviti"] == 1
    assert stato["should_exit"] is True
    assert chiamate and chiamate[0][1] is False
    assert "MeshRec in ascolto su" in capsys.readouterr().err


def test_serve_passa_porta_e_cache_assoluta_ad_apri(monkeypatch):
    """Punti 2 e 3 fix wave: il profilo Chromium e' per porta, e `cache' e'
    assoluta (security minor)."""
    from meshrec.app import finestra

    _server_finto(monkeypatch)
    ricevuto = {}
    porta = _porta_libera()

    def apri(indirizzo, *, cache, porta, forza_browser=False, avvisa=None):
        ricevuto["cache"] = cache
        ricevuto["porta"] = porta
        return "finestra"

    monkeypatch.setattr(finestra, "apri", apri)
    assert cli.main(["serve", "--port", str(porta)]) == 0
    assert ricevuto["porta"] == porta
    assert ricevuto["cache"].is_absolute()


def test_serve_browser_forza_il_browser_e_resta_in_ascolto_fino_a_should_exit(monkeypatch):
    from meshrec.app import finestra
    import threading

    stato = _server_finto(monkeypatch)
    chiamate = []

    def apri(indirizzo, *, cache, porta, forza_browser=False, avvisa=None):
        chiamate.append(forza_browser)
        # Nel ramo browser il server resta vivo: qualcuno deve fermarlo.
        threading.Timer(0.05, lambda: stato.__setitem__("should_exit", True)).start()
        return "browser"

    monkeypatch.setattr(finestra, "apri", apri)
    assert cli.main(["serve", "--port", str(_porta_libera()), "--browser"]) == 0
    assert chiamate == [True]


def test_serve_no_browser_non_apre_nulla(monkeypatch):
    from meshrec.app import finestra
    import threading

    stato = _server_finto(monkeypatch)
    monkeypatch.setattr(finestra, "apri", lambda *a, **k: pytest.fail("non doveva aprire"))
    threading.Timer(0.05, lambda: stato.__setitem__("should_exit", True)).start()
    assert cli.main(["serve", "--port", str(_porta_libera()), "--no-browser"]) == 0


def test_se_il_server_non_parte_entro_il_tempo_serve_lo_dice(monkeypatch, capsys):
    import uvicorn

    class ServerCheNonParte:
        def __init__(self, config):
            self.started = False
            self.should_exit = False

        def run(self):
            while not self.should_exit:
                import time

                time.sleep(0.01)

    monkeypatch.setattr(uvicorn, "Server", ServerCheNonParte)
    monkeypatch.setattr(cli, "ATTESA_AVVIO_S", 0.2)
    assert cli.main(["serve", "--port", str(_porta_libera()), "--no-browser"]) == 1
    assert "non si è messo in ascolto" in capsys.readouterr().err


def test_serve_col_no_browser_il_timeout_non_suggerisce_no_browser(monkeypatch, capsys):
    """Minor: l'utente l'ha gia' usato, il suggerimento non ha senso."""
    import uvicorn

    class ServerCheNonParte:
        def __init__(self, config):
            self.started = False
            self.should_exit = False

        def run(self):
            while not self.should_exit:
                import time

                time.sleep(0.01)

    monkeypatch.setattr(uvicorn, "Server", ServerCheNonParte)
    monkeypatch.setattr(cli, "ATTESA_AVVIO_S", 0.2)
    assert cli.main(["serve", "--port", str(_porta_libera()), "--no-browser"]) == 1
    detto = capsys.readouterr().err
    assert "l'errore di uvicorn è qui sopra" in detto
    assert "--no-browser" not in detto.split("qui sopra")[-1]


def test_serve_col_server_lento_a_fermarsi_main_torna_entro_5s(monkeypatch):
    """Punto 7 fix wave (test mancante): un `run()` che ignora `should_exit`
    per 0,3 s non deve far restare `main` appeso oltre `join(timeout=5)`."""
    import time as _time

    import uvicorn

    from meshrec.app import finestra

    class ServerLento:
        def __init__(self, config):
            self.started = True
            self.should_exit = False

        def run(self):
            scadenza = _time.monotonic() + 0.3
            while _time.monotonic() < scadenza:
                _time.sleep(0.01)
            while not self.should_exit:
                _time.sleep(0.01)

    monkeypatch.setattr(uvicorn, "Server", ServerLento)
    monkeypatch.setattr(finestra, "apri", lambda *a, **k: "finestra")
    inizio = _time.monotonic()
    codice = cli.main(["serve", "--port", str(_porta_libera())])
    durata = _time.monotonic() - inizio
    assert codice == 0
    assert durata < 5


def test_serve_col_server_che_parte_al_terzo_giro_di_polling(monkeypatch, capsys):
    """Punto 7 fix wave (test mancante): `started` non immediato -- il
    polling deve comunque rilevare l'avvio."""
    import time as _time

    import uvicorn

    from meshrec.app import finestra

    letture = {"n": 0}

    class Server:
        def __init__(self, config):
            self._should_exit = False

        @property
        def started(self):
            letture["n"] += 1
            return letture["n"] >= 3

        @property
        def should_exit(self):
            return self._should_exit

        @should_exit.setter
        def should_exit(self, valore):
            self._should_exit = valore

        def run(self):
            while not self._should_exit:
                _time.sleep(0.01)

    monkeypatch.setattr(uvicorn, "Server", Server)
    monkeypatch.setattr(finestra, "apri", lambda *a, **k: "finestra")
    codice = cli.main(["serve", "--port", str(_porta_libera())])
    assert codice == 0
    assert letture["n"] >= 3
    assert "MeshRec in ascolto su" in capsys.readouterr().err


def test_serve_se_il_guscio_solleva_ferma_comunque_il_server(monkeypatch, capsys):
    from meshrec.app import finestra

    stato = _server_finto(monkeypatch)

    def apri(indirizzo, *, cache, porta, forza_browser=False, avvisa=None):
        raise RuntimeError("cocoa")

    monkeypatch.setattr(finestra, "apri", apri)
    codice = cli.main(["serve", "--port", str(_porta_libera())])
    assert codice == 1
    assert stato["should_exit"] is True
    assert "cocoa" in capsys.readouterr().err


# --- Chiusura della finestra: il bug del 12/09/2026 -------------------------
# Sintomo di Mario: chiusa la finestra, il rilancio dice «la porta 8765 e' gia'
# occupata» e il launcher del bundle mostra il dialogo d'errore. Misurato con
# la finestra vera (scratchpad/repro-chiusura.py, giro C): il processo esce
# 5,34 s dopo la chiusura -- cioe' `join(timeout=5)` scaduto -- e la porta
# resta non-bindabile per 30,67 s. Senza connessione SSE aperta: 0,67 s.
# I due test qui sotto tengono i due anelli della catena.


def test_lo_spegnimento_non_resta_appeso_su_una_connessione_sse(monkeypatch):
    """`should_exit` deve fermare uvicorn anche con `/api/events` aperto.

    `flusso()` (server.py:2053-2106) e' un generatore SINCRONO con `while True`
    e `time.sleep(0.5)`: non guarda ne' la disconnessione del client ne'
    `should_exit`. Starlette lo fa girare in un thread del pool anyio, e finche'
    quel thread gira la connessione resta in `server_state.connections`; con
    `timeout_graceful_shutdown` a None (il default, che cli.py non cambia)
    `Server.shutdown()` ci aspetta sopra per sempre.

    L'interfaccia apre quella connessione al caricamento, sempre
    (app.js:816, `EventSource("/api/events")`): questo non e' un caso limite,
    e' il caso normale di ogni finestra aperta.
    """
    import threading
    import time
    import urllib.request

    import uvicorn

    from meshrec.app.server import create_app
    from meshrec.app.worker import Worker

    # Il tetto graceful qui vale 30 s, non i 2 di `serve`, ed e' voluto: cosi'
    # l'unica cosa che puo' far finire il thread entro il `join(timeout=5)` e'
    # `spegni`, cioe' il generatore che si accorge da se' dello spegnimento. Con
    # 2 s il test sarebbe verde anche con il `time.sleep(0.5)` di prima, cioe'
    # non pinnerebbe niente: lo spegnimento lo chiuderebbe uvicorn cancellando i
    # task allo scadere del tetto. Che il tetto vero sia 2 lo pinna
    # test_serve_mette_un_tetto_allo_spegnimento_di_uvicorn.
    annullamenti = []
    monkeypatch.setattr(Worker, "cancel", lambda self: annullamenti.append(1))
    porta = _porta_libera()
    app = create_app(None)
    server = uvicorn.Server(uvicorn.Config(
        app, host="127.0.0.1", port=porta, log_level="warning",
        timeout_graceful_shutdown=30,
    ))
    thread = threading.Thread(target=server.run, name="uvicorn", daemon=True)
    thread.start()
    scadenza = time.monotonic() + 10
    while not server.started and thread.is_alive() and time.monotonic() < scadenza:
        time.sleep(0.05)
    assert server.started, "il server di prova non si e' messo in ascolto"

    flusso = urllib.request.urlopen(f"http://127.0.0.1:{porta}/api/events", timeout=10)
    try:
        # La prima riga prova che lo stream e' vivo: senza, il test passerebbe
        # anche solo perche' la connessione non e' mai stata servita.
        assert flusso.readline().startswith(b"event: stato")
        app.state.spegni.set()
        server.should_exit = True
        thread.join(timeout=5)
        assert not thread.is_alive(), (
            "uvicorn non si e' spento entro 5 s con una connessione SSE aperta: "
            "e' il join(timeout=5) di cli.py che scade, e la porta resta occupata"
        )
        assert annullamenti, (
            "il lifespan non e' scattato: `lavoratore.cancel()` resta codice morto "
            "e lo step in corso resta orfano alla chiusura della finestra"
        )
    finally:
        flusso.close()
        server.should_exit = True


def test_la_sonda_della_porta_non_si_fa_ingannare_da_un_time_wait(monkeypatch, capsys):
    """Rilanciare subito dopo la chiusura deve funzionare.

    Il processo muore lasciando la connessione SSE in TIME_WAIT su quella
    porta: ~30 s in cui il `bind` nudo di cli.py:249-265 da' EADDRINUSE, mentre
    uvicorn (asyncio, `reuse_address=True`) ci si sarebbe messo in ascolto
    benissimo. Il messaggio «la porta ... e' gia' occupata» e' quindi falso:
    accusa una copia viva di MeshRec che non esiste piu'.
    """
    import socket as _socket

    from meshrec.app import finestra

    ascolto = _socket.socket(_socket.AF_INET, _socket.SOCK_STREAM)
    ascolto.setsockopt(_socket.SOL_SOCKET, _socket.SO_REUSEADDR, 1)
    ascolto.bind(("127.0.0.1", 0))
    porta = ascolto.getsockname()[1]
    ascolto.listen(1)
    cliente = _socket.create_connection(("127.0.0.1", porta))
    servito, _ = ascolto.accept()
    ascolto.close()
    servito.close()  # il lato server chiude per primo: TIME_WAIT su questa porta
    cliente.close()

    _server_finto(monkeypatch)
    monkeypatch.setattr(finestra, "apri", lambda *a, **k: "finestra")
    codice = cli.main(["serve", "--port", str(porta)])
    catturato = capsys.readouterr().err
    assert "già occupata" not in catturato, (
        "la sonda accusa una porta che e' solo in TIME_WAIT dalla corsa di prima"
    )
    assert codice == 0


def test_lo_spegnimento_senza_nessun_client_sse_resta_immediato():
    """Il rovescio del test qui sopra: senza connessioni la chiusura deve
    restare istantanea (0,67 s misurati il 12/09), non farsi rallentare dal
    tetto graceful ne' dall'attesa dell'Event di spegnimento."""
    import threading
    import time

    import uvicorn

    from meshrec.app.server import create_app

    porta = _porta_libera()
    server = uvicorn.Server(uvicorn.Config(
        create_app(None), host="127.0.0.1", port=porta, log_level="warning",
        timeout_graceful_shutdown=2,
    ))
    thread = threading.Thread(target=server.run, name="uvicorn", daemon=True)
    thread.start()
    scadenza = time.monotonic() + 10
    while not server.started and thread.is_alive() and time.monotonic() < scadenza:
        time.sleep(0.05)
    assert server.started, "il server di prova non si e' messo in ascolto"
    try:
        server.should_exit = True
        thread.join(timeout=2)
        assert not thread.is_alive()
    finally:
        server.should_exit = True


def test_serve_mette_un_tetto_allo_spegnimento_di_uvicorn(monkeypatch):
    """Senza `timeout_graceful_shutdown`, `Server.shutdown()` aspetta ogni
    connessione SSE per sempre: il `join(timeout=5)` di serve scade e il
    processo muore a meta' spegnimento, lasciando la porta in TIME_WAIT. Il
    tetto sta sotto quel join, e va tenuto sotto."""
    from meshrec.app import finestra

    stato = _server_finto(monkeypatch)
    monkeypatch.setattr(finestra, "apri", lambda *a, **k: "finestra")
    assert cli.main(["serve", "--port", str(_porta_libera())]) == 0
    assert stato["config"].timeout_graceful_shutdown == 2
    assert stato["config"].timeout_graceful_shutdown < 5


def test_su_windows_la_sonda_non_scambia_reuseaddr_per_cortesia(monkeypatch):
    """Su Windows `SO_REUSEADDR` lascia bindare SOPRA un listener **attivo**:
    la sonda diventerebbe cieca esattamente nel caso per cui esiste — la copia
    vecchia rimasta in ascolto — e `MeshRec.bat` e' un bersaglio spedito. Li'
    il bind resta nudo, TIME_WAIT compreso."""
    import socket as _socket
    import sys as _sys

    from meshrec.app import finestra

    opzioni = []
    vero = _socket.socket

    class Spia(vero):
        def setsockopt(self, livello, nome, valore):
            opzioni.append((livello, nome, valore))
            return super().setsockopt(livello, nome, valore)

    porta = _porta_libera()
    monkeypatch.setattr(_socket, "socket", Spia)
    monkeypatch.setattr(_sys, "platform", "win32")
    _server_finto(monkeypatch)
    monkeypatch.setattr(finestra, "apri", lambda *a, **k: "finestra")
    assert cli.main(["serve", "--port", str(porta)]) == 0
    assert (_socket.SOL_SOCKET, _socket.SO_REUSEADDR, 1) not in opzioni, (
        "la sonda ha chiesto SO_REUSEADDR su win32: li' permette il bind sopra "
        "un listener vivo, cioe' spegne la sonda"
    )


# --- Client SSE che se ne va --------------------------------------------------
# `flusso()` di /api/events e' un generatore sincrono: da solo non si accorge che
# il client ha chiuso. Oggi non serve, perche' uvicorn dichiara ASGI 2.3 e con
# la 2.3 lo StreamingResponse di starlette ascolta `http.disconnect` e cancella
# lo stream (starlette/responses.py, ramo `spec_version < 2.4`). Con la 2.4
# starlette smette di ascoltare e si fida di un OSError su `send` che uvicorn
# non solleva: misurato il 13/09/2026, 3 client chiusi = 3 thread fermi in
# flusso() per sempre, e dopo 40 il pool anyio e' esaurito.
# ponytail: guardia, non fix. Se diventa rosso dopo un aggiornamento di uvicorn
# o starlette, il fix e' `flusso` async con `await request.is_disconnected()`.


def _thread_dentro_flusso():
    """Thread fuori dal ciclo eventi con `flusso` sullo stack, cioe' fermi li'."""
    import sys
    import threading

    nomi = {t.ident: t.name for t in threading.enumerate()}
    fermi = 0
    for ident, quadro in sys._current_frames().items():
        if nomi.get(ident) == "uvicorn":
            continue
        while quadro is not None:
            if quadro.f_code.co_name == "flusso":
                fermi += 1
                break
            quadro = quadro.f_back
    return fermi


def test_i_client_sse_che_se_ne_vanno_non_lasciano_thread_appesi():
    import socket as _socket
    import threading
    import time

    import uvicorn

    from meshrec.app.server import create_app

    server = uvicorn.Server(uvicorn.Config(
        create_app(None), host="127.0.0.1", port=_porta_libera(), log_level="warning", log_config=None,
    ))
    thread = threading.Thread(target=server.run, name="uvicorn", daemon=True)
    thread.start()
    scadenza = time.monotonic() + 10
    while not server.started and thread.is_alive() and time.monotonic() < scadenza:
        time.sleep(0.05)
    assert server.started, "il server di prova non si e' messo in ascolto"
    try:
        for _ in range(3):
            presa = _socket.create_connection(("127.0.0.1", server.config.port), timeout=5)
            try:
                presa.sendall(b"GET /api/events HTTP/1.1\r\nHost: 127.0.0.1\r\n\r\n")
                letto = b""
                while b"event: stato" not in letto:
                    pezzo = presa.recv(4096)
                    assert pezzo, "il server ha chiuso prima del primo evento"
                    letto += pezzo
            finally:
                presa.close()
        scadenza = time.monotonic() + 5
        while _thread_dentro_flusso() and time.monotonic() < scadenza:
            time.sleep(0.05)
        rimasti = _thread_dentro_flusso()
        assert rimasti == 0, (
            f"{rimasti} thread restano dentro flusso() dopo 3 client chiusi: "
            "uvicorn/starlette non segnalano piu' la disconnessione (ASGI 2.4?)"
        )
    finally:
        server.should_exit = True
        thread.join(timeout=5)
