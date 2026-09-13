"""I modelli parametrici: prismi di membratura in mesh esaedrica.

hexa.py **costruisce e non misura**: riceve da wall.py sezioni, assi e
lunghezze gia' misurati e ne fa una mesh. Il confine con wall.py non e'
estetico, e' cio' che rende ciascuno dei due verificabile da solo contro una
geometria a verita' nota.

La mesh esaedrica si fa con gmsh, che dalla Fase 4 e' una dipendenza vera e non
un extra: superficie piana dal contorno, ricombinazione in quadrilateri,
estrusione a strati. Il modulo non riscrive `gmsh_backend.py`, che genera mesh
tetraedriche da una STL ed e' un'altra macchina; ne riprende pero' due
abitudini, perche' sono state pagate: la rimappatura dei tag di nodo su indici
di array, e l'inizializzazione per tentativo con il `finalize` in un `finally`.
"""

from __future__ import annotations

import warnings
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from meshrec.core import abaqus, io
from meshrec.core.config import ModelConfig
from meshrec.core.gmsh_backend import inizializza
from meshrec.core.wall import ruoli_dell_incontro

_ARROTONDAMENTO = 6
"""Cifre decimali su cui i nodi sono confrontati per l'ordine canonico.

Non e' una tolleranza geometrica: e' la risoluzione oltre la quale due
coordinate prodotte dalla stessa costruzione differiscono solo per l'ultimo
bit. In millimetri, un nanometro.
"""


def passo_di_mesh(contorno: np.ndarray, cfg: ModelConfig) -> float:
    """Passo caratteristico che rispetta il vincolo degli strati nello spessore.

    Il vincolo e' imposto dal codice e non suggerito: con uno o due strati la
    flessione nello spessore non e' rappresentata, e il risultato e' sbagliato
    senza alcun segnale. Il passo chiesto in configurazione, se c'e', viene
    quindi ridotto fin dove serve, mai alzato.
    """
    punti = np.asarray(contorno, dtype=np.float64)
    minima = float(np.min(np.ptp(punti, axis=0)))
    # Criterio scritto in positivo (#36, e ora #50): `minima <= 0.0` e' falso
    # per `nan`, quindi un contorno con un vertice non finito rendeva un passo
    # `nan` -- eseguito e misurato. Buono se e solo se finito e positivo.
    #
    # Il ticket sosteneva che quel `nan` finisse in
    # `gmsh.model.geo.addPoint(u, v, 0.0, passo)`: **e' falso**, verificato
    # tracciando `addPoint`, che viene chiamato **zero** volte. In
    # `mesh_prisma` il passo passa prima per `int(round(lunghezza / passo))`
    # (:165), che su `nan` solleva `ValueError: cannot convert float NaN to
    # integer`. Il difetto quindi non era una mesh corrotta ma un errore
    # opaco: sollevato dentro una conversione a intero, dopo l'import di
    # gmsh, senza nominare ne' il contorno ne' il passo. La funzione resta
    # pero' pubblica e chiamabile da sola -- ed era li' che rendeva `nan`
    # senza dire nulla.
    if not (np.isfinite(minima) and minima > 0.0):
        raise ValueError(
            f"il contorno ha estensione nulla o non finita su un asse "
            f"(minima={minima!r} mm): non è una sezione valida per un prisma"
        )
    tetto = minima / cfg.min_layers
    if cfg.target_size is None:
        return tetto
    return min(float(cfg.target_size), tetto)


def ordine_canonico(nodi: np.ndarray, esaedri: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Riordina nodi ed elementi in un ordine funzione delle sole coordinate.

    I tag di gmsh sono un ordine di generazione, non un dato della geometria, e
    un conteggio o un indice che ne dipendesse dipenderebbe dalla piattaforma:
    e' la stessa lezione gia' pagata sull'ordine dei voxel di Open3D fra
    Windows x86-64 e macOS arm64 (quinto vincolo di prodotto).

    L'ordine **interno** dei nodi di un esaedro non si tocca: e' la topologia
    dell'elemento, e riordinarlo cambierebbe il solido invece del suo nome.
    Si riordinano i nodi fra loro e gli elementi fra loro.
    """
    punti = np.asarray(nodi, dtype=np.float64)
    elementi = np.asarray(esaedri, dtype=np.int64)

    chiave = np.round(punti, _ARROTONDAMENTO)
    # lexsort ordina per l'ultima chiave data: (z, y, x) ordina per x, poi y, poi z
    permutazione = np.lexsort((chiave[:, 2], chiave[:, 1], chiave[:, 0]))
    posizione = np.empty(len(punti), dtype=np.int64)
    posizione[permutazione] = np.arange(len(punti))

    rimappati = posizione[elementi]
    # gli elementi si ordinano per la tupla dei propri nodi rimappati, che e'
    # un numero della geometria; lexsort vuole le chiavi dall'ultima alla prima
    ordine = np.lexsort(rimappati.T[::-1])
    return np.ascontiguousarray(punti[permutazione]), np.ascontiguousarray(rimappati[ordine])


def _area_poligono(contorno: np.ndarray) -> float:
    """Area con segno di un poligono chiuso, formula di Gauss.

    Solleva su un vertice non finito invece di rendere `nan` (#50). Quattro
    chiamanti, e tre usi diversi dello stesso numero: il **segno** decide un
    orientamento in `mesh_prisma` (:161) e in `dentro_prisma` (:342),
    l'**ampiezza** e' l'area della sezione (:163), e l'ampiezza negata e' una
    **chiave di ordinamento** in `taglia_giunzioni` (:569).

    I tre usi degenerano in modo diverso, e nessuno si vede: `nan < 0.0` e'
    falso, quindi il contorno rotto non viene invertito e la mesh esce con
    esaedri rovesciati o il test di appartenenza risponde al contrario; e un
    `nan` come chiave di `sorted` rende l'ordine arbitrario, perche' ogni
    confronto con `nan` e' falso.

    La guardia sta qui e non nei chiamanti perche' e' qui che tutti e quattro
    passano: una copia per sito sarebbe la stessa guardia scritta quattro
    volte, e dimenticata al quinto.
    """
    punti = np.asarray(contorno, dtype=np.float64)
    if not np.isfinite(punti).all():
        raise ValueError(
            "il contorno ha un vertice non finito: l'area con segno non "
            "esiste, quindi l'orientamento del poligono non è determinabile"
        )
    x, y = punti.T
    return float(0.5 * (np.dot(x, np.roll(y, -1)) - np.dot(y, np.roll(x, -1))))


def _base_del_piano(asse: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Due versori ortogonali all'asse, scelti in modo deterministico.

    Il riferimento e' l'asse coordinato meno allineato all'asse del prisma:
    sceglierlo dal dato invece che a caso rende la base la stessa su due
    esecuzioni, e quindi la mesh la stessa.
    """
    versore = np.asarray(asse, dtype=np.float64)
    versore = versore / np.linalg.norm(versore)
    candidati = np.eye(3)
    riferimento = candidati[int(np.argmin(np.abs(candidati @ versore)))]
    e1 = riferimento - versore * np.dot(riferimento, versore)
    e1 = e1 / np.linalg.norm(e1)
    return e1, np.cross(versore, e1)


def mesh_prisma(
    contorno: np.ndarray,
    origine: np.ndarray,
    asse: np.ndarray,
    lunghezza: float,
    cfg: ModelConfig,
) -> tuple[np.ndarray, np.ndarray, dict[str, object]]:
    """Un prisma retto in esaedri: contorno di sezione estruso lungo l'asse.

    La sagoma viene costruita nel piano locale, ricombinata in quadrilateri ed
    estrusa a strati; solo alla fine il prisma viene ruotato e traslato al
    proprio posto. Costruire in locale e trasformare con numpy tiene fuori da
    gmsh ogni scelta di riferimento, che e' l'unica parte di questa funzione da
    cui potrebbe entrare una dipendenza dalla piattaforma.

    Il contorno e' orientato in senso antiorario prima di essere passato a
    gmsh: con l'orientazione opposta l'estrusione produce esaedri rovesciati,
    con Jacobiano negativo, e nessuna metrica della mesh lo direbbe guardandola.

    Restituisce nodi, esaedri e metriche, con nodi ed elementi gia' in ordine
    canonico.

    Va chiamata serialmente: `gmsh.initialize()`/`gmsh.finalize()` operano su
    stato globale di modulo, non per istanza, e due chiamate concorrenti (thread
    o processi che condividono lo stato) si pesterebbero i piedi.
    """
    if not (np.isfinite(float(lunghezza)) and float(lunghezza) > 0.0):
        raise ValueError(
            f"lunghezza={lunghezza!r} non è finita e positiva: un prisma "
            "richiede un'estrusione di lunghezza maggiore di zero"
        )

    import gmsh

    sagoma = np.asarray(contorno, dtype=np.float64)
    if _area_poligono(sagoma) < 0.0:
        sagoma = sagoma[::-1]
    area = abs(_area_poligono(sagoma))
    passo = passo_di_mesh(sagoma, cfg)
    strati = max(cfg.min_layers, int(round(float(lunghezza) / passo)))

    inizializza(gmsh)
    try:
        gmsh.option.setNumber("General.Terminal", 0)
        punti = [gmsh.model.geo.addPoint(u, v, 0.0, passo) for u, v in sagoma]
        linee = [
            gmsh.model.geo.addLine(punti[indice], punti[(indice + 1) % len(punti)])
            for indice in range(len(punti))
        ]
        anello = gmsh.model.geo.addCurveLoop(linee)
        superficie = gmsh.model.geo.addPlaneSurface([anello])
        gmsh.model.geo.mesh.setRecombine(2, superficie)
        gmsh.model.geo.extrude(
            [(2, superficie)], 0.0, 0.0, float(lunghezza),
            numElements=[strati], recombine=True,
        )
        gmsh.model.geo.synchronize()
        # A impedire i prismi a base triangolare e' Mesh.RecombineAll=1 sotto,
        # non setRecombine sulla superficie sopra: verificato per mutazione,
        # togliendo setRecombine il risultato non cambia (832 esaedri, stesso
        # numero), mentre senza RecombineAll=1 o senza recombine=True
        # nell'estrusione gmsh non genera piu' esaedri puri, cioe' un elemento
        # che il deck non sa scrivere. setRecombine resta comunque a fissare
        # l'intento sulla faccia sorgente, che RecombineAll applica solo a
        # valle sull'intero maglio.
        gmsh.option.setNumber("Mesh.RecombineAll", 1)
        gmsh.option.setNumber("Mesh.MeshSizeMax", passo)
        gmsh.option.setNumber("Mesh.MeshSizeMin", passo)
        gmsh.option.setNumber("Mesh.MeshSizeExtendFromBoundary", 0)
        gmsh.option.setNumber("Mesh.MeshSizeFromCurvature", 0)
        gmsh.model.mesh.generate(3)

        tag_nodi, coordinate, _ = gmsh.model.mesh.getNodes()
        tipi, _, per_elemento = gmsh.model.mesh.getElements(3)
        if 5 not in list(tipi):
            raise RuntimeError(
                "gmsh non ha prodotto esaedri (tipo 5): la ricombinazione della "
                "sagoma non è riuscita, e un modello a prismi triangolari non è "
                "quello che il deck dichiara"
            )
        tag_esaedri = np.asarray(
            per_elemento[list(tipi).index(5)], dtype=np.int64
        ).reshape(-1, 8)
        versione = gmsh.option.getString("General.Version")
    finally:
        gmsh.finalize()

    tag_nodi = np.asarray(tag_nodi, dtype=np.int64)
    locali = np.ascontiguousarray(np.asarray(coordinate, dtype=np.float64).reshape(-1, 3))
    # I tag dei nodi sono 1-based e non contigui: senza rimappatura gli elementi
    # punterebbero a posizioni sbagliate dell'array, e la mesh sarebbe sbagliata
    # senza alcun segnale. Stessa cautela di gmsh_backend._extract_mesh.
    tavola = np.zeros(tag_nodi.max() + 1, dtype=np.int64)
    tavola[tag_nodi] = np.arange(len(tag_nodi))
    esaedri = np.ascontiguousarray(tavola[tag_esaedri])

    e1, e2 = _base_del_piano(asse)
    versore = np.asarray(asse, dtype=np.float64)
    versore = versore / np.linalg.norm(versore)
    rotazione = np.stack([e1, e2, versore])
    nodi = np.asarray(origine, dtype=np.float64) + locali @ rotazione

    nodi, esaedri = ordine_canonico(nodi, esaedri)
    metriche = {
        "hexes": int(len(esaedri)),
        "nodes": int(len(nodi)),
        "passo": float(passo),
        "strati": int(strati),
        "area_sezione": float(area),
        "volume_analitico": float(area * lunghezza),
        "gmsh_version": versione,
    }
    return nodi, esaedri, metriche


@dataclass(eq=False)
class Prisma:
    """Un prisma retto: contorno di sezione nel proprio piano, origine, asse, lunghezza.

    E' l'unica forma che i modelli parametrici conoscono. Il contorno e'
    convesso perche' viene da `wall.semplifica_contorno`, che ne prende
    l'inviluppo convesso con scipy e poi toglie vertici — e togliere vertici a
    un poligono convesso lo lascia convesso. La convessita' e' cio' che rende
    immediato il test di appartenenza usato dal taglio alle giunzioni.
    """

    contorno: np.ndarray
    origine: np.ndarray
    asse: np.ndarray
    lunghezza: float


def prisma_di(membratura, tipo: str) -> Prisma:
    """Il prisma di una membratura, secondo il modello richiesto.

    Non sono due generatori ma due argomenti: cambia se la sezione conserva la
    forma rilevata o diventa il rettangolo dei valori misurati, e se l'asse
    conserva il fuori piombo misurato o e' l'asse ideale, dritto. Il confronto
    separa cosi' due effetti diversi -- irregolarita' della sezione e fuori
    piombo -- invece di sommarli in un unico salto.

    In nessuno dei due casi la sezione viene dal disegno: prenderla dal disegno
    farebbe misurare al confronto anche lo scarto fra progetto e costruito, che
    e' un'altra domanda.
    """
    if tipo == "estruso":
        return Prisma(
            contorno=np.asarray(membratura.contorno, dtype=np.float64),
            origine=np.asarray(membratura.origine, dtype=np.float64),
            asse=np.asarray(membratura.asse, dtype=np.float64),
            lunghezza=float(membratura.lunghezza),
        )
    if tipo == "primitive":
        # Le due estensioni vengono da `membratura.sezione`, non da
        # `np.ptp(membratura.contorno, axis=0)`: il contorno e' gia' passato
        # da `semplifica_contorno`, che lo riduce a pochi vertici e ne
        # sposta l'inviluppo, mentre `sezione` e' l'estensione dei punti
        # grezzi nella stessa base di piano. Squadrare sul contorno
        # pubblicherebbe come "misurato" un numero che la semplificazione ha
        # gia' alterato.
        #
        # L'ancoraggio e' il centro del contorno (`(minimo + massimo) / 2`),
        # non il suo minimo: `Membratura` non porta il minimo dei punti
        # grezzi, solo `sezione` (le estensioni) e `contorno` (gia'
        # semplificato) -- e semplificare puo' togliere proprio il vertice
        # che realizzava il minimo grezzo. Ancorare al minimo del contorno
        # semplificato mentre le estensioni vengono dai punti grezzi e'
        # la combinazione peggiore delle due: il rettangolo inventa
        # materiale da un lato e non copre quello vero dall'altro,
        # spostando anche l'asse. Il centro non elimina l'errore -- il
        # minimo dei punti grezzi resta un dato che `Membratura` non porta
        # -- ma lo dimezza e lo rende simmetrico, cosi' l'asse non trasla.
        larghezza, altezza = (float(valore) for valore in membratura.sezione)
        contorno_grezzo = np.asarray(membratura.contorno, dtype=np.float64)
        centro = (contorno_grezzo.min(axis=0) + contorno_grezzo.max(axis=0)) / 2.0
        mezza_estensione = np.array([larghezza, altezza]) / 2.0
        rettangolo = centro + mezza_estensione * np.array(
            [[-1.0, -1.0], [1.0, -1.0], [1.0, 1.0], [-1.0, 1.0]]
        )
        return Prisma(
            contorno=rettangolo,
            origine=np.asarray(membratura.origine, dtype=np.float64),
            asse=np.asarray(membratura.asse_ideale, dtype=np.float64),
            lunghezza=float(membratura.lunghezza),
        )
    raise ValueError(f"modello '{tipo}' sconosciuto: i modelli sono 'estruso' e 'primitive'")


MODEL_STEP_SCHEMA = "AP214"  # l'unico che gmsh scrive: dichiarato, non scelto


def scrivi_step(prismi: list[Prisma], percorso: Path) -> dict[str, object]:
    """Il solido fuso dei prismi, scritto in STEP; la metrica porta il suo contraddittorio.

    I prismi sono quelli **non tagliati**: la fusione booleana toglie da se'
    la doppia contabilita' alle giunzioni, che `taglia_giunzioni` esiste per
    togliere alla mesh. Costruzione diretta in coordinate globali nel kernel
    OpenCASCADE, poi `occ.fuse` a opzioni predefinite: misurato il 07/09/2026
    (#188) che fino a 3 gradi di fuori piombo e 3 mm di compenetrazione
    fonde in un solido a volume esatto; prismi disgiunti, a contatto di solo
    spigolo o con un gioco sotto il decimo di millimetro restano solidi
    distinti, e la metrica lo dice con `solidi`.

    `volume_analitico` e' la somma area·lunghezza dei prismi cosi' come
    arrivano: sul telaio del prior i due volumi coincidono fino alla
    compenetrazione alle giunzioni, e lo scarto e' il numero da leggere.

    Va chiamata serialmente, mai con una sessione gmsh gia' aperta:
    `gmsh.initialize()`/`finalize()` sono globali, come per `mesh_prisma`.
    """
    if not prismi:
        raise ValueError(
            "nessuna membratura da scrivere in STEP: il prior non ne ha accettata "
            "alcuna. Guarda le regioni scartate e il controllo che le ha respinte"
        )
    # Prima di gmsh, non dentro: misurato il 08/09/2026 che `lunghezza=nan`
    # arriva a `occ.extrude` e abbatte il processo con SIGSEGV, e che un
    # contorno di area zero si scopre solo alla divisione dello scarto, a file
    # gia' scritto. La stessa area serve poi per `volume_analitico`.
    volumi_analitici = []
    for indice, p in enumerate(prismi):
        lunghezza = float(p.lunghezza)
        if not (np.isfinite(lunghezza) and lunghezza > 0.0):
            raise ValueError(
                f"prisma {indice}: lunghezza={p.lunghezza!r} non è finita e "
                "positiva: un prisma richiede un'estrusione di lunghezza "
                "maggiore di zero"
            )
        area = abs(_area_poligono(np.asarray(p.contorno, dtype=np.float64)))
        if not area > 0.0:
            raise ValueError(
                f"prisma {indice}: area del contorno = {area!r}, il contorno è "
                "degenere (vertici allineati o coincidenti) e non si estrude"
            )
        volumi_analitici.append(area * lunghezza)

    import gmsh

    analitico = float(sum(volumi_analitici))
    inizializza(gmsh)
    try:
        gmsh.option.setNumber("General.Terminal", 0)
        occ = gmsh.model.occ
        volumi = []
        for p in prismi:
            asse = np.asarray(p.asse, dtype=np.float64)
            asse = asse / np.linalg.norm(asse)
            e1, e2 = _base_del_piano(asse)
            origine = np.asarray(p.origine, dtype=np.float64)
            punti = [
                occ.addPoint(*(origine + u * e1 + v * e2))
                for u, v in np.asarray(p.contorno, dtype=np.float64)
            ]
            linee = [
                occ.addLine(punti[i], punti[(i + 1) % len(punti)])
                for i in range(len(punti))
            ]
            superficie = occ.addPlaneSurface([occ.addCurveLoop(linee)])
            estruso = occ.extrude([(2, superficie)], *(asse * float(p.lunghezza)))
            volumi += [tag for dim, tag in estruso if dim == 3]
        if len(volumi) > 1:
            fusi, _ = occ.fuse([(3, volumi[0])], [(3, t) for t in volumi[1:]])
        else:
            fusi = [(3, volumi[0])]
        occ.synchronize()
        # Ordinati per tag: il conteggio e' discreto e non deve dipendere
        # dall'ordine in cui gmsh li restituisce.
        solidi = sorted(tag for dim, tag in fusi if dim == 3)
        volume = float(sum(occ.getMass(3, tag) for tag in solidi))
        io.scrivi_atomico(percorso, lambda destinazione: gmsh.write(str(destinazione)))
    finally:
        gmsh.finalize()
    return {
        "file": str(percorso),
        "schema": MODEL_STEP_SCHEMA,
        "solidi": len(solidi),
        "volume": volume,
        "volume_analitico": analitico,
        "scarto_relativo": abs(volume - analitico) / analitico,
    }


def dentro(prisma: Prisma, punti: np.ndarray, tolleranza: float = 0.0) -> np.ndarray:
    """Quali dei punti dati cadono dentro il prisma, entro la tolleranza data.

    Due condizioni: la coordinata lungo l'asse sta fra zero e la lunghezza, e
    la proiezione sul piano di sezione sta dentro il contorno. Il contorno e'
    convesso, quindi «dentro» significa che tutti i prodotti vettoriali con i
    lati hanno lo stesso segno: nessun algoritmo di ray casting.

    `tolleranza` [mm] allarga la condizione **in tutte le direzioni**: lungo
    l'asse e nel piano di sezione. E' un parametro e non un valore fisso perche'
    ha due usi opposti. Il taglio alle giunzioni la lascia a zero, che e' la
    condizione esatta su cui la bisezione converge; le superfici del `*TIE` la
    chiedono piccola, come margine per il residuo in virgola mobile della
    bisezione stessa. Allargare invece la geometria del prisma -- gonfiarne
    origine e lunghezza -- non sarebbe la stessa cosa e sarebbe sbagliato: lo
    allargherebbe solo lungo il proprio asse e mai nella sezione, che e'
    proprio la direzione in cui due membrature che si incontrano si toccano.
    """
    coordinate = np.atleast_2d(np.asarray(punti, dtype=np.float64))
    versore = prisma.asse / np.linalg.norm(prisma.asse)
    e1, e2 = _base_del_piano(versore)
    relativi = coordinate - prisma.origine

    lungo = relativi @ versore
    nel_tratto = (lungo >= -tolleranza) & (lungo <= prisma.lunghezza + tolleranza)

    sezione = np.column_stack([relativi @ e1, relativi @ e2])
    contorno = prisma.contorno
    if _area_poligono(contorno) < 0.0:
        contorno = contorno[::-1]
    dentro_sezione = np.ones(len(coordinate), dtype=bool)
    for primo, secondo in zip(contorno, np.roll(contorno, -1, axis=0), strict=True):
        lato = secondo - primo
        scostamento = sezione - primo
        # Componente z del prodotto vettoriale, scritta per esteso: np.cross
        # rifiuta i vettori 2D da numpy 2.0 e solleva ValueError. E' la stessa
        # lezione gia' pagata e annotata in wall.semplifica_contorno, che con
        # numpy 2.5 e' l'unica versione che il progetto usa.
        # Il prodotto vale |lato| per la distanza dal lato, quindi la soglia si
        # normalizza sulla lunghezza del lato per essere una distanza in mm.
        verso = lato[0] * scostamento[:, 1] - lato[1] * scostamento[:, 0]
        dentro_sezione &= verso >= -tolleranza * float(np.linalg.norm(lato))
    return nel_tratto & dentro_sezione


_CAMPIONI_ASSE = 200
"""Campioni lungo l'asse con cui si cerca **se** un prisma entra in un altro.

Non e' un parametro di elaborazione: e' la risoluzione con cui si trova
l'intervallo che contiene il bordo, non la precisione del taglio, che e' quella
della bisezione qui sotto. Duecento campioni su una membratura di due metri
sono un centimetro, cioe' sotto la scala di qualunque giunzione.
"""

_PASSI_BISEZIONE = 40
"""Dimezzamenti con cui si trova il bordo del solido dentro l'intervallo trovato.

Quaranta dimezzamenti dividono per 2^40 (~1,1e12): un intervallo di partenza
fino al centimetro scende sotto 1e-11 mm, cioe' sotto la risoluzione di
`_ARROTONDAMENTO` con cui due coordinate prodotte dalla stessa costruzione sono
gia' lo stesso punto.
"""

_TOLLERANZA_CONTATTO = 1e-6
"""Margine minimo [mm] con cui due superfici tagliate a filo sono considerate a contatto.

Un micrometro e' la stessa risoluzione di `_ARROTONDAMENTO`, dove due
coordinate prodotte dalla stessa costruzione sono gia' lo stesso punto. Non e'
un raggio di ricerca e non deve diventarlo: dopo la bisezione le due superfici
distano il solo residuo in virgola mobile, e questo margine copre quello.
Verificato che serve: a tolleranza zero le superfici escono vuote per il solo
residuo di bisezione.

**Ruling AE:** e' un pavimento, non l'intera tolleranza. Il taglio produce una
faccia piana e perpendicolare all'asse di chi cede; se l'asse di chi cede e
quello di chi riceve non sono in squadra, la faccia di contatto di chi riceve
e' inclinata rispetto a quella piana, e i due piani non coincidono mai: resta
un cuneo. La tolleranza usata in `costruisci` e'
`max(_TOLLERANZA_CONTATTO, giunzione["cuneo"])`, dove `cuneo` (vedi
`_cuneo_vertice`) e' calcolato dalla geometria di ciascuna giunzione **prima**
di cercare i nodi -- non e' un raggio di ricerca allargato finche' la ricerca
trova qualcosa: e' la distanza che la geometria misurata impone fra due
superfici che si toccano davvero, e sarebbe la stessa anche senza mai generare
una mesh. E' questo a distinguerlo da un numero allargato a caso per far
passare il controllo: uno e' verificabile prima di cercare, l'altro no.
"""


def _bordo_del_solido(
    maggiore: Prisma, base: np.ndarray, versore: np.ndarray, fuori: float, dentro_s: float
) -> float:
    """Ascissa dell'ultimo punto fuori dal prisma maggiore, per bisezione.

    Bisezione sulla stessa funzione di appartenenza che il taglio usa gia',
    quindi il bordo trovato e' il bordo secondo `dentro` e non secondo una
    seconda descrizione della stessa superficie, che potrebbe non coincidere.
    `fuori` e' un'ascissa fuori dal maggiore, `dentro_s` una dentro; l'ordine
    numerico fra le due non conta.
    """
    for _ in range(_PASSI_BISEZIONE):
        mezzo = 0.5 * (fuori + dentro_s)
        if dentro(maggiore, base + mezzo * versore)[0]:
            dentro_s = mezzo
        else:
            fuori = mezzo
    return fuori


def _distanza_punto_faccia(punto: np.ndarray, angoli: np.ndarray) -> float:
    """Distanza dal punto al quadrilatero piano `angoli` (in ordine di perimetro).

    Non e' la distanza dal nodo o dal baricentro piu' vicino: su una faccia
    grande (mesh rada, come il lato indipendente di Ruling AH) il punto piu'
    vicino puo' cadere lontano da ogni angolo e dal centro, e CalculiX
    proietta ogni nodo dipendente sul punto piu' vicino della faccia intera,
    non su uno dei suoi quattro vertici.

    Si proietta sul piano della faccia; se la proiezione cade dentro il
    perimetro, quella e' la distanza (il segmento punto-proiezione e'
    perpendicolare al piano, quindi minimo). Se cade fuori, il punto piu'
    vicino sta su uno dei quattro lati, e la distanza punto-segmento standard
    (parametro clampato a [0, 1]) la trova.
    """
    normale = np.cross(angoli[1] - angoli[0], angoli[3] - angoli[0])
    normale = normale / np.linalg.norm(normale)
    scarto = float(np.dot(punto - angoli[0], normale))
    proiezione = punto - scarto * normale

    lati = np.roll(angoli, -1, axis=0) - angoli
    scostamenti = proiezione - angoli
    # Componente lungo la normale del prodotto vettoriale lato x scostamento,
    # per esteso: e' la stessa cautela di `dentro` sui vettori 2D, qui non
    # serve perche' i vettori sono gia' 3D, ma il segno interno/esterno del
    # poligono convesso e' lo stesso test.
    dentro_perimetro = all(
        float(np.dot(np.cross(lato, scostamento), normale)) >= 0.0
        for lato, scostamento in zip(lati, scostamenti, strict=True)
    )
    if dentro_perimetro:
        return abs(scarto)

    migliore = float("inf")
    for primo, lato in zip(angoli, lati, strict=True):
        t = float(np.clip(np.dot(punto - primo, lato) / np.dot(lato, lato), 0.0, 1.0))
        vicino = primo + t * lato
        migliore = min(migliore, float(np.linalg.norm(punto - vicino)))
    return migliore


def _asse_baricentrico_invaso(prisma: Prisma, altro: Prisma) -> np.ndarray:
    """Campioni lungo la retta baricentrica di `prisma`, dentro `altro`.

    Usata due volte per coppia, una per verso, per decidere chi cede in
    `taglia_giunzioni` (Ruling AD): cede il prisma il cui asse entra
    nell'altro, non quello di sezione minore.
    """
    versore = prisma.asse / np.linalg.norm(prisma.asse)
    passo = np.linspace(0.0, prisma.lunghezza, _CAMPIONI_ASSE)
    centro_sezione = prisma.contorno.mean(axis=0)
    e1, e2 = _base_del_piano(versore)
    base = prisma.origine + centro_sezione[0] * e1 + centro_sezione[1] * e2
    return dentro(altro, base + np.outer(passo, versore))


def _cuneo_vertice(punto: np.ndarray, versore: np.ndarray, maggiore: Prisma, limite: float) -> float:
    """Distanza, lungo `versore`, dal vertice sulla faccia di taglio al vero bordo di `maggiore`.

    Il taglio produce una faccia piana e perpendicolare all'asse di chi cede,
    trovata per bisezione **sulla sola retta baricentrica**. Se l'asse di chi
    cede non e' in squadra con quello di chi riceve, quella faccia piana non
    coincide con la superficie -- in generale inclinata -- di chi riceve in
    ogni altro punto del contorno: e' un cuneo, e questa funzione lo misura
    per un vertice, con la stessa bisezione che il taglio usa gia' (`dentro`,
    `_bordo_del_solido`), partendo dal vertice invece che dal baricentro.

    La ricerca dell'intervallo raddoppia il passo da `_ARROTONDAMENTO` in su
    (fine vicino al vertice, largo lontano) e si ferma a `limite`: raddoppiare
    senza un tetto rischierebbe di superare un cuneo vero ma sottile -- il
    contorno di chi riceve, sul dato misurato, non e' detto sia pulito (puo'
    avere vertici in piu' dalla compenetrazione residua) -- e agganciare
    un'invasione lontana e indipendente, molto piu' grande e non pertinente a
    questo vertice. Un campionamento uniforme fino a `limite` avrebbe lo stesso
    problema al contrario: passo troppo largo vicino a zero per vedere un
    cuneo sottile. Il raddoppio e' fine dove serve e limitato dove rischia.

    Zero se il vertice e' gia' dentro `maggiore` (il taglio li' sovrappone,
    non manca), zero se nessuna invasione cade entro `limite` (il vertice non
    tocca affatto: un angolo scoperto, non un cuneo), zero se il bordo trovato
    e' sotto la risoluzione di `_ARROTONDAMENTO` -- rumore della bisezione,
    non un cuneo vero. La soglia di rumore e' fissa e non `_TOLLERANZA_CONTATTO`,
    perche' il cuneo deve azzerarsi su un banco squadrato indipendentemente da
    quale tolleranza di contatto sia configurata.
    """
    soglia_rumore = 10.0**-_ARROTONDAMENTO
    if dentro(maggiore, punto)[0]:
        return 0.0
    fuori = 0.0
    passo = soglia_rumore
    while passo <= limite:
        if dentro(maggiore, punto + passo * versore)[0]:
            trovato = _bordo_del_solido(maggiore, punto, versore, fuori, passo)
            return trovato if trovato > soglia_rumore else 0.0
        fuori = passo
        passo *= 2.0
    return 0.0


def taglia_giunzioni(prismi: list[Prisma]) -> tuple[list[Prisma], list[dict[str, object]]]:
    """Accorcia i prismi minori dove entrano in un prisma maggiore.

    Le membrature si compenetrano dove si incontrano, e senza taglio il volume
    alle giunzioni viene contato due volte: un errore che nessuna metrica di
    qualita' della mesh vedrebbe, e per questo il controllo di chiusura del
    volume lo cerca esplicitamente.

    Il taglio si ferma sul **bordo del solido**, non sull'ultimo campione
    libero: i campioni servono solo a trovare l'intervallo che contiene il
    bordo, e la bisezione lo stringe fin sotto il rumore in virgola mobile.
    **E' la precisione del taglio a rendere possibile il `*TIE`**: fermarsi sul
    campione lascia fra le due membrature un vuoto grande quanto il passo di
    campionamento, cioe' `lunghezza / (_CAMPIONI_ASSE - 1)` -- e due superfici
    a quella distanza non si legano. Legarle allargando il raggio di ricerca
    farebbe passare il controllo senza rendere giusto il modello.

    Chi cede lo decide `wall.ruoli_dell_incontro` (Ruling AD), che e' anche il
    solo posto dove quel criterio e' scritto: qui non se ne tiene una seconda
    copia, o le due invecchierebbero a ritmi diversi. Quel che resta di
    pertinenza di questa funzione e' lo spareggio a pari invasione, che la
    decisione non ribalta e che questa funzione fornisce: `ordine` mette per
    prime le sezioni di area maggiore -- a pari area la lunghezza, a pari
    lunghezza l'indice, che e' l'ultima carta e serve solo a non lasciare la
    scelta all'ordinamento. I due casi di invasione doppia (attraversamento e
    contenimento) sono gia' fermati dalle guardie sotto, e quello di invasione
    nulla lascia ancora scattare la sola guardia d'angolo del Ruling Y.

    **Soffitto dichiarato:** il taglio e' un accorciamento lungo l'asse, quindi
    vale quando l'intersezione tocca un'estremita' del prisma minore -- il caso
    di un telaio, dove le membrature si incontrano alle estremita'. Gli altri
    due casi sollevano invece di produrre un risultato in silenzio: un prisma
    che attraversa l'altro da parte a parte (estremita' entrambe libere,
    invasione al centro) e un prisma interamente contenuto in un altro
    (estremita' entrambe invase). La via d'aggiornamento e' una vera operazione
    booleana fra solidi: `gmsh.model.occ.cut/fuse/intersect` la offrono gia' --
    gmsh e' dipendenza vera da questo ramo (pyproject.toml). Non manca la
    libreria: manca la frammentazione dei volumi che quell'operazione
    richiederebbe, e che rischia di perdere gli esaedri e ripiegare sul
    tetraedrico -- un compromesso che il documento della fase valuta e scarta
    (docs/fase-4-prior-telaio.md).
    """
    ordine = sorted(
        range(len(prismi)),
        key=lambda indice: (
            -abs(_area_poligono(prismi[indice].contorno)),
            -prismi[indice].lunghezza,
            indice,
        ),
    )
    tagliati = list(prismi)
    giunzioni: list[dict[str, object]] = []

    for posizione, maggiore in enumerate(ordine):
        for candidato in ordine[posizione + 1 :]:
            # Ruling AD: cede chi ha l'asse baricentrico invaso nell'altro, non
            # chi ha sezione minore -- vedi `wall.ruoli_dell_incontro`, dove la
            # decisione ora vive. Un solo verso invaso e'
            # il caso normale e decide da solo; entrambi o nessuno invaso
            # ricadono sullo spareggio per area gia' incorporato in `ordine`
            # (`maggiore`/`candidato` sono gia' ordinati per area decrescente).
            invaso_candidato = _asse_baricentrico_invaso(tagliati[candidato], tagliati[maggiore])
            invaso_maggiore = _asse_baricentrico_invaso(tagliati[maggiore], tagliati[candidato])
            minore, maggiore_effettivo, invaso = ruoli_dell_incontro(
                invaso_candidato, invaso_maggiore, candidato, maggiore
            )

            piccolo = tagliati[minore]
            versore = piccolo.asse / np.linalg.norm(piccolo.asse)
            passo = np.linspace(0.0, piccolo.lunghezza, _CAMPIONI_ASSE)
            centro_sezione = piccolo.contorno.mean(axis=0)
            e1, e2 = _base_del_piano(versore)
            base = piccolo.origine + centro_sezione[0] * e1 + centro_sezione[1] * e2
            # `invaso` e' gia' il campionamento della baricentrica di `piccolo`
            # dentro `maggiore_effettivo`, calcolato sopra per decidere i ruoli:
            # nessun bisogno di ricampionare.
            if not invaso.any():
                # La retta baricentrica puo' mancare il maggiore anche quando
                # i due prismi si compenetrano davvero: un angolo del
                # contorno minore puo' entrare senza che il suo baricentro lo
                # faccia. Le quattro rette dei vertici sono la guardia
                # additiva -- non cambiano l'esito quando la baricentrica gia'
                # vede l'invasione, la trovano solo quando lei sola non basta.
                # Il taglio assiale non sa togliere una sovrapposizione
                # d'angolo, quindi qui si solleva invece di ignorarla.
                vertice_invaso = any(
                    dentro(
                        tagliati[maggiore_effettivo],
                        (piccolo.origine + vx * e1 + vy * e2) + np.outer(passo, versore),
                    ).any()
                    for vx, vy in piccolo.contorno
                )
                if vertice_invaso:
                    raise ValueError(
                        "un vertice del contorno del prisma minore entra nel "
                        "prisma maggiore ma la retta baricentrica no: è una "
                        "sovrapposizione d'angolo che il taglio lungo l'asse "
                        "non sa togliere. Verifica la scomposizione"
                    )
                continue

            # I due casi che l'accorciamento lungo l'asse non sa fare, ciascuno
            # con la propria diagnosi. Sono guardie e non note: senza la guardia
            # dell'attraversamento, `libero[-1] + 1` esce dall'array dei campioni
            # (indice 200 su un array di 200) e il codice si schianta con un
            # IndexError che non dice all'operatore che la scomposizione e'
            # sbagliata -- non un accorciamento silenzioso, ma non e' comunque
            # una diagnosi utile.
            if invaso[0] and invaso[-1]:
                raise ValueError(
                    "un prisma è interamente dentro un altro: non c'è un "
                    "estremo da accorciare. Verifica la scomposizione: due "
                    "regioni sovrapposte non sono due membrature"
                )
            if not invaso[0] and not invaso[-1]:
                raise ValueError(
                    "un prisma attraversa un altro da parte a parte: il taglio "
                    "alle giunzioni accorcia lungo l'asse e non sa dividere un "
                    "prisma in due. Verifica la scomposizione: due membrature "
                    "che si attraversano sono quasi sempre una regione fusa"
                )

            libero = np.flatnonzero(~invaso)
            if invaso[0]:
                # invasa l'estremita' iniziale: il bordo sta fra il primo
                # campione libero e quello invaso che lo precede
                fine = _bordo_del_solido(
                    tagliati[maggiore_effettivo], base, versore,
                    passo[libero[0]], passo[libero[0] - 1],
                )
                nuova_origine = piccolo.origine + versore * fine
                nuova_lunghezza = piccolo.lunghezza - fine
            else:
                fine = _bordo_del_solido(
                    tagliati[maggiore_effettivo], base, versore,
                    passo[libero[-1]], passo[libero[-1] + 1],
                )
                nuova_origine = piccolo.origine
                nuova_lunghezza = fine

            # Ruling AE: il cuneo fra la faccia di taglio (piana, alla quota
            # `fine` sulla baricentrica) e il vero bordo di `maggiore_effettivo`,
            # misurato su ogni vertice del contorno di chi cede sulla stessa
            # quota -- vedi `_cuneo_vertice`. Zero su un banco squadrato.
            #
            # Il limite di ricerca e' quattro volte il passo con cui
            # `_CAMPIONI_ASSE` campiona l'asse di chi cede: quel passo e'
            # gia' dichiarato altrove come la scala sotto cui sta qualunque
            # giunzione, e un cuneo che nasce da un fuori squadra di pochi
            # gradi e' un effetto locale, non un salto a un'altra invasione
            # lontana e indipendente. Il fattore quattro e' un margine di
            # sicurezza sopra quella scala, non una misura.
            limite_ricerca = 4.0 * piccolo.lunghezza / (_CAMPIONI_ASSE - 1)
            cuneo = max(
                (
                    _cuneo_vertice(
                        piccolo.origine + fine * versore + vx * e1 + vy * e2,
                        versore,
                        tagliati[maggiore_effettivo],
                        limite_ricerca,
                    )
                    for vx, vy in piccolo.contorno
                ),
                default=0.0,
            )

            # Ruling AH: la POSITION TOLERANCE della card *TIE non e' una
            # costante di modulo, e' lo scostamento da squadra sulla zona di
            # contatto -- l'estensione del contorno di chi cede (la stessa
            # scala usata sopra per il cuneo) per il seno dell'angolo fuori
            # squadra fra i due assi. Il seno dell'angolo fra due versori che
            # sarebbero perpendicolari se in squadra e' esattamente il modulo
            # del loro prodotto scalare: nessuna approssimazione di piccolo
            # angolo, nessun arcoseno da invertire.
            versore_maggiore_eff = tagliati[maggiore_effettivo].asse
            versore_maggiore_eff = versore_maggiore_eff / np.linalg.norm(versore_maggiore_eff)
            seno_fuori_squadra = abs(float(np.dot(versore, versore_maggiore_eff)))
            posizione_tolleranza = float(np.ptp(piccolo.contorno, axis=0).max()) * seno_fuori_squadra

            giunzioni.append({
                "maggiore": int(maggiore_effettivo),
                "minore": int(minore),
                "accorciamento": float(piccolo.lunghezza - nuova_lunghezza),
                "cuneo": float(cuneo),
                "posizione_tolleranza": posizione_tolleranza,
            })
            tagliati[minore] = Prisma(
                contorno=piccolo.contorno,
                origine=nuova_origine,
                asse=piccolo.asse,
                lunghezza=float(nuova_lunghezza),
            )

    return tagliati, giunzioni


class MembratureNonLegateWarning(UserWarning):
    """Una o piu' membrature non compaiono in alcun `*TIE`.

    Non e' un errore: un modello con parti scollegate e' legittimo. Ma senza
    questo avviso lo stato non arriva all'operatore, e un gioco fra due
    geometrie sotto la risoluzione dello scanner produce lo stesso `ties=()`
    di una scelta deliberata di modellazione -- le due situazioni vanno
    distinte da chi guarda il risultato, non nascoste dietro lo stesso zero.
    """


class GiunzioneSenzaTieWarning(UserWarning):
    """Una giunzione tagliata non produce alcun `*TIE`.

    Non e' un errore: il taglio ha comunque tolto la doppia contabilita' del
    volume, che e' il suo solo compito. Ma senza questo avviso l'unico segnale
    e' la differenza fra `giunzioni` e `ties` in `metriche`, un confronto fra
    due numeri che nessuno guarda finche' non sa di doverlo fare.
    """


def costruisci(membrature: list, tipo: str, cfg: ModelConfig) -> dict[str, object]:
    """Il telaio intero: prismi tagliati, mesh di ciascuno, superfici e vincoli.

    Le mesh di membrature adiacenti non combaciano nodo a nodo -- ciascuna ha
    il passo della propria sezione, e due sezioni diverse danno due passi
    diversi -- quindi il legame e' un `*TIE` fra le superfici a contatto e non
    una fusione di nodi. **La mesh conforme multiblocco resta
    la via d'aggiornamento**, e non e' un dettaglio d'attuazione: e' una
    differenza fra i modelli che non deriva dalla geometria, ed e' per questo
    che il report la dichiara accanto al confronto. Senza quella riga, una
    differenza di rigidezza nata dal `*TIE` verrebbe letta come effetto della
    forma.
    """
    if not membrature:
        raise ValueError(
            "nessuna membratura da costruire: il prior non ne ha accettata alcuna. "
            "Guarda le regioni scartate e il controllo che le ha respinte, invece "
            "di generare un modello vuoto"
        )

    # la guardia del Ruling J: wall.py misura e non scarta, quindi il rifiuto
    # di una regione non prismatica arriva qui. Riempimento «vuoto» vuol dire
    # che l'ingombro non e' la sezione ma il suo contenitore -- tipicamente due
    # membrature unite a Π che la scomposizione non ha separato -- e un modello
    # costruito su quella sezione sarebbe inventato. Lo stato «non_verificabile»
    # non e' motivo di rifiuto: dice che la misura non vale, non che il pezzo e'
    # cavo. Lo stato basta da solo: `wall.misura` mette «vuoto» solo su una
    # misura affidabile e degrada a «non_verificabile» appena non lo e'.
    # Nessuna soglia da rileggere qui, e ModelConfig non ne ha una.
    vuote = [
        numero
        for numero, membratura in enumerate(membrature)
        if membratura.riempimento_stato == "vuoto"
    ]
    if vuote:
        raise ValueError(
            f"le membrature {vuote} hanno riempimento di sezione «vuoto» con "
            "misura affidabile: la loro sezione è un ingombro e non una "
            "sezione, e su di essa non si costruisce. Guarda la scomposizione: "
            "sono quasi sempre due membrature adiacenti fuse in una regione a Π"
        )

    prismi = [prisma_di(membratura, tipo) for membratura in membrature]
    tagliati, giunzioni = taglia_giunzioni(prismi)

    nodi_totali: list[np.ndarray] = []
    elementi_totali: list[np.ndarray] = []
    blocchi: list[dict[str, object]] = []
    scorrimento = 0
    primo_elemento = 0
    for numero, prisma in enumerate(tagliati):
        nodi, esaedri, metriche = mesh_prisma(
            prisma.contorno, prisma.origine, prisma.asse, prisma.lunghezza, cfg
        )
        nodi_totali.append(nodi)
        elementi_totali.append(esaedri + scorrimento)
        blocchi.append({
            "membratura": numero,
            "primo_nodo": scorrimento,
            "nodi": int(len(nodi)),
            "primo_elemento": primo_elemento,
            "elementi": int(len(esaedri)),
            **metriche,
        })
        scorrimento += len(nodi)
        primo_elemento += len(esaedri)

    nodi = np.ascontiguousarray(np.vstack(nodi_totali))
    elementi = np.ascontiguousarray(np.vstack(elementi_totali))

    # Le superfici a contatto: per ogni giunzione, le facce di bordo del
    # prisma minore il cui **baricentro** cade dentro il maggiore, e
    # viceversa (Ruling AF, giro di correzione 5: vedi `abaqus.tie_surface`
    # per la ragione fisica del criterio, diverso apposta da
    # `element_surface`). La tolleranza resta
    # `max(_TOLLERANZA_CONTATTO, giunzione["cuneo"])` (Ruling AE) e non il
    # passo di mesh: un margine grande quanto il passo di mesh legherebbe
    # anche superfici che non si toccano, e il controllo passerebbe senza che
    # il modello sia giusto.
    #
    # Il criterio per baricentro e' stato scelto al posto dell'altra leva
    # aperta -- infittire la mesh alle giunzioni -- per una decisione
    # dell'utente, non per semplicita' di codice: infittire proprio dove le
    # sollecitazioni sono massime introdurrebbe una variazione di densita' di
    # mesh in quella stessa zona, e una mesh disomogenea li' rende meno
    # leggibile il confronto fra i tre modelli (as-built, estruso,
    # primitive), che e' l'obiettivo del prior. Meglio una mesh omogenea
    # ovunque, anche a costo di una superficie di contatto un poco piu'
    # larga di quella nodo-per-nodo.
    #
    # Il dipendente e' il prisma che ha ceduto in `taglia_giunzioni` (Ruling
    # AD: chi ha l'asse baricentrico invaso nell'altro), non "la superficie
    # piu' fitta fa da dipendente": quando l'asse non basta a decidere
    # (entrambi o nessuno invaso) il ruolo ricade sull'area, che resta una
    # scelta di determinismo e non di convergenza numerica -- l'ordine per
    # area e quello per passo di mesh non coincidono, una sezione 1000 x 10 ha
    # area maggiore di una 90 x 90 (10000 contro 8100) e passo nove volte piu'
    # fine (3,333 contro 30,0). Verificato che su questa assegnazione CalculiX
    # genera i vincoli senza un solo nodo fallito; la via d'aggiornamento, se
    # una geometria reale mostrasse il contrario, e' ordinare i due ruoli per
    # `blocco["passo"]`.
    #
    # Non tutte le giunzioni tagliate diventano necessariamente un `*TIE`, e
    # non sarebbe un difetto del taglio se succedesse: il taglio toglie
    # sempre la doppia contabilita' del volume, che e' il suo solo compito.
    # Un lato puo' restare senza facce di bordo il cui baricentro cade
    # nell'altro solido se il cuneo (Ruling AE) non copre lo scarto fra il
    # piano di taglio e la superficie -- in generale inclinata -- di chi
    # riceve. La mesh conforme multiblocco resta la via d'aggiornamento che
    # toglierebbe il problema alla radice, condividendo i nodi sul contatto
    # invece di verificarne la posizione a posteriori.
    superfici: dict[str, list[tuple[int, int]]] = {}
    ties: list[tuple[str, str, str] | tuple[str, str, str, float]] = []
    connesse: set[int] = set()
    giunzioni_senza_tie: list[int] = []
    nodi_dipendenti_legati = 0
    nodi_dipendenti_totali = 0
    for numero, giunzione in enumerate(giunzioni, start=1):
        minore, maggiore = int(giunzione["minore"]), int(giunzione["maggiore"])
        tolleranza = max(_TOLLERANZA_CONTATTO, float(giunzione["cuneo"]))
        nomi = []
        nodi_faccia_per_ruolo: dict[str, set[int]] = {}
        # Dichiarata qui e non nel ramo "I" sotto: il ciclo esterno sulle
        # giunzioni non azzera le variabili locali fra un'iterazione e
        # l'altra, quindi se un giorno il ruolo "I" saltasse per una
        # giunzione, `facce_i` misurerebbe ancora contro le facce della
        # giunzione precedente invece di sollevare un NameError (F6).
        facce_i: list[np.ndarray] = []
        for ruolo, indice, altro, tocca in (
            # Ruling AH: il dipendente resta per solo baricentro (gia' giusto
            # sulla faccia di taglio piana); l'indipendente prende anche
            # "tocca" -- baricentro o almeno un nodo dentro -- perche' la sua
            # mesh e' piu' rada (la sezione dell'altra membratura) e una
            # faccia grande puo' coprire solo in parte la zona di contatto.
            ("D", minore, maggiore, False),
            ("I", maggiore, minore, True),
        ):
            blocco = blocchi[indice]
            el_inizio = blocco["primo_elemento"]
            el_fine = el_inizio + blocco["elementi"]
            grezze = abaqus.tie_surface(
                nodi, elementi[el_inizio:el_fine],
                lambda punti: dentro(tagliati[altro], punti, tolleranza),
                cfg.element,
                tocca=tocca,
            )
            nome = f"{cfg.tie_name_prefix}_{numero}_{ruolo}"
            superfici[nome] = [(elemento + el_inizio, faccia) for elemento, faccia in grezze]
            nomi.append(nome)
            nodi_faccia_per_ruolo[ruolo] = {
                int(n)
                for elemento_locale, faccia in grezze
                for n in elementi[el_inizio + elemento_locale][
                    list(abaqus.FACCE_DEL_SOLUTORE[8][faccia - 1])
                ]
            }
            if ruolo == "D":
                # Il totale e' il conteggio della superficie dipendente
                # candidata (i nodi delle sue facce di bordo, Ruling AF/AH),
                # non del blocco intero: la membratura ha centinaia di nodi
                # lungo tutta la sua lunghezza, la giunzione solo alla quota
                # del taglio -- il denominatore giusto e' quest'ultima scala.
                nodi_dipendenti_totali += len(nodi_faccia_per_ruolo[ruolo])
            else:
                # I quadrilateri delle facce indipendenti, non solo i loro
                # nodi d'angolo: CalculiX proietta un nodo dipendente sul
                # punto piu' vicino della faccia opposta intera, che su una
                # faccia grande (mesh rada, questo lato) puo' cadere lontano
                # da ogni angolo -- vedi `_distanza_punto_faccia`.
                facce_i = [
                    nodi[elementi[el_inizio + elemento_locale][
                        list(abaqus.FACCE_DEL_SOLUTORE[8][faccia - 1])
                    ]]
                    for elemento_locale, faccia in grezze
                ]
        if superfici[nomi[0]] and superfici[nomi[1]]:
            # Nodi legati su nodi dipendenti: conteggio interno (non una
            # lettura del solutore), quanti nodi della superficie dipendente
            # hanno un punto della superficie indipendente -- non solo un suo
            # nodo, la faccia intera, vedi `_distanza_punto_faccia` -- entro
            # la stessa tolleranza di posizione data a CalculiX. E' il numero
            # che rende leggibile, nel confronto fra i tre modelli, quanta
            # della cedevolezza del parametrico viene dal vincolo e non dalla
            # geometria (serve anche al Task 12). Non e' "quanti nodi stanno
            # nella superficie dipendente": quello e' il totale, sempre vero
            # per costruzione, e non direbbe nulla su quanti legano davvero.
            tolleranza_posizione = float(giunzione["posizione_tolleranza"])
            soglia_legame = max(_TOLLERANZA_CONTATTO, tolleranza_posizione)
            posizioni_d = nodi[sorted(nodi_faccia_per_ruolo["D"])]
            for punto_d in posizioni_d:
                distanza_minima = min(
                    _distanza_punto_faccia(punto_d, faccia_i) for faccia_i in facce_i
                )
                if distanza_minima <= soglia_legame:
                    nodi_dipendenti_legati += 1

            nome_tie = f"{cfg.tie_name_prefix}_{numero}"
            # Zero (banco squadrato) non scrive il parametro affatto, non lo
            # scrive a zero: POSITION TOLERANCE=0.0 non e' la stessa cosa di
            # nessuna POSITION TOLERANCE per CalculiX, che senza il parametro
            # usa una stima propria -- passare zero esplicito rischia di
            # essere piu' severo del suo predefinito, non neutro.
            if tolleranza_posizione > 0.0:
                ties.append((nome_tie, nomi[0], nomi[1], tolleranza_posizione))
            else:
                ties.append((nome_tie, nomi[0], nomi[1]))
            connesse.add(minore)
            connesse.add(maggiore)
        else:
            # superficie vuota: le due mesh non si toccano davvero. Meglio
            # nessun vincolo che un *TIE su una superficie senza facce, che il
            # solutore accetterebbe e non vincolerebbe nulla.
            for nome in nomi:
                superfici.pop(nome, None)
            giunzioni_senza_tie.append(numero)

    if giunzioni_senza_tie:
        warnings.warn(
            f"{len(giunzioni_senza_tie)} giunzioni tagliate su {len(giunzioni)} "
            f"non producono un *TIE*: numeri {giunzioni_senza_tie}. Il taglio ha "
            "tolto comunque la doppia contabilità del volume; verifica se è un "
            "limite della rilevazione delle superfici o della geometria",
            GiunzioneSenzaTieWarning,
            stacklevel=2,
        )

    # Ruling Z: un telaio con membrature scollegate e' un modello legittimo
    # -- non e' compito di questa funzione deciderlo -- ma l'operatore deve
    # saperlo invece di dedurlo contando `ties`. Un gioco sotto la
    # risoluzione dello scanner e la scelta di modellare due parti separate
    # producono lo stesso stato interno, e solo l'avviso le distingue da un
    # errore silenzioso.
    non_legate = [numero for numero in range(len(tagliati)) if numero not in connesse]
    # Una membratura sola non ha niente a cui legarsi: l'avviso direbbe il vero
    # senza dire nulla, e un avviso che si ripete su un caso normale insegna a
    # ignorarlo proprio quando conta.
    if non_legate and len(tagliati) > 1:
        warnings.warn(
            f"membrature non legate da alcun *TIE*: {len(non_legate)} su "
            f"{len(tagliati)}, indici {non_legate}. Se non è la scelta di "
            "modellarle come corpi separati, verifica il gioco fra le geometrie",
            MembratureNonLegateWarning,
            stacklevel=2,
        )

    return {
        "nodi": nodi,
        "elementi": elementi,
        "blocchi": blocchi,
        "superfici": superfici,
        "ties": tuple(ties),
        "metriche": {
            "tipo": tipo,
            "membrature": len(tagliati),
            "giunzioni": len(giunzioni),
            "ties": len(ties),
            "membrature_non_legate": len(non_legate),
            "accorciamenti": [giunzione["accorciamento"] for giunzione in giunzioni],
            "element_type": cfg.element,
            "nodi_dipendenti_legati": nodi_dipendenti_legati,
            "nodi_dipendenti_totali": nodi_dipendenti_totali,
        },
    }
