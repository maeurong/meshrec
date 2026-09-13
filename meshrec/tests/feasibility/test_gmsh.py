"""Fase 0 — Gmsh genera e migliora una mesh tetraedrica partendo da una STL?"""

import meshio
import numpy as np
import pytest

from meshrec.core import synth
from meshrec.core.gmsh_backend import inizializza

pytestmark = pytest.mark.feasibility

SIZE = (100.0, 40.0, 200.0)


def _write_stl(path) -> None:
    vertices, faces = synth.box_mesh(SIZE)
    meshio.write_points_cells(path, np.asarray(vertices), [("triangle", np.asarray(faces))])


def test_gmsh_meshes_and_optimizes_a_box(tmp_path):
    gmsh = pytest.importorskip("gmsh")

    stl_path = tmp_path / "box.stl"
    _write_stl(str(stl_path))

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

        gmsh.model.mesh.generate(3)
        _, tags, _ = gmsh.model.mesh.getElements(3)
        before = np.asarray(gmsh.model.mesh.getElementQualities(tags[0]))

        # "Netgen" non e' garantito in ogni build: un solo ripiego su "" (default).
        try:
            gmsh.model.mesh.optimize("Netgen")
            optimizer_used = "Netgen"
        except Exception:
            gmsh.model.mesh.optimize("")
            optimizer_used = "default (\"\")"

        _, tags_after, _ = gmsh.model.mesh.getElements(3)
        after = np.asarray(gmsh.model.mesh.getElementQualities(tags_after[0]))

        # L'esito di Fase 0 dichiara optimize("Netgen") come scelta per la
        # Fase 1: se qui servisse il ripiego, l'asserzione deve fallire,
        # cosi' il documento degli esiti si corregge invece di restare falso.
        assert optimizer_used == "Netgen"

        # L'ottimizzazione puo aggiungere/rimuovere elementi (split/collapse):
        # il confronto e' sulla qualita minima dell'intera mesh, non elemento
        # per elemento, quindi resta valido anche se il conteggio cambia. Nella
        # misura di riferimento il numero di elementi passa da 540 a 775, quindi
        # il confronto non e' a parita di elementi: parte del guadagno di qualita
        # viene dal raffittimento, non dalla sola ottimizzazione.
        assert len(before) > 10
        assert before.min() > 0.0
        assert after.min() > before.min()  # miglioramento stretto: un optimize no-op deve far fallire il test
        assert after.min() > 0.1  # soglia assoluta di usabilita per FEM (misura di riferimento: 0.42)

        print(
            f"optimizer_used={optimizer_used} "
            f"n_before={len(before)} n_after={len(after)} "
            f"qmin_before={before.min():.6f} qmin_after={after.min():.6f}"
        )
    finally:
        gmsh.finalize()
