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


# Le due righe segnalate dall'architect come scoperte dallo Step 1.


def test_pulisci_sfera_pulita_rende_stesso_conteggio_e_true():
    v, f = _sfera()
    nv, nf, convergito = ai.pulisci_autointersezioni(v, f)
    assert convergito is True
    assert len(nf) == len(f)


def test_il_wrap_vuoto_solleva_anche_con_facce_valide(monkeypatch):
    """Wrap che esce senza facce: mesh_set finto, non una geometria cercata a mano."""

    class _MeshSetVuoto:
        def current_mesh(self):
            return self

        def bounding_box(self):
            return self

        def diagonal(self):
            return 100.0

        def apply_filter(self, *a, **k):
            pass

        def vertex_matrix(self):
            return np.zeros((0, 3))

        def face_matrix(self):
            return np.zeros((0, 3), dtype=np.int64)

    monkeypatch.setattr(ai, "_mesh_set", lambda vertices, faces: _MeshSetVuoto())
    with pytest.raises(ValueError, match="non ha prodotto facce"):
        ai.avvolgi(*_sfera(), 5.0)


# Riga «facce int64 e int32 → stesso conteggio» del contratto ingressi: nessuno
# dei 9 test sopra confronta i due dtype, la aggiungo qui.


def test_conteggio_uguale_fra_facce_int64_e_int32():
    v, f = _sfera((0.0, 0.0, -70.0))
    assert ai.conta_autointersezioni(v, f.astype(np.int64)) == ai.conta_autointersezioni(
        v, f.astype(np.int32)
    )
