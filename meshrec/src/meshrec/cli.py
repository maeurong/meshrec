"""Riga di comando minima, non definitiva: serve a lavorare nelle Fasi 1 e 2.

L'interfaccia vera arriva in Fase 3. Qui non vive alcun valore predefinito:
tutto viene dal file di configurazione.
"""

from __future__ import annotations

import argparse
import json
import sys
import traceback
from pathlib import Path

from meshrec.core.config import (
    RunConfig,
    load_config,
    load_experiment,
)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="meshrec", description="Da nuvola di punti a modello FEM")
    commands = parser.add_subparsers(dest="command", required=True)

    run_command = commands.add_parser("run", help="esegue la pipeline su un file di configurazione")
    run_command.add_argument("config", type=Path)
    run_command.add_argument(
        "--from-step",
        type=int,
        default=None,
        help=(
            "riparte dagli artefatti già presenti nella cartella di elaborazione. "
            "Non verifica che siano stati prodotti con questa configurazione."
        ),
    )
    run_command.add_argument("--to-step", type=int, default=None)
    run_command.add_argument(
        "--only-step",
        type=int,
        default=None,
        help="esegue soltanto questo step, riusando gli artefatti a monte",
    )
    run_command.add_argument("--out-dir", type=Path, default=None)

    sweep_command = commands.add_parser("sweep", help="esegue una griglia di candidati")
    sweep_command.add_argument("experiment", type=Path)

    verify_command = commands.add_parser(
        "sweep-verify", help="ricontrolla le impronte degli artefatti di un registro"
    )
    verify_command.add_argument("registry", type=Path)

    report_command = commands.add_parser("sweep-report", help="genera il report da un registro")
    report_command.add_argument("registry", type=Path)
    report_command.add_argument("--out", type=Path, required=True)

    wall_command = commands.add_parser(
        "wall", help="ricalcola il solo prior geometrico sugli artefatti già presenti"
    )
    wall_command.add_argument("config", type=Path)

    model_command = commands.add_parser(
        "model", help="genera un modello parametrico come corsa figlia"
    )
    model_command.add_argument("config", type=Path)
    model_command.add_argument(
        "--tipo", choices=("estruso", "primitive"), required=True,
        help="estruso conserva sezione e fuori piombo misurati; primitive li raddrizza",
    )
    model_command.add_argument(
        "--out-dir", type=Path, default=None,
        help="cartella della corsa figlia; se omessa, quella della madre col suffisso del tipo",
    )

    compare_command = commands.add_parser(
        "compare", help="confronta le cartelle dei modelli generati dello stesso pezzo"
    )
    compare_command.add_argument("cartelle", type=Path, nargs="+")
    compare_command.add_argument("--out", type=Path, required=True)

    serve_command = commands.add_parser(
        "serve", help="avvia il server locale e apre MeshRec in una finestra (o nel browser con --browser)"
    )
    serve_command.add_argument(
        "config",
        type=Path,
        nargs="?",
        default=None,
        help=(
            "configurazione da aprire. Se omessa, l'interfaccia si apre sulla "
            "schermata d'ingresso: le corse già in runs/ e una corsa nuova da "
            "un file di punti"
        ),
    )
    serve_command.add_argument("--port", type=int, default=None)
    serve_command.add_argument("--no-browser", action="store_true", help="solo il server, nessuna finestra")
    serve_command.add_argument(
        "--browser", action="store_true",
        help="nel browser di sistema invece che nella finestra (DevTools, debug)",
    )

    return parser




# I tre tipi con cui questo programma parla all'operatore. Ricavati dai test che
# la scelta la fissavano gia': ValueError e' il vettore principale, OSError copre
# i FileNotFoundError che `wall` e `model` sollevano nominando l'artefatto
# mancante, RuntimeError quelli che nascono da un lavoro che non si e' potuto
# fare. Vedi `_riporta` per il debito che questo elenco porta.
_DIAGNOSTICI = (ValueError, OSError, RuntimeError)

# Quanto aspettare che uvicorn si metta in ascolto prima di dire che non ce
# l'ha fatta.
ATTESA_AVVIO_S = 10.0


def _riporta(errore: BaseException) -> int:
    """Una riga per un errore che il programma ha scritto, la traccia per gli altri.

    `_DIAGNOSTICI` sono i tre tipi con cui questo programma parla
    all'operatore: il messaggio e' gia' scritto per essere letto, e la traccia
    sopra lo seppellirebbe. Non e' un elenco scelto a priori -- l'ho ricavato
    dai test che quella scelta la fissavano gia', uno per tipo, e ognuno e'
    caduto quando ho provato a stampare la traccia dappertutto.

    **Debito dichiarato:** il discriminante giusto non e' il tipo ma se
    l'eccezione l'abbiamo sollevata noi, e si terrebbe con una classe marcatore
    invece che con un elenco. L'elenco cresce ogni volta che un comando nuovo
    sceglie un tipo nuovo, e il modo in cui lo scopri e' un test che cade.

    Ogni altra eccezione e' un guasto che nessuno ha previsto, e la sola riga
    di riepilogo non basta ad agire. Misurato il 30/08/2026 su un utente
    fermo al primo step: `UnicodeDecodeError: 'utf-8' codec can't decode byte
    0xe0 in position 79` e' arrivato senza dire quale file stesse leggendo, e
    senza la traccia non era diagnosticabile ne' da lui ne' da chi lo aiutava.

    **`UnicodeError` e' escluso a mano, e non e' un dettaglio.** Discende da
    `ValueError` -- `UnicodeDecodeError` -&gt; `UnicodeError` -&gt; `ValueError` --
    quindi la sola regola «una riga per i ValueError» avrebbe tolto la traccia
    proprio all'errore per cui questa funzione e' stata scritta. Trovato
    scrivendo il test, non leggendo: il primo giro e' passato verde sul caso
    sbagliato.
    """
    print(f"{type(errore).__name__}: {errore}", file=sys.stderr)
    scritto_da_noi = isinstance(errore, _DIAGNOSTICI) and not isinstance(errore, UnicodeError)
    if not scritto_da_noi:
        traceback.print_exception(errore, file=sys.stderr)
    return 1


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)

    if args.command == "sweep":
        from meshrec.core import sweep

        experiment = load_experiment(args.experiment)
        try:
            result = sweep.run_experiment(experiment, load_config(experiment.base))
        except Exception as error:
            return _riporta(error)
        print(json.dumps(result["summary"], indent=2, ensure_ascii=False, default=float))
        print(f"registro in {result['registry']}", file=sys.stderr)
        return 0

    if args.command == "sweep-verify":
        from meshrec.core import sweep

        esito = sweep.verify_registry(args.registry)
        print(json.dumps(esito, indent=2, ensure_ascii=False))
        stantie = [voce for voce in esito if voce["stale"]]
        if stantie:
            print(f"{len(stantie)} righe stantie", file=sys.stderr)
            return 1
        return 0

    if args.command == "sweep-report":
        from meshrec.core import report

        print(f"report in {report.write_report(args.registry, args.out)}")
        return 0

    if args.command == "wall":
        from meshrec.core import io, pipeline

        try:
            cfg = load_config(args.config)
            out = Path(cfg.run.out_dir)
            sorgente = out / pipeline.ARTIFACTS[2]
            if not sorgente.exists():
                raise FileNotFoundError(
                    f"manca {sorgente}: il prior misura la nuvola segmentata, che è "
                    "l'artefatto dello step 2. Esegui almeno fino a quello "
                    f"(`meshrec run {args.config} --to-step 2`) e riprova"
                )
            punti, _ = io.read_cloud(sorgente)
            spaziatura = io.mean_spacing(punti, cfg.input.spacing_sample, cfg.input.seed)
            esito = pipeline.calcola_prior(out, cfg, punti, spaziatura)
        except Exception as error:
            return _riporta(error)
        print(json.dumps(esito, indent=2, default=float, ensure_ascii=False))
        return 0

    if args.command == "model":
        from meshrec.core import pipeline

        try:
            cfg = load_config(args.config)
            destinazione = args.out_dir
            if destinazione is None:
                madre = Path(cfg.run.out_dir)
                destinazione = madre.with_name(f"{madre.name}-{args.tipo}")
            esito = pipeline.genera_modello(cfg, args.tipo, destinazione)
        except Exception as error:
            return _riporta(error)
        print(json.dumps(esito, indent=2, default=float, ensure_ascii=False))
        return 0

    if args.command == "compare":
        from meshrec.core import report

        try:
            percorso = report.write_comparison_report(args.cartelle, args.out)
        except Exception as error:
            return _riporta(error)
        print(f"confronto in {percorso}")
        return 0

    if args.command == "serve":
        import socket

        from meshrec.core.config import ServerConfig

        impostazioni = ServerConfig()
        if args.port is not None:
            impostazioni.port = args.port

        # La porta si prova PRIMA di annunciare l'ascolto e prima di aprire il
        # browser. Senza, il programma diceva «MeshRec in ascolto su ...» e poi
        # uvicorn falliva il bind: l'annuncio era una bugia, e il browser si
        # apriva sul server GIA' IN ASCOLTO su quella porta -- cioe' su una
        # copia vecchia del programma, con il codice di prima. Misurato il
        # 30/08/2026 su un utente che ha lavorato per ore su un processo
        # rimasto vivo, convinto di usare la versione appena aggiornata.
        def sonda(porta: int) -> int:
            prova = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            # Come uvicorn (asyncio usa `reuse_address=True`): senza, un socket in
            # TIME_WAIT lasciato dalla copia appena chiusa fa dire «porta gia'
            # occupata» per ~30 s, su una porta dove il server si metterebbe in
            # ascolto benissimo. Su POSIX contro un listener vivo il bind resta
            # rifiutato (errno 48) -- cioe' la sonda continua a fare il suo
            # mestiere. Su Windows no: li' SO_REUSEADDR lascia bindare SOPRA un
            # listener attivo, e la sonda diventerebbe cieca proprio nel caso per
            # cui esiste (MeshRec.bat e' un bersaglio spedito). Windows tiene
            # quindi il bind nudo, TIME_WAIT compreso.
            if sys.platform != "win32":
                prova.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                prova.bind((impostazioni.host, porta))
                return prova.getsockname()[1]
            finally:
                prova.close()

        try:
            sonda(impostazioni.port)
        except OSError as errore:
            if args.port is None:
                # Porta non scelta a mano: MeshRec.app lancia `serve` nudo, e
                # con la 8765 tenuta da un altro programma non si apriva
                # affatto (13/09/2026). Il browser va sull'indirizzo di QUESTO
                # processo, quindi la copia vecchia non inganna piu' nessuno.
                # ponytail: la porta puo' sparire fra sonda e bind di uvicorn;
                # allora il server non parte e lo dice il messaggio d'avvio.
                occupata = impostazioni.port
                impostazioni.port = sonda(0)
                print(
                    f"la porta {occupata} è occupata da un altro programma: uso la "
                    f"{impostazioni.port}. Se è un'altra copia di MeshRec rimasta "
                    "aperta, conviene chiuderla.",
                    file=sys.stderr,
                )
            else:
                print(
                    f"la porta {impostazioni.port} è già occupata su {impostazioni.host}: "
                    f"{errore.strerror or errore}.\n"
                    "Quasi sempre è un'altra copia di MeshRec rimasta aperta, e finché "
                    "resta viva il browser parla con quella — non con questa. Chiudila, "
                    "oppure scegli un'altra porta con `--port`.\n"
                    "Per trovarla: su Windows `netstat -ano | findstr :"
                    f"{impostazioni.port}` dà il PID nell'ultima colonna; su macOS e "
                    f"Linux `lsof -i :{impostazioni.port}`.",
                    file=sys.stderr,
                )
                return 1
        indirizzo = f"http://{impostazioni.host}:{impostazioni.port}/"

        import threading
        import time

        import uvicorn

        from meshrec.app import finestra
        from meshrec.app.server import CACHE_DIR, create_app

        # uvicorn in un thread e il thread principale al guscio: pywebview
        # vuole il thread principale (Cocoa) e uvicorn, fuori da esso, salta
        # da solo i gestori di segnale. `should_exit` lo ferma.
        app = create_app(args.config)
        server = uvicorn.Server(uvicorn.Config(
            app, host=impostazioni.host, port=impostazioni.port, log_level="warning",
            # Senza, `shutdown()` aspetta ogni connessione SSE per sempre e il
            # lifespan (che sta dopo quell'attesa) non parte mai. Sotto il
            # `join(timeout=5)` qui sotto, e va tenuto sotto.
            timeout_graceful_shutdown=2,
        ))

        def ferma():
            # `should_exit` da solo non basta: il generatore di /api/events
            # dorme in un thread e tiene aperta la sua connessione, che e'
            # esattamente cio' che uvicorn aspetta prima di spegnersi. L'Event
            # lo sveglia, il tetto graceful qui sopra resta la cintura.
            app.state.spegni.set()
            server.should_exit = True

        thread = threading.Thread(target=server.run, name="uvicorn", daemon=True)
        thread.start()
        scadenza = time.monotonic() + ATTESA_AVVIO_S
        while not server.started and thread.is_alive() and time.monotonic() < scadenza:
            time.sleep(0.05)
        if not server.started:
            ferma()
            thread.join(timeout=2)
            suggerimento = (
                "l'errore di uvicorn è qui sopra."
                if args.no_browser
                else "Rilancia con `--no-browser` per vedere l'errore di uvicorn."
            )
            print(
                f"il server non si è messo in ascolto su {indirizzo} entro {ATTESA_AVVIO_S:.0f} s. "
                f"{suggerimento}",
                file=sys.stderr,
            )
            return 1
        print(f"MeshRec in ascolto su {indirizzo}", file=sys.stderr)
        if args.no_browser or not impostazioni.open_browser:
            try:
                thread.join()
            except KeyboardInterrupt:
                ferma()
                thread.join(timeout=5)
            return 0
        try:
            modo = finestra.apri(
                indirizzo,
                cache=CACHE_DIR.parent.resolve(),
                porta=impostazioni.port,
                forza_browser=args.browser,
            )
        except Exception as errore:
            # Un guscio che crasha (Cocoa, WebView2 rotto) non deve lasciare
            # uvicorn appeso: ferma il server anche quando apri() non torna.
            ferma()
            thread.join(timeout=5)
            return _riporta(errore)
        if modo == "browser":
            # Come prima: il server resta in ascolto finche' Ctrl-C.
            try:
                thread.join()
            except KeyboardInterrupt:
                ferma()
                thread.join(timeout=5)
            return 0
        ferma()
        thread.join(timeout=5)
        return 0

    from meshrec.core import pipeline

    try:
        cfg = load_config(args.config)
        # from_step e to_step si assegnano insieme, mai uno alla volta: con
        # validate_assignment=True ogni riga rivalida l'intero modello, e
        # nessun ordine e' sicuro. La configurazione sul disco puo' portare un
        # to_step piu' piccolo di quello chiesto, e allora from_step per primo
        # rompe; oppure un from_step piu' grande, lasciato da una corsa
        # precedente, e allora to_step per primo rompe. Chiedere lo step 2 con
        # from_step=4 sul disco falliva cosi', e il pannello non lo diceva.
        # L'unico stato che deve esistere e' quello finale.
        richiesti: dict[str, int] = {}
        if args.only_step is not None:
            richiesti = {"from_step": args.only_step, "to_step": args.only_step}
        else:
            if args.from_step is not None:
                richiesti["from_step"] = args.from_step
            if args.to_step is not None:
                richiesti["to_step"] = args.to_step
        if richiesti:
            cfg.run = RunConfig.model_validate({**cfg.run.model_dump(), **richiesti})
        if args.out_dir is not None:
            cfg.run.out_dir = args.out_dir
        metrics = pipeline.run(cfg)
    except Exception as error:  # la riga di comando riporta il problema, non lo stack
        return _riporta(error)

    print(json.dumps(metrics, indent=2, default=float, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
