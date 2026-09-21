import re

import numpy as np
import open3d as o3d
import pytest

from meshrec.core import autointersezioni as ai
from meshrec.core import config, volume


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


def test_spostamento_e_deterministico():
    """`get_hausdorff_distance` di PyMeshLab (commit 64b6220, prima del fix
    round 2) non era deterministico nemmeno su campioni fissi: jitter interno
    alla libreria, non al campionamento (verificato in sessione, 21/09/2026).
    `spostamento` ora misura con `scipy.spatial.cKDTree`: stessi ingressi,
    stesso dict, byte per byte."""
    v, f = _sfera((0.0, 0.0, -70.0))
    wv, wf, _ = ai.avvolgi(v, f, 5.0)
    assert ai.spostamento(v, f, wv, wf) == ai.spostamento(v, f, wv, wf)


def test_spostamento_non_sottostima_il_polo_passante():
    """Il campionamento Montecarlo di PyMeshLab (commit 64b6220, prima del fix
    round 2) aveva trovato punti fino a 30,38 mm su questa stessa coppia (9
    chiamate, 21/09/2026: 29,39-30,38). Lo spostamento vero e' quindi
    >= 30,38 mm: un campionamento fisso troppo rado (solo
    vertici+baricentri+punti medi, ~21 mm) lo mancherebbe, e la tolleranza
    deve essere un limite vero, non un'indicazione. `passo_mm` qui e' lo
    stesso tol/5 che usa `prepara_ingresso` (vedi il suo commento: misurato
    30,82 mm, sopra soglia)."""
    v, f = _sfera((0.0, 0.0, -70.0))
    wv, wf, _ = ai.avvolgi(v, f, 5.0)
    assert ai.spostamento(v, f, wv, wf, passo_mm=5.0 / 5.0)["max"] >= 30.38


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


# prepara_ingresso (Task 3): dal brief, verbatim.


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
    """Il messaggio porta il valore misurato, sopra la tolleranza dichiarata.
    Non un regex sul primo intero: col campionamento deterministico il valore
    non è più 3x,xx per costruzione, solo > 5.0."""
    v, f = _sfera((0.0, 0.0, -70.0))
    with pytest.raises(ai.WrapOltreTolleranzaError) as caduta:
        ai.prepara_ingresso(v, f, config.TetConfig(wrap_tolerance=5.0), step_8_acceso=False)
    trovato = re.search(r"fino a ([\d,.]+) mm", str(caduta.value))
    assert trovato is not None
    assert float(trovato.group(1).replace(",", ".")) > 5.0


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


# Le 4 righe aggiunte dall'architect al contratto ingressi: nessun test sopra
# le copre (superficie non chiusa, superficie vuota col wrap acceso, residue
# del wrap che non fermano, e l'ordine dei due controlli col wrap spento).


def test_superficie_aperta_ferma_prima_del_wrap():
    v, f = _sfera()
    f_aperta = f[1:]  # una faccia tolta: bordo aperto
    with pytest.raises(volume.NotWatertightError):
        ai.prepara_ingresso(v, f_aperta, config.TetConfig(wrap_tolerance=5.0), step_8_acceso=False)


def test_superficie_senza_facce_wrap_acceso_da_notwatertight_non_valueerror():
    v = np.zeros((0, 3))
    f = np.zeros((0, 3), dtype=np.int64)
    with pytest.raises(volume.NotWatertightError, match="senza facce"):
        ai.prepara_ingresso(v, f, config.TetConfig(wrap_tolerance=5.0), step_8_acceso=False)


def test_wrap_con_residue_le_registra_senza_fermare_lo_step(monkeypatch):
    monkeypatch.setattr(ai, "conta_autointersezioni", lambda *a: 3)
    v, f = _sfera()
    _, _, misure, cambiata = ai.prepara_ingresso(
        v, f, config.TetConfig(wrap_tolerance=5.0), step_8_acceso=False
    )
    assert cambiata is True
    assert misure["wrap_applied"] is True
    assert misure["self_intersections_after"] == 3


def test_wrap_spento_superficie_aperta_con_autointersezioni_da_notwatertight():
    v, f = _sfera((0.0, 0.0, -70.0))
    f_aperta = f[1:]  # bordo aperto, oltre al polo passante
    with pytest.raises(volume.NotWatertightError):
        ai.prepara_ingresso(v, f_aperta, config.TetConfig(), step_8_acceso=False)
