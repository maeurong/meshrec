import numpy as np
import open3d as o3d
import pytest

from meshrec.core import autointersezioni as ai
from meshrec.core import config, volume


def _sfera(polo: tuple[float, float, float] | None = None, resolution: int = 20):
    """Sfera di raggio 50 mm; `polo` sposta il vertice piu' alto.

    Con polo a (0, 0, -70) il vertice attraversa la calotta opposta: 80 facce
    autointersecanti su 1520, misurato il 21/09/2026. Due cubi compenetrati NON
    servono: MeshFix li riduce a 7 vertici dichiarando successo.
    """
    sfera = o3d.geometry.TriangleMesh.create_sphere(radius=50.0, resolution=resolution)
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


def test_spostamento_coglie_il_polo_passante():
    """Il campionamento Montecarlo di PyMeshLab (commit 64b6220, prima del fix
    round 2) aveva trovato punti fino a 30,38 mm su questa stessa coppia (9
    chiamate, 21/09/2026: 29,39-30,38). Lo spostamento vero e' quindi
    >= 30,38 mm: un campionamento fisso troppo rado (solo
    vertici+baricentri+punti medi, ~21 mm) lo mancherebbe di 9 mm.

    Il massimo e' la distanza esatta sui campioni della griglia, quindi una
    stima per difetto del vero: a tol/5 (1 mm) vale 30,23 mm, a 0,5 mm 30,34,
    a 0,25 mm 30,44 (misurati l'11/10/2026, #211). La soglia a 30,0 boccia il
    campionamento rado senza chiedere alla griglia di raggiungere il valore
    vero, che da sotto non garantisce."""
    v, f = _sfera((0.0, 0.0, -70.0))
    wv, wf, _ = ai.avvolgi(v, f, 5.0)
    assert ai.spostamento(v, f, wv, wf, passo_mm=5.0 / 5.0)["max"] >= 30.0


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
    # I numeri di una prova non sono quelli della corsa dell'utente.
    assert "646" not in messaggio and "7747" not in messaggio


def test_convergenza_non_dichiarata_con_zero_residue_non_dice_zero_restano(monkeypatch):
    conteggi = iter([80, 0])
    monkeypatch.setattr(ai, "conta_autointersezioni", lambda *a: next(conteggi))
    monkeypatch.setattr(ai, "pulisci_autointersezioni", lambda v, f: (v, f, False))
    with pytest.raises(ai.AutointersezioniResidueError) as caduta:
        ai.prepara_ingresso(*_sfera(), config.TetConfig(), step_8_acceso=False)
    messaggio = str(caduta.value)
    assert "0 facce autointersecanti restano" not in messaggio
    assert "convergenza" in messaggio


def test_il_wrap_oltre_la_tolleranza_registra_lo_spostamento_e_non_ferma():
    """Tolleranza dichiarativa (decisione di Mario, 21/09/2026): sul caso reale
    il massimo viene dalle cavita' piu' strette di alpha, che il wrap chiude
    per costruzione, e col limite lo step falliva a ogni valore.

    28,0 e non 30,38 (il massimo del Montecarlo su questa coppia): qui il
    passo lo sceglie `prepara_ingresso`, ed e' lo spigolo mediano (7,85 mm
    su questa sfera grossolana), che misura 28,76. Una sottostima di qualche
    % non fa passare nulla di nascosto, la tolleranza non ferma piu'. Il
    30,38 resta nel test di `spostamento` a passo esplicito."""
    v, f = _sfera((0.0, 0.0, -70.0))
    _, _, misure, cambiata = ai.prepara_ingresso(
        v, f, config.TetConfig(wrap_tolerance=5.0), step_8_acceso=False
    )
    assert cambiata is True
    assert misure["wrap_hausdorff_max_mm"] >= 28.0
    assert misure["wrap_hausdorff_mean_mm"] <= misure["wrap_hausdorff_p95_mm"] <= misure["wrap_hausdorff_max_mm"]


def test_il_wrap_di_una_superficie_senza_ingombro_e_un_valueerror_leggibile():
    """Tutti i vertici coincidenti: la diagonale e' 0 e la percentuale di
    PyMeshLab sarebbe una divisione per zero, non un messaggio."""
    v = np.zeros((4, 3))
    f = np.array([[0, 2, 1], [0, 1, 3], [0, 3, 2], [1, 2, 3]], dtype=np.int64)
    with pytest.raises(ValueError, match="diagonale"):
        ai.prepara_ingresso(v, f, config.TetConfig(wrap_tolerance=5.0), step_8_acceso=False)


def test_una_tolleranza_minuscola_non_fa_esplodere_la_misura(monkeypatch):
    """Il passo e' tol/5 ma mai sotto lo spigolo mediano dell'ingresso: con
    tol 1e-6 il passo tol/5 chiederebbe ~500 000 punti per faccia (tetto
    1000 suddivisioni), centinaia di milioni sulla sfera."""
    import time

    v, f = _sfera()
    lati = np.linalg.norm(v[f] - v[np.roll(f, 1, axis=1)], axis=2)
    monkeypatch.setattr(ai, "avvolgi", lambda v, f, tol: (v, f, {"wrap_alpha_mm": tol}))
    vero = ai.spostamento

    def controllato(*args, passo_mm):
        assert passo_mm >= float(np.median(lati))
        return vero(*args, passo_mm=passo_mm)

    monkeypatch.setattr(ai, "spostamento", controllato)
    avvio = time.perf_counter()
    _, _, misure, _ = ai.prepara_ingresso(
        v, f, config.TetConfig(wrap_tolerance=1e-6), step_8_acceso=False
    )
    assert time.perf_counter() - avvio < 30.0
    assert misure["wrap_hausdorff_max_mm"] == pytest.approx(0.0, abs=1e-9)


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
    assert misure["meshfix_clean_converged"] is None


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


# Fix round 3: i campioni di spostamento a lotti (finding b, round 2). Round 2
# costruiva tutti i campioni in un colpo solo (`np.vstack`); su una mesh reale
# (1-4 M facce, spigoli 10-20 mm, passo tol/5) sono centinaia di milioni di
# punti, OOM.


def test_spostamento_con_facce_enormi_e_passo_piccolo_non_esplode():
    """Esempio del finding: 2 triangoli da 1000 mm di spigolo, passo 0,1 —
    senza il tetto e senza lotti, miliardi di punti. Qui deve solo finire,
    in fretta, senza MemoryError."""
    v = np.array(
        [[0.0, 0.0, 0.0], [1000.0, 0.0, 0.0], [1000.0, 1000.0, 0.0], [0.0, 1000.0, 0.0]]
    )
    f = np.array([[0, 1, 2], [0, 2, 3]], dtype=np.int64)
    risultato = ai.spostamento(v, f, v, f, passo_mm=0.1)
    assert risultato["max"] == pytest.approx(0.0, abs=1e-6)


def test_i_lotti_di_campioni_restano_sotto_il_budget_anche_su_molte_facce():
    """La mesh reale del finding ha 1-4 M facce uniformi (10-20 mm), non
    poche facce enormi: e' il totale che esplode, non una singola faccia.
    Qui una sfera con tante facce piccole e un passo che le costringe a piu'
    di un lotto: ogni lotto deve restare sotto il budget, il totale no —
    e' la prova che il picco di memoria dipende dal lotto."""
    v, f = _sfera(resolution=80)
    lotti = list(ai._lotti_di_campioni(v, f, 0.3))
    assert len(lotti) > 1
    assert sum(len(lotto) for lotto in lotti) > ai._PUNTI_PER_LOTTO_CAMPIONI
    for lotto in lotti:
        assert len(lotto) <= ai._PUNTI_PER_LOTTO_CAMPIONI


def test_spostamento_e_indipendente_dalla_dimensione_del_lotto(monkeypatch):
    """Una faccia o un lotto parziale finale non deve cambiare il risultato:
    stessa mesh, lotto piu' piccolo. I massimi identici; le medie a meno
    dell'ultimo bit, perche' la somma e' esatta per lotto, non fra lotti."""
    v, f = _sfera((0.0, 0.0, -70.0))
    wv, wf, _ = ai.avvolgi(v, f, 5.0)
    con_lotto_grande = ai.spostamento(v, f, wv, wf, passo_mm=1.0)
    monkeypatch.setattr(ai, "_PUNTI_PER_LOTTO_CAMPIONI", 500)
    con_lotto_piccolo = ai.spostamento(v, f, wv, wf, passo_mm=1.0)
    for chiave in ("max_a_verso_b", "max_b_verso_a", "max"):
        assert con_lotto_grande[chiave] == con_lotto_piccolo[chiave]
    assert con_lotto_grande["mean"] == pytest.approx(con_lotto_piccolo["mean"], rel=1e-12)


def test_nessun_campione_da_media_zero():
    v, f = _sfera()
    vuoti_v, vuoti_f = np.empty((0, 3)), np.empty((0, 3), dtype=np.int64)
    massimo, media, distanze = ai._distanza_massima_e_media(vuoti_v, vuoti_f, 1.0, v, f)
    assert (massimo, media, len(distanze)) == (0.0, 0.0, 0)


# Issue #211: la distanza punto-superficie deve essere esatta, non un limite
# superiore dato dai soli 8 centroidi piu' vicini. Oracolo: forza bruta su tutte
# le facce con la stessa proiezione esatta.


def _forza_bruta(punti, v, f):
    a, b, c = v[f[:, 0]], v[f[:, 1]], v[f[:, 2]]
    return ai._punto_piu_vicino_su_triangolo(punti[:, None, :], a[None], b[None], c[None]).min(axis=1)


def _grande_fra_piccoli():
    """Un triangolo da 300 mm in z=0 (centroide a (100, 100, 0)) e una
    griglia di triangoli da 1 mm in z=5 sopra il suo angolo: per i punti
    vicini all'angolo, a 0,5 mm dal triangolo grande, gli 8 centroidi piu'
    vicini sono tutti piccoli, a ~4,5 mm."""
    v = [[0.0, 0.0, 0.0], [300.0, 0.0, 0.0], [0.0, 300.0, 0.0]]
    f = [[0, 1, 2]]
    for x in range(-5, 6):
        for y in range(-5, 6):
            i = len(v)
            v += [[x, y, 5.0], [x + 1.0, y, 5.0], [x, y + 1.0, 5.0]]
            f.append([i, i + 1, i + 2])
    return np.array(v), np.array(f, dtype=np.int64)


def test_la_faccia_piu_vicina_fuori_dagli_8_centroidi_si_trova():
    v, f = _grande_fra_piccoli()
    xy = np.stack(np.meshgrid(np.linspace(0.5, 3.0, 6), np.linspace(0.5, 3.0, 6)), axis=-1).reshape(-1, 2)
    punti = np.column_stack([xy, np.full(len(xy), 0.5)])
    vero = _forza_bruta(punti, v, f)
    assert vero.max() == pytest.approx(0.5)
    np.testing.assert_allclose(ai._distanza_punti_a_superficie(punti, v, f), vero, rtol=0, atol=1e-9)


def test_distanza_di_nessun_punto_e_vuota():
    v, f = _sfera()
    assert len(ai._distanza_punti_a_superficie(np.empty((0, 3)), v, f)) == 0


def test_distanza_verso_una_sola_faccia_e_esatta():
    v = np.array([[0.0, 0.0, 0.0], [10.0, 0.0, 0.0], [0.0, 10.0, 0.0]])
    f = np.array([[0, 1, 2]], dtype=np.int64)
    punti = np.array([[1.0, 1.0, 3.0], [20.0, 0.0, 0.0], [-4.0, -3.0, 0.0]])
    np.testing.assert_allclose(ai._distanza_punti_a_superficie(punti, v, f), [3.0, 10.0, 5.0], atol=1e-12)


def test_triangoli_degeneri_danno_distanza_finita_ed_esatta():
    v, f = _sfera()
    n = len(v)
    v = np.vstack([v, [[0.0, 0.0, 60.0], [10.0, 0.0, 60.0], [20.0, 0.0, 60.0], [5.0, 5.0, 70.0]]])
    f = np.vstack([f, [[n, n + 1, n + 2], [n + 3, n + 3, n + 3]]])  # collineare, coincidente
    rng = np.random.default_rng(0)
    punti = rng.uniform(-80.0, 80.0, size=(500, 3))
    d = ai._distanza_punti_a_superficie(punti, v, f)
    assert np.isfinite(d).all()
    np.testing.assert_allclose(d, _forza_bruta(punti, v, f), rtol=0, atol=1e-9)


def test_un_triangolo_da_149_mm_fra_facce_da_35_non_alza_il_picco_di_memoria(monkeypatch):
    """Le misure delle superfici reali di #211: lato mediano 35 mm, massimo
    149. Punti fino a 100 mm dal piano, cosi' k deve crescere: ogni blocco
    resta sotto `_LOTTO_PUNTI * _CANDIDATI_PER_PUNTO` coppie punto-faccia,
    e il risultato resta quello della forza bruta."""
    xs = np.arange(11) * 35.0
    gx, gy = np.meshgrid(xs, xs, indexing="ij")
    v = np.column_stack([gx.ravel(), gy.ravel(), np.zeros(gx.size)])
    i = (np.arange(10)[:, None] * 11 + np.arange(10)[None, :]).ravel()
    f = np.vstack([np.column_stack([i, i + 11, i + 1]), np.column_stack([i + 1, i + 11, i + 12])])
    v = np.vstack([v, [[20.0, 20.0, 1.0], [169.0, 20.0, 1.0], [20.0, 169.0, 1.0]]])
    f = np.vstack([f, [[len(v) - 3, len(v) - 2, len(v) - 1]]]).astype(np.int64)
    punti = np.random.default_rng(1).uniform([-50.0, -50.0, -20.0], [400.0, 400.0, 100.0], size=(1000, 3))

    monkeypatch.setattr(ai, "_LOTTO_PUNTI", 100)
    tetto = ai._LOTTO_PUNTI * ai._CANDIDATI_PER_PUNTO
    vera, blocchi = ai._punto_piu_vicino_su_triangolo, []

    def contata(p, a, b, c):
        blocchi.append(a.shape[0] * a.shape[1])
        return vera(p, a, b, c)

    monkeypatch.setattr(ai, "_punto_piu_vicino_su_triangolo", contata)
    d = ai._distanza_punti_a_superficie(punti, v, f)
    assert max(blocchi) <= tetto
    np.testing.assert_allclose(d, _forza_bruta(punti, v, f), rtol=0, atol=1e-9)


@pytest.mark.filterwarnings("error")
def test_facce_tutte_di_raggio_zero_non_dividono_per_zero():
    """Ogni faccia e' un punto: mediana di r_f = 0, la classe di taglia non
    deve dividere per zero (RuntimeWarning reso errore)."""
    v = np.random.default_rng(2).uniform(-10.0, 10.0, size=(20, 3))
    f = np.repeat(np.arange(20)[:, None], 3, axis=1).astype(np.int64)
    punti = np.random.default_rng(3).uniform(-15.0, 15.0, size=(50, 3))
    np.testing.assert_allclose(ai._distanza_punti_a_superficie(punti, v, f), _forza_bruta(punti, v, f), rtol=0, atol=1e-9)


def test_il_tetto_di_memoria_regge_quando_k_cresce_oltre_il_blocco(monkeypatch):
    """Punti lontani da una griglia di facce uguali (una classe sola): k deve
    arrivare a tutte le 800 facce. Raddoppiando, il salto di k supera da solo
    il tetto di coppie per blocco; deve crescere a passi che ci stanno."""
    xs = np.arange(21) * 10.0
    gx, gy = np.meshgrid(xs, xs, indexing="ij")
    v = np.column_stack([gx.ravel(), gy.ravel(), np.zeros(gx.size)])
    i = (np.arange(20)[:, None] * 21 + np.arange(20)[None, :]).ravel()
    f = np.vstack([np.column_stack([i, i + 21, i + 1]), np.column_stack([i + 1, i + 21, i + 22])]).astype(np.int64)
    punti = np.array([[100.0, 100.0, 500.0], [0.0, 0.0, 300.0], [-200.0, 50.0, 400.0]])

    monkeypatch.setattr(ai, "_LOTTO_PUNTI", 1)
    tetto = ai._LOTTO_PUNTI * ai._CANDIDATI_PER_PUNTO
    vera, blocchi = ai._punto_piu_vicino_su_triangolo, []

    def contata(p, a, b, c):
        blocchi.append(a.shape[0] * a.shape[1])
        return vera(p, a, b, c)

    monkeypatch.setattr(ai, "_punto_piu_vicino_su_triangolo", contata)
    d = ai._distanza_punti_a_superficie(punti, v, f)
    assert max(blocchi) <= tetto
    np.testing.assert_allclose(d, _forza_bruta(punti, v, f), rtol=0, atol=1e-9)


def test_distanza_verso_una_superficie_senza_facce_solleva():
    with pytest.raises(ValueError, match="senza facce"):
        ai._distanza_punti_a_superficie(np.zeros((3, 3)), np.zeros((0, 3)), np.zeros((0, 3), dtype=np.int64))
