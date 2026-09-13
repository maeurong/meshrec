"""Sequenza degli step. E' l'unico modulo che conosce l'ordine.

Ogni step scrive il proprio artefatto numerato: la ripresa con `from_step`
ricarica l'artefatto precedente invece di rifare il lavoro.
"""

from __future__ import annotations

import json
import time
from collections.abc import Callable
from pathlib import Path

import numpy as np

from meshrec.core import (
    abaqus,
    attribuzione,
    io,
    quality,
    repair,
    segment,
    steps,
    surface,
    volume,
    wall,
)
from meshrec.core.config import PipelineConfig, save_config

METRICS_FILENAME = "metrics.json"
METRICS_PARTIAL = "metrics.partial.json"
WALL_FILENAME = "12_wall.json"
# Il deck di calcolo dello step 11: il file che si importa in Abaqus o si da' a
# CalculiX. Una costante perche' da
# adesso lo nomina anche il server, che lo consegna a chi lo chiede
# (`/api/deck`): scritto due volte, il giorno che cambia ne cambia una sola.
DECK_FILENAME = "wall_model.inp"
# Il maglio dello stesso step in forma leggibile da ParaView. Costante per lo
# stesso motivo del deck: lo nomina anche lo scambio dello storico, che lo
# sposta insieme al deck perche' lo scrive la stessa chiamata.
WALL_VTU_FILENAME = "wall_model.vtu"


class _FermataRichiesta(Exception):
    """Uscita normale quando to_step e' raggiunto: non e' un errore.

    Serve perche' le guardie degli step hanno rami else di ripresa, che
    ricaricano artefatti a monte: spegnerle con una condizione su to_step
    farebbe scattare proprio quei rami sugli step che non si devono toccare.
    Interrompere il flusso e' l'unico modo che non tocca le guardie.
    """

ARTIFACTS: dict[int, str] = {
    1: "01_cloud.ply",
    2: "02_segmented.ply",
    3: "03_downsampled.ply",
    4: "04_normals.ply",
    5: "05_surface.ply",
    6: "06_repaired.ply",
    8: "08_simplified.ply",
    9: "09_volume.vtu",
}

# Tabelle esplicite da from_step all'artefatto da ricaricare, verificate a mano
# per ogni from_step da 2 a 12 (non solo il caso 1). Sostituiscono un calcolo
# con ARTIFACTS[min(from_step - 1, N)] che era sbagliato in due punti:
# - per from_step=8 chiedeva ARTIFACTS[7], che non esiste (KeyError);
# - per from_step=4..7 la nuvola di riferimento per l'errore geometrico dello
#   step 7 finiva per essere quella ridotta o normale, non quella segmentata.
# Una tabella e' piu facile da controllare a colpo d'occhio di un'espressione.

# Nuvola da ricaricare come ingresso dello step che riparte (usata anche solo
# per stimare la spaziatura quando lo step stesso legge il proprio artefatto).
# Le chiavi da 5 in poi valgono SOLO quando la corsa arriva al prior dello step
# 12, l'unico consumatore della nuvola a valle dello step 4: la guardia sta in
# `run()`, che senza di essa pretendeva 04_normals.ply per eseguire il solo
# step 10 o il solo step 11, che la nuvola non la toccano.
_RESUME_POINTS: dict[int, int] = {
    2: 1, 3: 2, 4: 3, 5: 4, 6: 4, 7: 4, 8: 4, 9: 4, 10: 4, 11: 4, 12: 4
}

# Mesh (vertici/facce) da ricaricare come ingresso dello step che riparte.
# Lo step 7 non scrive un proprio artefatto (produce solo metriche), quindi
# from_step=8 riparte anch'esso dalla superficie riparata dello step 6.
# from_step da 9 in poi non e' qui: l'artefatto giusto dipende da
# cfg.simplify.enabled (vedi run()), perche' lo step 8 scrive
# 08_simplified.ply solo se abilitato. Vale per il 9 che la genera e per gli
# step di valle che la rileggono -- lo step 11 ne ha bisogno perche' e' la
# superficie, non i nodi del volume, a definire il sistema di riferimento del
# modello (abaqus.align_to_axes).
_RESUME_MESH: dict[int, int] = {6: 5, 7: 6, 8: 6}


def _write_mesh(path: Path, vertices: np.ndarray, faces: np.ndarray) -> None:
    import open3d as o3d

    mesh = o3d.geometry.TriangleMesh(
        o3d.utility.Vector3dVector(np.asarray(vertices, dtype=np.float64)),
        o3d.utility.Vector3iVector(np.asarray(faces, dtype=np.int32)),
    )

    def scrivi(destinazione: Path) -> None:
        with io.percorso_open3d(destinazione, scrittura=True) as nativo:
            o3d.io.write_triangle_mesh(nativo, mesh)

    io.scrivi_atomico(path, scrivi)


def _read_mesh(path: Path) -> tuple[np.ndarray, np.ndarray]:
    import open3d as o3d

    with io.percorso_open3d(path) as nativo:
        mesh = o3d.io.read_triangle_mesh(nativo)
    vertices = np.ascontiguousarray(np.asarray(mesh.vertices), dtype=np.float64)
    faces = np.ascontiguousarray(np.asarray(mesh.triangles), dtype=np.int64)
    # open3d NON solleva su file assente: scrive un avviso su stderr e torna una
    # mesh vuota (misurato il 24/08/2026: "Read PLY failed: unable to open
    # file", zero vertici, nessuna eccezione). Senza questa guardia uno step
    # ripreso a monte inesistente girava su zero vertici, scriveva un artefatto
    # vuoto e lo registrava "riuscito": un successo falso, che e' peggio di un
    # errore perche' nessuno lo va a cercare. Simmetrica a io.read_cloud, che
    # la guardia ce l'ha gia'.
    #
    # Anche zero facce e non solo zero vertici: un .ply di soli punti si apre
    # senza errore e passerebbe la prima meta' del controllo, per poi far
    # girare la riparazione su una superficie che facce non ne ha.
    if len(vertices) == 0 or len(faces) == 0:
        # Non «file assente»: i due soli chiamanti passano da
        # `_ingresso_di_ripresa`, che il file inesistente lo intercetta prima
        # con un messaggio suo. Qui il file c'e' sempre, e dirlo assente
        # contraddirebbe la frase che lo avvolge.
        raise ValueError(
            f"nessuna superficie letta da '{path}': vuota o di formato non riconosciuto"
        )
    return vertices, faces


def _ingresso_di_ripresa(
    chiede: int, da: int, out: Path, leggi: Callable[[Path], tuple[np.ndarray, np.ndarray]]
) -> tuple[np.ndarray, np.ndarray]:
    """Ricarica l'artefatto dello step `da` come ingresso dello step `chiede`.

    Esiste per il messaggio, non per la lettura: `read_cloud` e `_read_mesh`
    nominano il FILE che manca, e chi guarda l'interfaccia ragiona per STEP.
    "nessun punto letto da '04_normals.ply'" non dice a nessuno che deve
    eseguire lo step 4 prima del 5.

    La sequenza resta consigliata e non imposta: qui si rifiuta e si dice cosa
    manca, mentre i bottoni dell'interfaccia restano cliccabili sempre.

    File assente e file illeggibile sono due messaggi diversi apposta. Dire
    "lo step 4 non ha ancora scritto" davanti a un artefatto che esiste ma e'
    troncato manderebbe a rieseguire uno step che e' gia' stato eseguito,
    senza spiegare perche' la prima volta non e' bastata.

    Il ramo «esiste ma non si legge» cattura `Exception` e non un elenco di
    tipi. L'elenco c'era -- `(ValueError, OSError)` -- e lasciava passare tutto
    il resto: un `09_volume.vtu` con zero celle fa alzare a `meshio.read` un
    `IndexError` suo, prima che `_maglio_di_volume` veda un solo array, e
    quell'errore risaliva nudo fino al pannello, che rispondeva 500 senza
    nominare ne' il file ne' lo step da rifare. I lettori sono tre
    (`io.read_cloud`, `_read_mesh`, `_maglio_di_volume`) e si appoggiano a tre
    librerie diverse: prevedere che cosa alza ciascuna e' una lista che
    invecchia a ogni aggiornamento, mentre la domanda a cui questa funzione
    risponde e' una sola e non cambia. L'errore originale resta nel messaggio e
    in `__cause__`, quindi non si perde niente nel tradurlo.
    """
    percorso = out / ARTIFACTS[da]
    if not percorso.exists():
        raise ValueError(
            f"lo step {chiede} pretende {ARTIFACTS[da]}, che lo step {da} non ha ancora "
            f"scritto. Esegui prima lo step {da}, oppure «Esegui da qui fino al deck» "
            f"dallo step {da}"
        )
    try:
        return leggi(percorso)
    except Exception as errore:
        raise ValueError(
            f"lo step {chiede} pretende {ARTIFACTS[da]}, che esiste ma non si legge "
            f"({errore}). Riesegui lo step {da}"
        ) from errore


def calcola_prior(
    out: Path, cfg: PipelineConfig, points: np.ndarray, spacing: float
) -> dict[str, object]:
    """Step 12: il prior geometrico, calcolato e scritto accanto agli altri artefatti.

    Sta in una funzione propria e non dentro `run()` perche' ha due chiamanti:
    la corsa intera e il comando `meshrec wall`, che ricalcola il solo prior
    sugli artefatti gia' presenti. Una seconda copia del calcolo sarebbe una
    seconda cosa da tenere allineata.
    """
    esito = wall.prior(points, cfg.segment, cfg.wall, spacing)
    io.scrivi_atomico(
        out / WALL_FILENAME,
        lambda destinazione: destinazione.write_text(
            json.dumps(esito, indent=2, default=float, ensure_ascii=False), encoding="utf-8"
        ),
    )
    return esito


MODEL_FILENAME = "modello.json"
MODEL_STEP_FILENAME = "modello.step"


def _ricostruisci_membrature(prior: dict[str, object]) -> list:
    """Le `Membratura` del prior, per costruire un modello parametrico.

    Quindici dei diciotto campi sono presi 1:1 dal dizionario per membratura che
    `wall.prior` scrive. Gli altri tre stanno annidati sotto
    `voce["riempimento"]`, il dizionario che `wall.riempimento` scrive: e' da
    li' che viene `riempimento_stato`, il campo su cui poggia la guardia del
    Ruling J in `hexa.costruisci`, che rifiuta di costruire un modello da una
    sezione dichiarata «vuota». Estratta come funzione propria perche' e'
    l'unico punto di questa mappatura, ed e' testabile da sola.

    `sezioni_fette`, `quote_fette` e `base_sezione` si leggono con `.get`
    perche' un prior scritto prima che quelle misure esistessero non le porta,
    e assente vuol dire assente: il predefinito vuoto e' cio' che impedisce a
    `wall.giunzioni` di dedurre un'invasione su un piano che non c'e'. Ma su un
    prior **nuovo** vanno rilette, o i tre campi verrebbero scritti in
    `12_wall.json` e buttati alla rilettura: l'attribuzione, che passa di
    qui, troverebbe `base_sezione` vuota su dati freschi,
    e `wall.giunzioni` gli renderebbe `[]` in silenzio.
    """
    from meshrec.core.wall import Membratura

    return [
        Membratura(
            punti=np.arange(0),
            asse=np.asarray(voce["asse"], dtype=np.float64),
            origine=np.asarray(voce["origine"], dtype=np.float64),
            lunghezza=float(voce["lunghezza"]),
            sezione=tuple(voce["sezione"]),
            sezione_dispersione=tuple(voce["sezione_dispersione"]),
            contorno=np.asarray(voce["contorno"], dtype=np.float64),
            fuori_piombo_deg=float(voce["fuori_piombo_deg"]),
            asse_ideale=np.asarray(voce["asse_ideale"], dtype=np.float64),
            scarto_asse_deg=float(voce["scarto_asse_deg"]),
            rigonfiamento=np.zeros(0),
            volume=float(voce["volume"]),
            riempimento_sezione=float(voce["riempimento"]["valore"]),
            riempimento_stato=str(voce["riempimento"]["stato"]),
            densita_dispersione=float(voce["riempimento"]["densita_dispersione"]),
            sezioni_fette=np.asarray(
                voce.get("sezioni_fette", []), dtype=np.float64
            ).reshape(-1, 2),
            quote_fette=np.asarray(voce.get("quote_fette", []), dtype=np.float64),
            base_sezione=np.asarray(voce.get("base_sezione", []), dtype=np.float64).reshape(-1, 3),
        )
        for voce in prior["membrature"]
    ]


def _membrature_del_prior(percorso: Path, chi: str) -> list:
    """Le membrature di `12_wall.json`, rilette da chi non le puo' calcolare.

    Due chiamanti, e lo stesso mestiere: il modello parametrico, che si
    costruisce sulle membrature misurate, e lo step 11 quando la
    configurazione dichiara delle regioni -- `RegioneConfig.membratura` cita
    per costruzione gli indici di questo file, e allo step 11 le membrature
    non esistono ancora.

    Rileggere il prior allo step 11 non e' leggere il futuro: il prior misura
    la **nuvola segmentata**, che e' l'artefatto dello step 2, e non dipende
    dal maglio di volume. Chi arriva qui senza prior deve rifare lo step 12,
    oppure il solo prior col comando `meshrec wall`: il messaggio nomina
    entrambi, come gia' fa il comando `wall` quando manca la nuvola segmentata.

    `chi` e' il soggetto della frase del rifiuto -- l'unica cosa che cambia fra
    i due chiamanti, e la sola ragione per cui questa non e' una funzione senza
    argomenti.

    Le due porte sono quelle di `_ingresso_di_ripresa`: l'assente e il
    troncato dicono cose diverse, perche' «esegui lo step 12» davanti a un
    file che esiste ma non si legge manderebbe a rieseguire uno step che e'
    gia' stato eseguito.
    """
    prior = _prior_letto(percorso, chi)
    try:
        return _ricostruisci_membrature(prior)
    except (ValueError, KeyError, TypeError) as errore:
        raise ValueError(
            f"{percorso} esiste ma non si legge come prior ({errore}): "
            "riesegui lo step 12, o il comando `meshrec wall`"
        ) from errore


def _prior_letto(percorso: Path, chi: str) -> dict[str, object]:
    """Il `12_wall.json` come sta sul disco, per chi lo consuma tal quale.

    `_membrature_del_prior` lo traduce in `Membratura`. Era separata perche'
    un secondo lettore (`core/telaio.py`, uscito con la mappa #161) leggeva il
    dizionario grezzo con le stesse due porte del rifiuto -- l'assente e il
    troncato. Oggi ha un chiamante solo; resta separata perche' le porte del
    rifiuto stanno in un posto.
    """
    if not percorso.exists():
        raise FileNotFoundError(
            f"manca {percorso}: {chi} si costruisce sul prior, e il prior è lo "
            "step 12. Esegui `meshrec wall` sulla stessa configurazione e riprova"
        )
    try:
        with percorso.open(encoding="utf-8") as handle:
            return json.load(handle)
    except (OSError, ValueError) as errore:
        raise ValueError(
            f"{percorso} esiste ma non si legge come prior ({errore}): "
            "riesegui lo step 12, o il comando `meshrec wall`"
        ) from errore


def genera_modello(cfg: PipelineConfig, tipo: str, out_dir: Path) -> dict[str, object]:
    """Genera un modello parametrico come corsa figlia, nella propria cartella.

    I due modelli parametrici sono **generatori di mesh di volume alternativi a
    TetGen**: producono nodi ed elementi e rientrano negli step esistenti di
    metriche di volume ed esportazione. Non sono rami di `run()`, e la ragione
    e' che biforcarla raddoppierebbe la complessita' della funzione piu'
    delicata del progetto senza risparmiare nulla.

    La cartella figlia porta la stessa `config.yaml` della madre -- e' lo
    stesso esperimento, e la stessa impronta -- piu' un `modello.json` che dice
    di quale tipo e' e da quale corsa viene. La provenienza sta li' e non nella
    configurazione, perche' la scelta del modello e' un'azione e non un
    parametro di elaborazione.
    """
    from meshrec.core import hexa

    sorgente = Path(cfg.run.out_dir)
    membrature = _membrature_del_prior(
        sorgente / WALL_FILENAME, "un modello parametrico"
    )

    out = Path(out_dir)

    # save_config solo dopo costruisci: se la generazione fallisce (sulla
    # nuvola vera fallisce, perche' il prior non accetta membrature), la
    # cartella figlia non deve nascere con dentro il solo config.yaml --
    # /api/compare la troverebbe (e' una directory) e la rifiuterebbe senza
    # ne' modello ne' corsa madre da leggere (vedi report.confronta).
    modello = hexa.costruisci(membrature, tipo, cfg.model)
    nodi = modello["nodi"]
    elementi = modello["elementi"]

    out.mkdir(parents=True, exist_ok=True)
    save_config(cfg, out / "config.yaml")

    # Prima del deck, non dopo: se `scrivi_step` solleva a deck gia' scritto, la
    # figlia resta con `config.yaml` + deck + vtu e senza `modello.json`, e
    # `report.confronta` la legge come «as-built» in silenzio; col solo
    # `config.yaml` la rifiuta a voce alta. I prismi sono quelli NON tagliati --
    # la fusione toglie da se' la doppia contabilita' alle giunzioni. E' una
    # seconda uscita: la mesh esaedrica e il suo deck non cambiano (spec
    # 2026-09-07, ADR STEP dal prior geometrico).
    step = hexa.scrivi_step(
        [hexa.prisma_di(membratura, tipo) for membratura in membrature],
        out / MODEL_STEP_FILENAME,
    )

    export = abaqus.export_model(
        out / DECK_FILENAME,
        out / WALL_VTU_FILENAME,
        nodi,
        elementi,
        cfg.export,
        cfg.tet,
        reference=nodi,
        element_type=cfg.model.element,
        element_surfaces=modello["superfici"],
        ties=modello["ties"],
    )

    # Lo scostamento dalla nuvola sorgente e' il perno del confronto (Task 12):
    # e' definito allo stesso modo per i tre modelli. Si misura qui, dove la
    # nuvola segmentata della madre e i nodi del modello sono entrambi a
    # portata; il confronto non ricalcola nulla.
    sorgente_nuvola, _ = io.read_cloud(sorgente / ARTIFACTS[2])
    scarti = quality.vertex_deviation(nodi, sorgente_nuvola)

    esito: dict[str, object] = {
        "tipo": tipo,
        "sorgente": str(sorgente),
        "modello": modello["metriche"],
        "blocchi": modello["blocchi"],
        "hexa": quality.hexa_metrics(nodi, elementi),
        "export": export,
        "step": step,
        "scostamento_nuvola": {
            "rms": float(np.sqrt(np.mean(scarti ** 2))),
            "max": float(scarti.max()),
            "nota": "distanza punto-nuvola nei soli nodi: sottostima dove gli "
                    "elementi sono grandi, come dichiara quality.vertex_deviation",
        },
        "nota_giunzioni": (
            "*TIE fra superfici a contatto: le mesh di membrature adiacenti "
            "non combaciano nodo a nodo. E' una differenza fra i modelli che "
            "non deriva dalla geometria -- as-built monolitico, parametrici "
            "vincolati alle giunzioni -- e va letta accanto al confronto"
        ),
        "nota_armatura": (
            "modello a calcestruzzo omogeneo: l'armatura è fuori ambito per "
            "decisione dell'autore, non per dimenticanza, e il dato resta nel "
            "disegno. Un telaio in cemento armato modellato senza armatura non "
            "è il telaio vero"
        ),
    }
    io.scrivi_atomico(
        out / MODEL_FILENAME,
        lambda destinazione: destinazione.write_text(
            json.dumps(esito, indent=2, default=float, ensure_ascii=False), encoding="utf-8"
        ),
    )
    return esito




def _maglio_di_volume(percorso: Path) -> tuple[np.ndarray, np.ndarray]:
    """Nodi e celle del maglio dello step 9, riletti dal proprio artefatto.

    Il blocco si prende per unicita' e non per nome. Il nome sarebbe quello di
    meshio ('tetra10'), mentre `metrics["11_export"]["element_type"]` porta
    quello di Abaqus ('C3D10'): sono due vocabolari per la stessa cosa, e
    cercare l'uno con l'altro non trova niente. `abaqus.write_vtu` scrive un
    solo blocco, quindi «l'unico» e' una chiave che non ha bisogno di
    traduzione. Un file che di blocchi ne porta un numero diverso da uno si
    dichiara qui e diventa il ramo «esiste ma non si legge» di
    `_ingresso_di_ripresa`, che e' il chiamante.

    L'unicita' del blocco pero' non dice niente sul numero di colonne, e da
    sola non basta: un file con un solo blocco di `triangle` passava per maglio
    di volume (misurato il 31/08/2026: nodi `(6, 3)`, celle `(2, 3)`) e la
    corsa moriva piu' in la', dentro `quality.volume_metrics`, con un
    `IndexError` sulla quarta colonna che non c'e'. Il controllo di forma sta
    qui e non presso i consumatori perche' i consumatori sono due -- le
    metriche dello step 10 e l'esportazione dello step 11 -- e passano tutti
    e due di qui.

    E' lo stesso controllo che `server._contorno_del_volume` fa da sempre sul
    proprio ingresso, con una differenza voluta: li' le dieci colonne del
    tetraedro quadratico si tagliano a quattro, perche' la topologia sta nei
    vertici e i nodi di lato non definiscono ne' facce ne' adiacenze; qui il
    maglio si restituisce intero, perche' il deck di Abaqus quei nodi li vuole
    tutti.
    """
    import meshio

    griglia = meshio.read(percorso)
    tipi = sorted(griglia.cells_dict)
    if len(tipi) != 1:
        raise ValueError(
            f"porta {len(tipi)} blocchi di celle ({tipi}) invece del solo maglio di "
            "volume che lo step 9 scrive"
        )
    celle = np.ascontiguousarray(griglia.cells_dict[tipi[0]])
    if celle.shape[1] not in (4, 10):
        raise ValueError(
            f"non porta tetraedri: il blocco {tipi} ha {celle.shape[1]} nodi per "
            "cella, invece dei 4 di un tetraedro lineare o dei 10 di uno quadratico"
        )
    return np.ascontiguousarray(griglia.points, dtype=np.float64), celle


def _unisci_metriche(out: Path, misure: dict[str, object]) -> dict[str, object]:
    """Fonde `misure` con il `metrics.json` gia' sul disco e riscrive il file.

    L'interfaccia esegue uno step per volta: se ognuno sostituisse
    `metrics.json`, il pannello delle metriche perderebbe tutto cio' che sta a
    monte dello step aperto.
    """
    precedenti: dict[str, object] = {}
    if (out / METRICS_FILENAME).exists():
        try:
            with (out / METRICS_FILENAME).open(encoding="utf-8") as handle:
                letto = json.load(handle)
            precedenti = letto if isinstance(letto, dict) else {}
        except (OSError, ValueError):
            # Un metrics.json illeggibile non fa fallire una corsa riuscita:
            # si riparte da quello che questa corsa ha misurato.
            #
            # ValueError e non json.JSONDecodeError, che ne e' una sottoclasse e
            # lascia scoperto UnicodeDecodeError -- sollevato dalla lettura del
            # file, prima del parse, su un byte non UTF-8. Qui la guardia esiste
            # proprio perche' una corsa RIUSCITA non deve fallire sulla
            # rilettura di cio' che c'era prima, e scritta stretta faceva
            # esattamente quello che era li' a impedire.
            precedenti = {}
    unite = dict(sorted({**precedenti, **misure}.items()))
    io.scrivi_atomico(
        out / METRICS_FILENAME,
        lambda destinazione: destinazione.write_text(
            json.dumps(unite, indent=2, default=float, ensure_ascii=False), encoding="utf-8"
        ),
    )
    return unite


def _con_le_misure_della_superficie(
    step_metrics: dict[str, object], vertices: np.ndarray, faces: np.ndarray
) -> dict[str, object]:
    """Le misure di `surface_metrics` che lo step non ha gia' scritto.

    Il pannello del modello descrive il fronte, e il fronte puo' fermarsi a
    uno qualunque degli step che scrivono una superficie: senza queste chiavi
    un fronte al 5 non saprebbe dire «aperta». Le chiavi proprie dello step
    vincono: `watertight_after` del 6 resta com'e'.

    Misurato il 03/09/2026 su muro_generato (`runs/muro-prova`, tre ripetizioni,
    `time.perf_counter`): a 221368 triangoli (05_surface) `surface_metrics`
    costa 377 ms contro 2,52 s dello step (15%); a 233930 triangoli
    (06_repaired) 406 ms contro 2,99 s (14%). Non nullo, ma un ordine di
    grandezza sotto lo step che lo chiama.
    """
    if len(faces) == 0:
        return step_metrics
    return {**quality.surface_metrics(vertices, faces), **step_metrics}


def run(cfg: PipelineConfig) -> dict[str, object]:
    """Esegue la pipeline e restituisce le metriche di ogni step.

    Dalla Fase 4 gli step di elaborazione sono dodici. Il dodicesimo e' il
    prior geometrico e chiude la corsa madre; non e' un punto di ripresa e non
    e' un ramo: i due modelli parametrici sono corse figlie con la propria
    cartella, non biforcazioni di questa funzione.

    Lo step 12, il prior geometrico, NON e' parte del nucleo che questa
    funzione esegue per difetto: `RunConfig.to_step` e' predefinito a 11, il
    deck, perche' li' si chiude il perimetro del prodotto (PRODUCT.md). Chi lo
    chiede esplicitamente lo ottiene -- il tetto e' 12 -- ma nessuna corsa di
    pipeline lo paga senza averlo chiesto: chi elabora molti candidati (lo
    sweep) non deve pagarlo per ciascuno, e per questo `sweep.run_candidate`
    chiede `--to-step 11` esplicito al sottoprocesso invece di ereditare questo
    predefinito (vedi
    `sweep.py`, che per la stessa ragione non lo richiede in `REQUIRED_STEPS`).

    `cfg.run.from_step` salta gli step precedenti e ricarica dal disco
    l'artefatto numerato che precede quello di ripartenza, secondo le tabelle
    `_RESUME_POINTS` e `_RESUME_MESH`. La ripresa si fida dell'operatore su un
    punto solo: non verifica che quegli artefatti siano stati prodotti con la
    configurazione corrente. Che esistano invece lo verifica, e se mancano
    solleva `ValueError` nominando lo step da eseguire prima
    (`_ingresso_di_ripresa`). Unica eccezione governata da `cfg`
    invece che dalla tabella: `from_step=9` ricarica `08_simplified.ply` se
    `cfg.simplify.enabled` e' vero, altrimenti `06_repaired.ply`, perche' lo
    step 8 scrive il proprio artefatto solo quando la semplificazione e'
    abilitata (predefinito: disabilitata). Se l'operatore riparte da 9 con
    `simplify.enabled=True` ma la corsa precedente non aveva scritto
    `08_simplified.ply` (per esempio perche' era disabilitata in quella
    corsa), la ripresa solleva `ValueError` invece di indovinare.

    La ripresa arriva fino allo step 12 (prior geometrico): `RunConfig.from_step`
    e' vincolato a 12 (vedi `config.py`). Solo lo step 9 ha una guardia
    `if start <= 9`, e riprendendo da piu' in la' rilegge il maglio da
    `09_volume.vtu` invece di ritetraedrizzare. Gli step 10, 11 e 12 non hanno
    guardia: sono metriche di volume, esportazione del deck e prior geometrico,
    tutti senza lavoro costoso da saltare, e vengono rieseguiti a ogni corsa che
    li comprende.

    Ogni ricarica e' condizionata al fatto che gli step compresi in questa corsa
    consumino davvero quell'artefatto, e la condizione guarda `to_step` oltre a
    `from_step`. Ricaricare cio' che non serve non e' costo sprecato: e' un
    RIFIUTO in una cartella incompleta, cioe' proprio nel caso per cui la
    ripresa esiste. La nuvola serve fino allo step 4 e poi al solo prior dello
    step 12; la superficie fino allo step 9 e poi alla sola esportazione dello
    step 11; la nuvola segmentata al solo errore geometrico dello step 7 e al
    solo prior dello step 12. «Esegui solo lo step 10» in una cartella che porta
    il solo 09_volume.vtu percio' esegue, e non pretende niente altro.
    """
    out = Path(cfg.run.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    save_config(cfg, out / "config.yaml")
    io.scarta_temporanei(out)
    impronte = steps.step_fingerprints(cfg)
    metrics: dict[str, object] = {}
    start = cfg.run.from_step
    stop = cfg.run.to_step
    # Lo step su cui il lavoro e' fermo in questo istante: serve al ramo di
    # fallimento, che deve dire quale step si e' rotto e non che la corsa
    # e' finita male in un punto imprecisato.
    in_corso = start
    # Vero solo se il flusso ha attraversato per intero il nucleo di
    # elaborazione geometrica che questa versione di run() esegue (oggi
    # 11_export, il deck): si aggiorna da solo spostandosi con la riga che lo
    # mette a True, senza un numero da tenere sincronizzato a mano con
    # cfg.run.to_step altrove. La riga si e' spostata con il perimetro del
    # prodotto, che chiude sul deck: lasciata dov'era, dopo lo step 12, ogni
    # corsa predefinita sarebbe caduta nel ramo di fusione e avrebbe conservato
    # in metrics.json un 12_wall misurato su un'altra geometria. Lo step 12 e'
    # un'azione in piu' che non ridefinisce questa completezza: una corsa
    # fermata a 11 (il predefinito, e lo sweep che lo chiede esplicito) e una
    # fermata a 12 sono ugualmente complete per questo flag -- la differenza
    # fra le due e' che cosa hanno in piu' del deck.
    pipeline_completa = False

    def registra(numero: int, avvio: float, artefatto: str | None) -> None:
        steps.write_state(
            out, numero, impronte[numero], "riuscito", artefatto, time.monotonic() - avvio
        )

    try:
        if start <= 1:
            in_corso = 1
            avvio = time.monotonic()
            points, step_metrics = io.load_cloud(cfg.input)
            metrics["01_load"] = step_metrics
            io.write_cloud(out / ARTIFACTS[1], points)
            registra(1, avvio, ARTIFACTS[1])
            if stop <= 1:
                raise _FermataRichiesta
        elif start <= 4 or stop >= 12:
            # La nuvola ha consumatori fino allo step 4 -- segmentazione,
            # rarefazione, normali -- e poi uno solo: la spaziatura che il
            # prior dello step 12 passa a `wall.prior`. Gli step da 5 a 11
            # leggono superficie e maglio, non la nuvola, e caricarla lo stesso
            # non era costo sprecato ma un RIFIUTO in una cartella incompleta:
            # «esegui solo lo step 10» si fermava su 04_normals.ply, un file
            # che quello step non guarda mai -- ed e' proprio il caso che il
            # tetto di from_step a 12 esiste per servire.
            #
            # Stessa guardia e stessa ragione della nuvola segmentata piu'
            # sotto, e come li' `chiede` nomina lo step che la CONSUMA, non
            # quello da cui la corsa riparte: «lo step 10 pretende
            # 04_normals.ply, esegui da qui in giu' dallo step 4» consigliava
            # di riscrivere gli artefatti dal 4 al 10, cioe' proprio quelli su
            # cui si stava iterando.
            points, _ = _ingresso_di_ripresa(
                start if start <= 4 else 12, _RESUME_POINTS[start], out, io.read_cloud
            )

        # Stessa condizione del caricamento qui sopra (`start <= 1` la implica):
        # senza nuvola non c'e' spaziatura da stimare, e senza consumatori non
        # c'e' spaziatura da chiedere.
        #
        # LIMITE DICHIARATO, preesistente e non chiuso qui. `metrics` nasce
        # vuoto a ogni corsa, quindi su una ripresa il primo addendo manca
        # sempre e la spaziatura si ristima dalla nuvola caricata. Per
        # from_step da 5 a 12 quella nuvola e' 04_normals.ply, gia' rarefatta
        # dallo step 3, mentre una corsa intera prende
        # `metrics["01_load"]["spacing"]`, misurato sulla nuvola grezza: la
        # stessa cartella da' quindi due prior diversi a seconda di quanti step
        # la corsa comprende. Misurato il 31/08/2026 sul cubo sintetico
        # (spaziatura nativa 4,0): con `downsample.voxel_size` a 8,0 la nuvola
        # ridotta da' 7,447 contro i 4,0 della grezza, 1,86 volte. Sulla
        # configurazione di prova, dove `voxel_size` uguaglia la spaziatura
        # nativa, le due misure coincidono e la differenza non si vede. Chiuderlo
        # vuol dire decidere quale delle due misure e' quella giusta per
        # `wall.prior`, che e' una decisione sul prior e non sulla ripresa.
        if start <= 4 or stop >= 12:
            spacing = float(
                metrics.get("01_load", {}).get("spacing")
                or io.mean_spacing(points, cfg.input.spacing_sample, cfg.input.seed)
            )

        if start <= 2:
            in_corso = 2
            avvio = time.monotonic()
            points, step_metrics = segment.segment_cloud(points, cfg.segment, spacing)
            metrics["02_segment"] = step_metrics
            io.write_cloud(out / ARTIFACTS[2], points)
            source_cloud = points
            registra(2, avvio, ARTIFACTS[2])
            if stop <= 2:
                raise _FermataRichiesta
        elif start <= 7 or stop >= 12:
            # La nuvola segmentata (uscita dello step 2) ha DUE consumatori e
            # nessun altro: l'errore geometrico dello step 7 e il prior dello
            # step 12. La condizione li nomina entrambi invece di caricarla
            # sempre, e non e' una micro-ottimizzazione: caricarla quando non
            # gira nessuno dei due faceva FALLIRE una corsa che non ne aveva
            # bisogno. «Esegui solo lo step 9» in una cartella senza
            # 02_segmented.ply si fermava per un artefatto che quello step non
            # tocca -- ed e' proprio il caso che from_step == to_step esiste per
            # servire (config.py, RunConfig).
            #
            # `chiede` e' lo step che la consuma, non quello da cui la corsa
            # riparte. Nominare `start` produceva un consiglio che distrugge il
            # lavoro: «lo step 9 pretende 02_segmented.ply, esegui da qui in
            # giu' dallo step 2» riscrive gli artefatti dal 2 al 9, cioe'
            # proprio quelli su cui si stava iterando.
            source_cloud, _ = _ingresso_di_ripresa(
                7 if start <= 7 else 12, 2, out, io.read_cloud
            )

        if start <= 3:
            in_corso = 3
            avvio = time.monotonic()
            points, step_metrics = surface.downsample(points, cfg.downsample, spacing)
            metrics["03_downsample"] = step_metrics
            io.write_cloud(out / ARTIFACTS[3], points)
            registra(3, avvio, ARTIFACTS[3])
            if stop <= 3:
                raise _FermataRichiesta

        if start <= 4:
            in_corso = 4
            avvio = time.monotonic()
            normals, step_metrics = surface.estimate_normals(points, cfg.normals, spacing)
            metrics["04_normals"] = step_metrics
            io.write_cloud(out / ARTIFACTS[4], points, normals)
            registra(4, avvio, ARTIFACTS[4])
            if stop <= 4:
                raise _FermataRichiesta
        elif start <= 5:
            # `points` e `normals` hanno un consumatore solo, la ricostruzione
            # dello step 5. Da 6 in poi si lavora sulla superficie, e questa
            # riga era la seconda lettura della stessa nuvola nella stessa
            # corsa (misurate due letture di 04_normals.ply per ogni ripresa da
            # 5 in giu'), oltre che il secondo artefatto preteso da chi non lo
            # consuma.
            points, normals = _ingresso_di_ripresa(start, 4, out, io.read_cloud)

        if start <= 5:
            in_corso = 5
            avvio = time.monotonic()
            vertices, faces, step_metrics = surface.reconstruct(points, normals, cfg.surface)
            metrics["05_reconstruct"] = _con_le_misure_della_superficie(step_metrics, vertices, faces)
            _write_mesh(out / ARTIFACTS[5], vertices, faces)
            registra(5, avvio, ARTIFACTS[5])
            if stop <= 5:
                raise _FermataRichiesta
        elif start <= 8:
            vertices, faces = _ingresso_di_ripresa(start, _RESUME_MESH[start], out, _read_mesh)
        elif start <= 9 or stop >= 11:
            # lo step 8 scrive 08_simplified.ply solo se la semplificazione e'
            # abilitata: con from_step=9 la mesh valida a monte e' quella
            # dello step 8 se abilitata, altrimenti quella riparata dello
            # step 6 (predefinito), mai un ripiego generico sull'ultimo file
            # esistente.
            #
            # Non solo `== 9` da quando il tetto di from_step e' 12: lo step 11
            # pretende la stessa superficie con la stessa regola, perche' e'
            # lei -- e non i nodi del volume -- a definire il sistema di
            # riferimento del modello (`abaqus.align_to_axes`). Lo step 11 pero'
            # gira anche senza guardia di partenza, quindi la condizione e'
            # `stop >= 11` e non `start >= 11`: chi riparte dal 10 per fermarsi
            # al 10 fa solo metriche di volume, e la superficie non la guarda.
            # Come per la nuvola, `chiede` nomina lo step che la consuma.
            resume_from = 8 if cfg.simplify.enabled else 6
            vertices, faces = _ingresso_di_ripresa(
                start if start <= 9 else 11, resume_from, out, _read_mesh
            )

        if start <= 6:
            in_corso = 6
            avvio = time.monotonic()
            vertices, faces, step_metrics = repair.repair_surface(vertices, faces, cfg.repair)
            metrics["06_repair"] = _con_le_misure_della_superficie(step_metrics, vertices, faces)
            _write_mesh(out / ARTIFACTS[6], vertices, faces)
            registra(6, avvio, ARTIFACTS[6])
            if stop <= 6:
                raise _FermataRichiesta

        if start <= 7:
            in_corso = 7
            avvio = time.monotonic()
            step_metrics = quality.surface_metrics(vertices, faces)
            step_metrics["geometric_error"] = quality.geometric_error(vertices, faces, source_cloud)
            metrics["07_surface_quality"] = step_metrics
            registra(7, avvio, None)
            if stop <= 7:
                raise _FermataRichiesta

        if start <= 8:
            in_corso = 8
            avvio = time.monotonic()
            vertices, faces, step_metrics = surface.simplify(vertices, faces, cfg.simplify)
            metrics["08_simplify"] = _con_le_misure_della_superficie(step_metrics, vertices, faces)
            if cfg.simplify.enabled:
                _write_mesh(out / ARTIFACTS[8], vertices, faces)
            registra(8, avvio, ARTIFACTS[8] if cfg.simplify.enabled else None)
            if stop <= 8:
                raise _FermataRichiesta

        if start <= 9:
            in_corso = 9
            avvio = time.monotonic()
            nodes, tets, step_metrics = volume.tetrahedralize_with_metrics(
                vertices, faces, cfg.tet
            )
            metrics["09_tetrahedralize"] = step_metrics
            # Il tipo va dichiarato: `write_vtu` non lo indovina dal numero di
            # colonne, e il suo predefinito e' il lineare. Senza, un maglio
            # quadratico finirebbe scritto come `tetra` e meshio rifiuterebbe la
            # forma -- che e' il modo buono di sbagliare, ma solo perche' meshio
            # controlla.
            abaqus.write_vtu(out / ARTIFACTS[9], nodes, tets, element_type=cfg.tet.element)
            registra(9, avvio, ARTIFACTS[9])
            if stop <= 9:
                raise _FermataRichiesta
        else:
            # La guardia esiste per questo: il tetto di from_step e' salito a 12
            # perche' l'interfaccia esegue uno step alla volta, e senza di essa
            # «esegui lo step 10» avrebbe ritetraedrizzato -- su una scansione
            # reale decine di secondi per un conteggio che ne costa meno di uno.
            # `_maglio_di_volume` e' lo stesso lettore che il solutore usa: il
            # blocco di celle si prende per unicita' e non per nome, perche' i
            # nomi sono due (`tetra`, `tetra10`) e uno solo e' scritto.
            nodes, tets = _ingresso_di_ripresa(start, 9, out, _maglio_di_volume)

        in_corso = 10
        avvio = time.monotonic()
        metrics["10_volume_quality"] = quality.volume_metrics(nodes, tets, cfg.tet.reference_ratio)
        registra(10, avvio, None)
        if stop <= 10:
            raise _FermataRichiesta

        in_corso = 11
        avvio = time.monotonic()
        # Le regioni si attribuiscono qui, sui nodi **non allineati**:
        # `align_to_axes` gira dentro `export_model` e sposta le coordinate,
        # non l'ordine degli elementi. Misurata nello stesso riferimento in
        # cui il prior misura, la mappa e' fatta di soli indici e resta valida
        # nel deck allineato.
        regioni_deck, attribuzione_metriche = None, None
        if cfg.regioni:
            membrature = _membrature_del_prior(
                out / WALL_FILENAME, "l'attribuzione delle regioni"
            )
            prismi = attribuzione.prismi_delle_regioni(membrature, cfg.regioni)
            etichette, attribuzione_metriche = attribuzione.attribuisci(nodes, tets, prismi)
            # Soli indici: il deck nudo non porta sezioni, quindi il materiale
            # che la regione dichiara non ha piu' una strada verso il .inp.
            regioni_deck = {
                nome: np.flatnonzero(etichette == posizione)
                for posizione, nome in enumerate(prismi)
            }
        # `vertices` e' la superficie da cui la mesh di volume e' stata
        # generata: e' quella, e non i nodi del volume, a definire il sistema
        # di riferimento del modello (vedi abaqus.align_to_axes).
        metrics["11_export"] = abaqus.export_model(
            out / DECK_FILENAME,
            out / WALL_VTU_FILENAME,
            nodes,
            tets,
            cfg.export,
            cfg.tet,
            reference=vertices,
            regioni=regioni_deck,
        )
        if attribuzione_metriche is not None:
            metrics["11_export"]["regioni"] = attribuzione_metriche
        registra(11, avvio, DECK_FILENAME)
        pipeline_completa = True

        if stop <= 11:
            raise _FermataRichiesta

        in_corso = 12
        avvio = time.monotonic()
        # Il prior misura la nuvola segmentata e non la superficie ricostruita:
        # il rilievo e' il dato, e la ricostruzione di Poisson e' gia' una
        # interpretazione del rilievo. `source_cloud` e' esattamente l'uscita
        # dello step 2, che la ripresa ricarica quando riparte da piu' in la'.
        metrics["12_wall"] = calcola_prior(out, cfg, source_cloud, spacing)
        registra(12, avvio, WALL_FILENAME)
    except _FermataRichiesta:
        # Fermata su richiesta: gli step chiesti sono stati eseguiti e il
        # risultato e' valido quanto quello di una corsa intera, per gli step
        # che comprende.
        pass
    except BaseException:
        # Registra il fallimento dello step su cui il lavoro era fermo, poi
        # rilancia intatto: la pipeline non ingoia mai un errore, si limita a
        # lasciarne traccia. BaseException e non Exception perche' anche
        # un'interruzione da tastiera lascia lo stato coerente.
        steps.write_state(out, in_corso, impronte[in_corso], "fallito", None, 0.0)
        raise
    finally:
        # Il parziale, non metrics.json: una corsa interrotta lascia intatto
        # l'ultimo risultato completo invece di sostituirlo con il proprio
        # frammento. Era il difetto per cui la Fase 2 ha dovuto costruire
        # is_complete per distinguerli.
        with (out / METRICS_PARTIAL).open("w", encoding="utf-8") as handle:
            json.dump(metrics, handle, indent=2, default=float, ensure_ascii=False)

    # Solo qui, cioe' solo se nessuna eccezione non gestita e' uscita dal try:
    # la corsa e' arrivata dove doveva arrivare.
    completa = start == 1 and pipeline_completa
    if completa:
        # Una corsa intera e' autoritativa: sostituisce, non fonde. E' il
        # percorso che lo sweep esegue, e la Fase 2 dipende dal fatto che una
        # cartella di candidato non erediti nulla.
        (out / METRICS_PARTIAL).replace(out / METRICS_FILENAME)
        return metrics

    unite = _unisci_metriche(out, metrics)
    (out / METRICS_PARTIAL).unlink(missing_ok=True)
    return unite
