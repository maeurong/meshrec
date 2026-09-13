"""Il motore di sweep: impronta, griglia, registro, dominanza."""

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from meshrec.core import config, pipeline, steps, sweep



def _base() -> config.PipelineConfig:
    return config.PipelineConfig(input=config.InputConfig(path="nuvola.ply", scale=1000.0))


def test_un_candidato_fallito_porta_ancora_le_sue_metriche_parziali(tmp_path):
    """La Fase 2 legge metrics.json anche dai candidati falliti: con la
    correzione quel file non esiste piu', e la riga deve leggere il parziale.
    """
    from meshrec.core import pipeline, sweep

    cartella = tmp_path / "candidato"
    cartella.mkdir()
    (cartella / pipeline.METRICS_PARTIAL).write_text(
        json.dumps({"01_load": {"spacing": 1.19}}), encoding="utf-8"
    )
    lette = sweep.leggi_metriche(cartella)
    assert lette["01_load"]["spacing"] == pytest.approx(1.19)
    assert sweep.is_complete(lette) is False


def test_il_parziale_non_viene_contato_fra_gli_artefatti():
    assert pipeline.METRICS_PARTIAL in sweep._CANDIDATE_FILES


def test_the_fingerprint_ignores_where_the_run_is_written():
    """out_dir e from_step non cambiano il risultato, quindi non cambiano l'identita'.

    Includerli renderebbe diverse due corse identiche, che e' esattamente cio'
    che l'impronta esiste per impedire.
    """
    here = _base()
    elsewhere = _base()
    elsewhere.run.out_dir = Path("runs/altrove")
    elsewhere.run.from_step = 9

    assert sweep.fingerprint(here) == sweep.fingerprint(elsewhere)


def test_the_fingerprint_changes_with_any_processing_parameter():
    changed = sweep.with_override(_base(), "tet.min_ratio", 2.5)

    assert sweep.fingerprint(changed) != sweep.fingerprint(_base())
    assert changed.tet.min_ratio == pytest.approx(2.5)
    assert _base().tet.min_ratio == pytest.approx(1.8)


def test_la_tolleranza_degli_insiemi_e_un_asse_e_resta_validata():
    """`export.set_tolerance_factor` e' un asse di sweep come `tet.min_ratio`.

    `with_override` passa dal dump e da `model_validate` proprio per non
    lasciare entrare un valore fuori dominio: sull'asse nuovo lo si pretende
    qui, perche' `gt=0` sul campo non basta se la strada dello sweep lo aggira.

    Mutazione che lo uccide: tornare ad assegnare l'attributo. Lo zero passa
    intatto fino allo step 11.
    """
    cambiata = sweep.with_override(_base(), "export.set_tolerance_factor", 4.0)

    assert cambiata.export.set_tolerance_factor == pytest.approx(4.0)
    assert sweep.fingerprint(cambiata) != sweep.fingerprint(_base())

    with pytest.raises(ValidationError):
        sweep.with_override(_base(), "export.set_tolerance_factor", 0.0)


def test_one_axis_at_a_time_does_not_multiply_the_levels():
    """Tre livelli su due assi sono cinque candidati, non nove: uno per livello piu la base."""
    experiment = config.ExperimentConfig(
        name="prova",
        base=Path("muro.yaml"),
        axes=[
            config.AxisSpec(path="tet.min_ratio", values=[1.7, 1.8, 2.0]),
            config.AxisSpec(path="surface.poisson_depth", values=[8, 9, 10]),
        ],
    )

    candidates = sweep.expand(experiment, _base())

    assert len(candidates) == 5
    assert len({sweep.fingerprint(cfg) for _, cfg in candidates}) == 5
    assert any(axes == {} for axes, _ in candidates)


def test_a_declared_pair_is_crossed_in_full():
    experiment = config.ExperimentConfig(
        name="prova",
        base=Path("muro.yaml"),
        axes=[
            config.AxisSpec(path="tet.min_ratio", values=[1.8, 2.0]),
            config.AxisSpec(path="tet.nobisect", values=[False, True]),
        ],
        pairs=[("tet.min_ratio", "tet.nobisect")],
    )

    candidates = sweep.expand(experiment, _base())
    marks = {sweep.fingerprint(cfg) for _, cfg in candidates}
    atteso = {
        sweep.fingerprint(
            sweep.with_override(sweep.with_override(_base(), "tet.min_ratio", a), "tet.nobisect", b)
        )
        for a in (1.8, 2.0)
        for b in (False, True)
    }

    # Le quattro combinazioni della coppia esistono tutte fra i candidati. Non
    # si contano le etichette `axes` con due voci: una combinazione della
    # coppia che coincide con la base, o con una voce a un asse solo, viene
    # deduplicata per impronta e sopravvive con l'etichetta piu corta.
    assert atteso <= marks
    assert len(marks) == len(candidates)


def test_uno_sweep_e_completo_senza_il_prior():
    """Il prior (step 12) non e' un requisito di completezza per uno sweep:
    nessun asse della griglia lo tocca (BLOCCHI_FUORI_IMPRONTA), e un
    candidato e' completo quando ha il proprio deck, non quando ha il prior.
    Le undici chiavi fino a 11_export bastano, "12_wall" assente compreso."""
    senza_prior = {chiave: {} for chiave in steps.STEP_KEYS if chiave != "12_wall"}
    assert "12_wall" not in senza_prior
    assert sweep.is_complete(senza_prior) is True


def test_uno_sweep_senza_un_vero_step_di_elaborazione_resta_incompleto():
    """Il controllo che smentisce: senza di esso un REQUIRED_STEPS svuotato
    per errore passerebbe il test sopra a vuoto. Qui manca 09_tetrahedralize,
    uno step di elaborazione vero, e il candidato deve restare incompleto."""
    senza_tet = {
        chiave: {} for chiave in steps.STEP_KEYS if chiave not in ("12_wall", "09_tetrahedralize")
    }
    assert sweep.is_complete(senza_tet) is False


def test_a_partial_metrics_file_is_not_complete():
    """Il blocco finally di pipeline.run scrive un dizionario parziale quando una corsa muore.

    Quel file e' oggi indistinguibile da uno completo, ed e' il motivo per cui
    un candidato entra nel fronte solo se porta tutte le chiavi di step.
    """
    completo = {name: {} for name in sweep.REQUIRED_STEPS}

    assert sweep.is_complete(completo) is True
    assert sweep.is_complete({"01_load": {}, "08_simplify": {}}) is False
    assert sweep.is_complete({}) is False
    # metrics.json puo' essere uno scalare JSON valido (un intero) se il file
    # e' stato troncato o scritto a meta': "step in metrics" solleverebbe
    # TypeError su un intero senza il controllo di tipo.
    assert sweep.is_complete(5) is False


def test_the_registry_is_append_only_and_reads_back(tmp_path):
    path = tmp_path / "registro.jsonl"

    sweep.append_row(path, {"fingerprint": "aaa", "outcome": "riuscito"})
    sweep.append_row(path, {"fingerprint": "bbb", "outcome": "fallito"})

    rows = sweep.load_registry(path)
    assert [row["fingerprint"] for row in rows] == ["aaa", "bbb"]
    assert path.read_text(encoding="utf-8").count("\n") == 2


def test_the_digest_of_a_file_changes_with_its_content(tmp_path):
    path = tmp_path / "artefatto.ply"
    path.write_bytes(b"uno")
    prima = sweep.file_digest(path)
    path.write_bytes(b"due")

    assert sweep.file_digest(path) != prima
    assert len(prima) == 64


def test_provenance_records_the_code_that_produced_the_row():
    """Il commit e' leggibile, o dirty e' sconosciuto: mai un dirty fabbricato accanto a un commit assente.

    Su una macchina dove git non riesce a partire (sandbox che nega l'avvio del
    processo) commit vale "sconosciuto" e dirty deve restare None, non un bool
    inventato. Dove git parte, valgono le garanzie piene.
    """
    provenance = sweep.provenance()

    if provenance["commit"] == "sconosciuto":
        assert provenance["dirty"] is None
    else:
        assert len(provenance["commit"]) >= 7
        assert isinstance(provenance["dirty"], bool)
    assert "open3d" in provenance["versions"]
    assert "tetgen" in provenance["versions"]


def test_provenance_when_git_cannot_start_reports_dirty_as_unknown_not_false(monkeypatch):
    """Se git non parte, dirty deve restare sconosciuto, non fabbricato a False.

    bool("") e' False: se il fallimento venisse letto come uno stdout vuoto,
    un albero sporco si scriverebbe pulito con apparente certezza. E' precisamente
    il difetto che questo registro esiste per impedire, riprodotto dentro la riga.
    """
    def _raise(*args, **kwargs):
        raise OSError("git non trovato")

    monkeypatch.setattr(sweep.subprocess, "run", _raise)

    with pytest.warns(sweep.GitUnavailableWarning):
        provenance = sweep.provenance()

    assert provenance["dirty"] is None
    assert provenance["commit"] == "sconosciuto"


def test_provenance_outside_a_repository_reports_dirty_as_unknown_not_clean(tmp_path, monkeypatch):
    """git parte, esce con codice != 0 e non scrive nulla su stdout.

    Uno stdout vuoto per fallimento non e' un albero pulito: senza distinguere
    il codice d'uscita, `dirty` diventerebbe bool("") = False e ogni riga scritta
    fuori dal repository dichiarerebbe pulito un albero di cui non si sa nulla.
    """
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("GIT_CEILING_DIRECTORIES", str(tmp_path))

    with pytest.warns(sweep.GitUnavailableWarning):
        provenance = sweep.provenance()

    assert provenance["commit"] == "sconosciuto"
    assert provenance["dirty"] is None


def test_provenance_in_a_clean_repository_reports_dirty_false_not_unknown(tmp_path, monkeypatch):
    """git riesce su un albero pulito: stdout vuoto con codice 0 vale False, non None.

    E' la distinzione che la guardia sul codice d'uscita non deve schiacciare.
    """
    git = ["git", "-c", "user.email=t@t", "-c", "user.name=t"]
    sweep.subprocess.run([*git, "init", "-q", str(tmp_path)], check=True)
    sweep.subprocess.run([*git, "commit", "-q", "--allow-empty", "-m", "vuoto"], cwd=tmp_path, check=True)
    monkeypatch.chdir(tmp_path)

    provenance = sweep.provenance()

    assert provenance["dirty"] is False
    assert provenance["commit"] != "sconosciuto"


def test_provenance_reads_a_whitespace_only_git_output_as_a_clean_tree(monkeypatch):
    """Solo spazi bianchi da git: dopo strip e' vuoto, quindi albero pulito."""
    def _blank(*args, **kwargs):
        return sweep.subprocess.CompletedProcess(args, 0, stdout="  \n", stderr="")

    monkeypatch.setattr(sweep.subprocess, "run", _blank)

    assert sweep.provenance()["dirty"] is False


def test_a_candidate_that_fails_becomes_a_row_and_not_an_exception(tmp_path):
    """Un buco nel registro sarebbe indistinguibile da un candidato mai provato.

    Qui il fallimento e' provocato con una nuvola inesistente, che e' il modo
    piu rapido di far uscire `meshrec run` con codice diverso da zero.
    """
    cfg = config.PipelineConfig(input=config.InputConfig(path=str(tmp_path / "assente.ply")))

    row = sweep.run_candidate({}, cfg, tmp_path / "candidato", timeout_s=120.0)

    assert row["outcome"] == "fallito"
    assert row["exit_code"] != 0
    assert row["stderr"]
    assert row["complete"] is False
    assert row["fingerprint"] == sweep.fingerprint(cfg)


def test_a_candidate_that_succeeds_records_its_artifacts(tmp_path):
    """Sul cubo sintetico la catena intera gira in pochi secondi ed e' l'unico
    caso in cui il motore puo' essere provato end-to-end dentro la suite."""
    from meshrec.core import io, synth

    cloud = tmp_path / "cubo.ply"
    io.write_cloud(cloud, synth.sample_box_surface(size=(100.0, 40.0, 200.0), spacing=4.0))
    cfg = config.PipelineConfig(
        input=config.InputConfig(path=str(cloud)),
        surface=config.SurfaceConfig(poisson_depth=6),
    )

    row = sweep.run_candidate({"tet.min_ratio": 1.8}, cfg, tmp_path / "candidato", timeout_s=600.0)

    assert row["outcome"] == "riuscito"
    assert row["complete"] is True
    assert row["axes"] == {"tet.min_ratio": 1.8}
    assert row["input_digest"] == sweep.file_digest(cloud)
    assert "09_volume.vtu" in row["artifacts"]
    assert row["duration_s"] > 0.0
    # run_candidate chiede --to-step 11 esplicito al sottoprocesso e non lo
    # eredita. La richiesta esplicita e' esattamente cio' che rende lo sweep
    # indifferente a come il predefinito cambia, e il predefinito e' cambiato
    # due volte: 13 fino alla Fase 7, 12 dalla Fase 8 (#140), 11 dal perimetro
    # del prodotto. Senza quella richiesta, alla Fase 7 questo candidato
    # risolveva davvero (ccx e' spesso installato dove gira lo sweep), pagando
    # un processo esterno e i suoi artefatti (.frd/.vtu) senza che la selezione
    # di Pareto li legga mai. La decisione e' del chiamante, non del
    # predefinito -- vedi il commento su REQUIRED_STEPS in sweep.py.
    assert "13_solve" not in row["metrics"]


def test_a_truncated_metrics_file_does_not_raise_and_becomes_incomplete(tmp_path, monkeypatch):
    """pipeline.run scrive metrics.json in un blocco finally: un processo ucciso
    a meta' (timeout, memoria esaurita) lo lascia troncato. json.JSONDecodeError
    non deve salire qui: e' esattamente il caso che questa funzione esiste per
    assorbire.

    Il sottoprocesso reale e' sostituito con uno finto, cosi' il file troncato
    scritto a mano sopravvive fino alla lettura che questo test verifica.
    """
    out_dir = tmp_path / "candidato"
    out_dir.mkdir()
    (out_dir / "metrics.json").write_text('{"01_load": {"n":', encoding="utf-8")

    def _fake_run(cmd, **kwargs):
        return sweep.subprocess.CompletedProcess(cmd, returncode=1, stdout="", stderr="ucciso")

    monkeypatch.setattr(sweep.subprocess, "run", _fake_run)

    row = sweep.run_candidate({}, _base(), out_dir, timeout_s=120.0)

    assert row["metrics"] == {}
    assert row["complete"] is False
    assert row["fingerprint"] == sweep.fingerprint(_base())


def test_a_candidate_whose_folder_cannot_be_created_becomes_a_row_and_not_an_exception(tmp_path):
    """Permessi negati o collisione con un file omonimo non devono far salire
    OSError: il candidato diventa comunque una riga, con esito 'errore'.

    Qui la collisione e' un file normale creato al percorso dove out_dir
    dovrebbe nascere: mkdir(exist_ok=True) solleva se il percorso esiste ma
    non e' una cartella.
    """
    blocked = tmp_path / "candidato"
    blocked.write_text("non e' una cartella", encoding="utf-8")

    cfg = _base()
    row = sweep.run_candidate({}, cfg, blocked, timeout_s=120.0)

    assert row["outcome"] == "errore"
    assert row["stderr"]
    assert row["fingerprint"] == sweep.fingerprint(cfg)
    # Il registro viaggia fra Windows e macOS: nessun separatore di Windows.
    assert "\\" not in row["out_dir"]


def _row(fingerprint_: str, thickness_error: float, tets: int, over: float, **extra):
    row = {
        "fingerprint": fingerprint_,
        "outcome": "riuscito",
        "complete": True,
        "thickness_error": thickness_error,
        "metrics": {
            "10_volume_quality": {"tets": tets, "radius_edge_over_reference": over},
        },
        "artifacts_kept": True,
    }
    row.update(extra)
    return row


def test_a_dominated_candidate_leaves_the_front():
    peggiore = _row("a", thickness_error=20.0, tets=2_000_000, over=0.20)
    migliore = _row("b", thickness_error=5.0, tets=1_000_000, over=0.08)

    front = sweep.pareto_front([peggiore, migliore])

    assert [row["fingerprint"] for row in front] == ["b"]


def test_a_candidate_better_on_one_axis_survives():
    """Il fronte non sceglie: scarta solo chi e' battuto su tutto."""
    leggero = _row("a", thickness_error=20.0, tets=500_000, over=0.20)
    fedele = _row("b", thickness_error=2.0, tets=2_000_000, over=0.09)

    front = sweep.pareto_front([leggero, fedele])

    assert {row["fingerprint"] for row in front} == {"a", "b"}


def test_an_incomplete_candidate_never_enters_the_front():
    parziale = _row("a", thickness_error=1.0, tets=1, over=0.0)
    parziale["complete"] = False
    normale = _row("b", thickness_error=9.0, tets=900_000, over=0.10)

    assert [row["fingerprint"] for row in sweep.pareto_front([parziale, normale])] == ["b"]


def test_objectives_returns_none_without_raising_when_a_volume_subkey_is_missing():
    """is_complete controlla solo la chiave di step "10_volume_quality", non le
    sue sottochiavi: un candidato ucciso a meta' scrittura puo' completare
    tutti gli step ma lasciare il dizionario dello step senza
    radius_edge_over_reference o tets. Prima della correzione objectives()
    sollevava KeyError qui, prima ancora che il registro venisse scritto."""
    riga = {
        "outcome": "riuscito",
        "complete": True,
        "thickness_error": 5.0,
        "metrics": {"10_volume_quality": {"tets": 1000}},
    }

    assert sweep.objectives(riga) is None


def test_a_front_as_large_as_the_grid_is_reported():
    """Se nessun candidato e' dominato gli assi non discriminano, e senza
    questa sorveglianza il caso si presenterebbe come un fronte ricco."""
    rows = [
        _row("a", thickness_error=1.0, tets=3, over=0.3),
        _row("b", thickness_error=2.0, tets=2, over=0.2),
        _row("c", thickness_error=3.0, tets=1, over=0.1),
    ]

    with pytest.warns(sweep.SweepDiagnosticWarning, match="non discrimina"):
        report = sweep.check_sweep(rows, sweep.pareto_front(rows))

    assert report["front_is_whole_grid"] is True


def test_zero_comparable_candidates_is_reported():
    """I1: front_is_whole_grid protegge dal falso allarme sul fronte vuoto
    quando comparable e' vuoto (bool(comparable) lo esclude apposta), ma il
    caso vuoto reale restava scoperto: se nessuna riga ha un errore di
    spessore misurabile lo sweep finisce con fronte vuoto, uscita zero, e
    prima di questa correzione nessun avviso."""
    rows = [
        _row("a", thickness_error=None, tets=1, over=0.1),
        _row("b", thickness_error=None, tets=2, over=0.2),
    ]

    with pytest.warns(sweep.SweepDiagnosticWarning, match="nessuno dei 2 candidati"):
        report = sweep.check_sweep(rows, sweep.pareto_front(rows))

    assert report["comparable"] == 0
    assert report["front"] == 0
    assert report["front_is_whole_grid"] is False


def test_more_than_half_failing_is_reported():
    """Con un solo candidato confrontabile il fronte e' anche largo quanto
    la griglia comparabile: scattano entrambi gli avvisi, e vanno asseriti
    entrambi, altrimenti quello che sfugge non conta piu' nella suite."""
    rows = [
        _row("a", thickness_error=1.0, tets=1, over=0.1),
        {"fingerprint": "b", "outcome": "fallito", "complete": False},
        {"fingerprint": "c", "outcome": "timeout", "complete": False},
    ]

    with pytest.warns(sweep.SweepDiagnosticWarning) as record:
        report = sweep.check_sweep(rows, sweep.pareto_front(rows))

    messages = [str(warning.message) for warning in record]
    assert any("griglia" in message for message in messages)
    assert any("non discrimina" in message for message in messages)
    assert report["failed_fraction"] == pytest.approx(2 / 3)


def test_candidates_tied_on_every_axis_all_survive():
    """Due tuple uguali non si dominano a vicenda: ne' _dominates ne'
    other != score le fa cadere, in nessuna delle due direzioni."""
    prima = _row("a", thickness_error=5.0, tets=1_000_000, over=0.10)
    seconda = _row("b", thickness_error=5.0, tets=1_000_000, over=0.10)

    front = sweep.pareto_front([prima, seconda])

    assert {row["fingerprint"] for row in front} == {"a", "b"}


def test_pruning_keeps_config_and_metrics_and_marks_the_row(tmp_path):
    """Una corsa completa pesa circa 300 MB: i dominati conservano la riga, non i file."""
    dominato = tmp_path / "dominato"
    dominato.mkdir()
    for name in ("config.yaml", "metrics.json", "09_volume.vtu", "wall_model.inp"):
        (dominato / name).write_text("x", encoding="utf-8")
    sopravvive = tmp_path / "fronte"
    sopravvive.mkdir()
    (sopravvive / "09_volume.vtu").write_text("x", encoding="utf-8")

    scartato = _row("a", thickness_error=20.0, tets=2, over=0.5, out_dir=str(dominato))
    tenuto = _row("b", thickness_error=1.0, tets=1, over=0.1, out_dir=str(sopravvive))

    removed = sweep.prune([scartato, tenuto], [tenuto])

    assert removed == 2
    assert (dominato / "config.yaml").exists()
    assert (dominato / "metrics.json").exists()
    assert not (dominato / "09_volume.vtu").exists()
    assert (sopravvive / "09_volume.vtu").exists()
    assert scartato["artifacts_kept"] is False
    assert tenuto["artifacts_kept"] is True


def _experiment(tmp_path, known_thickness):
    return config.ExperimentConfig(
        name="prova",
        base=Path("muro.yaml"),
        axes=[config.AxisSpec(path="tet.min_ratio", values=[1.8, 2.0])],
        known_thickness=known_thickness,
        sweep=config.SweepConfig(
            runs_root=tmp_path / "runs", registry_root=tmp_path / "experiments"
        ),
    )


def test_run_experiment_refuses_to_write_inside_an_existing_run(tmp_path):
    """root/metrics.json esiste gia': e' una corsa della pipeline, non una cartella d'esperimento.

    Il cancello scatta prima di expand() e prima della misura di spessore:
    nessuna delle due chiama run_candidate, quindi il messaggio deve arrivare
    senza toccare io.load_cloud o alcun sottoprocesso.
    """
    experiment = _experiment(tmp_path, known_thickness=100.0)
    run_dir = Path(experiment.sweep.runs_root) / experiment.name
    run_dir.mkdir(parents=True)
    (run_dir / "metrics.json").write_text("{}", encoding="utf-8")

    with pytest.raises(ValueError, match="corsa della pipeline"):
        sweep.run_experiment(experiment, _base())


def test_run_experiment_refuses_a_second_sweep_over_an_existing_registry(tmp_path):
    """I3: la radice di un esperimento non ha metrics.json, i candidati sono
    sottocartelle, quindi la guardia sopra non basta a fermare un secondo
    sweep. Senza questa seconda guardia un secondo `meshrec sweep` sullo
    stesso esperimento rigirerebbe tutto e appenderebbe altre righe in coda
    allo stesso registro in sola aggiunta, raddoppiando il report in
    silenzio. Il cancello deve scattare prima di expand(), senza toccare
    io.load_cloud o alcun sottoprocesso.
    """
    experiment = _experiment(tmp_path, known_thickness=100.0)
    registry = Path(experiment.sweep.registry_root) / experiment.name / "registro.jsonl"
    sweep.append_row(registry, {"fingerprint": "aaa", "outcome": "riuscito"})

    with pytest.raises(ValueError, match="registro"):
        sweep.run_experiment(experiment, _base())


def test_the_gate_raises_when_the_thickness_error_exceeds_five_percent(tmp_path, monkeypatch):
    """Il cancello ferma lo sweep prima di eseguire candidati, coi numeri nel messaggio.

    run_candidate e' sostituito con uno che solleva se chiamato: se il cancello
    non fermasse lo sweep prima di expand(), pytest.raises vedrebbe
    AssertionError al posto di ValueError e il test fallirebbe da solo, senza
    bisogno di una quarta asserzione o di un contatore di chiamate.
    """
    import numpy as np

    monkeypatch.setattr("meshrec.core.io.load_cloud", lambda cfg: (np.zeros((4, 3)), {"spacing": 1.0}))
    monkeypatch.setattr("meshrec.core.segment.segment_cloud", lambda points, cfg, spacing: (points, {}))
    monkeypatch.setattr(
        "meshrec.core.quality.thickness",
        lambda points, bin_width: {"thickness": 120.0, "axis": 0, "extent": 10.0, "bimodal": True},
    )

    def _boom(*args, **kwargs):
        raise AssertionError("run_candidate chiamato: il cancello non ha fermato lo sweep")

    monkeypatch.setattr(sweep, "run_candidate", _boom)

    with pytest.raises(ValueError, match="120.0 mm contro 100.0 mm"):
        sweep.run_experiment(_experiment(tmp_path, known_thickness=100.0), _base())


def test_the_gate_raises_when_the_source_distribution_is_not_bimodal(tmp_path, monkeypatch):
    """Anche a scarto piccolo, senza due modi la misura non e' utilizzabile: il cancello scatta lo stesso."""
    import numpy as np

    monkeypatch.setattr("meshrec.core.io.load_cloud", lambda cfg: (np.zeros((4, 3)), {"spacing": 1.0}))
    monkeypatch.setattr("meshrec.core.segment.segment_cloud", lambda points, cfg, spacing: (points, {}))
    monkeypatch.setattr(
        "meshrec.core.quality.thickness",
        lambda points, bin_width: {"thickness": 100.5, "axis": 0, "extent": 10.0, "bimodal": False},
    )

    with pytest.raises(ValueError, match="bimodale=False"):
        sweep.run_experiment(_experiment(tmp_path, known_thickness=100.0), _base())


def test_the_gate_reports_a_readable_message_when_the_source_thickness_is_not_measurable(
    tmp_path, monkeypatch
):
    """quality.thickness su una nuvola sorgente degenere restituisce thickness None.

    abs(None - known_thickness) romperebbe il cancello con un TypeError
    proprio mentre sta segnalando il problema: qui si verifica che il
    messaggio dichiari esplicitamente la nuvola non misurabile, senza
    stampare un numero fabbricato ne' sollevare l'eccezione sbagliata.
    """
    import numpy as np

    monkeypatch.setattr("meshrec.core.io.load_cloud", lambda cfg: (np.zeros((4, 3)), {"spacing": 1.0}))
    monkeypatch.setattr("meshrec.core.segment.segment_cloud", lambda points, cfg, spacing: (points, {}))
    monkeypatch.setattr(
        "meshrec.core.quality.thickness",
        lambda points, bin_width: {"thickness": None, "axis": 0, "extent": 10.0, "bimodal": False},
    )

    with pytest.raises(ValueError, match="non misurabile"):
        sweep.run_experiment(_experiment(tmp_path, known_thickness=100.0), _base())


def test_measure_thickness_error_returns_none_without_raising_when_metrics_is_empty(tmp_path):
    """06_repaired.ply esiste ma metrics.json non e' mai stato scritto: il candidato
    ucciso dopo la riparazione e prima del blocco finally che lo scrive. La riga
    resta comparabile a False, ma la funzione non deve sollevare KeyError."""
    import numpy as np
    import open3d as o3d

    out_dir = tmp_path / "candidato"
    out_dir.mkdir()
    mesh = o3d.geometry.TriangleMesh()
    mesh.vertices = o3d.utility.Vector3dVector(
        np.array([[0.0, 0.0, 0.0], [1.0, 0.0, 0.0], [0.0, 1.0, 0.0]])
    )
    mesh.triangles = o3d.utility.Vector3iVector(np.array([[0, 1, 2]]))
    o3d.io.write_triangle_mesh(str(out_dir / "06_repaired.ply"), mesh)

    row = {"out_dir": str(out_dir), "metrics": {}}

    assert sweep.measure_thickness_error(row, source_thickness=100.0) is None


def test_measure_thickness_error_returns_none_without_raising_on_a_degenerate_mesh(tmp_path):
    """06_repaired.ply esiste, metrics.json e' completo, ma la mesh riparata e'
    piatta: quality.thickness dichiara bimodal False (radice corretta in
    quality.py), non ValueError su np.argmax di una fetta vuota."""
    import numpy as np
    import open3d as o3d

    out_dir = tmp_path / "candidato"
    out_dir.mkdir()
    mesh = o3d.geometry.TriangleMesh()
    mesh.vertices = o3d.utility.Vector3dVector(
        np.array([[0.0, 0.0, 0.0], [1.0, 0.0, 0.0], [0.0, 1.0, 0.0]])
    )
    mesh.triangles = o3d.utility.Vector3iVector(np.array([[0, 1, 2]]))
    o3d.io.write_triangle_mesh(str(out_dir / "06_repaired.ply"), mesh)

    row = {"out_dir": str(out_dir), "metrics": {"01_load": {"spacing": 1.0}}}

    assert sweep.measure_thickness_error(row, source_thickness=100.0) is None


def test_measure_thickness_error_returns_none_without_raising_on_a_nan_vertex(tmp_path):
    """Prova end-to-end: un vertice NaN nella mesh riparata non deve fermare
    run_experiment dopo che tutti i candidati sono gia' stati eseguiti e
    prima di ogni append_row. Coordinate non finite possono uscire da una
    ricostruzione di Poisson andata male, da una chiusura dei fori o da una
    stima delle normali degenere: non e' un caso teorico."""
    import numpy as np
    import open3d as o3d

    out_dir = tmp_path / "candidato"
    out_dir.mkdir()
    mesh = o3d.geometry.TriangleMesh()
    mesh.vertices = o3d.utility.Vector3dVector(
        np.array([[np.nan, 0.0, 0.0], [1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]])
    )
    mesh.triangles = o3d.utility.Vector3iVector(np.array([[0, 1, 2], [1, 2, 3]]))
    o3d.io.write_triangle_mesh(str(out_dir / "06_repaired.ply"), mesh)

    row = {"out_dir": str(out_dir), "metrics": {"01_load": {"spacing": 1.0}}}

    assert sweep.measure_thickness_error(row, source_thickness=100.0) is None


def test_measure_thickness_error_returns_none_without_raising_on_a_zero_spacing(tmp_path):
    """Prova end-to-end che conta di piu: uno spacing 0.0 esce davvero da
    io.mean_spacing su punti duplicati esatti, e la cattura (KeyError,
    TypeError) su row["metrics"] non lo intercetta perche' spacing e' un
    float valido. np.arange con passo zero solleva dentro quality.thickness,
    non qui: la mesh su disco e' valida, solo il passo e' corrotto."""
    import numpy as np
    import open3d as o3d

    out_dir = tmp_path / "candidato"
    out_dir.mkdir()
    mesh = o3d.geometry.TriangleMesh()
    mesh.vertices = o3d.utility.Vector3dVector(
        np.array([[0.0, 0.0, 0.0], [1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]])
    )
    mesh.triangles = o3d.utility.Vector3iVector(np.array([[0, 1, 2], [1, 2, 3]]))
    o3d.io.write_triangle_mesh(str(out_dir / "06_repaired.ply"), mesh)

    row = {"out_dir": str(out_dir), "metrics": {"01_load": {"spacing": 0.0}}}

    assert sweep.measure_thickness_error(row, source_thickness=100.0) is None


def test_measure_thickness_error_returns_none_without_raising_on_a_non_numeric_spacing(tmp_path):
    """spacing e' una stringa non numerica ("abc"): float() solleva ValueError,
    non catturato dalla cattura originale (KeyError, TypeError). E' lo stesso
    caso del candidato ucciso a meta', letto da un metrics.json corrotto in
    un altro modo: la riga resta comparabile a False, la funzione non deve
    sollevare."""
    import numpy as np
    import open3d as o3d

    out_dir = tmp_path / "candidato"
    out_dir.mkdir()
    mesh = o3d.geometry.TriangleMesh()
    mesh.vertices = o3d.utility.Vector3dVector(
        np.array([[0.0, 0.0, 0.0], [1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]])
    )
    mesh.triangles = o3d.utility.Vector3iVector(np.array([[0, 1, 2], [1, 2, 3]]))
    o3d.io.write_triangle_mesh(str(out_dir / "06_repaired.ply"), mesh)

    row = {"out_dir": str(out_dir), "metrics": {"01_load": {"spacing": "abc"}}}

    assert sweep.measure_thickness_error(row, source_thickness=100.0) is None


def test_verify_declares_stale_a_row_whose_artifact_changed(tmp_path):
    """La prova a variabile unica: si altera un artefatto e la riga deve cadere.

    E' il caso della Fase 1 in cui un wall_model.inp di una corsa superata e'
    rimasto accanto a un metrics.json fermo a 08_simplify, e niente nei due
    file diceva che non appartenessero alla stessa elaborazione.
    """
    out_dir = tmp_path / "candidato"
    out_dir.mkdir()
    artefatto = out_dir / "wall_model.inp"
    artefatto.write_text("corsa corrente", encoding="utf-8")

    registry = tmp_path / "registro.jsonl"
    sweep.append_row(
        registry,
        {
            "fingerprint": "aaa",
            "out_dir": str(out_dir),
            "artifacts_kept": True,
            "artifacts": {"wall_model.inp": sweep.file_digest(artefatto)},
        },
    )

    assert all(voce["stale"] is False for voce in sweep.verify_registry(registry))

    artefatto.write_text("corsa superata", encoding="utf-8")
    esito = sweep.verify_registry(registry)

    assert esito[0]["stale"] is True
    assert "wall_model.inp" in esito[0]["reason"]


def test_verify_does_not_call_pruned_rows_stale(tmp_path):
    registry = tmp_path / "registro.jsonl"
    sweep.append_row(
        registry,
        {
            "fingerprint": "bbb",
            "out_dir": str(tmp_path / "assente"),
            "artifacts_kept": False,
            "artifacts": {"wall_model.inp": "0" * 64},
        },
    )

    esito = sweep.verify_registry(registry)

    assert esito[0]["stale"] is False
    assert "potati" in esito[0]["reason"]


def test_prune_skips_a_row_whose_out_dir_is_not_a_directory():
    """C2, in isolamento: prune non deve chiamare iterdir() su un file.

    run_candidate produce questa riga quando la cartella del candidato non si
    e' potuta creare (permessi negati, collisione con un file omonimo):
    out_dir e' una stringa non vuota, ma il percorso e' un file. Prima della
    guardia, Path(out_dir).iterdir() sollevava NotADirectoryError qui.
    """
    errore = _row("a", thickness_error=1.0, tets=1, over=0.1, out_dir="C:/non/esiste/come/cartella")
    errore["outcome"] = "errore"
    tenuto = _row("b", thickness_error=9.0, tets=900_000, over=0.10)

    removed = sweep.prune([errore, tenuto], [tenuto])

    assert removed == 0
    assert errore["artifacts_kept"] is True  # non toccata: nessuna cartella da potare


def test_run_experiment_writes_the_registry_even_when_a_candidate_cannot_create_its_folder(
    tmp_path, monkeypatch
):
    """Prova end-to-end per C2: prune() non deve mai impedire la scrittura del registro.

    Un candidato la cui cartella non si e' potuta creare produce una riga con
    outcome 'errore' e un out_dir che non e' una cartella (run_candidate,
    ramo dell'OSError). run_experiment chiama prune() prima del ciclo che
    scrive le righe: senza la guardia in prune(), Path(out_dir).iterdir()
    solleva NotADirectoryError e il registro non viene scritto affatto,
    perdendo con esso ogni candidato riuscito nello stesso sweep.
    """
    import numpy as np

    monkeypatch.setattr("meshrec.core.io.load_cloud", lambda cfg: (np.zeros((4, 3)), {"spacing": 1.0}))
    monkeypatch.setattr("meshrec.core.segment.segment_cloud", lambda points, cfg, spacing: (points, {}))
    monkeypatch.setattr(
        "meshrec.core.quality.thickness",
        lambda points, bin_width: {"thickness": 100.0, "axis": 0, "extent": 10.0, "bimodal": True},
    )

    def _fake_run(cmd, **kwargs):
        return sweep.subprocess.CompletedProcess(cmd, returncode=0, stdout="", stderr="")

    monkeypatch.setattr(sweep.subprocess, "run", _fake_run)

    experiment = _experiment(tmp_path, known_thickness=None)
    base = _base()
    root = Path(experiment.sweep.runs_root) / experiment.name

    # Blocca la cartella del secondo candidato con un file omonimo: stessa
    # collisione di test_a_candidate_whose_folder_cannot_be_created_becomes_a_row_and_not_an_exception,
    # ma qui dentro il flusso reale di run_experiment.
    candidates = sweep.expand(experiment, base)
    assert len(candidates) == 2
    blocked_dir = root / sweep.fingerprint(candidates[-1][1])[:12]
    blocked_dir.parent.mkdir(parents=True, exist_ok=True)
    blocked_dir.write_text("non e' una cartella", encoding="utf-8")

    # Il sottoprocesso e' finto e non scrive mai 06_repaired.ply, quindi
    # nessuna riga ha un errore di spessore misurabile: check_sweep (I1) lo
    # segnala. Atteso qui, non un effetto collaterale da ignorare.
    with pytest.warns(sweep.SweepDiagnosticWarning, match="nessuno dei 2 candidati"):
        result = sweep.run_experiment(experiment, base)

    rows = sweep.load_registry(Path(result["registry"]))
    assert len(rows) == 2
    assert {row["outcome"] for row in rows} == {"riuscito", "errore"}


def test_un_asse_su_un_blocco_fuori_impronta_viene_rifiutato(tmp_path):
    """Due candidati indistinguibili nel registro sarebbero peggio di nessuno
    sweep: l'errore arriva prima di eseguire, non dopo aver scritto le righe."""
    from meshrec.core.config import AxisSpec, ExperimentConfig, InputConfig


    esperimento = ExperimentConfig(
        name="prova",
        base=tmp_path / "base.yaml",
        axes=[AxisSpec(path="wall.min_cells", values=[8, 12])],
    )
    base = config.PipelineConfig(input=InputConfig(path=tmp_path / "n.ply"))
    with pytest.raises(ValueError, match="non entra nell'impronta"):
        sweep.expand(esperimento, base)


def test_le_impronte_dei_registri_non_si_muovono():
    """Le ventidue righe di experiments/ sono la tabella sperimentale della
    tesi: ogni cartella di corsa e' nominata con i primi dodici caratteri
    dell'impronta della propria configurazione, ed e' quell'ancoraggio a
    rendere la tabella risalibile alla corsa che l'ha prodotta.

    E' l'invariante che governa tutta la Fase 8 e va verificata dopo ogni onda,
    non solo dopo quella che tocca la configurazione.

    **Perche' l'ancoraggio e non il ricalcolo.** La verifica piu' forte --
    rileggere `config` dalla riga, ripassarla in `PipelineConfig` e ricalcolare
    `sweep.fingerprint` -- oggi fallisce su tutte e ventidue le righe, e gia'
    su 7be879b, prima della Fase 8. Le righe furono scritte quando
    `PipelineConfig` non aveva ancora i blocchi `model`, `regioni` e `wall`
    ne' `run.to_step`, e aveva invece `simplify.target_faces`,
    `surface.bpa_radius_factors` e `surface.alpha_factor`: la configurazione
    registrata non e' piu' la configurazione di oggi, quindi la sua impronta di
    oggi non e' piu' quella di allora. Ripristinare quel confronto e' lavoro
    dell'onda 0, che possiede la configurazione; qui si verifica cio' che e'
    vero e verificabile, e non si ratifica un'impronta ricalcolata per farla
    tornare.
    """
    registri = sorted(Path("experiments").glob("*/registro.jsonl"))
    if not registri:
        pytest.skip("nessun registro di sweep in questa copia di lavoro")

    righe = 0
    for registro in registri:
        for linea in registro.read_text(encoding="utf-8").splitlines():
            if not linea.strip():
                continue
            record = json.loads(linea)
            cartella = record["out_dir"].replace("\\", "/").rstrip("/").rsplit("/", 1)[-1]
            assert cartella == record["fingerprint"][:12], (
                f"{registro}: la cartella {cartella} non porta piu' l'impronta "
                f"{record['fingerprint'][:12]} della propria riga"
            )
            righe += 1
    assert righe == 22, f"attese 22 righe registrate, trovate {righe}"


def test_la_provenienza_legge_l_uscita_di_git_dichiarando_la_codifica(monkeypatch):
    """`git` su Windows nomina i file nella codepage locale, non in utf-8.

    `subprocess.run(..., text=True)` senza `encoding` decodifica con quella
    preferita dalla macchina. Dentro il sottoprocesso del server quella e'
    utf-8 -- `app/worker.py` gli mette `PYTHONUTF8=1` nell'ambiente -- e il
    byte `0xE0` di «Universita'» non e' una continuazione utf-8 valida: la
    provenienza, che gira a ogni corsa, solleva `UnicodeDecodeError` prima
    ancora che il candidato parta.

    Il banco riproduce `git` VERO su Windows: restituisce i byte cp1252
    decodificati con le chiavi che il codice sotto esame passa davvero. Se non
    ne passa nessuna il finto solleva `KeyError` e il test cade, che e' il modo
    di provare il contratto su una macchina dove la codifica preferita e' gia'
    utf-8 e un test scritto ingenuamente passerebbe anche col codice rotto.

    La riga si scrive comunque, storta se serve: una provenienza illeggibile e'
    una provenienza da leggere con un punto interrogativo dentro, non una corsa
    che non parte.
    """
    sporco = " M nuvole/Università degli Studi di Perugia.pcd\n"

    def git_di_windows(comando, **chiavi):
        grezzo = (sporco if "status" in comando else "abc1234def\n").encode("cp1252")
        return sweep.subprocess.CompletedProcess(
            comando,
            0,
            stdout=grezzo.decode(chiavi["encoding"], errors=chiavi["errors"]),
            stderr="",
        )

    monkeypatch.setattr(sweep.subprocess, "run", git_di_windows)

    provenienza = sweep.provenance()

    assert provenienza["dirty"] is True
    assert provenienza["commit"] == "abc1234def"


def test_il_candidato_legge_l_uscita_del_sottoprocesso_dichiarando_la_codifica(
    tmp_path, monkeypatch
):
    """Lo stderr del candidato entra nella riga del registro: va letto dichiarando come.

    Il candidato e' un `meshrec run` in un processo separato, e il suo stderr
    e' dove finiscono gli avvisi che la riga registra. Con `text=True` e nessuna
    codifica i due capi del tubo scelgono ciascuno la propria: su Windows il
    figlio scrive nella codepage e il padre legge utf-8, e un solo nome di file
    accentato -- o una riga di `ccx`, che scrive sul descrittore saltando
    `sys.stdout` -- fa saltare l'intero candidato con `UnicodeDecodeError`.

    Stesso banco della provenienza: il finto decodifica con le chiavi che il
    codice passa davvero, e senza chiavi solleva `KeyError`.
    """
    out_dir = tmp_path / "candidato"
    out_dir.mkdir()

    def figlio_di_windows(comando, **chiavi):
        if comando[0] == "git":
            # Riuscito e muto: la provenienza non e' l'oggetto di questo test e
            # un suo avviso maschererebbe il KeyError del contratto.
            return sweep.subprocess.CompletedProcess(comando, 0, stdout="", stderr="")
        grezzo = "*WARNING: nodo isolato in città.ply\n".encode("cp1252")
        return sweep.subprocess.CompletedProcess(
            comando,
            1,
            stdout="",
            stderr=grezzo.decode(chiavi["encoding"], errors=chiavi["errors"]),
        )

    monkeypatch.setattr(sweep.subprocess, "run", figlio_di_windows)

    row = sweep.run_candidate({}, _base(), out_dir, timeout_s=120.0)

    assert row["outcome"] == "fallito"
    assert "*WARNING: nodo isolato" in row["stderr"]


def test_l_uscita_del_candidato_ucciso_entra_nella_riga_come_testo_non_come_repr(
    tmp_path, monkeypatch
):
    """Un candidato ucciso per timeout lascia un'uscita troncata, e in byte.

    Misurato su questa macchina (CPython 3.12.14, POSIX): con `text=True`,
    `TimeoutExpired.stderr` NON e' decodificata -- `_check_timeout` costruisce
    l'eccezione unendo i pezzi grezzi, e la traduzione di riga avviene solo
    sulla via normale. Su Windows invece `subprocess.run` richiama
    `communicate()` dopo il `kill()` e la stessa attributo e' `str`.

    Quindi la riga del registro scriveva `b'*WARNING...\\n'` su Linux e
    `*WARNING...` su Windows: la stessa corsa uccisa allo stesso modo lascia
    due tracce diverse, e su Linux quella che c'e' non e' l'uscita ma la sua
    rappresentazione. Il candidato resta incompleto in tutti e due i casi --
    questo il codice lo dichiara gia' -- ma l'uscita va letta, non stampata
    come oggetto.
    """
    out_dir = tmp_path / "candidato"
    out_dir.mkdir()

    def ucciso(comando, **_chiavi):
        if comando[0] == "git":
            return sweep.subprocess.CompletedProcess(comando, 0, stdout="", stderr="")
        raise sweep.subprocess.TimeoutExpired(
            comando,
            120.0,
            output=None,
            # Come le costruisce CPython su POSIX: byte, anche con `text=True`.
            stderr="*WARNING: nodo isolato in città.ply\n".encode("utf-8"),
        )

    monkeypatch.setattr(sweep.subprocess, "run", ucciso)

    row = sweep.run_candidate({}, _base(), out_dir, timeout_s=120.0)

    assert row["outcome"] == "timeout"
    assert row["complete"] is False
    assert "*WARNING: nodo isolato in città.ply" in row["stderr"]
    assert "\\x" not in row["stderr"] and not row["stderr"].endswith("'")


@pytest.mark.parametrize("asse", ["analysis.material.young", "carichi.spinta.coefficiente"])
def test_un_asse_dentro_un_blocco_che_non_esiste_dice_quale_asse_e_quale_blocco(asse):
    """Un asse scritto su un blocco tolto non e' un `KeyError` nudo.

    Gli `esperimento.yaml` gia' scritti portano assi dentro `analysis` e
    `carichi`, che il deck nudo ha tolto. `with_override` cammina il dump, e
    la guardia che c'era copriva il solo blocco presente-ma-nullo: sul blocco
    assente per intero l'indicizzazione sollevava `KeyError('analysis')`, che
    non dice ne' quale asse dell'esperimento l'ha chiesto ne' che il blocco
    non esiste piu'.

    Il ramo `analysis.material.young` dice anche che il blocco non esiste
    piu', con la data: chi obbedisce al messaggio di oggi ("compila
    'analysis'") e chi rifiuta i blocchi tolti (`config.BLOCCHI_RIMOSSI`)
    non devono contraddirsi.

    Mutazione che lo uccide: togliere la guardia sulla chiave assente. Torna
    un `KeyError` col solo nome del blocco.
    """
    with pytest.raises(ValueError) as rifiuto:
        sweep.with_override(_base(), asse, 1.0)

    messaggio = str(rifiuto.value)
    assert asse in messaggio
    assert asse.split(".")[0] in messaggio
    if asse == "analysis.material.young":
        assert "non esiste più" in messaggio
        assert "08/09/2026" in messaggio
        assert "compila" not in messaggio


def test_un_asse_su_un_passo_assente_di_un_blocco_vivo_dice_ancora_di_compilarlo():
    """Un blocco vivo (`tet` non e' mai stato tolto) con un passo che non c'e'
    nel suo dump non e' lo stesso caso del blocco tolto: resta il messaggio di
    oggi, "compila", non "non esiste piu'".

    Mutazione che lo uccide: estendere ai blocchi vivi il messaggio nuovo
    pensato per `config.BLOCCHI_RIMOSSI`.
    """
    with pytest.raises(ValueError) as rifiuto:
        sweep.with_override(_base(), "tet.non_esiste.qualcosa", 1.0)

    messaggio = str(rifiuto.value)
    assert "tet.non_esiste" in messaggio
    assert "compila" in messaggio
    assert "non esiste più" not in messaggio
