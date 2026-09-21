import inspect

import numpy as np
import pytest

from meshrec.core import config, quality, synth, volume

SIZE = (100.0, 40.0, 200.0)
EXACT_VOLUME = 100.0 * 40.0 * 200.0


def test_tetrahedralize_fills_the_box():
    vertices, faces = synth.box_mesh(SIZE)
    nodes, tets = volume.tetrahedralize(
        vertices, faces, max_volume=50_000.0, min_ratio=1.8, max_steiner_points=-1, nobisect=False
    )

    assert nodes.ndim == 2 and nodes.shape[1] == 3
    assert tets.ndim == 2 and tets.shape[1] == 4
    assert len(tets) > 10
    assert tets.max() < len(nodes)


def test_sum_of_tet_volumes_equals_the_exact_volume():
    vertices, faces = synth.box_mesh(SIZE)
    nodes, tets = volume.tetrahedralize(
        vertices, faces, max_volume=50_000.0, min_ratio=1.8, max_steiner_points=-1, nobisect=False
    )

    total = np.abs(quality.tet_volumes(nodes, tets)).sum()
    assert total == pytest.approx(EXACT_VOLUME, rel=1e-6)


def test_no_inverted_elements():
    vertices, faces = synth.box_mesh(SIZE)
    nodes, tets = volume.tetrahedralize(
        vertices, faces, max_volume=50_000.0, min_ratio=1.8, max_steiner_points=-1, nobisect=False
    )

    assert len(quality.inverted_tets(nodes, tets)) == 0


def test_max_volume_controls_the_number_of_elements():
    vertices, faces = synth.box_mesh(SIZE)
    _, coarse = volume.tetrahedralize(
        vertices, faces, max_volume=200_000.0, min_ratio=1.8, max_steiner_points=-1, nobisect=False
    )
    _, fine = volume.tetrahedralize(
        vertices, faces, max_volume=20_000.0, min_ratio=1.8, max_steiner_points=-1, nobisect=False
    )

    assert len(fine) > len(coarse)


def test_an_open_surface_is_refused_before_tetgen_runs():
    """fTetWild non e' installabile su Windows: la guardia e' l'unica difesa."""
    vertices, faces = synth.box_mesh(SIZE)
    damaged = synth.punch_holes(faces)

    with pytest.raises(volume.NotWatertightError, match="4 spigoli di bordo"):
        volume.tetrahedralize(vertices, damaged, min_ratio=1.8, max_steiner_points=-1, nobisect=False)


def test_with_metrics_reports_counts_and_time():
    vertices, faces = synth.box_mesh(SIZE)

    nodes, tets, metrics = volume.tetrahedralize_with_metrics(vertices, faces, config.TetConfig())

    assert metrics["nodes"] == len(nodes)
    assert metrics["tets"] == len(tets)
    assert metrics["seconds"] > 0.0
    # Il predefinito e' il quadratico dal ripristino di #45: il manuale
    # CalculiX dice del lineare «not suited for structural calculations».
    assert metrics["element"] == "C3D10"


def test_inverted_elements_are_a_blocking_error(monkeypatch):
    """La spec chiede errore bloccante, non avviso: qui si esercita il sollevamento."""
    nodes = np.array([[0.0, 0.0, 0.0], [1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]])
    flipped = np.array([[0, 2, 1, 3]])
    monkeypatch.setattr(volume, "tetrahedralize", lambda *args, **kwargs: (nodes, flipped))

    vertices, faces = synth.box_mesh(SIZE)
    with pytest.raises(volume.InvertedElementsError, match="invertiti"):
        volume.tetrahedralize_with_metrics(vertices, faces, config.TetConfig())


class _TetGenCheFallisce:
    """TetGen che si interrompe con un messaggio scelto, senza raffinare nulla.

    La diagnosi si esercita sul messaggio, che e' l'unica cosa che la libreria
    dia: riprodurre davvero una superficie con strozzature sotto il millimetro
    costerebbe una scansione reale e trenta secondi per prova.
    """

    def __init__(self, messaggio):
        self._messaggio = messaggio

    def __call__(self, *_args, **_kwargs):
        return self

    def tetrahedralize(self, **_opzioni):
        raise RuntimeError(self._messaggio)


def test_l_invasione_delle_facce_consiglia_nobisect_e_non_un_min_ratio_piu_alto(monkeypatch):
    """`split_subface` a nobisect spento non e' un vincolo troppo severo.

    Nel raffinamento di Delaunay una faccia di ingresso viene suddivisa anche
    per **invasione** della sua sfera diametrale, e quella suddivisione ricorre
    fino alla distanza locale fra lembi opposti della superficie: dove quella
    distanza crolla, nessun valore del rapporto raggio-spigolo la ferma.
    `docs/fase-1-min-ratio.md` lo misura su `lab_frame.pcd` -- 1,8 · 2,5 · 3,0 ·
    4,0 · 6,0 e 12,0 falliscono tutti, e con `nobisect` la stessa superficie
    converge a 1,8. Il consiglio «alza min_ratio» mandava l'utente a tarare per
    ore un parametro gia' escluso come causa.

    TetGen stessa dichiara questa diagnosi nel proprio sorgente
    (`terminatetetgen`, codice 5): «Two very close input facets were detected.
    Hint: use -Y option to avoid adding Steiner points in boundary». `-Y` e'
    `nobisect`.
    """
    monkeypatch.setattr(
        volume.tetgen,
        "TetGen",
        _TetGenCheFallisce("Internal TetGen error within `split_subface`."),
    )
    vertices, faces = synth.box_mesh(SIZE)

    with pytest.raises(volume.RefinementFailedError) as caduta:
        volume.tetrahedralize(
            vertices, faces, None, min_ratio=1.8, max_steiner_points=-1, nobisect=False
        )

    messaggio = str(caduta.value)
    assert "nobisect" in messaggio
    # Il consiglio vecchio non deve sopravvivere accanto a quello nuovo: due
    # rimedi contraddittori nello stesso messaggio non sono una diagnosi.
    assert "Alza tet.min_ratio" not in messaggio


def test_a_nobisect_gia_acceso_l_invasione_non_e_piu_il_sospetto(monkeypatch):
    """Con `nobisect` acceso TetGen non suddivide le facce di ingresso.

    Consigliare di accendere una leva gia' accesa e' peggio di non consigliare
    niente: manda a cercare il difetto dove non c'e'. Qui resta il rimedio sul
    vincolo di qualita', che a quel punto e' di nuovo il sospetto principale.
    """
    monkeypatch.setattr(
        volume.tetgen,
        "TetGen",
        _TetGenCheFallisce("Internal TetGen error within `split_subface`."),
    )
    vertices, faces = synth.box_mesh(SIZE)

    with pytest.raises(volume.RefinementFailedError) as caduta:
        volume.tetrahedralize(
            vertices, faces, None, min_ratio=1.8, max_steiner_points=-1, nobisect=True
        )

    messaggio = str(caduta.value)
    assert "Alza tet.min_ratio" in messaggio
    # La minuscola rendeva l'asserzione morta: il sorgente scrive «Accendi», e
    # `in` distingue le maiuscole, quindi "accendi" non compariva in NESSUNO dei
    # tre rami e la riga era vera per ogni ingresso. Provate tutte e sei le
    # combinazioni il 31/08/2026: solo l'altra asserzione uccideva il test.
    assert "Accendi tet.nobisect" not in messaggio


def test_il_recupero_del_bordo_non_e_un_problema_di_qualita(monkeypatch):
    """`recoversubfaces` fallisce prima che il raffinamento cominci.

    E' il recupero delle facce di ingresso nella triangolazione di Delaunay: il
    vincolo raggio-spigolo non e' ancora entrato in gioco, quindi consigliarlo
    e' falso a prescindere dalla geometria. Le autointersezioni sono una
    causa, non l'unica: su runs/geoandgeo-mm fallisce anche una superficie
    che TetGen `-d` dichiara corretta.
    """
    monkeypatch.setattr(
        volume.tetgen,
        "TetGen",
        _TetGenCheFallisce("Internal TetGen error within `recoversubfaces`."),
    )
    vertices, faces = synth.box_mesh(SIZE)

    with pytest.raises(volume.RefinementFailedError) as caduta:
        volume.tetrahedralize(
            vertices, faces, None, min_ratio=1.8, max_steiner_points=-1, nobisect=False
        )

    messaggio = str(caduta.value)
    assert "Alza tet.min_ratio" not in messaggio
    assert "nobisect" not in messaggio
    assert "tet.wrap_tolerance" in messaggio
    assert "sostituita" in messaggio


def test_un_guasto_che_non_si_riconosce_non_viene_diagnosticato(monkeypatch):
    """Un messaggio ignoto tiene il rimedio generico invece di inventarne uno.

    Una diagnosi sbagliata costa piu' di nessuna diagnosi: e' il difetto che
    queste righe correggono, e ripeterlo al contrario non sarebbe un progresso.
    """
    monkeypatch.setattr(
        volume.tetgen,
        "TetGen",
        _TetGenCheFallisce("Internal TetGen error within `qualcosa_di_nuovo`."),
    )
    vertices, faces = synth.box_mesh(SIZE)

    with pytest.raises(volume.RefinementFailedError) as caduta:
        volume.tetrahedralize(
            vertices, faces, None, min_ratio=1.8, max_steiner_points=-1, nobisect=False
        )

    assert "Alza tet.min_ratio" in str(caduta.value)


def test_l_errore_originale_di_tetgen_sopravvive_a_ogni_diagnosi(monkeypatch):
    """Qualunque cosa il programma concluda, il messaggio grezzo resta leggibile.

    E' cio' che permette di smentire la diagnosi: senza, un rimedio sbagliato
    non sarebbe piu' contestabile da chi legge il registro.
    """
    vertices, faces = synth.box_mesh(SIZE)
    for grezzo in (
        "Internal TetGen error within `split_subface`.",
        "Internal TetGen error within `recoversubfaces`.",
        "Internal TetGen error within `qualcosa_di_nuovo`.",
    ):
        monkeypatch.setattr(volume.tetgen, "TetGen", _TetGenCheFallisce(grezzo))
        with pytest.raises(volume.RefinementFailedError) as caduta:
            volume.tetrahedralize(
                vertices, faces, None, min_ratio=1.8, max_steiner_points=-1, nobisect=False
            )
        assert grezzo in str(caduta.value)


def test_the_default_config_puts_no_ceiling_on_the_refinement():
    """Il tetto predefinito della libreria (100000) non deve tornare di nascosto."""
    assert config.TetConfig().max_steiner_points == -1


def test_no_processing_default_lives_in_the_signature():
    """L'unico luogo dove un parametro di elaborazione ha un predefinito e' config.

    `min_ratio: float = 1.1` nella firma contraddiceva il predefinito 1.8 di
    `TetConfig` ed era il valore che sul muro reale non converge: un chiamante
    che lo lasciava implicito otteneva un valore diverso da quello configurato.
    """
    parameters = inspect.signature(volume.tetrahedralize).parameters
    for name in ("min_ratio", "max_steiner_points", "nobisect"):
        assert parameters[name].default is inspect.Parameter.empty


def test_nobisect_leaves_the_input_surface_untouched():
    """`nobisect` vieta a TetGen di suddividere le facce di ingresso.

    E' la leva che porta a termine il raffinamento dove la scala locale della
    superficie scende sotto il millimetro (vedi docs/fase-1-min-ratio.md). Sul
    cubo l'effetto e' visibile in modo netto: senza, il bordo viene infittito e
    i nodi si moltiplicano; con, restano gli otto vertici dati piu i punti
    aggiunti all'interno.
    """
    vertices, faces = synth.box_mesh(SIZE)
    common = {"max_volume": 2_000.0, "min_ratio": 1.8, "max_steiner_points": -1}

    liberi, _ = volume.tetrahedralize(vertices, faces, nobisect=False, **common)
    vincolati, _ = volume.tetrahedralize(vertices, faces, nobisect=True, **common)

    assert len(liberi) > 10 * len(vincolati)
    conservati = {tuple(riga) for riga in np.round(vincolati, 9)}
    assert all(tuple(riga) in conservati for riga in np.round(np.asarray(vertices), 9))


def test_nobisect_can_make_the_volume_limit_inert_and_says_so():
    """Con `nobisect` il limite di volume puo' restare lettera morta.

    Se la superficie di ingresso e' grossolana, TetGen non ha punti di bordo da
    cui partire e restituisce pochi tetraedri enormi senza segnalare nulla:
    `max_volume` risulta impostato e disatteso. E' la stessa trappola di
    `fixedvolume`, e come quella va dichiarata invece che scoperta a valle.
    """
    vertices, faces = synth.box_mesh(SIZE)
    cfg = config.TetConfig(max_volume=2_000.0, nobisect=True)

    with pytest.warns(volume.IneffectiveVolumeLimitWarning):
        nodes, tets, metrics = volume.tetrahedralize_with_metrics(vertices, faces, cfg)

    assert metrics["nobisect"] is True
    assert np.abs(quality.tet_volumes(nodes, tets)).max() > cfg.max_volume

    # Il maglio che ne esce e' grossolano anche in qualita, non solo in
    # dimensione: dodici tetraedri e il 66,67% fuori dal min_ratio richiesto.
    # E' un effetto della superficie di ingresso a otto vertici, non di
    # nobisect in se: su lab_frame, dove la superficie ha 213.154 vertici,
    # nobisect lascia fuori vincolo il 9,55% degli elementi, in linea con
    # l'8,10% del muro senza nobisect.
    assert metrics["radius_edge_ratio_over_limit"] > 0.5


def test_an_exhausted_steiner_budget_is_reported_not_hidden():
    """Una mesh troncata non e' la mesh che i vincoli di qualita descrivono.

    Il budget e' fissato cosi basso da essere certamente esaurito: i punti
    aggiunti eguagliano il tetto, la metrica lo dichiara e l'avviso lo dice a
    voce. Senza questo, il troncamento resta invisibile perche' TetGen non lo
    segnala e la mesh troncata non ha elementi invertiti.
    """
    vertices, faces = synth.box_mesh(SIZE)
    cfg = config.TetConfig(max_volume=20_000.0, max_steiner_points=20)

    with pytest.warns(volume.TruncatedRefinementWarning):
        nodes, tets, metrics = volume.tetrahedralize_with_metrics(vertices, faces, cfg)

    assert metrics["steiner_saturated"] is True
    assert metrics["steiner_points"] == 20
    assert metrics["max_steiner_points"] == 20
    # I nodi **d'angolo**, non tutti i nodi. Dal ripristino del quadratico
    # (#45) il predefinito e' C3D10, e `nodes` porta anche i sei nodi di lato
    # per elemento: contarli qui diceva 126 invece di 28, cioe' misurava
    # l'ordine dell'elemento al posto del budget di raffinamento.
    import numpy as np

    assert len(np.unique(tets[:, :4])) == len(vertices) + 20


def test_without_a_ceiling_the_refinement_is_not_reported_as_truncated():
    vertices, faces = synth.box_mesh(SIZE)

    _, _, metrics = volume.tetrahedralize_with_metrics(
        vertices, faces, config.TetConfig(max_volume=20_000.0)
    )

    assert metrics["steiner_saturated"] is False
    assert metrics["max_steiner_points"] == -1


def test_the_quality_constraint_is_checked_on_the_result_not_only_requested():
    """`min_ratio` chiede un tetto al rapporto raggio-spigolo: qui si verifica.

    Dei parametri di TetConfig, `max_steiner_points` e `max_volume` erano
    controllati sul maglio prodotto e `min_ratio` no. Tre parametri di libreria
    sono gia' stati trovati impostati e inerti, tutti per caso: questo chiude la
    famiglia. La grandezza registrata e' la frazione di elementi fuori
    vincolo, che si legge senza bisogno di taratura: sul cubo vale zero, sul
    muro di riferimento 8,10 per cento.
    """
    vertices, faces = synth.box_mesh(SIZE)

    _, _, metrics = volume.tetrahedralize_with_metrics(
        vertices, faces, config.TetConfig(max_volume=20_000.0)
    )

    assert metrics["radius_edge_ratio_over_limit"] == 0.0
    assert metrics["radius_edge_ratio_p99"] < config.TetConfig().min_ratio


def test_a_mesh_the_constraint_does_not_govern_is_reported(monkeypatch):
    """Quando gli elementi fuori vincolo sono la maggioranza, si dice.

    Non e' una soglia tarata ma un'affermazione qualitativa: se il vincolo e'
    violato da piu' elementi di quanti lo rispettino, `min_ratio` non sta
    governando quel maglio. Sulle corse reali una sana ne lascia fuori l'8,10
    per cento (muro), una malata l'86,36 (lab_crop).

    La misura e' sostituita perche' fabbricare un maglio davvero cosi' cattivo
    richiederebbe di sconfiggere TetGen, che e' precisamente cio' che il
    vincolo impedisce: stessa tecnica di
    test_inverted_elements_are_a_blocking_error.
    """
    vertices, faces = synth.box_mesh(SIZE)
    nodes, tets = volume.tetrahedralize(
        vertices, faces, max_volume=50_000.0, min_ratio=1.8, max_steiner_points=-1, nobisect=False
    )
    fuori_vincolo = np.full(len(tets), 10.0)
    fuori_vincolo[: len(tets) // 4] = 1.0
    monkeypatch.setattr(volume, "radius_edge_ratios", lambda *args: fuori_vincolo)
    # `over_limit` passa ora da quality.fraction_over_ratio, che chiama la
    # radius_edge_ratios del proprio modulo: va patchata anche li', non solo
    # sul nome importato in volume.
    monkeypatch.setattr(quality, "radius_edge_ratios", lambda *args: fuori_vincolo)
    monkeypatch.setattr(volume, "tetrahedralize", lambda *args, **kwargs: (nodes, tets))

    with pytest.warns(volume.UnmetQualityConstraintWarning, match="supera il min_ratio"):
        _, _, metrics = volume.tetrahedralize_with_metrics(vertices, faces, config.TetConfig())

    assert metrics["radius_edge_ratio_over_limit"] == pytest.approx(0.75, abs=0.01)
