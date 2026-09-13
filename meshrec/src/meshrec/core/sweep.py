"""Motore di sweep: griglia, impronta, esecuzione, registro, dominanza.

Ogni candidato e' una cartella con il proprio config.yaml, eseguita come
`meshrec run` in un processo separato. La pipeline non viene toccata: il
motore le sta sopra, e cio' che esegue e' esattamente il comando con cui
sono stati prodotti i numeri della Fase 1.
"""

from __future__ import annotations

import hashlib
import itertools
import json
import subprocess
import sys
import time
import warnings
from concurrent.futures import ThreadPoolExecutor
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

import numpy as np

from meshrec.core.config import (
    BLOCCHI_RIMOSSI,
    ExperimentConfig,
    PipelineConfig,
    _separatori_posix,
)


# I blocchi di PipelineConfig che non entrano mai nell'impronta di sweep.
# `run` non ci entra perche' out_dir e from_step non cambiano il risultato
# dell'elaborazione. `wall` e `model` non ci entrano perche' sono nati con la
# Fase 4, dopo che i registri della Fase 2 erano gia' scritti: includerli
# cambierebbe l'impronta di ogni riga gia' registrata, cioe' la provenienza
# della tabella sperimentale della tesi, e nessun asse di sweep li tocca --
# tutti gli assi della griglia stanno a monte dello step 11.
#
# Questa lista e' la stessa conoscenza che STEP_BLOCKS (core/steps.py) tiene
# come fonte unica -- quale blocco conta per quale step -- scritta una seconda
# volta a mano. Le due possono divergere in silenzio, ed e' cosi' che
# un'esclusione e' sopravvissuta al blocco che la giustificava: tenerle
# d'accordo e' un obbligo, non una comodita'.
#
# `solutore` stava qui fino alla mappa #161, ed e' uscito col blocco: era
# escluso in secco, quindi toglierlo non muove le ventidue righe gia'
# registrate -- che e' precisamente la ragione per cui ci stava.
BLOCCHI_FUORI_IMPRONTA: tuple[str, ...] = ("run", "wall", "model")

# I blocchi che entrano nell'impronta solo quando portano qualcosa.
#
# `regioni` (Fase 8, #135) e' letto dallo step 11 (STEP_BLOCKS[11]), partiziona
# ALL_WALL in `*ELSET` e cambia il deck, che e' artefatto richiesto di ogni
# candidato -- lo sweep arriva a --to-step 11. Quindi due candidati con regioni
# diverse sono esperimenti diversi e devono avere impronte diverse: la cartella
# di un candidato e' fingerprint(cfg)[:12], e senza questa distinzione la
# seconda corsa sovrascrive la prima in silenzio, con verify_registry che se ne
# accorge solo a posteriori e solo se eseguito.
#
# Perche' condizionato e non secco: includere un blocco senza condizione
# cambierebbe l'impronta delle 22 righe di experiments/muro e
# experiments/lab_crop, cioe' la provenienza della tabella sperimentale della
# tesi -- nate prima della Fase 8, il blocco non ce l'hanno. Con l'omissione
# del blocco vuoto ne cambia 0 su 22. La regola regge anche da sola, non solo
# per compatibilita': una corsa senza regioni e una corsa le cui regioni sono
# assenti sono lo stesso esperimento.
#
# E' l'unica regola condizionata dell'impronta, e va dichiarata come tale:
# dentro l'impronta sopravvivono gia' quattro valori nulli (segment.crop_min,
# segment.crop_max, repair.max_hole_area, tet.max_volume) che nessuno omette.
#
# La regola copre i blocchi AGGIUNTI, non i campi TOLTI: togliere un campo da
# un modello sposta l'impronta di ogni riga gia' registrata.
#
# `regioni` e' un `dict[NomeSet, RegioneConfig]` che nasce `{}` -- cioe' falso
# -- e la forma a dizionario e' precisamente cio' che rende sicura la sua
# presenza in questa lista: un modello con campi porterebbe i propri
# predefiniti, e basta uno solo truthy fra quelli perche' il predicato di
# vuotezza qui sotto non scatti piu' e le ventidue righe si muovano, con il
# test dei blocchi verde.
#
# La regola dell'omissione vale per l'IMPRONTA DI CANDIDATO di questo modulo e
# NON per la catena degli step (`steps.step_fingerprints`), che hasha il
# payload cosi' com'e': `{"regioni": {}}` vi entra comunque. Aggiungere o
# togliere un blocco letto dallo step 11 sposta percio' le impronte degli step
# 11 e 12 una volta sola, e ogni corsa gia' su disco si dichiara da rieseguire
# da li' in giu' al primo avvio -- senza che l'operatore abbia cambiato un
# campo. E' una volta sola e si accetta; inseguire l'omissione dentro
# `step_fingerprints` sarebbe un'altra decisione.
BLOCCHI_VUOTI_FUORI_IMPRONTA: tuple[str, ...] = ("regioni",)


def fingerprint(cfg: PipelineConfig) -> str:
    """Sha256 della configurazione canonica, esclusi i blocchi che non contano.

    Due liste, non una: BLOCCHI_FUORI_IMPRONTA esce sempre,
    BLOCCHI_VUOTI_FUORI_IMPRONTA esce solo quando il blocco non porta nulla.
    Il motivo di ciascuna e' commentato dove sono dichiarate.

    out_dir e from_step non cambiano il risultato dell'elaborazione, e
    includerli renderebbe diverse due corse identiche: e' precisamente cio'
    che l'impronta esiste per impedire. Stessa impronta significa stesso
    esperimento.
    """
    payload = cfg.model_dump(mode="json")
    for blocco in BLOCCHI_FUORI_IMPRONTA:
        payload.pop(blocco, None)
    for blocco in BLOCCHI_VUOTI_FUORI_IMPRONTA:
        if not any((payload.get(blocco) or {}).values()):
            payload.pop(blocco, None)
    canonical = json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def with_override(cfg: PipelineConfig, path: str, value: object) -> PipelineConfig:
    """Copia della configurazione con un solo parametro cambiato, rivalidata.

    Passa dal dump e da model_validate invece di assegnare l'attributo:
    i modelli annidati non hanno validate_assignment, quindi un valore fuori
    dominio scritto per assegnazione arriverebbe intatto fino alla pipeline.
    """
    data = cfg.model_dump(mode="json")
    node = data
    parts = path.split(".")
    for indice, part in enumerate(parts[:-1]):
        # Il blocco puo' non esserci affatto: `analysis`, `carichi` e
        # `selettori` sono usciti col deck nudo e gli `esperimento.yaml` gia'
        # scritti li portano ancora come assi. Questa strada cammina il dump e
        # non l'attributo, quindi non passa dalla validazione di
        # `PipelineConfig`: senza questa riga l'indicizzazione dava
        # `KeyError('analysis')` sul blocco assente e `TypeError: 'NoneType'
        # object is not subscriptable` su quello nullo, e nessuno dei due dice
        # quale asse dell'esperimento l'ha chiesto.
        node = node.get(part) if isinstance(node, dict) else None
        if node is None:
            blocco = ".".join(parts[: indice + 1])
            if blocco in BLOCCHI_RIMOSSI:
                raise ValueError(
                    f"l'asse '{path}' punta a '{blocco}', che non esiste più "
                    f"({BLOCCHI_RIMOSSI[blocco]}): togli l'asse dall'esperimento"
                )
            raise ValueError(
                f"l'asse '{path}' scende dentro '{blocco}', che questa configurazione "
                f"non dichiara: compila '{blocco}' nella base dell'esperimento prima "
                "di farne un asse dello sweep"
            )
    node[parts[-1]] = value
    return PipelineConfig.model_validate(data)


def expand(
    experiment: ExperimentConfig, base: PipelineConfig
) -> list[tuple[dict[str, object], PipelineConfig]]:
    """Candidati della griglia: la base, un asse alla volta, poi le coppie dichiarate.

    Un fattoriale pieno sui cinque assi della griglia reale (3x3x3x4x2 livelli)
    sono 216 candidati, in
    gran parte combinazioni che nessuno leggera'. Il fronte di Pareto si
    costruisce su qualunque insieme di candidati e non richiede una griglia
    cartesiana per essere valido.

    I duplicati sono rimossi per impronta: un livello uguale al valore di
    base non produce un secondo candidato identico.

    Il rifiuto qui sotto esiste perche' due candidati che differissero solo per
    un blocco fuori impronta avrebbero la stessa impronta. Resta il caso
    degenere dell'asse su un blocco condizionato che sta vuoto a tutti i
    livelli, che non produce candidati distinti: non serve una guardia, lo
    assorbe la deduplica per impronta qui sotto.
    """
    for asse in experiment.axes:
        blocco = asse.path.split(".")[0]
        if blocco in BLOCCHI_FUORI_IMPRONTA:
            raise ValueError(
                f"l'asse '{asse.path}' punta al blocco '{blocco}', che non entra "
                "nell'impronta: due candidati che differissero solo per quel "
                "valore avrebbero la stessa impronta e il registro non potrebbe "
                "distinguerli"
            )

    levels = {axis.path: axis.values for axis in experiment.axes}
    combinations: list[dict[str, object]] = [{}]

    for path, values in levels.items():
        combinations.extend({path: value} for value in values)

    for first, second in experiment.pairs:
        combinations.extend(
            {first: a, second: b} for a, b in itertools.product(levels[first], levels[second])
        )

    candidates: list[tuple[dict[str, object], PipelineConfig]] = []
    seen: set[str] = set()
    for axes in combinations:
        cfg = base
        for path, value in axes.items():
            cfg = with_override(cfg, path, value)
        mark = fingerprint(cfg)
        if mark not in seen:
            seen.add(mark)
            candidates.append((axes, cfg))
    return candidates


# Le chiavi che rendono completo un candidato di sweep: derivate da
# STEP_KEYS (fonte unica) invece di riscritte a mano, ma non tutte -- "12_wall"
# e' tagliata per chiave e non per posizione (un domani STEP_KEYS piu' lungo
# non sbaglierebbe in silenzio con un indice numerico). Il prior non e' un
# requisito di completezza dello sweep: nessun asse della griglia lo tocca
# (vedi BLOCCHI_FUORI_IMPRONTA), sta a valle dello step 11, e un candidato e'
# completo quando ha il proprio deck, non quando ha il prior. Stessa ragione
# per cui `run_candidate` chiede `--to-step 11` esplicito al sottoprocesso
# invece di ereditare il predefinito di RunConfig.to_step, che ha gia' valso
# 13, poi 12, e ora 11 dal perimetro del prodotto: le due esclusioni -- qui e
# li' -- si spiegano a vicenda, perche' sono una decisione del chiamante e non
# un'eredita'.
from meshrec.core.pipeline import METRICS_FILENAME, METRICS_PARTIAL
from meshrec.core.steps import STEP_KEYS

REQUIRED_STEPS: tuple[str, ...] = tuple(
    chiave for chiave in STEP_KEYS if chiave != "12_wall"
)

_TRACKED_PACKAGES: tuple[str, ...] = ("open3d", "tetgen", "pymeshfix", "pymeshlab", "numpy")

# Nomi dei file che ogni candidato porta a prescindere dall'esito: la
# configurazione con cui e' partito e le metriche con cui e' arrivato, complete
# o parziali se e' morto a meta'. Non sono artefatti della pipeline e vanno
# esclusi ovunque si elenchino o si potino gli artefatti di un candidato.
CONFIG_FILENAME = "config.yaml"
_CANDIDATE_FILES: tuple[str, str, str] = (CONFIG_FILENAME, METRICS_FILENAME, METRICS_PARTIAL)


def is_complete(metrics: dict[str, object]) -> bool:
    """Vero se il metrics.json porta tutte le chiavi di step.

    pipeline.run scrive metrics.json in un blocco finally, quindi una corsa
    uccisa lascia un dizionario parziale che nessun controllo distingueva da
    uno completo. Un candidato incompleto non puo' entrare nel fronte.

    metrics puo' essere un JSON scalare valido (per esempio 5) invece di un
    dizionario, se il file e' stato troncato o scritto a meta': `step in
    metrics` solleverebbe TypeError su un intero, quindi il controllo di tipo
    precede il controllo delle chiavi.
    """
    return isinstance(metrics, dict) and all(step in metrics for step in REQUIRED_STEPS)


def leggi_metriche(out_dir: Path) -> dict[str, object]:
    """metrics.json se c'e', altrimenti il parziale che la corsa ha lasciato.

    Dalla Fase 3 la pipeline scrive metrics.json solo quando arriva in fondo:
    un candidato fallito lascia soltanto il parziale, e la riga del registro
    deve continuare a portarne le metriche come faceva prima.
    """
    for nome in (METRICS_FILENAME, METRICS_PARTIAL):
        percorso = Path(out_dir) / nome
        if not percorso.exists():
            continue
        try:
            with percorso.open(encoding="utf-8") as maniglia:
                return json.load(maniglia)
        except (OSError, ValueError):
            # Un processo ucciso puo' lasciare il file troncato: si prova il
            # successivo invece di sollevare, e is_complete({}) resta falso.
            #
            # ValueError e non json.JSONDecodeError, che ne e' una sottoclasse e
            # lascia fuori UnicodeDecodeError: quello lo solleva la lettura del
            # file prima ancora del parse, su un byte non UTF-8. Qui pesa il
            # doppio, perche' uno sweep gira i candidati in parallelo e un
            # metrics.json storto fermerebbe la raccolta di TUTTI invece di far
            # scartare quel candidato.
            continue
    return {}


def file_digest(path: Path) -> str:
    """Sha256 di un file, letto a blocchi: gli artefatti arrivano a 101 MB."""
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


class GitUnavailableWarning(UserWarning):
    """git non e' partito: la riga scrive provenienza incompleta, non fabbricata."""


def provenance() -> dict[str, object]:
    """Commit del codice, stato dell'albero e versioni delle librerie che contano.

    Senza queste tre cose una riga non e' ricostruibile a distanza di mesi:
    la stessa configurazione su un codice diverso e' un altro esperimento.
    """
    def _git(*args: str) -> str | None:
        try:
            result = subprocess.run(
                # `git` e' di terze parti e su Windows nomina i file nella
                # codepage locale. Senza `encoding` la lettura userebbe quella
                # preferita dalla macchina -- utf-8 dentro il sottoprocesso del
                # server, che parte con `PYTHONUTF8=1` -- e un nome accentato
                # farebbe cadere la provenienza, che gira a ogni corsa, prima
                # ancora che il candidato parta. `replace` perche' una
                # provenienza storta si legge, un'eccezione no.
                ["git", *args],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                check=False,
            )
        except OSError as exc:
            # git assente, o l'avvio del processo negato dall'ambiente: in ogni
            # caso None e' distinto da "" (comando riuscito, output vuoto),
            # altrimenti un albero sporco letto a vuoto si scriverebbe pulito.
            warnings.warn(f"git non avviabile, provenienza incompleta: {exc}", GitUnavailableWarning)
            return None
        if result.returncode != 0:
            # Comando partito ma fallito (fuori da un repository, per esempio):
            # stdout e' vuoto per il fallimento, non perche' l'albero e' pulito.
            warnings.warn(
                f"git {' '.join(args)} fallito ({result.returncode}), provenienza incompleta",
                GitUnavailableWarning,
            )
            return None
        return result.stdout.strip()

    versions: dict[str, str] = {}
    for name in _TRACKED_PACKAGES:
        try:
            versions[name] = version(name)
        except PackageNotFoundError:
            versions[name] = "assente"

    dirty_raw = _git("status", "--porcelain")

    return {
        "commit": _git("rev-parse", "HEAD") or "sconosciuto",
        "dirty": None if dirty_raw is None else bool(dirty_raw),
        "python": sys.version.split()[0],
        "versions": versions,
    }


def append_row(path: Path, row: dict[str, object]) -> None:
    """Aggiunge una riga al registro. In sola aggiunta: nessuna riga viene riscritta."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, ensure_ascii=False, default=float) + "\n")


def load_registry(path: Path) -> list[dict[str, object]]:
    """Rilegge il registro riga per riga."""
    path = Path(path)
    if not path.exists():
        return []
    with path.open(encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def run_candidate(
    axes: dict[str, object],
    cfg: PipelineConfig,
    out_dir: Path,
    timeout_s: float,
) -> dict[str, object]:
    """Esegue un candidato come processo separato e ne restituisce la riga.

    Il sottoprocesso, e non un pool in memoria, per una ragione misurata: in
    Fase 1 il processo e' stato ucciso dal sistema per esaurimento della
    memoria senza sollevare alcuna eccezione. Un worker perso cosi' rompe un
    ProcessPoolExecutor e porta giu' lo sweep; un sottoprocesso lascia un
    codice di uscita e una riga di fallimento.

    Non solleva mai per un candidato che fallisce: fallire e' un esito, e un
    buco nel registro sarebbe indistinguibile da un candidato mai provato.
    """
    from meshrec.core.config import save_config

    out_dir = Path(out_dir)
    cfg = cfg.model_copy(deep=True)
    cfg.run.out_dir = out_dir
    config_path = out_dir / CONFIG_FILENAME

    try:
        out_dir.mkdir(parents=True, exist_ok=True)
        save_config(cfg, config_path)
    except OSError as exc:
        # La cartella del candidato non si e' potuta preparare (permessi
        # negati, collisione con un file omonimo): nessun sottoprocesso e'
        # partito, ma la riga esiste comunque. L'impronta si calcola senza
        # toccare il disco, quindi resta valida anche qui.
        return {
            "fingerprint": fingerprint(cfg),
            "axes": axes,
            "outcome": "errore",
            "exit_code": None,
            "duration_s": 0.0,
            "complete": False,
            "stderr": f"preparazione della cartella del candidato fallita: {exc}",
            "config": cfg.model_dump(mode="json"),
            "input_digest": None,
            "artifacts": {},
            "artifacts_kept": False,
            "out_dir": out_dir.as_posix(),
            # config.yaml non e' mai stato scritto su disco in questo ramo:
            # un rerun che lo cita fallirebbe fra mesi. None, non un comando morto.
            "rerun": None,
            "metrics": {},
            "provenance": provenance(),
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        }

    started = time.monotonic()
    try:
        completed = subprocess.run(
            # --to-step 11 esplicito, e non ereditato dal predefinito di
            # RunConfig.to_step, che oggi vale 11 e coincide: la richiesta resta
            # esplicita perche' e' una decisione del chiamante, e il predefinito
            # e' gia' cambiato tre volte sotto di essa (13, poi 12, poi 11).
            # Uno sweep valuta candidati di *elaborazione*, e la selezione di
            # Pareto non legge ne' il prior ne' la soluzione -- stessa ragione
            # per cui REQUIRED_STEPS qui sotto non li richiede. Era 12, e
            # faceva pagare a ogni candidato un prior geometrico intero che
            # nessuno rileggeva; pagare anche ccx e i suoi artefatti
            # (.frd/.vtu, MB per candidato) sarebbe costo puro.
            [sys.executable, "-m", "meshrec.cli", "run", str(config_path), "--to-step", "11"],
            capture_output=True,
            text=True,
            # Lo stderr del candidato entra nella riga del registro: senza
            # `encoding` i due capi del tubo scelgono ognuno la propria, e su
            # Windows il figlio scrive nella codepage mentre il padre legge
            # utf-8. Un solo nome accentato -- o una riga di `ccx`, che scrive
            # sul descrittore saltando `sys.stdout` -- farebbe saltare
            # l'intero candidato.
            encoding="utf-8",
            errors="replace",
            timeout=timeout_s,
            check=False,
        )
        exit_code, stderr = completed.returncode, completed.stderr
        outcome = "riuscito" if exit_code == 0 else "fallito"
    except subprocess.TimeoutExpired as expired:
        exit_code, outcome = None, "timeout"
        # `TimeoutExpired.stderr` non e' decodificata su POSIX nemmeno con
        # `text=True` -- l'eccezione unisce i pezzi grezzi -- mentre su Windows
        # `subprocess.run` richiama `communicate()` dopo il `kill()` e la trova
        # `str`. Senza questo la stessa corsa uccisa lasciava `b'*WARNING...'`
        # su una macchina e il testo sull'altra.
        parziale = expired.stderr or ""
        if isinstance(parziale, bytes):
            parziale = parziale.decode("utf-8", errors="replace")
        stderr = f"nessuna uscita entro {timeout_s} s\n{parziale}"
    duration = time.monotonic() - started

    metrics = leggi_metriche(out_dir)

    artifacts: dict[str, str | None] = {}
    for item in sorted(out_dir.iterdir()):
        try:
            if not item.is_file() or item.name in _CANDIDATE_FILES:
                continue
            artifacts[item.name] = file_digest(item)
        except OSError:
            # File cancellato o illeggibile fra l'elenco e la lettura: la
            # riga registra che l'impronta manca invece di sollevare qui.
            artifacts[item.name] = None
    input_path = Path(cfg.input.path)
    input_digest: str | None = None
    if input_path.exists():
        try:
            input_digest = file_digest(input_path)
        except OSError:
            # Stesso principio dell'elenco artefatti: l'impronta manca, la
            # riga lo registra invece di sollevare qui.
            input_digest = None

    return {
        "fingerprint": fingerprint(cfg),
        "axes": axes,
        "outcome": outcome,
        "exit_code": exit_code,
        "duration_s": duration,
        "complete": is_complete(metrics),
        # stderr e' dove finiscono TruncatedRefinementWarning,
        # IneffectiveVolumeLimitWarning e UnconstrainedModelWarning: qui
        # diventano un campo della riga invece di una riga su un terminale
        # che nel frattempo si e' chiuso.
        "stderr": stderr.strip(),
        "config": cfg.model_dump(mode="json"),
        "input_digest": input_digest,
        "artifacts": artifacts,
        "artifacts_kept": True,
        "out_dir": out_dir.as_posix(),
        "rerun": f"uv run meshrec run {config_path.as_posix()} --to-step 11",
        "metrics": metrics,
        "provenance": provenance(),
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
    }


class SweepDiagnosticWarning(UserWarning):
    """Lo sweep e' arrivato in fondo ma il suo esito non e' utilizzabile cosi' com'e'."""


def objectives(row: dict[str, object]) -> tuple[float, float, float] | None:
    """I tre assi del fronte, tutti da minimizzare, o None se la riga non ne ha.

    Errore di spessore, numero di tetraedri, frazione di elementi oltre il
    metro fisso. La fedelta' e' lo spessore e non l'errore bidirezionale
    perche' quello resta piccolo mentre Poisson ingrassa il muro reale da
    176 a 214 mm: e' cieco proprio sull'errore che governa la rigidezza.
    """
    if row.get("outcome") != "riuscito" or not row.get("complete"):
        return None
    volume = row.get("metrics", {}).get("10_volume_quality")
    if volume is None or row.get("thickness_error") is None:
        return None
    # is_complete controlla solo che la chiave di step "10_volume_quality"
    # esista, non le sue sottochiavi: un candidato ucciso a meta' scrittura
    # puo' completare tutti gli step ma lasciare il dizionario dello step
    # senza radius_edge_over_reference o tets. Accesso difensivo invece di
    # KeyError, con lo stesso esito di una riga non confrontabile.
    tets = volume.get("tets")
    over = volume.get("radius_edge_over_reference")
    if tets is None or over is None:
        return None
    return (float(row["thickness_error"]), float(tets), float(over))


def _dominates(a: tuple[float, ...], b: tuple[float, ...]) -> bool:
    return all(x <= y for x, y in zip(a, b)) and any(x < y for x, y in zip(a, b))


def pareto_front(rows: list[dict[str, object]]) -> list[dict[str, object]]:
    """Righe non dominate. Nessun punteggio pesato, nessun peso arbitrario.

    Un candidato cade se un altro lo eguaglia o lo batte su tutti e tre gli
    assi e lo batte su almeno uno. I candidati falliti o incompleti non
    entrano: restano righe, ma non sono confrontabili.
    """
    # ponytail: confronto O(n^2), adeguato a decine di candidati; se la
    # griglia crescera' di un ordine, ordinare per il primo asse e potare.
    scored = [(row, objectives(row)) for row in rows]
    valid = [(row, score) for row, score in scored if score is not None]
    return [
        row
        for row, score in valid
        if not any(_dominates(other, score) for _, other in valid if other != score)
    ]


def check_sweep(
    rows: list[dict[str, object]], front: list[dict[str, object]]
) -> dict[str, object]:
    """Le tre sorveglianze sull'esito complessivo dello sweep.

    Nessuna delle tre e' tarata: sono affermazioni qualitative, come la
    soglia a meta di min_ratio e quella della copertura d'appoggio. Quando
    piu di meta della griglia non arriva in fondo e' la griglia a stare nel
    posto sbagliato; quando nessun candidato e' dominato gli assi non stanno
    discriminando e il fronte non sta scartando nulla; quando nessuna riga e'
    confrontabile lo sweep finisce con fronte vuoto e uscita zero, e senza
    questo avviso quell'esito e' indistinguibile da uno sweep che non aveva
    ancora candidati da confrontare.
    """
    failed = [row for row in rows if row.get("outcome") != "riuscito"]
    comparable = [row for row in rows if objectives(row) is not None]
    failed_fraction = len(failed) / len(rows) if rows else 0.0
    front_is_whole_grid = bool(comparable) and len(front) == len(comparable)
    no_comparable_candidates = bool(rows) and not comparable

    if failed_fraction > 0.5:
        warnings.warn(
            f"il {failed_fraction:.0%} dei candidati non arriva in fondo: "
            "è la griglia a stare nel posto sbagliato, non i candidati",
            SweepDiagnosticWarning,
            stacklevel=2,
        )
    if no_comparable_candidates:
        warnings.warn(
            f"nessuno dei {len(rows)} candidati è confrontabile: nessuna riga "
            "porta un errore di spessore misurabile, il fronte è vuoto",
            SweepDiagnosticWarning,
            stacklevel=2,
        )
    if front_is_whole_grid:
        warnings.warn(
            f"il fronte contiene tutti e {len(front)} i candidati confrontabili: "
            "non discrimina, e non sta scartando nulla",
            SweepDiagnosticWarning,
            stacklevel=2,
        )

    return {
        "candidates": len(rows),
        "failed": len(failed),
        "failed_fraction": failed_fraction,
        "comparable": len(comparable),
        "front": len(front),
        "front_is_whole_grid": front_is_whole_grid,
    }


def measure_thickness_error(row: dict[str, object], source_thickness: float | None) -> float | None:
    """Scarto fra lo spessore ricostruito e quello della nuvola sorgente [mm].

    Lo spessore ricostruito si misura sui vertici della superficie riparata,
    cioe' sulla geometria che entra nella tetraedrizzazione, con la stessa
    funzione usata sulla sorgente: e' il confronto a misura unica che rende
    l'asse verificabile.

    Non solleva mai: un candidato ucciso dopo la riparazione e prima del
    blocco finally che scrive metrics.json (memoria esaurita, timeout) lascia
    06_repaired.ply sul disco ma metrics vuoto. run_experiment chiama questa
    funzione dopo aver gia' eseguito tutti i candidati e prima di scrivere il
    registro: un'eccezione qui perderebbe ore di calcolo senza lasciarne
    traccia. Un asse di fedelta' che non si riesce a misurare per una riga e'
    un thickness_error nullo, non un registro vuoto. source_thickness e'
    None quando la nuvola sorgente stessa e' risultata non bimodale: nessuno
    scarto e' calcolabile contro un valore che non esiste.
    """
    from meshrec.core import io, quality
    from meshrec.core.pipeline import ARTIFACTS

    repaired = Path(_separatori_posix(row["out_dir"])) / ARTIFACTS[6]
    if not repaired.exists():
        return None
    import open3d as o3d

    try:
        with io.percorso_open3d(repaired) as nativo:
            mesh = o3d.io.read_triangle_mesh(nativo)
    except OSError:
        # File cancellato o illeggibile fra il controllo e l'apertura: nessuna
        # mesh, quindi nessuna misura, non un'eccezione che ferma lo sweep.
        return None
    vertices = np.asarray(mesh.vertices)
    if len(vertices) == 0:
        return None
    try:
        spacing = float(row["metrics"]["01_load"]["spacing"])
    except (KeyError, TypeError, ValueError):
        # metrics.json manca, e' incompleto o porta un valore non numerico
        # ("abc", ""): float() solleva ValueError, non catturato in
        # precedenza. Il caso del candidato ucciso a meta'. La riga resta,
        # semplicemente senza asse di fedelta'.
        return None
    # Su vertici degeneri (mesh piatta o collineare) quality.thickness non
    # solleva: dichiara bimodal False, gestito subito sotto.
    measured = quality.thickness(vertices, bin_width=spacing)
    row["thickness_reconstructed"] = measured["thickness"]
    row["thickness_bimodal"] = measured["bimodal"]
    if not measured["bimodal"] or source_thickness is None:
        return None
    return abs(measured["thickness"] - source_thickness)


def prune(rows: list[dict[str, object]], front: list[dict[str, object]]) -> int:
    """Rimuove gli artefatti dei dominati; config.yaml e metrics.json restano.

    La riga dichiara `artifacts_kept: false` e porta gia' il comando che li
    rigenera: config completo piu impronta del codice rendono la
    riesecuzione un comando, non una ricostruzione.
    """
    kept = {row["fingerprint"] for row in front}
    removed = 0
    for row in rows:
        if row["fingerprint"] in kept or not row.get("out_dir"):
            continue
        candidate_dir = Path(_separatori_posix(row["out_dir"]))
        if not candidate_dir.is_dir():
            # run_candidate scrive questa riga quando la cartella del
            # candidato non si e' potuta creare (permessi negati, collisione
            # con un file omonimo): out_dir esiste come stringa ma non come
            # cartella. iterdir() su un file solleva NotADirectoryError; la
            # riga porta gia' artifacts_kept=False dalla sua origine, quindi
            # non c'e' nulla da potare qui.
            continue
        for item in candidate_dir.iterdir():
            if item.is_file() and item.name not in _CANDIDATE_FILES:
                item.unlink()
                removed += 1
        row["artifacts_kept"] = False
    return removed


def run_experiment(
    experiment: ExperimentConfig, base: PipelineConfig
) -> dict[str, object]:
    """Espande la griglia, esegue i candidati in parallelo, scrive il registro.

    I thread attendono soltanto i sottoprocessi e non calcolano nulla, quindi
    OMP_NUM_THREADS=1 continua a valere dentro ciascun candidato e la
    riproducibilita verificata in Fase 1 regge invariata.
    """
    from meshrec.core import io, quality, segment

    root = Path(experiment.sweep.runs_root) / experiment.name
    registry = Path(experiment.sweep.registry_root) / experiment.name / "registro.jsonl"

    if (root / METRICS_FILENAME).exists():
        # metrics.json nasce solo dalla rinomina che pipeline.run fa a corsa
        # conclusa (il blocco finally scrive metrics.partial.json, non
        # questo): se metrics.json e' li' dentro root, root e' comunque la
        # cartella di una corsa della pipeline, e non una cartella
        # d'esperimento vuota. Un esperimento non scrive mai dentro una corsa
        # esistente, a maggior ragione se e' runs/muro o runs/lab_crop,
        # dichiarate di sola lettura.
        raise ValueError(
            f"{root} esiste già e contiene metrics.json: è la cartella di "
            "una corsa della pipeline, non una cartella d'esperimento vuota. "
            "Mi rifiuto di scrivere sopra una corsa esistente"
        )
    if registry.exists():
        # La radice di un esperimento non ha metrics.json (i candidati sono
        # sottocartelle), quindi la guardia sopra non basta: un secondo
        # `meshrec sweep` sullo stesso esperimento la supererebbe, rigirerebbe
        # tutto e appenderebbe altre righe in coda allo stesso registro, che
        # essendo in sola aggiunta non sostituisce nulla. Il registro
        # raddoppia in silenzio, e verify_registry non se ne accorge perche'
        # le impronte restano le stesse.
        raise ValueError(
            f"{registry} esiste già: un secondo sweep dello stesso esperimento "
            "appenderebbe altre righe allo stesso registro invece di "
            "sostituirlo. Cancella il registro per rifare questo esperimento, "
            "o cambia experiment.name per farne uno nuovo"
        )

    # La sorgente si legge con load_cloud, che applica input.scale: read_cloud
    # non lo fa, e su una configurazione con scale 1000 la misura uscirebbe in
    # metri contro un valore noto in millimetri. Si segmenta poi con i
    # parametri della base perche' la segmentazione non e' un asse, quindi e'
    # comune a tutti i candidati, ed e' la stessa nuvola su cui si misura lo
    # spessore ricostruito.
    source, load_metrics = io.load_cloud(base.input)
    spacing = float(load_metrics["spacing"])
    source, _ = segment.segment_cloud(source, base.segment, spacing)
    source_thickness = quality.thickness(source, bin_width=spacing)
    if experiment.known_thickness is not None:
        misurato = source_thickness["thickness"]
        # bimodal falso comporta thickness assente (None, dichiarato invece di
        # simulato): il controllo precede quello sullo scarto, altrimenti
        # abs(None - known_thickness) romperebbe il cancello con un TypeError
        # proprio mentre sta segnalando il problema.
        non_valido = misurato is None or not source_thickness["bimodal"]
        if not non_valido:
            scarto = abs(misurato - experiment.known_thickness)
            non_valido = scarto / experiment.known_thickness > 0.05
        if non_valido:
            letto = "non misurabile" if misurato is None else f"{misurato:.1f} mm"
            raise ValueError(
                "la misura di spessore non riproduce il valore noto sulla nuvola "
                f"sorgente: letto {letto} contro "
                f"{experiment.known_thickness:.1f} mm noti, bimodale="
                f"{source_thickness['bimodal']}. L'asse di fedelta non è "
                "utilizzabile e lo sweep non parte"
            )

    candidates = expand(experiment, base)
    with ThreadPoolExecutor(max_workers=experiment.sweep.workers) as pool:
        rows = list(
            pool.map(
                lambda item: run_candidate(
                    item[0],
                    item[1],
                    root / fingerprint(item[1])[:12],
                    experiment.sweep.timeout_s,
                ),
                candidates,
            )
        )

    for row in rows:
        row["thickness_source"] = source_thickness["thickness"]
        row["thickness_error"] = measure_thickness_error(row, source_thickness["thickness"])

    front = pareto_front(rows)
    summary = check_sweep(rows, front)
    if not experiment.sweep.keep_dominated_artifacts:
        summary["pruned_files"] = prune(rows, front)

    front_marks = {row["fingerprint"] for row in front}
    for row in rows:
        row["on_front"] = row["fingerprint"] in front_marks
        append_row(registry, row)

    return {"summary": summary, "rows": rows, "front": front, "registry": str(registry)}


def verify_registry(path: Path) -> list[dict[str, object]]:
    """Ricalcola le impronte degli artefatti e marca stantia ogni riga che non torna.

    E' il primo principio applicato al registro stesso: senza questo controllo
    una riga e i file che dice di descrivere possono divergere in silenzio, ed
    e' esattamente cio' che e' accaduto in Fase 1.

    Una riga potata non e' stantia: dichiara di non avere piu artefatti, e
    quella dichiarazione e' coerente con il disco.
    """
    esito: list[dict[str, object]] = []
    for row in load_registry(path):
        if not row.get("artifacts_kept", True):
            esito.append(
                {"fingerprint": row["fingerprint"], "stale": False, "reason": "artefatti potati"}
            )
            continue

        mancanti: list[str] = []
        diversi: list[str] = []
        for name, digest in row.get("artifacts", {}).items():
            item = Path(_separatori_posix(row["out_dir"])) / name
            if not item.exists():
                mancanti.append(name)
            elif file_digest(item) != digest:
                diversi.append(name)

        reason = ""
        if diversi:
            reason = f"impronta diversa: {', '.join(sorted(diversi))}"
        elif mancanti:
            reason = f"artefatti assenti: {', '.join(sorted(mancanti))}"
        esito.append(
            {
                "fingerprint": row["fingerprint"],
                "stale": bool(diversi or mancanti),
                "reason": reason or "coerente",
            }
        )
    return esito
