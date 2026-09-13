"""Ingresso: avviare il programma senza una configurazione scritta a mano.

Il programma nasceva legato a uno yaml (`create_app` esigeva un percorso, e la
riga di comando un argomento obbligatorio). All'universita' arriva una nuvola di
punti, non uno yaml: questi test fissano la strada che parte dal file di punti e
finisce su una corsa in `runs/`.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from meshrec.app import server
from meshrec.app.server import create_app
from meshrec.core.config import InputConfig, PipelineConfig, load_config, save_config


# Il server risponde solo a un nome locale (middleware `solo_dal_calcolatore_locale`
# in server.py, contro il DNS rebinding). Il predefinito di TestClient e'
# `http://testserver`, che quel middleware rifiuta con 403 -- ed e' giusto che lo
# rifiuti: i banchi devono parlare col server come ci parla il browser vero.
BASE_LOCALE = "http://127.0.0.1"


@pytest.fixture()
def nuvola(tmp_path: Path) -> Path:
    """Una nuvola vera ma minuscola: il server la legge solo per esistere."""
    from meshrec.core import io, synth

    percorso = tmp_path / "scansione.ply"
    io.write_cloud(percorso, synth.sample_box_surface((10.0, 10.0, 10.0), 5.0))
    return percorso


@pytest.fixture()
def slegato(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setattr(server, "CACHE_DIR", tmp_path / "cache")
    return TestClient(
        create_app(
            None,
            radice_corse=tmp_path / "runs",
        ),
        base_url=BASE_LOCALE,
        raise_server_exceptions=False,
    )


def test_senza_configurazione_lo_stato_dice_che_non_c_e_una_corsa(slegato):
    """Prima schermata, non pagina d'errore: `legata` e' falso e basta."""
    corpo = slegato.get("/api/run").json()

    assert corpo["legata"] is False
    assert corpo.get("steps") is None


def test_l_elenco_delle_corse_di_una_radice_assente_e_vuoto(slegato):
    """Ingresso degenere: nessuna cartella runs/ sul disco."""
    corpo = slegato.get("/api/corse").json()

    assert corpo["corse"] == []
    assert corpo["corrente"] is None


def test_senza_corsa_aperta_non_c_e_nessun_deck_da_consegnare(slegato):
    """Ingresso degenere della tratta che esporta: senza corsa aperta non c'e'
    nessuna cartella da cui prendere il file, e la tratta lo dice invece di
    cercarlo in una cartella indovinata. Nell'interfaccia il comando non c'e'
    affatto: il pannello dello step vive dentro la schermata di lavoro, che a
    corsa slegata resta chiusa."""
    risposta = slegato.get("/api/deck")

    assert risposta.status_code == 400
    assert "nessuna corsa aperta" in risposta.json()["messaggio"]


def test_creare_una_corsa_scrive_il_config_e_lega_l_applicazione(slegato, nuvola, tmp_path):
    risposta = slegato.post("/api/corse", json={"nome": "provino", "nuvola": str(nuvola)})

    assert risposta.status_code == 200
    scritto = load_config(tmp_path / "runs" / "provino" / "config.yaml")
    assert scritto.input.path == nuvola
    assert scritto.run.out_dir == tmp_path / "runs" / "provino"
    stato = slegato.get("/api/run").json()
    assert stato["legata"] is True
    assert len(stato["steps"]) == 12


def test_una_corsa_creata_compare_nell_elenco_con_la_sua_nuvola(slegato, nuvola):
    slegato.post("/api/corse", json={"nome": "provino", "nuvola": str(nuvola)})

    corpo = slegato.get("/api/corse").json()

    assert [voce["nome"] for voce in corpo["corse"]] == ["provino"]
    assert corpo["corse"][0]["nuvola"] == str(nuvola)
    assert corpo["corse"][0]["errore"] is None
    assert corpo["corrente"] == "provino"


def test_un_nome_gia_occupato_e_rifiutato_invece_di_sovrascrivere(slegato, nuvola):
    """`runs/lab_crop` e `runs/muro` sono corse di riferimento di sola lettura:
    una sovrascrittura silenziosa qui cancellerebbe un risultato di tesi."""
    slegato.post("/api/corse", json={"nome": "provino", "nuvola": str(nuvola)})

    risposta = slegato.post("/api/corse", json={"nome": "provino", "nuvola": str(nuvola)})

    assert risposta.status_code == 400
    assert "provino" in risposta.json()["messaggio"]


def test_una_nuvola_inesistente_e_rifiutata_prima_di_scrivere(slegato, tmp_path):
    risposta = slegato.post(
        "/api/corse", json={"nome": "provino", "nuvola": str(tmp_path / "assente.ply")}
    )

    assert risposta.status_code == 400
    assert not (tmp_path / "runs" / "provino").exists()


def test_una_cartella_al_posto_della_nuvola_e_rifiutata(slegato, tmp_path):
    risposta = slegato.post("/api/corse", json={"nome": "provino", "nuvola": str(tmp_path)})

    assert risposta.status_code == 400
    assert not (tmp_path / "runs" / "provino").exists()


def test_un_formato_non_letto_dal_programma_e_rifiutato(slegato, tmp_path):
    estranea = tmp_path / "scansione.e57"
    estranea.write_bytes(b"non importa")

    risposta = slegato.post("/api/corse", json={"nome": "provino", "nuvola": str(estranea)})

    assert risposta.status_code == 400
    assert ".pcd" in risposta.json()["messaggio"]


@pytest.mark.parametrize("nome", ["..", "fuori/provino", "", "spazio vietato"])
def test_un_nome_di_corsa_fuori_tabella_e_rifiutato(slegato, nuvola, nome):
    """Il nome diventa una cartella: senza vincolo scrive fuori da `runs/`."""
    risposta = slegato.post("/api/corse", json={"nome": nome, "nuvola": str(nuvola)})

    assert risposta.status_code in (400, 422)


def test_aprire_una_corsa_esistente_la_lega(slegato, nuvola, tmp_path):
    slegato.post("/api/corse", json={"nome": "prima", "nuvola": str(nuvola)})
    slegato.post("/api/corse", json={"nome": "seconda", "nuvola": str(nuvola)})

    risposta = slegato.put("/api/corrente", json={"nome": "prima"})

    assert risposta.status_code == 200
    assert slegato.get("/api/corse").json()["corrente"] == "prima"
    assert slegato.get("/api/config").json()["run"]["out_dir"] == (
        tmp_path / "runs" / "prima"
    ).as_posix()


def test_aprire_una_corsa_che_non_c_e_e_un_rifiuto_leggibile(slegato):
    risposta = slegato.put("/api/corrente", json={"nome": "mai-vista"})

    assert risposta.status_code == 400
    assert "mai-vista" in risposta.json()["messaggio"]


def test_una_corsa_col_config_illeggibile_non_nasconde_le_altre(slegato, nuvola, tmp_path):
    """Ingresso degenere: uno yaml troncato da un processo ucciso."""
    slegato.post("/api/corse", json={"nome": "sana", "nuvola": str(nuvola)})
    rotta = tmp_path / "runs" / "rotta"
    rotta.mkdir(parents=True)
    (rotta / "config.yaml").write_text("input: {path:", encoding="utf-8")

    corse = {voce["nome"]: voce for voce in slegato.get("/api/corse").json()["corse"]}

    assert corse["sana"]["errore"] is None
    assert corse["rotta"]["errore"]
    assert corse["rotta"]["nuvola"] is None


def test_una_cartella_senza_config_non_e_una_corsa(slegato, tmp_path):
    (tmp_path / "runs" / "artefatti-orfani").mkdir(parents=True)

    assert slegato.get("/api/corse").json()["corse"] == []


def test_con_una_configurazione_all_avvio_lo_stato_e_gia_legato(tmp_path, monkeypatch):
    """Controprova: la forma vecchia, `serve config.yaml`, continua a valere."""
    cfg = PipelineConfig(input=InputConfig(path=tmp_path / "nuvola.ply"))
    cfg.run.out_dir = tmp_path / "corsa"
    save_config(cfg, tmp_path / "config.yaml")
    monkeypatch.setattr(server, "CACHE_DIR", tmp_path / "cache")
    cliente = TestClient(create_app(tmp_path / "config.yaml"), base_url=BASE_LOCALE, raise_server_exceptions=False)

    assert cliente.get("/api/run").json()["legata"] is True


@pytest.mark.parametrize("nome", ["127.0.0.1", "localhost", "127.0.0.1:8765"])
def test_il_server_risponde_ai_nomi_locali(tmp_path, monkeypatch, nome):
    """Il controllo che smentisce quello sotto: un guardiano che rifiuta tutto
    passerebbe il test del rifiuto senza proteggere niente."""
    monkeypatch.setattr(server, "CACHE_DIR", tmp_path / "cache")
    cliente = TestClient(
        create_app(None, radice_corse=tmp_path / "runs"), raise_server_exceptions=False
    )

    assert cliente.get("/api/run", headers={"host": nome}).status_code == 200


@pytest.mark.parametrize("nome", ["testserver", "attaccante.example", "meshrec.evil.com"])
def test_un_host_che_non_e_locale_e_rifiutato(tmp_path, monkeypatch, nome):
    """DNS rebinding: un dominio ostile che risolve su 127.0.0.1 rende le
    richieste same-origin e salta il preflight che chiude il CSRF classico.
    Da li' una pagina qualunque enumererebbe i percorsi assoluti del disco,
    creerebbe corse e lancerebbe sottoprocessi. E' il nome nell'Host, non
    l'indirizzo del chiamante, l'unica cosa che distingue i due casi.
    """
    monkeypatch.setattr(server, "CACHE_DIR", tmp_path / "cache")
    cliente = TestClient(
        create_app(None, radice_corse=tmp_path / "runs"), raise_server_exceptions=False
    )

    risposta = cliente.get("/api/corse", headers={"host": nome})

    assert risposta.status_code == 403
    assert nome in risposta.json()["messaggio"]


def test_una_corsa_di_riferimento_si_apre_ma_non_si_riscrive(slegato, nuvola, tmp_path):
    """`runs/muro` e `runs/lab_crop` sono risultati che finiscono in tesi.

    La sentinella li apre in lettura: la corsa si guarda, ma le tratte che
    scrivono si fermano dicendo perche', invece di riscrivere un risultato con
    un clic sbagliato in sede di discussione.
    """
    slegato.post("/api/corse", json={"nome": "riferimento", "nuvola": str(nuvola)})
    (tmp_path / "runs" / "riferimento" / server.SENTINELLA_SOLA_LETTURA).touch()
    slegato.put("/api/corrente", json={"nome": "riferimento"})

    assert slegato.get("/api/corse").json()["corse"][0]["riferimento"] is True
    # Leggere si', sempre.
    assert slegato.get("/api/config").status_code == 200
    for tratta in ("/api/step/1", "/api/step/1/from"):
        risposta = slegato.post(tratta)
        assert risposta.status_code == 400, tratta
        assert "sola lettura" in risposta.json()["messaggio"], tratta
    scrittura = slegato.put("/api/config", json=slegato.get("/api/config").json())
    assert scrittura.status_code == 400
    assert "sola lettura" in scrittura.json()["messaggio"]


def test_una_corsa_senza_sentinella_resta_scrivibile(slegato, nuvola):
    """Il controllo che smentisce: la sentinella deve fermare quelle marcate,
    non tutte."""
    slegato.post("/api/corse", json={"nome": "normale", "nuvola": str(nuvola)})

    assert slegato.get("/api/corse").json()["corse"][0]["riferimento"] is False
    assert slegato.put("/api/config", json=slegato.get("/api/config").json()).status_code == 200


def test_le_tratte_che_scrivono_si_fermano_anche_senza_una_corsa(slegato):
    """A legame vuoto il Worker lanciava `meshrec.cli run None`: un 200 che non
    eseguiva niente e lasciava il lavoratore occupato, cosi' che la richiesta
    successiva rispondeva «uno step sta gia' girando»."""
    for tratta in ("/api/step/1", "/api/step/1/from"):
        risposta = slegato.post(tratta)
        assert risposta.status_code == 400, tratta
        assert "nessuna corsa" in risposta.json()["messaggio"], tratta


def test_il_flusso_degli_eventi_non_cade_senza_una_corsa(slegato):
    """L'interfaccia apre l'EventSource al caricamento del modulo, quindi anche
    sulla schermata d'ingresso. `corrente()` sollevava dentro il generatore,
    cioe' dopo che le intestazioni erano partite: il gestore generico non lo
    poteva piu' convertire e il browser riceveva 200 con corpo vuoto,
    riconnettendo ogni tre secondi.
    """
    risposta = slegato.get("/api/events?max_eventi=1")

    assert risposta.status_code == 200
    assert '"legata": false' in risposta.text
    assert '"steps": []' in risposta.text


def test_l_errore_di_una_configurazione_rotta_non_e_il_verbale_di_pydantic(slegato, tmp_path):
    """Chi apre il programma deve leggere quale campo e perche', non imparare
    pydantic: `str(ValidationError)` porta il tipo interno, il valore ricevuto e
    un collegamento alla documentazione, e reso in un `<small>` collassa tutto
    su una riga."""
    rotta = tmp_path / "runs" / "rotta"
    rotta.mkdir(parents=True)
    (rotta / "config.yaml").write_text(
        "input:\n  path: nuvola.ply\n  scale: nonumero\n", encoding="utf-8"
    )

    errore = slegato.get("/api/corse").json()["corse"][0]["errore"]

    # Per etichetta e non per chiave, come ogni altro rifiuto di questo server.
    assert errore.startswith("fattore di scala verso i millimetri:")
    assert "errors.pydantic.dev" not in errore
    assert "\n" not in errore


def test_un_percorso_vuoto_non_diventa_il_punto(slegato):
    """`Path("")` e' `PosixPath('.')`: il campo lasciato vuoto tornava indietro
    come «'.' non e' un file», cioe' un punto comparso dal nulla."""
    risposta = slegato.post("/api/corse", json={"nome": "provino", "nuvola": "   "})

    assert risposta.status_code == 400
    messaggio = risposta.json()["messaggio"]
    assert "'.'" not in messaggio
    assert "percorso" in messaggio


@pytest.mark.parametrize("nome", ["...", "....."])
def test_un_nome_di_soli_punti_e_rifiutato(slegato, nuvola, nome):
    """Il punto e' ammesso dalla tabella -- `lab.v2` e' legittimo -- quindi il
    solo pattern lasciava passare anche i nomi di soli punti. Su POSIX `...` e'
    una cartella letterale, su Win32 i punti finali vengono normalizzati via."""
    risposta = slegato.post("/api/corse", json={"nome": nome, "nuvola": str(nuvola)})

    assert risposta.status_code == 422


def test_un_nome_col_punto_resta_legittimo(slegato, nuvola, tmp_path):
    """Il controllo che smentisce: si vietano i passi dell'albero, non il punto."""
    risposta = slegato.post("/api/corse", json={"nome": "lab.v2", "nuvola": str(nuvola)})

    assert risposta.status_code == 200
    assert (tmp_path / "runs" / "lab.v2" / "config.yaml").is_file()


def test_scrivere_la_configurazione_senza_una_corsa_e_un_rifiuto_leggibile(slegato):
    """Ingresso degenere: la PUT arriva mentre l'applicazione non e' legata.

    `save_config(nuova, None)` cadrebbe con un TypeError, che dice al browser
    che il programma si e' rotto invece di dirgli che non ha aperto una corsa.
    """
    cfg = PipelineConfig(input=InputConfig(path=Path("nuvola.ply")))

    risposta = slegato.put("/api/config", json=cfg.model_dump(mode="json"))

    assert risposta.status_code == 400
    assert "nessuna corsa" in risposta.json()["messaggio"]


def test_il_cambio_di_corsa_sposta_anche_le_metriche(slegato, nuvola, tmp_path):
    """Il legame e' mutabile, e ogni tratta deve leggere la corsa di adesso.

    `/api/config` e' gia' provata sopra; le metriche sono l'altra meta' della
    pagina, e servirle dalla corsa precedente farebbe leggere un risultato
    attribuendolo alla scansione sbagliata.
    """
    import json

    slegato.post("/api/corse", json={"nome": "prima", "nuvola": str(nuvola)})
    slegato.post("/api/corse", json={"nome": "seconda", "nuvola": str(nuvola)})
    for nome, punti in (("prima", 1), ("seconda", 2)):
        (tmp_path / "runs" / nome / "metrics.json").write_text(
            json.dumps({"01_load": {"points": punti}}), encoding="utf-8"
        )

    slegato.put("/api/corrente", json={"nome": "prima"})

    assert slegato.get("/api/metrics").json()["01_load"]["points"] == 1


# --- Sfoglia: il selettore file di sistema --------------------------------
#
# Il selettore vero apre una finestra e aspetta un essere umano, quindi nessun
# test lo lancia davvero: si sostituisce `subprocess.run`, che e' il confine
# fra il programma e il sistema. Cio' che resta sotto prova e' tutto quello che
# sta da questa parte del confine -- la cartella iniziale scelta, il contratto
# della risposta, i tre modi in cui puo' non aprirsi.


def _selettore_finto(uscita="", codice=0, stderr="", solleva=None):
    """Rimpiazza il sottoprocesso e registra con che argomenti e' stato chiamato."""
    chiamate = []

    def finto(comando, **kwargs):
        chiamate.append((comando, kwargs))
        if solleva is not None:
            raise solleva
        return subprocess.CompletedProcess(comando, codice, uscita, stderr)

    finto.chiamate = chiamate
    return finto


def test_sfogliare_restituisce_il_percorso_scelto(slegato, monkeypatch, tmp_path):
    scelta = tmp_path / "scansione.ply"
    monkeypatch.setattr(server.subprocess, "run", _selettore_finto(uscita=f"{scelta}\n"))

    corpo = slegato.post("/api/sfoglia", json={"iniziale": ""}).json()

    assert corpo["percorso"] == str(scelta)


def test_annullare_il_selettore_non_e_un_errore(slegato, monkeypatch):
    """Chiudere la finestra deve lasciare il campo com'era, non svuotarlo ne'
    far comparire un rifiuto: e' l'esito piu' comune di un clic per sbaglio."""
    monkeypatch.setattr(server.subprocess, "run", _selettore_finto(uscita=""))

    risposta = slegato.post("/api/sfoglia", json={"iniziale": ""})

    assert risposta.status_code == 200
    assert risposta.json()["percorso"] is None


def test_il_selettore_riapre_nella_cartella_del_percorso_gia_battuto(
    slegato, monkeypatch, nuvola
):
    finto = _selettore_finto(uscita="")
    monkeypatch.setattr(server.subprocess, "run", finto)

    slegato.post("/api/sfoglia", json={"iniziale": str(nuvola)})

    # L'ultimo argomento del comando e' `initialdir`: la cartella del file, non
    # il file, e non la radice da cui gira il server.
    assert finto.chiamate[0][0][-1] == str(nuvola.parent)


def test_una_cartella_iniziale_inesistente_ripiega_invece_di_rompere(slegato, monkeypatch):
    """Ingresso degenere: il campo porta un percorso battuto a meta'."""
    finto = _selettore_finto(uscita="")
    monkeypatch.setattr(server.subprocess, "run", finto)

    risposta = slegato.post("/api/sfoglia", json={"iniziale": "/questo/non/esiste/x.ply"})

    assert risposta.status_code == 200
    assert Path(finto.chiamate[0][0][-1]).is_dir()


def test_senza_tkinter_lo_dice_e_manda_a_scrivere_il_percorso(slegato, monkeypatch):
    """Alcune build di Python non hanno Tk, e una sessione remota non ha uno
    schermo a cui attaccarsi. Nessuno dei due impedisce di lavorare: il campo
    resta scrivibile e il messaggio lo dice, invece di lasciare il bottone muto.
    """
    monkeypatch.setattr(
        server.subprocess,
        "run",
        _selettore_finto(
            codice=1,
            stderr="Traceback (most recent call last):\n  ...\nModuleNotFoundError: No module named 'tkinter'\n",
        ),
    )

    risposta = slegato.post("/api/sfoglia", json={"iniziale": ""})

    assert risposta.status_code == 400
    messaggio = risposta.json()["messaggio"]
    assert "ModuleNotFoundError: No module named 'tkinter'" in messaggio
    assert "scrivi il percorso" in messaggio
    # La riga decisiva, non le venti che dicono da dove.
    assert "Traceback" not in messaggio


def test_un_dialogo_lasciato_aperto_non_blocca_il_server(slegato, monkeypatch):
    monkeypatch.setattr(
        server.subprocess,
        "run",
        _selettore_finto(solleva=subprocess.TimeoutExpired(cmd="python", timeout=120)),
    )

    risposta = slegato.post("/api/sfoglia", json={"iniziale": ""})

    assert risposta.status_code == 400
    assert "120" in risposta.json()["messaggio"]
    # Il server risponde ancora: il timeout ha ucciso il sottoprocesso, non lui.
    assert slegato.get("/api/run").status_code == 200


def test_il_selettore_gira_fuori_dal_processo_del_server():
    """Non e' un dettaglio di stile: su macOS Tk pretende il thread principale
    del processo, e FastAPI esegue gli endpoint sincroni in un threadpool.
    `tkinter` chiamato li' dentro non fa cadere la richiesta, fa cadere il
    processo. Il giorno che qualcuno lo «semplifichi» in una chiamata diretta,
    questo test lo dice prima dell'utente.
    """
    sorgente = Path(server.__file__).read_text(encoding="utf-8")

    assert "import tkinter" not in sorgente.replace(server._SELETTORE, "")
    assert "askopenfilename" not in sorgente.replace(server._SELETTORE, "")
    assert "timeout=SECONDI_SELETTORE" in sorgente


def test_i_launcher_non_chiedono_una_configurazione():
    """Il doppio clic deve arrivare alla schermata d'ingresso, non a un dialogo.

    Chi riceve una scansione non ha uno yaml da scegliere: `meshrec serve`
    senza argomenti apre l'elenco delle corse e la creazione da un file di
    punti. I due launcher passano solo quello che ricevono (`"$@"` e `%*`, che
    al doppio clic sono vuoti) e non nominano nessun file di configurazione.

    La riga sul `.bat` non e' cosmetica: `>/dev/null` e' sintassi Unix, e
    `cmd.exe` la legge come il percorso `.\\dev\\null`. La cartella non esiste,
    la redirezione fallisce, `errorlevel` va a 1 e il controllo su `uv`
    scattava sempre -- il launcher dichiarava uv assente anche quando c'era.
    """
    radice = Path(__file__).resolve().parents[1]
    bundle_rel = "MeshRec.app/Contents/MacOS/MeshRec"
    bundle = (radice / bundle_rel).read_text(encoding="utf-8")
    bat = (radice / "MeshRec.bat").read_text(encoding="utf-8")

    assert 'uv run meshrec serve "$@"' in bundle
    assert "uv run meshrec serve %*" in bat

    # Sulle sole righe eseguibili: un commento che cita `casi/lab_telaio.yaml`
    # come esempio spiega, non passa niente al programma.
    def istruzioni(testo, prefissi):
        return [
            riga for riga in testo.splitlines()
            if riga.strip() and not riga.strip().lower().startswith(prefissi)
        ]

    corpo_bat = "\n".join(istruzioni(bat, ("rem", "@rem")))
    for corpo, nome in (
        ("\n".join(istruzioni(bundle, ("#",))), bundle_rel),
        (corpo_bat, "MeshRec.bat"),
    ):
        assert ".yaml" not in corpo, f"{nome} passa una configurazione al programma"
        assert "askopenfilename" not in corpo, f"{nome} apre un selettore file"
    # Solo sul .bat: `>/dev/null` nel bundle macOS e' legittimo e c'e'.
    assert "/dev/null" not in corpo_bat, "redirezione Unix in un file .bat"
    # Uno script del bundle senza bit di esecuzione non si apre col doppio
    # clic: il Finder lancia MeshRec.app ma il processo interno fallisce.
    assert os.access(radice / bundle_rel, os.X_OK), f"{bundle_rel} non e' eseguibile"
    # E il bit deve stare *nell'indice di git*, non solo su questo disco:
    # `core.fileMode` qui e' false, quindi il permesso locale non viene
    # registrato da solo e un clone fresco riceverebbe un 100644 inerte. Il
    # difetto e' esattamente di quelli che passano inosservati: il file gira
    # sulla macchina di chi lo scrive e non su quella di chi lo riceve.
    modo = subprocess.run(
        ["git", "ls-files", "-s", bundle_rel],
        cwd=radice, capture_output=True, text=True, check=True,
    ).stdout.split()
    assert modo and modo[0] == "100755", (
        f"{bundle_rel} e' {modo[0] if modo else 'assente'} nell'indice di git, "
        "non 100755: su un clone fresco il doppio clic non lo apre"
    )


def test_la_riga_di_comando_accetta_serve_senza_configurazione():
    from meshrec.cli import _build_parser

    assert _build_parser().parse_args(["serve"]).config is None
    assert _build_parser().parse_args(["serve", "config.yaml"]).config == Path("config.yaml")
