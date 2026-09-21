"""Autointersezioni della superficie prima di TetGen, e il ripiego che la rifà.

Lo step 8 le crea (646 facce dopo il remeshing, 7747 dopo Taubin, misurato su
runs/geoandgeo-mm) e TetGen le scopre solo fermandosi in `recoversubfaces`.
Vedi docs/ricerca/2026-09-21-autointersezioni-e-degeneri.md.
"""

from __future__ import annotations

import time

import numpy as np

from meshrec.core import volume
from meshrec.core.config import TetConfig
from meshrec.core.quality import mesh_volume


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


def _campioni_deterministici(vertices: np.ndarray, faces: np.ndarray) -> np.ndarray:
    """Vertici, baricentri delle facce, punti medi degli spigoli: niente Montecarlo.

    `get_hausdorff_distance` con `sampleface=True` campiona l'interno delle
    facce a caso, e la versione installata di PyMeshLab non espone un seme
    (verificato con `pymeshlab.print_filter_parameter_list('get_hausdorff_distance')`,
    21/09/2026: nessun parametro di seme in lista). Stessi ingressi, valori
    diversi a ogni chiamata — misurato: 29,85/30,11/30,11/30,38/... mm sulla
    stessa coppia. Questi punti sono fissi, quindi lo e' anche il campione.
    """
    v = np.asarray(vertices, dtype=np.float64)
    f = np.asarray(faces, dtype=np.int64)
    baricentri = v[f].mean(axis=1)
    spigoli = np.concatenate([f[:, [0, 1]], f[:, [1, 2]], f[:, [2, 0]]])
    punti_medi = v[spigoli].mean(axis=1)
    return np.ascontiguousarray(np.vstack([v, baricentri, punti_medi]))


def spostamento(
    va: np.ndarray, fa: np.ndarray, vb: np.ndarray, fb: np.ndarray
) -> dict[str, float]:
    """Hausdorff nei due versi fra due superfici, su campioni fissi (deterministico).

    Il campione e' `_campioni_deterministici`: vertici, baricentri e punti
    medi degli spigoli, misurati con `samplevert=True` soltanto (nessun
    Montecarlo). Il solo campionamento dei vertici sottostimerebbe l'errore
    dove i triangoli sono grandi (`quality.geometric_error`,
    meshrec/src/meshrec/core/quality.py:519-526); qui i baricentri e i punti
    medi coprono anche l'interno delle facce, senza il dado del Montecarlo.
    `mean` e' il **massimo** delle due medie direzionali: nome ingannevole ma
    voluto, cautelativo.
    """
    import pymeshlab

    mesh_set = _mesh_set(va, fa)  # 0: superficie A
    mesh_set.add_mesh(
        pymeshlab.Mesh(np.asarray(vb, dtype=np.float64), np.asarray(fb, dtype=np.int32))
    )  # 1: superficie B
    mesh_set.add_mesh(pymeshlab.Mesh(_campioni_deterministici(va, fa)))  # 2: campioni di A
    mesh_set.add_mesh(pymeshlab.Mesh(_campioni_deterministici(vb, fb)))  # 3: campioni di B
    versi = {}
    for nome, campionata, bersaglio in (
        ("max_a_verso_b", 2, 1),
        ("max_b_verso_a", 3, 0),
    ):
        versi[nome] = dict(
            mesh_set.apply_filter(
                "get_hausdorff_distance",
                sampledmesh=campionata,
                targetmesh=bersaglio,
                samplevert=True,
                sampleface=False,
                maxdist=pymeshlab.PercentageValue(100.0),
            )
        )
    return {
        "max_a_verso_b": float(versi["max_a_verso_b"]["max"]),
        "max_b_verso_a": float(versi["max_b_verso_a"]["max"]),
        "max": max(float(r["max"]) for r in versi.values()),
        "mean": max(float(r["mean"]) for r in versi.values()),
    }


class AutointersezioniResidueError(ValueError):
    """MeshFix non ha tolto le autointersezioni: TetGen si fermerebbe comunque."""


class WrapOltreTolleranzaError(ValueError):
    """L'alpha wrap ha spostato la superficie oltre quanto l'utente ha dichiarato."""


def prepara_ingresso(
    vertices: np.ndarray, faces: np.ndarray, cfg: TetConfig, *, step_8_acceso: bool
) -> tuple[np.ndarray, np.ndarray, dict[str, object], bool]:
    """La superficie che TetGen riceve, e cio' che le e' successo per arrivarci."""
    # Stesso controllo di volume.tetrahedralize, e prima di lui: la spec vuole
    # che vuota/aperta si fermino "prima del wrap" (specs/…-design.md:111-112).
    volume.verifica_superficie_pronta(faces)

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
