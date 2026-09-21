"""Verifica di Fase 1: il parallelepipedo a soluzione nota attraversa tutta la catena."""

import json
import shutil
from pathlib import Path

import numpy as np
import pytest
from pydantic import ValidationError

from meshrec.core import autointersezioni, config, io, pipeline, quality, steps, synth


SIZE = (120.0, 60.0, 240.0)
SPACING = 4.0
EXACT_VOLUME = 120.0 * 60.0 * 240.0


def _config_cubo(tmp_path):
    """Configurazione del cubo di prova, la stessa della fixture run_dir.

    `to_step=12` esplicito e non ereditato: non coincide col predefinito di
    RunConfig, che dal perimetro del prodotto vale 11, ma questo banco serve gran parte della suite per
    esercitare l'elaborazione geometrica (1-12), non il solutore -- e su una
    macchina con `ccx` installato ereditare un predefinito che un giorno
    tornasse 13 farebbe girare un processo esterno vero a ogni singola
    chiamata. Stessa ragione, stesso numero, di `sweep.run_candidate`."""
    pytest.importorskip("pymeshfix")
    cloud_path = tmp_path / "box.ply"
    io.write_cloud(cloud_path, synth.sample_box_surface(SIZE, SPACING))
    return config.PipelineConfig(
        input=config.InputConfig(path=cloud_path, spacing_sample=5000),
        downsample=config.DownsampleConfig(voxel_size=SPACING),
        surface=config.SurfaceConfig(poisson_depth=8, density_quantile=0.02),
        tet=config.TetConfig(min_ratio=1.2),
        # Il predefinito 6.0 e' tarato su un muro vero (1,8 m di altezza,
        # spaziatura 22 mm): qui il pezzo e' alto 240 mm e il maglio esaedrico
        # della corsa figlia ha spaziatura 25, quindi la banda a 6.0 vale 150 mm
        # e `BASE` e `TOP` si toccano. E' il banco a essere piccolo, non la
        # tolleranza a essere sbagliata: qui vale 50 mm, cioe' un quinto
        # dell'altezza, che e' l'ordine di grandezza del caso vero.
        export=config.ExportConfig(set_tolerance_factor=2.0),
        run=config.RunConfig(out_dir=tmp_path / "out", to_step=12),
    )


def test_una_corsa_interrotta_non_sostituisce_le_metriche_complete(tmp_path, monkeypatch):
    """Il difetto storico: il finally scriveva metrics.json col dizionario com'era,
    e una corsa morta a meta' cancellava quella completa di prima.
    """
    from meshrec.core import pipeline, surface

    corsa = tmp_path / "corsa"
    corsa.mkdir()
    complete = {chiave: {"ok": True} for chiave in ("01_load", "11_export")}
    (corsa / pipeline.METRICS_FILENAME).write_text(json.dumps(complete), encoding="utf-8")

    cfg = _config_cubo(tmp_path)
    cfg.run.out_dir = corsa

    def esplode(*_argomenti, **_chiavi):
        raise RuntimeError("interruzione simulata dello step 3")

    monkeypatch.setattr(surface, "downsample", esplode)
    with pytest.raises(RuntimeError):
        pipeline.run(cfg)

    rilette = json.loads((corsa / pipeline.METRICS_FILENAME).read_text(encoding="utf-8"))
    assert rilette == complete, "metrics.json completo sostituito da uno parziale"
    assert (corsa / pipeline.METRICS_PARTIAL).exists(), "il parziale deve restare, per diagnosi"


def test_una_corsa_piena_sostituisce_una_chiave_estranea_gia_sul_disco(tmp_path):
    """completa non puo' restare legata a stop == 11 scritto a mano: con
    RunConfig.to_step ora a 12 di default (Fase 4), una corsa piena dalla
    configurazione predefinita deve continuare a sostituire, non fondere,
    anche quando metrics.json porta gia' una chiave che questa corsa non
    riscrive. Con la condizione vecchia stop vale 12, completa risulta
    falso, e la chiave estranea sopravvive al posto di sparire.
    """
    from meshrec.core import pipeline

    cfg = _config_cubo(tmp_path)
    out = cfg.run.out_dir
    out.mkdir(parents=True, exist_ok=True)
    (out / pipeline.METRICS_FILENAME).write_text(
        json.dumps({"99_estranea": {"ok": True}}), encoding="utf-8"
    )

    pipeline.run(cfg)

    metriche = json.loads((out / pipeline.METRICS_FILENAME).read_text(encoding="utf-8"))
    assert "99_estranea" not in metriche


@pytest.fixture(scope="module")
def run_dir(tmp_path_factory):
    """Esegue la pipeline una volta sola: e' il test piu lento della suite.

    `to_step=12`: questa fixture serve i test sui passi 1-11 (superficie,
    volume, deck), non il solutore -- stessa ragione di `_config_cubo`."""
    pytest.importorskip("pymeshfix")
    base = tmp_path_factory.mktemp("run")
    cloud_path = base / "box.ply"
    io.write_cloud(cloud_path, synth.sample_box_surface(SIZE, SPACING))

    cfg = config.PipelineConfig(
        input=config.InputConfig(path=cloud_path, spacing_sample=5000),
        downsample=config.DownsampleConfig(voxel_size=SPACING),
        surface=config.SurfaceConfig(poisson_depth=8, density_quantile=0.02),
        tet=config.TetConfig(min_ratio=1.2),
        run=config.RunConfig(out_dir=base / "out", to_step=12),
    )
    metrics = pipeline.run(cfg)
    return base / "out", metrics


def test_the_run_directory_holds_config_metrics_and_the_deck(run_dir):
    out, _ = run_dir
    assert (out / "config.yaml").exists()
    assert (out / "metrics.json").exists()
    assert (out / "wall_model.inp").exists()
    assert (out / "wall_model.vtu").exists()
    assert config.load_config(out / "config.yaml").tet.min_ratio == pytest.approx(1.2)


def test_ogni_step_che_scrive_una_superficie_dice_se_e_chiusa(run_dir):
    """Il pannello del modello descrive il fronte, e il fronte puo' fermarsi al
    5: senza queste chiavi un fronte al 5 non saprebbe dire «aperta». Le chiavi
    proprie dello step non si toccano: `watertight_after` del 6 resta."""
    _out, metrics = run_dir
    for chiave in ("05_reconstruct", "06_repair", "08_simplify"):
        for misura in (
            "vertices",
            "triangles",
            "watertight",
            "boundary_edges",
            "area",
            "volume",
            "aspect_ratio",
        ):
            assert misura in metrics[chiave], f"{chiave} non porta {misura}"
    assert metrics["06_repair"]["watertight_after"] == metrics["06_repair"]["watertight"]


def test_le_misure_della_superficie_rispettano_lo_step_e_le_facce_vuote():
    """Lo step vince sulle misure aggiunte, e zero facce non si misurano:
    `surface_metrics` su zero facce non solleva, produce misure prive di
    senso (area 0, «chiusa» vera per assenza di spigoli) che finirebbero in
    `metrics.json` come fatti. La guardia lascia le metriche dello step
    com'erano."""
    vertici = np.array([[0.0, 0.0, 0.0], [1.0, 0.0, 0.0], [0.0, 1.0, 0.0]])
    facce = np.array([[0, 1, 2]])
    unite = pipeline._con_le_misure_della_superficie({"vertices": 99, "watertight_after": True}, vertici, facce)
    assert unite["vertices"] == 99, "la chiave dello step deve vincere"
    assert unite["watertight"] is False and unite["boundary_edges"] == 3
    assert unite["watertight_after"] is True
    vuote = pipeline._con_le_misure_della_superficie({"triangles": 0}, vertici, np.zeros((0, 3), dtype=int))
    assert vuote == {"triangles": 0}


def test_the_surface_is_closed(run_dir):
    _, metrics = run_dir
    assert metrics["06_repair"]["watertight_after"] is True


def test_the_volume_matches_the_exact_value(run_dir):
    _, metrics = run_dir
    assert metrics["11_export"]["volume"] == pytest.approx(EXACT_VOLUME, rel=0.1)


def test_no_inverted_tetrahedra(run_dir):
    _, metrics = run_dir
    assert metrics["10_volume_quality"]["inverted"] == 0
    assert metrics["10_volume_quality"]["min_dihedral_deg"]["min"] > 0.0


def test_the_deck_is_readable_and_counts_agree(run_dir):
    meshio = pytest.importorskip("meshio")
    out, metrics = run_dir
    mesh = meshio.read(out / "wall_model.inp")
    assert len(mesh.points) == metrics["09_tetrahedralize"]["nodes"]
    assert sum(len(block.data) for block in mesh.cells) == metrics["09_tetrahedralize"]["tets"]


def test_the_base_set_holds_only_the_nodes_at_the_lowest_level(run_dir):
    out, metrics = run_dir
    text = (out / "wall_model.inp").read_text(encoding="ascii")
    assert "*NSET, NSET=BASE" in text
    assert metrics["11_export"]["node_sets"]["BASE"] > 0

    meshio = pytest.importorskip("meshio")
    points = meshio.read(out / "wall_model.inp").points
    lines = text.splitlines()
    start = lines.index("*NSET, NSET=BASE") + 1
    indices = []
    for line in lines[start:]:
        if line.startswith("*"):
            break
        indices += [int(value) - 1 for value in line.split(",") if value.strip()]
    tolerance = metrics["11_export"]["set_tolerance"]
    assert len(indices) == metrics["11_export"]["node_sets"]["BASE"]
    assert points[indices][:, 2].max() <= points[:, 2].min() + tolerance + 1e-9


def test_geometric_error_against_the_source_cloud_is_reported(run_dir):
    pytest.importorskip("pymeshlab")
    _, metrics = run_dir
    error = metrics["07_surface_quality"]["geometric_error"]
    assert error["hausdorff"] > 0.0
    assert error["cloud_to_mesh"]["RMS"] < SPACING * 2.0


def test_metrics_json_is_the_same_as_the_returned_dictionary(run_dir):
    out, metrics = run_dir
    with (out / "metrics.json").open(encoding="utf-8") as handle:
        assert json.load(handle) == json.loads(json.dumps(metrics))


def test_the_same_configuration_run_twice_gives_the_same_result(tmp_path):
    """Criterio di accettazione: la stessa configurazione produce lo stesso risultato."""
    pytest.importorskip("pymeshfix")
    cloud_path = tmp_path / "box.ply"
    io.write_cloud(cloud_path, synth.sample_box_surface(SIZE, 8.0))

    def once(name):
        cfg = config.PipelineConfig(
            input=config.InputConfig(path=cloud_path, spacing_sample=2000),
            downsample=config.DownsampleConfig(voxel_size=8.0),
            surface=config.SurfaceConfig(poisson_depth=7, density_quantile=0.02),
            run=config.RunConfig(out_dir=tmp_path / name, to_step=12),
        )
        return pipeline.run(cfg)

    first, second = once("a"), once("b")
    assert first["09_tetrahedralize"]["nodes"] == second["09_tetrahedralize"]["nodes"]
    assert first["09_tetrahedralize"]["tets"] == second["09_tetrahedralize"]["tets"]
    assert first["11_export"]["volume"] == pytest.approx(second["11_export"]["volume"], rel=1e-9)


def test_lo_step_9_dichiara_le_autointersezioni_anche_quando_sono_zero(run_dir):
    out, metrics = run_dir
    passo = metrics["09_tetrahedralize"]
    assert passo["self_intersections_before"] == 0
    assert passo["wrap_applied"] is False
    assert "geometric_error" not in passo


def _ripresa_dallo_step_9(run_dir, tmp_path, **tet):
    """Copia della corsa condivisa: `run_dir` e' di modulo, riprendere li'
    riscriverebbe gli artefatti che gli altri test leggono. `to_step=9`
    tiene la corsa fuori dalla condizione `stop >= 12` che carica gia' la
    nuvola (`pipeline.py:668`): senza, il test non passerebbe dal codice nuovo."""
    out, _ = run_dir
    copia = tmp_path / "copia"
    shutil.copytree(out, copia)
    cfg = config.load_config(copia / "config.yaml")
    cfg.run.out_dir = copia
    cfg.run.from_step = 9
    cfg.run.to_step = 9
    cfg.tet.wrap_tolerance = tet.get("wrap_tolerance")
    return copia, cfg


def test_il_wrap_acceso_rimisura_l_errore_contro_la_nuvola(run_dir, tmp_path):
    _, cfg = _ripresa_dallo_step_9(run_dir, tmp_path, wrap_tolerance=20.0)
    passo = pipeline.run(cfg)["09_tetrahedralize"]
    assert passo["wrap_applied"] is True
    assert passo["wrap_hausdorff_max_mm"] <= 20.0
    assert "hausdorff" in passo["geometric_error"]


def test_senza_la_nuvola_segmentata_la_rimisura_nomina_lo_step_2(run_dir, tmp_path):
    copia, cfg = _ripresa_dallo_step_9(run_dir, tmp_path, wrap_tolerance=20.0)
    (copia / "02_segmented.ply").unlink()
    with pytest.raises(ValueError, match="lo step 2 non ha ancora scritto"):
        pipeline.run(cfg)


def test_senza_rimisura_necessaria_non_serve_la_nuvola_segmentata(run_dir, tmp_path):
    """Riga del contratto ingressi: ripresa 9->9 senza 02_segmented.ply e senza
    rimisura necessaria (superficie pulita, wrap spento) -> la corsa riesce.
    Se il codice leggesse comunque la nuvola, il file mancante alzerebbe
    l'errore di `_ingresso_di_ripresa` che nomina lo step 2."""
    copia, cfg = _ripresa_dallo_step_9(run_dir, tmp_path)
    (copia / "02_segmented.ply").unlink()
    passo = pipeline.run(cfg)["09_tetrahedralize"]
    assert passo["self_intersections_before"] == 0
    assert "geometric_error" not in passo


def test_l_errore_dentro_lo_step_9_non_scrive_un_nuovo_09_volume_vtu(run_dir, tmp_path, monkeypatch):
    """Riga del contratto ingressi: `WrapOltreTolleranzaError` /
    `AutointersezioniResidueError` dentro la corsa -> nessun `09_volume.vtu`
    nuovo. `prepara_ingresso` e' il primo passo dello step 9, prima di
    `write_vtu`: simularne il fallimento basta a provare che l'artefatto
    vecchio resta intatto, senza dover inventare una geometria che fallisca
    per davvero."""
    copia, cfg = _ripresa_dallo_step_9(run_dir, tmp_path)
    volume_path = copia / pipeline.ARTIFACTS[9]
    prima = volume_path.read_bytes()

    def esplode(*_args, **_kwargs):
        raise autointersezioni.WrapOltreTolleranzaError("wrap simulato oltre tolleranza")

    monkeypatch.setattr(pipeline.autointersezioni, "prepara_ingresso", esplode)
    with pytest.raises(autointersezioni.WrapOltreTolleranzaError):
        pipeline.run(cfg)

    assert volume_path.read_bytes() == prima


def test_resuming_from_tetrahedralize_works_when_simplify_is_disabled(run_dir):
    """Configurazione predefinita (simplify.enabled=False): lo step 8 non scrive
    08_simplified.ply, quindi from_step=9 deve ricaricare la superficie riparata
    dello step 6, non l'artefatto (assente) dello step 8."""
    out, _ = run_dir
    cfg = config.load_config(out / "config.yaml")
    assert cfg.simplify.enabled is False
    cfg.run.from_step = 9

    resumed = pipeline.run(cfg)
    assert resumed["09_tetrahedralize"]["nodes"] > 0
    assert resumed["11_export"]["volume"] == pytest.approx(EXACT_VOLUME, rel=0.1)


def test_resuming_from_tetrahedralize_still_works_when_simplify_is_enabled(tmp_path):
    """La correzione per simplify disabilitato non deve rompere il caso abilitato."""
    pytest.importorskip("pymeshfix")
    cloud_path = tmp_path / "box.ply"
    io.write_cloud(cloud_path, synth.sample_box_surface(SIZE, SPACING))

    def makecfg(from_step):
        return config.PipelineConfig(
            input=config.InputConfig(path=cloud_path, spacing_sample=5000),
            downsample=config.DownsampleConfig(voxel_size=SPACING),
            surface=config.SurfaceConfig(poisson_depth=8, density_quantile=0.02),
            simplify=config.SimplifyConfig(enabled=True, remesh_target_len_pct=2.0),
            run=config.RunConfig(out_dir=tmp_path / "out", from_step=from_step, to_step=12),
        )

    pipeline.run(makecfg(1))
    resumed = pipeline.run(makecfg(9))
    assert resumed["09_tetrahedralize"]["nodes"] > 0
    assert resumed["11_export"]["volume"] == pytest.approx(EXACT_VOLUME, rel=0.1)


def test_una_mesh_assente_non_si_legge_come_una_mesh_vuota(tmp_path):
    """open3d non solleva su file assente: torna una mesh vuota e scrive un
    avviso su stderr, che nessuno legge (misurato il 24/08/2026: "Read PLY
    failed: unable to open file", zero vertici, nessuna eccezione).

    Senza la guardia questo era il difetto peggiore della ripresa: la lettura
    riusciva, lo step girava su zero vertici e si registrava "riuscito"."""
    with pytest.raises(ValueError, match="nessuna superficie letta"):
        pipeline._read_mesh(tmp_path / "mai-scritta.ply")


def test_una_nuvola_al_posto_di_una_superficie_non_passa_per_superficie(tmp_path):
    """Un .ply di soli punti si apre senza errore e ha zero facce. Contare i
    soli vertici lo lascerebbe passare, e la riparazione girerebbe su una
    superficie che facce non ne ha."""
    solo_punti = tmp_path / "solo-punti.ply"
    io.write_cloud(solo_punti, synth.sample_box_surface(SIZE, SPACING))

    with pytest.raises(ValueError, match="nessuna superficie letta"):
        pipeline._read_mesh(solo_punti)


def test_saltare_uno_step_dice_quale_manca_invece_di_nominare_un_file(tmp_path):
    """Il messaggio nomina gli STEP, non solo il file: chi guarda l'interfaccia
    ragiona per step, e "nessun punto letto da '04_normals.ply'" non dice a
    nessuno che deve eseguire lo step 4 prima del 5."""
    with pytest.raises(ValueError) as caduta:
        pipeline._ingresso_di_ripresa(5, 4, tmp_path, io.read_cloud)

    detto = str(caduta.value)
    assert "lo step 5 pretende 04_normals.ply" in detto
    assert "lo step 4 non ha ancora scritto" in detto
    # La sequenza e' consigliata, non imposta: il messaggio dice come rimediare.
    assert "Esegui prima lo step 4" in detto


def test_un_artefatto_illeggibile_non_si_scambia_per_uno_mai_scritto(tmp_path):
    """Due guasti diversi, due messaggi diversi. Mandare a "eseguire prima lo
    step 4" davanti a un file che esiste ed e' troncato manderebbe a rifare uno
    step gia' fatto, senza dire perche' la prima volta non e' bastata."""
    (tmp_path / "04_normals.ply").write_text("non e' un ply", encoding="utf-8")

    with pytest.raises(ValueError) as caduta:
        pipeline._ingresso_di_ripresa(5, 4, tmp_path, io.read_cloud)

    detto = str(caduta.value)
    assert "esiste ma non si legge" in detto
    assert "non ha ancora scritto" not in detto


def test_riprendere_da_uno_step_saltato_rifiuta_invece_di_corrompere_il_seguito(
    run_dir, tmp_path
):
    """La corsa reale, non la funzione presa a se'.

    Prima della guardia: si toglie 05_surface.ply, si riparte dal 6, la
    riparazione gira su zero vertici, RISCRIVE 06_repaired.ply vuoto e lo
    registra "riuscito". Il danno non era il rifiuto mancato, era che un
    artefatto BUONO a valle veniva sostituito da uno vuoto senza un errore.

    L'oracolo e' quindi doppio: rifiuta, e lascia intatto cio' che c'era."""
    import shutil

    out, _ = run_dir
    copia = tmp_path / "corsa"
    shutil.copytree(out, copia)

    riparata = copia / pipeline.ARTIFACTS[6]
    impronta_prima = riparata.read_bytes()
    (copia / pipeline.ARTIFACTS[5]).unlink()

    cfg = config.load_config(copia / "config.yaml")
    cfg.run.out_dir = copia
    cfg.run.from_step = 6

    with pytest.raises(ValueError, match="lo step 6 pretende 05_surface.ply"):
        pipeline.run(cfg)

    assert riparata.read_bytes() == impronta_prima


def test_un_artefatto_presente_ma_senza_facce_non_attraversa_la_ripresa(run_dir, tmp_path):
    """Il caso che il controllo di esistenza NON copre, e per cui la guardia in
    `_read_mesh` esiste: il file c'e', si apre, ed e' vuoto.

    Misurato togliendo la guardia: senza, questo e' esattamente il percorso su
    cui la riparazione gira su zero vertici e riscrive 06_repaired.ply vuoto
    dichiarandosi riuscita. Il test che toglie il file non basta a coprirlo,
    perche' si ferma prima, sul controllo di esistenza."""
    import shutil

    out, _ = run_dir
    copia = tmp_path / "corsa"
    shutil.copytree(out, copia)

    riparata = copia / pipeline.ARTIFACTS[6]
    prima = riparata.read_bytes()
    # Un .ply VALIDO scritto dove la ripresa cerca una superficie: ha vertici,
    # non ha facce. open3d lo apre senza un solo errore -- e' il caso peggiore,
    # perche' non c'e' niente su cui inciampare tranne le facce che mancano.
    io.write_cloud(copia / pipeline.ARTIFACTS[5], synth.sample_box_surface(SIZE, SPACING))
    assert (copia / pipeline.ARTIFACTS[5]).exists()

    cfg = config.load_config(copia / "config.yaml")
    cfg.run.out_dir = copia
    cfg.run.from_step = 6

    with pytest.raises(ValueError, match="esiste ma non si legge"):
        pipeline.run(cfg)

    assert riparata.read_bytes() == prima


def test_la_nuvola_di_riferimento_dello_step_7_si_ricarica_dal_2_e_non_dalla_tabella(
    run_dir, tmp_path
):
    """Dei cinque punti di ripresa, questo e' l'unico che chiede un numero
    fisso invece della tabella `_RESUME_POINTS`: `source_cloud` e' la nuvola
    SEGMENTATA dello step 2 e nient'altro, perche' e' il riferimento contro cui
    lo step 7 misura l'errore geometrico.

    Attraversato da ogni ripresa, ma senza un oracolo suo: sostituita la riga
    con `_RESUME_POINTS[start]` -- l'errore di copia naturale, dato che le due
    righe si somigliano -- una ripresa dal 6 caricherebbe 04_normals.ply, che
    esiste, e proseguirebbe misurando contro la nuvola sbagliata senza dire
    niente. Misurato il 24/08/2026: con quella sostituzione, `790 passed`.
    """
    import shutil

    out, _ = run_dir
    copia = tmp_path / "corsa"
    shutil.copytree(out, copia)
    # Solo la segmentata: cio' che serve al punto di ripresa provato qui sopra
    # (04_normals.ply) resta al suo posto, cosi' se la riga ripiegasse sulla
    # tabella la ripresa passerebbe invece di fermarsi.
    (copia / pipeline.ARTIFACTS[2]).unlink()

    cfg = config.load_config(copia / "config.yaml")
    cfg.run.out_dir = copia
    cfg.run.from_step = 6

    # «lo step 7» e non «lo step 6»: il messaggio nomina lo step che la
    # CONSUMA, non quello da cui la corsa riparte. Ripartendo dal 6 lo step 7
    # gira, quindi quella nuvola serve davvero e il rifiuto e' giusto.
    with pytest.raises(ValueError, match="lo step 7 pretende 02_segmented.ply"):
        pipeline.run(cfg)


def test_eseguire_un_solo_step_non_pretende_artefatti_che_quello_step_non_tocca(
    run_dir, tmp_path
):
    """«Tecnicamente io devo poter eseguire qualsiasi step in qualsiasi
    momento»: questo e' quel requisito, sul caso concreto.

    La nuvola segmentata dello step 2 ha due soli consumatori, l'errore
    geometrico dello step 7 e il prior dello step 12. Veniva pero' ricaricata a
    ogni ripresa, quindi «esegui solo lo step 9» in una cartella senza
    02_segmented.ply si fermava per un artefatto che lo step 9 non guarda mai.
    """
    import shutil

    out, _ = run_dir
    copia = tmp_path / "corsa"
    shutil.copytree(out, copia)
    (copia / pipeline.ARTIFACTS[2]).unlink()

    cfg = config.load_config(copia / "config.yaml")
    cfg.run.out_dir = copia
    cfg.run.to_step = 9
    cfg.run.from_step = 9

    esito = pipeline.run(cfg)
    assert esito["09_tetrahedralize"]["nodes"] > 0


def test_quando_la_nuvola_di_riferimento_serve_davvero_il_rifiuto_nomina_chi_la_consuma(
    run_dir, tmp_path
):
    """Se invece la corsa arriva al prior, quella nuvola serve sul serio.

    Il messaggio deve nominare lo step 12, che la consuma, e non lo step da cui
    la corsa riparte: «lo step 9 pretende 02_segmented.ply» era falso, e il
    consiglio che ne seguiva -- riprendere dal 2 -- riscrive gli artefatti dal 2
    al 9, cioe' proprio quelli su cui si stava iterando.
    """
    import shutil

    out, _ = run_dir
    copia = tmp_path / "corsa"
    shutil.copytree(out, copia)
    (copia / pipeline.ARTIFACTS[2]).unlink()

    cfg = config.load_config(copia / "config.yaml")
    cfg.run.out_dir = copia
    cfg.run.from_step = 9

    with pytest.raises(ValueError) as caduta:
        pipeline.run(cfg)

    detto = str(caduta.value)
    assert "lo step 12 pretende 02_segmented.ply" in detto
    assert "lo step 9 pretende" not in detto


# ---------------------------------------------------------------------------
# La forma delle celle del maglio, e la ripresa dagli step di valle (10, 11, 12).
# ---------------------------------------------------------------------------


def _scrivi_maglio(percorso, tipo, celle):
    """Un `09_volume.vtu` con un blocco di celle scelto a mano.

    Serve a costruire i file che `abaqus.write_vtu` non scriverebbe mai — un
    blocco di triangoli, due blocchi invece di uno — perché è esattamente da
    quei file che la ripresa si deve difendere: il maglio arriva dal disco, e
    chi lo mette lì non è sempre la corsa precedente di questa pipeline.
    """
    import meshio

    punti = np.array(
        [
            [0.0, 0.0, 0.0],
            [1.0, 0.0, 0.0],
            [0.0, 1.0, 0.0],
            [0.0, 0.0, 1.0],
            [1.0, 1.0, 0.0],
            [1.0, 0.0, 1.0],
        ]
    )
    meshio.write(percorso, meshio.Mesh(punti, [(tipo, np.asarray(celle))]))


def _corsa_con_maglio(run_dir, tmp_path, tipo, celle):
    """Una copia della corsa in cui il solo `09_volume.vtu` è stato sostituito."""
    out, _ = run_dir
    copia = tmp_path / "corsa"
    shutil.copytree(out, copia)
    _scrivi_maglio(copia / pipeline.ARTIFACTS[9], tipo, celle)

    cfg = config.load_config(copia / "config.yaml")
    cfg.run.out_dir = copia
    cfg.run.from_step = 10
    cfg.run.to_step = 10
    return cfg


def test_un_maglio_di_triangoli_non_si_scambia_per_un_maglio_di_volume(run_dir, tmp_path):
    """Il gemello di `server._contorno_del_volume` non controllava la forma.

    Il blocco si prende per unicità, e l'unicità non dice niente sul numero di
    colonne: un file con un solo blocco di `triangle` veniva accettato come
    maglio di volume — misurato `(6, 3) (2, 3)` — e lo step 10 esplodeva più in
    là con `IndexError: index 3 is out of bounds for axis 1 with size 3`.
    `_ingresso_di_ripresa` cattura il guasto e lo traduce, ma un `IndexError`
    che sfugge non attraversa il ramo «esiste ma non si legge»: chi guarda il
    pannello vede un 500 nudo, senza il nome del file né lo step da rifare.

    Mutazione che uccide: togliere il controllo di forma da `_maglio_di_volume`
    — la corsa non si ferma qui e muore dentro `quality.volume_metrics`.
    """
    cfg = _corsa_con_maglio(run_dir, tmp_path, "triangle", [[0, 1, 2], [3, 4, 5]])

    with pytest.raises(ValueError) as caduta:
        pipeline.run(cfg)

    detto = str(caduta.value)
    # Il file lo nomina l'involucro, i tipi e le colonne il lettore: insieme
    # dicono che cosa c'è nel file e perché non serve.
    assert "09_volume.vtu" in detto
    assert "esiste ma non si legge" in detto
    assert "il blocco ['triangle'] ha 3 nodi per cella" in detto


def test_due_blocchi_di_celle_dicono_quanti_ne_ha_trovati(run_dir, tmp_path):
    """Il ramo `len(tipi) != 1` esisteva senza una prova che lo attraversasse.

    `abaqus.write_vtu` scrive un blocco solo, quindi «l'unico» è una chiave che
    non ha bisogno di traduzione fra il vocabolario di meshio e quello di
    Abaqus. Un file che ne porta due non è quel file, e il rifiuto deve dire
    quanti ne ha trovati invece di prenderne uno a caso.

    Mutazione che uccide: `tipi[0]` al posto della guardia — la corsa prende il
    primo blocco in ordine alfabetico e prosegue in silenzio.
    """
    out, _ = run_dir
    copia = tmp_path / "corsa"
    shutil.copytree(out, copia)

    import meshio

    punti = np.array(
        [[0.0, 0.0, 0.0], [1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]]
    )
    meshio.write(
        copia / pipeline.ARTIFACTS[9],
        meshio.Mesh(punti, [("tetra", [[0, 1, 2, 3]]), ("triangle", [[0, 1, 2]])]),
    )

    cfg = config.load_config(copia / "config.yaml")
    cfg.run.out_dir = copia
    cfg.run.from_step = 10
    cfg.run.to_step = 10

    with pytest.raises(ValueError) as caduta:
        pipeline.run(cfg)

    detto = str(caduta.value)
    assert "porta 2 blocchi di celle" in detto
    assert "09_volume.vtu" in detto


def test_un_maglio_senza_celle_si_dichiara_invece_di_rompersi(run_dir, tmp_path):
    """Un `.vtu` con zero celle: il guasto arriva da meshio, non dalla forma.

    Misurato il 31/08/2026: `meshio.write` rifiuta un blocco di lunghezza zero
    («need at least one array to concatenate»), quindi un `cells_dict` con
    `shape == (0,)` non è raggiungibile per quella strada. Un `.vtu` scritto a
    mano con `NumberOfCells="0"` invece si legge, e `meshio.read` stesso alza
    `IndexError: index 0 is out of bounds for axis 0 with size 0` prima che
    questo modulo veda un solo array.

    È lo stesso difetto di `IndexError` visto dall'altro capo: la lista dei
    tipi catturati da `_ingresso_di_ripresa` non può prevedere che cosa alzano
    tre lettori diversi (meshio, open3d, io.read_cloud). Un artefatto che esiste
    e non si legge è un artefatto che non si legge, qualunque cosa alzi.

    Mutazione che uccide: rimettere `except (ValueError, OSError)` — l'errore
    risale nudo e il pannello risponde 500 senza nominare né il file né lo step.
    """
    out, _ = run_dir
    copia = tmp_path / "corsa"
    shutil.copytree(out, copia)
    (copia / pipeline.ARTIFACTS[9]).write_text(
        '<?xml version="1.0"?>\n'
        '<VTKFile type="UnstructuredGrid" version="0.1" byte_order="LittleEndian">\n'
        "  <UnstructuredGrid>\n"
        '    <Piece NumberOfPoints="4" NumberOfCells="0">\n'
        "      <Points>\n"
        '        <DataArray type="Float64" NumberOfComponents="3" format="ascii">\n'
        "          0 0 0  1 0 0  0 1 0  0 0 1\n"
        "        </DataArray>\n"
        "      </Points>\n"
        "      <Cells>\n"
        '        <DataArray type="Int64" Name="connectivity" format="ascii"> </DataArray>\n'
        '        <DataArray type="Int64" Name="offsets" format="ascii"> </DataArray>\n'
        '        <DataArray type="UInt8" Name="types" format="ascii"> </DataArray>\n'
        "      </Cells>\n"
        "    </Piece>\n"
        "  </UnstructuredGrid>\n"
        "</VTKFile>\n",
        encoding="utf-8",
    )

    cfg = config.load_config(copia / "config.yaml")
    cfg.run.out_dir = copia
    cfg.run.from_step = 10
    cfg.run.to_step = 10

    with pytest.raises(ValueError) as caduta:
        pipeline.run(cfg)

    detto = str(caduta.value)
    assert "lo step 10 pretende 09_volume.vtu" in detto
    assert "esiste ma non si legge" in detto


def _solo_gli_artefatti(run_dir, tmp_path, tenuti):
    """Una copia della corsa con i soli artefatti numerati elencati in `tenuti`."""
    out, _ = run_dir
    copia = tmp_path / "corsa"
    shutil.copytree(out, copia)
    for numero, nome in pipeline.ARTIFACTS.items():
        if numero not in tenuti:
            (copia / nome).unlink(missing_ok=True)

    cfg = config.load_config(copia / "config.yaml")
    cfg.run.out_dir = copia
    return cfg


def test_le_metriche_di_volume_non_pretendono_nuvola_ne_superficie(run_dir, tmp_path):
    """«Esegui solo lo step 10» in una cartella che ha il solo maglio.

    Lo step 10 è `quality.volume_metrics(nodes, tets, ...)`: non tocca `points`,
    non tocca `spacing`, non tocca `vertices`. La ripresa li ricaricava lo
    stesso, quindi in una cartella incompleta si fermava su `04_normals.ply`
    prima e su `06_repaired.ply` poi — due file che quello step non guarda —
    e il consiglio che ne seguiva («Esegui da qui fino al deck dallo step 4»)
    riscrive gli artefatti dal 4 al 10, cioè proprio quelli su cui si sta
    iterando. È la stessa trappola già chiusa per `02_segmented.ply`.

    Mutazione che uccide: togliere una delle due guardie nuove — la corsa
    pretende di nuovo un artefatto che questo step non consuma.
    """
    cfg = _solo_gli_artefatti(run_dir, tmp_path, {9})
    cfg.run.from_step = 10
    cfg.run.to_step = 10

    esito = pipeline.run(cfg)
    assert esito["10_volume_quality"]["tets"] > 0


def test_il_deck_si_riesporta_senza_la_nuvola_ma_con_maglio_e_superficie(
    run_dir, tmp_path
):
    """Lo step 11 usa `vertices` — il riferimento di `align_to_axes` — e basta.

    La nuvola non entra nell'esportazione da nessuna parte: pretenderla
    rifiutava una riesportazione del deck che aveva tutto ciò che le serve.

    Mutazione che uccide: rimettere il caricamento della nuvola incondizionato
    — la corsa si ferma su `04_normals.ply`, che qui non c'è.
    """
    cfg = _solo_gli_artefatti(run_dir, tmp_path, {6, 9})
    cfg.run.from_step = 11
    cfg.run.to_step = 11

    esito = pipeline.run(cfg)
    assert esito["11_export"]["volume"] == pytest.approx(EXACT_VOLUME, rel=0.1)


def test_lo_step_11_ricarica_la_superficie_semplificata_quando_e_accesa(tmp_path):
    """La regola di `from_step=9` vale identica per l'11, e la guardia nuova
    non deve perderla: con la semplificazione accesa la superficie valida a
    monte è `08_simplified.ply`, altrimenti `06_repaired.ply`.

    Mutazione che uccide: fissare `resume_from = 6` — la corsa si ferma su
    `06_repaired.ply`, che qui è stato tolto apposta.
    """
    pytest.importorskip("pymeshfix")
    cloud_path = tmp_path / "box.ply"
    io.write_cloud(cloud_path, synth.sample_box_surface(SIZE, SPACING))

    def makecfg(from_step, to_step):
        return config.PipelineConfig(
            input=config.InputConfig(path=cloud_path, spacing_sample=5000),
            downsample=config.DownsampleConfig(voxel_size=SPACING),
            surface=config.SurfaceConfig(poisson_depth=8, density_quantile=0.02),
            simplify=config.SimplifyConfig(enabled=True, remesh_target_len_pct=2.0),
            tet=config.TetConfig(min_ratio=1.2),
            run=config.RunConfig(
                out_dir=tmp_path / "out", from_step=from_step, to_step=to_step
            ),
        )

    pipeline.run(makecfg(1, 12))
    out = tmp_path / "out"
    assert (out / pipeline.ARTIFACTS[8]).exists()
    # Solo la riparata: se la guardia ripiegasse sul 6 la ripresa si fermerebbe.
    (out / pipeline.ARTIFACTS[6]).unlink()

    esito = pipeline.run(makecfg(11, 11))
    assert esito["11_export"]["volume"] == pytest.approx(EXACT_VOLUME, rel=0.1)


def test_il_prior_la_nuvola_la_pretende_davvero_e_il_rifiuto_la_nomina(run_dir, tmp_path):
    """Lo step 12 è l'unico dei tre di valle che la nuvola la consuma: la
    spaziatura che passa a `wall.prior` viene da lì. Le guardie nuove tolgono
    il caricamento a chi non lo usa, non a chi lo usa.

    Mutazione che uccide: aggiungere `stop >= 12` alla guardia sbagliata (o
    toglierlo da quella giusta) — la corsa arriva al prior senza spaziatura,
    o non arriva affatto.
    """
    cfg = _solo_gli_artefatti(run_dir, tmp_path, {2, 6, 9})
    cfg.run.from_step = 12
    cfg.run.to_step = 12

    with pytest.raises(ValueError) as caduta:
        pipeline.run(cfg)

    detto = str(caduta.value)
    assert "lo step 12 pretende 04_normals.ply" in detto


def test_una_corsa_completa_lascia_i_dodici_step_di_elaborazione_validi(tmp_path):
    """Dal Task 9 (Fase 4) lo step 12 (prior geometrico) e' parte della corsa
    madre: una corsa intera non lascia piu' nulla di "mai eseguito". Il
    registro finisce li', e `_config_cubo` fissa `to_step=12` (vedi il suo
    docstring)."""
    from meshrec.core import pipeline, steps

    cfg = _config_cubo(tmp_path)
    pipeline.run(cfg)
    stato = steps.run_state(cfg.run.out_dir, cfg)
    per_numero = {voce["numero"]: voce["stato"] for voce in stato}
    assert all(per_numero[n] == "valido" for n in range(1, 13))


def test_cambiare_un_parametro_a_monte_invalida_gli_step_a_valle(tmp_path):
    """Prova a variabile unica sulla corsa vera, non sulle sole impronte."""
    from meshrec.core import pipeline, steps

    cfg = _config_cubo(tmp_path)
    pipeline.run(cfg)
    cfg.surface.poisson_depth = cfg.surface.poisson_depth - 1
    per_numero = {voce["numero"]: voce["stato"] for voce in steps.run_state(cfg.run.out_dir, cfg)}
    assert [per_numero[n] for n in (1, 2, 3, 4)] == ["valido"] * 4
    assert [per_numero[n] for n in (5, 6, 7, 8, 9, 10, 11)] == ["non valido"] * 7


def test_fermarsi_a_uno_step_non_esegue_quelli_dopo(tmp_path):
    from meshrec.core import pipeline, steps

    cfg = _config_cubo(tmp_path)
    cfg.run.to_step = 3
    metriche = pipeline.run(cfg)
    assert set(metriche) == {"01_load", "02_segment", "03_downsample"}
    per_numero = {voce["numero"]: voce["stato"] for voce in steps.run_state(cfg.run.out_dir, cfg)}
    assert per_numero[3] == "valido"
    assert per_numero[4] == "mai eseguito"


def test_to_step_non_puo_precedere_from_step(tmp_path):
    from meshrec.core.config import RunConfig

    with pytest.raises(ValueError):
        RunConfig(from_step=5, to_step=3)


def test_una_corsa_interrotta_registra_quale_step_si_e_rotto(tmp_path, monkeypatch):
    """Il ramo che scrive lo stato 'fallito' va provato su una corsa vera:
    e' un'affermazione scritta su disco, e finora nulla la smentiva."""
    from meshrec.core import pipeline, steps, surface

    cfg = _config_cubo(tmp_path)

    def esplode(*_argomenti, **_chiavi):
        raise RuntimeError("interruzione simulata dello step 3")

    monkeypatch.setattr(surface, "downsample", esplode)
    with pytest.raises(RuntimeError):
        pipeline.run(cfg)

    salvato = steps.read_state(cfg.run.out_dir)
    assert salvato["03_downsample"]["esito"] == "fallito"
    assert salvato["02_segment"]["esito"] == "riuscito"
    assert "04_normals" not in salvato


def test_gli_step_eseguiti_uno_alla_volta_accumulano_le_metriche(tmp_path):
    """L'interfaccia esegue uno step per volta: se ognuno sostituisse
    metrics.json, il pannello delle metriche perderebbe tutto cio' che sta a
    monte dello step aperto."""
    from meshrec.core import pipeline

    cfg = _config_cubo(tmp_path)
    cfg.run.to_step = 1
    pipeline.run(cfg)

    # to_step prima di from_step: con validate_assignment=True ogni riga
    # rivalida l'intero modello, e assegnare from_step=2 mentre to_step e'
    # ancora 1 (il valore lasciato dalla corsa precedente) violerebbe il
    # vincolo to_step >= from_step su uno stato intermedio che non esiste
    # mai nella configurazione finale.
    cfg.run.to_step = 2
    cfg.run.from_step = 2
    unite = pipeline.run(cfg)

    assert set(unite) == {"01_load", "02_segment"}
    rilette = json.loads((cfg.run.out_dir / pipeline.METRICS_FILENAME).read_text(encoding="utf-8"))
    assert rilette == unite


def test_una_corsa_completa_arriva_allo_step_dodici(tmp_path):
    """Lo step 12 chiude la corsa madre: se non compare nelle metriche, il
    prior non e' stato calcolato e i modelli parametrici non hanno da cosa
    partire."""
    from meshrec.core import pipeline, steps

    cfg = _config_cubo(tmp_path)

    metriche = pipeline.run(cfg)

    assert "12_wall" in metriche
    assert (cfg.run.out_dir / pipeline.WALL_FILENAME).exists()
    stato = steps.read_state(cfg.run.out_dir)
    assert stato["12_wall"]["esito"] == "riuscito"


def test_lo_step_dodici_si_puo_fermare_prima_con_to_step(tmp_path):
    """to_step=11 lascia la corsa dov'era prima della Fase 4: le corse gia'
    fatte restano riproducibili senza calcolare un prior che nessuno ha
    chiesto."""
    from meshrec.core import pipeline

    cfg = _config_cubo(tmp_path)
    cfg.run.to_step = 11

    metriche = pipeline.run(cfg)

    assert "11_export" in metriche
    assert "12_wall" not in metriche
    assert not (cfg.run.out_dir / pipeline.WALL_FILENAME).exists()


def test_una_corsa_predefinita_non_eredita_il_prior_della_corsa_precedente(tmp_path):
    """Il flag di completezza deve seguire il nucleo, o metrics.json mente.

    `pipeline_completa` decide se la corsa e' autoritativa -- sostituisce
    metrics.json -- oppure se si fonde con cio' che la cartella conteneva gia'.
    La riga che lo mette a True stava dopo lo step 12; sceso il predefinito a
    11, ogni corsa predefinita usciva prima di raggiungerla, cadeva nel ramo di
    fusione, e si portava dietro il `12_wall` della corsa precedente --
    misurato su un'altra geometria e presentato come proprio. In un progetto la
    cui tesi e' la provenienza, e' il difetto peggiore della categoria.

    La suite non lo vedeva perche' ogni test parte da una `tmp_path` vergine.
    Serve una cartella *riusata*, che e' poi il caso d'uso vero: si ritara un
    parametro e si rilancia sulla stessa corsa.

    Mutazione che lo uccide: rimettere `pipeline_completa = True` dopo lo step
    12."""
    cfg = _config_cubo(tmp_path)
    pipeline.run(cfg)
    salvato = json.loads(
        (cfg.run.out_dir / pipeline.METRICS_FILENAME).read_text(encoding="utf-8")
    )
    assert "12_wall" in salvato, "la corsa a 12 non ha lasciato il prior: il test non proverebbe nulla"

    cfg.run = config.RunConfig(out_dir=cfg.run.out_dir)
    metriche = pipeline.run(cfg)

    assert "12_wall" not in metriche
    riletto = json.loads(
        (cfg.run.out_dir / pipeline.METRICS_FILENAME).read_text(encoding="utf-8")
    )
    assert "12_wall" not in riletto, (
        "metrics.json conserva un prior che questa corsa non ha calcolato"
    )


@pytest.fixture(scope="module")
def corsa_all_undici(tmp_path_factory):
    """Una corsa ferma al deck: il punto di partenza del comando `solve`.

    Di modulo per la ragione di `run_dir`: l'elaborazione geometrica e' la
    parte lenta, e i banchi qui sotto ne cambiano solo la coda. Ogni test ne
    prende una copia propria, perche' risolvere scrive nella cartella.
    """
    pytest.importorskip("pymeshfix")
    base = tmp_path_factory.mktemp("undici")
    cloud_path = base / "box.ply"
    io.write_cloud(cloud_path, synth.sample_box_surface(SIZE, SPACING))
    cfg = config.PipelineConfig(
        input=config.InputConfig(path=cloud_path, spacing_sample=5000),
        downsample=config.DownsampleConfig(voxel_size=SPACING),
        surface=config.SurfaceConfig(poisson_depth=8, density_quantile=0.02),
        tet=config.TetConfig(min_ratio=1.2),
        run=config.RunConfig(out_dir=base / "out", to_step=11),
    )
    pipeline.run(cfg)
    return cfg


def _copia_della_corsa(corsa, tmp_path):
    """La corsa del modulo sotto tmp_path, con la configurazione che la nomina."""
    destinazione = tmp_path / "out"
    shutil.copytree(corsa.run.out_dir, destinazione)
    cfg = corsa.model_copy(deep=True)
    cfg.run.out_dir = destinazione
    return cfg


def test_una_corsa_fermata_al_dieci_non_si_dichiara_completa(tmp_path):
    """Il gemello di `test_una_corsa_piena_sostituisce_una_chiave_estranea...`,
    dall'altro lato del confine: una corsa intera SOSTITUISCE metrics.json, una
    corsa parziale ci si FONDE, ed e' la distinzione da cui dipende lo sweep
    della Fase 2.

    Serve perche' senza di lui spostare o non spostare `pipeline_completa =
    True` lascia la suite verde in entrambi i casi. La chiave estranea
    sopravvive solo se la corsa si e' considerata parziale: e' un controllo
    indiretto ma non circolare, perche' non rilegge il valore che vuole
    provare.

    Il confine si e' spostato una volta, e questo test con lui. Fermava a 11
    quando il nucleo di `run()` chiudeva allo step 12; ora il nucleo chiude al
    deck dello step 11 -- e' il perimetro del prodotto, vedi PRODUCT.md --
    quindi una corsa a 11 e' intera e
    sostituisce, mentre la prima parziale e' quella a 10. Il guardiano e' lo
    stesso, un passo piu' sotto: sorveglia il confine, non il numero.

    L'altro lato lo tiene
    `test_una_corsa_predefinita_non_eredita_il_prior_della_corsa_precedente`,
    che verifica che a 11 la sostituzione avvenga davvero.
    """
    from meshrec.core import pipeline

    cfg = _config_cubo(tmp_path)
    cfg.run.to_step = 10
    out = cfg.run.out_dir
    out.mkdir(parents=True, exist_ok=True)
    (out / pipeline.METRICS_FILENAME).write_text(
        json.dumps({"99_estranea": {"ok": True}}), encoding="utf-8"
    )

    pipeline.run(cfg)

    metriche = json.loads((out / pipeline.METRICS_FILENAME).read_text(encoding="utf-8"))
    assert "99_estranea" in metriche


def test_il_prior_scritto_su_disco_e_quello_che_le_metriche_dichiarano(tmp_path):
    """La provenienza e' parte del risultato: il file e le metriche non possono
    raccontare due storie diverse dello stesso calcolo."""
    from meshrec.core import pipeline

    cfg = _config_cubo(tmp_path)
    metriche = pipeline.run(cfg)

    scritto = json.loads(
        (cfg.run.out_dir / pipeline.WALL_FILENAME).read_text(encoding="utf-8")
    )
    assert scritto["regioni_trovate"] == metriche["12_wall"]["regioni_trovate"]
    assert len(scritto["membrature"]) == len(metriche["12_wall"]["membrature"])


def test_la_corsa_figlia_ha_cartella_configurazione_deck_e_metriche_proprie(tmp_path):
    """Ogni modello e' la propria cartella: la provenienza e' parte del
    risultato, e un modello senza la configurazione che lo ha prodotto non e'
    ricostruibile a distanza di mesi.

    Mutazione che deve morire: cancellare `save_config(cfg, out / "config.yaml")`
    in `genera_modello` -- la prima asserzione non troverebbe piu' il file.
    """
    cfg = _config_cubo(tmp_path)
    pipeline.run(cfg)
    figlia = tmp_path / "figlia-estruso"

    esito = pipeline.genera_modello(cfg, "estruso", figlia)

    assert (figlia / "config.yaml").exists()
    assert (figlia / "wall_model.inp").exists()
    assert (figlia / pipeline.MODEL_FILENAME).exists()
    assert esito["tipo"] == "estruso"
    assert esito["sorgente"] == str(cfg.run.out_dir)
    assert esito["hexa"]["hexes"] > 0
    assert esito["hexa"]["inverted"] == 0


def test_un_prior_scritto_prima_delle_nuove_misure_si_rilegge_ancora():
    """`runs/muro/` e `runs/lab_crop/` sono corse di riferimento in sola
    lettura, e i loro 12_wall.json non portano le chiavi nuove. Rileggerle non
    deve rompersi -- e non deve nemmeno riempirle: assente vuol dire assente,
    non zero e non una stima.

    Il test passa gia' oggi, perche' i tre campi hanno un predefinito e
    `_ricostruisci_membrature` non li nomina. Resta come guardia: e' cio' che
    impedisce a un compito futuro di renderli obbligatori senza accorgersene.
    """
    voce_vecchia = {
        "asse": [0.0, 0.0, 1.0],
        "origine": [0.0, 0.0, 0.0],
        "lunghezza": 3000.0,
        "sezione": [300.0, 300.0],
        "sezione_dispersione": [0.01, 0.01],
        "contorno": [[-150.0, -150.0], [150.0, -150.0], [150.0, 150.0], [-150.0, 150.0]],
        "fuori_piombo_deg": 0.0,
        "asse_ideale": [0.0, 0.0, 1.0],
        "scarto_asse_deg": 0.0,
        "volume": 270_000_000.0,
        "riempimento": {"valore": 0.98, "stato": "pieno", "densita_dispersione": 0.1},
    }

    membrature = pipeline._ricostruisci_membrature({"membrature": [voce_vecchia]})

    assert len(membrature) == 1
    assert len(membrature[0].sezioni_fette) == 0, "non inventare fette che nessuno ha misurato"
    assert len(membrature[0].quote_fette) == 0
    assert membrature[0].base_sezione.shape == (0, 3)


def test_un_prior_senza_base_di_sezione_non_fabbrica_giunzioni():
    """L'altra meta' della compatibilita' all'indietro: le membrature
    ricostruite da un prior vecchio non portano il piano di sezione, e
    `wall.giunzioni` deve rendere la lista vuota invece di dedurre un'invasione
    su una base che non c'e'. Due montanti dichiarati identici e coincidenti:
    se la base assente venisse ignorata, questo sarebbe l'incontro piu' facile
    da inventare.
    """
    from meshrec.core import wall

    def voce(origine):
        return {
            "asse": [0.0, 0.0, 1.0],
            "origine": origine,
            "lunghezza": 3000.0,
            "sezione": [300.0, 300.0],
            "sezione_dispersione": [0.01, 0.01],
            "contorno": [[-150.0, -150.0], [150.0, -150.0], [150.0, 150.0], [-150.0, 150.0]],
            "fuori_piombo_deg": 0.0,
            "asse_ideale": [0.0, 0.0, 1.0],
            "scarto_asse_deg": 0.0,
            "volume": 270_000_000.0,
            "riempimento": {"valore": 0.98, "stato": "pieno", "densita_dispersione": 0.1},
        }

    membrature = pipeline._ricostruisci_membrature(
        {"membrature": [voce([0.0, 0.0, 0.0]), voce([0.0, 0.0, 0.0])]}
    )

    assert wall.giunzioni(membrature) == []


def test_lo_scostamento_dalla_nuvola_prende_i_nodi_e_la_nuvola_giusti(tmp_path):
    """Giro di correzione 2: questo test **non verifica l'aritmetica** di
    `quality.vertex_deviation` -- e' gia' protetta altrove (mutare
    `quality.py:469` uccide quattro test in `tests/test_quality.py`, fra cui
    `test_su_una_calotta_il_campionamento_dei_soli_vertici_sottostima_l_errore`).
    Verifica solo il **cablaggio**: che `esito["scostamento_nuvola"]` venga
    davvero dai nodi del modello e dalla nuvola segmentata della madre, e non
    da qualcos'altro o da nessuna parte. Ricostruisce qui, indipendentemente,
    nodi e nuvola dagli stessi file su disco e ricalcola, invece di rileggere
    il numero che `genera_modello` ha appena scritto.

    Mutazione che deve morire (quella del giro di correzione 1): rinominare la
    chiave `"scostamento_nuvola"` in `genera_modello`, per esempio in
    `"scostamento_nuvola_assente"` -- il primo accesso a
    `esito["scostamento_nuvola"]` solleva `KeyError`.
    """
    from meshrec.core import hexa

    cfg = _config_cubo(tmp_path)
    pipeline.run(cfg)

    esito = pipeline.genera_modello(cfg, "estruso", tmp_path / "figlia")

    with (cfg.run.out_dir / pipeline.WALL_FILENAME).open(encoding="utf-8") as handle:
        prior = json.load(handle)
    membrature = pipeline._ricostruisci_membrature(prior)
    modello_indipendente = hexa.costruisci(membrature, "estruso", cfg.model)
    nuvola, _ = io.read_cloud(cfg.run.out_dir / pipeline.ARTIFACTS[2])
    scarti = quality.vertex_deviation(modello_indipendente["nodi"], nuvola)

    scostamento = esito["scostamento_nuvola"]
    assert scostamento["rms"] == pytest.approx(float(np.sqrt(np.mean(scarti ** 2))))
    assert scostamento["max"] == pytest.approx(float(scarti.max()))
    assert scostamento["rms"] >= 0.0


def test_lo_scostamento_dalla_nuvola_e_esatto_su_una_nuvola_spostata_di_una_distanza_nota(tmp_path):
    """Geometria di risposta nota, calcolata su carta prima di eseguire il
    codice: la nuvola sorgente e' i nodi del modello, gli stessi che
    `genera_modello` ricostruira' internamente dallo stesso prior, spostati di
    un offset costante lungo x. L'offset (0,001 mm) e' molto sotto il passo di
    mesh del cubo di prova (~20 mm, vedi `hexa.passo_di_mesh`): nessun nodo
    spostato puo' essere piu' vicino al proprio vicino del proprio gemello
    spostato. Quindi ogni nodo ha distanza esatta `offset` dal punto piu'
    vicino della nuvola, e per un campione a valore costante RMS = max =
    offset, per definizione, senza bisogno di eseguire nulla per saperlo.

    Mutazione che deve morire: `distanze * 2.0` in
    `quality.vertex_deviation` (`quality.py:469`, quella del revisore) -- RMS
    e max uscirebbero il doppio dell'offset atteso.
    """
    from meshrec.core import hexa

    cfg = _config_cubo(tmp_path)
    pipeline.run(cfg)

    with (cfg.run.out_dir / pipeline.WALL_FILENAME).open(encoding="utf-8") as handle:
        prior = json.load(handle)
    membrature = pipeline._ricostruisci_membrature(prior)
    nodi = hexa.costruisci(membrature, "estruso", cfg.model)["nodi"]

    offset = 0.001
    nuvola_nota = nodi + np.array([offset, 0.0, 0.0])
    io.write_cloud(cfg.run.out_dir / pipeline.ARTIFACTS[2], nuvola_nota)

    esito = pipeline.genera_modello(cfg, "estruso", tmp_path / "figlia-nota")

    assert esito["scostamento_nuvola"]["rms"] == pytest.approx(offset, abs=1e-9)
    assert esito["scostamento_nuvola"]["max"] == pytest.approx(offset, abs=1e-9)


def test_il_deck_della_corsa_figlia_e_esaedrico(tmp_path):
    """Mutazione che deve morire: scambiare `cfg.model.element` con `cfg.tet.element`
    nella chiamata a `abaqus.export_model` dentro `genera_modello` -- il deck
    tornerebbe a scrivere C3D4, e la prima asserzione fallirebbe."""
    cfg = _config_cubo(tmp_path)
    pipeline.run(cfg)
    figlia = tmp_path / "figlia-primitive"

    pipeline.genera_modello(cfg, "primitive", figlia)

    testo = (figlia / "wall_model.inp").read_text(encoding="ascii")
    assert "*ELEMENT, TYPE=C3D8I" in testo
    assert "TYPE=C3D4" not in testo


_TELAIO_QUATTRO_MEMBRATURE = [
    ((0.0, -90.0, 0.0), (200.0, 180.0, 1600.0)),
    ((1400.0, -130.0, 0.0), (200.0, 260.0, 1600.0)),
    ((0.0, -70.0, 1600.0), (1600.0, 140.0, 300.0)),
    ((0.0, -170.0, -300.0), (1600.0, 340.0, 300.0)),
]
"""Stesso telaio sintetico di tests/test_wall.py:33-38 e tests/feasibility/test_calculix.py.

I numeri del banco stanno qui, non in src/: e' la stessa convenzione gia'
seguita da test_calculix.py, che li duplica invece di importarli da un altro
file di test."""

_TELAIO_A_SEZIONE_UNIFORME = [
    ((0.0, 0.0, 0.0), (200.0, 200.0, 1600.0)),
    ((1400.0, 0.0, 0.0), (200.0, 200.0, 1600.0)),
    ((0.0, 0.0, 1600.0), (1600.0, 200.0, 300.0)),
    ((0.0, 0.0, -300.0), (1600.0, 200.0, 300.0)),
]
"""Stesso telaio di tests/test_wall.py:442-445 (TELAIO_A_SEZIONE_UNIFORME): le
quattro sezioni uguali fondono la scomposizione in un'unica regione a Π, che
il riempimento dichiara «vuoto» e affidabile (vedi
test_la_regione_a_pi_esce_vuota_e_affidabile_invece_di_essere_scartata in
quel file) senza scartarla -- il rifiuto spetta a chi costruisce."""

_SPAZIATURA_TELAIO = 20.0


def _scrivi_prior_telaio(cfg, telaio, spaziatura=_SPAZIATURA_TELAIO):
    """Scrive `02_segmented.ply` e `12_wall.json` per un telaio sintetico, senza
    passare per `pipeline.run` (che su un telaio costerebbe Poisson piu'
    TetGen): chiama `wall.prior` direttamente, come il codice vero lo produce."""
    from meshrec.core import wall

    punti = synth.sample_frame_surface(telaio, spaziatura)
    out = cfg.run.out_dir
    out.mkdir(parents=True, exist_ok=True)
    io.write_cloud(out / pipeline.ARTIFACTS[2], punti)
    esito_prior = wall.prior(punti, cfg.segment, cfg.wall, spaziatura)
    (out / pipeline.WALL_FILENAME).write_text(
        json.dumps(esito_prior, indent=2, default=float, ensure_ascii=False), encoding="utf-8"
    )
    return esito_prior


@pytest.mark.parametrize("tipo", ["estruso", "primitive"])
def test_genera_modello_scrive_anche_la_geometria_step(tmp_path, tipo):
    """Accanto al deck, `modello.step`: un solido per il telaio sintetico, la
    metrica in `esito["step"]` e in modello.json, per entrambi i tipi."""
    cfg = _config_cubo(tmp_path)
    _scrivi_prior_telaio(cfg, _TELAIO_QUATTRO_MEMBRATURE)
    figlia = tmp_path / f"figlia-{tipo}"
    esito = pipeline.genera_modello(cfg, tipo, figlia)
    assert (figlia / pipeline.MODEL_STEP_FILENAME).exists()
    assert esito["step"]["solidi"] == 1
    assert esito["step"]["volume"] > 0.0
    # Il telaio sintetico compenetra alle giunzioni: lo scarto e' 0,0209
    # (estruso) e 0,0178 (primitive). Zero vorrebbe dire che il `fuse` non ha
    # fuso -- quattro solidi accostati, volume uguale alla somma -- e passerebbe
    # con il solo estremo superiore.
    assert 0.005 < esito["step"]["scarto_relativo"] < 0.05
    riletto = json.loads((figlia / pipeline.MODEL_FILENAME).read_text(encoding="utf-8"))
    assert riletto["step"]["file"].endswith("modello.step")


def test_il_deck_parametrico_e_nudo_quanto_quello_del_muro(tmp_path):
    """`genera_modello` scrive `*TIE`/`*SURFACE` (il legame fra membrature) e
    nessuna card di materiale, vincolo o passo: il deck parametrico e' nudo
    quanto quello del muro (spec 2026-09-07).

    `test_il_telaio_costruito_dichiara_le_superfici_del_tie` (test_hexa.py)
    guarda il dizionario che `hexa.costruisci` produce, non il file scritto:
    qui si legge il `.inp`.

    Mutazione che lo uccide: togliere `ties=` o `element_surfaces=` dalla
    chiamata a `export_model` in `genera_modello` (pipeline.py).
    """
    cfg = _config_cubo(tmp_path)
    _scrivi_prior_telaio(cfg, _TELAIO_QUATTRO_MEMBRATURE)
    figlia = tmp_path / "figlia-estruso"

    pipeline.genera_modello(cfg, "estruso", figlia)

    testo = (figlia / pipeline.DECK_FILENAME).read_text(encoding="ascii")
    assert "*TIE, NAME=" in testo
    assert "*SURFACE, TYPE=ELEMENT" in testo
    for card in ("*SOLID SECTION", "*MATERIAL", "*BOUNDARY", "*STEP"):
        assert card not in testo


def test_senza_geometria_step_non_resta_un_modello_json_che_la_dichiara(tmp_path, monkeypatch):
    """`scrivi_step` che solleva dopo il deck: l'eccezione propaga e
    `modello.json` non viene scritto -- non deve restare un modello.json che
    dichiara uno step senza il file."""
    from meshrec.core import hexa

    def rotto(prismi, percorso):
        raise RuntimeError("step rotto")

    monkeypatch.setattr(hexa, "scrivi_step", rotto)

    cfg = _config_cubo(tmp_path)
    _scrivi_prior_telaio(cfg, _TELAIO_QUATTRO_MEMBRATURE)
    figlia = tmp_path / "figlia-estruso"

    with pytest.raises(RuntimeError, match="step rotto"):
        pipeline.genera_modello(cfg, "estruso", figlia)

    # Lo step si scrive prima del deck: caduto lui, la figlia resta col solo
    # `config.yaml`, che `report.confronta` rifiuta a voce alta. Col deck
    # dentro e senza `modello.json` la leggerebbe invece come «as-built».
    assert not (figlia / pipeline.DECK_FILENAME).exists()
    assert sorted(p.name for p in figlia.iterdir()) == ["config.yaml"]
    assert not (figlia / pipeline.MODEL_FILENAME).exists()


def test_la_ricostruzione_legge_riempimento_sezione_e_densita_dispersione_dalle_chiavi_giuste(tmp_path):
    """Giro di correzione 2: dei quindici campi di `Membratura`, dodici sono
    presi 1:1 dal JSON del prior e tre stanno annidati sotto `"riempimento"`.
    `riempimento_stato` e' gia' protetto dalla guardia del Ruling J (vedi
    sotto); `riempimento_sezione` e `densita_dispersione` no, perche' oggi
    nessuna funzione a valle li legge da una `Membratura` -- solo lo stato
    alimenta la guardia. Questo test chiude quel divario leggendo
    direttamente il risultato di `pipeline._ricostruisci_membrature`, invece
    di aspettare un consumatore a valle che oggi non esiste.

    Mutazione che deve morire (quella del revisore): leggere
    `riempimento_sezione` da `voce["riempimento"]["soglia"]` invece che da
    `["valore"]` -- sul cubo di prova le due chiavi hanno valori diversi (la
    soglia e' un parametro di configurazione, il valore e' la misura), quindi
    la prima asserzione fallirebbe.
    """
    cfg = _config_cubo(tmp_path)
    pipeline.run(cfg)
    with (cfg.run.out_dir / pipeline.WALL_FILENAME).open(encoding="utf-8") as handle:
        prior = json.load(handle)

    membrature = pipeline._ricostruisci_membrature(prior)

    voce = prior["membrature"][0]
    membratura = membrature[0]
    assert voce["riempimento"]["valore"] != voce["riempimento"]["soglia"], (
        "il banco deve dare due chiavi con valori diversi, o la mutazione non e' rilevabile"
    )
    assert membratura.riempimento_sezione == pytest.approx(voce["riempimento"]["valore"])
    assert membratura.densita_dispersione == pytest.approx(voce["riempimento"]["densita_dispersione"])
    assert membratura.riempimento_stato == voce["riempimento"]["stato"]


def test_una_corsa_figlia_fallita_non_lascia_una_cartella_orfana(tmp_path):
    """F1: se `hexa.costruisci` solleva, la cartella figlia non deve restare
    con dentro il solo `config.yaml` -- /api/compare la includerebbe (e' una
    directory), non ci troverebbe ne' `modello.json` ne' `12_wall.json`, e la
    rifiuterebbe con lo stesso errore che oggi si legge alla prima apertura
    della pagina (vedi `report.confronta`).

    Mutazione che deve morire: in `genera_modello`, richiamare `save_config`
    prima di `hexa.costruisci` invece che dopo -- la cartella figlia
    conterrebbe `config.yaml` anche quando la generazione fallisce.
    """
    cfg = _config_cubo(tmp_path)
    esito_prior = _scrivi_prior_telaio(cfg, _TELAIO_A_SEZIONE_UNIFORME)
    assert esito_prior["membrature"][0]["riempimento"]["stato"] == "vuoto"

    figlia = tmp_path / "figlia-fallita"
    with pytest.raises(ValueError, match="riempimento di sezione «vuoto»"):
        pipeline.genera_modello(cfg, "estruso", figlia)

    assert not (figlia / "config.yaml").exists()


def test_la_corsa_madre_non_cambia_quando_si_genera_un_modello(tmp_path):
    """La selezione e' un'azione e non un parametro: se toccasse la
    configurazione della madre, rigenerare un modello in piu' cambierebbe
    l'impronta di una corsa che non e' cambiata.

    Il solo confronto testuale non basta: `save_config` e' deterministica,
    quindi riscrivere `config.yaml` della madre con lo stesso `cfg` invariato
    produrrebbe un testo bit-identico, e la mutazione piu' ovvia (scrivere su
    `sorgente / "config.yaml"` invece che su `out / "config.yaml"`, senza
    toccare `cfg`) passerebbe inosservata. Il tempo di modifica del file
    cambia a ogni scrittura, che ne cambi o no il contenuto: e' il sensore
    che il confronto testuale non e'.

    Mutazione che deve morire (giro di correzione 2): `save_config(cfg, out /
    "config.yaml")` -> `save_config(cfg, sorgente / "config.yaml")` in
    `genera_modello`, senza mutare `cfg` -- il testo resta identico ma il
    tempo di modifica del file della madre cambia, e la terza asserzione lo
    nota.
    """
    from meshrec.core.sweep import fingerprint

    cfg = _config_cubo(tmp_path)
    pipeline.run(cfg)
    percorso_madre = cfg.run.out_dir / "config.yaml"
    prima = percorso_madre.read_text(encoding="utf-8")
    mtime_prima = percorso_madre.stat().st_mtime_ns
    impronta = fingerprint(cfg)

    figlia = tmp_path / "figlia"
    pipeline.genera_modello(cfg, "estruso", figlia)

    assert (figlia / "config.yaml").exists()
    assert percorso_madre.read_text(encoding="utf-8") == prima
    assert percorso_madre.stat().st_mtime_ns == mtime_prima, "config.yaml della madre e' stato riscritto"
    assert fingerprint(config.load_config(percorso_madre)) == impronta


def test_generare_un_modello_senza_prior_dice_che_cosa_manca(tmp_path):
    """Mutazione che deve morire: in `genera_modello`, cambiare il messaggio
    dell'eccezione sollevata quando manca `12_wall.json` togliendo il nome
    del file dal testo (per esempio `"manca il prior geometrico"` invece di
    citare `percorso_prior`) -- il `match` sotto smetterebbe di trovarlo."""
    cfg = _config_cubo(tmp_path)
    cfg.run.to_step = 11
    pipeline.run(cfg)

    with pytest.raises(FileNotFoundError, match="12_wall.json"):
        pipeline.genera_modello(cfg, "estruso", tmp_path / "figlia")


def test_una_corsa_senza_export_arriva_al_deck_col_predefinito(tmp_path):
    """Ingresso degenere: una `config.yaml` che il blocco `export` non lo porta.

    E' la forma di ogni corsa nata prima che il blocco esistesse. Il
    predefinito deve bastare a scrivere il deck: un campo obbligatorio qui
    fermerebbe la catena dopo l'intera geometria, al punto di massimo spreco.
    """
    pytest.importorskip("pymeshfix")
    percorso = tmp_path / "senza-export.yaml"
    config.save_config(_config_cubo(tmp_path), percorso)
    testo = percorso.read_text(encoding="utf-8")
    righe = testo.splitlines(keepends=True)
    inizio = next(n for n, riga in enumerate(righe) if riga.startswith("export:"))
    fine = next(
        (n for n in range(inizio + 1, len(righe)) if not righe[n].startswith(" ")),
        len(righe),
    )
    percorso.write_text("".join(righe[:inizio] + righe[fine:]), encoding="utf-8")

    cfg = config.load_config(percorso)
    assert cfg.export.set_tolerance_factor == pytest.approx(6.0)

    cfg.run.to_step = 11
    metriche = pipeline.run(cfg)

    assert (tmp_path / "out" / "wall_model.inp").exists()
    assert metriche["11_export"]["set_tolerance"] > 0.0


def test_il_deck_dello_step_11_e_nudo(tmp_path):
    """Dalla PR 2 del deck nudo la pipeline scrive il solo maglio: nessun
    passo, nessun vincolo, nessuna sezione e nessun materiale nel deck del
    muro. Sezione e materiale si assegnano in Abaqus, sul deck importato."""
    cfg = _config_cubo(tmp_path)
    cfg.run.to_step = 11
    pipeline.run(cfg)
    deck = (tmp_path / "out" / "wall_model.inp").read_text()
    for card in ("*STEP", "*BOUNDARY", "*SOLID SECTION", "*MATERIAL"):
        assert card not in deck


def test_una_config_yaml_vecchia_e_rifiutata_prima_di_scrivere_qualunque_cosa(tmp_path):
    """La catena intera su una `config.yaml` scritta prima del deck nudo.

    `test_config.py` prova che `load_config` rifiuta i blocchi usciti; qui si
    prova la conseguenza che conta per chi lancia una corsa: il rifiuto arriva
    prima di ogni scrittura, e la cartella della corsa non nasce nemmeno. Una
    corsa che partisse e morisse a meta' lascerebbe artefatti parziali di una
    configurazione che il programma ha gia' dichiarato di non saper eseguire.

    I blocchi vecchi sono quelli di `runs/geoandgeo-lab/config.yaml`, con le
    due chiavi laterali a `null` come le scriveva l'interfaccia quando
    restavano vuote: quelle restano ignorate, `carichi:` e `selettori:` no.

    Mutazione che lo uccide: togliere `carichi`/`selettori` da
    `BLOCCHI_RIMOSSI` -- la corsa ripartirebbe e la cartella comparirebbe.
    """
    vecchia = tmp_path / "config.yaml"
    config.save_config(_config_cubo(tmp_path), vecchia)
    # Le due chiavi laterali vanno *dentro* il `model:` gia' scritto: un
    # secondo `model:` in coda sarebbe una chiave omonima, che
    # `_LoaderChiaviUniche` rifiuta prima di arrivare al punto in esame.
    testo = vecchia.read_text(encoding="utf-8").replace(
        "model:\n", "model:\n  lateral_nset: null\n  lateral_pressure: null\n", 1
    )
    vecchia.write_text(
        testo
        + "carichi:\n"
        "  spinta:\n    coefficiente: 0.1\n    asse: y\n"
        "  carico_sommita:\n    risultante: 1200.0\n    nset: TOP\n"
        "  modale: {}\n"
        "selettori:\n"
        "  angolo:\n    tipo: sfera\n    centro: [0.0, 0.0, 0.0]\n    raggio: 5.0\n",
        encoding="utf-8",
    )

    with pytest.raises(ValidationError) as rifiuto:
        config.load_config(vecchia)

    detto = str(rifiuto.value)
    assert "carichi" in detto and "selettori" in detto
    assert not (tmp_path / "out").exists()


# --- Lo step 11 rilegge il prior dello step 12 (#135) -----------------------
#
# Le membrature non esistono allo step 11: `RegioneConfig.membratura` cita per
# costruzione gli indici di `12_wall.json`, che e' l'artefatto dello step 12.
# Lo step 11 lo rilegge invece di ricalcolarlo -- lo stesso mestiere di
# `genera_modello`, e per la stessa ragione: il prior misura la nuvola
# segmentata dello step 2, non il maglio di volume, quindi rileggerlo qui non
# e' leggere il futuro. Il flusso e' arrivare a 12, dichiarare le regioni,
# rieseguire lo step 11.

def _regione(membratura):
    """Una `RegioneConfig`: l'indice del prisma, e nient'altro."""
    return config.RegioneConfig(membratura=membratura)


def test_lo_step_11_rilegge_il_prior_e_porta_l_elset_della_regione_nel_deck(tmp_path):
    """Il prior della corsa gia' fatta diventa i prismi dell'attribuzione.

    La seconda corsa riparte dallo step 9 e si ferma all'11: `12_wall.json` e'
    quello che la prima ha scritto, e lo step 11 lo rilegge invece di
    pretendere membrature che alla sua ora non esistono.

    Il deck che ne esce porta l'`*ELSET` della regione -- il materiale che lo
    riempie si assegna in Abaqus, non qui -- e il resoconto dice quanti
    elementi sono finiti dove.

    Mutazione che deve morire: passare `regioni=None` a `export_model` allo
    step 11, o costruire le regioni senza rileggere il prior.
    """
    cfg = _config_cubo(tmp_path)
    pipeline.run(cfg)
    assert (cfg.run.out_dir / pipeline.WALL_FILENAME).exists()

    cfg.regioni = {"NUCLEO": _regione(0)}
    cfg.run.from_step = 9
    cfg.run.to_step = 11
    metriche = pipeline.run(cfg)

    testo = (cfg.run.out_dir / pipeline.DECK_FILENAME).read_text(encoding="ascii")
    assert "*ELSET, ELSET=NUCLEO" in testo
    assert "*SOLID SECTION" not in testo
    assert "*MATERIAL" not in testo

    resoconto = metriche["11_export"]["regioni"]
    assert resoconto["elementi_per_regione"]["NUCLEO"] > 0
    assert 0.0 <= resoconto["frazione_orfana"] <= 1.0


def test_lo_step_11_senza_il_prior_nomina_lo_step_12_e_il_comando_wall(tmp_path):
    """Regioni dichiarate e nessun `12_wall.json`: la corsa si ferma e dice come.

    Proseguire ignorando le regioni darebbe un deck monomaterico da una
    configurazione che ne dichiara due: e' il silenzio che questo progetto non
    produce. Il rifiuto nomina lo step che scrive il prior e il comando che lo
    calcola da solo, come gia' fa `genera_modello`.

    Mutazione che deve morire: ricadere su `regioni=None` quando il prior
    manca, invece di sollevare.
    """
    cfg = _config_cubo(tmp_path)
    cfg.regioni = {"NUCLEO": _regione(0)}
    cfg.run.to_step = 11

    with pytest.raises(FileNotFoundError) as errore:
        pipeline.run(cfg)

    messaggio = str(errore.value)
    assert pipeline.WALL_FILENAME in messaggio
    assert "step 12" in messaggio
    assert "meshrec wall" in messaggio
    assert not (cfg.run.out_dir / pipeline.DECK_FILENAME).exists()


def test_un_prior_troncato_e_dichiarato_invece_di_valere_come_prior(tmp_path):
    """Un `12_wall.json` a meta' non e' un prior: e' un file che c'e'.

    Senza questa porta l'errore sarebbe quello di `json`, che parla di una
    colonna in un documento e manda a cercare un difetto nel formato invece
    che nella corsa da rifare.

    Mutazione che deve morire: leggere il prior senza `try`, lasciando salire
    `JSONDecodeError` nuda.
    """
    cfg = _config_cubo(tmp_path)
    pipeline.run(cfg)
    percorso = cfg.run.out_dir / pipeline.WALL_FILENAME
    percorso.write_text(percorso.read_text(encoding="utf-8")[:80], encoding="utf-8")

    cfg.regioni = {"NUCLEO": _regione(0)}
    cfg.run.from_step = 9
    cfg.run.to_step = 11

    with pytest.raises(ValueError, match="non si legge"):
        pipeline.run(cfg)


def test_senza_regioni_lo_step_11_non_rilegge_il_prior(tmp_path):
    """Nessuna regione, nessuna rilettura: lo step 11 gira prima del 12.

    E' il vincolo piu' stretto della fase, e qui si misura nel punto in cui si
    romperebbe per primo: una corsa fermata all'11 non ha ancora un
    `12_wall.json`, quindi una rilettura incondizionata la farebbe fallire.

    Mutazione che deve morire: rileggere il prior senza guardare `cfg.regioni`.
    """
    cfg = _config_cubo(tmp_path)
    cfg.run.to_step = 11

    metriche = pipeline.run(cfg)

    assert not (cfg.run.out_dir / pipeline.WALL_FILENAME).exists()
    assert "regioni" not in metriche["11_export"]
    testo = (cfg.run.out_dir / pipeline.DECK_FILENAME).read_text(encoding="ascii")
    assert "*ELSET" not in testo




def test_riprendere_dallo_step_10_non_ritetraedrizza(run_dir, tmp_path, monkeypatch):
    """«Qualità volume» non deve ripagare TetGen per contare gli elementi.

    E' il motivo per cui il tetto di `from_step` si alza: senza la guardia sullo
    step 9, alzarlo soltanto avrebbe reso lo step 10 eseguibile **rifacendo la
    tetraedrizzazione**, cioe' i minuti che la ripresa esiste per non ripagare.
    Su una scansione reale sono decine di secondi per un conteggio che costa
    meno di uno.

    La prova e' osservabile e non temporale: se la tetraedrizzazione parte, il
    sostituto solleva.
    """
    import shutil

    from meshrec.core import volume

    out, _ = run_dir
    copia = tmp_path / "corsa"
    shutil.copytree(out, copia)

    def _non_chiamarmi(*_args, **_kwargs):
        raise AssertionError("lo step 10 non deve ritetraedrizzare")

    monkeypatch.setattr(volume, "tetrahedralize_with_metrics", _non_chiamarmi)

    cfg = config.load_config(copia / "config.yaml")
    cfg.run.out_dir = copia
    cfg.run.from_step = 10
    cfg.run.to_step = 10

    esito = pipeline.run(cfg)
    assert esito["10_volume_quality"]["tets"] > 0


def test_riprendere_dallo_step_11_riscrive_il_deck_dal_maglio_sul_disco(
    run_dir, tmp_path, monkeypatch
):
    """Lo step 11 esporta: rilegge il maglio, non lo rigenera.

    Lo step 11 ha bisogno di due cose che non sono in memoria quando la corsa
    parte da li': il maglio di volume, che rilegge da 09_volume.vtu, e la
    superficie da cui e' nato, che definisce il sistema di riferimento del
    modello (`abaqus.align_to_axes`) e si ricarica con la stessa regola dello
    step 9 -- 08_simplified.ply se la semplificazione e' accesa, altrimenti la
    superficie riparata dello step 6.
    """
    import shutil

    from meshrec.core import volume

    out, _ = run_dir
    copia = tmp_path / "corsa"
    shutil.copytree(out, copia)
    (copia / pipeline.DECK_FILENAME).unlink()

    def _non_chiamarmi(*_args, **_kwargs):
        raise AssertionError("lo step 11 non deve ritetraedrizzare")

    monkeypatch.setattr(volume, "tetrahedralize_with_metrics", _non_chiamarmi)

    cfg = config.load_config(copia / "config.yaml")
    cfg.run.out_dir = copia
    cfg.run.from_step = 11
    cfg.run.to_step = 11

    esito = pipeline.run(cfg)
    assert esito["11_export"]["volume"] > 0
    assert esito["11_export"]["element_type"] == cfg.tet.element
    assert (copia / pipeline.DECK_FILENAME).exists()


def test_riprendere_da_uno_step_di_valle_senza_il_maglio_lo_dichiara(run_dir, tmp_path):
    """Il maglio assente e' un rifiuto che nomina il file, non un KeyError.

    E' la stessa garanzia che `_ingresso_di_ripresa` da' per ogni altro
    artefatto: chi riprende da uno step di valle in una cartella incompleta
    deve leggere quale file manca e quale step lo scrive.
    """
    import shutil

    out, _ = run_dir
    copia = tmp_path / "corsa"
    shutil.copytree(out, copia)
    (copia / pipeline.ARTIFACTS[9]).unlink()

    cfg = config.load_config(copia / "config.yaml")
    cfg.run.out_dir = copia
    cfg.run.from_step = 10
    cfg.run.to_step = 10

    with pytest.raises(ValueError) as caduta:
        pipeline.run(cfg)
    assert "09_volume.vtu" in str(caduta.value)


def test_riprendere_dallo_step_12_calcola_il_prior_senza_ritetraedrizzare(
    run_dir, tmp_path, monkeypatch
):
    """Lo step 12 è l'ultimo punto di ripresa, e il suo ingresso non è come gli altri.

    Gli step 10 e 11 leggono il maglio di volume; il prior geometrico legge la
    nuvola segmentata dello step 2, che nessuno degli altri due chiede. È
    l'ingresso che rende questa ripresa diversa dalle sue vicine, e il motivo
    per cui provarle non prova questa: una corsa che riparte dal 12 deve
    ricaricare `02_segmented.ply` e non deve ripagare TetGen per farlo.

    La prova è osservabile e non temporale, come per gli step 10 e 11: se la
    tetraedrizzazione parte, il sostituto solleva.
    """
    import shutil

    from meshrec.core import volume

    out, _ = run_dir
    copia = tmp_path / "corsa"
    shutil.copytree(out, copia)
    (copia / pipeline.WALL_FILENAME).unlink()

    def _non_chiamarmi(*_args, **_kwargs):
        raise AssertionError("lo step 12 non deve ritetraedrizzare")

    monkeypatch.setattr(volume, "tetrahedralize_with_metrics", _non_chiamarmi)

    cfg = config.load_config(copia / "config.yaml")
    cfg.run.out_dir = copia
    cfg.run.from_step = 12
    cfg.run.to_step = 12

    esito = pipeline.run(cfg)
    assert esito["12_wall"]
    assert (copia / pipeline.WALL_FILENAME).exists()


def test_riprendere_da_valle_con_la_semplificazione_accesa_rilegge_lo_step_8(tmp_path):
    """La regola che sceglie la superficie a monte vale per tutti gli step di valle.

    `test_resuming_from_tetrahedralize_still_works_when_simplify_is_enabled`
    prova che la ripresa dal 9 riesce, non da quale artefatto: con la
    superficie riparata dello step 6 ancora sul disco, riesce comunque.
    Misurato il 31/08/2026 sostituendo `resume_from = 8 if
    cfg.simplify.enabled else 6` con `resume_from = 6`: tutti e 75 i test di
    questo file restano verdi.

    Qui la superficie dello step 6 non c'è più, quindi l'unico artefatto che
    può soddisfare la ripresa è `08_simplified.ply`, e la ripresa è da uno step
    di valle -- l'11, che la pretende perché è la superficie, e non i nodi del
    volume, a definire il sistema di riferimento del modello.
    """
    pytest.importorskip("pymeshfix")
    cloud_path = tmp_path / "box.ply"
    io.write_cloud(cloud_path, synth.sample_box_surface(SIZE, SPACING))

    def makecfg(from_step, to_step):
        return config.PipelineConfig(
            input=config.InputConfig(path=cloud_path, spacing_sample=5000),
            downsample=config.DownsampleConfig(voxel_size=SPACING),
            surface=config.SurfaceConfig(poisson_depth=8, density_quantile=0.02),
            simplify=config.SimplifyConfig(enabled=True, remesh_target_len_pct=2.0),
            run=config.RunConfig(
                out_dir=tmp_path / "out", from_step=from_step, to_step=to_step
            ),
        )

    pipeline.run(makecfg(1, 12))
    corsa = tmp_path / "out"
    assert (corsa / pipeline.ARTIFACTS[8]).exists()
    (corsa / pipeline.ARTIFACTS[6]).unlink()
    (corsa / pipeline.DECK_FILENAME).unlink()

    ripresa = pipeline.run(makecfg(11, 11))
    assert ripresa["11_export"]["volume"] == pytest.approx(EXACT_VOLUME, rel=0.1)
    assert (corsa / pipeline.DECK_FILENAME).exists()
