"""Server locale: pilota il core, non lo reimplementa.

Ogni numero che serve viene da metrics.json o dalle funzioni di core; ogni
parametro che scrive passa dai modelli di config.py.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
import subprocess
import sys
import traceback
import threading
import time
import zipfile
from collections import Counter
from contextlib import asynccontextmanager
from functools import lru_cache
from pathlib import Path
from typing import Annotated, Literal, get_args, get_origin

import numpy as np
from fastapi import FastAPI, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from pydantic import (
    AfterValidator,
    BaseModel,
    BeforeValidator,
    ConfigDict,
    Field,
    ValidationError,
)

from meshrec.app import identita, immagini, storico
from meshrec.app.worker import Worker
from meshrec.core import (
    io,
    pipeline,
    quality,
    segment,
    steps,
    sweep,
    viewport,
)
from meshrec.core.config import (
    InputConfig,
    PipelineConfig,
    RunConfig,
    SegmentConfig,
    ViewportConfig,
    carica_yaml_da_testo,
    load_config,
    save_config,
)
from meshrec.core.io import scrivi_atomico

UI_DIR = Path(__file__).resolve().parent.parent / "ui"

# Mai dentro una cartella di corsa: runs/muro, runs/lab_crop, runs/sweep,
# experiments/muro ed experiments/lab_crop sono di sola lettura e contengono
# la tabella sperimentale della tesi. Percorso relativo come run.out_dir:
# risolto rispetto alla cartella da cui gira il server (meshrec/).
CACHE_DIR = Path(".cache/viewport")

# Incrementala quando cambia il modo in cui il contorno viene calcolato: il
# verso delle facce (quality._TET_FACES) o la regola di compattazione dei
# vertici (np.unique(..., return_inverse) in _contorno_del_volume). La chiave
# (sorgente, mtime) e' completa come parametri ma non registra il codice che ha
# prodotto la voce: senza incremento, ogni voce gia' su disco continuerebbe a
# rispondere col risultato vecchio per tutta la vita del file sorgente, che e'
# «restituisce in silenzio il risultato di qualcun altro». Entra nel nome, non
# nel contenuto, perche' _rimuovi_voci_vecchie sfratta per marchio e non guarda
# che cosa segue: cambiare la versione basta a far ripulire le voci precedenti.
VERSIONE_CONTORNO = 2


def _percorso_contorno(sorgente: Path) -> Path:
    """Voce di cache del contorno di un volume, con chiave (sorgente, versione, mtime).

    Duplica in piccolo viewport._cache_path, che non e' riusabile qui: la sua
    chiave porta budget, spacing_sample e seed, che l'estrazione del contorno
    non ha (dipende solo dal file), e il suo formato salva punti e gruppi di
    lunghezza variabile, non vertici e facce.

    Sottocartella propria, e non la stessa di viewport: _rimuovi_voci_vecchie
    cancella ogni altra voce che porta il marchio della sorgente, e il marchio
    e' l'hash del solo percorso. Nella stessa cartella la nuvola e il contorno
    di uno stesso file si sfratterebbero a vicenda ad ogni scrittura, e il
    ritorno del ricalcolo da dodici secondi non avrebbe alcun segnale. Oggi non
    accade perche' read_cloud rifiuta un .vtu, cioe' per una ragione che sta in
    un altro modulo: separare le cartelle non dipende da quella ragione.
    """
    sorgente = Path(sorgente)
    marchio = hashlib.sha256(str(sorgente.resolve()).encode("utf-8")).hexdigest()[:16]
    return (
        Path(CACHE_DIR)
        / "contorno"
        / f"{marchio}-{VERSIONE_CONTORNO}-{sorgente.stat().st_mtime_ns}.npz"
    )


def _leggi_contorno(voce: Path) -> tuple[np.ndarray, np.ndarray, np.ndarray] | None:
    """Una voce assente o corrotta non e' un errore: si ricalcola, come _leggi_cache."""
    if not voce.exists():
        return None
    try:
        with np.load(voce, allow_pickle=False) as dati:
            vertici, facce, indici = dati["vertici"], dati["facce"], dati["indici"]
        if len(facce) and facce.max() >= len(vertici):
            # Come _leggi_cache col suo offsets: un indice fuori misura non
            # solleva mai in numpy, quindi va negato qui. Senza, la voce arriva
            # al browser con un 200 e three.js disegna fuori dall'attributo
            # position, senza un errore e senza un messaggio. Zero facce e' una
            # voce valida e max() su un array vuoto solleverebbe: il len() a
            # sinistra la lascia passare.
            raise ValueError("facce incoerenti con i vertici")
        if len(indici) != len(vertici):
            # L'argomento di sopra vale di piu' per indici, non di meno: e'
            # l'unico dei tre che indicizza un array diverso
            # (griglia.point_data, non vertici), e /api/campo lo usa per
            # ritagliare il campo sui nodi del contorno. Lungo o corto con
            # valori tutti in dominio, numpy non solleva: il campo esce di una
            # lunghezza che non e' quella dei vertici, e il colore si posa
            # sfalsato di un nodo senza che nessuno lo dica. Il client se ne
            # accorge solo quando le due lunghezze differiscono; se il ritaglio
            # sfalsato ne restituisse una giusta, non se ne accorgerebbe
            # nessuno.
            raise ValueError("indici incoerenti con i vertici")
    except (OSError, ValueError, KeyError, EOFError, zipfile.BadZipFile):
        return None
    return vertici, facce, indici


def _scrivi_contorno(voce: Path, vertici: np.ndarray, facce: np.ndarray, indici: np.ndarray) -> bool:
    """Vero se la voce e' finita su disco. Il chiamante ci lega la pulizia (MI-2)."""

    def scrittore(destinazione: Path) -> None:
        np.savez(str(destinazione), vertici=vertici, facce=facce, indici=indici)

    try:
        scrivi_atomico(voce, scrittore)
    except OSError:
        # Come in viewport._scrivi_cache: due richieste sovrapposte condividono
        # il nome del temporaneo. Una cache che non riesce a scriversi costa un
        # ricalcolo alla prossima chiamata, mai una richiesta fallita.
        return False
    return True


def _contorno_del_volume(
    percorso: Path, griglia=None
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Vertici, triangoli e indici dei nodi originali del contorno di una mesh
    di volume, con cache su disco.

    `griglia`: la stessa mesh gia' letta dal chiamante, quando ce l'ha. A cache
    fredda il .vtu si leggeva due volte per richiesta — una in `campo()` per i
    campi di soluzione, una qui per il contorno — su un file da 8,58 MB
    (13_solution.vtu di runs/lab_telaio_v2, misurato il 22/08/2026) e con un
    picco che su lab_crop il commento a VERSIONE_CONTORNO dichiara oltre il
    gigabyte. Due letture intere sul primo clic del pannello Campo, che e'
    quello della dimostrazione. Il ramo a cache calda non tocca la griglia e
    non la legge affatto: passarla non costa niente a chi ce l'ha gia' e non
    obbliga chi non ce l'ha.

    Su lab_crop l'estrazione costa circa 15 s e oltre un gigabyte di picco, e
    senza cache ogni clic sullo step 9 la rifa' identica. La chiave e' la sola
    coppia (sorgente, mtime) perche' l'estrazione non ha altri ingressi: non
    legge la configurazione e non ha parametri.

    Il terzo elemento (indici) e' cio' che serve alla Fase 5 per portare un
    campo per nodo (spostamenti, tensioni) fino ai vertici del contorno senza
    ricalcolarlo altrove: `vertici[i]` e' sempre `griglia.points[indici[i]]`,
    quindi un campo scritto su `griglia.points` si legge con `campo[indici]`.
    """
    import meshio

    voce = _percorso_contorno(percorso)
    trovato = _leggi_contorno(voce)
    if trovato is not None:
        return trovato

    if griglia is None:
        griglia = meshio.read(percorso)
    # Il blocco si prende per unicita' e non per nome, come in
    # pipeline._maglio_di_volume: `abaqus.write_vtu` ne scrive uno solo, e i
    # nomi sono due -- `tetra` per C3D4, `tetra10` per C3D10, che e' il
    # predefinito di TetConfig.element. Cercando `tetra` la vista del volume
    # non si e' mai aperta sull'elemento predefinito, e nemmeno quella dei
    # campi di soluzione, su file perfettamente validi.
    tipi = sorted(griglia.cells_dict)
    if len(tipi) != 1:
        raise ValueError(
            f"{percorso.name} porta {len(tipi)} blocchi di celle ({tipi}) invece del solo "
            "maglio di volume che lo step 9 scrive"
        )
    tetraedri = np.asarray(griglia.cells_dict[tipi[0]])
    # Le stesse quattro colonne che abaqus.boundary_faces prende, e per la
    # stessa ragione scritta li': la topologia sta nei vertici, i sei nodi di
    # lato di un C3D10 stanno a meta' degli spigoli e non definiscono ne'
    # facce ne' adiacenze. In VTK come in Abaqus i vertici sono i primi
    # quattro, ed e' la convenzione che volume.TETGEN_A_ABAQUS garantisce.
    if tetraedri.shape[1] == 10:
        tetraedri = tetraedri[:, :4]
    if tetraedri.shape[1] != 4:
        raise ValueError(
            f"{percorso.name} non contiene tetraedri: le celle sono {tipi}"
        )
    # quality._TET_FACES: la stessa convenzione, non una copia. E' privata, ma
    # da lei dipende il verso uscente delle facce e due copie di una
    # convenzione che decide un segno prima o poi divergono.
    facce_tutte = np.vstack([tetraedri[:, list(schema)] for schema in quality._TET_FACES])
    # L'ordinamento serve solo a confrontare le facce e perde il verso.
    # return_index riporta la faccia originale, quindi l'orientamento
    # uscente degli schemi qui sopra sopravvive al conteggio.
    _ordinate, primo, conteggi = np.unique(
        np.sort(facce_tutte, axis=1), axis=0, return_index=True, return_counts=True
    )
    # Una faccia che appartiene a un solo tetraedro sta sul contorno: e' la
    # stessa definizione che quality.boundary_edges applica agli spigoli di
    # una superficie.
    contorno = facce_tutte[primo[conteggi == 1]]
    # Solo i nodi che il contorno tocca: griglia.points porta anche quelli
    # interni, che nessun triangolo disegna, e X-Vertices direbbe un numero
    # che nessuna lettura sostiene.
    usati, rimappate = np.unique(contorno, return_inverse=True)
    # I tipi del trasporto gia' qui, non solo nella risposta: cosi' la cache
    # calda e quella fredda restituiscono gli stessi byte invece di far
    # dipendere la precisione da quale delle due strade ha risposto.
    vertici = np.ascontiguousarray(griglia.points[usati], dtype="<f4")
    facce = np.ascontiguousarray(rimappate.reshape(contorno.shape), dtype="<u4")
    indici = np.ascontiguousarray(usati, dtype="<u4")
    # MI-2: la pulizia solo se la scrittura e' riuscita. Sfrattare la voce
    # vecchia quando la nuova non esiste lascia la cache vuota e costa un
    # ricalcolo da quindici secondi, mai un dato sbagliato. viewport ha lo
    # stesso schema e non e' modificabile da qui: i due divergono apposta.
    if _scrivi_contorno(voce, vertici, facce, indici):
        viewport._rimuovi_voci_vecchie(voce.parent, voce)
    return vertici, facce, indici


def _non_booleano(valore: object) -> object:
    """True e False non sono coordinate, ma pydantic li accetta come float.

    `bool` e' sottotipo di `int` per Python, quindi `{"min": [true, false, true]}`
    passava il confine e finiva in configurazione come `(1.0, 0.0, 1.0)`: un tipo
    sbagliato scritto sul disco, che e' esattamente cio' che B-1 vietava. Il
    controllo sta prima della conversione, perche' dopo il booleano non esiste
    piu'. I numeri scritti come stringhe restano accettati apposta: `"1.0"` e' un
    numero espresso male, `true` non e' un numero.
    """
    if isinstance(valore, bool):
        raise ValueError("un booleano non è una coordinata: attesa una misura in mm")
    return valore


Coordinata = Annotated[float, BeforeValidator(_non_booleano)]


class BoxRitaglio(BaseModel):
    """Il corpo di POST /api/crop, verificato prima di toccare la configurazione.

    Tipizzato invece di dict[str, list[float]] apposta: cosi' e' FastAPI a
    rifiutare arita' sbagliata, chiave mancante e valore non numerico, con un
    messaggio che dice quale campo e perche', e la tratta non arriva mai ad
    assegnare. Senza, l'assegnazione finiva su SegmentConfig, che non ha
    validate_assignment e quindi non verifica nulla; numpy trasmetteva
    (N,3) >= (1,) senza lamentarsi; save_config usa model_dump, che non valida,
    e scriveva su disco una tupla di uno in un campo dichiarato di tre. Da li'
    in poi load_config rifiutava la corsa e l'interfaccia restava morta.

    NaN e Infinity restano fuori di qui e li guarda `_estremi_finiti`: json
    non li ammette in uscita, e il corpo del 422 di FastAPI riporta il valore
    ricevuto. Rifiutarli con `allow_inf_nan=False` farebbe quindi fallire la
    codifica della risposta, e a video arriverebbe «Out of range float values
    are not JSON compliant» invece del nome del campo — misurato, non dedotto.
    """

    model_config = ConfigDict(extra="forbid")

    min: tuple[Coordinata, Coordinata, Coordinata]
    max: tuple[Coordinata, Coordinata, Coordinata]


def _estremi_finiti(box: BoxRitaglio) -> None:
    """NaN e Infinity fuori dal box: sono float per pydantic e non coordinate.

    json.loads li legge, quindi arrivano davvero. Il messaggio dice quale
    estremo e quale asse, come le altre tratte del modulo: «KeyError: 'max'»
    era la forma da cui non si capiva dove guardare.
    """
    for nome, estremo in (("min", box.min), ("max", box.max)):
        for asse, coordinata in zip("xyz", estremo):
            if not math.isfinite(coordinata):
                raise ValueError(
                    f"la coordinata {asse} di '{nome}' vale {coordinata} e non un numero finito: "
                    "il box va dato in coordinate della nuvola, nelle unità di lavoro (mm)"
                )


@lru_cache(maxsize=1)
def _ingresso_del_ritaglio(sorgente: Path, _mtime_ns: int, vicini: int, scarto: float) -> np.ndarray:
    """La nuvola come lo step 2 la vede un istante prima di ritagliarla.

    Riproduce la tratta, non la funzione: `segment.segment_cloud` legge
    l'artefatto dello step 1 e fa remove_outliers e poi crop_box, in
    quest'ordine. Un'anteprima che ritagliasse 02_segmented.ply
    lavorerebbe su un file gia' ripulito e gia' ritagliato, e allargando il box
    non potrebbe far tornare indietro nessun punto; una che ritagliasse
    01_cloud.ply e basta sovrastimerebbe, perche' terrebbe gli outlier che lo
    step toglie prima. Il ritaglio resta di segment.crop_box: qui non ce n'e'
    una seconda copia da tenere allineata.

    Misurato su runs/lab_crop, 6 329 096 punti: 0,70 s di lettura piu' 25,86 s
    di remove_outliers. Senza memoria ogni ritocco del box li ripagherebbe
    interi, e il pannello del ritaglio si usa proprio ritoccando.

    _mtime_ns sta nella chiave e non nel corpo: e' quello che fa scadere la
    voce quando lo step 1 riscrive l'artefatto.

    Il tetto: una voce sola, in memoria, viva quanto il processo — circa 146 MB
    per la nuvola di lab_crop. Due corse usate a turno se la scambiano e
    ripagano i 26 s ogni volta; alzare maxsize costa un'altra nuvola intera.
    L'array torna condiviso fra i chiamanti: crop_box lo legge e copia i punti
    scelti, non lo modifica.
    """
    punti, _normali = io.read_cloud(sorgente)
    puliti, _metriche = segment.remove_outliers(
        punti, SegmentConfig(outlier_neighbors=vicini, outlier_std_ratio=scarto)
    )
    return puliti


# Quale superficie e quale nuvola, per lo scarto per vertice dello step 7.
#
# Non scelti qui: sono la coppia che `pipeline.run` misura a quello step. La
# superficie e' quella riparata dello step 6 -- `pipeline._RESUME_MESH[7]` vale
# 6, e lo step 7 non scrive un artefatto proprio -- e la nuvola e' quella
# segmentata dello step 2, che `run()` carica in `source_cloud` e passa a
# `quality.geometric_error`. Una coppia diversa dipingerebbe un campo che
# nessuna metrica sostiene: il banco che tiene ferma la corrispondenza legge
# `_RESUME_MESH` invece di ricopiarne il numero.
_SCARTO_MESH = 6
_SCARTO_NUVOLA = 2


@lru_cache(maxsize=1)
def _scarto_dei_vertici(
    mesh: Path, _mesh_mtime_ns: int, nuvola: Path, _nuvola_mtime_ns: int
) -> np.ndarray:
    """La distanza di ogni vertice della superficie dalla nuvola segmentata.

    E' la stessa funzione che lo step 7 usa per il verso mesh_to_cloud del
    proprio `geometric_error`, sugli stessi due file: qui non c'e' una seconda
    misura da tenere allineata, c'e' la stessa misura prima che venga ridotta a
    quattro scalari.

    In memoria e non nel file di stato, ed e' una scelta di perimetro: la mappa
    non e' un artefatto della corsa. Scriverla vorrebbe dire allargare lo schema
    degli artefatti, l'invalidazione a valle e le impronte del registro per un
    campo che si guarda e non si cita. Le due mtime stanno nella chiave e la
    fanno scadere quando uno dei due file viene riscritto, come in
    `_ingresso_del_ritaglio`.

    Il costo e' l'albero: su lab_crop la nuvola segmentata ha 4.229.538 punti.
    Si paga una volta per coppia di file, contro i 34 s dello step che l'ha
    prodotta. In memoria resta il solo vettore degli scarti -- uno float per
    vertice -- perche' l'albero e' locale e muore col ritorno: la voce in cache
    e' piccola, e non e' ovvio guardando la firma.

    ponytail: nessun lucchetto. Due richieste identiche in volo insieme
    costruiscono due alberi, perche' `lru_cache` scrive la voce solo a conto
    finito. Dalla parte del browser il bottone si spegne mentre la misura gira,
    quindi il caso resta quello delle due schede aperte sulla stessa corsa --
    utente singolo, per dichiarazione di prodotto. Se dovesse capitare davvero:
    un `threading.Lock` attorno alla chiamata, come quello che `Worker` tiene
    per le righe del sottoprocesso.
    """
    import open3d as o3d

    triangolare = o3d.io.read_triangle_mesh(str(mesh))
    vertici = np.asarray(triangolare.vertices)
    # La nuvola vuota la rifiuta gia' `quality.vertex_deviation`, con la propria
    # ragione. Questa e' l'altra meta': una mesh senza vertici darebbe un campo
    # vuoto, cioe' un 200 con zero valori che il browser leggerebbe come «campo
    # e superficie non corrispondono» invece che come «non c'e' niente da
    # misurare».
    if len(vertici) == 0:
        raise ValueError(f"{mesh.name} non ha vertici da cui misurare lo scarto")
    punti, _normali = io.read_cloud(nuvola)
    return quality.vertex_deviation(vertici, punti)


# Il nome di una corsa diventa il nome di una cartella dentro `runs/`. Il
# vincolo non e' cosmetico: senza, un nome come `../fuori` scriverebbe fuori
# dalla radice, e uno con una barra creerebbe un annidamento che l'elenco non
# ritroverebbe piu'. Stessa forma del vincolo su `Material.name`, piu' il
# divieto esplicito su `.` e `..`: il punto e' un carattere ammesso dalla
# tabella (`lab.v2` e' un nome legittimo), quindi il solo pattern lascia
# passare proprio le due voci che risalgono l'albero.
NOME_CORSA = r"^[A-Za-z0-9_.-]+$"

# Il file che marca una corsa come di riferimento. Vive nella cartella della
# corsa e non in un elenco dentro il codice: cosi' la protezione viaggia con la
# cartella, e chi la copia altrove se la porta dietro.
SENTINELLA_SOLA_LETTURA = "SOLA_LETTURA"

# I nomi con cui il server accetta di essere chiamato. `ServerConfig.host` e'
# 127.0.0.1: qualunque altro nome nell'Host significa che la richiesta e'
# passata per una risoluzione che non e' quella dell'utente.
NOMI_LOCALI = frozenset({"127.0.0.1", "localhost", "::1", "0.0.0.0"})

# Il selettore file di sistema, per il campo del percorso nella schermata
# d'ingresso. Sfogliare e' una comodita' e non l'unica strada: il campo resta
# scrivibile, e chi lavora da remoto o incolla un percorso non passa di qui.
#
# Gira in un SOTTOPROCESSO e non nel server, per due ragioni che non sono
# stilistiche:
#   1. su macOS Tk pretende il thread principale del processo, e FastAPI
#      esegue gli endpoint sincroni in un threadpool. Chiamare tkinter li'
#      dentro non fa cadere la richiesta: fa cadere il processo.
#   2. un dialogo lasciato aperto terrebbe occupato quel thread per sempre.
#      Un sottoprocesso ha il proprio timeout e si uccide.
#
# Il percorso torna su stdout e nient'altro finisce li': gli avvisi di Tk vanno
# su stderr, e mescolarli al risultato darebbe un percorso che non esiste.
_SELETTORE = """
import sys
import tkinter
from tkinter import filedialog

radice = tkinter.Tk()
radice.withdraw()
# Senza questo la finestra nasce dietro al browser e sembra che il clic non
# abbia fatto niente.
radice.attributes("-topmost", True)
# Su macOS un dialogo con `parent` nasce come sheet agganciato alla radice:
# quella è `withdraw()`, mai mostrata, ferma nell'angolo di default, e lo
# sheet esce tagliato sul bordo -- e non si trascina. Altrove `parent` serve
# solo a modalità e posizione, e resta.
argomenti = dict(
    title="MeshRec - scegli la nuvola di punti",
    initialdir=sys.argv[1],
    filetypes=[("Nuvole di punti", "*.pcd *.ply *.xyz"), ("Tutti i file", "*")],
)
if sys.platform != "darwin":
    argomenti["parent"] = radice
scelto = filedialog.askopenfilename(**argomenti)
radice.destroy()
# In byte e non con `write`, e la codifica dichiarata da tutte e due le parti.
# `sys.stdout.write` su Windows userebbe la codepage locale (cp1252), e il
# lettore la decodifica: un percorso con una lettera accentata -- una cartella
# qualunque di un utente italiano -- usciva 0xe0 ed entrava come utf-8, che
# quel byte non lo ammette come continuazione. Le due parole d'esempio non si
# scrivono qui: questo commento vive dentro il sorgente che va sulla riga di
# comando del sottoprocesso, e non c'e' ragione di metterci caratteri fuori
# tabella. L'utente vedeva un
# UnicodeDecodeError al posto del file che aveva appena scelto.
sys.stdout.buffer.write((scelto or "").encode("utf-8"))
"""

# Due minuti: il dialogo e' un'azione umana e non una richiesta di rete, ma
# senza un tetto un sottoprocesso dimenticato resterebbe fino allo spegnimento.
SECONDI_SELETTORE = 120


class CartellaIniziale(BaseModel):
    """Da dove aprire il selettore. Vuoto: la cartella da cui gira il server."""

    model_config = ConfigDict(extra="forbid")

    iniziale: str = ""


def _riga_decisiva(stderr: str) -> str:
    """L'ultima riga non vuota di una traccia: quella che dice che cosa e'
    successo, senza le venti che dicono da dove."""
    righe = [riga.strip() for riga in stderr.splitlines() if riga.strip()]
    return righe[-1] if righe else "nessun dettaglio"


def _non_e_un_passo_dell_albero(nome: str) -> str:
    """Rifiuta i nomi fatti di soli punti.

    Il punto e' un carattere ammesso dalla tabella -- `lab.v2` e' un nome
    legittimo -- quindi il solo pattern lascia passare `.`, `..` e `...`.
    I primi due risalgono l'albero; il terzo su POSIX e' una cartella
    letterale, ma su Win32 i punti finali vengono normalizzati via. La regola
    che li copre tutti e' una: un nome non e' un passo dell'albero.
    """
    if not nome.strip("."):
        raise ValueError(
            f"'{nome}' non è un nome di corsa: è un passo dell'albero delle cartelle"
        )
    return nome


# Uvicorn serve le tratte sincrone su un pool di thread: due scritture di
# configurazione possono sovrapporsi davvero, e il deposito dello storico legge
# lo stato prima di scriverlo.
#
# Rientrante per margine, non per necessita': qui c'era scritto che gli endpoint
# dello storico lo prendessero e chiamassero funzioni che lo riprendono, e non
# e' vero -- ne' `_deposita_le_modifiche_fatte_a_mano` ne' `_ripristina` lo
# prendono, e `scrivi_config` non e' mai chiamata da dentro. Un Lock semplice
# basterebbe oggi. Resta rientrante perche' questo blocco tiene insieme una
# lettura e una scrittura, ed e' il posto dove un giorno una chiamata annidata
# ci finisce dentro: un errore di provenienza e' silenzioso, uno stallo no, ma
# un'applicazione locale che si pianta e' comunque un guasto che l'utente
# subisce senza saperne il perche'.
_LUCCHETTO_STORICO = threading.RLock()


def _campi_cambiati(
    vecchio: dict[str, object], nuovo: dict[str, object], prefisso: str = ""
) -> list[str]:
    """I percorsi puntati dei campi diversi fra due `model_dump`.

    Il registro dello storico non si pota mai, quindi cio' che vi si scrive
    resta per sempre: elencare i blocchi di primo livello a ogni scrittura
    sarebbe precisione inventata proprio nel file che dovra' rispondere «da
    dove viene questa versione». Il vocabolario e' quello che gia' registrano
    `POST /api/crop` e `POST /api/cluster`: `segment.crop_min`, non `segment`.
    """
    cambiati: list[str] = []
    for chiave, valore in nuovo.items():
        percorso = f"{prefisso}{chiave}"
        prima = vecchio.get(chiave)
        if isinstance(prima, dict) and isinstance(valore, dict):
            cambiati.extend(_campi_cambiati(prima, valore, f"{percorso}."))
        elif prima != valore:
            cambiati.append(percorso)
    return cambiati


# I tipi che si battono in una riga sola. `Path` sta con `str` e non fra i
# composti: per python e' un oggetto, per chi lo scrive e' un percorso, ed e'
# il campo piu' importante del pannello dello step 1.
_TIPI_SCALARI: dict[object, str] = {
    bool: "booleano",
    int: "intero",
    float: "reale",
    str: "testo",
    Path: "testo",
}

# I quattro estremi di annotated_types, letti per nome dalla `metadata` del
# campo. `ge` e `gt` restano distinti: uno slider che li confonde offre un
# valore che il modello rifiuta.
_ESTREMI = ("gt", "ge", "lt", "le")


def _forma_del_campo(campo: object) -> dict[str, object]:
    """Di che tipo e' un campo e che valori ammette, letto dal modello.

    Dalle annotazioni e dai vincoli di pydantic, non da una tabella scritta
    accanto ai modelli: una tabella parallela e' una seconda verita' da tenere
    allineata, e il primo campo aggiunto la lascia indietro.

    Il pannello ne ha bisogno per scegliere la casella: prima il tipo veniva
    indovinato da `typeof` del valore corrente, e un intero valeva testo
    finche' era `None`.
    """
    annotazione = campo.annotation
    nullabile = type(None) in get_args(annotazione)
    if nullabile:
        annotazione = next(t for t in get_args(annotazione) if t is not type(None))
    forma: dict[str, object] = {"nullabile": nullabile}
    if get_origin(annotazione) is Literal:
        forma["tipo"] = "enumerazione"
        forma["valori"] = list(get_args(annotazione))
    else:
        # Una lista, una tupla, un modello annidato: si modificano dal file di
        # configurazione, e il pannello li tiene in sola lettura.
        forma["tipo"] = _TIPI_SCALARI.get(annotazione, "composto")
    for vincolo in campo.metadata:
        for nome in _ESTREMI:
            # getattr e non isinstance: `Interval` porta tutti e quattro gli
            # attributi insieme, i tre non dichiarati a None.
            estremo = getattr(vincolo, nome, None)
            if estremo is not None:
                forma[nome] = estremo
    # `title` solo dove il modello lo dichiara: dove manca, la chiave resta
    # l'unica cosa che si sa e il pannello non inventa una frase.
    if campo.title is not None:
        forma["etichetta"] = campo.title
    return forma


# I campi che il pannello di uno step non mostra, benche' il blocco sia suo in
# `STEP_BLOCKS`. Quella tabella assegna blocchi interi ed e' anche la tabella
# da cui discende l'invalidazione a valle (`steps.step_fingerprints`):
# toglierne un blocco sposta la catena delle impronte e dichiara da rieseguire
# le corse gia' su disco. E' cio' che il deck nudo ha fatto una volta, con la
# decisione presa (spec 2026-09-07); per il solo nascondere un campo il posto
# resta qui, a grana di campo, dove riguarda solo cio' che si vede.
#
# Una voce e' un blocco intero (`tet`) o un campo solo (`tet.reference_ratio`).
_FUORI_DAL_PANNELLO: dict[int, frozenset[str]] = {
    # `reference_ratio` e' il metro con cui lo step 10 conta gli elementi fuori
    # vincolo: non tocca nulla di cio' che lo step 9 fa, e nel pannello del 9
    # sembrerebbe un secondo `min_ratio`.
    9: frozenset({"tet.reference_ratio"}),
    # Lo step 11 esporta il modello: non tetraedrizza (quello e' il 9), e `tet`
    # si dichiara nei pannelli del 9 e del 10. Di `export` resta tutto: e' un
    # campo solo, la tolleranza con cui gli insiemi di faccia sono estratti.
    11: frozenset({"tet"}),
}


def _etichetta_del_percorso(percorso: tuple[object, ...]) -> str:
    """L'etichetta del campo che il validatore ha rifiutato.

    «Una chiave non si stampa mai, si stampa la sua etichetta» (PRODUCT.md)
    vale anche per il rifiuto: sotto la casella compariva
    `surface.poisson_depth`, cioe' la stessa chiave grezza che il pannello ha
    smesso di mostrare sopra di essa. Dove il modello non dichiara `title` la
    chiave resta l'unica cosa che si sa, e non si inventa una frase.

    `body` in testa lo mette FastAPI quando il rifiuto arriva dalla lettura del
    corpo della richiesta: non e' un campo e non si stampa.
    """
    pezzi = [str(passo) for passo in percorso if passo != "body"]
    modello: object = PipelineConfig
    etichetta: str | None = None
    for pezzo in pezzi:
        campi = getattr(modello, "model_fields", None)
        if not campi or pezzo not in campi:
            etichetta = None
            break
        campo = campi[pezzo]
        etichetta = campo.title or pezzo
        modello = campo.annotation
    return etichetta or ".".join(pezzi) or "la configurazione"


# I rifiuti di pydantic che il pannello sa produrre, detti in italiano. Sono i
# vincoli che i campi dichiarano -- gli estremi, il tipo, l'insieme chiuso, il
# campo obbligatorio -- e non la tabella intera di pydantic: cio' che non e'
# qui esce come il validatore lo scrive, che e' meglio di una traduzione
# indovinata.
_RIFIUTI_TRADOTTI: tuple[tuple[str, str], ...] = (
    (r"^Input should be less than or equal to (.+)$", "non può superare {}"),
    (r"^Input should be less than (.+)$", "deve stare sotto {}"),
    (r"^Input should be greater than or equal to (.+)$", "non può stare sotto {}"),
    (r"^Input should be greater than (.+)$", "deve superare {}"),
    (r"^Input should be a valid integer.*$", "vuole un numero intero"),
    (r"^Input should be a valid number.*$", "vuole un numero"),
    (r"^Input should be a valid boolean.*$", "vuole vero o falso"),
    (r"^Input should be a valid string$", "vuole del testo"),
    (r"^Field required$", "è obbligatorio e non è stato dichiarato"),
    # La regex non si stampa: chi dichiara un materiale legge «C25/30» rifiutato
    # da `'^[A-Za-z0-9_.-]+$'` e non sa che cosa correggere. I caratteri sono
    # detti per nome perche' nel progetto il vincolo e' uno solo -- `NomeSet` in
    # core/config.py e `NOME_CORSA` qui, che portano la stessa classe -- e
    # nominarli e' l'unica forma utile: un «non e' nella forma ammessa» non dice
    # quale sia la forma. Un pattern nuovo e diverso vorra' la propria riga.
    (
        r"^String should match pattern .*$",
        "ammette solo lettere non accentate, cifre, punto, trattino e trattino basso",
    ),
    (r"^Input should be (.+)$", "ammette {}"),
)


def _ragione_tradotta(msg: str) -> str:
    for forma, italiano in _RIFIUTI_TRADOTTI:
        trovata = re.match(forma, msg)
        if trovata:
            return italiano.format(*trovata.groups())
    return msg


def _rifiuto_leggibile(errore: Exception) -> str:
    """Una riga che dice che cosa non va, non il verbale del validatore.

    `str(ValidationError)` sono cinque righe con il tipo interno, il valore
    ricevuto e un collegamento alla documentazione di pydantic; rese dentro un
    `<small>` collassano in una riga sola e illeggibile. Chi apre il programma
    deve leggere quale campo e perche', non imparare pydantic.
    """
    if isinstance(errore, ValidationError) and errore.errors():
        voce = errore.errors()[0]
        return f"{_etichetta_del_percorso(tuple(voce['loc']))}: {_ragione_tradotta(voce['msg'])}"
    return f"{type(errore).__name__}: {errore}"


NomeCorsa = Annotated[
    str,
    Field(pattern=NOME_CORSA, min_length=1, max_length=64),
    AfterValidator(_non_e_un_passo_dell_albero),
]


class NuovaCorsa(BaseModel):
    """Tutto cio' che serve per far nascere una corsa: un nome e una nuvola."""

    model_config = ConfigDict(extra="forbid")

    nome: NomeCorsa
    nuvola: Path


class CorsaScelta(BaseModel):
    """La corsa gia' su disco da legare all'applicazione."""

    model_config = ConfigDict(extra="forbid")

    nome: NomeCorsa



def create_app(
    config_path: Path | None = None,
    radice_corse: Path = Path("runs"),
) -> FastAPI:
    """Applicazione legata a un file di configurazione, che e' la corsa corrente.

    Il legame e' mutabile e puo' nascere vuoto. `serve` senza argomenti apre
    l'interfaccia su nessuna corsa: si sceglie una cartella di `runs/` o si
    crea una corsa nuova da un file di punti, e da li' in poi tutto il resto
    del server lavora come prima su `config_path`. Chi passa gia' un percorso
    (la forma vecchia, `serve config.yaml`) trova l'applicazione legata
    all'avvio, come e' sempre stato.

    `radice_corse` e' la cartella dove le corse nascono e dove vengono cercate,
    relativa come `run.out_dir` e `CACHE_DIR`: risolta rispetto alla cartella
    da cui gira il server, non rispetto al file di configurazione.
    """
    config_path = Path(config_path) if config_path is not None else None
    radice_corse = Path(radice_corse)
    app = FastAPI(title="MeshRec", docs_url=None, redoc_url=None)

    def corrente() -> PipelineConfig:
        if config_path is None:
            raise ValueError(
                "nessuna corsa aperta: scegline una fra quelle di "
                f"'{radice_corse}' oppure creane una da un file di punti"
            )
        return load_config(config_path)

    def lega(percorso: Path) -> None:
        nonlocal config_path
        # Letta prima di legare: una configurazione illeggibile non deve
        # lasciare l'applicazione appesa a un percorso che nessun endpoint
        # riuscira' piu' a caricare.
        load_config(percorso)
        config_path = percorso
        # `mappe` e' indicizzata sul solo numero di step: senza questa riga, dopo
        # un cambio di corsa `/api/cluster` troverebbe la mappa di decimazione
        # della corsa precedente, la guardia `if not gruppi` resterebbe
        # soddisfatta, e la risposta sarebbe un cluster plausibile e sbagliato.
        mappe.clear()

    def sola_lettura() -> bool:
        """Vero se la corsa aperta porta il file sentinella `SOLA_LETTURA`.

        `runs/muro` e `runs/lab_crop` sono le corse di riferimento della tesi.
        Prima bastava un clic nell'elenco per legarle e da li' ogni bottone ci
        scriveva dentro; la sentinella le apre in lettura e ferma le tratte che
        scrivono.
        """
        return config_path is not None and (config_path.parent / SENTINELLA_SOLA_LETTURA).exists()

    def non_in_sola_lettura(azione: str) -> None:
        if sola_lettura():
            raise ValueError(
                f"'{nome_corrente() or config_path.parent}' è una corsa di riferimento, "
                f"aperta in sola lettura: {azione} la modificherebbe. Toglile il file "
                f"{SENTINELLA_SOLA_LETTURA} se vuoi davvero riscriverla, oppure creane una nuova"
            )

    def nome_corrente() -> str | None:
        """Il nome della corsa aperta, se e' una delle corse di `radice_corse`.

        `serve casi/lab_telaio.yaml` apre una configurazione che non sta in
        `runs/`: non e' una voce dell'elenco, e restituire «casi» segnerebbe
        come corrente una riga che non esiste.
        """
        if config_path is None:
            return None
        cartella = config_path.parent
        if cartella.resolve().parent != radice_corse.resolve():
            return None
        return cartella.name

    @app.middleware("http")
    async def solo_dal_calcolatore_locale(richiesta, prosegui):
        """Rifiuta le richieste che non arrivano da un nome locale.

        Il DNS rebinding fa risolvere un dominio ostile su 127.0.0.1 e rende le
        richieste same-origin: da li' una pagina qualunque enumererebbe i
        percorsi assoluti del disco (`/api/corse`), creerebbe corse e
        lancerebbe sottoprocessi. Lo ferma il controllo sull'`Host`: il nome e
        non l'indirizzo del chiamante, perche' e' l'`Host` che il rebinding
        controlla e che l'origine legittima non puo' falsificare dal browser.

        **Il CSRF non era chiuso, e qui c'era scritto che lo fosse.** L'argomento
        era «i corpi sono application/json, quindi il browser fa il preflight»,
        e vale per le sole tratte che un corpo ce l'hanno. Cinque non ce l'hanno:
        `/api/storico/indietro` e `/api/storico/avanti`, e prima di loro
        `/api/cancel`, `/api/step/{numero}`, `/api/step/{numero}/from` -- di cui
        due lanciano sottoprocessi.
        Una POST senza corpo non porta `Content-Type`, quindi e' una richiesta
        CORS-safelisted e il preflight non parte; l'`Host` che arriva e'
        `127.0.0.1`, quindi la guardia sopra la lascia passare. La risposta
        resta opaca -- nessun `CORSMiddleware` in questo server -- quindi non si
        legge niente, ma l'effetto collaterale succede lo stesso, e un
        `<form method=POST>` auto-inviato non ha bisogno nemmeno di JS.

        `Sec-Fetch-Site` lo chiude per tutte e cinque in un punto solo: lo scrive
        il browser e una pagina non lo puo' falsificare. Assente vuol dire che a
        chiamare non e' un browser -- `curl`, un test, la suite -- e passa: chi
        non ha un browser non ha nemmeno una vittima da far cliccare, che e' il
        presupposto del CSRF. `none` e' la navigazione diretta, cioe' l'indirizzo
        battuto a mano o il segnalibro con cui questa applicazione si apre.
        """
        sito = richiesta.headers.get("sec-fetch-site")
        if sito is not None and sito not in {"same-origin", "same-site", "none"}:
            return JSONResponse(
                status_code=403,
                content={
                    "errore": "RichiestaDaUnAltroSito",
                    "messaggio": (
                        f"richiesta partita da un altro sito (Sec-Fetch-Site: {sito}): "
                        "questo server risponde solo alla propria interfaccia. "
                        "Aprila da http://127.0.0.1"
                    ),
                },
            )
        nome = (richiesta.headers.get("host") or "").split(":")[0].strip("[]").lower()
        if nome and nome not in NOMI_LOCALI:
            return JSONResponse(
                status_code=403,
                content={
                    "errore": "HostNonLocale",
                    "messaggio": (
                        f"richiesta arrivata con Host '{nome}': questo server risponde "
                        "solo a localhost. Aprilo da http://127.0.0.1"
                    ),
                },
            )
        return await prosegui(richiesta)

    @app.exception_handler(RequestValidationError)
    async def il_corpo_rifiutato_lo_dice_in_italiano(_richiesta, errore: RequestValidationError):
        # Un corpo che non passa i modelli non arriva mai all'endpoint: lo
        # ferma FastAPI, e il suo 422 porta il `detail` grezzo di pydantic, con
        # la chiave del campo e la frase inglese. E' cio' che compariva sotto
        # la casella accanto al cursore: «surface.poisson_depth: Input should
        # be less than or equal to 14». Qui prende la stessa forma di ogni
        # altro rifiuto di questo server, {errore, messaggio}, che
        # `ragioneDelRifiuto` legge per prima.
        voci = errore.errors()
        messaggio = (
            f"{_etichetta_del_percorso(tuple(voci[0]['loc']))}: "
            f"{_ragione_tradotta(voci[0]['msg'])}"
            if voci
            else "la configurazione non è stata accettata"
        )
        return JSONResponse(
            status_code=422,
            content={"errore": "ValidationError", "messaggio": messaggio},
        )

    @app.exception_handler(Exception)
    async def nessuna_eccezione_verso_il_browser(_richiesta, errore: Exception):
        # Il contratto vale sulla tratta: nessun endpoint solleva verso il
        # browser. L'errore torna strutturato, con il tipo, perche'
        # l'interfaccia possa dirlo invece di mostrare una pagina bianca.
        return JSONResponse(
            status_code=400,
            content={"errore": type(errore).__name__, "messaggio": str(errore)},
        )

    # no-cache: un F5 rivalida la pagina ma non i moduli importati, e un
    # viewport.js vecchio con un app.js nuovo ha gia' rotto l'apertura della corsa.
    RIVALIDA_SEMPRE = {"Cache-Control": "no-cache"}

    @app.get("/")
    def interfaccia() -> FileResponse:
        return FileResponse(UI_DIR / "index.html", headers=RIVALIDA_SEMPRE)

    @app.get("/ui/{nome:path}")
    def statico(nome: str) -> FileResponse:
        percorso = (UI_DIR / nome).resolve()
        if not percorso.is_relative_to(UI_DIR) or not percorso.is_file():
            raise FileNotFoundError(f"nessun file dell'interfaccia chiamato {nome}")
        return FileResponse(percorso, headers=RIVALIDA_SEMPRE)

    @app.get("/api/info")
    def informazioni_sul_programma() -> dict[str, object]:
        return identita.informazioni()

    @app.get("/api/run")
    def stato_corsa() -> dict[str, object]:
        # Nessuna corsa non e' un errore: e' lo stato in cui il programma si
        # apre la prima volta. Rispondere 400 qui farebbe nascere l'interfaccia
        # da una pagina rossa invece che dalla schermata d'ingresso.
        if config_path is None:
            return {"legata": False, "corsa": None, "out_dir": None,
                    "config_path": None, "steps": None}
        cfg = corrente()
        return {
            "legata": True,
            "corsa": nome_corrente(),
            "out_dir": cfg.run.out_dir.as_posix(),
            "config_path": config_path.as_posix(),
            "steps": steps.run_state(cfg.run.out_dir, cfg),
        }

    @app.get("/api/corse")
    def elenco_corse() -> dict[str, object]:
        """Le corse trovate su disco: una cartella con un config.yaml dentro.

        Una configurazione illeggibile non fa sparire le altre: quella riga
        porta il proprio errore e resta nell'elenco, perche' una corsa rotta
        che non compare e' indistinguibile da una corsa che non e' mai esistita.
        """
        corse: list[dict[str, object]] = []
        if radice_corse.is_dir():
            for cartella in sorted(radice_corse.iterdir()):
                percorso = cartella / "config.yaml"
                if not percorso.is_file():
                    continue
                voce: dict[str, object] = {
                    "nome": cartella.name,
                    "nuvola": None,
                    "modificata": None,
                    "riferimento": (cartella / SENTINELLA_SOLA_LETTURA).exists(),
                    "errore": None,
                }
                # `stat()` dentro il try quanto `load_config`: un config
                # cancellato fra `is_file()` e qui faceva 400 sull'intero
                # elenco invece di perdere la sola riga che lo riguarda.
                try:
                    voce["modificata"] = percorso.stat().st_mtime
                    cfg = load_config(percorso)
                except Exception as errore:
                    voce["errore"] = _rifiuto_leggibile(errore)
                else:
                    voce["nuvola"] = cfg.input.path.as_posix()
                corse.append(voce)
        return {"radice": str(radice_corse), "corse": corse, "corrente": nome_corrente()}

    @app.post("/api/corse")
    def crea_corsa(richiesta: NuovaCorsa) -> dict[str, object]:
        """Fa nascere una corsa dalla sola nuvola, e ci lega l'applicazione.

        Scrive `input.path` e `run.out_dir` e nient'altro: ogni altro parametro
        resta al proprio predefinito, dichiarato in `config.py`. Il materiale
        non e' fra questi: col deck nudo si assegna in Abaqus.
        """
        # Prima di ogni altra cosa: `Path("")` e' `PosixPath('.')`, e senza
        # questo ramo un campo lasciato vuoto tornava indietro come
        # «'.' non e' un file», cioe' un punto comparso dal nulla.
        if not str(richiesta.nuvola).strip():
            raise ValueError("indica il percorso del file di punti da cui far nascere la corsa")
        nuvola = Path(richiesta.nuvola).expanduser()
        if not nuvola.exists():
            raise ValueError(f"nessun file di punti in '{nuvola}'")
        if not nuvola.is_file():
            raise ValueError(f"'{nuvola}' non è un file: serve una nuvola di punti")
        if not nuvola.suffix:
            raise ValueError(
                f"'{nuvola.name}' non ha estensione: servono "
                f"{', '.join(io.ESTENSIONI_NUVOLA)}"
            )
        if nuvola.suffix.lower() not in io.ESTENSIONI_NUVOLA:
            raise ValueError(
                f"'{nuvola.suffix}' non è un formato che il programma legge: "
                f"servono {', '.join(io.ESTENSIONI_NUVOLA)}"
            )
        cartella = radice_corse / richiesta.nome
        if cartella.exists():
            raise ValueError(
                f"'{richiesta.nome}' esiste già in '{radice_corse}': scegli un altro "
                "nome. Una corsa non viene mai sovrascritta"
            )
        cfg = PipelineConfig(
            input=InputConfig(path=nuvola),
            run=RunConfig(out_dir=cartella),
        )
        percorso = cartella / "config.yaml"
        save_config(cfg, percorso)
        lega(percorso)
        return stato_corsa()

    @app.put("/api/corrente")
    def apri_corsa(richiesta: CorsaScelta) -> dict[str, object]:
        percorso = radice_corse / richiesta.nome / "config.yaml"
        if not percorso.is_file():
            raise ValueError(
                f"nessuna corsa chiamata '{richiesta.nome}' in '{radice_corse}'"
            )
        lega(percorso)
        return stato_corsa()

    @app.post("/api/sfoglia")
    def sfoglia(richiesta: CartellaIniziale) -> dict[str, object]:
        """Il selettore file di sistema, per non dover scrivere il percorso.

        Apre la finestra sulla macchina dove gira il server -- che e' la stessa
        dove sta il file, e la stessa dove sta il browser: il programma e'
        locale per progetto. Un `<input type="file">` non servirebbe: il
        browser restituisce un oggetto File e nasconde la via reale
        (`C:\\fakepath\\...`), per difesa propria, quindi il percorso da
        scrivere in `input.path` non arriverebbe mai.

        Annullare non e' un errore: torna `percorso: null` e chi ha chiamato
        lascia il campo com'era.
        """
        iniziale = Path(richiesta.iniziale).expanduser() if richiesta.iniziale.strip() else None
        # Dalla cartella del percorso gia' battuto, se ne porta uno: riaprire
        # il selettore deve tornare dove si era, non alla radice ogni volta.
        if iniziale is not None and not iniziale.is_dir():
            iniziale = iniziale.parent
        if iniziale is None or not iniziale.is_dir():
            iniziale = Path.cwd()
        try:
            esito = subprocess.run(
                [sys.executable, "-c", _SELETTORE, str(iniziale)],
                capture_output=True,
                text=True,
                # Dichiarata, non ereditata: senza, `text=True` decodifica con
                # `locale.getpreferredencoding()`, che dipende dalla macchina e
                # dalle variabili d'ambiente -- e il figlio scrive utf-8 sempre.
                # `errors="replace"` perche' un percorso illeggibile e' un
                # percorso da mostrare storto e correggere, non un'eccezione
                # che si mangia la scelta appena fatta.
                encoding="utf-8",
                errors="replace",
                timeout=SECONDI_SELETTORE,
            )
        except subprocess.TimeoutExpired:
            raise ValueError(
                f"il selettore file è rimasto aperto più di {SECONDI_SELETTORE} secondi "
                "ed è stato chiuso: riprova, oppure scrivi il percorso nel campo"
            ) from None
        if esito.returncode != 0:
            # Succede senza tkinter (alcune build di Python ridotte) e senza
            # schermo a cui attaccarsi (sessione remota, servizio). Nessuno dei
            # due e' un motivo per non lavorare: il campo resta scrivibile, e
            # il messaggio lo dice invece di lasciare il bottone muto.
            raise ValueError(
                "il selettore file non si è aperto su questa macchina "
                f"({_riga_decisiva(esito.stderr)}): scrivi il percorso nel campo"
            )
        scelto = esito.stdout.strip()
        return {"percorso": scelto or None}

    class ImmagineDaSalvare(BaseModel):
        model_config = ConfigDict(extra="forbid")

        numero: int = Field(ge=1, le=99)
        nome: str = ""
        didascalia: str = ""
        dati: str

    @app.post("/api/immagine", response_model=None)
    async def salva_immagine(richiesta: Request) -> JSONResponse | dict[str, object]:
        """Il PNG del viewport, scritto in `<out_dir>/immagini/`.

        Il corpo si legge a mano e non con un modello nella firma: il limite di
        dimensione deve rispondere 413 prima di decodificare cinquanta
        megabyte, e un modello nella firma li avrebbe gia' letti.

        Le corse in sola lettura accettano: un PNG in `immagini/` non tocca
        configurazione ne' artefatti, e sono proprio le corse di riferimento
        quelle di cui servono le figure.
        """
        dichiarata = richiesta.headers.get("content-length")
        if dichiarata is not None and dichiarata.isdigit() and int(dichiarata) > immagini.LIMITE_BYTE:
            return JSONResponse(status_code=413, content={
                "errore": "ImmagineTroppoGrande",
                "messaggio": f"il corpo della richiesta supera i {immagini.LIMITE_BYTE // (1024 * 1024)} MB",
            })
        if config_path is None:
            return JSONResponse(status_code=409, content={
                "errore": "NessunaCorsa",
                "messaggio": "nessuna corsa aperta: apri o crea una corsa prima di salvare l'immagine",
            })
        corpo = await richiesta.body()
        if len(corpo) > immagini.LIMITE_BYTE:
            return JSONResponse(status_code=413, content={
                "errore": "ImmagineTroppoGrande",
                "messaggio": f"il corpo della richiesta supera i {immagini.LIMITE_BYTE // (1024 * 1024)} MB",
            })
        try:
            dati = ImmagineDaSalvare.model_validate_json(corpo)
        except ValidationError:
            return JSONResponse(status_code=400, content={
                "errore": "ImmagineNonValida",
                "messaggio": "l'immagine non si è potuta leggere: il corpo non ha i campi attesi "
                             "(numero, nome, didascalia, dati)",
            })
        try:
            png = immagini.decodifica_png(dati.dati)
        except ValueError as errore:
            return JSONResponse(status_code=400, content={
                "errore": "ImmagineNonValida",
                "messaggio": str(errore),
            })
        percorso = immagini.salva(Path(corrente().run.out_dir), dati.numero, dati.nome, dati.didascalia, png)
        return {"percorso": str(percorso)}

    @app.get("/api/config")
    def configurazione() -> dict[str, object]:
        return corrente().model_dump(mode="json")

    def scrivi_config(
        nuova: PipelineConfig, endpoint: str, campi: list[str] | None = None
    ) -> None:
        """L'unico punto in cui l'interfaccia scrive la configurazione, e in cui
        la versione di prima finisce nello storico.

        `campi` sono i percorsi puntati di cio' che cambia. Chi li conosce li
        passa -- crop e cluster mutano `cfg` in posto, e un confronto qui
        troverebbe l'oggetto uguale a se stesso; chi non li conosce lascia
        calcolare il confronto qui, perche' e' qui che la configurazione di
        prima e' ancora in mano.

        `core.config.save_config` non si tocca: la chiamano anche pipeline e
        sweep, e agganciare lo storico li' depositerebbe una versione per ogni
        candidato di uno sweep. Il punto condiviso giusto e' il server, non il
        core: e' il server a servire i gesti di una persona, ed e' dei gesti di
        una persona che si tiene lo storico.

        `run.out_dir` non si sposta da qui. In `PUT /api/config` la
        configurazione arriva dal corpo della richiesta, quindi senza questa
        guardia il deposito nascerebbe dove dice il browser: `runs/lab_crop` e
        `runs/muro` sono corse di riferimento in sola lettura, e una `.storico/`
        dentro una di loro e' una scrittura che non si doveva fare. Peggio, la
        versione «avvio» conterrebbe il config della corsa vecchia depositato
        nel deposito della nuova, e il cursore della vecchia resterebbe
        indietro: da li' due «indietro» consecutivi consultano due depositi
        diversi.

        La guardia sta qui, nell'unico punto di scrittura, e non nel solo
        endpoint che oggi ne ha bisogno: crop e cluster partono da `corrente()`
        e la superano per costruzione.

        Per la stessa ragione ci sta anche quella di sola lettura, che i tre
        chiamanti di oggi hanno gia' ciascuno per conto proprio. Lasciarla solo
        a loro voleva dire che il quarto chiamante -- quello che ancora non
        esiste -- avrebbe depositato una `.storico/` dentro una corsa di
        riferimento senza che niente lo fermasse. Ripeterla e' senza effetto
        sui tre che la fanno gia': solleva sullo stesso stato, prima.
        """
        non_in_sola_lettura(f"scrivere la configurazione ({endpoint})")
        with _LUCCHETTO_STORICO:
            # La lettura sta dentro insieme alla scrittura: e' su questa che si
            # decide che cosa registrare, e una decisione presa su uno stato che
            # nel frattempo e' cambiato e' una decisione sbagliata. Due PUT
            # sovrapposte scriverebbero il contenuto giusto -- quello e'
            # protetto -- e una provenienza falsa, cioe' il difetto peggiore dei
            # due: registro.jsonl non si pota mai, quindi quella riga resta.
            attuale = corrente()
            if Path(nuova.run.out_dir) != Path(attuale.run.out_dir):
                raise ValueError(
                    f"la corsa non si cambia dall'interfaccia: run.out_dir è "
                    f"{attuale.run.out_dir} e la richiesta chiede {nuova.run.out_dir}. "
                    "Per lavorare su un'altra corsa riavvia meshrec serve con il suo "
                    "file di configurazione"
                )
            if campi is None:
                campi = _campi_cambiati(
                    attuale.model_dump(mode="json"), nuova.model_dump(mode="json")
                )
            out_dir = Path(attuale.run.out_dir)
            # La versione di partenza, depositata pigramente alla prima
            # modifica: senza, il primo «indietro» non avrebbe niente a cui
            # tornare e la prima modifica sarebbe l'unica non annullabile. Pigra
            # e non all'avvio perche' aprire l'interfaccia senza toccare niente
            # non e' un gesto da registrare.
            if not storico.esiste(out_dir):
                storico.deposita(out_dir, config_path.read_text(encoding="utf-8"), "avvio", [])
            # La modifica fatta a mano si deposita anche QUI, e non solo prima
            # di un «indietro». `scriviParametro` rimanda l'intera copia che il
            # browser ha in memoria, quindi una riga cambiata dall'editor nel
            # frattempo viene sovrascritta per intero da questa PUT: senza
            # questa riga non finiva in nessuna versione e non esisteva piu' da
            # nessuna parte. Era la stessa perdita irrecuperabile che la porta
            # accanto dichiarava chiusa, entrata dal percorso di scrittura.
            #
            # A deposito appena creato non fa niente: «avvio» ha appena messo
            # dentro il file corrente, quindi i due testi coincidono e torna
            # False senza scrivere.
            _deposita_le_modifiche_fatte_a_mano(out_dir)
            save_config(nuova, config_path)
            storico.deposita(out_dir, config_path.read_text(encoding="utf-8"), endpoint, campi)

    @app.put("/api/config")
    def scrivi_configurazione(nuova: PipelineConfig) -> dict[str, object]:
        # La validazione e' quella dei modelli: l'interfaccia non ne ha una
        # propria, e un valore fuori dominio non arriva mai alla pipeline.
        # `corrente()` prima della scrittura per la sola guardia sul legame:
        # senza, `save_config(nuova, None)` cadrebbe con un TypeError che non
        # dice quale sia il problema.
        corrente()
        non_in_sola_lettura("riscrivere la configurazione")
        scrivi_config(nuova, "PUT /api/config")
        return nuova.model_dump(mode="json")

    def _deposita_le_modifiche_fatte_a_mano(out_dir: Path) -> bool:
        """Deposita il config che sta su disco, se non e' quello al cursore.
        Torna vero quando il deposito ha tolto una coda del rifare.

        Il progetto e' nato CLI-first e le Fasi 1 e 2 si lavorano da editor: col
        server acceso, un parametro cambiato a mano in `config.yaml` non sta in
        nessuna versione, e un «indietro» lo sovrascriverebbe senza che ne
        esista una copia da nessuna parte. E' l'unica perdita irrecuperabile di
        questa superficie, e basta depositarlo per chiuderla.

        Depositato, e' l'ultima scrittura: «indietro» la toglie e «avanti» la
        rimette. E' cio' che chi preme Ctrl+Z si aspetta senza dover leggere
        niente, mentre un rifiuto lo lascerebbe senza undo fino a un
        ricaricamento che nessuno gli ha detto di fare.

        Ma la coda tolta va DETTA: senza, «avanti» risponde «niente da rifare»
        dopo aver fatto sparire proprio le versioni che c'erano da rifare, cioe'
        tace un fatto.

        Il deposito non si crea qui: se non esiste non c'e' niente da annullare,
        e crearlo vorrebbe dire scrivere in una cartella che un config appena
        cambiato a mano puo' aver spostato altrove.
        """
        if not storico.esiste(out_dir):
            return False
        attuale = config_path.read_text(encoding="utf-8")
        if attuale == storico.versione_corrente(out_dir):
            return False
        # Chiesta PRIMA del deposito: dopo, la versione appena scritta e' essa
        # stessa oltre il cursore di prima.
        coda = storico.coda_oltre_il_cursore(out_dir)
        storico.deposita(out_dir, attuale, "modifica fuori dall'interfaccia", [])
        return coda

    def _ripristina(testo: str | None, vuoto: str, rimetti, versione: int) -> dict[str, object]:
        """`rimetti` riporta il cursore dove stava: indietro e avanti lo hanno
        gia' spostato quando questa funzione riceve il testo, e ogni rifiuto da
        qui in giu' deve annullare anche quello spostamento.

        Ogni rifiuto porta `guasto`, che distingue i due casi che si somigliano
        solo nella forma. «Niente da annullare» e' il caso normale di chi preme
        Ctrl+Z una volta di troppo; «una versione non e' leggibile» chiede
        invece di mettere le mani dentro `.storico`. Senza quel bit il browser
        li mostrerebbe con lo stesso peso. Non e' un codice di stato perche' la
        richiesta e' formata bene: e' lo stato sul disco a essere rotto, e ne'
        400 (malformata) ne' 404 (non c'e' ancora) hanno una casella per questo.
        """
        if testo is None:
            return {"annullato": False, "guasto": False, "perche": vuoto}
        cfg_prima = corrente()
        deposito = Path(cfg_prima.run.out_dir) / storico.CARTELLA
        # Si valida una COPIA in memoria: su disco va comunque il testo
        # originale, quindi nessun modello riserializzato tocca il file. Non e'
        # una cautela di troppo: senza, quel testo arriva fino a config.yaml e
        # nessuno lo respinge prima. `load_config` lo respinge dopo, a file gia'
        # riscritto, e da quel momento ogni tratta che chiama corrente()
        # fallisce -- compresi questi due endpoint, cioe' il deposito smette di
        # essere raggiungibile via HTTP.
        # `carica_yaml_da_testo` e NON `yaml.safe_load`: dev'essere lo stesso
        # lettore che rileggera' il file, senno' la prova e' piu' permissiva
        # del controllo vero. Con `safe_load` una versione con due chiavi
        # omonime passava di qui, finiva su config.yaml, e la respingeva
        # `load_config` -- dopo la scrittura, cioe' quando il deposito era gia'
        # irraggiungibile. E' l'unico ingresso degenere che non ha altro
        # sintomo: il lettore di serie tiene l'ultima e la prima sparisce muta.
        try:
            candidata = PipelineConfig.model_validate(carica_yaml_da_testo(testo))
        except Exception as errore:
            rimetti()
            return {
                "annullato": False,
                "guasto": True,
                "perche": (
                    f"una versione salvata non è più una configurazione leggibile "
                    f"({type(errore).__name__}): correggi o cancella {deposito}, "
                    "poi riprova"
                ),
            }
        # Il caso peggiore e' quello che NON solleva: una versione con un altro
        # out_dir e' valida, e accettarla ripunterebbe l'applicazione su
        # un'altra corsa in silenzio. Il prossimo «esegui step» scriverebbe i
        # suoi artefatti la' dentro, che se e' una corsa di riferimento e' il
        # danno che l'intero progetto vieta.
        if Path(candidata.run.out_dir) != Path(cfg_prima.run.out_dir):
            rimetti()
            return {
                "annullato": False,
                "guasto": True,
                "perche": (
                    f"quella versione punta a un'altra corsa ({candidata.run.out_dir}): "
                    "per lavorarci riavvia meshrec serve con il suo file di configurazione"
                ),
            }
        # Il testo si riscrive tale e quale, senza ripassare dal modello: la
        # versione depositata e' gia' per costruzione rileggibile (l'ha scritta
        # save_config), e ripassarci la normalizzerebbe -- cioe' l'undo
        # restituirebbe un file diverso da quello che ha tolto.
        try:
            scrivi_atomico(
                config_path,
                lambda destinazione: destinazione.write_text(testo, encoding="utf-8"),
            )
        except OSError:
            # Il cursore si e' mosso prima che la scrittura riuscisse:
            # lasciarlo avanzato farebbe saltare una versione al tentativo
            # successivo.
            rimetti()
            raise
        cfg_dopo = corrente()
        # Se la versione era un'esecuzione, i suoi artefatti tornano con lo
        # scambio; per una configurazione restano, e la catena di impronte li
        # marca da se'. Ma dirlo e' obbligatorio -- un ritorno indietro che
        # cambia in silenzio lo stato di sette step e' una modifica invisibile
        # -- e lo dice `steps`, che porta lo stato nuovo per intero.
        esecuzione = storico.scambia(Path(cfg_dopo.run.out_dir), versione)
        risposta: dict[str, object] = {
            "annullato": True,
            "tipo": "esecuzione" if esecuzione else "configurazione",
            "steps": steps.run_state(cfg_dopo.run.out_dir, cfg_dopo),
        }
        if esecuzione:
            risposta.update(esecuzione)
        return risposta

    @app.post("/api/storico/indietro", response_model=None)
    def storico_indietro() -> dict[str, object] | JSONResponse:
        """Rimette la versione precedente della configurazione.

        Non tace mai: a storico vuoto risponde col proprio «perche'», perche' un
        silenzio identico fra riuscita e nulla-da-fare e' gia' stato prodotto e
        corretto una volta su questo progetto (il bottone «Annulla»).

        Limite dichiarato: dove sta il deposito lo dice `corrente()`, quindi se
        e' `config.yaml` a non essere piu' leggibile questi due endpoint
        rispondono 400 come ogni altra tratta, e lo strumento di recupero muore
        insieme alla cosa da recuperare. Resta cosi' di proposito: quel file lo
        si e' rotto dall'editor, e l'editor e' ancora aperto -- il rimedio e'
        li'. La rottura che una persona non puo' vedere e' quella dentro
        `.storico`, e quella e' coperta.
        """
        with _LUCCHETTO_STORICO:
            non_in_sola_lettura("annullare una modifica")
            if (rifiuto := _in_corso()) is not None:
                return rifiuto
            out_dir = Path(corrente().run.out_dir)
            _deposita_le_modifiche_fatte_a_mano(out_dir)
            # Il numero PRIMA di muovere il cursore: e' la versione che
            # «indietro» toglie, e la sola che puo' avere una cartella da
            # scambiare.
            da_togliere = storico.cursore(out_dir)
            return _ripristina(
                storico.indietro(out_dir),
                "niente da annullare",
                lambda: storico.avanti(out_dir),
                versione=da_togliere,
            )

    @app.post("/api/storico/avanti", response_model=None)
    def storico_avanti() -> dict[str, object] | JSONResponse:
        with _LUCCHETTO_STORICO:
            non_in_sola_lettura("rifare una modifica")
            if (rifiuto := _in_corso()) is not None:
                return rifiuto
            out_dir = Path(corrente().run.out_dir)
            coda_tolta = _deposita_le_modifiche_fatte_a_mano(out_dir)
            # Solo «avanti» ha bisogno di distinguere: dopo un deposito
            # «indietro» ha sempre una versione a cui tornare, quindi non
            # risponde mai a vuoto e non tace niente.
            vuoto = (
                # Il gesto per nome, non un comando per nome: «Annulla» non
                # esiste nell'interfaccia -- il solo bottone che gli somiglia
                # dice «Interrompi il calcolo» (index.html:40) e ferma la corsa,
                # cioe' l'azione sbagliata. Annullare e' solo da tastiera.
                "la modifica fatta a mano a config.yaml ha preso il posto delle "
                "versioni da rifare: per tornare a quella di prima premi Ctrl/Cmd+Z"
                if coda_tolta
                else "niente da rifare"
            )
            testo = storico.avanti(out_dir)
            # Il numero DOPO: «avanti» rimette la versione su cui e' arrivato.
            return _ripristina(
                testo,
                vuoto,
                lambda: storico.indietro(out_dir),
                versione=storico.cursore(out_dir),
            )

    @app.get("/api/metrics")
    def metriche() -> dict[str, object]:
        """Le metriche cosi' come stanno sul disco. L'interfaccia non ne calcola."""
        return sweep.leggi_metriche(corrente().run.out_dir)

    @app.get("/api/deck")
    def deck() -> FileResponse:
        """Consegna il deck dello step 11 cosi' com'e' sul disco.

        Non lo rigenera: il file che si importa in Abaqus dev'essere quello di
        cui il registro porta l'impronta e di cui il report parla. Una copia
        ricalcolata sarebbe un altro file con lo stesso nome, e nessuno avrebbe
        modo di accorgersene.

        Nessun nome di file arriva dalla richiesta: la tratta ne serve uno solo,
        scritto qui, e l'insieme dei nomi serviti e' chiuso perche' non esiste il
        parametro con cui allargarlo. Il controllo sul percorso resta lo stesso:
        `run.out_dir` viene dalla configurazione, la cartella della corsa la
        scrive chiunque abbia il disco, e un `wall_model.inp` che e' un
        collegamento simbolico punta dove vuole. Per questo si confronta il
        percorso RISOLTO, non quello composto.

        La sentinella `SOLA_LETTURA` non la ferma, ed e' deliberato: consegnare
        e' leggere. Le corse di riferimento sono proprio quelle il cui deck serve
        davvero, e una guardia messa qui per simmetria con le tratte che
        scrivono le renderebbe inesportabili.
        """
        cfg = corrente()
        cartella = Path(cfg.run.out_dir).resolve()
        percorso = (cartella / pipeline.DECK_FILENAME).resolve()
        if not percorso.is_relative_to(cartella):
            raise ValueError(
                f"il {pipeline.DECK_FILENAME} di questa corsa porta fuori dalla sua "
                f"cartella ('{percorso}'): non viene consegnato"
            )
        if not percorso.is_file():
            raise ValueError(
                f"nessun deck da esportare: {pipeline.DECK_FILENAME} lo scrive lo step 11, "
                "che questa corsa non ha ancora eseguito. Esegui lo step 11, oppure "
                "«Esegui da qui fino al deck» da uno step a monte"
            )
        # Il nome dice da quale corsa viene: tre `wall_model.inp` scaricati da
        # tre corse diverse sono tre file indistinguibili nella cartella dei
        # download, e la provenienza fa parte del risultato.
        #
        # FileResponse e non un corpo letto in memoria: il deck di `muro` pesa
        # 35.931.310 byte, e starlette lo manda a blocchi.
        return FileResponse(
            percorso,
            media_type="application/octet-stream",
            filename=f"{cartella.name}_{pipeline.DECK_FILENAME}",
        )

    @app.get("/api/schema")
    def schema() -> dict[str, object]:
        """Quali parametri appartengono a quale step, con descrizione e dominio.

        Le descrizioni vengono dai modelli: sono le stesse che documentano il
        perche' di ogni predefinito misurato, e vanno mostrate accanto al
        campo invece di essere riscritte nell'interfaccia.
        """
        modelli = PipelineConfig.model_fields
        fuori: dict[str, object] = {}
        for numero, blocchi in steps.STEP_BLOCKS.items():
            escluse = _FUORI_DAL_PANNELLO.get(numero, frozenset())
            campi: dict[str, object] = {}
            for blocco in blocchi:
                if blocco in escluse:
                    continue
                # `regioni` e' un `dict[NomeSet, RegioneConfig]`, non un
                # `BaseModel`: le sue voci sono nominate dall'operatore, non
                # campi fissi da descrivere uno per uno. Niente `model_fields`
                # da leggere, quindi nessun campo da elencare per questo blocco.
                #
                # La guardia regge le annotazioni che non sono modelli
                # affatto, come questo dict: senza, `model_fields` verrebbe
                # chiesto a un `dict[...]` e /api/schema uscirebbe 200 con i
                # campi mancanti invece di sollevare dove qualcuno se ne
                # accorge. Il difetto muto e' il peggiore dei due -- le
                # annotazioni che non sono modelli le scarta questo `hasattr`.
                annidato = modelli[blocco].annotation
                if not hasattr(annidato, "model_fields"):
                    campi[blocco] = {}
                    continue
                campi[blocco] = {
                    nome: {
                        **_forma_del_campo(campo),
                        "description": campo.description or "",
                        # Un campo obbligatorio non ha predefinito: null, e non
                        # il sentinella di pydantic, che finirebbe a video come
                        # la stringa "PydanticUndefined" e somiglierebbe a un
                        # valore.
                        "default": (
                            None
                            if campo.is_required()
                            else campo.get_default(call_default_factory=True)
                        ),
                        # Il predefinito da solo non basta a distinguerli: un
                        # campo obbligatorio arriva `null`, ma anche uno
                        # nullabile il cui predefinito e' None (`voxel_size`).
                        # Il pannello richiude i campi rimasti al predefinito e
                        # tiene in vista gli altri: senza questo bit
                        # richiuderebbe un obbligatorio non ancora compilato --
                        # cioe' nasconderebbe l'unico campo che chiede una
                        # risposta.
                        "obbligatorio": campo.is_required(),
                    }
                    for nome, campo in annidato.model_fields.items()
                    if f"{blocco}.{nome}" not in escluse
                }
            # Un blocco senza campi non diventa una sezione vuota: `regioni`
            # e' un `dict` a chiavi libere e non ne puo' avere per costruzione,
            # e una sezione che non puo' mai contenere nulla non ha niente da
            # mostrare.
            campi = {blocco: voci for blocco, voci in campi.items() if voci}
            fuori[str(numero)] = {
                "blocchi": [blocco for blocco in blocchi if blocco in campi],
                "campi": campi,
            }
        # Un predefinito puo' essere un Path, una tupla o un modello annidato:
        # non tutti sono serializzabili in JSON, e il pannello li mostra come
        # testo. default=str li rende senza inventarne il valore.
        return json.loads(json.dumps(fuori, default=str))

    lavoratore = Worker()
    # `flusso()` (/api/events) e' un generatore SINCRONO che gira in un thread
    # del pool anyio: finche' dorme, la connessione SSE resta aperta e uvicorn
    # la aspetta. Questo Event e' l'unica via che ha quel thread per sapere che
    # il server sta chiudendo, e senza il generatore resta appeso dentro
    # Py_Finalize -- uno per connessione, gettoni del pool anyio inclusi.
    spegni = threading.Event()
    # Su `app.state` perche' chi spegne e' fuori di qui: cli.py lo alza insieme
    # a `should_exit`. Dal lifespan soltanto sarebbe troppo tardi -- quel ramo
    # gira DOPO che uvicorn ha finito di aspettare le connessioni, cioe' dopo
    # aver aspettato proprio il thread che questo Event deve svegliare.
    app.state.spegni = spegni

    @asynccontextmanager
    async def _ciclo_vita(app: FastAPI):
        # Uvicorn esegue questo ramo quando `should_exit` diventa vero: vale
        # per finestra, `--app`, Ctrl-C e `--no-browser`, senza toccare
        # cli.py. Senza questo, lo step in corso resta orfano alla chiusura.
        yield
        spegni.set()
        lavoratore.cancel()

    app.router.lifespan_context = _ciclo_vita

    def _avvia(da: int, a: int, endpoint: str) -> dict[str, object]:
        """Deposita, poi avvia. In quest'ordine e sotto lo stesso lucchetto
        dello storico: un'esecuzione senza deposito non si puo' annullare, e
        un deposito che solleva lascia il worker fermo con il motivo in
        risposta."""
        # Senza questa riga, a legame vuoto il Worker lanciava
        # `python -m meshrec.cli run None` e restava occupato: un 200 che non
        # eseguiva niente e bloccava anche la richiesta successiva.
        corrente()
        # La guardia sta PRIMA del deposito: `steps.dimentica(range(0, 1))`
        # farebbe `STEP_KEYS[-1]` e toglierebbe in silenzio la voce del prior,
        # e 13 solleverebbe `IndexError` a versione gia' depositata.
        # Prima del dominio: `/api/step/12/from` chiede il 12 e riceve il tetto
        # a 11, cioe' `a < da`. Il messaggio del dominio direbbe «chiesto 12,
        # fino a 11» a chi ha appena chiesto uno step che esiste, e mentirebbe
        # due volte: sul perche' del rifiuto e su cio' che resta possibile.
        if 1 <= da <= 12 and a < da:
            raise ValueError(
                "«Esegui da qui fino al deck» si ferma all'11: per il prior usa "
                "`meshrec wall` oppure lo step 12 da solo"
            )
        if not (1 <= da <= a <= 12):
            raise ValueError(
                f"lo step va scelto fra 1 e 12 (chiesto {da}"
                + (f", fino a {a}" if a != da else "")
                + ")"
            )
        non_in_sola_lettura(
            f"eseguire lo step {da}" if da == a else f"eseguire dallo step {da} in giù"
        )
        with _LUCCHETTO_STORICO:
            if lavoratore.is_running():
                raise RuntimeError(
                    "uno step sta già girando: annullalo prima di avviarne un altro"
                )
            out_dir = Path(corrente().run.out_dir)
            if not storico.esiste(out_dir):
                storico.deposita(out_dir, config_path.read_text(encoding="utf-8"), "avvio", [])
            _deposita_le_modifiche_fatte_a_mano(out_dir)
            storico.deposita(
                out_dir,
                config_path.read_text(encoding="utf-8"),
                endpoint,
                [],
                scambio=storico.elenco_di_scambio(da, a),
            )
            steps.dimentica(out_dir, range(da, a + 1))
            steps.dimentica(out_dir, range(da, a + 1), nome=pipeline.METRICS_FILENAME)
            lavoratore.start(config_path, da, a)
            _scalda_le_nuvole(out_dir, da, a, corrente().input)
        return {"avviato": da, "fino_a": a}

    # Gli step con una nuvola. Una nuvola disegnata non e' l'artefatto: e' la sua
    # decimazione, che `decimate_file` calcola e tiene su disco per (sorgente,
    # budget, campione, seme, mtime). Rieseguito lo step, l'mtime cambia e la
    # voce vale per la corsa nuova, non per quella di prima.
    _STEP_CON_NUVOLA = (1, 2, 3, 4)

    def _scalda_le_nuvole(out_dir: Path, da: int, a: int, ingresso: InputConfig) -> None:
        """Decima in anticipo le nuvole che la corsa appena avviata riscrivera'.

        La decimazione a cache fredda e' l'unica attesa dell'interfaccia che
        superi la soglia di un gesto. Misurata il 04/09/2026 su una nuvola
        sintetica da 1.505.012 punti: 1,24 s in tutto -- 0,07 di lettura, 0,30
        di spaziatura media, 0,87 dentro `voxel_down_sample_and_trace` di Open3D
        -- contro i 50-130 ms della stessa richiesta a cache calda, e contro i
        30-50 ms di uno step con una mesh, che quella strada non la percorre.
        Sulla scansione di riferimento, quattro volte piu' grande, il conto
        cresce con lei.

        Il costo non si toglie: sta quasi tutto dentro una chiamata C++ di
        Open3D, e non e' nostro da rendere piu' veloce. Si sposta. Chi ha appena
        lanciato uno step sta gia' aspettando -- il piu' lungo misurato dura
        34,39 s -- e un secondo speso li' dentro non lo vede nessuno, mentre lo
        stesso secondo dopo il clic e' l'interfaccia che non risponde.

        Su un thread suo e dopo la fine della corsa, non prima: durante, il
        sottoprocesso ha i propri thread di calcolo e l'artefatto non e' ancora
        scritto. Se qualcosa qui dentro va storto non se ne accorge nessuno, ed
        e' voluto: al peggio il primo clic paga il freddo, cioe' quello che
        pagava comunque prima di questa funzione. Nessun ramo dell'interfaccia
        dipende dal fatto che abbia funzionato.

        La configurazione la riceve per copia e non la rilegge da `corrente()`:
        fra l'avvio e la fine chi guarda puo' aver cambiato un campo, e
        scaldare con parametri che non sono quelli della corsa scriverebbe una
        voce che nessuna richiesta poi ritrova -- lavoro buttato, e per giunta
        silenzioso.
        """
        def lavora() -> None:
            try:
                while lavoratore.is_running():
                    time.sleep(0.2)
                # Fallita o interrotta, gli artefatti a valle non ci sono o non
                # valgono: scaldarli sarebbe decimare la nuvola di prima e
                # tenerla per una corsa che non l'ha prodotta.
                #
                # Il lavoratore e' uno solo e vive oltre la corsa: fra l'uscita
                # dal ciclo e questa riga puo' esserne partita un'altra, e allora
                # qui si legge lo stato SUA. Non e' un buco: `start` rimette
                # `exit_code` a None, e None non e' 0, quindi il caso si chiude
                # da se' rinunciando a scaldare -- che e' anche la cosa giusta,
                # perche' l'artefatto di questa corsa sta per essere riscritto
                # dall'altra. Resta una finestra in cui `decimate_file` legge un
                # file mentre la corsa nuova lo riscrive: l'eccezione la
                # raccoglie il ramo qui sotto, e l'mtime nella chiave impedisce
                # che una lettura a meta' finisca in cache come voce buona.
                # ponytail: nessuna identita' di corsa catturata, si cattura un
                # numero di generazione il giorno che il sintomo si vede.
                if lavoratore.exit_code != 0 or lavoratore.annullato:
                    return
                # Il budget predefinito, che e' l'unico che l'interfaccia
                # chiede: app.js chiama /api/cloud/N senza `max_points`. La
                # rotta pero' accetta anche un budget esplicito, e quello e' una
                # chiave di cache diversa -- mentre `_rimuovi_voci_vecchie`
                # tiene una voce sola per sorgente. Chi chiede un budget suo,
                # cioe' chi sta indagando a mano, paga il freddo e puo' vedersi
                # cancellare la voce da questo thread: e' quello che gli
                # succedeva comunque prima, e non vale una seconda voce per
                # sorgente tenuta in vita per una strada che l'interfaccia non
                # percorre.
                budget = ViewportConfig().max_points
                for numero in _STEP_CON_NUVOLA:
                    if not (da <= numero <= a):
                        continue
                    percorso = out_dir / pipeline.ARTIFACTS[numero]
                    if not percorso.exists():
                        continue
                    viewport.decimate_file(
                        percorso, budget, ingresso.spacing_sample, ingresso.seed, CACHE_DIR
                    )
            except Exception as errore:
                # Nudo apposta: questo thread non ha nessuno a cui riferire e
                # non deve poter rovinare una corsa riuscita. Un artefatto
                # sparito sotto, un disco pieno, una nuvola vuota: tutti casi in
                # cui la cosa giusta e' non scaldare niente e lasciare che il
                # clic paghi il freddo, cioe' quello che pagava comunque.
                # Ma non muto. Un `pass` secco ingoia allo stesso modo un disco
                # pieno e un errore di battitura in questa funzione, e il
                # secondo non si vedrebbe MAI: il meccanismo e' invisibile per
                # costruzione, quindi il suo unico sintomo sarebbe un'attesa
                # che nessuno collega. Su stderr, come `_riporta` in cli.py:
                # chi ha lanciato `meshrec serve` ha quel flusso davanti, e chi
                # non ha problemi non ci legge niente.
                print("scaldacache delle nuvole fallito, il primo clic pagherà "
                      "la decimazione a freddo", file=sys.stderr)
                traceback.print_exception(errore, file=sys.stderr)

        threading.Thread(target=lavora, daemon=True).start()

    def _in_corso() -> JSONResponse | None:
        if not lavoratore.is_running():
            return None
        return JSONResponse(
            status_code=409,
            content={
                "errore": "InCorso",
                "messaggio": "uno step sta girando: aspetta la fine, oppure interrompi il calcolo",
            },
        )

    # Le mappe dell'ultima decimazione servita, per step. Il ritaglio e la
    # selezione le rileggono: senza, agirebbero su indici che non esistono.
    mappe: dict[int, list] = {}

    @app.post("/api/step/{numero}")
    def esegui_step(numero: int) -> dict[str, object]:
        return _avvia(numero, numero, f"POST /api/step/{numero}")

    @app.post("/api/step/{numero}/from")
    def esegui_da(numero: int) -> dict[str, object]:
        # 11, il deck: e' dove si chiude il perimetro del prodotto
        # (PRODUCT.md) e dove finisce una corsa da riga di comando. Il prior
        # (12) resta raggiungibile con `meshrec wall` e con
        # `POST /api/step/12`, ma non parte da un bottone che non lo nomina.
        return _avvia(numero, 11, f"POST /api/step/{numero}/from")

    @app.post("/api/cancel")
    def annulla() -> dict[str, object]:
        return {"annullato": lavoratore.cancel()}

    @app.post("/api/crop")
    def ritaglia(box: BoxRitaglio) -> dict[str, object]:
        """Il box disegnato nel viewport diventa segment.crop_min e crop_max.

        L'interfaccia disegna il box; la pulizia la esegue
        segment.remove_outliers e il ritaglio segment.crop_box, che sono le
        stesse funzioni che la pipeline usa allo step 2 e nello stesso ordine.
        Non c'e' una seconda implementazione da tenere allineata.

        `completo` dice fin dove l'anteprima arriva, e non e' un ornamento: con
        `method: auto` lo step 2 non finisce col ritaglio, prosegue con
        extract_planes e cluster e riscrive points_after col numero del cluster
        scelto (`segment.segment_cloud`, ramo `method == "auto"`). Su una
        nuvola di 5 050 punti sono 5 000
        contro 82. L'anteprima si ferma comunque al ritaglio, e lo dichiara
        invece di affermare il falso: il resto della tratta, misurato su
        runs/lab_crop, costa 57,76 s di extract_planes piu' 26,35 s di cluster,
        e quel costo non e' memorizzabile perche' dipende dal box, cioe' proprio
        dalla cosa che si sta ritoccando. Un pannello in cui ogni ritocco costa
        un minuto e mezzo non e' un'anteprima. La didascalia legge questo campo.

        La configurazione si scrive solo se il ritaglio e' andato a buon fine:
        un box degenere o vuoto solleva prima, e non lascia sul disco estremi
        che nessuno step potrebbe applicare.
        """
        _estremi_finiti(box)
        cfg = corrente()
        cfg.segment.crop_min = box.min
        cfg.segment.crop_max = box.max
        # I due estremi sono accoppiati e SegmentConfig non ha
        # validate_assignment: l'unico punto in cui lo stato risultante viene
        # verificato per intero e' qui, prima che finisca su disco.
        # model_validate e' la stessa che load_config applica in lettura,
        # quindi cio' che si scrive e' per costruzione rileggibile.
        cfg = PipelineConfig.model_validate(cfg.model_dump())
        # L'ingresso dello step 2, non la sua uscita: vedi _ingresso_del_ritaglio.
        sorgente = Path(cfg.run.out_dir) / pipeline.ARTIFACTS[1]
        if not sorgente.exists():
            raise FileNotFoundError(
                f"lo step 1 non ha ancora prodotto {pipeline.ARTIFACTS[1]}: "
                "il ritaglio si misura sulla nuvola letta, che è l'ingresso dello step 2"
            )
        puliti = _ingresso_del_ritaglio(
            sorgente,
            sorgente.stat().st_mtime_ns,
            cfg.segment.outlier_neighbors,
            cfg.segment.outlier_std_ratio,
        )
        _dentro, metriche = segment.crop_box(puliti, cfg.segment)
        non_in_sola_lettura("scrivere il ritaglio")
        # I campi passati a mano: `cfg` viene da corrente() ed e' stato mutato
        # in posto, quindi un confronto dentro scrivi_config troverebbe
        # l'oggetto uguale a se stesso e registrerebbe «nessun campo».
        scrivi_config(cfg, "POST /api/crop", ["segment.crop_min", "segment.crop_max"])
        # Le metriche del core sono l'unica fonte: points_after c'e' gia'
        # dentro (`segment.crop_box`), e riscriverlo qui sarebbe una riga che
        # sembra calcolare qualcosa e non lo fa.
        #
        # `== "crop"` e non `!= "auto"`: il giorno che segment.method prendesse
        # un terzo valore, questo direbbe «incompleta» per prudenza invece di
        # promettere una coincidenza che nessuno ha verificato.
        return {**metriche, "completo": cfg.segment.method == "crop"}

    @app.get("/api/cloud/{numero}")
    def nuvola(numero: int, max_points: int | None = None) -> Response:
        """Punti decimati dello step richiesto, in binario Float32.

        Decima l'artefatto dello step chiesto e non un altro: servire al posto
        della nuvola dello step 2 quella dello step 3, che e' gia' piccola e
        pronta, mostrerebbe una nuvola diversa da quella su cui il ritaglio
        agisce.
        """
        if numero not in pipeline.ARTIFACTS:
            raise ValueError(
                f"lo step {numero} non esiste: gli step con una nuvola sono {sorted(pipeline.ARTIFACTS)}"
            )
        cfg = corrente()
        percorso = Path(cfg.run.out_dir) / pipeline.ARTIFACTS[numero]
        if not percorso.exists():
            raise FileNotFoundError(
                f"lo step {numero} non ha ancora prodotto {pipeline.ARTIFACTS[numero]}"
            )
        if max_points is not None and max_points <= 0:
            raise ValueError(f"max_points={max_points} non valido: atteso un intero positivo")
        budget = max_points if max_points is not None else ViewportConfig().max_points
        # decimate_file calcola la spaziatura al proprio interno, solo a
        # cache fredda: qui non si legge piu' la nuvola ne' si controlla la
        # cache in anticipo, perche' spacing_sample e seed sono gia' nella
        # sua chiave (vedi viewport.decimate_file).
        ridotti, gruppi, voxel = viewport.decimate_file(
            percorso, budget, cfg.input.spacing_sample, cfg.input.seed, CACHE_DIR
        )
        mappe[numero] = gruppi
        return Response(
            content=viewport.to_float32(ridotti),
            media_type="application/octet-stream",
            headers={
                "X-Points-Drawn": str(len(ridotti)),
                "X-Points-Total": str(sum(len(gruppo) for gruppo in gruppi)),
                "X-Voxel": f"{voxel:.6g}",
            },
        )

    @app.post("/api/cluster")
    def scegli_cluster(richiesta: dict[str, int]) -> dict[str, object]:
        """Dal punto disegnato al cluster_index che segment_cloud consuma.

        Il punto cliccato e' un indice della nuvola DISEGNATA (decimata),
        cioe' quella che /api/cloud/2 ha servito al browser: interpretarlo
        come indice della nuvola piena risponderebbe un cluster plausibile
        ma sbagliato, senza sollevare. La mappa che /api/cloud/2 ha salvato
        in `mappe` lo riporta a TUTTI i punti pieni del gruppo di
        decimazione (un voxel puo' contenere punti di piu' cluster): il
        rappresentante e' il cluster in maggioranza fra loro, non il primo
        punto del gruppo (task-11a-review.md misura il difetto del primo
        punto sopra qualche milione di punti).

        Il raggruppamento resta in core.segment.cluster: qui non ce n'e' una
        seconda implementazione da tenere allineata.
        """
        gruppi = mappe.get(2)
        if not gruppi:
            raise ValueError("nessuna nuvola caricata: apri prima lo step 2 nel viewport")
        disegnato = int(richiesta["punto"])
        if not 0 <= disegnato < len(gruppi):
            raise ValueError(f"il punto {disegnato} non appartiene alla nuvola disegnata")
        gruppo = gruppi[disegnato]

        cfg = corrente()
        # I punti pieni per la ricerca delle coordinate (sotto) restano quelli
        # DISEGNATI, cioe' 02_segmented.ply: e' la nuvola che /api/cloud/2 ha
        # servito e su cui gli indici di `gruppo` sono definiti.
        punti, _normali = io.read_cloud(Path(cfg.run.out_dir) / pipeline.ARTIFACTS[2])

        # Ma la CLUSTERIZZAZIONE deve essere quella che la corsa 'auto' esegue
        # davvero (`segment.segment_cloud`), non quella di 02_segmented.ply
        # preso a se': quel file e' l'uscita del metodo 'crop' (nessun piano
        # tolto), mentre la corsa parte sempre dall'ingresso grezzo dello
        # step 2 (ARTIFACTS[1], vedi lo step 2 di `pipeline.run`) per la
        # spaziatura e per
        # remove_outliers -> crop_box -> extract_planes -> cluster, in
        # quest'ordine. Saltare extract_planes clusterizzava un insieme
        # diverso: sul dato vero, 4293 gruppi (il clic, sbagliato) contro
        # 2447 (la corsa, task-11b-allineamento.md). Nessuna cache qui,
        # apposta (vedi il mandato di questo giro): ogni clic ripaga
        # l'intera tratta, come la pagherebbe la corsa.
        sorgente_grezza = Path(cfg.run.out_dir) / pipeline.ARTIFACTS[1]
        if not sorgente_grezza.exists():
            raise FileNotFoundError(
                f"lo step 1 non ha ancora prodotto {pipeline.ARTIFACTS[1]}: "
                "il clic clusterizza a partire dall'ingresso grezzo dello step 2"
            )
        grezzi, _normali_grezze = io.read_cloud(sorgente_grezza)
        spaziatura = io.mean_spacing(grezzi, cfg.input.spacing_sample, cfg.input.seed)
        puliti, _metriche_outlier = segment.remove_outliers(grezzi, cfg.segment)
        ritagliati, _metriche_crop = segment.crop_box(puliti, cfg.segment)
        _piani, residuo, _metriche_piani = segment.extract_planes(ritagliati, cfg.segment, spaziatura)
        insiemi, metriche = segment.cluster(residuo, cfg.segment, spaziatura)

        def cluster_del_punto_pieno(indice_pieno: int) -> int | None:
            coordinata = punti[indice_pieno]
            return next(
                (
                    indice
                    for indice, insieme in enumerate(insiemi)
                    if np.isclose(insieme, coordinata).all(axis=1).any()
                ),
                None,
            )

        # Un gruppo disegnato e' un voxel di decimazione: quando il voxel e'
        # piu' grande del raggio che separa due cluster (nuvole sopra
        # qualche milione di punti, vedi task-11a-review.md), il gruppo puo'
        # contenere punti pieni di piu' cluster. Il primo punto del gruppo e'
        # un rappresentante arbitrario; il rappresentante corretto e' la
        # MAGGIORANZA del gruppo: si vota il cluster (o il rumore, None) di
        # ogni punto pieno e vince chi ha piu' voti.
        #
        # Due casi che la maggioranza da sola non decide, dichiarati qui:
        # - pareggio fra cluster (o fra un cluster e il rumore): vince il
        #   cluster piu' popoloso IN ASSOLUTO. insiemi e' gia' ordinato per
        #   numerosita' decrescente (core.segment.cluster), quindi a parita'
        #   di voti nel gruppo l'indice piu' basso e' la scelta piu'
        #   prudente e deterministica.
        # - il rumore e' in MAGGIORANZA STRETTA (piu' voti di ogni singolo
        #   cluster): il clic e' trattato come rumore e solleva, senza
        #   scrivere. A parita' con il cluster piu' votato vince il cluster:
        #   un pareggio non e' un'evidenza sufficiente per scartare un
        #   match reale.
        voti = Counter(
            v for v in (cluster_del_punto_pieno(int(p)) for p in gruppo) if v is not None
        )
        voti_rumore = len(gruppo) - sum(voti.values())
        scelto, voti_vincitore = max(
            voti.items(), key=lambda kv: (kv[1], -kv[0]), default=(None, 0)
        )
        if scelto is None or voti_rumore > voti_vincitore:
            raise ValueError(
                "il punto cliccato ricade per lo più nel rumore: "
                "DBSCAN non assegna il gruppo a nessun cluster"
            )

        metodo_precedente = cfg.segment.method
        cfg.segment.method = "auto"
        cfg.segment.cluster_index = scelto
        non_in_sola_lettura("scegliere il cluster")
        # Come sopra: `cfg` e' mutato in posto.
        scrivi_config(cfg, "POST /api/cluster", ["segment.method", "segment.cluster_index"])
        return {
            "cluster_index": scelto,
            "cluster_points": int(len(insiemi[scelto])),
            "method_before": metodo_precedente,
            "method_after": cfg.segment.method,
            **metriche,
        }



    @app.get("/api/mesh/{numero}")
    def mesh(numero: int) -> Response:
        """Vertici e facce in un solo corpo binario: prima i Float32 delle
        coordinate, poi gli Uint32 degli indici. I conteggi stanno nelle
        intestazioni, cosi' il browser sa dove tagliare.
        """
        if numero not in pipeline.ARTIFACTS:
            raise ValueError(
                f"lo step {numero} non esiste: gli step con un artefatto sono {sorted(pipeline.ARTIFACTS)}"
            )
        cfg = corrente()
        percorso = Path(cfg.run.out_dir) / pipeline.ARTIFACTS[numero]
        if not percorso.exists():
            raise FileNotFoundError(
                f"lo step {numero} non ha ancora prodotto {pipeline.ARTIFACTS[numero]}"
            )
        if percorso.suffix == ".vtu":
            vertici, facce, _indici = _contorno_del_volume(percorso)
        else:
            import open3d as o3d

            triangolare = o3d.io.read_triangle_mesh(str(percorso))
            vertici = np.asarray(triangolare.vertices)
            facce = np.asarray(triangolare.triangles)
        # Senza triangoli non c'e' nulla da disegnare: 01_cloud.ply letto come
        # mesh da' vertici e zero facce, e risponderebbe 200 con un solido
        # vuoto invece di dire che quell'artefatto e' una nuvola.
        if len(vertici) == 0 or len(facce) == 0:
            raise ValueError(
                f"{percorso.name} non è una mesh disegnabile: "
                f"{len(vertici)} vertici e {len(facce)} triangoli"
            )
        # Le normali viaggiano col corpo invece di essere ricalcolate di la'.
        # `computeVertexNormals` di three.js gira sul thread PRINCIPALE del
        # browser: finche' dura, la pagina intera e' ferma -- non solo la vista,
        # anche i bottoni e la colonna degli step. Misurato nel browser il
        # 04/09/2026 su 908.118 triangoli, il conteggio che l'aiuto dello step 5
        # cita per la scansione di riferimento a `poisson_depth` 9: mediano di
        # sette prove, 1078 ms. Qui lo stesso calcolo, in numpy e sugli stessi
        # 908.118 triangoli, ha un mediano di 64 ms: diciassette volte meno, e
        # su un thread che non e' quello con cui l'utente sta parlando.
        #
        # Il prezzo, misurato e non stimato: il corpo cresce di un terzo -- tre
        # Float32 per vertice in piu' sopra posizioni e indici, 2,58 MB che
        # diventano 3,43 sulla mesh dello step 6 di una corsa da 143.102
        # triangoli -- e la risposta passa da una quarantina di millisecondi a
        # 60-90. Su un socket locale sono i millisecondi piu' economici che
        # questa applicazione possa spendere.
        #
        # `viewport.vertex_normals` non e' una definizione qualsiasi: e' quella
        # di three.js replicata, verso del prodotto vettoriale compreso. Un
        # segno sbagliato non darebbe normali «un po' diverse», ribalterebbe il
        # chiaro e lo scuro del pezzo che finisce in appendice.
        normali = viewport.vertex_normals(vertici, facce)
        corpo = (
            viewport.to_float32(vertici)
            + np.ascontiguousarray(facce, dtype="<u4").tobytes()
            + viewport.to_float32(normali)
        )
        return Response(
            content=corpo,
            media_type="application/octet-stream",
            # X-Normals dichiara che la coda c'e', e il browser ci si aggancia
            # invece di dedurla dalla lunghezza del corpo: dedurla vorrebbe dire
            # che un corpo troncato a meta' si legge come «senza normali» e la
            # pagina disegna un pezzo nero senza dire niente.
            headers={
                "X-Vertices": str(len(vertici)),
                "X-Triangles": str(len(facce)),
                "X-Normals": "1",
            },
        )

    @app.get("/api/scarto")
    def scarto() -> Response:
        """Lo scarto della superficie dalla nuvola, un Float32 per vertice.

        Corrisponde vertice per vertice a `/api/mesh/6`, e la garanzia e' che
        i due gestori leggono lo stesso file invece di accordarsi fra loro.

        **Limite dichiarato**, ed e' quello di `quality.vertex_deviation`:
        campiona i SOLI vertici, nel verso mesh_to_cloud. Dove la superficie
        sbaglia fra un vertice e l'altro questa mappa non lo vede, e non e'
        cloud_to_mesh -- il verso in cui i campioni sono i punti della nuvola e
        il numero e' piu' grande. E' una mappa diagnostica: dice dove guardare,
        non quanto vale la fedelta'. La didascalia lo porta a video, perche'
        l'immagine finisce in appendice staccata da questa docstring.
        """
        cfg = corrente()
        radice = Path(cfg.run.out_dir)
        mesh = radice / pipeline.ARTIFACTS[_SCARTO_MESH]
        nuvola = radice / pipeline.ARTIFACTS[_SCARTO_NUVOLA]
        for percorso, numero in ((mesh, _SCARTO_MESH), (nuvola, _SCARTO_NUVOLA)):
            if not percorso.exists():
                raise FileNotFoundError(
                    f"lo step {numero} non ha ancora prodotto {percorso.name}: lo scarto "
                    "si misura fra la superficie riparata e la nuvola segmentata"
                )
        scarti = _scarto_dei_vertici(
            mesh, mesh.stat().st_mtime_ns, nuvola, nuvola.stat().st_mtime_ns
        )
        # Il massimo viaggia in intestazione e il taglio lo calcola il browser,
        # come per /api/campo: il conteggio dei vertici sopra la soglia esiste
        # in un posto solo, `scalaDelCampo`, e un secondo che lo ricontasse qui
        # potrebbe dire un numero diverso dallo stesso dato.
        #
        # Intestazione VUOTA e non uno zero quando nessun valore e' finito: il
        # browser la legge come «non disponibile», e uno zero li' si leggerebbe
        # «scarto nullo», cioe' una ricostruzione perfetta.
        finiti = scarti[np.isfinite(scarti)]
        return Response(
            content=viewport.to_float32(scarti),
            media_type="application/octet-stream",
            headers={"X-Max": str(float(finiti.max())) if len(finiti) else ""},
        )


    @app.get("/api/events")
    def eventi(max_eventi: int | None = None) -> StreamingResponse:
        """Avanzamento e log verso il browser. Una direzione sola, quindi SSE:
        WebSocket aggiungerebbe un secondo protocollo per traffico che va da
        una parte sola, e EventSource riconnette da solo."""

        def flusso():
            inviate = 0
            emesse = 0
            avvio_visto = None
            while True:
                # Nessuna corsa aperta non e' un errore qui, ed e' lo stato in
                # cui la schermata d'ingresso vive: il browser apre
                # l'EventSource al caricamento del modulo, sempre. Sollevare
                # dentro il generatore non produce nemmeno un 400 -- le
                # intestazioni sono gia' partite, e il gestore generico non le
                # puo' piu' toccare: il browser riceveva 200 con corpo vuoto e
                # riconnetteva ogni tre secondi, con una traccia per giro.
                cfg = corrente() if config_path is not None else None
                stato = {
                    "legata": cfg is not None,
                    "in_corso": lavoratore.is_running(),
                    "step": lavoratore.step,
                    "a_step": lavoratore.a_step,
                    "exit_code": lavoratore.exit_code,
                    "annullato": lavoratore.annullato,
                    "da_secondi": lavoratore.da_secondi(),
                    "durata_secondi": lavoratore.durata,
                    "steps": steps.run_state(cfg.run.out_dir, cfg) if cfg else [],
                }
                yield f"event: stato\ndata: {json.dumps(stato, default=str)}\n\n"
                emesse += 1
                # `avvii` (worker.py) e' l'identita' della corsa, letto PRIMA
                # di righe(): due corse ravvicinate nello stesso poll possono
                # lasciare la corsa nuova con lo stesso numero di righe della
                # vecchia (o di piu'), e la sola guardia sul conteggio non se
                # ne accorgeva -- la prima riga della corsa nuova cadeva nel
                # taglio, proprio quella che il pannello dell'esito legge
                # quando la corsa fallisce subito. Se una corsa parte fra
                # queste due letture, righe() e' gia' quella nuova (svuotata
                # e ripopolata) e questo giro puo' rimandare righe gia' viste;
                # il giro dopo `avvii` risulta cambiato e il taglio riparte da
                # zero. Ripetute sono accettabili, perse no.
                avvio_ora = lavoratore.avvii
                righe = lavoratore.righe()
                if avvio_ora != avvio_visto:
                    avvio_visto = avvio_ora
                    inviate = 0
                elif len(righe) < inviate:
                    # Cintura: l'identita' e' quella vera; questo resta come
                    # rete di sicurezza se `avvii` non si muove per un caso
                    # non previsto.
                    inviate = 0
                for riga in righe[inviate:]:
                    yield f"event: riga\ndata: {json.dumps(riga)}\n\n"
                inviate = len(righe)
                if max_eventi is not None and emesse >= max_eventi:
                    return
                # Non `time.sleep`: un `sleep` non si accorge dello spegnimento
                # e tiene la connessione (quindi il server) in piedi.
                if spegni.wait(0.5):
                    return

        return StreamingResponse(flusso(), media_type="text/event-stream")

    return app
