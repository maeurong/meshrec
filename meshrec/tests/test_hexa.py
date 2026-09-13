"""I modelli parametrici: prismi in esaedri, con il volume analitico a smentirli.

hexa.py costruisce e non misura, esattamente come wall.py misura e non
costruisce. Il confine e' cio' che rende questi test possibili: la verita' di
riferimento e' il volume analitico del prisma, calcolato qui e non dal codice
sotto prova.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from meshrec.core import hexa, quality
from meshrec.core.config import ModelConfig
from meshrec.core.gmsh_backend import inizializza

# Un rettangolo 200 x 140, in senso antiorario. Sono numeri del banco.
RETTANGOLO = np.array([[0.0, 0.0], [200.0, 0.0], [200.0, 140.0], [0.0, 140.0]])
LUNGHEZZA = 1500.0
ASSE_Z = np.array([0.0, 0.0, 1.0])


def test_il_prisma_e_fatto_di_soli_esaedri_e_ne_ha_il_volume_analitico():
    """La verita' di riferimento e' 200 x 140 x 1500: se la mesh non la
    riproduce, ogni massa e ogni confronto che ne discendono sono falsi."""
    nodi, esaedri, metriche = hexa.mesh_prisma(
        RETTANGOLO, np.zeros(3), ASSE_Z, LUNGHEZZA, ModelConfig()
    )

    assert esaedri.shape[1] == 8, "soli esaedri: nessun prisma a base triangolare"
    volume = quality.hex_volumes(nodi, esaedri).sum()
    assert volume == pytest.approx(200.0 * 140.0 * LUNGHEZZA, rel=1e-6)
    assert metriche["hexes"] == len(esaedri)
    assert metriche["volume_analitico"] == pytest.approx(200.0 * 140.0 * LUNGHEZZA)


def test_nessun_esaedro_del_prisma_ha_jacobiano_non_positivo():
    """Un elemento rovesciato in mezzo a centomila non si vede guardando la
    mesh, e il solutore o si ferma o restituisce numeri senza senso."""
    nodi, esaedri, _ = hexa.mesh_prisma(
        RETTANGOLO, np.zeros(3), ASSE_Z, LUNGHEZZA, ModelConfig()
    )

    assert (quality.scaled_jacobian(nodi, esaedri) > 0.0).all()


def test_lo_spessore_ha_almeno_tre_strati_di_elementi():
    """Vincolo imposto dal codice e non suggerito: con uno o due strati la
    flessione nello spessore non e' rappresentata, e il risultato e' sbagliato
    senza alcun segnale."""
    cfg = ModelConfig(target_size=1000.0)  # un passo assurdamente grosso

    nodi, esaedri, metriche = hexa.mesh_prisma(
        RETTANGOLO, np.zeros(3), ASSE_Z, LUNGHEZZA, cfg
    )

    assert metriche["passo"] <= 140.0 / 3.0 + 1e-9, (
        "il passo chiesto e' stato ridotto fino a garantire tre strati nella "
        "sezione minima, o non lo e' stato ed e' un difetto"
    )
    # tre strati nello spessore vogliono almeno quattro piani di nodi
    quote = np.unique(np.round(nodi[:, 1], 6))
    assert len(quote) >= 4


def test_il_prisma_parte_dall_origine_e_va_lungo_l_asse_che_gli_si_da():
    """L'asse misurato conserva il fuori piombo: se la funzione lo ignorasse,
    il modello estruso e quello primitive sarebbero la stessa cosa e il
    confronto non separerebbe piu' i due effetti."""
    asse = np.array([0.0, np.sin(np.radians(5.0)), np.cos(np.radians(5.0))])
    origine = np.array([100.0, 50.0, -20.0])

    nodi, _esaedri, _ = hexa.mesh_prisma(RETTANGOLO, origine, asse, LUNGHEZZA, ModelConfig())

    lungo = (nodi - origine) @ asse
    assert lungo.min() == pytest.approx(0.0, abs=1e-6)
    assert lungo.max() == pytest.approx(LUNGHEZZA, abs=1e-6)


def test_l_ordine_di_nodi_ed_elementi_e_canonico_e_non_quello_dei_tag():
    """Quinto vincolo di prodotto. I tag di gmsh sono un ordine di generazione,
    non un dato della geometria, e il progetto ha gia' pagato una volta la
    lezione dell'ordine di iterazione di una libreria fra due piattaforme.

    Il cubo unitario non basta a provarlo: e' simmetrico per permutazione
    degli assi, quindi non distingue la priorita' x -> y -> z dichiarata da
    `ordine_canonico` da una qualunque altra priorita' fra gli stessi tre
    assi (RULING S). Qui il parallelepipedo ha tre estensioni diverse fra
    loro (1, 2, 3), e la sequenza ordinata attesa e' calcolata a mano
    scorrendo prima tutti gli x=0, poi gli x=1, e dentro ciascuno prima gli
    y piu' piccoli poi quelli piu' grandi, e infine gli z: e' l'unica
    sequenza compatibile con la priorita' x, poi y, poi z."""
    nodi = np.array([
        [1.0, 0.0, 0.0], [0.0, 0.0, 0.0], [0.0, 2.0, 0.0], [1.0, 2.0, 0.0],
        [1.0, 0.0, 3.0], [0.0, 0.0, 3.0], [0.0, 2.0, 3.0], [1.0, 2.0, 3.0],
    ])
    esaedri = np.array([[1, 0, 3, 2, 5, 4, 7, 6]], dtype=np.int64)

    ordinati, rimappati = hexa.ordine_canonico(nodi, esaedri)

    # sequenza calcolata a mano: x=0 prima di x=1, dentro ciascuno y=0 prima
    # di y=2, dentro ciascuno z=0 prima di z=3. Una priorita' diversa da
    # x -> y -> z (per esempio z -> y -> x) produrrebbe un'altra sequenza,
    # perche' le tre estensioni sono diverse fra loro e nessuna permutazione
    # delle chiavi coincide con un'altra: verificato permutando le chiavi del
    # lexsort e osservando la sequenza cambiare (vedi task-7-report.md).
    attesi = np.array([
        [0.0, 0.0, 0.0], [0.0, 0.0, 3.0], [0.0, 2.0, 0.0], [0.0, 2.0, 3.0],
        [1.0, 0.0, 0.0], [1.0, 0.0, 3.0], [1.0, 2.0, 0.0], [1.0, 2.0, 3.0],
    ])
    assert ordinati == pytest.approx(attesi)
    # l'elemento punta agli stessi punti fisici di prima
    assert np.sort(ordinati[rimappati[0]], axis=0) == pytest.approx(
        np.sort(nodi[esaedri[0]], axis=0)
    )
    # e il volume non e' cambiato: la topologia interna dell'elemento resta
    assert quality.hex_volumes(ordinati, rimappati) == pytest.approx(
        quality.hex_volumes(nodi, esaedri)
    )


def test_metriche_strati_conta_i_piani_di_nodi_lungo_l_asse():
    """`metriche["strati"]` dichiara il vincolo portante del task (RULING U):
    non puo' essere l'unico testimone di se stesso. N strati di elementi
    vogliono N+1 piani di nodi distinti lungo l'asse di estrusione, ed e'
    quello che si conta qui, indipendentemente da come il numero e' stato
    calcolato."""
    nodi, _esaedri, metriche = hexa.mesh_prisma(
        RETTANGOLO, np.zeros(3), ASSE_Z, LUNGHEZZA, ModelConfig()
    )

    piani = np.unique(np.round(nodi[:, 2], 6))
    assert len(piani) == metriche["strati"] + 1


def test_mesh_prisma_rifiuta_una_lunghezza_non_positiva():
    """RULING U: senza guardia, lunghezza=0 o negativa producono una mesh
    valida in forma ma di volume nullo o negativo, senza alcun segnale."""
    with pytest.raises(ValueError, match="lunghezza"):
        hexa.mesh_prisma(RETTANGOLO, np.zeros(3), ASSE_Z, 0.0, ModelConfig())
    with pytest.raises(ValueError, match="lunghezza"):
        hexa.mesh_prisma(RETTANGOLO, np.zeros(3), ASSE_Z, -1500.0, ModelConfig())


def test_passo_di_mesh_rifiuta_un_contorno_con_estensione_nulla_su_un_asse():
    """RULING U: un contorno degenere (per esempio appiattito su un asse) fa
    scendere la sezione minima a zero; senza guardia il passo si azzera e la
    divisione successiva fallisce con un errore che non dice ne' il valore
    ne' la ragione."""
    degenere = np.array([[0.0, 0.0], [200.0, 0.0], [200.0, 0.0], [0.0, 0.0]])
    with pytest.raises(ValueError, match="estensione"):
        hexa.passo_di_mesh(degenere, ModelConfig())


# Un vertice non finito in una sezione: il contorno non e' un poligono, e le
# tre guardie che lo riguardano erano scritte in negativo (#50), cioe' false
# su `nan`. I quattro test qui sotto sono uno per sito eseguito.
_SEZIONE_ROTTA = np.array([[0.0, 0.0], [1.0, 0.0], [1.0, float("nan")], [0.0, 1.0]])


def test_l_area_con_segno_rifiuta_un_vertice_non_finito():
    """Il segno di `_area_poligono` **decide un orientamento** in tre punti e
    la sua ampiezza e' una chiave di ordinamento in un quarto. `nan < 0.0` e'
    falso: il contorno rotto non veniva invertito e nessuno lo sapeva.
    Misurato prima della correzione: rendeva `nan`.
    """
    with pytest.raises(ValueError, match="non finito"):
        hexa._area_poligono(_SEZIONE_ROTTA)


def test_l_area_con_segno_di_una_sezione_piatta_resta_zero():
    """Controprova: la guardia nuova non deve inghiottire il caso degenere
    gia' definito. Un poligono appiattito ha area **zero**, che e' un numero
    e una risposta -- diversa da «non e' un numero».
    """
    piatta = np.array([[0.0, 0.0], [1.0, 0.0], [2.0, 0.0], [3.0, 0.0]])

    assert hexa._area_poligono(piatta) == 0.0


def test_il_passo_di_mesh_rifiuta_un_vertice_non_finito():
    """Senza la forma in positivo il passo usciva `nan` e arrivava intatto a
    `gmsh.model.geo.addPoint(u, v, 0.0, passo)` -- eseguito e misurato."""
    with pytest.raises(ValueError, match="non finita"):
        hexa.passo_di_mesh(_SEZIONE_ROTTA, ModelConfig())


def test_mesh_prisma_rifiuta_una_lunghezza_non_finita():
    """Stessa forma negata di `lunghezza <= 0.0`, ma il difetto **non era**
    l'assenza di segnale: e' il segnale sbagliato, misurato prima della
    correzione sui tre valori.

    - `-inf` era gia' preso, perche' `-inf <= 0.0` e' vero;
    - `nan` scavalcava e cadeva piu' avanti su `int(round(nan / passo))`,
      cioe' `ValueError: cannot convert float NaN to integer` -- dopo
      l'import di gmsh, e senza nominare la lunghezza;
    - `inf` scavalcava e cadeva sullo stesso `int(round(...))` con
      **`OverflowError`**, che non e' nemmeno un `ValueError`: un chiamante
      che catturasse `ValueError` per riportare l'errore all'utente si
      sarebbe visto passare accanto un'eccezione di un'altra famiglia.

    Il test chiede quindi tutti e tre nello **stesso** tipo e con lo stesso
    messaggio, che e' la parte che la vecchia forma non dava.
    """
    for lunghezza in (float("nan"), float("inf"), float("-inf")):
        with pytest.raises(ValueError, match="lunghezza"):
            hexa.mesh_prisma(RETTANGOLO, np.zeros(3), ASSE_Z, lunghezza, ModelConfig())


def _membratura_finta(
    contorno, origine, asse, lunghezza, asse_ideale, riempimento="pieno", sezione=None
):
    from meshrec.core.wall import Membratura

    # Default = ptp(contorno), come sul dato reale quando la semplificazione
    # non ha spostato l'inviluppo. `sezione` e' un parametro perche' A4 ha
    # bisogno di rendere le due grandezze diverse, cosa che il default non
    # puo' mai fare per costruzione.
    if sezione is None:
        sezione = (float(np.ptp(contorno[:, 0])), float(np.ptp(contorno[:, 1])))
    return Membratura(
        punti=np.arange(0),
        asse=np.asarray(asse, dtype=np.float64),
        origine=np.asarray(origine, dtype=np.float64),
        lunghezza=float(lunghezza),
        sezione=sezione,
        sezione_dispersione=(0.0, 0.0),
        contorno=np.asarray(contorno, dtype=np.float64),
        fuori_piombo_deg=0.0,
        asse_ideale=np.asarray(asse_ideale, dtype=np.float64),
        scarto_asse_deg=0.0,
        rigonfiamento=np.zeros(4),
        volume=0.0,
        riempimento_sezione=1.0 if riempimento == "pieno" else 0.3,
        riempimento_stato=riempimento,
        densita_dispersione=0.0,
    )


# Il telaio del banco: una colonna 200 x 200 alta 1400 e una trave 300 x 200
# lunga 1400, la cui faccia inferiore sta a z = 1300. Sono numeri scelti perche'
# ogni valore atteso qui sotto sia un prodotto di dimensioni o una differenza
# fra due quote, mai una misura letta dal codice sotto prova.
COLONNA = np.array([[0.0, 0.0], [200.0, 0.0], [200.0, 200.0], [0.0, 200.0]])
TRAVE = np.array([[0.0, 0.0], [300.0, 0.0], [300.0, 200.0], [0.0, 200.0]])
QUOTA_TRAVE = 1300.0
ALTEZZA_COLONNA = 1400.0
LUNGHEZZA_TRAVE = 1400.0
# 1400 - 1300: la colonna arriva 100 mm dentro la trave e li' va tagliata.
ACCORCIAMENTO_ATTESO = ALTEZZA_COLONNA - QUOTA_TRAVE


def _telaio_di_prova():
    """Le due membrature del banco, nell'ordine colonna, trave."""
    return [
        _membratura_finta(COLONNA, [0.0, 0.0, 0.0], [0.0, 0.0, 1.0],
                          ALTEZZA_COLONNA, [0.0, 0.0, 1.0]),
        _membratura_finta(TRAVE, [0.0, 0.0, QUOTA_TRAVE], [1.0, 0.0, 0.0],
                          LUNGHEZZA_TRAVE, [1.0, 0.0, 0.0]),
    ]


def test_una_membratura_a_sezione_vuota_non_diventa_un_modello():
    """La guardia del Ruling J, che e' l'unica che ferma una Π: wall.py misura
    e non scarta, quindi una regione il cui ingombro non e' la sezione arriva
    fin qui. Costruirci sopra vorrebbe dire dare per pieno un vano vuoto.

    Muore se: si toglie la guardia, o se la si allarga a «non_verificabile»
    (il test qui sotto e' la meta' che smentisce questa)."""
    vuota = _membratura_finta(
        RETTANGOLO, [0.0, 0.0, 0.0], [0.0, 0.0, 1.0], LUNGHEZZA, ASSE_Z, riempimento="vuoto"
    )

    with pytest.raises(ValueError, match="vuoto"):
        hexa.costruisci([vuota], "estruso", ModelConfig())


def test_una_membratura_non_verificabile_si_costruisce_lo_stesso():
    """Il controllo che smentisce la guardia: «non verificabile» dice che la
    misura non vale, non che il pezzo e' cavo. Su una nuvola rada e' l'esito
    normale, e rifiutarlo fermerebbe il modello su meta' dei casi reali.

    Muore se: la guardia rifiuta ogni stato diverso da «pieno»."""
    incerta = _membratura_finta(
        RETTANGOLO, [0.0, 0.0, 0.0], [0.0, 0.0, 1.0], LUNGHEZZA, ASSE_Z,
        riempimento="non_verificabile",
    )

    esito = hexa.costruisci([incerta], "estruso", ModelConfig())

    assert len(esito["blocchi"]) == 1


def test_il_modello_primitive_raddrizza_l_asse_e_squadra_la_sezione():
    """I due modelli separano due effetti diversi: l'irregolarita' della sezione
    e il fuori piombo. Se primitive non raddrizzasse, il confronto li
    sommerebbe in un unico salto invece di distinguerli.

    Muore se: primitive restituisce `membratura.asse` invece di `asse_ideale`,
    o il contorno rilevato invece del rettangolo."""
    storto = np.array([0.0, np.sin(np.radians(6.0)), np.cos(np.radians(6.0))])
    sezione_irregolare = np.array([[0.0, 0.0], [200.0, 4.0], [197.0, 140.0], [3.0, 136.0]])
    membratura = _membratura_finta(
        sezione_irregolare, [0.0, 0.0, 0.0], storto, LUNGHEZZA, [0.0, 0.0, 1.0]
    )

    estruso = hexa.prisma_di(membratura, "estruso")
    primitive = hexa.prisma_di(membratura, "primitive")

    assert estruso.asse == pytest.approx(storto)
    assert primitive.asse == pytest.approx([0.0, 0.0, 1.0])
    assert len(estruso.contorno) == 4
    assert len(primitive.contorno) == 4
    # primitive e' il rettangolo dei valori misurati: quattro angoli retti
    lati = np.diff(np.vstack([primitive.contorno, primitive.contorno[:1]]), axis=0)
    for primo, secondo in zip(lati, np.roll(lati, -1, axis=0), strict=True):
        assert float(np.dot(primo, secondo)) == pytest.approx(0.0, abs=1e-9)


def test_il_modello_primitive_conserva_le_dimensioni_misurate():
    """Il controllo che smentisce il precedente: raddrizzare non vuol dire
    inventare. Le due dimensioni del rettangolo sono quelle misurate.

    La sezione del banco e' **irregolare** apposta: con un rettangolo gia'
    squadrato, un primitive che restituisse il contorno tal quale supererebbe
    il test senza fare nulla — verificato per mutazione.

    Muore se: primitive copia il contorno rilevato; muore anche se lo squadra
    su dimensioni che non sono le due estensioni misurate."""
    # 250 x 175 sono le estensioni della sezione irregolare qui sotto:
    # np.ptp sui vertici da' esattamente quei due numeri.
    sezione = np.array([[0.0, 0.0], [250.0, 6.0], [246.0, 175.0], [4.0, 169.0]])
    membratura = _membratura_finta(
        sezione, [0.0, 0.0, 0.0], [0.0, 0.0, 1.0], 900.0, [0.0, 0.0, 1.0]
    )

    primitive = hexa.prisma_di(membratura, "primitive")

    assert np.ptp(primitive.contorno, axis=0) == pytest.approx([250.0, 175.0])
    assert primitive.lunghezza == pytest.approx(900.0)
    assert not np.allclose(primitive.contorno, sezione), "primitive squadra, non copia"


def test_il_modello_primitive_squadra_sulla_sezione_misurata_non_sul_contorno():
    """A4 del giro di correzione 1: `membratura.contorno` e' gia' passato da
    `semplifica_contorno`, che sposta l'inviluppo; `membratura.sezione` e'
    l'estensione dei punti grezzi nella stessa base di piano. Le due grandezze
    divergono sul dato reale (differenza misurata di 5 mm alla tolleranza di
    contorno predefinita), e qui la fixture le rende diverse per costruzione:
    senza una `sezione` esplicita e diversa da `ptp(contorno)`, questo test
    non potrebbe distinguerle.

    Muore se: `prisma_di("primitive")` torna a usare
    `np.ptp(membratura.contorno, axis=0)` invece di `membratura.sezione`."""
    contorno_semplificato = np.array([[0.0, 0.0], [200.0, 0.0], [200.0, 140.0], [0.0, 140.0]])
    sezione_grezza = (210.0, 150.0)  # deliberatamente diversa da ptp(contorno) = (200, 140)
    membratura = _membratura_finta(
        contorno_semplificato, [0.0, 0.0, 0.0], [0.0, 0.0, 1.0], LUNGHEZZA, ASSE_Z,
        sezione=sezione_grezza,
    )

    primitive = hexa.prisma_di(membratura, "primitive")

    assert np.ptp(primitive.contorno, axis=0) == pytest.approx(sezione_grezza)


def test_il_modello_primitive_ancora_il_rettangolo_al_centro_non_al_minimo():
    """Emendamento al Ruling AB (giro di correzione 2): l'ancoraggio al minimo
    del contorno gia' semplificato, combinato con le estensioni prese da
    `membratura.sezione` (punti grezzi), e' la combinazione peggiore delle
    due -- `semplifica_contorno` puo' togliere proprio il vertice che
    realizza il minimo, e il rettangolo allora inventa materiale da un lato e
    non copre quello vero dall'altro lato, spostando anche l'asse.

    Contorno pulito 200x140 (minimo [0,0], centro [100,70]), sezione
    deliberatamente diversa (210,150): le due grandezze vengono da fonti
    diverse, come sul dato reale dopo `semplifica_contorno`. Se il minimo e
    il centro coincidessero (fixture con `sezione = ptp(contorno)`) il test
    non vedrebbe nulla, la stessa trappola di A4.

    Provenienza: centro = (minimo + massimo) / 2 = ([0,0] + [200,140]) / 2 =
    [100, 70]. Rettangolo atteso = centro +- sezione/2 =
    [100 -+ 105, 70 -+ 75] = [-5, 205] x [-5, 145].

    Muore se: l'ancoraggio torna al minimo del contorno invece che al centro
    (produrrebbe [0, 210] x [0, 150], non [-5, 205] x [-5, 145])."""
    contorno = np.array([[0.0, 0.0], [200.0, 0.0], [200.0, 140.0], [0.0, 140.0]])
    sezione_grezza = (210.0, 150.0)
    membratura = _membratura_finta(
        contorno, [0.0, 0.0, 0.0], [0.0, 0.0, 1.0], LUNGHEZZA, ASSE_Z,
        sezione=sezione_grezza,
    )

    primitive = hexa.prisma_di(membratura, "primitive")

    assert np.min(primitive.contorno, axis=0) == pytest.approx([-5.0, -5.0])
    assert np.max(primitive.contorno, axis=0) == pytest.approx([205.0, 145.0])


def test_l_appartenenza_a_un_prisma_e_esatta_sul_contorno_convesso():
    """Muore se: la tolleranza viene applicata sempre invece che su richiesta
    (il punto «appena fuori» entrerebbe), o se non viene applicata affatto
    (non entrerebbe nemmeno quando la si chiede)."""
    prisma = hexa.Prisma(
        contorno=RETTANGOLO, origine=np.zeros(3), asse=ASSE_Z, lunghezza=1000.0
    )
    dentro = np.array([[100.0, 70.0, 500.0], [1.0, 1.0, 1.0]])
    fuori = np.array([[300.0, 70.0, 500.0], [100.0, 70.0, 1500.0], [100.0, -5.0, 500.0]])

    assert hexa.dentro(prisma, dentro).all()
    assert not hexa.dentro(prisma, fuori).any()

    # la tolleranza e' un margine chiesto, non un predefinito: mezzo millimetro
    # fuori dalla faccia y = 0 sta fuori, ed entra solo se la si concede.
    appena_fuori = np.array([[100.0, -0.5, 500.0]])
    assert not hexa.dentro(prisma, appena_fuori).any()
    assert hexa.dentro(prisma, appena_fuori, tolleranza=1.0).all()


def test_due_prismi_che_si_compenetrano_vengono_tagliati_sul_bordo_del_solido():
    """Le membrature si compenetrano dove si incontrano, e senza taglio il
    volume viene contato due volte: un errore che nessuna metrica di qualita'
    vedrebbe, e per questo il controllo lo cerca esplicitamente.

    Il taglio si ferma sul **bordo del solido**, trovato per bisezione, non
    sull'ultimo campione libero: la differenza e' 5,5 mm su questo banco, ed e'
    cio' che rende possibile il `*TIE` del test in fondo — due superfici
    distanti mezzo centimetro non si legano.

    Ogni numero atteso qui e' geometria dichiarata, non una lettura:
    l'accorciamento e' 1400 - 1300 = 100 mm, cioe' quanto la colonna entrava
    nella trave; il volume e' la somma di due prodotti di dimensioni, senza
    sottrazioni, perche' dopo il taglio i due solidi non si sovrappongono piu'.

    Muore se: si toglie il taglio (accorciamento 0, volume in eccesso del 2,941%);
    muore anche se si toglie la sola bisezione e ci si ferma sul campione
    (accorciamento 105,528 invece di 100 -- si taglia di piu', non di meno --
    volume in difetto dello 0,163%) — entrambe le mutazioni applicate e
    verificate in questa sessione (vedi task-8-report.md)."""
    colonna = hexa.Prisma(
        contorno=COLONNA, origine=np.array([0.0, 0.0, 0.0]),
        asse=np.array([0.0, 0.0, 1.0]), lunghezza=ALTEZZA_COLONNA,
    )
    trave = hexa.Prisma(
        contorno=TRAVE, origine=np.array([0.0, 0.0, QUOTA_TRAVE]),
        asse=np.array([1.0, 0.0, 0.0]), lunghezza=LUNGHEZZA_TRAVE,
    )

    tagliati, giunzioni = hexa.taglia_giunzioni([colonna, trave])

    assert len(tagliati) == 2
    assert len(giunzioni) == 1
    # per indice e mai con min(): la trave e' piu' corta della colonna intera,
    # e un min() farebbe passare il test scegliendo il prisma mai tagliato.
    assert (giunzioni[0]["minore"], giunzioni[0]["maggiore"]) == (0, 1)
    assert giunzioni[0]["accorciamento"] == pytest.approx(ACCORCIAMENTO_ATTESO, abs=1e-6)
    assert tagliati[0].lunghezza == pytest.approx(QUOTA_TRAVE, abs=1e-6)
    assert tagliati[1].lunghezza == pytest.approx(LUNGHEZZA_TRAVE)

    somma = sum(
        abs(hexa._area_poligono(p.contorno)) * p.lunghezza for p in tagliati
    )
    # rel=1e-9 e non una tolleranza larga: dopo la bisezione l'errore misurato
    # e' 1,3e-15, cioe' il solo residuo in virgola mobile. Una tolleranza che
    # copre l'errore che dovrebbe scoprire e' un permesso, non una tolleranza.
    assert somma == pytest.approx(
        200.0 * 200.0 * QUOTA_TRAVE + 300.0 * 200.0 * LUNGHEZZA_TRAVE, rel=1e-9
    )


def test_un_prisma_che_attraversa_un_altro_da_parte_a_parte_e_rifiutato():
    """Il soffitto dichiarato del taglio, con il proprio controllo invece che
    come nota: l'accorciamento lungo l'asse non sa dividere un prisma in due.

    Una colonna alta 1600 passa oltre la trave, che sta fra 1300 e 1500: le due
    estremita' restano libere e l'invasione e' una banda centrale. Prima della
    correzione del 20/08/2026 questo caso non sollevava — la guardia guardava
    `invaso[0] and invaso[-1]`, che e' il contenimento, non l'attraversamento.
    Non produceva un accorciamento di zero in silenzio: `libero[-1] + 1` usciva
    dall'array dei campioni e il codice si schiantava con un `IndexError` che
    non diceva all'operatore che la scomposizione era sbagliata.

    Muore se: la guardia torna a controllare il contenimento invece
    dell'attraversamento, o sparisce."""
    passante = hexa.Prisma(
        contorno=COLONNA, origine=np.array([0.0, 0.0, 0.0]),
        asse=np.array([0.0, 0.0, 1.0]), lunghezza=1600.0,
    )
    trave = hexa.Prisma(
        contorno=TRAVE, origine=np.array([0.0, 0.0, QUOTA_TRAVE]),
        asse=np.array([1.0, 0.0, 0.0]), lunghezza=LUNGHEZZA_TRAVE,
    )

    with pytest.raises(ValueError, match="parte a parte"):
        hexa.taglia_giunzioni([passante, trave])


def test_il_telaio_costruito_dichiara_le_superfici_del_tie():
    """La mesh di due membrature adiacenti non combacia nodo a nodo: il legame
    e' un *TIE fra superfici a contatto, e le superfici devono avere facce.

    Non basta che i due nomi esistano nel dizionario: un *TIE su una superficie
    senza facce e' accettato dal solutore e non vincola nulla — verificato con
    CalculiX, che sulla geometria compenetrata esce con codice 0, senza alcun
    `*ERROR`, e stampa `*WARNING in gentiedmpc: no tied MPC`. Le facce sono la
    cosa da asserire.

    Muore se: si toglie il taglio (le due mesh si compenetrano e le superfici
    nominano facce sepolte dentro l'altro solido, che il solutore non lega);
    muore se si toglie la bisezione (le superfici restano vuote, distanti 5,5 mm,
    e `ties` esce vuota); muore se la tolleranza di contatto va a zero (le
    superfici restano vuote per il solo residuo della bisezione)."""
    modello = hexa.costruisci(_telaio_di_prova(), "estruso", ModelConfig())

    assert modello["elementi"].shape[1] == 8
    assert len(modello["blocchi"]) == 2
    assert modello["ties"], "due membrature che si toccano devono avere un *TIE"
    for _nome, dipendente, indipendente in modello["ties"]:
        assert modello["superfici"][dipendente], "superficie dipendente senza facce"
        assert modello["superfici"][indipendente], "superficie indipendente senza facce"
    # una sola giunzione, e legata: nel caso buono i due numeri coincidono
    # (Ruling AA). Muore se "giunzioni" torna a rileggere len(ties) invece di
    # len(giunzioni): con _TOLLERANZA_CONTATTO = 0 (vedi test dedicato sotto)
    # i due numeri divergono, e solo l'assert su "giunzioni" lo vedrebbe.
    assert modello["metriche"]["giunzioni"] == 1
    assert modello["metriche"]["ties"] == 1
    assert modello["metriche"]["accorciamenti"] == pytest.approx(
        [ACCORCIAMENTO_ATTESO], abs=1e-6
    )


def test_un_telaio_senza_legami_avvisa_invece_di_uscire_muto():
    """A1 del giro di correzione 1. Un gioco di 0,1 mm fra colonna e trave --
    sotto la risoluzione di qualunque scanner -- e' geometricamente identico,
    nello stato interno, alla scelta deliberata di modellare due membrature
    come corpi separati (Ruling Z): in nessuno dei due casi c'e' un errore da
    sollevare. Ma senza avviso l'operatore riceve `ties=()` e
    `accorciamenti=[]` senza un fiato, e non puo' distinguere un modello
    voluto da uno rotto.

    Muore se: si toglie il conteggio `metriche["membrature_non_legate"]`, o
    si toglie il `warnings.warn` quando e' maggiore di zero."""
    colonna = _membratura_finta(
        COLONNA, [0.0, 0.0, 0.0], [0.0, 0.0, 1.0], QUOTA_TRAVE - 0.1, [0.0, 0.0, 1.0]
    )
    trave = _membratura_finta(
        TRAVE, [0.0, 0.0, QUOTA_TRAVE], [1.0, 0.0, 0.0], LUNGHEZZA_TRAVE, [1.0, 0.0, 0.0]
    )

    with pytest.warns(hexa.MembratureNonLegateWarning):
        modello = hexa.costruisci([colonna, trave], "estruso", ModelConfig())

    assert modello["metriche"]["membrature_non_legate"] == 2
    assert modello["ties"] == ()


def test_una_membratura_sola_non_avvisa_di_non_essere_legata():
    """Il rovescio del test qui sopra. Una membratura sola non ha niente a cui
    legarsi: l'avviso direbbe il vero senza dire nulla, e un avviso che si
    ripete su un caso normale insegna a ignorarlo proprio quando conta. Il
    conteggio pero' resta, perche' e' un fatto e non un giudizio.

    Muore se: la condizione dell'avviso torna a essere il solo `non_legate`
    senza il vincolo sul numero di membrature."""
    import warnings as modulo_avvisi

    sola = _membratura_finta(RETTANGOLO, [0.0, 0.0, 0.0], [0.0, 0.0, 1.0], LUNGHEZZA, ASSE_Z)

    with modulo_avvisi.catch_warnings():
        modulo_avvisi.simplefilter("error", hexa.MembratureNonLegateWarning)
        esito = hexa.costruisci([sola], "estruso", ModelConfig())

    assert esito["metriche"]["membrature_non_legate"] == 1


def test_una_sovrapposizione_d_angolo_che_la_baricentrica_non_vede_e_rifiutata():
    """A2 del giro di correzione 1. La retta baricentrica del prisma minore
    puo' mancare il maggiore anche quando i due prismi si compenetrano
    davvero: qui il 4% del volume della trave (200.000 mm^3) e' dentro la
    colonna, ma la loro sovrapposizione e' tutta in un angolo che la
    baricentrica non attraversa. Senza la guardia sulle rette dei vertici il
    volume verrebbe contato due volte senza alcun segnale -- l'errore esatto
    che il docstring di `taglia_giunzioni` dice di cercare.

    Geometria e percentuale riprodotte in proprio (non lette da un rapporto):
    colonna 400x400 lungo z per 1000, trave 100x100 lungo x per 500 con
    origine [-400, -80, 500] -- la trave attraversa l'angolo della colonna fra
    x=0 e x=20 circa, fuori dall'asse baricentrico della trave (y=-30, fuori
    dai suoi stessi limiti di sezione).

    Muore se: la guardia additiva sulle rette dei vertici viene tolta, o si
    allarga a scattare anche quando la baricentrica gia' vede l'invasione
    (cambierebbe l'esito di test gia' verdi)."""
    colonna = hexa.Prisma(
        contorno=np.array([[0.0, 0.0], [400.0, 0.0], [400.0, 400.0], [0.0, 400.0]]),
        origine=np.array([0.0, 0.0, 0.0]), asse=np.array([0.0, 0.0, 1.0]), lunghezza=1000.0,
    )
    trave = hexa.Prisma(
        contorno=np.array([[0.0, 0.0], [100.0, 0.0], [100.0, 100.0], [0.0, 100.0]]),
        origine=np.array([-400.0, -80.0, 500.0]), asse=np.array([1.0, 0.0, 0.0]), lunghezza=500.0,
    )

    with pytest.raises(ValueError, match="sovrapposizione d'angolo"):
        hexa.taglia_giunzioni([colonna, trave])


def test_un_prisma_interamente_contenuto_in_un_altro_e_rifiutato():
    """B1 del giro di correzione 1: meta' del soffitto dichiarato del taglio
    (il contenimento) non aveva un proprio test -- il revisore ha mutato la
    guardia in `if False` e la suite e' rimasta verde 16/16.

    Mutazione applicata e verificata in questa sessione: `if invaso[0] and
    invaso[-1]:` -> `if False:` fa morire questo test (nessun ValueError
    sollevato); ripristinata subito dopo (vedi task-8-report.md).

    Muore se: la guardia del contenimento sparisce o e' resa inattiva."""
    grande = hexa.Prisma(
        contorno=np.array([[0.0, 0.0], [400.0, 0.0], [400.0, 400.0], [0.0, 400.0]]),
        origine=np.array([0.0, 0.0, 0.0]), asse=np.array([0.0, 0.0, 1.0]), lunghezza=1000.0,
    )
    piccolo = hexa.Prisma(
        contorno=np.array([[50.0, 50.0], [150.0, 50.0], [150.0, 150.0], [50.0, 150.0]]),
        origine=np.array([0.0, 0.0, 300.0]), asse=np.array([0.0, 0.0, 1.0]), lunghezza=200.0,
    )

    with pytest.raises(ValueError, match="interamente dentro"):
        hexa.taglia_giunzioni([grande, piccolo])


def test_una_superficie_vuota_non_produce_un_tie(monkeypatch):
    """B2 del giro di correzione 1, e la stessa geometria mostra anche A3
    (Ruling AA): a `_TOLLERANZA_CONTATTO = 0.0` il taglio avviene comunque
    (`giunzioni == 1`, il taglio e' indipendente dalla tolleranza di
    contatto) ma il residuo della bisezione lascia i nodi appena fuori dal
    margine nullo, le superfici tagliate escono vuote, e senza un vincolo su
    quello nessun `*TIE` si forma (`ties == 0`): i due numeri divergono
    apposta, ed e' il caso in cui la distinzione introdotta da A3 conta.

    Mutazione applicata e verificata in questa sessione: `if
    superfici[nomi[0]] and superfici[nomi[1]]:` -> `if True:` fa morire questo
    test (produce un `*TIE` su una superficie senza facce, cioe' esattamente
    il modo di fallire con `no tied MPC` che da' il nome al task); ripristinata
    subito dopo (vedi task-8-report.md).

    Muore se: la guardia sulla superficie vuota sparisce o diventa sempre
    vera.

    Anche il test di `GiunzioneSenzaTieWarning` (giro di correzione 4, punto
    3): questa giunzione e' tagliata (`giunzioni == 1`) ma non lega
    (`ties == 0`), il caso esatto per cui l'avviso esiste. Muore se
    l'avviso sparisce o smette di scattare quando una giunzione tagliata
    non produce un `*TIE`."""
    monkeypatch.setattr(hexa, "_TOLLERANZA_CONTATTO", 0.0)
    with pytest.warns(hexa.GiunzioneSenzaTieWarning):
        modello = hexa.costruisci(_telaio_di_prova(), "estruso", ModelConfig())

    assert modello["metriche"]["giunzioni"] == 1
    assert modello["metriche"]["ties"] == 0
    assert modello["ties"] == ()
    assert modello["superfici"] == {}


def test_il_telaio_a_quattro_membrature_si_costruisce_ruling_ad():
    """Giro di correzione 3: `hexa.costruisci` sollevava su `TELAIO`
    (`tests/test_wall.py:33-38`), la geometria piu' vicina al caso reale che
    il progetto abbia -- non una geometria inventata per rompere. Con due
    prismi il criterio per area e quello per asse invaso coincidono sempre
    (RETTANGOLO/COLONNA/TRAVE dei test sopra non l'avrebbero mai visto): qui
    servono le quattro membrature del telaio, e il dato di ingresso lo
    produce la pipeline vera di wall.py (scarta_pavimento, scomponi, terna,
    misura, controlla -- gli stessi passi di `wall.prior`, non la mia mano),
    non una `Membratura` finta.

    Sul telaio, uno dei quattro accoppiamenti sceglie il ruolo sbagliato con
    «cede la sezione minore»: la sovrapposizione e' un montante che entra nel
    traverso da sotto, e accorciare il traverso lungo il proprio asse non la
    toglie -- e' il caso che la guardia d'angolo del Ruling Y intercetta e
    trasforma in un `ValueError` invece di lasciarlo passare in silenzio.

    Muore se: si ripristina il criterio «cede il prisma di sezione minore»
    (`invaso = dentro(tagliati[maggiore], ...)` con `minore`/`maggiore` presi
    direttamente dall'ordine per area, senza il confronto fra i due assi
    baricentrici) -- verificato applicando davvero quella mutazione: solleva
    `ValueError` con `"sovrapposizione d'angolo"` invece di costruire."""
    from meshrec.core import synth, wall
    from meshrec.core.config import SegmentConfig, WallConfig

    telaio = [
        ((0.0, -90.0, 0.0), (200.0, 180.0, 1600.0)),
        ((1400.0, -130.0, 0.0), (200.0, 260.0, 1600.0)),
        ((0.0, -70.0, 1600.0), (1600.0, 140.0, 300.0)),
        ((0.0, -170.0, -300.0), (1600.0, 340.0, 300.0)),
    ]
    spaziatura = 20.0
    punti = synth.sample_frame_surface(telaio, spaziatura)
    cfg_segment = SegmentConfig()
    cfg_wall = WallConfig()

    # Gli stessi passi di wall.prior, senza la serializzazione JSON finale che
    # prior fa per il disco/browser: hexa.costruisci vuole oggetti Membratura,
    # non il dizionario di soli tipi JSON che prior restituisce.
    puliti, _maschera, _ = wall.scarta_pavimento(punti, cfg_segment, cfg_wall, spaziatura)
    regioni_punti, *_ = wall.scomponi(puliti, cfg_segment, cfg_wall, spaziatura)
    direzioni, _ = wall.terna(puliti)
    accettate = []
    for indici in regioni_punti:
        membratura = wall.misura(puliti[indici], direzioni, cfg_wall)
        membratura.punti = indici
        membratura.esiti = wall.controlla(membratura, cfg_wall)
        if all(esito["passato"] for esito in membratura.esiti.values()):
            accettate.append(membratura)
    assert len(accettate) == 4, "il banco ha quattro membrature: se ne arrivano altre, non e' piu' questo test"

    modello = hexa.costruisci(accettate, "estruso", ModelConfig())

    assert len(modello["blocchi"]) == 4
    assert modello["metriche"]["giunzioni"] == 4
    assert modello["metriche"]["membrature_non_legate"] == 0
    # Misurato in questa sessione (giro di correzione 5, dopo Ruling AF): 4 su
    # 4, non 2 come nel giro 4. Il criterio per baricentro (vedi
    # `abaqus.tie_surface`) trova una superficie non vuota anche sulle due
    # giunzioni dove il criterio per nodi uno dei due lati restava a zero
    # (una faccia puo' avere il baricentro dentro l'altro solido pur non
    # avendo tutti i nodi dentro). Misurato, non assunto: la previsione era
    # quattro, e il numero letto e' quattro.
    assert modello["metriche"]["ties"] == 4


def test_il_cuneo_e_calcolato_dalla_geometria_e_allarga_le_facce_a_contatto():
    """Ruling AE (giro di correzione 4): il taglio produce una faccia piana e
    perpendicolare all'asse di chi cede; se le due membrature non sono in
    squadra, quella faccia non coincide con la superficie -- in generale
    inclinata -- di chi riceve, e resta un cuneo. Colonna qui e' fuori piombo
    di 1 grado, con un tilt in Y-Z e non in X-Z: un tilt in X-Z farebbe
    scattare `_base_del_piano` su un'altra coppia di assi di riferimento
    (verificato in questa sessione con `_asse_baricentrico_invaso` -- il
    criterio di Ruling AD stesso cambierebbe chi cede), che non e' cio' che
    questo test vuole isolare.

    Provenienza del cuneo atteso: il centro della sezione 200x200 di colonna
    dista 100 mm dal proprio bordo lungo la direzione del tilt; il cuneo e'
    quella distanza per la tangente dell'angolo fuori squadra --
    100 * tan(1 grado) = 1,7455 mm.

    I conteggi delle facce (20 sul lato dipendente per baricentro, 26 sul
    lato indipendente per "tocca" -- Ruling AH del giro di correzione 6)
    erano letti da `hexa.costruisci` ed asseriti esatti. **Non lo sono piu'**
    (#66): dipendono dal maglio, e il maglio di gmsh dipende dalla
    piattaforma. Le asserzioni sono ora sul **regime** e non sul valore --
    vedi il commento accanto.

    Muore se: la tolleranza di contatto torna a essere solo
    `_TOLLERANZA_CONTATTO`, senza il cuneo per giunzione -- misurato in
    questa sessione che le facce scendono da 20/26 a 10/16 (mutazione
    applicata: `tolleranza = max(_TOLLERANZA_CONTATTO, ...)` ->
    `tolleranza = _TOLLERANZA_CONTATTO`)."""
    angolo = np.radians(1.0)
    colonna = _membratura_finta(
        COLONNA, [0.0, 0.0, 0.0], [0.0, np.sin(angolo), np.cos(angolo)],
        ALTEZZA_COLONNA, [0.0, 0.0, 1.0],
    )
    trave = _membratura_finta(
        TRAVE, [0.0, 0.0, QUOTA_TRAVE], [1.0, 0.0, 0.0], LUNGHEZZA_TRAVE, [1.0, 0.0, 0.0]
    )

    prismi = [hexa.prisma_di(colonna, "estruso"), hexa.prisma_di(trave, "estruso")]
    _tagliati, giunzioni = hexa.taglia_giunzioni(prismi)
    assert giunzioni[0]["cuneo"] == pytest.approx(100.0 * np.tan(angolo), rel=1e-6)

    modello = hexa.costruisci([colonna, trave], "estruso", ModelConfig())
    assert modello["ties"], "la giunzione fuori squadra deve comunque legarsi"
    _nome, dipendente, indipendente = modello["ties"][0]
    # Confini e non valori registrati (#66). I conteggi esatti dipendono dal
    # maglio, e il maglio dipende dalla piattaforma: misurato in CI, gmsh
    # 4.15.2 rende 1221 nodi e 832 esaedri su macOS arm64 contro 1188 e 800
    # su Linux x86-64, a parita' di versione e di ingresso. Su questo provino
    # il lato dipendente valeva 20 facce su macOS e 19 su Linux.
    #
    # Cio' che il test vuole distinguere non e' il conteggio: e' il regime.
    # Con il cuneo le facce sono 20/26, senza (mutazione dichiarata nel
    # docstring) crollano a 10/16 -- un fattore due. I confini stanno a meta'
    # fra i due regimi, quindi la mutazione resta morta con ampio margine e
    # una differenza di poche facce fra piattaforme non fabbrica un rosso.
    assert len(modello["superfici"][dipendente]) >= 15, "senza il cuneo sarebbero 10"
    assert len(modello["superfici"][indipendente]) >= 21, "senza il cuneo sarebbero 16"


def _prisma_scatola(origine, asse, lati, lunghezza):
    """Un parallelepipedo come Prisma: contorno rettangolare centrato nel piano locale."""
    a, b = lati
    contorno = np.array([[-a / 2, -b / 2], [a / 2, -b / 2], [a / 2, b / 2], [-a / 2, b / 2]])
    return hexa.Prisma(
        contorno=contorno, origine=np.asarray(origine, dtype=np.float64),
        asse=np.asarray(asse, dtype=np.float64), lunghezza=float(lunghezza),
    )


def _rileggi_step(percorso):
    """Solidi e volume totale del file STEP, riletti con gmsh: e' l'oracolo, non la funzione."""
    import gmsh
    inizializza(gmsh)
    try:
        gmsh.option.setNumber("General.Terminal", 0)
        entita = gmsh.model.occ.importShapes(str(percorso))
        gmsh.model.occ.synchronize()
        solidi = [tag for dim, tag in entita if dim == 3]
        return len(solidi), sum(gmsh.model.occ.getMass(3, tag) for tag in solidi)
    finally:
        gmsh.finalize()


def test_due_prismi_a_t_danno_un_solido_di_volume_analitico(tmp_path):
    """Pilastro verticale 300x300x3000 e trave 300x500x4000 appoggiata in testa,
    a contatto: un solido, volume = somma dei due (rel 1e-9)."""
    pilastro = _prisma_scatola((0.0, 0.0, 0.0), (0.0, 0.0, 1.0), (300.0, 300.0), 3000.0)
    trave = _prisma_scatola((-500.0, 0.0, 3250.0), (1.0, 0.0, 0.0), (300.0, 500.0), 4000.0)
    metrica = hexa.scrivi_step([pilastro, trave], tmp_path / "modello.step")
    atteso = 300.0 * 300.0 * 3000.0 + 300.0 * 500.0 * 4000.0
    assert metrica["solidi"] == 1
    assert metrica["volume_analitico"] == pytest.approx(atteso, rel=1e-9)
    assert metrica["volume"] == pytest.approx(atteso, rel=1e-9)
    assert metrica["scarto_relativo"] == pytest.approx(0.0, abs=1e-9)
    solidi, volume = _rileggi_step(tmp_path / "modello.step")
    assert solidi == 1
    assert volume == pytest.approx(atteso, rel=1e-9)


def test_due_prismi_disgiunti_restano_due_solidi_e_il_file_si_scrive(tmp_path):
    """Dieci millimetri d'aria: nessuna eccezione, `solidi == 2`, volume = somma."""
    a = _prisma_scatola((0.0, 0.0, 0.0), (0.0, 0.0, 1.0), (300.0, 300.0), 3000.0)
    b = _prisma_scatola((310.0, 0.0, 0.0), (0.0, 0.0, 1.0), (300.0, 300.0), 3000.0)
    metrica = hexa.scrivi_step([a, b], tmp_path / "modello.step")
    assert metrica["solidi"] == 2
    assert metrica["volume"] == pytest.approx(2 * 300.0 * 300.0 * 3000.0, rel=1e-9)
    # Niente si compenetra: i due volumi coincidono e lo scarto e' zero. Uno
    # `scarto_relativo` costante nel ramo multi-solido passerebbe senza queste due.
    assert metrica["volume_analitico"] == pytest.approx(metrica["volume"], rel=1e-9)
    assert metrica["scarto_relativo"] == pytest.approx(0.0, abs=1e-9)
    assert _rileggi_step(tmp_path / "modello.step")[0] == 2


def test_costruisci_senza_membrature_solleva_prima_di_toccare_il_disco():
    """Il gemello di `test_zero_prismi_non_scrivono_un_file` sull'altra porta del
    modulo: lista vuota di membrature, non sezione rifiutata. Il piano la dava
    coperta da `test_una_corsa_figlia_fallita...`, che prova invece il
    riempimento «vuoto» -- un'altra guardia, un altro messaggio."""
    with pytest.raises(ValueError, match="nessuna membratura"):
        hexa.costruisci([], "estruso", ModelConfig())


def test_zero_prismi_non_scrivono_un_file(tmp_path):
    with pytest.raises(ValueError, match="membratura"):
        hexa.scrivi_step([], tmp_path / "modello.step")
    assert not (tmp_path / "modello.step").exists()


def test_una_lunghezza_non_finita_solleva_prima_di_gmsh_e_non_scrive(tmp_path):
    """`lunghezza=nan` arrivava fino a `occ.extrude`, che abbatte il processo con
    SIGSEGV (verificato a mano il 08/09/2026: exit 139). La guardia sta prima di
    `gmsh.initialize()` e nomina indice e valore, come in `mesh_prisma`."""
    buono = _prisma_scatola((0.0, 0.0, 0.0), (0.0, 0.0, 1.0), (300.0, 300.0), 3000.0)
    rotto = _prisma_scatola((1000.0, 0.0, 0.0), (0.0, 0.0, 1.0), (300.0, 300.0), 1.0)
    rotto = hexa.Prisma(
        contorno=rotto.contorno, origine=rotto.origine, asse=rotto.asse,
        lunghezza=float("nan"),
    )
    with pytest.raises(ValueError, match=r"prisma 1.*nan"):
        hexa.scrivi_step([buono, rotto], tmp_path / "modello.step")
    assert not (tmp_path / "modello.step").exists()


def test_un_contorno_collineare_solleva_prima_di_gmsh_e_non_scrive(tmp_path):
    """Tre punti su una retta: area zero. Prima della guardia lo scarto relativo
    divideva per zero *dopo* aver scritto il file, e restava un `modello.step`
    che nessuna metrica accompagnava."""
    collineare = hexa.Prisma(
        contorno=np.array([[0.0, 0.0], [100.0, 0.0], [200.0, 0.0]]),
        origine=np.zeros(3), asse=ASSE_Z, lunghezza=3000.0,
    )
    with pytest.raises(ValueError, match=r"prisma 0.*area"):
        hexa.scrivi_step([collineare], tmp_path / "modello.step")
    assert not (tmp_path / "modello.step").exists()


def test_una_scrittura_interrotta_non_lascia_un_modello_step_col_nome_finale(tmp_path, monkeypatch):
    """`gmsh.write` che muore a meta' non deve lasciare un `modello.step` monco
    col nome finale: chi rilegge gli artefatti lo prenderebbe per completo.
    Come gli altri artefatti, passa da `io.scrivi_atomico`."""
    import gmsh

    def a_meta(percorso, *args, **kwargs):
        Path(percorso).write_text("ISO-10303-21;\n", encoding="utf-8")
        raise RuntimeError("scrittura interrotta")

    monkeypatch.setattr(gmsh, "write", a_meta)
    pilastro = _prisma_scatola((0.0, 0.0, 0.0), (0.0, 0.0, 1.0), (300.0, 300.0), 3000.0)
    with pytest.raises(RuntimeError, match="scrittura interrotta"):
        hexa.scrivi_step([pilastro], tmp_path / "modello.step")
    assert not (tmp_path / "modello.step").exists()


def test_il_prisma_fuori_piombo_fonde_con_la_trave_e_lo_scarto_e_il_cuneo(tmp_path):
    """Due gradi di fuori piombo (misurato in #188: fonde a opzioni predefinite).
    La testa inclinata entra nella trave per un cuneo B*tan(theta)*(B/2)^2/2
    (la formula di esperimento.py, caso_piombo): il volume fuso e' l'analitico
    meno il cuneo, e lo scarto lo dichiara -- 1,35e-4, non zero."""
    theta = np.radians(2.0)
    asse = np.array([np.sin(theta), 0.0, np.cos(theta)])
    lunghezza = 3000.0 / np.cos(theta)
    pilastro = _prisma_scatola((0.0, 0.0, 0.0), asse, (300.0, 300.0), lunghezza)
    trave = _prisma_scatola((-500.0, 0.0, 3250.0), (1.0, 0.0, 0.0), (300.0, 500.0), 4000.0)
    metrica = hexa.scrivi_step([pilastro, trave], tmp_path / "modello.step")
    analitico = 300.0 * 300.0 * lunghezza + 300.0 * 500.0 * 4000.0
    cuneo = 300.0 * np.tan(theta) * 150.0 ** 2 / 2.0
    assert metrica["solidi"] == 1
    assert metrica["volume_analitico"] == pytest.approx(analitico, rel=1e-9)
    assert metrica["volume"] == pytest.approx(analitico - cuneo, rel=1e-9)
    assert metrica["scarto_relativo"] == pytest.approx(cuneo / analitico, rel=1e-6)


def test_un_prisma_solo_non_fonde_nulla_e_il_volume_e_quello(tmp_path):
    """Un solo prisma: nessun `fuse` (vuole oggetto e strumento), un solido,
    volume esattamente area·lunghezza."""
    pilastro = _prisma_scatola((0.0, 0.0, 0.0), (0.0, 0.0, 1.0), (300.0, 300.0), 3000.0)
    metrica = hexa.scrivi_step([pilastro], tmp_path / "modello.step")
    assert metrica["solidi"] == 1
    assert metrica["volume"] == pytest.approx(300.0 * 300.0 * 3000.0, rel=1e-9)
    assert metrica["scarto_relativo"] == pytest.approx(0.0, abs=1e-9)
    assert _rileggi_step(tmp_path / "modello.step") == (1, pytest.approx(300.0 * 300.0 * 3000.0, rel=1e-9))
    # `schema: "AP214"` e' l'unico campo della metrica che nessun altro controllo
    # smentisce: gmsh 4.15.2 lo scrive come FILE_SCHEMA(('AUTOMOTIVE_DESIGN ...')).
    intestazione = (tmp_path / "modello.step").read_text(encoding="utf-8", errors="replace")[:2000]
    assert "AUTOMOTIVE_DESIGN" in intestazione
