"""Step 1: caricamento, filtro dei non finiti, spaziatura, scala."""

import ast
import json
from pathlib import Path

import numpy as np
import pytest

from meshrec.core import config, io, steps, sweep, synth

SIZE = (100.0, 40.0, 200.0)
SPACING = 10.0


def _write_ply(path, points):
    open3d = pytest.importorskip("open3d")
    cloud = open3d.geometry.PointCloud(open3d.utility.Vector3dVector(np.asarray(points)))
    open3d.io.write_point_cloud(str(path), cloud)


def test_mean_spacing_matches_a_regular_grid():
    points = synth.sample_box_surface(SIZE, SPACING)
    assert io.mean_spacing(points, sample=5000, seed=0) == pytest.approx(SPACING, rel=0.2)


def test_non_finite_points_are_dropped_and_counted(tmp_path):
    points = synth.sample_box_surface(SIZE, SPACING)
    dirty = np.vstack([points, [[np.nan, 0.0, 0.0], [np.inf, 1.0, 2.0]]])
    path = tmp_path / "sporca.ply"
    _write_ply(path, dirty)

    loaded, metrics = io.load_cloud(config.InputConfig(path=path))

    assert metrics["points_dropped"] == 2
    assert metrics["points_kept"] == len(loaded) == len(points)
    assert np.isfinite(loaded).all()


def test_scale_factor_converts_the_extent(tmp_path):
    """Nuvola in metri: scale=1000 la porta in mm e l'ingombro lo dimostra."""
    points = synth.sample_box_surface(SIZE, SPACING) / 1000.0
    path = tmp_path / "metri.ply"
    _write_ply(path, points)

    _, metrics = io.load_cloud(config.InputConfig(path=path, scale=1000.0))

    assert metrics["extent"] == pytest.approx(SIZE, rel=1e-3)


def test_extent_far_from_expected_size_raises(tmp_path):
    """La difesa contro l'errore di unita: silenzioso e di ordini di grandezza."""
    points = synth.sample_box_surface(SIZE, SPACING) / 1000.0
    path = tmp_path / "metri.ply"
    _write_ply(path, points)

    with pytest.raises(io.ScaleError, match="ingombro"):
        io.load_cloud(config.InputConfig(path=path, scale=1.0, expected_size=SIZE))


def test_expected_size_is_satisfied_when_scale_is_right(tmp_path):
    points = synth.sample_box_surface(SIZE, SPACING) / 1000.0
    path = tmp_path / "metri.ply"
    _write_ply(path, points)

    _, metrics = io.load_cloud(
        config.InputConfig(path=path, scale=1000.0, expected_size=SIZE)
    )

    assert metrics["size_check"] == "ok"


def test_too_many_points_raises(tmp_path):
    points = synth.sample_box_surface(SIZE, SPACING)
    path = tmp_path / "nuvola.ply"
    _write_ply(path, points)

    with pytest.raises(ValueError, match="max_points"):
        io.load_cloud(config.InputConfig(path=path, max_points=10))


def test_cloud_round_trip_preserves_points_and_normals(tmp_path):
    points = synth.sample_box_surface(SIZE, SPACING)
    normals = np.tile([0.0, 0.0, 1.0], (len(points), 1))
    path = tmp_path / "con_normali.ply"

    io.write_cloud(path, points, normals)
    back, back_normals = io.read_cloud(path)

    assert back == pytest.approx(points, abs=1e-3)
    assert back_normals == pytest.approx(normals, abs=1e-3)


def test_missing_file_raises_with_message(tmp_path):
    """open3d.io.read_point_cloud non solleva su file assente: va controllato a mano."""
    path = tmp_path / "assente.ply"

    with pytest.raises(ValueError, match="nessun punto letto"):
        io.load_cloud(config.InputConfig(path=path))


def test_all_points_non_finite_raises_with_message(tmp_path):
    """Se il filtro dei non finiti svuota la nuvola, l'errore deve dirlo esplicitamente."""
    points = np.full((5, 3), np.nan)
    path = tmp_path / "tutta_non_finita.ply"
    _write_ply(path, points)

    with pytest.raises(ValueError, match="coordinate non finite"):
        io.load_cloud(config.InputConfig(path=path))


def _sorgenti_del_pacchetto() -> list[Path]:
    radice = Path(__file__).resolve().parent.parent / "src" / "meshrec"
    sorgenti = sorted(radice.rglob("*.py"))
    assert sorgenti, f"nessun sorgente sotto {radice}: il controllo sorveglierebbe il nulla"
    return sorgenti


def _nome_puntato(nodo: ast.expr) -> str:
    """`json.JSONDecodeError` da un albero, senza valutarlo."""
    if isinstance(nodo, ast.Attribute):
        return f"{_nome_puntato(nodo.value)}.{nodo.attr}"
    if isinstance(nodo, ast.Name):
        return nodo.id
    return ""


def test_nessuna_guardia_cattura_json_decode_error_al_posto_di_value_error():
    """`json.JSONDecodeError` come tipo catturato e' sempre un difetto, qui.

    E' una SOTTOCLASSE di `ValueError`, e sorella di `UnicodeDecodeError`: chi
    scrive `except json.JSONDecodeError` sta scrivendo «il file e' troncato» e
    lascia passare «il file e' storto», cioe' un byte che non e' UTF-8. Quel
    byte la lettura lo solleva PRIMA del parse, quindi la guardia non lo vede
    nemmeno arrivare.

    Non e' un caso di scuola. Il guasto di codifica del 25/08/2026 e' arrivato
    da un tubo che non dichiarava le proprie codifiche, e ha lasciato dietro
    l'osservazione che le stesse tre righe stavano anche qui. Su un artefatto
    scritto storto, una guardia che dichiara di coprire l'illeggibile e non lo
    copre non fallisce dove sta scritta: fa saltare il chiamante.

    Il controllo e' STRUTTURALE e non per sito, e questa e' la ragione: il
    difetto era gia' stato trovato e chiuso UNA VOLTA, in
    `core/report.py::_legge_json` (che infatti cattura `ValueError` e lo
    motiva), e i tre fratelli erano rimasti aperti. Un controllo per sito
    avrebbe chiuso i tre e lasciato passare il quarto che verra'.

    Non impone di catturare qualcosa: chi vuole SOLLEVARE su un artefatto
    corrotto -- ed e' la scelta giusta per il prior e per il registro degli
    sweep, che sono dati di tesi -- semplicemente non scrive un `except`.
    Questo controllo parla solo di chi la guardia ce l'ha gia'.

    Mutazione che lo uccide: rimettere `json.JSONDecodeError` in una qualunque
    delle tre guardie (`core/steps.py`, `core/sweep.py`, `core/pipeline.py`).
    """
    colpevoli: list[str] = []
    for sorgente in _sorgenti_del_pacchetto():
        albero = ast.parse(sorgente.read_text(encoding="utf-8"), filename=str(sorgente))
        for nodo in ast.walk(albero):
            if not isinstance(nodo, ast.ExceptHandler) or nodo.type is None:
                continue
            catturati = (
                nodo.type.elts if isinstance(nodo.type, ast.Tuple) else [nodo.type]
            )
            for tipo in catturati:
                if _nome_puntato(tipo).endswith("JSONDecodeError"):
                    colpevoli.append(f"{sorgente.name}:{nodo.lineno}")

    assert colpevoli == [], (
        "guardie che dicono «troncato» e non coprono «storto» "
        f"(usa ValueError, che le comprende entrambe): {colpevoli}"
    )


def test_uno_stato_scritto_storto_vale_come_stato_assente(tmp_path):
    """Un `steps.json` con un byte non UTF-8 non deve far saltare la rilettura.

    La guardia dichiarava «uno stato illeggibile e' uno stato assente», ed e' il
    contratto giusto: tutti gli step tornano «mai eseguito», che e' pessimista e
    mai falsamente rassicurante. Ma copriva il solo troncamento. Un byte storto
    -- `0xE0`, cioe' `à` scritto in cp1252 -- solleva `UnicodeDecodeError` alla
    lettura, prima del parse, e scavalcava la guardia: la colonna degli step
    smetteva di disegnarsi invece di mostrarli tutti da rifare.

    Mutazione che lo uccide: rimettere `json.JSONDecodeError` al posto di
    `ValueError` in `read_state`.
    """
    (tmp_path / "steps.json").write_bytes(b'{"1": {"esito": "citt\xe0"}}')

    assert steps.read_state(tmp_path) == {}


def test_metriche_scritte_storte_non_fermano_la_raccolta_di_uno_sweep(tmp_path):
    """Uno sweep non deve fermarsi tutto per un candidato scritto storto.

    `leggi_metriche` prova `metrics.json` e poi il parziale: la guardia esiste
    perche' un processo ucciso lascia il primo a meta'. Con un byte non UTF-8 la
    lettura sollevava invece di passare al successivo, e siccome gli sweep
    girano i candidati in parallelo quel guasto non scartava UN candidato:
    fermava la raccolta di tutti.

    Il parziale qui e' scritto BENE apposta: si misura che la guardia lasci
    proseguire, non solo che non sollevi. Con un solo file storto un `return {}`
    frettoloso passerebbe lo stesso.

    Mutazione che lo uccide: rimettere `json.JSONDecodeError` al posto di
    `ValueError` in `leggi_metriche`.
    """
    (tmp_path / sweep.METRICS_FILENAME).write_bytes(b'{"nodi": "citt\xe0"}')
    (tmp_path / sweep.METRICS_PARTIAL).write_text(
        json.dumps({"nodi": 14103}), encoding="utf-8"
    )

    assert sweep.leggi_metriche(tmp_path) == {"nodi": 14103}


# Percorsi con accenti. Il rosso vero e' solo su Windows: Open3D converte il
# percorso alla code page ANSI (`fs::path::string()`) e poi stampa i suoi avvisi
# con `py::print`, che decodifica UTF-8. Su macOS/Linux restano verdi.
ACCENTATI = ["Rilievo_città", "Łódź_rilievo"]


@pytest.mark.parametrize("cartella", ACCENTATI)
@pytest.mark.parametrize("estensione", io.ESTENSIONI_NUVOLA)
def test_una_nuvola_in_una_cartella_accentata_si_legge(tmp_path, cartella, estensione):
    points = synth.sample_box_surface(SIZE, SPACING)
    ascii_path = tmp_path / f"nuvola{estensione}"
    _write_ply(ascii_path, points)
    accentato = tmp_path / cartella / f"più_nuvola{estensione}"
    accentato.parent.mkdir()
    accentato.write_bytes(ascii_path.read_bytes())

    letti, _ = io.read_cloud(accentato)

    assert letti == pytest.approx(io.read_cloud(ascii_path)[0])


@pytest.mark.parametrize("cartella", ACCENTATI)
def test_una_nuvola_accentata_assente_dice_il_messaggio_del_programma(tmp_path, cartella):
    percorso = tmp_path / cartella / "città.ply"

    with pytest.raises(ValueError, match="nessun punto letto") as errore:
        io.read_cloud(percorso)

    assert str(percorso) in str(errore.value)


@pytest.mark.parametrize("cartella", ACCENTATI)
def test_una_nuvola_scritta_in_una_corsa_accentata_si_rilegge(tmp_path, cartella):
    points = synth.sample_box_surface(SIZE, SPACING)
    percorso = tmp_path / cartella / "01_cloud.ply"

    io.write_cloud(percorso, points)

    assert io.read_cloud(percorso)[0] == pytest.approx(points, abs=1e-3)


@pytest.mark.parametrize("cartella", ACCENTATI)
def test_una_mesh_scritta_in_una_corsa_accentata_si_rilegge(tmp_path, cartella):
    from meshrec.core import pipeline

    vertici = np.array([[0.0, 0.0, 0.0], [1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]])
    facce = np.array([[0, 1, 2], [0, 1, 3], [0, 2, 3], [1, 2, 3]])
    percorso = tmp_path / cartella / "06_repaired.ply"

    pipeline._write_mesh(percorso, vertici, facce)
    letti, lette = pipeline._read_mesh(percorso)

    assert letti == pytest.approx(vertici)
    assert (lette == facce).all()
