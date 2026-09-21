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
    `mean` e' il **massimo** delle due medie direzionali: nome ingannevole ma
    voluto, cautelativo.
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
