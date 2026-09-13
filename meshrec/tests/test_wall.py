"""Il prior geometrico: terna del pezzo, celle, spessore locale, regioni.

Ogni verifica ha una geometria sintetica a verita' nota dietro: il numero di
membrature atteso viene dal banco di prova e mai dal codice, che deve poter
girare su una geometria che non ha mai visto.
"""

from __future__ import annotations

import numpy as np
import pytest

from meshrec.core import synth, wall
from meshrec.core.config import SegmentConfig, WallConfig

# Un telaio sintetico: due montanti, un traverso in alto, uno in basso. Sei
# numeri che stanno qui, nel banco, e in nessun file di src/.
#
# Le quattro sezioni (l'estensione in y di ciascun prisma, cioe' lo spessore
# che scomponi() sorveglia) sono deliberatamente tutte diverse fra loro. La
# scomposizione separa le membrature per costanza dello spessore locale: con
# quattro sezioni uguali il banco non proverebbe nulla, perche' un algoritmo
# che fonde tutto in una regione sola passerebbe la prova tanto quanto uno che
# separa correttamente (e' proprio il caso limite verificato piu' sotto da
# test_una_sezione_uniforme_smentisce_la_separazione_per_spessore). I valori
# sono del banco, scelti per essere ben distanti oltre la tolleranza relativa
# predefinita fra ogni coppia di membrature che si toccano a un nodo, non le
# sezioni del provino di laboratorio: quelle vivono nella configurazione del
# Task 15. Ogni sezione e' centrata sull'origine in y (invece che appoggiata a
# y=0): mantiene la simmetria per riflessione attorno a y che il telaio a
# sezione uniforme ha per costruzione, cosi' la terna stimata dalla SVD trova
# ancora y come trasversale in modo esatto e non solo approssimato.
TELAIO = [
    ((0.0, -90.0, 0.0), (200.0, 180.0, 1600.0)),        # montante sinistro
    ((1400.0, -130.0, 0.0), (200.0, 260.0, 1600.0)),    # montante destro
    ((0.0, -70.0, 1600.0), (1600.0, 140.0, 300.0)),     # traverso superiore
    ((0.0, -170.0, -300.0), (1600.0, 340.0, 300.0)),    # traverso inferiore
]
SPAZIATURA = 20.0

# Due montanti a quattro metri l'uno dall'altro: nessuna delle due entra
# nell'altra, e nessun traverso le lega. Il banco degli incontri che non ci
# sono. Le due sezioni restano diverse fra loro, come nel TELAIO, perche' la
# scomposizione separa per costanza dello spessore locale.
MEMBRATURE_LONTANE = [
    ((0.0, -100.0, 0.0), (200.0, 200.0, 1600.0)),
    ((4000.0, -150.0, 0.0), (200.0, 300.0, 1600.0)),
]


def _cfg() -> WallConfig:
    return WallConfig()


def test_la_terna_mette_la_direzione_trasversale_per_ultima():
    """Il telaio e' sottile in y: la terna deve riconoscerlo dal dato, non da
    un asse scelto a mano."""
    punti = synth.sample_frame_surface(TELAIO, SPAZIATURA)
    direzioni, centro = wall.terna(punti)

    assert direzioni.shape == (3, 3)
    assert centro.shape == (3,)
    trasversale = direzioni[2]
    assert abs(abs(trasversale[1]) - 1.0) < 1e-6, f"trasversale attesa lungo y, e' {trasversale}"
    # terna ortonormale destrorsa: e' la condizione perche' u, v, n siano un
    # sistema di riferimento e non tre direzioni qualunque
    assert np.linalg.det(direzioni) == pytest.approx(1.0, abs=1e-9)


def test_la_terna_ha_lo_stesso_verso_su_due_esecuzioni_e_su_una_nuvola_rimescolata():
    """Il verso di una direzione principale e' arbitrario per la SVD: senza
    convenzione due esecuzioni sulla stessa nuvola darebbero assi opposti, e
    ogni indice derivato dalla terna dipenderebbe dall'ordine dei punti."""
    punti = synth.sample_frame_surface(TELAIO, SPAZIATURA)
    rimescolati = punti[np.random.default_rng(0).permutation(len(punti))]

    prima, _ = wall.terna(punti)
    dopo, _ = wall.terna(rimescolati)
    assert prima == pytest.approx(dopo, abs=1e-9)


def test_le_celle_sono_indici_non_negativi_misurati_dal_minimo():
    piano = np.array([[0.0, 0.0], [10.0, 0.0], [0.0, 25.0], [-5.0, -5.0]])
    celle = wall.chiavi_di_cella(piano, lato=5.0)

    assert celle.dtype == np.int64
    assert (celle >= 0).all()
    assert celle.shape == (4, 2)
    # il minimo cade nella cella (0, 0); 10 mm a destra del minimo sono tre celle
    assert celle[3].tolist() == [0, 0]
    assert celle[0].tolist() == [1, 1]


def test_lo_spessore_locale_di_una_scatola_e_la_sua_dimensione_sottile():
    """La grandezza sorvegliata e' lo spessore, e su una scatola nota vale la
    dimensione sottile: se non lo fa, ogni regione trovata piu' avanti misura
    un'altra cosa."""
    punti = synth.sample_box_surface((400.0, 180.0, 900.0), SPAZIATURA)
    direzioni, centro = wall.terna(punti)
    centrati = punti - centro
    piano = centrati @ direzioni[:2].T
    trasversale = centrati @ direzioni[2]

    celle, spessori, _ = wall.spessore_per_cella(piano, trasversale, lato=4.0 * SPAZIATURA)

    assert len(celle) == len(spessori)
    # le celle interne alla faccia larga vedono le due facce a 180 mm di distanza
    assert np.median(spessori) == pytest.approx(180.0, abs=1.5 * SPAZIATURA)


def test_il_pavimento_viene_scartato_come_piano_e_non_come_quota():
    """Il pavimento e' un piano quasi orizzontale esteso oltre l'ingombro del
    pezzo. Scartarlo con una soglia di quota sarebbe tarare una costante sulla
    scansione di oggi; qui viene scartato per cio' che e'."""
    telaio = synth.sample_frame_surface(TELAIO, SPAZIATURA)
    pavimento = synth.sample_box_surface((4000.0, 3000.0, 10.0), SPAZIATURA * 2.0)
    pavimento = pavimento + np.array([-1200.0, -1400.0, -320.0])
    punti = np.vstack([telaio, pavimento])

    puliti, maschera, metriche = wall.scarta_pavimento(punti, SegmentConfig(), _cfg(), SPAZIATURA)

    assert metriche["pavimento_trovato"] is True
    assert len(puliti) < len(punti)
    # nessun punto sotto il piede del telaio sintetico resta in circolazione
    assert puliti[:, 2].min() > -320.0
    assert puliti[:, 2].min() == pytest.approx(-300.0, abs=3.0 * SPAZIATURA)
    # la maschera e' il contratto che permette di tradurre un indice dentro
    # `puliti` in un indice dentro `punti`: deve avere una spunta per ogni
    # punto tenuto e nessuna per quelli tolti col pavimento.
    assert maschera.shape == (len(punti),)
    assert maschera.dtype == bool
    assert maschera.sum() == len(puliti)
    np.testing.assert_array_equal(punti[maschera], puliti)


def test_senza_pavimento_non_ne_viene_inventato_uno():
    """Il controllo che smentisce il precedente: su una nuvola che pavimento
    non ha, la funzione non deve togliere una faccia del pezzo scambiandola per
    tale."""
    punti = synth.sample_frame_surface(TELAIO, SPAZIATURA)

    puliti, maschera, metriche = wall.scarta_pavimento(punti, SegmentConfig(), _cfg(), SPAZIATURA)

    assert metriche["pavimento_trovato"] is False
    assert len(puliti) == len(punti)
    assert maschera.all(), "senza pavimento nessun punto va tolto"


def test_una_scatola_da_una_sola_membratura():
    """La prova che la scomposizione non inventa membrature dove non ce ne
    sono. Il numero atteso viene dal banco, non dal codice."""
    punti = synth.sample_box_surface((400.0, 180.0, 1200.0), SPAZIATURA)

    regioni, metriche, *_ = wall.scomponi(punti, SegmentConfig(), _cfg(), SPAZIATURA)

    assert len(regioni) == 1
    assert metriche["regioni_trovate"] == 1


def test_un_telaio_sintetico_da_le_membrature_che_ha():
    """Quattro prismi di tre sezioni diverse: la scomposizione deve separarli
    per costanza dello spessore, e i due montanti identici, che sono disgiunti
    nel piano, restano due regioni e non una."""
    punti = synth.sample_frame_surface(TELAIO, SPAZIATURA)

    regioni, metriche, *_ = wall.scomponi(punti, SegmentConfig(), _cfg(), SPAZIATURA)

    assert metriche["regioni_trovate"] == len(regioni)
    assert 2 <= len(regioni) <= 6, (
        f"attese fra 2 e 6 regioni sui quattro prismi del banco, trovate {len(regioni)}: "
        "sotto, la scomposizione fonde membrature diverse; sopra, le frammenta"
    )
    # ogni punto sta in al piu' una regione: una regione non ruba punti a un'altra
    tutti = np.concatenate(regioni)
    assert len(tutti) == len(np.unique(tutti))


def test_l_ordine_delle_regioni_non_dipende_dall_ordine_dei_punti():
    """Quinto vincolo di prodotto: un ordine e' un esito discreto e deve essere
    funzione del dato. E' la stessa lezione gia' pagata sull'ordine dei voxel di
    Open3D fra Windows x86-64 e macOS arm64."""
    punti = synth.sample_frame_surface(TELAIO, SPAZIATURA)
    rimescolati = punti[np.random.default_rng(1).permutation(len(punti))]

    prima, *_ = wall.scomponi(punti, SegmentConfig(), _cfg(), SPAZIATURA)
    dopo, *_ = wall.scomponi(rimescolati, SegmentConfig(), _cfg(), SPAZIATURA)

    assert len(prima) == len(dopo)
    # confronto per insieme di coordinate, non per indice: gli indici puntano a
    # due ordinamenti diversi della stessa nuvola
    for regione_prima, regione_dopo in zip(prima, dopo, strict=True):
        a = np.unique(np.round(punti[regione_prima], 6), axis=0)
        b = np.unique(np.round(rimescolati[regione_dopo], 6), axis=0)
        assert a.shape == b.shape
        assert a == pytest.approx(b)


def test_la_tolleranza_di_spessore_decide_fra_una_regione_e_due():
    """Il test che morde davvero la soglia, e non solo la connettivita'.

    Due prismi identici a parte lo spessore, affiancati e a contatto (nessun
    vuoto fra le celle): se la differenza di spessore sta sotto
    `thickness_tolerance` in relativo, `regioni` li deve fondere in una
    regione sola; se sta sopra, li deve separare in due. Le due differenze
    sono derivate da `WallConfig.thickness_tolerance` invece che scritte come
    numeri che «funzionano», cosi' il test segue il predefinito se cambia
    invece di rompersi in silenzio. E' il confronto -- stesso confine
    geometrico, tolleranza sotto contro sopra -- a dimostrare che e' la
    tolleranza a decidere: un `regioni` che ignorasse `thickness_tolerance` e
    facesse solo componenti connesse fonderebbe entrambi i casi in una regione
    sola, e solo il secondo assert lo smentirebbe."""
    tolleranza = _cfg().thickness_tolerance
    base = 200.0

    def scomponi_con_spessore(spessore_secondo_prisma: float) -> tuple[list[np.ndarray], dict]:
        prismi = [
            ((0.0, 0.0, 0.0), (600.0, base, 500.0)),
            ((600.0, 0.0, 0.0), (600.0, spessore_secondo_prisma, 500.0)),
        ]
        punti = synth.sample_frame_surface(prismi, SPAZIATURA)
        regioni, metriche, *_ = wall.scomponi(punti, SegmentConfig(), _cfg(), SPAZIATURA)
        return regioni, metriche

    sotto_soglia = base * (1.0 + tolleranza / 2.0)  # scarto relativo meta' della tolleranza
    sopra_soglia = base * (1.0 + tolleranza * 3.0)  # scarto relativo tre volte la tolleranza

    regioni_fuse, metriche_fuse = scomponi_con_spessore(sotto_soglia)
    assert len(regioni_fuse) == 1
    assert metriche_fuse["regioni_trovate"] == 1

    regioni_separate, metriche_separate = scomponi_con_spessore(sopra_soglia)
    assert len(regioni_separate) == 2
    assert metriche_separate["regioni_trovate"] == 2


def test_una_sezione_uniforme_e_un_canarino_per_la_separazione_per_orientamento():
    """Non e' una prova di correttezza dell'algoritmo attuale: e' un canarino.

    La scomposizione separa le membrature per costanza dello spessore locale.
    Un telaio a sezione uniforme e' un anello fisicamente continuo con
    spessore identico ovunque, quindi restituisce una regione sola per pura
    geometria -- lo farebbe anche un `regioni` che ignorasse del tutto
    `thickness_tolerance` e facesse solo componenti connesse. Questo test da
    solo non dimostra che la tolleranza lavora (per quello vedi
    `test_la_tolleranza_di_spessore_decide_fra_una_regione_e_due`): dichiara
    invece il confine del metodo attuale, che non separa membrature adiacenti
    a sezione uguale (qui un piedritto e una trave, uniti a Π). Non e' un
    risultato falso in silenzio: una regione a Π non e' un prisma, e il
    riempimento di sezione del Task 3 la dichiara «vuoto» con la propria misura
    (vedi `test_la_regione_a_pi_esce_vuota_e_affidabile_invece_di_essere_scartata`),
    perche' chi costruisce possa rifiutarla. Il giorno in cui qualcuno implementasse la separazione per
    orientamento locale (vedi il commento `ponytail:` su `regioni` in
    `wall.py`), e' questo test che smettera' di passare, ed e' il segnale
    giusto per riscriverlo."""
    telaio_a_sezione_uniforme = [
        ((0.0, 0.0, 0.0), (200.0, 200.0, 1600.0)),      # montante sinistro
        ((1400.0, 0.0, 0.0), (200.0, 200.0, 1600.0)),   # montante destro
        ((0.0, 0.0, 1600.0), (1600.0, 200.0, 300.0)),   # traverso superiore
        ((0.0, 0.0, -300.0), (1600.0, 200.0, 300.0)),   # traverso inferiore
    ]
    punti = synth.sample_frame_surface(telaio_a_sezione_uniforme, SPAZIATURA)

    regioni, metriche, *_ = wall.scomponi(punti, SegmentConfig(), _cfg(), SPAZIATURA)

    assert len(regioni) == 1
    assert metriche["regioni_trovate"] == 1


def test_il_contorno_di_un_rettangolo_ha_quattro_vertici():
    """Il contorno misurato non deve portare nella mesh il rumore dello
    scanner: un rettangolo campionato fitto resta un rettangolo."""
    lato_u = np.linspace(0.0, 200.0, 60)
    lato_v = np.linspace(0.0, 140.0, 40)
    bordo = np.vstack([
        np.column_stack([lato_u, np.zeros_like(lato_u)]),
        np.column_stack([lato_u, np.full_like(lato_u, 140.0)]),
        np.column_stack([np.zeros_like(lato_v), lato_v]),
        np.column_stack([np.full_like(lato_v, 200.0), lato_v]),
    ])

    contorno = wall.semplifica_contorno(bordo, tolleranza=5.0)

    assert len(contorno) == 4, f"attesi 4 vertici, trovati {len(contorno)}"
    assert contorno.min(axis=0) == pytest.approx([0.0, 0.0], abs=1e-9)
    assert contorno.max(axis=0) == pytest.approx([200.0, 140.0], abs=1e-9)


def test_il_contorno_semplificato_non_perde_area_oltre_la_tolleranza():
    """Il controllo che smentisce il precedente: semplificare e' lecito finche'
    l'area della sezione non cambia piu' di quanto la tolleranza consenta."""
    angoli = np.linspace(0.0, 2.0 * np.pi, 400, endpoint=False)
    cerchio = np.column_stack([100.0 * np.cos(angoli), 100.0 * np.sin(angoli)])

    contorno = wall.semplifica_contorno(cerchio, tolleranza=2.0)

    def area(poligono):
        x, y = poligono[:, 0], poligono[:, 1]
        return 0.5 * abs(np.dot(x, np.roll(y, -1)) - np.dot(y, np.roll(x, -1)))

    assert len(contorno) < len(cerchio)
    assert area(contorno) == pytest.approx(area(cerchio), rel=0.05)


def test_la_misura_di_un_prisma_noto_ritrova_sezione_asse_e_lunghezza():
    """Verita' nota del banco: un prisma 200 x 140 lungo 1500 lungo z."""
    punti = synth.sample_box_surface((200.0, 140.0, 1500.0), 15.0)
    direzioni, _ = wall.terna(punti)

    membratura = wall.misura(punti, direzioni, _cfg())

    assert membratura.lunghezza == pytest.approx(1500.0, abs=30.0)
    lunga, corta = sorted(membratura.sezione, reverse=True)
    assert lunga == pytest.approx(200.0, abs=15.0)
    assert corta == pytest.approx(140.0, abs=15.0)
    assert abs(abs(membratura.asse[2]) - 1.0) < 1e-3, "asse atteso verticale"
    assert membratura.fuori_piombo_deg == pytest.approx(0.0, abs=1.0)
    assert membratura.volume == pytest.approx(200.0 * 140.0 * 1500.0, rel=0.15)


def test_la_membratura_restituisce_una_sezione_per_fetta_con_la_propria_quota():
    """Le venti fette che `misura` gia' calcola per la dispersione escono dalla
    funzione: sono le stazioni su cui il modello a telaio poggia.

    Su un prisma a sezione costante le sezioni di fetta sono tutte uguali fra
    loro e uguali alla sezione complessiva; il test verifica la forma e
    l'accordo, non un valore fabbricato.
    """
    punti = synth.sample_box_surface((200.0, 140.0, 1500.0), 15.0)
    direzioni, _ = wall.terna(punti)

    membratura = wall.misura(punti, direzioni, _cfg())

    assert membratura.sezioni_fette.ndim == 2
    assert membratura.sezioni_fette.shape[1] == 2
    assert len(membratura.quote_fette) == len(membratura.sezioni_fette)
    assert len(membratura.sezioni_fette) > 1, "una sola fetta non e' una stazione"
    # le quote crescono lungo l'asse e stanno dentro la lunghezza misurata
    assert np.all(np.diff(membratura.quote_fette) > 0.0)
    assert membratura.quote_fette.min() >= 0.0
    assert membratura.quote_fette.max() <= membratura.lunghezza
    # su un prisma costante ogni fetta vede la sezione del pezzo
    assert np.allclose(membratura.sezioni_fette, np.asarray(membratura.sezione), rtol=0.05)


def test_la_base_del_piano_di_sezione_esce_dalla_misura_ed_e_ortonormale():
    """`misura` costruisce gia' e1 ed e2 e le tiene per se'. Senza di loro
    nessuno puo' collocare una barra nel piano della sezione: sono il dato che
    trasforma due estensioni in una geometria.
    """
    punti = synth.sample_box_surface((200.0, 140.0, 1500.0), 15.0)
    direzioni, _ = wall.terna(punti)

    membratura = wall.misura(punti, direzioni, _cfg())
    base = membratura.base_sezione

    assert base.shape == (2, 3)
    assert np.allclose(np.linalg.norm(base, axis=1), 1.0), "e1 ed e2 devono essere versori"
    assert abs(float(base[0] @ base[1])) < 1e-9, "e1 ed e2 devono essere ortogonali"
    assert np.allclose(base @ membratura.asse, 0.0, atol=1e-9), (
        "il piano di sezione e' ortogonale all'asse"
    )


def test_la_base_resta_ortonormale_anche_se_la_trasversale_e_parallela_all_asse():
    """Ingresso degenere: `direzioni[2]` quasi parallela all'asse della
    regione. Il ramo di ripiego su `direzioni[0]` esiste gia' in `misura`; qui
    si prova che la base che ne esce e' ortonormale come l'altra, invece di
    nascere da una divisione per una norma quasi nulla.
    """
    punti = synth.sample_box_surface((1500.0, 200.0, 140.0), 15.0)
    direzioni, _ = wall.terna(punti)
    assert abs(float(np.dot(direzioni[2], np.array([1.0, 0.0, 0.0])))) < 0.9, (
        "il banco vale solo se la trasversale non e' gia' quella lunga"
    )
    # la terna e' del pezzo intero: la si forza col caso che il ramo copre,
    # trasversale allineata all'asse della regione
    forzata = np.vstack([direzioni[2], direzioni[1], direzioni[0]])

    membratura = wall.misura(punti, forzata, _cfg())
    base = membratura.base_sezione

    assert base.shape == (2, 3)
    assert np.all(np.isfinite(base))
    assert np.allclose(np.linalg.norm(base, axis=1), 1.0)
    assert abs(float(base[0] @ base[1])) < 1e-9
    assert np.allclose(base @ membratura.asse, 0.0, atol=1e-9)


def test_una_regione_con_meno_di_venti_fette_utili_non_ne_dichiara_venti():
    """Ingresso degenere: cinque punti sparsi. Le fette povere sono gia'
    scartate da `misura` (meno di quattro punti, nessuna misura inventata), e
    il numero di stazioni restituito deve essere quello vero -- fosse anche
    zero -- non venti righe fabbricate per riempire la forma.
    """
    punti_pochi = np.array([
        [0.0, 0.0, 0.0],
        [10.0, 0.0, 0.0],
        [0.0, 10.0, 0.0],
        [0.0, 0.0, 10.0],
        [10.0, 10.0, 10.0],
    ])
    direzioni, _ = wall.terna(punti_pochi)

    membratura = wall.misura(punti_pochi, direzioni, _cfg())

    assert len(membratura.sezioni_fette) < 20
    assert membratura.sezioni_fette.shape[1] == 2, (
        "anche vuoto l'array resta (n, 2): chi lo legge non deve indovinare la forma"
    )
    assert len(membratura.quote_fette) == len(membratura.sezioni_fette)


def test_una_fetta_di_area_nulla_e_un_risultato_che_si_mostra():
    """Ingresso degenere: un prisma sano con in coda un filamento di punti
    allineati sull'asse. L'ultima fetta li vede da sola e misura estensione
    nulla in entrambe le direzioni, cioe' area nulla. E' una misura da
    mostrare, non un errore che ferma: chi costruisce decide, chi misura
    riporta.
    """
    scatola = synth.sample_box_surface((200.0, 140.0, 1500.0), 15.0)
    quote = np.linspace(1520.0, 1600.0, 6)
    # sull'asse di simmetria trasversale della scatola: fuori da li' il
    # filamento sposterebbe la direzione principale e la fetta leggerebbe uno
    # sbieco invece dello zero che il banco vuole provare
    filamento = np.column_stack([
        np.full_like(quote, 100.0),
        np.full_like(quote, 70.0),
        quote,
    ])
    punti = np.vstack([scatola, filamento])
    direzioni, _ = wall.terna(punti)

    membratura = wall.misura(punti, direzioni, _cfg())

    aree = membratura.sezioni_fette[:, 0] * membratura.sezioni_fette[:, 1]
    assert len(aree) > 0, "le fette esistono anche quando la loro area e' nulla"
    assert float(aree.min()) == pytest.approx(0.0, abs=1e-9)


def test_il_fuori_piombo_misura_l_inclinazione_e_il_rigonfiamento_no():
    """Le due grandezze restano distinte perche' sono difetti diversi: un
    elemento puo' essere perfettamente piano e tutto storto, oppure a piombo e
    panciuto. Un prisma inclinato di 4 gradi ha fuori piombo e non pancia."""
    punti = synth.sample_box_surface((200.0, 140.0, 1500.0), 15.0)
    angolo = np.radians(4.0)
    rotazione = np.array([
        [1.0, 0.0, 0.0],
        [0.0, np.cos(angolo), -np.sin(angolo)],
        [0.0, np.sin(angolo), np.cos(angolo)],
    ])
    inclinati = punti @ rotazione.T
    direzioni, _ = wall.terna(inclinati)

    membratura = wall.misura(inclinati, direzioni, _cfg())

    assert membratura.fuori_piombo_deg == pytest.approx(4.0, abs=1.0)
    assert np.abs(membratura.rigonfiamento).max() < 20.0, (
        "un prisma inclinato ma dritto non deve risultare panciuto: se lo "
        "risulta, il rigonfiamento sta misurando l'inclinazione"
    )


@pytest.mark.parametrize("gradi", [0.0, 4.0])
def test_il_rigonfiamento_non_dipende_dall_ultima_cifra_dei_punti(gradi):
    """Esito discreto che dipendeva dal giro: su Windows lo stesso prisma
    inclinato dava rigonfiamento 0 in un giro e 31,1 nel successivo. Le facce
    di testa stanno esattamente sul bordo dell'ultima cella lungo l'asse, e un
    errore d'arrotondamento all'ultima cifra ne mandava una parte in una riga
    in piu', dove il massimo non trova la faccia. Rimescolare i punti o
    spostarli di un miliardesimo di mm riproduce lo stesso arrotondamento
    anche dove BLAS e' deterministico. Tolleranza dichiarata: 1e-6 mm."""
    punti = synth.sample_box_surface((200.0, 140.0, 1500.0), 15.0)
    angolo = np.radians(gradi)
    rotazione = np.array([
        [1.0, 0.0, 0.0],
        [0.0, np.cos(angolo), -np.sin(angolo)],
        [0.0, np.sin(angolo), np.cos(angolo)],
    ])
    base = punti @ rotazione.T
    rng = np.random.default_rng(0)
    varianti = [base, base]
    varianti += [base[rng.permutation(len(base))] for _ in range(5)]
    varianti += [base + rng.normal(0.0, 1e-9, base.shape) for _ in range(5)]

    mappe = []
    for variante in varianti:
        direzioni, _ = wall.terna(variante)
        membratura = wall.misura(variante, direzioni, _cfg())
        assert membratura.fuori_piombo_deg == pytest.approx(gradi, abs=1.0)
        assert np.abs(membratura.rigonfiamento).max() < 20.0
        mappe.append(np.sort(membratura.rigonfiamento))

    np.testing.assert_array_equal(mappe[0], mappe[1])
    for mappa in mappe[2:]:
        assert mappa == pytest.approx(mappe[0], abs=1e-6)


def test_un_prisma_dritto_col_rumore_del_rilievo_passa_il_parallelismo():
    """La riga fantasma in coda alla griglia non e' solo un difetto di
    Windows: con 1 mm di rumore l'ultima riga raccoglie i pochi punti della
    testa che sporgono, il massimo li' non trova la faccia e il parallelismo di
    un prisma dritto oscillava fra 0,1 e 5,5 gradi a seconda del seme, oltre
    la soglia di 5 su un seme su dieci (il primo e' 25), su ogni piattaforma.
    Trenta semi fissi: il generatore PCG64 da' gli stessi numeri ovunque."""
    punti = synth.sample_box_surface((200.0, 140.0, 1500.0), 15.0)
    for seme in range(30):
        rumorosi = punti + np.random.default_rng(seme).normal(0.0, 1.0, punti.shape)
        direzioni, _ = wall.terna(rumorosi)

        membratura = wall.misura(rumorosi, direzioni, _cfg())

        esito = wall.controlla(membratura, _cfg())["parallelismo"]
        assert esito["passato"] is True, f"seme {seme}: {esito['valore']:.2f} gradi"


def test_il_rigonfiamento_e_una_mappa_e_trova_la_pancia_dove_c_e():
    """Il controllo che smentisce il precedente: una faccia gonfiata di 25 mm
    al centro deve comparire nella mappa, e nel fuori piombo no."""
    punti = synth.sample_box_surface((200.0, 140.0, 1500.0), 15.0)
    sulla_faccia = np.isclose(punti[:, 1], 140.0)
    altezza_relativa = (punti[:, 2] - 750.0) / 750.0
    gonfiati = punti.copy()
    gonfiati[sulla_faccia, 1] += 25.0 * (1.0 - altezza_relativa[sulla_faccia] ** 2)
    direzioni, _ = wall.terna(gonfiati)

    membratura = wall.misura(gonfiati, direzioni, _cfg())

    assert membratura.rigonfiamento.ndim == 1
    assert len(membratura.rigonfiamento) > 10, "il rigonfiamento e' una mappa, non un numero"
    assert np.abs(membratura.rigonfiamento).max() > 10.0
    assert membratura.fuori_piombo_deg == pytest.approx(0.0, abs=1.5)


def test_i_controlli_intrinseci_passano_su_un_prisma_pulito():
    punti = synth.sample_box_surface((200.0, 140.0, 1500.0), 15.0)
    direzioni, _ = wall.terna(punti)
    membratura = wall.misura(punti, direzioni, _cfg())

    esiti = wall.controlla(membratura, _cfg())

    assert set(esiti) == {"parallelismo", "copertura_faccia", "costanza_sezione"}
    for nome, esito in esiti.items():
        assert esito["passato"] is True, f"{nome} non doveva fallire: {esito}"
        assert "valore" in esito and "soglia" in esito, (
            f"{nome} deve dire quale numero lo ha deciso, non solo se e' passato"
        )


def test_una_regione_a_sezione_variabile_non_e_un_prisma_e_lo_dice():
    """Il controllo che smentisce il prior: un tronco di piramide non e' una
    membratura, e viene riportato come tale invece di essere spacciato per una
    con la sezione media."""
    z = np.linspace(0.0, 1500.0, 120)
    punti = []
    for quota in z:
        mezzo_lato = 100.0 * (1.0 - 0.6 * quota / 1500.0)
        angoli = np.linspace(0.0, 2.0 * np.pi, 40, endpoint=False)
        punti.append(np.column_stack([
            mezzo_lato * np.cos(angoli),
            mezzo_lato * np.sin(angoli),
            np.full_like(angoli, quota),
        ]))
    cono = np.vstack(punti)
    direzioni, _ = wall.terna(cono)
    membratura = wall.misura(cono, direzioni, _cfg())

    esiti = wall.controlla(membratura, _cfg())

    assert esiti["costanza_sezione"]["passato"] is False
    assert esiti["costanza_sezione"]["valore"] > esiti["costanza_sezione"]["soglia"]


def test_senza_riscontri_dichiarati_il_prior_non_inventa_un_aspettativa():
    """Su un pezzo nuovo i riscontri non esistono per definizione. Il prior
    riporta cio' che ha trovato, e nel posto dell'atteso non mette un numero."""
    punti = synth.sample_frame_surface(TELAIO, SPAZIATURA)

    esito = wall.prior(punti, SegmentConfig(), _cfg(), SPAZIATURA)

    riscontri = esito["riscontri"]
    assert riscontri["membrature_attese"] is None
    assert riscontri["volume_atteso"] is None
    assert riscontri["scarto_membrature"] is None
    assert riscontri["scarto_volume"] is None
    assert esito["membrature"], "il prior deve comunque riportare cio' che ha trovato"


def test_con_i_riscontri_dichiarati_il_prior_riporta_lo_scarto():
    """I numeri dell'atteso stanno qui, nel test, dove e' legittimo che
    compaiano: sono dati del caso, non del programma."""
    punti = synth.sample_frame_surface(TELAIO, SPAZIATURA)
    volume_vero = sum(dx * dy * dz for _origine, (dx, dy, dz) in TELAIO)
    cfg = WallConfig(membrature_attese=4, volume_atteso=volume_vero)

    esito = wall.prior(punti, SegmentConfig(), cfg, SPAZIATURA)

    riscontri = esito["riscontri"]
    assert riscontri["membrature_attese"] == 4
    assert riscontri["scarto_membrature"] == len(esito["membrature"]) - 4
    assert riscontri["volume_atteso"] == pytest.approx(volume_vero)
    assert riscontri["scarto_volume"] is not None


def test_l_esito_del_prior_e_serializzabile_in_json():
    """Lo step 12 lo scrive su disco e il server lo manda al browser: un array
    di numpy dentro il dizionario romperebbe entrambi dopo l'intera corsa."""
    import json

    punti = synth.sample_frame_surface(TELAIO, SPAZIATURA)
    esito = wall.prior(punti, SegmentConfig(), _cfg(), SPAZIATURA)

    testo = json.dumps(esito)
    assert json.loads(testo)["regioni_trovate"] == esito["regioni_trovate"]


def test_cede_chi_ha_l_asse_invaso_e_non_chi_ha_l_indice_piu_basso():
    """Ruling AD: cede la membratura che finisce dentro l'altra, come una trave
    appoggiata su un pilastro accorcia il pilastro e non la trave. Il criterio
    e' del dato, non dell'ordine in cui le membrature arrivano.
    """
    invaso = np.array([True, True, False, False])
    libero = np.zeros(4, dtype=bool)

    # il candidato 7 ha l'asse invaso dentro il 3: cede il 7
    cede, resta, campionamento = wall.ruoli_dell_incontro(invaso, libero, 7, 3)
    assert (cede, resta) == (7, 3)
    assert campionamento is invaso

    # rovesciato: e' il 3 ad avere l'asse invaso dentro il 7, quindi cede il 3
    cede, resta, campionamento = wall.ruoli_dell_incontro(libero, invaso, 7, 3)
    assert (cede, resta) == (3, 7)
    assert campionamento is invaso


def test_a_pari_invasione_lo_spareggio_non_dipende_dall_ordine():
    """Entrambi invasi o nessuno invaso: decide l'ordine che il chiamante ha
    gia' stabilito per area, e la funzione non lo ribalta.
    """
    entrambi = np.array([True, False])
    cede, resta, _ = wall.ruoli_dell_incontro(entrambi, entrambi, 7, 3)
    assert (cede, resta) == (7, 3), "a pari invasione cede il candidato, non il maggiore"

    nessuno = np.zeros(2, dtype=bool)
    cede, resta, _ = wall.ruoli_dell_incontro(nessuno, nessuno, 7, 3)
    assert (cede, resta) == (7, 3)


def test_il_nodo_e_la_proiezione_sull_asse_di_chi_resta():
    """Su una geometria rilevata gli assi non si intersecano quasi mai: passano
    vicini e si scansano. Il nodo e' la proiezione di chi cede sull'asse di chi
    resta -- il traverso continuo col montante che vi si innesta.
    """
    # traverso lungo x a quota z=3000; montante verticale che gli passa
    # accanto, scansato di 40 mm lungo y
    origine_resta = np.array([0.0, 0.0, 3000.0])
    asse_resta = np.array([1.0, 0.0, 0.0])
    origine_cede = np.array([1000.0, 40.0, 0.0])
    asse_cede = np.array([0.0, 0.0, 1.0])

    nodo, distanza, limitato = wall.nodo_di_giunzione(
        origine_cede, asse_cede, 3000.0, origine_resta, asse_resta, 2000.0
    )

    # il nodo sta sull'asse del traverso, quindi a y = 0 e z = 3000
    assert np.allclose(nodo, np.array([1000.0, 0.0, 3000.0]), atol=1e-9)
    # e il montante ha dovuto spostarsi dei 40 mm di cui era scansato
    assert distanza == pytest.approx(40.0, abs=1e-9)
    assert limitato is False


def test_assi_che_si_incontrano_davvero_danno_distanza_nulla():
    """Il caso ideale non e' un caso speciale: la stessa formula lo copre, e la
    distanza dice da sola che non c'e' stato nessuno spostamento.
    """
    nodo, distanza, limitato = wall.nodo_di_giunzione(
        np.array([1000.0, 0.0, 0.0]),
        np.array([0.0, 0.0, 1.0]),
        3000.0,
        np.array([0.0, 0.0, 3000.0]),
        np.array([1.0, 0.0, 0.0]),
        2000.0,
    )
    assert np.allclose(nodo, np.array([1000.0, 0.0, 3000.0]), atol=1e-9)
    assert distanza == pytest.approx(0.0, abs=1e-9)
    assert limitato is False


def test_due_assi_paralleli_non_dividono_per_zero():
    """Ingresso degenere: due membrature complanari con assi paralleli. Il nodo
    e' una proiezione ortogonale, non l'intersezione di due rette: la formula
    non ha il seno dell'angolo a denominatore e su assi paralleli restituisce
    numeri finiti invece di NaN.
    """
    nodo, distanza, limitato = wall.nodo_di_giunzione(
        np.array([500.0, 0.0, 0.0]),
        np.array([1.0, 0.0, 0.0]),
        1000.0,
        np.array([0.0, 250.0, 0.0]),
        np.array([1.0, 0.0, 0.0]),
        2000.0,
    )

    assert np.all(np.isfinite(nodo))
    assert np.isfinite(distanza)
    assert limitato is False
    # la proiezione ortogonale di un estremo su una parallela dista quanto le
    # due rette: 250 mm, il vero scarto fra gli assi
    assert distanza == pytest.approx(250.0, abs=1e-9)


def _membratura_di_prova(origine, asse, lunghezza, sezione, base_sezione):
    """Una `Membratura` costruita a mano, per i banchi degli incontri.

    Il contorno e' il rettangolo della sezione centrato sull'origine: e' la
    forma che `misura` produce su una nuvola simmetrica, e tenerla esplicita
    qui rende visibile quale ancoraggio il predicato di invasione usa.
    """
    mezza = np.asarray(sezione, dtype=np.float64) / 2.0
    contorno = mezza * np.array([[-1.0, -1.0], [1.0, -1.0], [1.0, 1.0], [-1.0, 1.0]])
    return wall.Membratura(
        punti=np.arange(0),
        asse=np.asarray(asse, dtype=np.float64),
        origine=np.asarray(origine, dtype=np.float64),
        lunghezza=float(lunghezza),
        sezione=tuple(float(valore) for valore in sezione),
        sezione_dispersione=(0.0, 0.0),
        contorno=contorno,
        fuori_piombo_deg=0.0,
        asse_ideale=np.asarray(asse, dtype=np.float64),
        scarto_asse_deg=0.0,
        rigonfiamento=np.zeros(4),
        volume=0.0,
        riempimento_sezione=1.0,
        riempimento_stato="pieno",
        densita_dispersione=0.0,
        base_sezione=np.asarray(base_sezione, dtype=np.float64),
    )


_TRAVE_X = ([0.0, 0.0, 0.0], [1.0, 0.0, 0.0], 1000.0, (100.0, 100.0), [[0, 1, 0], [0, 0, 1]])


def test_una_colonna_che_attraversa_una_trave_dichiara_l_attraversamento():
    """`hexa.taglia_giunzioni` solleva su un attraversamento; qui no: il prior
    rileva e non valida. Ma un attraversamento non e' un incontro a T, e senza
    il tipo il record mostrerebbe «spostamento 400 mm» -- mezza colonna -- su
    un incontro geometricamente esatto.
    """
    trave = _membratura_di_prova(*_TRAVE_X)
    colonna = _membratura_di_prova(
        [500.0, 0.0, -400.0], [0.0, 0.0, 1.0], 800.0, (100.0, 100.0), [[1, 0, 0], [0, 1, 0]]
    )

    incontri = wall.giunzioni([trave, colonna])

    assert len(incontri) == 1
    assert incontri[0]["tipo_incontro"] == "attraversamento"
    assert incontri[0]["distanza_proiezione"] == pytest.approx(400.0, abs=1e-6)


def test_una_membratura_contenuta_in_un_altra_non_diventa_un_incontro_a_t():
    """L'altro caso su cui `hexa` solleva: nessun estremo da accorciare. Qui il
    record esce lo stesso, perche' un'anomalia geometrica e' un risultato da
    mostrare, ma dice che cos'e'.
    """
    trave = _membratura_di_prova(*_TRAVE_X)
    dentro = _membratura_di_prova(
        [400.0, 0.0, 0.0], [1.0, 0.0, 0.0], 200.0, (40.0, 40.0), [[0, 1, 0], [0, 0, 1]]
    )

    incontri = wall.giunzioni([trave, dentro])

    assert len(incontri) == 1
    assert incontri[0]["tipo_incontro"] == "contenimento"


def test_un_incontro_a_un_estremo_e_dichiarato_tale():
    """Il caso normale, che i due sopra devono restare capaci di distinguere:
    la colonna arriva da sotto e si ferma dentro la trave.
    """
    trave = _membratura_di_prova(*_TRAVE_X)
    colonna = _membratura_di_prova(
        [500.0, 0.0, -800.0], [0.0, 0.0, 1.0], 800.0, (100.0, 100.0), [[1, 0, 0], [0, 1, 0]]
    )

    incontri = wall.giunzioni([trave, colonna])

    assert len(incontri) == 1
    assert incontri[0]["tipo_incontro"] == "estremo"


def test_due_travi_che_si_sovrappongono_danno_un_nodo_dentro_il_pezzo():
    """Il rilievo 1 visto dal record intero e non dalla sola funzione: il nodo
    scritto sta sul segmento di chi resta, e il record porta il campo che dice
    se e' stato limitato.
    """
    prima = _membratura_di_prova(*_TRAVE_X)
    seconda = _membratura_di_prova(
        [900.0, 0.0, -45.0], [1.0, 0.0, 0.01], 600.0, (100.0, 100.0), [[0, 1, 0], [0, 0, 1]]
    )

    incontri = wall.giunzioni([prima, seconda])

    assert len(incontri) == 1
    nodo = np.asarray(incontri[0]["nodo"])
    lungo = float((nodo - prima.origine) @ prima.asse)
    assert 0.0 <= lungo <= prima.lunghezza, "il nodo deve stare sul pezzo su cui si proietta"
    assert "nodo_limitato" in incontri[0]


def test_il_prisma_di_prova_e_ancorato_al_centro_del_contorno_e_non_all_origine():
    """Una colonna 100 x 100 x 1000 vista da due sole facce: il caso normale di
    uno scanner, non un caso limite. L'origine sta sull'asse del **baricentro**
    della nuvola, che su una nuvola asimmetrica non e' il centro della sezione,
    e `sezione` e' un `ptp` e non una semiestensione simmetrica.

    Misurato: col prisma ancorato all'origine nuda il 4,76% dei punti della
    regione cade fuori dal prisma con cui il predicato di invasione decide, ed
    e' materiale vero dichiarato aria. Ancorando al centro del contorno --
    quello che `hexa.prisma_di` gia' fa -- la frazione va a zero.
    """
    passo = 10.0
    lato, altezza = 100.0, 1000.0

    def griglia(a, b):
        na, nb = int(round(a / passo)) + 1, int(round(b / passo)) + 1
        u, v = np.meshgrid(np.linspace(0.0, a, na), np.linspace(0.0, b, nb), indexing="ij")
        return u.ravel(), v.ravel()

    u, v = griglia(lato, altezza)
    faccia_x = np.column_stack([np.zeros_like(u), u, v])
    faccia_y = np.column_stack([u, np.zeros_like(u), v])
    punti = np.unique(np.round(np.vstack([faccia_x, faccia_y]), 9), axis=0)

    direzioni, _ = wall.terna(punti)
    colonna = wall.misura(punti, direzioni, _cfg())
    colonna.punti = np.arange(len(punti))

    # la sonda corre lungo l'asse della colonna, appoggiata alla faccia vera
    # sul lato in cui il baricentro e' spostato: e' dentro il materiale, e il
    # predicato deve dirlo.
    trasversale = (punti - colonna.origine) @ colonna.base_sezione.T
    estremo = trasversale[:, 0].min()
    sonda = _membratura_di_prova(
        colonna.origine + colonna.base_sezione[0] * (estremo + 1.0) + colonna.asse * 10.0,
        colonna.asse,
        altezza - 20.0,
        (10.0, 10.0),
        colonna.base_sezione,
    )

    assert wall._baricentrica_invasa(sonda, colonna).any(), (
        "la sonda sta sulla faccia misurata della colonna: è materiale, non aria"
    )

    # e l'oracolo diretto: nessun punto della regione fuori dal prisma di prova
    centro = (colonna.contorno.min(axis=0) + colonna.contorno.max(axis=0)) / 2.0
    semi = np.asarray(colonna.sezione) / 2.0
    tolleranza = 1e-9
    fuori = np.abs(trasversale - centro) > semi + tolleranza
    assert not fuori.any(), "il prisma con cui si decide deve contenere i punti misurati"


def test_il_nodo_non_cade_fuori_dal_pezzo_su_cui_si_proietta():
    """Due travi quasi allineate che si sovrappongono. Scegliere l'estremo di
    chi cede sulla distanza dalla **retta** infinita di chi resta prendeva
    l'estremo lontano e proiettava 500 mm oltre la fine del pezzo: il telaio
    sarebbe nato su un nodo che non sta su nessuna membratura.

    Misurato prima della correzione: `nodo = [1499.97, 0, 0]` con
    `distanza_proiezione = 39.0`, mentre la sovrapposizione vera sta in
    `x` fra 900 e 1000.
    """
    nodo, distanza, limitato = wall.nodo_di_giunzione(
        np.array([900.0, 0.0, -45.0]),
        np.array([1.0, 0.0, 0.01]),
        600.0,
        np.array([0.0, 0.0, 0.0]),
        np.array([1.0, 0.0, 0.0]),
        1000.0,
    )

    assert 0.0 <= nodo[0] <= 1000.0, "il nodo deve stare sul segmento, non sulla retta"
    assert np.allclose(nodo, np.array([900.0, 0.0, 0.0]), atol=1e-9)
    assert distanza == pytest.approx(45.0, abs=1e-9)
    assert limitato is False


def test_un_estremo_oltre_la_fine_di_chi_resta_limita_il_nodo_e_lo_dichiara():
    """Un montante che comincia 10 mm oltre il capo del traverso. Il nodo va
    limitato al capo -- fuori dal pezzo non e' un nodo -- ma il limite e' un
    dato: dice che i due pezzi si scavalcano invece di incontrarsi, e chi
    disegna il telaio deve poterlo mostrare.
    """
    nodo, distanza, limitato = wall.nodo_di_giunzione(
        np.array([1010.0, 0.0, 0.0]),
        np.array([0.0, 0.0, 1.0]),
        300.0,
        np.array([0.0, 0.0, 0.0]),
        np.array([1.0, 0.0, 0.0]),
        1000.0,
    )

    assert np.allclose(nodo, np.array([1000.0, 0.0, 0.0]), atol=1e-9)
    assert distanza == pytest.approx(10.0, abs=1e-9)
    assert limitato is True


def test_il_contatto_a_meta_campata_misura_l_estremo_e_non_lo_scarto_del_giunto():
    """Il contatto sta a meta' della colonna, non a un suo capo: il numero che
    esce e' la distanza dell'estremo piu' vicino dal pezzo di chi resta, cioe'
    mezza colonna, e non lo scostamento di un giunto.

    I due banchi che c'erano avevano entrambi il contatto su un estremo, dove
    le due letture coincidono e la differenza non si vede.
    """
    nodo, distanza, limitato = wall.nodo_di_giunzione(
        np.array([500.0, 0.0, -400.0]),
        np.array([0.0, 0.0, 1.0]),
        800.0,
        np.array([0.0, 0.0, 0.0]),
        np.array([1.0, 0.0, 0.0]),
        1000.0,
    )

    assert np.allclose(nodo, np.array([500.0, 0.0, 0.0]), atol=1e-9)
    assert distanza == pytest.approx(400.0, abs=1e-9), "meta' colonna, non lo scarto del giunto"
    assert limitato is False


def test_il_prior_scrive_le_sezioni_di_fetta_e_la_base_in_json():
    """Il prior finisce su disco e nel browser: le misure nuove devono uscire
    come tipi JSON, non come array numpy.
    """
    import json

    punti = synth.sample_frame_surface(TELAIO, SPAZIATURA)

    esito = wall.prior(punti, SegmentConfig(), _cfg(), SPAZIATURA)
    voce = esito["membrature"][0]

    assert isinstance(voce["sezioni_fette"], list)
    assert all(isinstance(coppia, list) and len(coppia) == 2 for coppia in voce["sezioni_fette"])
    assert isinstance(voce["quote_fette"], list)
    assert len(voce["quote_fette"]) == len(voce["sezioni_fette"])
    assert isinstance(voce["base_sezione"], list)
    assert len(voce["base_sezione"]) == 2
    assert all(len(riga) == 3 for riga in voce["base_sezione"])
    # la prova che conta: l'intero esito e' serializzabile
    json.dumps(esito)


def test_il_prior_scrive_le_giunzioni_col_nodo_e_la_distanza():
    """L'adiacenza e' una misura del prior come l'asse e la sezione: chi
    costruisce un telaio la legge da `12_wall.json` invece di ricalcolarla.
    """
    import json

    punti = synth.sample_frame_surface(TELAIO, SPAZIATURA)

    esito = wall.prior(punti, SegmentConfig(), _cfg(), SPAZIATURA)

    assert "giunzioni" in esito
    assert len(esito["giunzioni"]) >= 1, "due membrature che si toccano fanno una giunzione"
    incontro = esito["giunzioni"][0]
    assert set(incontro) >= {
        "cede",
        "resta",
        "nodo",
        "distanza_proiezione",
        "nodo_limitato",
        "tipo_incontro",
    }
    assert incontro["cede"] != incontro["resta"]
    assert isinstance(incontro["nodo_limitato"], bool)
    assert incontro["tipo_incontro"] in {"estremo", "attraversamento", "contenimento"}
    assert 0 <= incontro["cede"] < len(esito["membrature"])
    assert 0 <= incontro["resta"] < len(esito["membrature"])
    assert len(incontro["nodo"]) == 3
    assert incontro["distanza_proiezione"] >= 0.0
    json.dumps(esito)


def test_membrature_che_non_si_toccano_non_fanno_giunzioni():
    """Una giunzione inventata fra due pezzi lontani sarebbe un telaio che sta
    in piedi su un legame che non esiste.
    """
    punti = synth.sample_frame_surface(MEMBRATURE_LONTANE, SPAZIATURA)

    esito = wall.prior(punti, SegmentConfig(), _cfg(), SPAZIATURA)

    assert len(esito["membrature"]) == 2, (
        "il banco vale solo se le due membrature lontane sono state trovate entrambe"
    )
    assert esito["giunzioni"] == []


def test_senza_membrature_le_giunzioni_sono_la_lista_vuota_e_non_mancano():
    """Ingresso degenere, la classe piu' frequente di questo repository:
    l'insieme vuoto che schianta invece di dichiarare. Nessuna membratura vuol
    dire nessuna giunzione, e la chiave c'e' lo stesso.
    """
    assert wall.giunzioni([]) == []


def test_una_sola_membratura_non_fa_giunzioni_e_non_avvisa():
    """Ingresso degenere: una membratura sola non e' «non legata», e' sola.
    Un avviso qui sarebbe rumore su una scatola, che e' il caso normale del
    prior su un pezzo che non e' un telaio.
    """
    import warnings

    punti = synth.sample_box_surface((200.0, 140.0, 1500.0), 15.0)
    direzioni, _ = wall.terna(punti)
    sola = wall.misura(punti, direzioni, _cfg())

    with warnings.catch_warnings():
        warnings.simplefilter("error")
        assert wall.giunzioni([sola]) == []


def test_l_ordine_delle_giunzioni_non_dipende_dall_ordine_dei_punti():
    """Quinto vincolo di prodotto: un ordine e' un esito discreto e deve essere
    funzione del dato, non della piattaforma. Stessa lezione gia' pagata
    sull'ordine dei voxel di Open3D fra Windows x86-64 e macOS arm64.
    """
    punti = synth.sample_frame_surface(TELAIO, SPAZIATURA)
    rimescolati = punti[np.random.default_rng(7).permutation(len(punti))]

    prima = wall.prior(punti, SegmentConfig(), _cfg(), SPAZIATURA)["giunzioni"]
    dopo = wall.prior(rimescolati, SegmentConfig(), _cfg(), SPAZIATURA)["giunzioni"]

    assert len(prima) == len(dopo)
    # gli indici, che sono l'unico esito discreto in ballo: `regioni` dichiara
    # e mantiene l'ordine canonico, quindi `cede` e `resta` numerano la stessa
    # cosa nelle due corse. Il nodo e la distanza sono grandezze continue, che
    # PRODUCT.md:22-26 esclude esplicitamente da questa norma.
    assert [(v["cede"], v["resta"]) for v in prima] == [(v["cede"], v["resta"]) for v in dopo]
    assert [v["tipo_incontro"] for v in prima] == [v["tipo_incontro"] for v in dopo]


def test_prior_non_scarta_il_pavimento_due_volte(monkeypatch):
    """F11 del giro di correzione finale: wall.prior chiamava scarta_pavimento
    direttamente, e scomponi lo richiamava una seconda volta con gli stessi
    argomenti -- extract_planes pagato due volte sulla stessa nuvola. Stessa
    storia per terna(puliti): calcolata da scomponi, scartata da prior e
    rifatta -- due SVD sull'intera nuvola ripulita. scomponi ora restituisce
    anche puliti/tenuti/direzioni, e prior li riusa invece di ricalcolarli.

    Mutazione che deve morire: in `prior`, richiamare `scarta_pavimento` o
    `terna` invece di leggerli dal risultato di `scomponi` -- il conteggio
    sotto tornerebbe a 2.
    """
    punti = synth.sample_frame_surface(TELAIO, SPAZIATURA)

    chiamate = {"scarta_pavimento": 0, "terna": 0}
    originale_scarta = wall.scarta_pavimento
    originale_terna = wall.terna

    def spia_scarta(*args, **kwargs):
        chiamate["scarta_pavimento"] += 1
        return originale_scarta(*args, **kwargs)

    def spia_terna(*args, **kwargs):
        chiamate["terna"] += 1
        return originale_terna(*args, **kwargs)

    monkeypatch.setattr(wall, "scarta_pavimento", spia_scarta)
    monkeypatch.setattr(wall, "terna", spia_terna)

    wall.prior(punti, SegmentConfig(), _cfg(), SPAZIATURA)

    assert chiamate["scarta_pavimento"] == 1, "scarta_pavimento pagato piu' di una volta"
    assert chiamate["terna"] == 1, "terna (SVD) pagata piu' di una volta"


def test_il_controllo_di_chiusura_del_volume_confronta_somma_e_unione():
    """Le membrature si compenetrano alle giunzioni: se la somma dei volumi
    supera quello dell'unione oltre la tolleranza, c'e' doppio conteggio, ed e'
    un errore che nessuna metrica di qualita' della mesh vedrebbe."""
    punti = synth.sample_frame_surface(TELAIO, SPAZIATURA)

    esito = wall.prior(punti, SegmentConfig(), _cfg(), SPAZIATURA)

    chiusura = esito["chiusura_volume"]
    assert chiusura["somma"] > 0.0
    assert chiusura["unione"] > 0.0
    assert isinstance(chiusura["passato"], bool)
    assert chiusura["scarto_relativo"] == pytest.approx(
        (chiusura["somma"] - chiusura["unione"]) / chiusura["unione"]
    )


TELAIO_A_SEZIONE_UNIFORME = [
    ((0.0, 0.0, 0.0), (200.0, 200.0, 1600.0)),      # montante sinistro
    ((1400.0, 0.0, 0.0), (200.0, 200.0, 1600.0)),   # montante destro
    ((0.0, 0.0, 1600.0), (1600.0, 200.0, 300.0)),   # traverso superiore
    ((0.0, 0.0, -300.0), (1600.0, 200.0, 300.0)),   # traverso inferiore
]

# Il banco a densita' bimodale dei due controesempi della terza review: un
# pezzo scansionato da un lato solo. La faccia che guarda lo scanner e' presa
# alla risoluzione piena dello strumento, le pareti che scappano di taglio sono
# sfiorate di striscio e vengono via venti volte piu' rade. Venti e' il
# rapporto di un'incidenza radente attorno agli 87 gradi: non un numero scelto
# per far cadere una soglia, ma il caso che una scansione da un lato solo
# produce per forza.
DENSITA_BIMODALE = (300.0, 300.0, 1500.0)
PASSO_RADO = 100.0
PASSO_FITTO = 5.0


def _faccia_fitta(
    dimensioni: tuple[float, float, float], asse_fisso: int, quota: float, passo: float
) -> np.ndarray:
    """Una faccia rettangolare del parallelepipedo, campionata al passo dato."""
    resto = [indice for indice in range(3) if indice != asse_fisso]
    lati = [dimensioni[indice] for indice in resto]
    numeri = [max(2, int(round(lato / passo)) + 1) for lato in lati]
    u, v = np.meshgrid(
        np.linspace(0.0, lati[0], numeri[0]),
        np.linspace(0.0, lati[1], numeri[1]),
        indexing="ij",
    )
    punti = np.zeros((u.size, 3))
    punti[:, resto[0]] = u.ravel()
    punti[:, resto[1]] = v.ravel()
    punti[:, asse_fisso] = quota
    return punti


def _prisma_a_densita_bimodale(facce_fitte: list[tuple[int, float]]) -> np.ndarray:
    """Prisma pieno con alcune facce fitte e tutte le altre rade."""
    rado = synth.sample_box_surface(DENSITA_BIMODALE, PASSO_RADO)
    fitte = [
        _faccia_fitta(DENSITA_BIMODALE, asse, quota, PASSO_FITTO) for asse, quota in facce_fitte
    ]
    return np.unique(np.round(np.vstack([rado, *fitte]), 9), axis=0)


def test_la_regione_a_pi_esce_vuota_e_affidabile_invece_di_essere_scartata():
    """Ruling J: il riempimento misura e dichiara, non scarta.

    La scomposizione fonde due membrature adiacenti a sezione uguale in una
    regione sola a forma di Π (vedi
    `test_una_sezione_uniforme_e_un_canarino_per_la_separazione_per_orientamento`).
    Quella regione non e' un prisma, e il riempimento e' la sola grandezza che
    lo vede: la dispersione e l'estensione, entrambe di bounding box, non
    vedono il vuoto al centro perche' i due piedritti attraversano tutta
    l'altezza e tengono l'ingombro pieno da un capo all'altro.

    Ma vederlo non e' scartarlo. La regione resta fra le membrature con lo
    stato «vuoto» e la misura dichiarata affidabile: e' esattamente
    l'informazione con cui chi costruisce i modelli parametrici (Task 8) puo'
    rifiutarla, senza ricalcolare nulla."""
    punti = synth.sample_frame_surface(TELAIO_A_SEZIONE_UNIFORME, SPAZIATURA)

    esito = wall.prior(punti, SegmentConfig(), _cfg(), SPAZIATURA)

    assert esito["regioni_trovate"] == 1, "il banco deve restare il caso limite: una regione a Π sola"
    assert esito["scartate"] == [], (
        f"il riempimento non scarta piu' nessuno: {esito['scartate']}"
    )
    assert len(esito["membrature"]) == 1
    riempimento = esito["membrature"][0]["riempimento"]
    assert riempimento["stato"] == "vuoto", riempimento
    assert riempimento["affidabile"] is True, riempimento
    assert riempimento["valore"] < riempimento["soglia"]


def test_le_membrature_piene_del_telaio_escono_piene():
    """Il controllo che smentisce il controllo: il telaio a sezioni diverse del
    Task 2 e' fatto di prismi veri, nessuno cavo, e ogni regione deve uscire
    «pieno» -- non basta che nessuna sia scartata, perche' ora il riempimento
    non scarta piu' nessuno e un esito sbagliato passerebbe inosservato."""
    punti = synth.sample_frame_surface(TELAIO, SPAZIATURA)

    esito = wall.prior(punti, SegmentConfig(), _cfg(), SPAZIATURA)

    assert esito["scartate"] == [], f"nessuna membratura del telaio doveva essere scartata: {esito['scartate']}"
    assert len(esito["membrature"]) == esito["regioni_trovate"]
    for membratura in esito["membrature"]:
        assert membratura["riempimento"]["stato"] == "pieno", membratura["riempimento"]


def test_i_prismi_pieni_escono_pieni_qualunque_sia_la_loro_forma():
    """Ruling H, ripreso dal Ruling J: cinque prismi pieni, senza alcun vuoto
    -- tozzo, corto, allungato, grande -- devono uscire «pieno». Se il
    riempimento misurasse il bordo invece del vuoto, una colonna tozza o un
    elemento corto uscirebbero «vuoto» come una Π."""
    casi = [
        (200.0, 140.0, 1500.0),
        (300.0, 300.0, 1500.0),
        (500.0, 500.0, 1500.0),
        (200.0, 140.0, 500.0),
        (500.0, 500.0, 500.0),
    ]
    for dimensioni in casi:
        punti = synth.sample_box_surface(dimensioni, SPAZIATURA)
        direzioni, _ = wall.terna(punti)

        membratura = wall.misura(punti, direzioni, _cfg())

        assert membratura.riempimento_stato == "pieno", (
            f"{dimensioni}: stato {membratura.riempimento_stato}, "
            f"valore {membratura.riempimento_sezione}, ma e' un prisma pieno"
        )
        assert membratura.riempimento_sezione > 0.9, f"{dimensioni}: {membratura.riempimento_sezione}"


def test_una_faccia_frontale_fitta_con_pareti_rade_non_e_vuota_ma_non_verificabile():
    """Primo controesempio della terza review, il punto centrale del Ruling J.

    Un prisma **pieno** scansionato da un lato solo: la faccia frontale e' presa
    fitta, le pareti laterali rade. La griglia del riempimento e' costruita su
    una spaziatura media, e una media non descrive una densita' bimodale a
    nessuna scala: il perimetro rado non si chiude, il riempimento crolla, e il
    prisma pieno sembra vuoto. L'esito giusto non e' «vuoto» -- e' «non
    verificabile», perche' e' la misura a non valere, non il pezzo a essere
    cavo."""
    punti = _prisma_a_densita_bimodale([(1, 0.0)])
    direzioni, _ = wall.terna(punti)

    membratura = wall.misura(punti, direzioni, _cfg())

    assert membratura.riempimento_stato == "non_verificabile", (
        f"stato {membratura.riempimento_stato}, valore {membratura.riempimento_sezione}, "
        f"dispersione densita' {membratura.densita_dispersione}"
    )


def test_tappi_terminali_fitti_con_pareti_rade_non_sono_vuoti_ma_non_verificabili():
    """Secondo controesempio della terza review: stessa densita' bimodale, ma
    concentrata sui due tappi terminali invece che su una parete laterale. La
    conclusione deve essere la stessa -- non verificabile, non vuoto -- perche'
    il difetto sta nella densita' del campionamento e non in dove capita."""
    punti = _prisma_a_densita_bimodale([(2, 0.0), (2, DENSITA_BIMODALE[2])])
    direzioni, _ = wall.terna(punti)

    membratura = wall.misura(punti, direzioni, _cfg())

    assert membratura.riempimento_stato == "non_verificabile", (
        f"stato {membratura.riempimento_stato}, valore {membratura.riempimento_sezione}, "
        f"dispersione densita' {membratura.densita_dispersione}"
    )


def test_una_regione_senza_punti_a_sufficienza_resta_non_verificabile():
    """Una grandezza non misurata non e' una grandezza piena, e non e' nemmeno
    una grandezza vuota. Con troppo pochi punti perche' una sola fetta ne veda
    almeno quattro, lo stato e' «non verificabile» e lo dice."""
    punti_pochi = np.array([
        [0.0, 0.0, 0.0],
        [10.0, 0.0, 0.0],
        [0.0, 10.0, 0.0],
        [0.0, 0.0, 10.0],
        [10.0, 10.0, 10.0],
    ])
    direzioni, _ = wall.terna(punti_pochi)

    membratura = wall.misura(punti_pochi, direzioni, _cfg())

    assert membratura.riempimento_stato == "non_verificabile"


def test_una_regione_rada_ma_uniforme_esce_piena():
    """Ruling I: una porzione di pezzo piu' lontana dallo scanner ha densita'
    locale piu' rada del resto del pezzo. Finche' e' rada in modo uniforme, la
    misura vale e un prisma pieno campionato rado esce «pieno»: e' la
    controprova dei due controesempi qui sopra, dove a mancare non e' la
    densita' ma la sua uniformita'."""
    punti = synth.sample_box_surface((300.0, 300.0, 1500.0), 70.0)
    direzioni, _ = wall.terna(punti)

    membratura = wall.misura(punti, direzioni, _cfg())

    assert membratura.riempimento_stato == "pieno", (
        f"stato {membratura.riempimento_stato}, dispersione densita' "
        f"{membratura.densita_dispersione}"
    )


def test_una_pi_molto_rada_non_esce_piena():
    """Il controllo che smentisce il precedente: una Π vera, campionata cosi'
    rada che la griglia locale copre la sezione con troppo poche celle per
    vedere il vuoto, non deve uscire «pieno» -- deve dichiararsi non
    verificabile."""
    punti = synth.sample_frame_surface(TELAIO_A_SEZIONE_UNIFORME, 200.0)
    direzioni, _ = wall.terna(punti)

    membratura = wall.misura(punti, direzioni, _cfg())

    assert membratura.riempimento_stato == "non_verificabile", (
        f"stato {membratura.riempimento_stato}, valore {membratura.riempimento_sezione}"
    )


def test_una_pi_meta_fitta_e_meta_rada_non_arriva_fra_le_membrature():
    """Il controesempio della terza re-review, e la ragione per cui il
    riempimento non ha una seconda misura di affidabilita' per fetta.

    Π vera, mai piena da nessuna parte, campionata a due densita': una meta'
    a 15 mm, l'altra a 150 mm. Su questa regione `riempimento_stato` esce
    davvero sbagliato -- «pieno» con misura affidabile su una meta', «vuoto»
    sull'altra -- perche' la parte rada si allinea a caso con i confini delle
    fette e alcune fette finiscono per contenere solo un pezzo della sezione,
    che e' genuinamente pieno, e leggono 1.0.

    Ma quello e' uno scostamento **della sezione fra fette**, non della
    densita': e' esattamente la grandezza che `costanza_sezione` misura, con
    una sensibilita' molto maggiore (qui 0.53 contro una soglia di 0.10). La
    regione non arriva mai fra le membrature, quindi non arriva mai alla
    guardia di chi costruisce, ed e' questa la proprieta' che conta e che
    questo test sorveglia. Il giorno in cui qualcuno allentasse
    `section_dispersion`, e' qui che si vedrebbe."""
    fitta = synth.sample_frame_surface(TELAIO_A_SEZIONE_UNIFORME, 15.0)
    rada = synth.sample_frame_surface(TELAIO_A_SEZIONE_UNIFORME, 150.0)
    meta = (fitta[:, 2].min() + fitta[:, 2].max()) / 2.0
    for sopra in (True, False):
        dentro = fitta[:, 2] >= meta if sopra else fitta[:, 2] < meta
        fuori = rada[:, 2] < meta if sopra else rada[:, 2] >= meta
        punti = np.vstack([fitta[dentro], rada[fuori]])

        esito = wall.prior(punti, SegmentConfig(), _cfg(), 15.0)

        quale = "alta" if sopra else "bassa"
        assert esito["membrature"] == [], (
            f"meta' fitta {quale}: la Π non deve arrivare a chi costruisce, "
            f"invece e' passata: {[m['riempimento'] for m in esito['membrature']]}"
        )
        assert "costanza_sezione" in esito["scartate"][0]["controlli_falliti"], (
            f"meta' fitta {quale}: doveva fermarla la costanza della sezione, "
            f"controlli falliti: {esito['scartate'][0]['controlli_falliti']}"
        )


# Una sezione senza spessore arrivava a `ConvexHull` senza guardia (#68): il
# QhullError usciva dal profondo di scipy, dentro il ciclo per regione di
# `prior`, e uccideva la corsa sulla prima regione difettosa. Su Linux x86-64
# il test della Pi mezza rada qui sopra lo produceva due volte su quattro
# corse di CI, mai su macOS arm64 -- ma il difetto e' latente su entrambe.
_COLLINEARI = np.array([[-46.0, 0.0], [-31.0, 0.0], [46.0, 0.0]])


def test_una_sezione_senza_spessore_nomina_la_sezione_e_non_qhull():
    """L'errore che esce deve dire che cosa non va nel **dato**, non quale
    libreria si e' arresa. `QhullError: Initial simplex is flat` non dice a
    chi legge ne' quale regione ne' che cosa cambiare.

    I tre punti sono quelli veri della traccia della corsa in CI, tutti a
    y = 0.
    """
    with pytest.raises(wall.SezioneDegenere, match="spessore"):
        wall.semplifica_contorno(_COLLINEARI, 5.0)


def test_la_guardia_e_sullo_spessore_non_sulla_collinearita_esatta():
    """Misurato: `ConvexHull` **accetta** tre punti a 1e-12 dalla retta e
    rende un triangolo di area praticamente nulla. Una guardia sul solo caso
    esatto lascerebbe quindi passare la stessa spazzatura un epsilon piu' in
    la', ed e' per questo che il criterio e' lo spessore contro la tolleranza
    di contorno e non l'allineamento perfetto.
    """
    quasi = np.array([[-46.0, 0.0], [-31.0, 1e-12], [46.0, 0.0]])

    with pytest.raises(wall.SezioneDegenere):
        wall.semplifica_contorno(quasi, 5.0)


def test_lo_spessore_si_misura_nella_direzione_piu_sottile():
    """La guardia deve valere anche su una retta **obliqua**: un `ptp` per
    coordinata vedrebbe estensione in x e in y e non si accorgerebbe di
    nulla. Qui i punti stanno sulla bisettrice, quindi entrambe le
    estensioni assiali valgono 100 e solo la direzione minore rivela che lo
    spessore e' zero.
    """
    obliqui = np.array([[0.0, 0.0], [50.0, 50.0], [100.0, 100.0]])
    assert np.ptp(obliqui[:, 0]) == 100.0 and np.ptp(obliqui[:, 1]) == 100.0

    with pytest.raises(wall.SezioneDegenere):
        wall.semplifica_contorno(obliqui, 5.0)


@pytest.mark.parametrize(
    "punti,etichetta",
    [
        (np.zeros((0, 2)), "nessun punto"),
        (np.array([[0.0, 0.0]]), "un punto"),
        (np.array([[0.0, 0.0], [10.0, 0.0]]), "due punti"),
        (np.array([[0.0, 0.0], [0.0, 0.0], [10.0, 0.0]]), "due coincidenti e un terzo"),
    ],
)
def test_ogni_sezione_troppo_povera_da_lo_stesso_esito(punti, etichetta):
    """Quattro ingressi che prima davano tre eccezioni **diverse** -- due
    QhullError con codici diversi (QH6154 e QH6214) e un `ValueError: No
    points given` -- cioe' tre modi di dire la stessa cosa, nessuno dei quali
    nomina la sezione. Ora sono un esito solo.
    """
    with pytest.raises(wall.SezioneDegenere):
        wall.semplifica_contorno(punti, 5.0)


def test_una_sezione_sana_non_cambia_comportamento():
    """Controprova, e senza di essa la guardia potrebbe rifiutare tutto: un
    rettangolo con vertici di rumore resta ridotto ai suoi quattro angoli."""
    rumoroso = np.array([
        [0.0, 0.0], [100.0, 0.1], [200.0, 0.0], [200.0, 70.0],
        [200.0, 140.0], [100.0, 139.9], [0.0, 140.0], [0.0, 70.0],
    ])

    contorno = wall.semplifica_contorno(rumoroso, 5.0)

    assert contorno.tolist() == [[0.0, 0.0], [200.0, 0.0], [200.0, 140.0], [0.0, 140.0]]


def test_una_regione_degenere_non_uccide_le_altre(monkeypatch):
    """La meta' che conta: `prior` deve **scartare** la regione e proseguire.

    Prima della correzione l'eccezione saliva da `misura` e usciva da
    `prior`, quindi una sola regione difettosa faceva perdere anche le
    regioni buone gia' misurate -- e la corsa aveva gia' pagato
    segmentazione e SVD. E' lo stesso ragionamento con cui `controlla`
    dichiara che un controllo fallito non solleva.

    La regione degenere e' iniettata invece che costruita: serve provare la
    gestione, e un banco che producesse davvero una sezione collassata
    dipenderebbe dal maglio, cioe' dalla piattaforma -- che e' il difetto
    misurato in #66.
    """
    punti = synth.sample_frame_surface(TELAIO, SPAZIATURA)
    vera = wall.misura
    chiamate = {"n": 0}

    def misura_con_una_degenere(punti_regione, direzioni, cfg):
        chiamate["n"] += 1
        if chiamate["n"] == 1:
            raise wall.SezioneDegenere(0.0, cfg.contour_tolerance, len(punti_regione))
        return vera(punti_regione, direzioni, cfg)

    monkeypatch.setattr(wall, "misura", misura_con_una_degenere)

    esito = wall.prior(punti, SegmentConfig(), _cfg(), SPAZIATURA)

    assert chiamate["n"] > 1, "il banco deve avere piu' di una regione, o non prova nulla"
    assert esito["membrature"], "le regioni buone devono arrivare in fondo lo stesso"

    degeneri = [v for v in esito["scartate"] if "sezione_degenere" in v["controlli_falliti"]]
    assert len(degeneri) == 1
    voce = degeneri[0]["esiti"]["sezione_degenere"]
    assert voce["passato"] is False
    # numerici entrambi: `disegnaScartate` in ui/app.js ci chiama `.toFixed(3)`
    assert isinstance(voce["valore"], float)
    assert isinstance(voce["soglia"], float)
