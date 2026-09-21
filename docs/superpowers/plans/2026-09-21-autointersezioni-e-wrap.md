# Autointersezioni e alpha wrap allo step 9 — piano d'implementazione

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** lo step 9 conta e pulisce le autointersezioni prima di TetGen, e a richiesta dell'utente sostituisce la superficie con un alpha wrap entro una tolleranza in mm.

**Architecture:** un modulo nuovo `core/autointersezioni.py` con quattro primitive (conta, pulisci, avvolgi, spostamento) e un orchestratore `prepara_ingresso`; `pipeline.py` lo chiama prima di `volume.tetrahedralize_with_metrics` e rimisura l'errore geometrico se la superficie è cambiata dopo lo step 7. Un campo nuovo `TetConfig.wrap_tolerance`, fuori dall'impronta di candidato quando vale `None`.

**Tech Stack:** Python 3.12, pymeshlab 2025.7.post1, pymeshfix 0.18.1, tetgen 0.8.4, pydantic, pytest.

**Spec:** `docs/superpowers/specs/2026-09-21-autointersezioni-e-wrap-design.md`

## Global Constraints

- Python ≥3.12 e <3.13; nessuna dipendenza nuova (pymeshlab e pymeshfix già in `meshrec/pyproject.toml:13-14`).
- Unità di lavoro: mm (`core/config.py:3`).
- Nessun predefinito di elaborazione fuori da `core/config.py` (`volume.py:143-150`).
- `wrap_tolerance` predefinito `None` = spento; nessun valore suggerito.
- Tutti i comandi da `/Users/mario/GitHub/Tesi/meshrec` con `uv run`; percorsi assoluti, un comando per chiamata.
- Suite onesta prima del commit finale: `uv run pytest -m "" -q` con `node` e `ccx` sul PATH (AGENTS.md, «Il verde che mente»).
- Messaggi all'utente in italiano con gli accenti; commenti nello stile del file che si tocca.

## File

- Create: `meshrec/src/meshrec/core/autointersezioni.py` — primitive + orchestratore dello step 9.
- Create: `meshrec/tests/test_autointersezioni.py`
- Modify: `meshrec/src/meshrec/core/config.py:275-340` — campo `wrap_tolerance` in `TetConfig`.
- Modify: `meshrec/src/meshrec/core/sweep.py:91-113` — campi nulli fuori impronta.
- Modify: `meshrec/src/meshrec/core/volume.py:101-108` — diagnosi di `recoversubface`.
- Modify: `meshrec/src/meshrec/core/pipeline.py:652-690, 777-783` — chiamata e rimisura.
- Modify: `meshrec/tests/test_config.py`, `meshrec/tests/test_volume.py`, `meshrec/tests/test_pipeline.py`
- Modify: `CHANGELOG.md` — voce in `[Unreleased]`.

## Fatti misurati che il piano usa (sonde del 21/09/2026, HEAD `2cb1b18`)

- `compute_selection_by_self_intersections_per_face` + `current_mesh().selected_face_number()` funzionano.
- `pymeshfix.PyTMesh()`: `load_array(V, F)`, `clean(max_iters=10, inner_loops=3) -> bool`, `return_arrays() -> (V, F)`.
- Sfera `open3d.create_sphere(radius=50, resolution=20)` con il vertice di z massima spostato a `[0, 0, -70]`: **80** facce autointersecanti su 1520; `clean` → `True`, 0 residue, 1516 facce.
- Due cubi compenetrati: `clean` rende `True` ma lascia 7 vertici e 10 facce. **Non usarli come superficie di prova.**
- `generate_alpha_wrap(alpha=PercentageValue, offset=PercentageValue)`; percentuali della diagonale del riquadro.
- `get_hausdorff_distance`: predefiniti `sampleface=False`, `samplenum` = 3 su un triangolo, `maxdist` = 50 % della diagonale. Vanno passati espliciti.
- Wrap con `alpha = tol`, `offset = tol/10`:
  - sfera pulita, tol 5 → 2412 facce, 0,09 s, spostamento max 0,500 mm, TetGen ok;
  - sfera col polo passante, tol 5 → spostamento ingresso→wrap **30,23 mm**, TetGen ok;
  - sfera col polo passante, tol 2 → 5,01 mm; tol 0,5 → 0,33 mm ma 232 630 facce, 506 autointersezioni residue, 15 s, TetGen ok.

---

### Task 1: campo `wrap_tolerance` fuori dall'impronta di candidato

**Files:**
- Modify: `meshrec/src/meshrec/core/config.py` (dentro `class TetConfig`, dopo `nobisect`)
- Modify: `meshrec/src/meshrec/core/sweep.py:91-113`
- Test: `meshrec/tests/test_config.py`

**Interfaces:**
- Produces: `TetConfig.wrap_tolerance: float | None`; `sweep.CAMPI_NULLI_FUORI_IMPRONTA: tuple[tuple[str, str], ...]`.

Perché: aggiungere un campo sposta `sweep.fingerprint` di tutte le 22 righe dei registri d'esperimento (memoria «togliere un campo sposta l'impronta»; guardia `tests/test_config.py:216-224`). Il precedente è `BLOCCHI_VUOTI_FUORI_IMPRONTA` (`sweep.py:91`) per i blocchi; qui lo stesso per un campo. La catena degli step (`steps.step_fingerprints`) invece si sposta **una volta** dagli step 9-12, come già accettato per `regioni` (`sweep.py:80-90`).

## Ingressi degeneri
- `wrap_tolerance=0` → `ValidationError` di pydantic, non accettato.
- `wrap_tolerance=-1` → `ValidationError`.
- `wrap_tolerance` assente nel YAML → `None`, e `sweep.fingerprint` identica a prima del campo.
- `wrap_tolerance=5.0` → `sweep.fingerprint` diversa da quella con `None`.

- [ ] **Step 1: test che falliscono** — in `tests/test_config.py`:

```python
def test_wrap_tolerance_e_spento_e_rifiuta_i_valori_non_positivi():
    assert config.TetConfig().wrap_tolerance is None
    for sbagliato in (0.0, -1.0):
        with pytest.raises(pydantic.ValidationError):
            config.TetConfig(wrap_tolerance=sbagliato)


def test_wrap_tolerance_acceso_sposta_l_impronta_di_candidato():
    from meshrec.core.sweep import fingerprint

    base = config.PipelineConfig(input=config.InputConfig(path="nuvola.ply"))
    acceso = base.model_copy(update={"tet": config.TetConfig(wrap_tolerance=5.0)})
    assert fingerprint(acceso) != fingerprint(base)
```

Che il campo spento **non** sposti l'impronta lo prova gia' la guardia sull'aggregato delle 22 righe (`test_config.py:216-224`) e quelle sui casi (`:230-232`): con il campo nel dump vanno rosse, senza restano verdi. Non riscriverne una copia.

- [ ] **Step 2: lancia e verifica il rosso**

Run: `uv run --directory /Users/mario/GitHub/Tesi/meshrec pytest tests/test_config.py -k wrap_tolerance -q`
Expected: FAIL: `TetConfig` rifiuta il campo sconosciuto o non lo ha.

- [ ] **Step 3: campo** — in `TetConfig`, dopo `nobisect`:

```python
    wrap_tolerance: float | None = Field(
        default=None,
        gt=0.0,
        title="spostamento ammesso dal ripiego alpha wrap [mm]",
        description=(
            "Vuoto = spento. Acceso, lo step 9 sostituisce la superficie con un "
            "alpha wrap di CGAL prima di TetGen: serve quando TetGen si ferma nel "
            "recupero del bordo (recoversubfaces). La superficie non viene "
            "riparata ma rifatta: il volume cresce dell'offset e le cavità più "
            "strette della tolleranza spariscono. Se lo spostamento misurato "
            "supera questo valore lo step fallisce. Vedi "
            "docs/ricerca/2026-09-21-autointersezioni-e-degeneri.md §5.1"
        ),
    )
```

- [ ] **Step 4: impronta** — in `sweep.py`, dopo `BLOCCHI_VUOTI_FUORI_IMPRONTA`:

```python
# Campi aggiunti dopo che i registri d'esperimento erano stati scritti: finche'
# valgono None non cambiano l'elaborazione, e metterli nel dump scollegherebbe
# le 22 righe gia' registrate (tests/test_config.py). Stessa regola di
# BLOCCHI_VUOTI_FUORI_IMPRONTA, un livello piu' giu'. Come quella, vale per
# l'impronta di candidato e non per la catena degli step.
CAMPI_NULLI_FUORI_IMPRONTA: tuple[tuple[str, str], ...] = (("tet", "wrap_tolerance"),)
```

e in `fingerprint`, dopo il ciclo su `BLOCCHI_VUOTI_FUORI_IMPRONTA`:

```python
    for blocco, campo in CAMPI_NULLI_FUORI_IMPRONTA:
        if (payload.get(blocco) or {}).get(campo, 0) is None:
            payload[blocco].pop(campo)
```

- [ ] **Step 5: verde, guardie comprese**

Run: `uv run --directory /Users/mario/GitHub/Tesi/meshrec pytest tests/test_config.py tests/test_steps.py tests/test_sweep.py -q`
Expected: PASS, compresi l'aggregato delle 22 righe (`test_config.py:221`) e le impronte dei casi (`test_config.py:230-232`) **senza** toccarne i valori. Se una di quelle guardie va rossa, fermati: vuol dire che il campo entra ancora nell'impronta.

- [ ] **Step 6: commit**

```bash
git -C /Users/mario/GitHub/Tesi add meshrec/src/meshrec/core/config.py meshrec/src/meshrec/core/sweep.py meshrec/tests/test_config.py
git -C /Users/mario/GitHub/Tesi commit -m "feat(config): tet.wrap_tolerance, fuori impronta quando spento"
```

---

### Task 2: primitive in `core/autointersezioni.py`

**Files:**
- Create: `meshrec/src/meshrec/core/autointersezioni.py`
- Test: `meshrec/tests/test_autointersezioni.py`

**Interfaces:**
- Produces:
  - `conta_autointersezioni(vertices: np.ndarray, faces: np.ndarray) -> int`
  - `pulisci_autointersezioni(vertices, faces) -> tuple[np.ndarray, np.ndarray, bool]` (il `bool` è il ritorno di `PyTMesh.clean`)
  - `avvolgi(vertices, faces, tolleranza: float) -> tuple[np.ndarray, np.ndarray, dict[str, float]]` (dict: `wrap_alpha_mm`, `wrap_offset_mm`, `wrap_seconds`)
  - `spostamento(va, fa, vb, fb) -> dict[str, float]` (chiavi `max_a_verso_b`, `max_b_verso_a`, `max`, `mean`)

## Ingressi degeneri
- superficie senza facce → `conta_autointersezioni` rende 0, non solleva; `avvolgi` solleva `ValueError` che dice «superficie senza facce».
- superficie pulita (sfera) → conteggio 0; `pulisci` rende la superficie con lo stesso numero di facce e `True`.
- sfera col polo passante → conteggio 80; dopo `pulisci` 0 e `True`.
- wrap che esce vuoto → `ValueError` «l'alpha wrap non ha prodotto facce», niente TetGen.
- `tolleranza` ≤ 0 passata direttamente → `ValueError` (la config la blocca già, qui difesa per chi chiama la funzione a mano).
- due superfici identiche → `spostamento` rende `max` 0 (entro 1e-9).

- [ ] **Step 1: test che falliscono** — `tests/test_autointersezioni.py`:

```python
import numpy as np
import open3d as o3d
import pytest

from meshrec.core import autointersezioni as ai


def _sfera(polo: tuple[float, float, float] | None = None):
    """Sfera di raggio 50 mm; `polo` sposta il vertice piu' alto.

    Con polo a (0, 0, -70) il vertice attraversa la calotta opposta: 80 facce
    autointersecanti su 1520, misurato il 21/09/2026. Due cubi compenetrati NON
    servono: MeshFix li riduce a 7 vertici dichiarando successo.
    """
    sfera = o3d.geometry.TriangleMesh.create_sphere(radius=50.0, resolution=20)
    v = np.asarray(sfera.vertices).copy()
    f = np.asarray(sfera.triangles).astype(np.int64)
    if polo is not None:
        v[int(np.argmax(v[:, 2]))] = polo
    return v, f


def test_la_sfera_pulita_non_ha_autointersezioni():
    assert ai.conta_autointersezioni(*_sfera()) == 0


def test_il_polo_passante_si_conta():
    assert ai.conta_autointersezioni(*_sfera((0.0, 0.0, -70.0))) == 80


def test_la_superficie_vuota_non_ha_autointersezioni():
    assert ai.conta_autointersezioni(np.zeros((0, 3)), np.zeros((0, 3), dtype=np.int64)) == 0


def test_meshfix_toglie_il_polo_passante_e_lo_dichiara():
    v, f, convergito = ai.pulisci_autointersezioni(*_sfera((0.0, 0.0, -70.0)))
    assert convergito is True
    assert ai.conta_autointersezioni(v, f) == 0
    assert len(f) > 1400  # non ha svuotato la sfera


def test_il_wrap_della_sfera_pulita_sposta_quanto_l_offset():
    v, f = _sfera()
    wv, wf, misure = ai.avvolgi(v, f, 5.0)
    assert len(wf) > 0
    assert misure["wrap_alpha_mm"] == pytest.approx(5.0)
    assert misure["wrap_offset_mm"] == pytest.approx(0.5)
    assert ai.spostamento(v, f, wv, wf)["max"] == pytest.approx(0.5, abs=0.05)


def test_il_wrap_rifiuta_superficie_vuota_e_tolleranza_non_positiva():
    with pytest.raises(ValueError, match="senza facce"):
        ai.avvolgi(np.zeros((0, 3)), np.zeros((0, 3), dtype=np.int64), 5.0)
    with pytest.raises(ValueError, match="tolleranza"):
        ai.avvolgi(*_sfera(), 0.0)


def test_due_superfici_identiche_non_si_spostano():
    v, f = _sfera()
    assert ai.spostamento(v, f, v, f)["max"] == pytest.approx(0.0, abs=1e-9)
```

- [ ] **Step 2: rosso**

Run: `uv run --directory /Users/mario/GitHub/Tesi/meshrec pytest tests/test_autointersezioni.py -q`
Expected: FAIL, `ModuleNotFoundError: meshrec.core.autointersezioni`.

- [ ] **Step 3: implementazione** — `src/meshrec/core/autointersezioni.py`:

```python
"""Autointersezioni della superficie prima di TetGen, e il ripiego che la rifà.

Lo step 8 le crea (646 facce dopo il remeshing, 7747 dopo Taubin, misurato su
runs/geoandgeo-mm) e TetGen le scopre solo fermandosi in `recoversubfaces`.
Vedi docs/ricerca/2026-09-21-autointersezioni-e-degeneri.md.
"""

from __future__ import annotations

import time

import numpy as np


def _mesh_set(vertices: np.ndarray, faces: np.ndarray):
    import pymeshlab

    mesh_set = pymeshlab.MeshSet()
    mesh_set.add_mesh(
        pymeshlab.Mesh(np.asarray(vertices, dtype=np.float64), np.asarray(faces, dtype=np.int32))
    )
    return mesh_set


def conta_autointersezioni(vertices: np.ndarray, faces: np.ndarray) -> int:
    """Facce che ne intersecano un'altra, per PyMeshLab (3-7 s su 1-4 M triangoli)."""
    if len(faces) == 0:
        return 0
    mesh_set = _mesh_set(vertices, faces)
    mesh_set.apply_filter("compute_selection_by_self_intersections_per_face")
    return int(mesh_set.current_mesh().selected_face_number())


def pulisci_autointersezioni(
    vertices: np.ndarray, faces: np.ndarray
) -> tuple[np.ndarray, np.ndarray, bool]:
    """Il ciclo di MeshFix che `repair.py` chiama gia', ma leggendone l'esito.

    `MeshFix.repair()` chiama `clean()` e ne scarta il bool
    (docs/ricerca/fonti/pymeshfix-meshfix-py.md:431). Qui si chiama `clean`
    direttamente. Il tetto 10/3 e' il predefinito della libreria: sulla
    superficie reale ha raggiunto lo zero al quinto giro esterno.
    """
    import pymeshfix

    maglia = pymeshfix.PyTMesh()
    maglia.load_array(np.asarray(vertices, dtype=np.float64), np.asarray(faces, dtype=np.int32))
    convergito = bool(maglia.clean(max_iters=10, inner_loops=3))
    v, f = maglia.return_arrays()
    return (
        np.ascontiguousarray(v, dtype=np.float64),
        np.ascontiguousarray(f, dtype=np.int64),
        convergito,
    )


def avvolgi(
    vertices: np.ndarray, faces: np.ndarray, tolleranza: float
) -> tuple[np.ndarray, np.ndarray, dict[str, float]]:
    """Alpha wrap di CGAL (dentro PyMeshLab): una superficie nuova, non riparata.

    alpha = tolleranza, offset = alpha/10: il manuale CGAL vuole l'offset una
    piccola frazione di alpha (fonti/cgal-alpha-wrap-3-manual.md:111). La wheel
    installata vuole percentuali della diagonale, non millimetri.
    """
    import pymeshlab

    if len(faces) == 0:
        raise ValueError("superficie senza facce: non c'è nulla da avvolgere")
    if not tolleranza > 0.0:
        raise ValueError(f"tolleranza del wrap {tolleranza}: deve essere positiva, in mm")
    mesh_set = _mesh_set(vertices, faces)
    diagonale = float(mesh_set.current_mesh().bounding_box().diagonal())
    offset = tolleranza / 10.0
    avvio = time.perf_counter()
    mesh_set.apply_filter(
        "generate_alpha_wrap",
        alpha=pymeshlab.PercentageValue(100.0 * tolleranza / diagonale),
        offset=pymeshlab.PercentageValue(100.0 * offset / diagonale),
    )
    secondi = time.perf_counter() - avvio
    avvolta = mesh_set.current_mesh()
    wv = np.ascontiguousarray(avvolta.vertex_matrix(), dtype=np.float64)
    wf = np.ascontiguousarray(avvolta.face_matrix(), dtype=np.int64)
    if len(wf) == 0:
        raise ValueError(
            f"l'alpha wrap non ha prodotto facce con tolleranza {tolleranza} mm"
        )
    return wv, wf, {"wrap_alpha_mm": tolleranza, "wrap_offset_mm": offset, "wrap_seconds": secondi}


def spostamento(
    va: np.ndarray, fa: np.ndarray, vb: np.ndarray, fb: np.ndarray
) -> dict[str, float]:
    """Hausdorff nei due versi fra due superfici, campionando vertici e facce.

    I predefiniti di `get_hausdorff_distance` campionano 3 punti e tagliano
    oltre il 50 % della diagonale: qui sono espliciti. Un campione per faccia.
    """
    import pymeshlab

    mesh_set = _mesh_set(va, fa)
    mesh_set.add_mesh(
        pymeshlab.Mesh(np.asarray(vb, dtype=np.float64), np.asarray(fb, dtype=np.int32))
    )
    versi = {}
    for nome, campionata, bersaglio, facce in (
        ("max_a_verso_b", 0, 1, len(fa)),
        ("max_b_verso_a", 1, 0, len(fb)),
    ):
        versi[nome] = dict(
            mesh_set.apply_filter(
                "get_hausdorff_distance",
                sampledmesh=campionata,
                targetmesh=bersaglio,
                samplevert=True,
                sampleface=True,
                samplenum=int(facce),
                maxdist=pymeshlab.PercentageValue(100.0),
            )
        )
    return {
        "max_a_verso_b": float(versi["max_a_verso_b"]["max"]),
        "max_b_verso_a": float(versi["max_b_verso_a"]["max"]),
        "max": max(float(r["max"]) for r in versi.values()),
        "mean": max(float(r["mean"]) for r in versi.values()),
    }
```

- [ ] **Step 4: verde**

Run: `uv run --directory /Users/mario/GitHub/Tesi/meshrec pytest tests/test_autointersezioni.py -q`
Expected: 7 passed. Se il conteggio del polo passante non è 80, **non** cambiare l'atteso a occhio: rimisuralo e scrivi nel docstring di `_sfera` il valore nuovo con la data.

- [ ] **Step 5: commit**

```bash
git -C /Users/mario/GitHub/Tesi add meshrec/src/meshrec/core/autointersezioni.py meshrec/tests/test_autointersezioni.py
git -C /Users/mario/GitHub/Tesi commit -m "feat(autointersezioni): conta, pulisci, avvolgi, spostamento"
```

---

### Task 3: orchestratore `prepara_ingresso`

**Files:**
- Modify: `meshrec/src/meshrec/core/autointersezioni.py`
- Test: `meshrec/tests/test_autointersezioni.py`

**Interfaces:**
- Consumes: le quattro primitive del Task 2; `TetConfig.wrap_tolerance` (Task 1).
- Produces:
  - `class AutointersezioniResidueError(ValueError)`
  - `class WrapOltreTolleranzaError(ValueError)`
  - `prepara_ingresso(vertices, faces, cfg: TetConfig, *, step_8_acceso: bool) -> tuple[np.ndarray, np.ndarray, dict[str, object], bool]` — l'ultimo `bool` dice se la superficie è cambiata.

Metriche prodotte (chiavi esatte): `self_intersections_before`, `self_intersections_after`, `meshfix_clean_converged` (`None` se non partito), `triangles_removed_by_clean`, `wrap_applied`; col wrap anche `wrap_alpha_mm`, `wrap_offset_mm`, `wrap_seconds`, `wrap_hausdorff_max_mm`, `wrap_hausdorff_mean_mm`, `wrap_volume_before`, `wrap_volume_after`, `wrap_note`.

## Ingressi degeneri
- superficie pulita, wrap spento → stessi array in uscita, `cambiata=False`, `meshfix_clean_converged=None`, `self_intersections_before=0`.
- polo passante, wrap spento → pulita, `self_intersections_after=0`, `meshfix_clean_converged=True`, `cambiata=True`.
- `clean` che rende `False` (monkeypatch di `pulisci_autointersezioni`) → `AutointersezioniResidueError` con il conteggio residuo nel messaggio e `tet.wrap_tolerance` nominato.
- residue > 0 con `step_8_acceso=True` → il messaggio nomina lo step 8.
- polo passante, wrap tol 5 → `WrapOltreTolleranzaError` con il valore misurato (≈30 mm) nel messaggio.
- sfera pulita, wrap tol 5 → `wrap_applied=True`, `wrap_hausdorff_max_mm` ≈ 0,5, MeshFix non chiamato (`meshfix_clean_converged=None`), `cambiata=True`.

- [ ] **Step 1: test che falliscono** — aggiungi a `tests/test_autointersezioni.py`:

```python
from meshrec.core import config


def test_superficie_pulita_passa_intatta():
    v, f = _sfera()
    ov, of, misure, cambiata = ai.prepara_ingresso(v, f, config.TetConfig(), step_8_acceso=False)
    assert cambiata is False
    assert of is f or np.array_equal(of, f)
    assert misure["self_intersections_before"] == 0
    assert misure["meshfix_clean_converged"] is None
    assert misure["wrap_applied"] is False


def test_il_polo_passante_viene_pulito_e_registrato():
    v, f = _sfera((0.0, 0.0, -70.0))
    _, of, misure, cambiata = ai.prepara_ingresso(v, f, config.TetConfig(), step_8_acceso=False)
    assert cambiata is True
    assert misure["self_intersections_before"] == 80
    assert misure["self_intersections_after"] == 0
    assert misure["meshfix_clean_converged"] is True
    assert misure["triangles_removed_by_clean"] == len(f) - len(of)


def test_una_pulizia_che_non_converge_ferma_lo_step(monkeypatch):
    v, f = _sfera((0.0, 0.0, -70.0))
    monkeypatch.setattr(ai, "pulisci_autointersezioni", lambda v, f: (v, f, False))
    with pytest.raises(ai.AutointersezioniResidueError) as caduta:
        ai.prepara_ingresso(v, f, config.TetConfig(), step_8_acceso=True)
    messaggio = str(caduta.value)
    assert "80" in messaggio
    assert "step 8" in messaggio
    assert "tet.wrap_tolerance" in messaggio


def test_il_wrap_oltre_tolleranza_ferma_lo_step_col_valore_misurato():
    v, f = _sfera((0.0, 0.0, -70.0))
    with pytest.raises(ai.WrapOltreTolleranzaError, match=r"3\d[,.]\d+ mm"):
        ai.prepara_ingresso(v, f, config.TetConfig(wrap_tolerance=5.0), step_8_acceso=False)


def test_il_wrap_entro_tolleranza_sostituisce_e_dichiara(monkeypatch):
    chiamate = []
    monkeypatch.setattr(ai, "pulisci_autointersezioni", lambda *a: chiamate.append(a))
    v, f = _sfera()
    _, _, misure, cambiata = ai.prepara_ingresso(
        v, f, config.TetConfig(wrap_tolerance=5.0), step_8_acceso=False
    )
    assert cambiata is True and chiamate == []
    assert misure["wrap_applied"] is True
    assert misure["wrap_hausdorff_max_mm"] == pytest.approx(0.5, abs=0.05)
    assert misure["wrap_volume_after"] > misure["wrap_volume_before"]
    assert misure["wrap_note"] == "superficie sostituita, non riparata"
```

- [ ] **Step 2: rosso**

Run: `uv run --directory /Users/mario/GitHub/Tesi/meshrec pytest tests/test_autointersezioni.py -q`
Expected: FAIL, `AttributeError: prepara_ingresso`.

- [ ] **Step 3: implementazione** — in `autointersezioni.py`, import in testa `from meshrec.core.config import TetConfig` e `from meshrec.core.quality import mesh_volume`, poi:

```python
class AutointersezioniResidueError(ValueError):
    """MeshFix non ha tolto le autointersezioni: TetGen si fermerebbe comunque."""


class WrapOltreTolleranzaError(ValueError):
    """L'alpha wrap ha spostato la superficie oltre quanto l'utente ha dichiarato."""


def prepara_ingresso(
    vertices: np.ndarray, faces: np.ndarray, cfg: TetConfig, *, step_8_acceso: bool
) -> tuple[np.ndarray, np.ndarray, dict[str, object], bool]:
    """La superficie che TetGen riceve, e cio' che le e' successo per arrivarci."""
    prima = conta_autointersezioni(vertices, faces)
    misure: dict[str, object] = {
        "self_intersections_before": prima,
        "self_intersections_after": prima,
        "meshfix_clean_converged": None,
        "triangles_removed_by_clean": 0,
        "wrap_applied": False,
    }

    if cfg.wrap_tolerance is not None:
        # Col wrap MeshFix non serve: la superficie viene rifatta comunque.
        wv, wf, del_wrap = avvolgi(vertices, faces, cfg.wrap_tolerance)
        distanza = spostamento(vertices, faces, wv, wf)
        misure.update(del_wrap)
        misure.update(
            wrap_applied=True,
            wrap_hausdorff_max_mm=distanza["max"],
            wrap_hausdorff_mean_mm=distanza["mean"],
            wrap_volume_before=mesh_volume(vertices, faces),
            wrap_volume_after=mesh_volume(wv, wf),
            wrap_note="superficie sostituita, non riparata",
            # Residue del wrap: si registrano e non fermano. Con alpha piccolo
            # restano (506 sulla sfera di prova a 0,5 mm) e TetGen chiude lo stesso.
            self_intersections_after=conta_autointersezioni(wv, wf),
        )
        if distanza["max"] > cfg.wrap_tolerance:
            raise WrapOltreTolleranzaError(
                f"l'alpha wrap ha spostato la superficie fino a {distanza['max']:.2f} mm "
                f"contro i {cfg.wrap_tolerance:g} mm ammessi da tet.wrap_tolerance: le "
                "cavità più strette di alpha sono sparite. Alza la tolleranza se lo "
                "spostamento è accettabile per il modello, abbassala per seguire meglio "
                "la superficie (più triangoli, più tempo)."
            )
        return wv, wf, misure, True

    if prima == 0:
        return vertices, faces, misure, False

    pv, pf, convergito = pulisci_autointersezioni(vertices, faces)
    dopo = conta_autointersezioni(pv, pf)
    misure.update(
        self_intersections_after=dopo,
        meshfix_clean_converged=convergito,
        triangles_removed_by_clean=int(len(faces) - len(pf)),
    )
    if not convergito or dopo > 0:
        origine = (
            " Lo step 8 è acceso ed è lui a crearle: sulla scansione misurata il "
            "remeshing ne ha introdotte 646 e Taubin le ha portate a 7747."
            if step_8_acceso
            else ""
        )
        raise AutointersezioniResidueError(
            f"{dopo} facce autointersecanti restano dopo la pulizia di MeshFix "
            f"(erano {prima}): TetGen si fermerebbe nel recupero del bordo.{origine} "
            "Accendi tet.wrap_tolerance per sostituire la superficie con un alpha wrap."
        )
    return pv, pf, misure, True
```

- [ ] **Step 4: verde**

Run: `uv run --directory /Users/mario/GitHub/Tesi/meshrec pytest tests/test_autointersezioni.py -q`
Expected: 12 passed.

- [ ] **Step 5: commit**

```bash
git -C /Users/mario/GitHub/Tesi add meshrec/src/meshrec/core/autointersezioni.py meshrec/tests/test_autointersezioni.py
git -C /Users/mario/GitHub/Tesi commit -m "feat(autointersezioni): prepara_ingresso con pulizia e wrap dichiarati"
```

---

### Task 4: diagnosi di `recoversubface`

**Files:**
- Modify: `meshrec/src/meshrec/core/volume.py:101-108`
- Test: `meshrec/tests/test_volume.py:170-193`

**Interfaces:** nessuna nuova; cambia il testo che `RefinementFailedError` porta.

## Ingressi degeneri
- messaggio con `recoversubface` → nomina `tet.wrap_tolerance` e «sostituita»; continua a non dire «Alza tet.min_ratio» né «nobisect».
- messaggio senza `recoversubface` → testo invariato (test esistenti da 106 a 234 restano verdi).

- [ ] **Step 1: estendi il test esistente** — in fondo a `test_il_recupero_del_bordo_non_e_un_problema_di_qualita`:

```python
    assert "tet.wrap_tolerance" in messaggio
    assert "sostituita" in messaggio
```

e nel docstring sostituisci «La causa tipica sono le autointersezioni della superficie, e il rimedio sta a monte.» con «Le autointersezioni sono una causa, non l'unica: su runs/geoandgeo-mm fallisce anche una superficie che TetGen `-d` dichiara corretta.»

- [ ] **Step 2: rosso**

Run: `uv run --directory /Users/mario/GitHub/Tesi/meshrec pytest tests/test_volume.py -k recupero_del_bordo -q`
Expected: FAIL su `"tet.wrap_tolerance" in messaggio`.

- [ ] **Step 3: testo** — sostituisci il `return` del ramo `recoversubface` in `_diagnosi_del_guasto`:

```python
        return (
            "il guasto è nel recupero delle facce di ingresso, prima "
            "che il raffinamento cominciasse: il vincolo raggio-spigolo non è "
            "ancora entrato in gioco e cambiarlo non sposta nulla. Le cause sono "
            "le autointersezioni della superficie, che lo step 9 conta e pulisce "
            "prima di arrivare qui, oppure geometria quasi degenere che TetGen non "
            "recupera anche senza autointersezioni (pieghe, segmenti quasi "
            "sovrapposti). Il ripiego è tet.wrap_tolerance: la superficie viene "
            "sostituita da un alpha wrap, con il volume gonfiato dell'offset e le "
            "cavità più strette della tolleranza perse."
        )
```

- [ ] **Step 4: verde su tutto il file**

Run: `uv run --directory /Users/mario/GitHub/Tesi/meshrec pytest tests/test_volume.py -q`
Expected: PASS.

- [ ] **Step 5: commit**

```bash
git -C /Users/mario/GitHub/Tesi add meshrec/src/meshrec/core/volume.py meshrec/tests/test_volume.py
git -C /Users/mario/GitHub/Tesi commit -m "fix(volume): recoversubface propone tet.wrap_tolerance"
```

---

### Task 5: lo step 9 chiama `prepara_ingresso` e rimisura l'errore

**Files:**
- Modify: `meshrec/src/meshrec/core/pipeline.py` (step 9, `:777-783`; caricamento della nuvola, `:652-690`)
- Test: `meshrec/tests/test_pipeline.py`

**Interfaces:**
- Consumes: `autointersezioni.prepara_ingresso` (Task 3); `quality.geometric_error(vertices, faces, cloud)` (`quality.py:508`); `_ingresso_di_ripresa(chiede, da, out, leggi)` (`pipeline.py:138`).
- Produces: metriche dello step 9 = quelle di `prepara_ingresso` unite a quelle di `tetrahedralize_with_metrics`, più `geometric_error` quando la superficie è cambiata dopo lo step 7.

Oggi la nuvola sorgente si carica in ripresa solo se `start <= 7 or stop >= 12` (`pipeline.py:667`), e `source_cloud` non è definita altrimenti. La rimisura la chiede solo quando serve, così una ripresa dallo step 9 senza cambi non paga la lettura.

## Ingressi degeneri
- corsa del cubo di prova (superficie pulita, step 8 spento) → `09_tetrahedralize` porta `self_intersections_before == 0`, `wrap_applied is False`, **nessuna** chiave `geometric_error`; nodi e tetraedri identici a prima (test di determinismo esistente verde).
- ripresa `from_step=9` con step 8 acceso → `geometric_error` presente, la nuvola caricata da `02_segmented.ply`.
- ripresa `from_step=9` con `02_segmented.ply` assente e rimisura necessaria → l'errore di `_ingresso_di_ripresa` che nomina lo step 2, non un `NameError`.
- `wrap_tolerance` acceso sul cubo → `wrap_applied is True`, `geometric_error` presente, deck scritto.

- [ ] **Step 1: test che falliscono** — in `tests/test_pipeline.py`, accanto ai test di ripresa (`:240`):

```python
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
    nuvola (`pipeline.py:667`): senza, il test non passerebbe dal codice nuovo."""
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
```

Prima di scriverli: leggi `run_dir` (`test_pipeline.py:96`) per il valore che rende e il test `:357` per come le corse copiate cambiano `out_dir`; allinea i test a quelle forme invece di indovinarle. `shutil` va importato se manca. Se `cfg.tet` non accetta assegnazione, usa `model_copy(update=...)`. La tolleranza 20 mm è scelta perché il cubo `SIZE = (100, 40, 200)` ha spigoli vivi che un wrap a tolleranza più piccola arrotonda di poco: se il test fallisce per `WrapOltreTolleranzaError`, rimisura lo spostamento e scrivi nel test il valore e la data, non alzare la soglia a occhio.

- [ ] **Step 2: rosso**

Run: `uv run --directory /Users/mario/GitHub/Tesi/meshrec pytest tests/test_pipeline.py -k "autointersezioni or wrap or step_2" -q`
Expected: FAIL, `KeyError: 'self_intersections_before'`.

- [ ] **Step 3: implementazione** — in `pipeline.py`:

(a) import in testa accanto agli altri moduli di `core`: `autointersezioni`.

(b) prima di `if start <= 2:` (`:658`): `source_cloud: np.ndarray | None = None` — solo se `source_cloud` non è già inizializzata sopra; controlla leggendo `run()` da `:522`.

(c) step 9 (`:777-783`) diventa:

```python
        if start <= 9:
            in_corso = 9
            avvio = time.monotonic()
            vertices, faces, preparazione, cambiata = autointersezioni.prepara_ingresso(
                vertices, faces, cfg.tet, step_8_acceso=cfg.simplify.enabled
            )
            nodes, tets, step_metrics = volume.tetrahedralize_with_metrics(
                vertices, faces, cfg.tet
            )
            step_metrics = {**preparazione, **step_metrics}
            # Lo step 7 misura l'errore prima dello step 8 e di questa
            # preparazione: se la superficie e' cambiata dopo, quel numero non
            # descrive piu' la superficie che TetGen ha riempito.
            if cambiata or cfg.simplify.enabled:
                if source_cloud is None:
                    source_cloud, _ = _ingresso_di_ripresa(9, 2, out, io.read_cloud)
                step_metrics["geometric_error"] = quality.geometric_error(
                    vertices, faces, source_cloud
                )
            metrics["09_tetrahedralize"] = step_metrics
```

il resto del blocco (`write_vtu`, `registra`, fermata) resta invariato.

- [ ] **Step 4: verde sui file toccati**

Run: `uv run --directory /Users/mario/GitHub/Tesi/meshrec pytest tests/test_pipeline.py tests/test_autointersezioni.py tests/test_volume.py -q`
Expected: PASS, compreso il determinismo (`test_pipeline.py:225-238`).

- [ ] **Step 5: suite onesta**

Run: `uv run --directory /Users/mario/GitHub/Tesi/meshrec pytest -m "" -q`
Expected: PASS, con gli stessi skip della corsa di riferimento: lancia `uv run --directory /Users/mario/GitHub/Tesi/meshrec pytest -m "" -q` **prima del Task 1** e annota passati/saltati. Se `test_report.py` o `test_server.py` vanno rossi per le chiavi nuove in `09_tetrahedralize`, leggi cosa verificano prima di toccarli: una tabella chiusa di chiavi è una scelta, non un incidente.

- [ ] **Step 6: commit**

```bash
git -C /Users/mario/GitHub/Tesi add meshrec/src/meshrec/core/pipeline.py meshrec/tests/test_pipeline.py
git -C /Users/mario/GitHub/Tesi commit -m "feat(pipeline): step 9 prepara la superficie e rimisura l'errore"
```

---

### Task 6: verifica sul caso reale e CHANGELOG

**Files:**
- Modify: `CHANGELOG.md` (`## [Unreleased]`)

HITL con Mario: la corsa è lunga e usa i suoi dati.

- [ ] **Step 1:** su `runs/geoandgeo-mm` (step 8 acceso, `taubin_iterations: 2`), senza wrap: lanciare dallo step 9 e verificare che fallisca con `AutointersezioniResidueError` **oppure** che MeshFix pulisca e TetGen si fermi in `recoversubfaces` con il messaggio nuovo. Annotare quale dei due, conteggi e tempi.
- [ ] **Step 2:** stessa corsa con `tet.wrap_tolerance` scelto da Mario (il caso misurato: con alpha 6,9 mm lo spostamento è arrivato a 27,6 mm, quindi sotto ~30 mm lo step fallirà — è il comportamento voluto). Annotare spostamento, volume prima/dopo, tetraedri, secondi, errore geometrico rimisurato.
- [ ] **Step 3:** voce nel CHANGELOG sotto `[Unreleased]`:

```markdown
### Aggiunto

- Lo step 9 conta le autointersezioni della superficie prima di TetGen, le pulisce con il
  ciclo di MeshFix leggendone l'esito, e rimisura l'errore geometrico quando la superficie è
  cambiata dopo lo step 7.
- `tet.wrap_tolerance`: ripiego a richiesta che sostituisce la superficie con un alpha wrap di
  CGAL entro uno spostamento dichiarato in mm; oltre, lo step fallisce con il valore misurato.
```

- [ ] **Step 4:** commit `docs: changelog autointersezioni e wrap`, con i numeri dei passi 1-2 nel corpo del messaggio.

---

## Cose che il piano sposta e che vanno dette nella PR

- La catena `steps.step_fingerprints` si sposta una volta dagli step 9-12: ogni corsa già su disco si dichiara da rieseguire da lì al primo avvio. Stesso compromesso già accettato per `regioni` (`sweep.py:80-90`).
- Lo step 9 costa 3-7 s in più su scansioni reali per il conteggio.
