"""Gmsh come generatore alternativo di mesh tetraedrica.

Non e' un post-processore: Gmsh ricostruisce la geometria dalla superficie e
genera la propria mesh, quindi il confronto con TetGen ha senso solo a parita
di numero di elementi. La misura di Fase 0 non lo era.

La dimensione caratteristica che produce esattamente N tetraedri non e' nota in
forma chiusa: la stima analitica sbagliava di un fattore sei. Qui la dimensione
non si stima soltanto, si calibra (vedi `_calibrate`).
"""

from __future__ import annotations

import contextlib
import os
import tempfile
from pathlib import Path

import numpy as np

from meshrec.core.quality import mesh_volume

# Parametri della calibrazione: non sono parametri di elaborazione esposti
# all'utente (TetConfig non li contiene e la pipeline non usa questo modulo),
# ma costanti dell'algoritmo che cerca la dimensione caratteristica.
_MAX_ATTEMPTS = 4
_ACCEPTED_RATIO = (0.85, 1.2)


def inizializza(gmsh) -> None:
    """`gmsh.initialize()` che lascia intatto il PATH nativo del processo.

    gmsh 4.15 in `Msg::Initialize` aggiunge la propria cartella al PATH
    (GmshMessage.cpp:185) leggendolo, su Windows, in un buffer di MAX_PATH
    byte (OS.cpp:290) e riscrivendolo con `_wputenv`: il PATH nativo si
    tronca (misurato in CI: 2865 -> 306 caratteri) mentre `os.environ` resta
    intatto, e ogni sottoprocesso lanciato dopo non trova piu' `git`.
    """
    path = os.environ.get("PATH")
    try:
        gmsh.initialize()
    finally:
        # ponytail: riassegnare os.environ richiama putenv e riscrive il PATH
        # nativo da solo, su tutte le piattaforme; su POSIX gmsh non tronca
        # ma aggiunge la cartella dell'interprete, e si toglie anche quella.
        if path is not None:
            os.environ["PATH"] = path


def _extract_mesh(gmsh) -> tuple[np.ndarray, np.ndarray]:
    """Nodi e tetraedri della mesh corrente, con i tag rimappati su indici di array."""
    node_tags, coordinates, _ = gmsh.model.mesh.getNodes()
    element_types, _, node_tags_per_element = gmsh.model.mesh.getElements(3)
    if 4 not in element_types:
        raise RuntimeError("Gmsh non ha prodotto tetraedri lineari (tipo 4)")
    tet_tags = np.asarray(node_tags_per_element[list(element_types).index(4)], dtype=np.int64)

    node_tags = np.asarray(node_tags, dtype=np.int64)
    nodes = np.ascontiguousarray(np.asarray(coordinates, dtype=np.float64).reshape(-1, 3))

    # I tag dei nodi sono 1-based e non contigui: senza rimappatura gli elementi
    # punterebbero a posizioni sbagliate dell'array, e la mesh sarebbe sbagliata
    # senza alcun segnale.
    lookup = np.zeros(node_tags.max() + 1, dtype=np.int64)
    lookup[node_tags] = np.arange(len(node_tags))
    tets = np.ascontiguousarray(lookup[tet_tags].reshape(-1, 4))
    return nodes, tets


def _mesh_from_stl(stl_path: Path, size: float | None) -> tuple[np.ndarray, np.ndarray]:
    """Ricostruisce la geometria dall'STL e genera la mesh di volume alla dimensione data.

    Ogni tentativo riparte da `initialize`: la geometria prodotta da
    `classifySurfaces` piu `createGeometry` e' parametrizzata sulla mesh
    d'appoggio dell'STL, e `mesh.clear()` la distrugge lasciando Gmsh a
    rimagliare una superficie senza parametrizzazione (verificato: la
    generazione successiva non termina). Ricostruire e' l'unico modo semplice
    per cambiare dimensione fra un tentativo e l'altro.
    """
    import gmsh

    inizializza(gmsh)
    try:
        gmsh.option.setNumber("General.Terminal", 0)
        gmsh.merge(str(stl_path))
        gmsh.model.mesh.classifySurfaces(np.pi / 4.0, True, True)
        gmsh.model.mesh.createGeometry()

        surfaces = [entity[1] for entity in gmsh.model.getEntities(2)]
        loop = gmsh.model.geo.addSurfaceLoop(surfaces)
        gmsh.model.geo.addVolume([loop])
        gmsh.model.geo.synchronize()

        if size is not None:
            # Con il solo Mesh.MeshSizeMax la taglia richiesta e' un tetto senza
            # pavimento e resta inerte quando la risoluzione dedotta dal bordo
            # e' gia' piu fine. Fissare anche il minimo, imporre la taglia sui
            # punti e spegnere i due meccanismi che la riderivano dal bordo e
            # dalla curvatura rende la dimensione effettivamente quella
            # richiesta: e' il presupposto perche' la calibrazione converga.
            gmsh.model.mesh.setSize(gmsh.model.getEntities(0), size)
            gmsh.option.setNumber("Mesh.MeshSizeMax", size)
            gmsh.option.setNumber("Mesh.MeshSizeMin", size)
            gmsh.option.setNumber("Mesh.MeshSizeExtendFromBoundary", 0)
            gmsh.option.setNumber("Mesh.MeshSizeFromCurvature", 0)

        gmsh.model.mesh.generate(3)
        gmsh.model.mesh.optimize("Netgen")
        return _extract_mesh(gmsh)
    finally:
        gmsh.finalize()


def _calibrate(
    stl_path: Path, vertices: np.ndarray, faces: np.ndarray, target_elements: int
) -> tuple[np.ndarray, np.ndarray, float, int]:
    """Cerca la dimensione caratteristica che produce circa `target_elements` tetraedri.

    Il numero di elementi scala col cubo dell'inverso della dimensione, quindi
    da un conteggio ottenuto la correzione e' il fattore
    `(ottenuti / obiettivo) ** (1/3)`: una o due iterazioni bastano di solito a
    rientrare nella fascia accettata. Superato il tetto di tentativi si
    restituisce il tentativo con il rapporto migliore, senza insistere.

    Restituisce nodi, tetraedri, dimensione usata e numero di tentativi spesi.
    """
    enclosed = abs(mesh_volume(vertices, faces))
    # Punto di partenza: lato del tetraedro regolare di volume medio V/N.
    size = (enclosed / target_elements * 6.0 * np.sqrt(2.0)) ** (1.0 / 3.0)
    best: tuple[np.ndarray, np.ndarray, float, int] | None = None
    best_error = np.inf

    for attempt in range(1, _MAX_ATTEMPTS + 1):
        nodes, tets = _mesh_from_stl(stl_path, size)
        ratio = len(tets) / target_elements
        # Lo scarto si misura in scala logaritmica: un rapporto e il suo
        # reciproco sono ugualmente lontani dalla parita.
        error = abs(np.log(ratio))
        if error < best_error:
            best, best_error = (nodes, tets, size, attempt), error
        if _ACCEPTED_RATIO[0] < ratio < _ACCEPTED_RATIO[1]:
            break
        size *= ratio ** (1.0 / 3.0)

    assert best is not None  # il ciclo gira almeno una volta
    return best


def tetrahedralize_gmsh(
    vertices: np.ndarray, faces: np.ndarray, target_elements: int | None
) -> tuple[np.ndarray, np.ndarray, dict[str, object]]:
    """Genera e ottimizza una mesh tetraedrica con Gmsh a partire dalla superficie chiusa.

    Con `target_elements` non nullo la dimensione caratteristica viene calibrata
    per avvicinare quel numero di tetraedri, cosi' che il confronto con TetGen
    avvenga a parita di elementi. Le metriche riportano il rapporto ottenuto: se
    la calibrazione non e' rientrata nella fascia, il rapporto lo dice.
    """
    import meshio

    # Gmsh scrive nella directory corrente file d'appoggio propri (per esempio
    # new_points.pos, la vista dei punti di Steiner del recupero del bordo).
    # Lavorare dentro la cartella temporanea li fa sparire con essa invece di
    # lasciarli nella radice del pacchetto.
    with tempfile.TemporaryDirectory() as folder, contextlib.chdir(folder):
        stl_path = Path(folder) / "surface.stl"
        meshio.write_points_cells(
            str(stl_path),
            np.asarray(vertices, dtype=np.float64),
            [("triangle", np.asarray(faces, dtype=np.int64))],
        )

        if target_elements is None:
            nodes, tets = _mesh_from_stl(stl_path, None)
            size, attempts = None, 1
        else:
            nodes, tets, size, attempts = _calibrate(stl_path, vertices, faces, target_elements)

    metrics = {
        "nodes": int(len(nodes)),
        "tets": int(len(tets)),
        "target_elements": target_elements,
        "mesh_size": None if size is None else float(size),
        "calibration_attempts": int(attempts),
        "element_ratio": None if target_elements is None else len(tets) / target_elements,
        "optimizer": "Netgen",
    }
    return nodes, tets, metrics
