"""Autointersezioni della superficie prima di TetGen, e il ripiego che la rifà.

Lo step 8 le crea (646 facce dopo il remeshing, 7747 dopo Taubin, misurato su
runs/geoandgeo-mm) e TetGen le scopre solo fermandosi in `recoversubfaces`.
Vedi docs/ricerca/2026-09-21-autointersezioni-e-degeneri.md.
"""

from __future__ import annotations

import math
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
    if not diagonale > 0.0:
        raise ValueError(
            "superficie senza ingombro (diagonale del riquadro nulla, vertici "
            "tutti coincidenti): l'alpha wrap non ha una scala su cui lavorare"
        )
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


# Tetto ai punti per faccia: un difetto che chiede un passo assurdamente fine
# su un lato enorme (spigolo degenere) si ferma qui, non satura la macchina.
# 1000 e' abbondante: il caso peggiore misurato (polo passante, passo 0,25 mm,
# spigolo 119,6 mm) ne chiede 479.
_N_MAX_SUBDIVISIONI_PER_FACCIA = 1000


def _diagonale(vertices: np.ndarray) -> float:
    v = np.asarray(vertices, dtype=np.float64)
    if len(v) == 0:
        return 0.0
    return float(np.linalg.norm(v.max(axis=0) - v.min(axis=0)))


# Budget di punti per lotto durante la generazione dei campioni. Round 2
# costruiva tutta la griglia in un colpo solo (`np.vstack`): su una
# superficie reale (1-4 M facce, spigoli 10-20 mm, passo tol/5) sono
# centinaia di milioni di punti, OOM (misurato: sistema ucciso per pressione
# di memoria durante lo sviluppo, 21/09/2026). Qui il picco di memoria
# dipende da questa costante, non dal totale della mesh.
_PUNTI_PER_LOTTO_CAMPIONI = 200_000


def _lotti_di_campioni(vertices: np.ndarray, faces: np.ndarray, passo: float):
    """Vertici piu' una griglia baricentrica per faccia, passo `passo` (mm), a lotti.

    Stesso punto di `_campioni_deterministici` di prima (round 2): un solo
    campione per faccia (baricentro) sottostima quando il triangolo e' grande
    o degenere — sulla sfera col polo passante mancavano ~9 mm rispetto al
    massimo trovato dal Montecarlo. La griglia (i/n, j/n) per faccia, con
    `n = ceil(spigolo piu' lungo / passo)`, chiude il buco.

    La differenza e' che qui i punti escono a lotti (`yield`), non tutti
    insieme: ogni lotto resta sotto `_PUNTI_PER_LOTTO_CAMPIONI` (salvo una
    singola faccia che da sola lo supera gia' — capita solo su un unico
    spigolo enorme, il tetto `_N_MAX_SUBDIVISIONI_PER_FACCIA` la tiene comunque
    limitata). Ogni lotto e' generato dalle stesse operazioni numpy
    deterministiche di prima: stessa chiamata, stessi lotti, byte per byte.
    """
    v = np.asarray(vertices, dtype=np.float64)
    f = np.asarray(faces, dtype=np.int64)
    if len(v) > 0:
        yield v
    if len(f) == 0:
        return
    a, b, c = v[f[:, 0]], v[f[:, 1]], v[f[:, 2]]
    lati = np.stack(
        [np.linalg.norm(b - a, axis=1), np.linalg.norm(c - b, axis=1), np.linalg.norm(a - c, axis=1)],
        axis=1,
    )
    n_per_faccia = np.clip(
        np.ceil(lati.max(axis=1) / passo).astype(np.int64), 1, _N_MAX_SUBDIVISIONI_PER_FACCIA
    )
    for n in np.unique(n_per_faccia):
        idx = np.flatnonzero(n_per_faccia == n)
        ij = np.array([(i, j) for i in range(n + 1) for j in range(n + 1 - i)], dtype=np.float64)
        u, w = (ij[:, 0] / n)[None, :, None], (ij[:, 1] / n)[None, :, None]
        facce_per_lotto = max(1, _PUNTI_PER_LOTTO_CAMPIONI // len(ij))
        for i in range(0, len(idx), facce_per_lotto):
            sel = idx[i : i + facce_per_lotto]
            griglia = a[sel][:, None, :] + u * (b[sel] - a[sel])[:, None, :] + w * (c[sel] - a[sel])[:, None, :]
            yield griglia.reshape(-1, 3)


# ponytail: k=8 candidati per centroide, non tutte le facce. Il tetto vero
# non sono gli aghi isolati ma la disparita' di taglia fra triangoli vicini:
# un triangolo grande col baricentro lontano, circondato da 12 piccoli, puo'
# restare fuori dagli 8 piu' vicini anche se la sua superficie e' a 0 mm dal
# punto (riprodotto in review: 0,99 mm invece di 0). La direzione dell'errore
# e' fail-safe: sovrastima, mai sottostima lo spostamento registrato. Se
# compaiono spostamenti gonfiati su mesh con taglie di triangolo molto
# disomogenee, la via d'uscita e' `query_ball_point` sui centroidi (raggio, non k fisso)
# al posto di questo k.
_CANDIDATI_PER_PUNTO = 8
_LOTTO_PUNTI = 20_000


def _punto_piu_vicino_su_triangolo(p: np.ndarray, a: np.ndarray, b: np.ndarray, c: np.ndarray) -> np.ndarray:
    """Distanza esatta punto-triangolo, vettoriale (Ericson, *Real-Time Collision
    Detection*, 5.1.5: regione piu' vicina per proiezione baricentrica)."""
    ab, ac, ap = b - a, c - a, p - a
    d1, d2 = np.sum(ab * ap, axis=-1), np.sum(ac * ap, axis=-1)
    bp = p - b
    d3, d4 = np.sum(ab * bp, axis=-1), np.sum(ac * bp, axis=-1)
    cp = p - c
    d5, d6 = np.sum(ab * cp, axis=-1), np.sum(ac * cp, axis=-1)
    vc, vb_, va_ = d1 * d4 - d3 * d2, d5 * d2 - d1 * d6, d3 * d6 - d5 * d4

    denom = va_ + vb_ + vc
    denom = np.where(denom == 0, 1.0, denom)
    interno = a + ab * (vb_ / denom)[..., None] + ac * (vc / denom)[..., None]
    su_ab = a + np.clip(d1 / np.where(d1 - d3 == 0, 1.0, d1 - d3), 0.0, 1.0)[..., None] * ab
    su_ac = a + np.clip(d2 / np.where(d2 - d6 == 0, 1.0, d2 - d6), 0.0, 1.0)[..., None] * ac
    su_bc = b + np.clip(
        (d4 - d3) / np.where((d4 - d3) + (d5 - d6) == 0, 1.0, (d4 - d3) + (d5 - d6)), 0.0, 1.0
    )[..., None] * (c - b)

    punto = interno.copy()
    punto = np.where(((va_ <= 0) & (d4 - d3 >= 0) & (d5 - d6 >= 0))[..., None], su_bc, punto)
    punto = np.where(((vb_ <= 0) & (d2 >= 0) & (d6 <= 0))[..., None], su_ac, punto)
    punto = np.where(((vc <= 0) & (d1 >= 0) & (d3 <= 0))[..., None], su_ab, punto)
    punto = np.where(((d6 >= 0) & (d5 <= d6))[..., None], c, punto)
    punto = np.where(((d3 >= 0) & (d4 <= d3))[..., None], b, punto)
    punto = np.where(((d1 <= 0) & (d2 <= 0))[..., None], a, punto)
    return np.linalg.norm(p - punto, axis=-1)


def _distanza_punti_a_superficie(punti: np.ndarray, vertices: np.ndarray, faces: np.ndarray) -> np.ndarray:
    """Distanza minima, esatta, da ogni punto alla superficie continua (non ai suoi vertici).

    Il candidato e' l'insieme delle `_CANDIDATI_PER_PUNTO` facce coi centroidi
    piu' vicini (KDTree), poi la proiezione esatta sceglie il punto. A lotti,
    cosi' il picco di memoria non dipende da quanti punti misuriamo insieme.
    """
    from scipy.spatial import cKDTree

    a = vertices[faces[:, 0]]
    b = vertices[faces[:, 1]]
    c = vertices[faces[:, 2]]
    albero = cKDTree((a + b + c) / 3.0)
    k = min(_CANDIDATI_PER_PUNTO, len(faces))
    distanze = np.empty(len(punti))
    for i in range(0, len(punti), _LOTTO_PUNTI):
        lotto = punti[i : i + _LOTTO_PUNTI]
        _, idx = albero.query(lotto, k=k)
        if k == 1:
            idx = idx[:, None]
        d = _punto_piu_vicino_su_triangolo(lotto[:, None, :], a[idx], b[idx], c[idx])
        distanze[i : i + _LOTTO_PUNTI] = d.min(axis=1)
    return distanze


def _distanza_massima_e_media(
    vertices: np.ndarray, faces: np.ndarray, passo: float, verso_v: np.ndarray, verso_f: np.ndarray
) -> tuple[float, float, np.ndarray]:
    """Massimo, media e distanze (float32) dai campioni di (vertices, faces) verso l'altra superficie.

    A lotti (`_lotti_di_campioni`): massimo e somma/conteggio si aggiornano
    lotto per lotto, cosi' non serve mai avere tutti i campioni in memoria
    insieme. Ogni lotto si somma con `math.fsum` (esatta, in C), poi le somme
    dei lotti con un altro `math.fsum`: deterministica a lotto fisso, e la
    dimensione del lotto e' una costante. Cambiarla puo' spostare la media
    nell'ultimo bit (due arrotondamenti, non uno); il massimo no.
    """
    massimo = 0.0
    somme: list[float] = []
    conteggio = 0
    # ponytail: tutte le distanze tenute in float32 per il percentile, 4 byte
    # a campione: 40 M campioni = 160 MB. Se la memoria diventa il problema,
    # un istogramma a passo fisso aggiornato lotto per lotto le sostituisce.
    distanze: list[np.ndarray] = []
    for lotto in _lotti_di_campioni(vertices, faces, passo):
        if len(lotto) == 0:
            continue
        d = _distanza_punti_a_superficie(lotto, verso_v, verso_f)
        massimo = max(massimo, float(d.max()))
        somme.append(math.fsum(d))
        conteggio += len(d)
        distanze.append(d.astype(np.float32))
    tutte = np.concatenate(distanze) if distanze else np.empty(0, dtype=np.float32)
    return massimo, (math.fsum(somme) / conteggio if conteggio else 0.0), tutte


def spostamento(
    va: np.ndarray,
    fa: np.ndarray,
    vb: np.ndarray,
    fb: np.ndarray,
    passo_mm: float | None = None,
) -> dict[str, float]:
    """Distanza punto-superficie nei due versi, deterministico.

    I campioni sono `_lotti_di_campioni`: il solo campionamento dei vertici
    sottostimerebbe l'errore dove i triangoli sono grandi
    (`quality.geometric_error`, meshrec/src/meshrec/core/quality.py:519-526),
    la griglia copre anche l'interno delle facce, a lotti cosi' il picco di
    memoria dipende dal lotto e non dalla mesh intera (round 2 costruiva
    tutto in un colpo solo: su una superficie reale, centinaia di milioni di
    punti). La distanza e' verso la superficie **continua** dell'altra mesh
    (`_distanza_punti_a_superficie`, proiezione esatta sul triangolo), non
    verso i suoi campioni: misurare punto-contro-punti-campionati sottostima
    anche su una superficie liscia (misurato: 1,05 mm invece di 0,5 mm sulla
    sfera pulita, wrap 5 mm).

    Il filtro `get_hausdorff_distance` di PyMeshLab, verificato in sessione,
    non e' deterministico nemmeno con `sampleface=False, samplevert=True` su
    una nuvola di punti gia' fissi: stessa coppia, stessi campioni, `max`
    diverso a ogni chiamata (jitter ~0,003 mm, sorgente interna alla
    libreria). Per questo la distanza qui e' calcolata in numpy/scipy, gia'
    dipendenze del progetto, non con quel filtro.

    `passo_mm` e' il passo (mm) della griglia; se `None` e' l'1 % della
    diagonale piu' grande fra le due superfici — sulla superficie reale
    (facce a lato ~1 % della diagonale) tiene un punto a faccia, veloce
    (159 200 facce, 557 202 campioni, ~2 s, misurato su una sfera fitta).
    Chi conosce una tolleranza piu' stretta (`prepara_ingresso`, col wrap)
    passa un passo piu' fine: un campione troppo rado sottostima lo
    spostamento che si registra.

    `mean` e' il **massimo** delle due medie direzionali: nome ingannevole ma
    voluto, cautelativo. `p95` e' il 95° percentile dei campioni dei due
    versi insieme.
    """
    if passo_mm is None:
        passo_mm = 0.01 * max(_diagonale(va), _diagonale(vb))
    max_a_verso_b, mean_a_verso_b, d_a = _distanza_massima_e_media(va, fa, passo_mm, vb, fb)
    max_b_verso_a, mean_b_verso_a, d_b = _distanza_massima_e_media(vb, fb, passo_mm, va, fa)
    insieme = np.concatenate([d_a, d_b])
    return {
        "max_a_verso_b": max_a_verso_b,
        "max_b_verso_a": max_b_verso_a,
        "max": max(max_a_verso_b, max_b_verso_a),
        "mean": max(mean_a_verso_b, mean_b_verso_a),
        "p95": float(np.percentile(insieme, 95)) if len(insieme) else 0.0,
    }


class AutointersezioniResidueError(ValueError):
    """MeshFix ha lasciato autointersezioni, o non ha dichiarato la convergenza.

    Nel secondo caso il conteggio residuo puo' essere zero: MeshFix si e'
    fermato al tetto dei giri senza garantire la superficie, e TetGen potrebbe
    fermarsi comunque.
    """


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
        # Lo spostamento si misura e si registra, non ferma lo step
        # (decisione del 21/09/2026: sul caso reale il massimo viene dalle
        # cavita' piu' strette di alpha, che il wrap chiude per costruzione,
        # e col limite lo step falliva a ogni tolleranza). Il passo di default
        # di spostamento() (1% della diagonale) sottostima sui difetti locali (misurato: ~30 mm contro un vero 30,82 mm sulla
        # sfera col polo passante, wrap 5 mm). tol/5 raggiunge gia' il valore
        # a cui il campionamento converge (uguale a tol/10, la meta' dei
        # punti); tol stesso no (29,86 mm, sotto soglia). 21/09/2026.
        distanza = spostamento(vertices, faces, wv, wf, passo_mm=cfg.wrap_tolerance / 5.0)
        misure.update(del_wrap)
        misure.update(
            wrap_applied=True,
            wrap_hausdorff_max_mm=distanza["max"],
            wrap_hausdorff_mean_mm=distanza["mean"],
            wrap_hausdorff_p95_mm=distanza["p95"],
            wrap_volume_before=mesh_volume(vertices, faces),
            wrap_volume_after=mesh_volume(wv, wf),
            wrap_note="superficie sostituita, non riparata",
            # Residue del wrap: si registrano e non fermano. Con alpha piccolo
            # restano (506 sulla sfera di prova a 0,5 mm) e TetGen chiude lo stesso.
            self_intersections_after=conta_autointersezioni(wv, wf),
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
        esito = (
            f"{dopo} facce autointersecanti restano dopo la pulizia di MeshFix "
            f"(erano {prima}): TetGen si fermerebbe nel recupero del bordo."
            if dopo > 0
            else f"MeshFix non ha dichiarato la convergenza; il conteggio residuo è "
            f"{dopo} (erano {prima}), ma la superficie non è garantita e TetGen "
            "potrebbe fermarsi nel recupero del bordo."
        )
        origine = (
            " Lo step 8 è acceso ed è la causa tipica: remeshing e Taubin "
            "introducono autointersezioni."
            if step_8_acceso
            else ""
        )
        raise AutointersezioniResidueError(
            f"{esito}{origine} Accendi tet.wrap_tolerance per sostituire la "
            "superficie con un alpha wrap."
        )
    return pv, pf, misure, True
