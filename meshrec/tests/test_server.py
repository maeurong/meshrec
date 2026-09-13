"""Endpoint del server. Il contratto vale sulla tratta, non sulla funzione."""

from __future__ import annotations

import hashlib
import json
import re
import shutil
import subprocess
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from meshrec.app import immagini, server
from meshrec.app.server import create_app
from meshrec.core.config import InputConfig, PipelineConfig, load_config, save_config


@pytest.fixture()
def cliente(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    cfg = PipelineConfig(input=InputConfig(path=tmp_path / "nuvola.ply"))
    cfg.run.out_dir = tmp_path / "corsa"
    save_config(cfg, tmp_path / "config.yaml")
    # I-5 della revisione: CACHE_DIR e' una costante di modulo che punta a
    # meshrec/.cache/viewport/ per davvero. Senza questo dirottamento, ogni
    # test che chiama /api/cloud lascia una voce che nessuna pulizia
    # raggiungera' mai (la sorgente e' sotto tmp_path e sparisce col test).
    monkeypatch.setattr(server, "CACHE_DIR", tmp_path / "cache")
    # raise_server_exceptions=False: il gestore generico in server.py risponde
    # con 400 e corpo strutturato, ma starlette rilancia comunque l'eccezione
    # al chiamante quando questo flag e' vero (e' il predefinito), per dare a
    # chi testa la scelta di vederla. Qui si vuole il contratto HTTP che vede
    # il browser, non l'eccezione interna.
    return TestClient(
        create_app(
            tmp_path / "config.yaml",
            radice_corse=tmp_path / "runs",
        ),
        # Il server risponde solo a un nome locale (middleware
        # `solo_dal_calcolatore_locale`, contro il DNS rebinding). Il
        # predefinito di TestClient e' `http://testserver`, che quel middleware
        # rifiuta con 403 -- ed e' giusto: il banco deve parlare col server come
        # ci parla il browser vero.
        base_url="http://127.0.0.1",
        raise_server_exceptions=False,
    )


def test_la_radice_serve_l_interfaccia(cliente):
    risposta = cliente.get("/")
    assert risposta.status_code == 200
    assert "text/html" in risposta.headers["content-type"]


@pytest.mark.parametrize("percorso", [
    "/", "/ui/app.js", "/ui/viewport.js", "/ui/vendor/three.module.min.js",
])
def test_l_interfaccia_si_rivalida_sempre_e_non_esce_mai_dalla_cache(cliente, percorso):
    """Senza Cache-Control il browser applica la freschezza euristica sul
    Last-Modified: un F5 rivalida la pagina, non i moduli importati. Il caso
    del 09/09: viewport.js vecchio dalla cache con app.js nuovo, `vista.azzera
    is not a function`, sei PNG con «nessuna corsa» in testata. `no-cache` e
    non `no-store`: il browser tiene la copia e chiede se e' ancora buona."""
    risposta = cliente.get(percorso)
    assert risposta.status_code == 200
    assert risposta.headers["cache-control"] == "no-cache"
    assert "etag" in risposta.headers


@pytest.mark.parametrize("percorso", ["/ui/inesistente.js", "/ui/%2e%2e/pyproject.toml"])
def test_i_file_fuori_dall_interfaccia_restano_rifiutati(cliente, percorso):
    risposta = cliente.get(percorso)
    assert risposta.status_code == 400
    assert risposta.json()["errore"] == "FileNotFoundError"
    assert "cache-control" not in risposta.headers


def test_lo_stato_della_corsa_elenca_i_dodici_step(cliente):
    """STEP_KEYS finisce sul prior dello step 12, e /api/run le elenca tutte."""
    corpo = cliente.get("/api/run").json()
    assert len(corpo["steps"]) == 12
    assert corpo["steps"][0]["chiave"] == "01_load"
    assert {voce["stato"] for voce in corpo["steps"]} == {"mai eseguito"}


def test_la_configurazione_torna_intera(cliente):
    corpo = cliente.get("/api/config").json()
    assert set(corpo) >= {"input", "segment", "surface", "tet", "export"}


def test_scrivere_la_configurazione_invalida_gli_step_a_valle(cliente, tmp_path):
    prima = cliente.get("/api/config").json()
    prima["surface"]["poisson_depth"] = 7
    risposta = cliente.put("/api/config", json=prima)
    assert risposta.status_code == 200
    assert risposta.json()["surface"]["poisson_depth"] == 7
    assert cliente.get("/api/config").json()["surface"]["poisson_depth"] == 7


def test_una_configurazione_fuori_dominio_non_solleva_ma_spiega(cliente):
    guasta = cliente.get("/api/config").json()
    guasta["surface"]["poisson_depth"] = 99   # il modello ammette 4..14
    risposta = cliente.put("/api/config", json=guasta)
    assert risposta.status_code == 422
    # Per etichetta e non per chiave: e' la regola di PRODUCT.md, e vale anche
    # per il rifiuto che compare sotto la casella.
    assert "profondità dell'ottree di Poisson" in risposta.json()["messaggio"]


def test_una_regione_che_collide_con_lelset_fabbricato_e_rifiutata_dallendpoint(cliente):
    """`PUT /api/config` accetta un `PipelineConfig` intero dall'esterno: e' la
    via vera per cui un nome di regione sbagliato arriva al programma, e il
    rifiuto a video restava non provato -- il test di `tests/test_config.py`
    cita `/api/config` nel commento ma la PUT non la esercita.

    `ALL_WALL` e' l'unico `*ELSET` che il deck fabbrica da se': e' l'insieme
    che le regioni partizionano.

    Mutazione che lo uccide: togliere `ALL_WALL` da `NOMI_ELSET_FABBRICATI`.
    """
    guasta = cliente.get("/api/config").json()
    guasta["regioni"] = {"all_wall": {"membratura": 0}}
    risposta = cliente.put("/api/config", json=guasta)
    assert risposta.status_code == 422
    # Il messaggio si legge a video: nomina la regione, l'insieme con cui
    # collide e il tipo di insieme.
    assert "la regione" in risposta.text
    assert "ALL_WALL" in risposta.text
    assert "*ELSET" in risposta.text


# /api/events e' un generatore SSE senza fine: una GET secca lo terrebbe
# aperto e bloccherebbe la suite. Ha il proprio test dedicato, con un tetto
# agli eventi emessi. Tenere questo insieme corto: cio' che vi entra esce
# dal contratto.
STREAMING = {"/api/events"}


def test_avviare_uno_step_risponde_senza_bloccare(cliente):
    risposta = cliente.post("/api/step/1")
    assert risposta.status_code == 200
    assert risposta.json()["avviato"] == 1


def test_annullare_quando_non_gira_nulla_non_solleva(cliente):
    risposta = cliente.post("/api/cancel")
    assert risposta.status_code == 200
    assert risposta.json()["annullato"] is False


def test_lo_stream_degli_eventi_manda_lo_stato_e_si_chiude(cliente):
    with cliente.stream("GET", "/api/events?max_eventi=1") as risposta:
        assert risposta.status_code == 200
        assert "text/event-stream" in risposta.headers["content-type"]
        testo = "".join(risposta.iter_text())
    assert "event: stato" in testo
    assert '"in_corso"' in testo


def test_la_nuvola_dichiara_sempre_entrambi_i_conteggi(cliente, tmp_path):
    import numpy as np
    from meshrec.core import io, pipeline

    corsa = tmp_path / "corsa"
    punti = np.random.default_rng(0).random((50_000, 3)) * 100.0
    io.write_cloud(corsa / pipeline.ARTIFACTS[1], punti)

    risposta = cliente.get("/api/cloud/1?max_points=1000")
    assert risposta.status_code == 200
    assert int(risposta.headers["X-Points-Total"]) == 50_000
    disegnati = int(risposta.headers["X-Points-Drawn"])
    assert disegnati <= 1000
    assert len(risposta.content) == disegnati * 3 * 4


def test_la_seconda_richiesta_della_stessa_nuvola_non_ricalcola(cliente, tmp_path, monkeypatch):
    """I-1 della revisione: il guadagno del Task 6-bis vive nell'endpoint, non
    nella funzione. Un test che chiama solo decimate_file lascerebbe scoperte
    proprio le tre righe che lo producono in server.py."""
    import numpy as np
    from meshrec.core import io, pipeline, viewport

    corsa = tmp_path / "corsa"
    punti = np.random.default_rng(0).random((50_000, 3)) * 100.0
    io.write_cloud(corsa / pipeline.ARTIFACTS[2], punti)

    prima = cliente.get("/api/cloud/2?max_points=1000")
    assert prima.status_code == 200

    def _non_chiamarmi(*_args, **_kwargs):
        raise AssertionError("decimate non deve essere richiamata a cache calda")

    monkeypatch.setattr(viewport, "decimate", _non_chiamarmi)
    poi = cliente.get("/api/cloud/2?max_points=1000")
    # status_code == 200 e non solo "non solleva": con raise_server_exceptions
    # =False un errore diventa comunque un 400, che passerebbe inosservato
    # senza questa asserzione esplicita.
    assert poi.status_code == 200
    assert poi.content == prima.content
    assert poi.headers["X-Points-Drawn"] == prima.headers["X-Points-Drawn"]
    assert poi.headers["X-Points-Total"] == prima.headers["X-Points-Total"]


def test_max_points_zero_o_negativo_e_rifiutato_con_messaggio_chiaro(cliente, tmp_path):
    """M-11 della revisione: prima della guardia, max_points=0 dava
    ZeroDivisionError e un negativo TypeError su un numero complesso — la
    tratta reggeva (400 in entrambi i casi) ma il messaggio era opaco."""
    import numpy as np
    from meshrec.core import io, pipeline

    corsa = tmp_path / "corsa"
    punti = np.random.default_rng(0).random((100, 3)) * 10.0
    io.write_cloud(corsa / pipeline.ARTIFACTS[1], punti)

    for valore in (0, -5):
        risposta = cliente.get(f"/api/cloud/1?max_points={valore}")
        assert risposta.status_code == 400
        corpo = risposta.json()
        assert corpo["errore"] not in ("ZeroDivisionError", "TypeError")
        assert str(valore) in corpo["messaggio"]
        assert "positivo" in corpo["messaggio"]


def test_chiedere_la_nuvola_di_uno_step_mai_eseguito_non_solleva(cliente):
    risposta = cliente.get("/api/cloud/9")
    assert risposta.status_code == 400
    assert "errore" in risposta.json()


def test_chiedere_la_nuvola_di_uno_step_fuori_intervallo_spiega_quali_esistono(cliente):
    """Prima della guardia, uno step fuori intervallo faceva sollevare
    pipeline.ARTIFACTS[numero] con un KeyError generico ('99', senza
    contesto), che il gestore trasformava in un messaggio inutile per
    l'utente. Deve dire quali step esistono."""
    risposta = cliente.get("/api/cloud/99")
    assert risposta.status_code == 400
    corpo = risposta.json()
    assert corpo["errore"] != "KeyError"
    assert "99" in corpo["messaggio"]
    # "8" e' uno step valido e non e' una sottostringa di "99": a differenza
    # di "9", puo' davvero far fallire il test se l'elenco sparisse dal
    # messaggio (M-8 della revisione).
    assert "8" in corpo["messaggio"]


def test_la_mesh_torna_in_binario_con_i_conteggi(cliente, tmp_path):
    import open3d as o3d

    from meshrec.core import pipeline

    corsa = tmp_path / "corsa"
    corsa.mkdir()
    cubo = o3d.geometry.TriangleMesh.create_box(1.0, 1.0, 1.0)
    o3d.io.write_triangle_mesh(str(corsa / pipeline.ARTIFACTS[6]), cubo)

    risposta = cliente.get("/api/mesh/6")
    assert risposta.status_code == 200
    vertici = int(risposta.headers["X-Vertices"])
    triangoli = int(risposta.headers["X-Triangles"])
    assert vertici == 8 and triangoli == 12
    # Tre code, non due: posizioni, indici e — dal 04/09/2026 — le normali,
    # che sono un Float32 per componente per vertice come le posizioni.
    assert risposta.headers["X-Normals"] == "1"
    assert len(risposta.content) == (vertici * 3 + triangoli * 3 + vertici * 3) * 4


def test_lo_scarto_corrisponde_vertice_per_vertice_alla_superficie_servita(cliente, tmp_path):
    """La mappa dello scarto si posa sulle posizioni che /api/mesh/6 manda: se i
    due corpi non hanno la stessa lunghezza, il colore di un vertice finisce su
    un altro e la mappa indica il posto sbagliato senza nessun errore.

    La garanzia non e' un accordo fra i due gestori: leggono lo stesso file.
    Questo banco la esercita davvero, chiedendo i due corpi e rimisurando lo
    scarto sulle coordinate servite.

    La nuvola sposta un punto SI' e uno NO, e non tutti: traslata intera darebbe
    uno scarto costante, che passerebbe anche con la corrispondenza rotta. La
    prima stesura di questo banco l'ha fatto, e l'asserzione sulla varianza qui
    sotto e' quella che l'ha fermata.
    """
    import numpy as np
    import open3d as o3d

    from meshrec.core import io, pipeline, quality

    corsa = tmp_path / "corsa"
    corsa.mkdir()
    cubo = o3d.geometry.TriangleMesh.create_box(1.0, 1.0, 1.0)
    o3d.io.write_triangle_mesh(str(corsa / pipeline.ARTIFACTS[6]), cubo)
    punti = np.asarray(cubo.vertices).copy()
    punti[::2] += np.array([0.25, 0.0, 0.0])
    io.write_cloud(corsa / pipeline.ARTIFACTS[2], punti)

    mesh = cliente.get("/api/mesh/6")
    scarto = cliente.get("/api/scarto")
    assert scarto.status_code == 200, scarto.json()
    vertici = int(mesh.headers["X-Vertices"])
    valori = np.frombuffer(scarto.content, dtype="<f4")
    assert len(valori) == vertici

    posizioni = np.frombuffer(
        mesh.content[: vertici * 3 * 4], dtype="<f4"
    ).reshape(-1, 3).astype(np.float64)
    atteso = quality.vertex_deviation(posizioni, punti)
    np.testing.assert_allclose(valori, atteso, rtol=1e-5)
    # Non costante: un campo piatto renderebbe vacuo il confronto qui sopra.
    assert float(valori.max()) > float(valori.min())
    assert float(scarto.headers["X-Max"]) == pytest.approx(float(atteso.max()), rel=1e-5)


def test_lo_scarto_misura_la_coppia_che_lo_step_7_misura():
    """Quale superficie e quale nuvola non sono una scelta del server: sono la
    coppia che `pipeline.run` passa a `quality.geometric_error` allo step 7.

    Senza questo controllo la coppia resta scritta a mano in due posti. Cambiata
    la tabella della pipeline -- lo step 7 che ripartisse da un'altra
    superficie, o la nuvola di riferimento che diventasse un'altra -- il server
    continuerebbe a dipingere la vecchia, e il campo a video non sarebbe piu'
    quello che la tabella delle metriche accanto misura. Un colore che
    contraddice il numero che gli sta sotto, e nessuno dei due lo dice.
    """
    from meshrec.app import server
    from meshrec.core import pipeline

    assert server._SCARTO_MESH == pipeline._RESUME_MESH[7], (
        "lo step 7 non riparte piu' dalla superficie che il server dipinge"
    )
    assert pipeline.ARTIFACTS[server._SCARTO_NUVOLA] == "02_segmented.ply", (
        "la nuvola di riferimento dello scarto non e' piu' quella segmentata"
    )


def test_lo_scarto_senza_i_due_artefatti_dice_quale_manca(cliente, tmp_path):
    """Un rifiuto dichiarato e non una pagina bianca, come ogni altro gestore.

    E nomina lo step: «lo scarto non e' disponibile» lascerebbe l'utente a
    indovinare se manchi la superficie o la nuvola, cioe' se debba rieseguire
    dal 6 o dal 2 -- e rieseguire dal 2 riscrive tutto quello che c'e' sotto.
    """
    import numpy as np
    import open3d as o3d

    from meshrec.core import io, pipeline

    corsa = tmp_path / "corsa"
    corsa.mkdir()

    vuoto = cliente.get("/api/scarto")
    assert vuoto.status_code == 400
    assert "6" in vuoto.json()["messaggio"]

    # La superficie c'e', la nuvola no: il rifiuto cambia bersaglio.
    cubo = o3d.geometry.TriangleMesh.create_box(1.0, 1.0, 1.0)
    o3d.io.write_triangle_mesh(str(corsa / pipeline.ARTIFACTS[6]), cubo)
    mezzo = cliente.get("/api/scarto")
    assert mezzo.status_code == 400
    assert "02_segmented.ply" in mezzo.json()["messaggio"]

    # Con entrambi, passa: senza questa riga i due rifiuti sopra resterebbero
    # verdi anche se il gestore rifiutasse sempre.
    io.write_cloud(corsa / pipeline.ARTIFACTS[2], np.asarray(cubo.vertices))
    assert cliente.get("/api/scarto").status_code == 200


def test_chiedere_la_mesh_di_uno_step_senza_artefatto_non_solleva(cliente):
    risposta = cliente.get("/api/mesh/6")
    assert risposta.status_code == 400
    assert "errore" in risposta.json()


def test_chiedere_la_mesh_di_uno_step_fuori_intervallo_spiega_quali_esistono(cliente):
    """Stessa guardia di /api/cloud: senza, ARTIFACTS[99] darebbe un KeyError
    generico ('99', senza contesto) e il gestore lo mostrerebbe cosi'."""
    risposta = cliente.get("/api/mesh/99")
    assert risposta.status_code == 400
    corpo = risposta.json()
    assert corpo["errore"] != "KeyError"
    assert "99" in corpo["messaggio"]
    # "8" e' uno step valido e non e' una sottostringa di "99".
    assert "8" in corpo["messaggio"]


def _nuvola_un_cluster_e_rumore():
    """3.000 punti fitti nell'origine, 1.000 radi a 500 mm.

    Il secondo blocco e' disperso su 10 mm, quindi con eps = 4 x spaziatura
    DBSCAN non ci trova nessun nucleo: e' rumore, non un secondo cluster.
    Misurato: un cluster da 2.992 punti e 1.008 punti di rumore. Un clic che
    ricada li' dentro DEVE ottenere 400.

    Esiste come funzione, e non copiata in ogni test, perche' tre docstring
    affermano "stessa nuvola" l'una dell'altra: cosi' l'affermazione e' vera
    per costruzione invece che per manutenzione.
    """
    import numpy as np

    primo = np.random.default_rng(0).random((3_000, 3)) * 10.0
    secondo = np.random.default_rng(1).random((1_000, 3)) * 10.0 + 500.0
    return np.vstack([primo, secondo])


def _nuvola_due_cluster():
    """Come sopra, ma il secondo blocco e' disperso su 7 mm invece che 10.

    Tre millimetri di differenza cambiano la natura del dato, non la sua
    taglia: a 7 mm il secondo blocco supera min_points e diventa un cluster
    vero, quindi esiste un cluster_index 1 su cui puntare. Serve ai test che
    devono distinguere una scrittura corretta da un "scrivi sempre 0", che
    sulla nuvola a 10 mm resterebbe invisibile per coincidenza.
    """
    import numpy as np

    primo = np.random.default_rng(0).random((3_000, 3)) * 10.0
    secondo = np.random.default_rng(1).random((1_000, 3)) * 7.0 + 500.0
    return np.vstack([primo, secondo])


def _prepara_click_semplice(cliente, corsa: Path, punti) -> None:
    """Scrive la stessa nuvola come ingresso grezzo (step 1, ARTIFACTS[1]) e
    come uscita segmentata (step 2, ARTIFACTS[2]): dopo l'allineamento
    (task-11b), /api/cluster legge sempre ARTIFACTS[1] e rifa'
    remove_outliers -> crop_box -> extract_planes -> cluster (vedi
    server.scegli_cluster). I test di questa sezione, tranne quello
    dell'allineamento stesso, esercitano solo la REGOLA DI VOTO sul gruppo
    disegnato: con plane_max_count=0 e un outlier_std_ratio enorme quella
    tratta diventa un non-operazione, e la nuvola che arriva davvero a
    segment.cluster torna a essere esattamente quella scritta qui, come lo
    era prima dell'allineamento (quando l'endpoint clusterizzava
    ARTIFACTS[2] senza altro).
    """
    from meshrec.core import io, pipeline

    io.write_cloud(corsa / pipeline.ARTIFACTS[1], punti)
    io.write_cloud(corsa / pipeline.ARTIFACTS[2], punti)
    attuale = cliente.get("/api/config").json()
    attuale["segment"]["plane_max_count"] = 0
    attuale["segment"]["outlier_std_ratio"] = 1_000_000.0
    risposta = cliente.put("/api/config", json=attuale)
    assert risposta.status_code == 200


def _clusterizza_come_l_endpoint(corsa: Path, cfg):
    """Rifa', fuori dall'endpoint, esattamente il calcolo che /api/cluster fa
    dopo l'allineamento: stessa base di spaziatura (ARTIFACTS[1], grezzo) e
    la stessa sequenza remove_outliers -> crop_box -> extract_planes ->
    cluster. Oracolo indipendente per i test che pretendono un
    cluster_index preciso, senza duplicare la logica dell'endpoint a mano.
    """
    from meshrec.core import io, pipeline, segment

    grezzi, _normali = io.read_cloud(corsa / pipeline.ARTIFACTS[1])
    spaziatura = io.mean_spacing(grezzi, cfg.input.spacing_sample, cfg.input.seed)
    puliti, _metriche_outlier = segment.remove_outliers(grezzi, cfg.segment)
    ritagliati, _metriche_crop = segment.crop_box(puliti, cfg.segment)
    _piani, residuo, _metriche_piani = segment.extract_planes(ritagliati, cfg.segment, spaziatura)
    insiemi, metriche = segment.cluster(residuo, cfg.segment, spaziatura)
    return insiemi, metriche, spaziatura


def test_il_clic_risolve_il_punto_disegnato_a_un_cluster(cliente, tmp_path):
    """Un clic dentro il blocco fitto risolve al cluster che lo contiene.

    Attenzione a come e' fatta la nuvola, perche' e' la stessa dei tre test
    piu' sotto: il secondo blocco NON e' un secondo cluster. Mille punti
    sparsi in dieci millimetri cubi sono troppo radi per l'eps che
    segment.cluster deriva dalla spaziatura, e DBSCAN li classifica in blocco
    come rumore (misurato: un solo cluster da 2992 punti, 1008 di rumore).
    Un clic che ci cadesse dentro dovrebbe dare 400, non un secondo cluster.

    Il punto disegnato 0 cade nel blocco fitto perche' viewport.decimate
    ordina i gruppi per indice pieno minimo, e l'indice pieno 0 e' del primo
    blocco: senza quel contratto l'indice 0 dipenderebbe dalla hash map di
    Open3D e quindi dalla piattaforma.
    """

    corsa = tmp_path / "corsa"
    _prepara_click_semplice(cliente, corsa, _nuvola_un_cluster_e_rumore())

    cliente.get("/api/cloud/2?max_points=2000")     # popola la mappa
    risposta = cliente.post("/api/cluster", json={"punto": 0})
    assert risposta.status_code == 200
    corpo = risposta.json()
    # Zero e non "0 oppure 1": su questa nuvola DBSCAN trova un cluster solo
    # (misurato sopra), quindi ammettere un 1 contraddirebbe la docstring.
    assert corpo["cluster_index"] == 0
    assert corpo["cluster_points"] > 0


def test_un_clic_senza_mappa_caricata_non_solleva(cliente):
    risposta = cliente.post("/api/cluster", json={"punto": 0})
    assert risposta.status_code == 400


def test_un_clic_senza_mappa_solleva_anche_con_la_nuvola_gia_su_disco(cliente, tmp_path):
    """Isola la sola variabile della mappa: qui, a differenza del test sopra,
    02_segmented.ply esiste davvero ed e' leggibile. Senza questo test la
    guardia sulla mappa mancante puo' sparire dall'endpoint senza che la
    suite se ne accorga: il 400 del test sopra arriva anche da un file
    assente (io.read_cloud solleva comunque), non prova la guardia. Qui
    l'unica cosa che manca e' che /api/cloud/2 non e' mai stato chiamato, e
    deve bastare a dare 400: se la guardia venisse tolta, la lettura andrebbe
    a buon fine e la richiesta risponderebbe 200.
    """
    import numpy as np
    from meshrec.core import io, pipeline

    corsa = tmp_path / "corsa"
    punti = np.random.default_rng(0).random((200, 3)) * 10.0
    io.write_cloud(corsa / pipeline.ARTIFACTS[2], punti)

    risposta = cliente.post("/api/cluster", json={"punto": 0})
    assert risposta.status_code == 400


def test_il_clic_sul_gruppo_piccolo_risolve_al_cluster_piccolo(cliente, tmp_path):
    """Il controllo che smentisce (brief task-11a): il primo test passerebbe
    identico anche se l'endpoint ignorasse la mappa e rispondesse sempre col
    cluster piu' numeroso. Qui si clicca un indice disegnato che la mappa di
    decimazione fa risalire SOLO a indici del gruppo piccolo, e si pretende
    cluster_index == 1: nel ritorno di segment.cluster i gruppi sono
    ordinati per numerosita' decrescente (core/segment.py), quindi il gruppo
    piccolo non puo' mai finire in 0.

    Il gruppo piccolo qui e' 1 000 punti in un cubo da 7 mm e non da 10 mm
    come nel test del piano: con lo stesso cubo di 10 mm la densita' locale
    del gruppo piccolo (1 000 punti / 1000 mm^3) resta sotto la soglia che
    DBSCAN userebbe con cluster_min_points=50 e l'eps calcolato sulla
    spaziatura media DELLA NUVOLA MISTA (dominata dal gruppo grande, piu'
    denso): misurato, il gruppo piccolo cadrebbe intero nel rumore invece che
    in un proprio cluster, e il test non avrebbe piu' un cluster piccolo da
    pretendere. A 7 mm la densita' dei due gruppi e' paragonabile
    (3 000/1000mm^3 contro 1 000/343mm^3) e DBSCAN, coi predefiniti di
    SegmentConfig e senza toccare core.segment.cluster, trova davvero due
    cluster: misurato qui, 2 747 e 792 punti.

    L'indice disegnato non si legge da uno stato interno del server: si
    ricalcola con la stessa funzione (viewport.decimate) sugli stessi
    argomenti che l'endpoint /api/cloud/2 ha gia' usato (spacing_sample=20000,
    seed=0, i predefiniti di InputConfig che 'cliente' non sovrascrive), sulla
    nuvola riletta da disco esattamente come la rilegge il server: read_cloud
    passa per Open3D e non garantisce di restituire gli stessi byte scritti.
    """
    from meshrec.core import io, pipeline, viewport

    corsa = tmp_path / "corsa"
    _prepara_click_semplice(cliente, corsa, _nuvola_due_cluster())

    risposta_nuvola = cliente.get("/api/cloud/2?max_points=2000")
    assert risposta_nuvola.status_code == 200

    punti_letti, _normali = io.read_cloud(corsa / pipeline.ARTIFACTS[2])
    spaziatura = io.mean_spacing(punti_letti, 20_000, 0)
    _ridotti, gruppi, _voxel = viewport.decimate(punti_letti, 2_000, spaziatura)
    # Solo un gruppo i cui indici pieni appartengono TUTTI al secondo blocco:
    # i due blocchi sono a 500 mm di distanza e il voxel di decimazione e'
    # microscopico al confronto, quindi nessun gruppo dovrebbe mischiarli, ma
    # 'all' (e non 'any') lo pretende invece di assumerlo.
    disegnato = next(i for i, gruppo in enumerate(gruppi) if (gruppo >= 3_000).all())

    risposta = cliente.post("/api/cluster", json={"punto": disegnato})
    assert risposta.status_code == 200
    corpo = risposta.json()
    assert corpo["cluster_index"] == 1
    assert corpo["cluster_points"] < 2_000


def test_il_clic_sul_gruppo_a_cavallo_risolve_alla_maggioranza(cliente, tmp_path):
    """Task 11a, giro 2 (bloccante misurato in task-11a-review.md): un gruppo
    di decimazione a cavallo di un confine fra due cluster deve risolvere al
    cluster della MAGGIORANZA dei suoi punti pieni, non al primo.

    max_points=1 forza tutta la nuvola in un solo punto disegnato: il gruppo
    unico contiene sia il blocco minoranza (indici 0-799, primi nell'array)
    sia il blocco maggioranza (indici 800-3799). Misurato fuori dal test:
    DBSCAN trova due cluster, 2 875 punti (maggioranza, dal blocco grande) e
    238 punti (minoranza, dal blocco piccolo), e il PRIMO indice del gruppo
    (0) appartiene al cluster di minoranza (238). Con `pieno = gruppi[0][0]`
    (il codice del primo giro) la risposta sarebbe cluster_index=1 (238
    punti): questo test pretende il cluster di maggioranza, indice 0.
    """
    import numpy as np

    corsa = tmp_path / "corsa"
    minoranza = np.random.default_rng(1).random((800, 3)) * 7.0
    maggioranza = np.random.default_rng(2).random((3_000, 3)) * 10.0 + 500.0
    _prepara_click_semplice(cliente, corsa, np.vstack([minoranza, maggioranza]))

    risposta_nuvola = cliente.get("/api/cloud/2?max_points=1")
    assert risposta_nuvola.status_code == 200

    risposta = cliente.post("/api/cluster", json={"punto": 0})
    assert risposta.status_code == 200
    corpo = risposta.json()
    assert corpo["cluster_index"] == 0
    assert corpo["cluster_points"] > 2_000


def test_il_clic_sul_gruppo_in_pareggio_risolve_al_cluster_piu_popoloso_in_assoluto(cliente, tmp_path):
    """Il pareggio che la maggioranza da sola non decide (dichiarato in
    server.py, scegli_cluster): due copie traslate dello stesso blocco
    danno per costruzione due cluster della stessa numerosita' (misurato:
    1 375 e 1 375). A parita' di voti nel gruppo vince il cluster piu'
    popoloso IN ASSOLUTO; qui i due sono identici, quindi vince l'indice
    piu' basso (0), la scelta deterministica dichiarata.
    """
    import numpy as np

    corsa = tmp_path / "corsa"
    base = np.random.default_rng(0).random((1_500, 3)) * 10.0
    copia = base.copy()
    copia[:, 0] += 500.0
    _prepara_click_semplice(cliente, corsa, np.vstack([base, copia]))

    risposta_nuvola = cliente.get("/api/cloud/2?max_points=1")
    assert risposta_nuvola.status_code == 200

    risposta = cliente.post("/api/cluster", json={"punto": 0})
    assert risposta.status_code == 200
    corpo = risposta.json()
    # Precondizione: il pareggio e' avvenuto davvero, non solo per fortuna.
    assert corpo["clusters_found"] == 2
    assert corpo["cluster_sizes"][0] == corpo["cluster_sizes"][1]
    assert corpo["cluster_index"] == 0


def test_il_clic_sul_pareggio_esatto_fra_rumore_e_cluster_risolve_al_cluster(cliente, tmp_path):
    """Mutazione D del revisore (task-11a-fix-2-review.md): il commento di
    scegli_cluster dichiara "a parita' fra il cluster piu' votato e il
    rumore vince il cluster", ma nessun test costruiva il confine ESATTO
    (tutti i test esistenti hanno o rumore strettamente minoritario o
    maggioranza schiacciante). Qui un blocco di 55 punti fitti (stesso
    raggio 3 mm del test della maggioranza-rumore, sopra cluster_min_points
    =50) forma un cluster vero, e una catena di ESATTAMENTE 55 punti isolati
    (passo 50 mm, oltre l'eps calcolato sulla spaziatura mista) resta tutta
    rumore: misurato fuori dal test, voti-cluster=55 e voti-rumore=55, un
    pareggio esatto, non una minoranza. Con max_points=1 l'intera nuvola
    (110 punti) e' un solo gruppo disegnato, come nel test della
    maggioranza-rumore sopra. La richiesta deve rispondere 200 col cluster:
    con `>=` al posto di `>` (la mutazione D) il pareggio si leggerebbe come
    rumore in maggioranza e risponderebbe 400.
    """
    import numpy as np

    corsa = tmp_path / "corsa"
    denso = np.random.default_rng(0).random((55, 3)) * 3.0
    catena = np.zeros((55, 3))
    catena[:, 0] = 300.0 + np.arange(55) * 50.0
    _prepara_click_semplice(cliente, corsa, np.vstack([denso, catena]))

    risposta_nuvola = cliente.get("/api/cloud/2?max_points=1")
    assert risposta_nuvola.status_code == 200

    risposta = cliente.post("/api/cluster", json={"punto": 0})
    assert risposta.status_code == 200
    corpo = risposta.json()
    # Precondizione: il pareggio e' avvenuto davvero (55 voti-cluster contro
    # 55 voti-rumore), non un rumore minoritario che sarebbe accettato
    # comunque anche senza la regola del confine.
    assert corpo["clusters_found"] == 1
    assert corpo["cluster_sizes"][0] == 55
    assert corpo["noise_points"] == 55
    assert corpo["cluster_index"] == 0


def test_il_clic_sul_pareggio_di_voti_fra_cluster_di_taglia_diversa_risolve_al_piu_popoloso(
    cliente, tmp_path, monkeypatch
):
    """Mutazione E del revisore (task-11a-fix-2-review.md), la piu'
    istruttiva: il test ufficiale del pareggio (sopra) costruisce due
    cluster di taglia ASSOLUTA identica, quindi passa anche senza il
    criterio di spareggio dichiarato (`-kv[0]` nel key del max()), per
    coincidenza fra le taglie e l'ordine di iterazione del Counter — non
    perche' la regola "vince il cluster piu' popoloso IN ASSOLUTO" sia
    verificata.

    Qui i due cluster hanno taglia assoluta DIVERSA (misurato: 2 781 e 797
    punti su questa nuvola), ma il gruppo disegnato e' costruito a mano
    (patch di viewport.decimate_file, non la voxelizzazione vera) con
    ESATTAMENTE 5 voti a testa nel gruppo: un pareggio nei VOTI, non nella
    taglia. Gli indici del cluster PICCOLO stanno PRIMA di quelli del
    cluster GRANDE nell'array del gruppo, apposta: il Counter costruito
    iterando il gruppo incontra il piccolo per primo, quindi un max() senza
    lo spareggio esplicito (la mutazione E) risponderebbe il cluster
    piccolo, indice 1 — l'ordine di iterazione da solo non puo' dare la
    risposta corretta. La regola dichiarata pretende il piu' popoloso in
    assoluto, indice 0 (2 781 punti): solo lo spareggio esplicito lo
    garantisce contro quest'ordine avverso.
    """
    import numpy as np
    from meshrec.core import io, pipeline
    from meshrec.core.config import load_config

    corsa = tmp_path / "corsa"
    grande = np.random.default_rng(2).random((3_000, 3)) * 10.0
    piccolo = np.random.default_rng(1).random((1_000, 3)) * 7.0 + 500.0
    _prepara_click_semplice(cliente, corsa, np.vstack([grande, piccolo]))

    # Stesso calcolo che l'endpoint rifara' alla POST (ARTIFACTS[1] ->
    # remove_outliers -> crop_box -> extract_planes -> cluster, coi
    # predefiniti salvati da _prepara_click_semplice): gli indici scelti
    # qui devono restare validi in quel momento.
    cfg = load_config(tmp_path / "config.yaml")
    insiemi, metriche, _spaziatura = _clusterizza_come_l_endpoint(corsa, cfg)
    assert metriche["clusters_found"] == 2
    # Precondizione: le taglie ASSOLUTE sono diverse (altrimenti questo test
    # sarebbe solo una copia del pareggio-di-taglia-uguale sopra).
    assert metriche["cluster_sizes"][0] > metriche["cluster_sizes"][1]

    # Il gruppo disegnato e' un indice nella nuvola SERVITA (ARTIFACTS[2]),
    # non nel residuo: la stessa distinzione che fa l'endpoint.
    punti, _normali = io.read_cloud(corsa / pipeline.ARTIFACTS[2])

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

    grande_idx: list[int] = []
    piccolo_idx: list[int] = []
    for i in range(len(punti)):
        c = cluster_del_punto_pieno(i)
        if c == 0 and len(grande_idx) < 5:
            grande_idx.append(i)
        elif c == 1 and len(piccolo_idx) < 5:
            piccolo_idx.append(i)
        if len(grande_idx) == 5 and len(piccolo_idx) == 5:
            break
    assert len(grande_idx) == 5 and len(piccolo_idx) == 5

    # Il piccolo prima del grande: l'ordine di iterazione del Counter, da
    # solo, indicherebbe il piccolo.
    gruppo_avverso = np.array(piccolo_idx + grande_idx, dtype=np.int64)

    def decimate_file_finto(*_args, **_kwargs):
        return np.zeros((1, 3), dtype=np.float32), [gruppo_avverso], 1.0

    monkeypatch.setattr(server.viewport, "decimate_file", decimate_file_finto)

    risposta_nuvola = cliente.get("/api/cloud/2?max_points=1")
    assert risposta_nuvola.status_code == 200

    risposta = cliente.post("/api/cluster", json={"punto": 0})
    assert risposta.status_code == 200
    corpo = risposta.json()
    assert corpo["cluster_index"] == 0
    assert corpo["cluster_points"] == metriche["cluster_sizes"][0]


def test_il_clic_sul_gruppo_a_maggioranza_rumore_solleva_come_rumore(cliente, tmp_path):
    """La maggioranza-rumore che la maggioranza da sola non decide
    (dichiarato in server.py, scegli_cluster): un blocco di 55 punti
    fitti forma un cluster valido (>= cluster_min_points=50), ma una
    catena di 70 punti isolati (troppo radi per il min_points, anche se
    a coppie dentro l'eps globale) resta tutta rumore. Misurato fuori dal
    test: clusters_found=1, cluster_sizes=[55], noise_points=70 — il
    rumore e' in maggioranza STRETTA sul gruppo (70 contro 55).

    Il primo indice del gruppo (0) appartiene pero' al cluster valido: con
    `pieno = gruppi[0][0]` (il codice del primo giro) la risposta sarebbe
    200 col cluster da 55 punti, nascondendo che la maggioranza del gruppo
    e' rumore. Qui si pretende il rifiuto, e che nulla sia scritto su
    disco.
    """
    import numpy as np
    from meshrec.core.config import load_config

    corsa = tmp_path / "corsa"
    denso = np.random.default_rng(0).random((55, 3)) * 3.0
    catena = np.zeros((70, 3))
    catena[:, 0] = 300.0 + np.arange(70) * 50.0
    _prepara_click_semplice(cliente, corsa, np.vstack([denso, catena]))

    risposta_nuvola = cliente.get("/api/cloud/2?max_points=1")
    assert risposta_nuvola.status_code == 200

    prima = load_config(tmp_path / "config.yaml")
    risposta = cliente.post("/api/cluster", json={"punto": 0})
    assert risposta.status_code == 400

    dopo = load_config(tmp_path / "config.yaml")
    assert dopo.segment.method == prima.segment.method
    assert dopo.segment.cluster_index == prima.segment.cluster_index


def test_un_indice_negativo_non_avvolge_al_gruppo_di_coda(cliente, tmp_path):
    """Mutazione A del revisore (task-11a-review.md): senza la guardia sui
    limiti, un indice negativo si indicizza da solo (regola di Python) e
    risponde il cluster di un gruppo che l'utente non ha cliccato, invece
    di rifiutare.

    Un solo blocco denso e non due, apposta: con due blocchi separati
    l'ultimo gruppo di decimazione (gruppi[-1]) e' quasi sempre rumore di
    bordo (misurato), e un 400 ottenuto cosi' non proverebbe la guardia,
    esattamente il rischio che il revisore segnala. Con 15 000 punti in
    un solo cubo, misurato fuori dal test, gruppi[-1] cade INTERO in un
    cluster vero (indice 0): senza la guardia la richiesta risponderebbe
    200, non 400, e questo test lo pretenderebbe rifiutato comunque.

    ARTIFACTS[1] scritto qui (con _prepara_click_semplice, non solo
    ARTIFACTS[2] come prima dell'allineamento): senza, dopo l'allineamento
    (task-11b) questo test passava per una ragione DIVERSA da quella che
    dichiara — la guardia nuova su ARTIFACTS[1] mancante avrebbe dato lo
    stesso 400 anche a guardia dei limiti RIMOSSA, e la mutazione A
    sarebbe rimasta invisibile (verificato per esecuzione: 74 passed con
    la guardia dei limiti tolta, prima di questa correzione).
    """
    import numpy as np

    corsa = tmp_path / "corsa"
    punti = np.random.default_rng(0).random((15_000, 3)) * 10.0
    _prepara_click_semplice(cliente, corsa, punti)

    cliente.get("/api/cloud/2?max_points=2000")
    risposta = cliente.post("/api/cluster", json={"punto": -1})
    assert risposta.status_code == 400


def test_il_cluster_index_scritto_su_disco_coincide_con_la_risposta(cliente, tmp_path):
    """Mutazione B del revisore: nessun test rileggeva config.yaml dopo la
    POST per verificare che cio' che finisce SUL DISCO sia cio' che torna
    NELLA RISPOSTA. E' la stessa specie di difetto che il ramo insegue da
    ieri (disco e schermo che divergono in silenzio).

    Serve un cluster_index DIVERSO da 0, altrimenti la mutazione
    'scrivi sempre 0' resterebbe invisibile per coincidenza: stessa nuvola
    di test_il_clic_sul_gruppo_piccolo_risolve_al_cluster_piccolo (7 mm,
    due cluster reali), click sul gruppo piccolo, cluster_index atteso 1.
    """
    from meshrec.core import io, pipeline, viewport
    from meshrec.core.config import load_config

    corsa = tmp_path / "corsa"
    _prepara_click_semplice(cliente, corsa, _nuvola_due_cluster())

    cliente.get("/api/cloud/2?max_points=2000")
    punti_letti, _normali = io.read_cloud(corsa / pipeline.ARTIFACTS[2])
    spaziatura = io.mean_spacing(punti_letti, 20_000, 0)
    _ridotti, gruppi, _voxel = viewport.decimate(punti_letti, 2_000, spaziatura)
    disegnato = next(i for i, gruppo in enumerate(gruppi) if (gruppo >= 3_000).all())

    risposta = cliente.post("/api/cluster", json={"punto": disegnato})
    assert risposta.status_code == 200
    corpo = risposta.json()
    assert corpo["cluster_index"] == 1

    scritta = load_config(tmp_path / "config.yaml")
    assert scritta.segment.cluster_index == corpo["cluster_index"]
    assert scritta.segment.method == "auto"


def test_il_cluster_eps_e_sensibile_alla_spaziatura_vera(cliente, tmp_path):
    """Mutazione C del revisore: nessun test legava cluster_eps alla
    spaziatura calcolata sulla nuvola VERA. Il valore atteso e' ricalcolato
    qui in modo indipendente, sugli stessi punti e parametri che l'endpoint
    usa (spacing_sample=20000, seed=0, i predefiniti di InputConfig che
    'cliente' non sovrascrive); una spaziatura calcolata su un campione
    troncato (es. i primi 50 punti soli) darebbe un valore diverso.

    Sulla nuvola di _nuvola_un_cluster_e_rumore, che dichiara da se' perche'
    il secondo blocco sia rumore e non un secondo cluster. Il punto disegnato
    0 cade nel primo blocco perche' viewport.decimate ordina i gruppi per
    indice pieno minimo.
    """
    from meshrec.core import io, pipeline

    corsa = tmp_path / "corsa"
    _prepara_click_semplice(cliente, corsa, _nuvola_un_cluster_e_rumore())

    cliente.get("/api/cloud/2?max_points=2000")
    risposta = cliente.post("/api/cluster", json={"punto": 0})
    assert risposta.status_code == 200
    corpo = risposta.json()

    # La spaziatura vera si legge sull'ingresso GREZZO (ARTIFACTS[1]), non
    # sulla nuvola servita: e' la base su cui l'endpoint la ricalcola dopo
    # l'allineamento (task-11b), non piu' su ARTIFACTS[2].
    punti_letti, _normali = io.read_cloud(corsa / pipeline.ARTIFACTS[1])
    spaziatura_vera = io.mean_spacing(punti_letti, 20_000, 0)
    assert corpo["cluster_eps"] == pytest.approx(4.0 * spaziatura_vera)


def test_il_clic_dichiara_il_cambio_di_metodo(cliente, tmp_path):
    """Il cambio silenzioso crop -> auto (segnalato in task-11a-review.md,
    non verificabile dal browser): la risposta deve portare il metodo che
    c'era prima del clic e quello che c'e' dopo, cosi' chi mostra la UI
    puo' avvisare l'utente invece di lasciarlo scoprire il cambio da un
    file che non vede.

    Sulla nuvola di _nuvola_un_cluster_e_rumore, che dichiara da se' perche'
    il secondo blocco sia rumore e non un secondo cluster. Il punto disegnato
    0 cade nel primo blocco perche' viewport.decimate ordina i gruppi per
    indice pieno minimo.
    """

    corsa = tmp_path / "corsa"
    _prepara_click_semplice(cliente, corsa, _nuvola_un_cluster_e_rumore())

    cliente.get("/api/cloud/2?max_points=2000")
    risposta = cliente.post("/api/cluster", json={"punto": 0})
    assert risposta.status_code == 200
    corpo = risposta.json()
    assert corpo["method_before"] == "crop"
    assert corpo["method_after"] == "auto"


def test_il_secondo_clic_dichiara_auto_auto(cliente, tmp_path):
    """Buco minore segnalato in task-11a-fix-2-review.md (sezione 5): il
    test sopra copre solo il primo clic (crop -> auto). Un secondo clic
    sullo stesso gruppo, con cfg.segment.method gia' 'auto' dal primo, deve
    dichiarare method_before='auto' (letto davvero, non un valore stantio)
    e method_after='auto'.

    Sulla nuvola di _nuvola_un_cluster_e_rumore, che dichiara da se' perche'
    il secondo blocco sia rumore e non un secondo cluster. Il punto disegnato
    0 cade nel primo blocco perche' viewport.decimate ordina i gruppi per
    indice pieno minimo.
    """

    corsa = tmp_path / "corsa"
    _prepara_click_semplice(cliente, corsa, _nuvola_un_cluster_e_rumore())

    cliente.get("/api/cloud/2?max_points=2000")
    prima_risposta = cliente.post("/api/cluster", json={"punto": 0})
    assert prima_risposta.status_code == 200
    assert prima_risposta.json()["method_after"] == "auto"

    seconda_risposta = cliente.post("/api/cluster", json={"punto": 0})
    assert seconda_risposta.status_code == 200
    corpo = seconda_risposta.json()
    assert corpo["method_before"] == "auto"
    assert corpo["method_after"] == "auto"


def test_il_clic_senza_lo_step_1_non_solleva(cliente, tmp_path):
    """L'allineamento (task-11b) fa dipendere il clic da ARTIFACTS[1], non
    piu' solo da ARTIFACTS[2]: uno scenario nuovo, impossibile prima di
    questo giro, e' che la mappa sia popolata (02_segmented.ply esiste ed e'
    stato aperto nel viewport) ma 01_cloud.ply sia assente (una corsa mai
    arrivata allo step 1 con questo out_dir, o il file cancellato a mano).
    Deve fallire con un errore chiaro, non con l'eccezione grezza di
    io.read_cloud su un file mancante.
    """
    import numpy as np
    from meshrec.core import io, pipeline

    corsa = tmp_path / "corsa"
    punti = np.random.default_rng(0).random((200, 3)) * 10.0
    io.write_cloud(corsa / pipeline.ARTIFACTS[2], punti)  # niente ARTIFACTS[1]

    cliente.get("/api/cloud/2?max_points=200")
    risposta = cliente.post("/api/cluster", json={"punto": 0})
    assert risposta.status_code == 400
    corpo = risposta.json()
    assert corpo["errore"] == "FileNotFoundError"
    assert pipeline.ARTIFACTS[1] in corpo["messaggio"]


def test_lindice_del_clic_coincide_con_quello_della_corsa_vera(cliente, tmp_path, monkeypatch):
    """La prova che l'allineamento (task-11b) tiene: l'indice che il clic
    sceglie e quello che la corsa 'auto' assegnerebbe DAVVERO allo stesso
    punto devono coincidere. Prima di questo giro non coincidevano: il clic
    clusterizzava 02_segmented.ply intero (senza extract_planes), mentre la
    corsa clusterizza il residuo DOPO extract_planes (core/segment.py,
    segment_cloud, righe 146-150) — sul dato vero (lab_crop) 4293 gruppi
    (il clic, sbagliato) contro 2447 (la corsa), vedi
    task-11b-allineamento.md.

    Qui un "pavimento" piatto (2 000 punti a z=0 su 30x30 mm, un piano vero)
    sta sopra la soglia di estrazione (plane_min_points_ratio=0.05 di 4 000
    punti = 200), e due "pareti" (1 500 e 500 punti, cubi separati fra loro
    e lontani dal pavimento) restano nel residuo. Con plane_max_count=1
    l'estrazione si ferma dopo il pavimento, deterministica: il residuo e'
    ESATTAMENTE le due pareti, 2 000 punti.

    La differenza e' osservabile, misurata (non solo dedotta): con
    cluster_eps_factor=8 (vedi sotto) il pavimento e' denso abbastanza da
    formare DBSCAN un cluster vero anche SENZA extract_planes (il difetto),
    non solo rumore — la scelta che rende la mutazione visibile invece di
    silenziosamente innocua (un pavimento troppo rado, misurato in un primo
    tentativo, finiva sempre in rumore in entrambi i casi, e la mutazione
    passava lo stesso test per coincidenza). Cosi' DBSCAN sull'intera nuvola
    (pavimento+pareti) trova TRE cluster ordinati per numerosita'
    decrescente (2000, 1500, 500), zero rumore: un clic sulla parete
    piccola risolverebbe all'indice 2 — il pavimento occuperebbe lo 0. CON
    extract_planes (questo giro), il residuo ha solo le due pareti: lo
    stesso clic deve risolvere all'indice 1, che e' anche l'indice che la
    clusterizzazione REALE (ricalcolata qui sotto, indipendentemente
    dall'endpoint, con la stessa sequenza che la corsa 'auto' esegue)
    assegna allo stesso punto.
    """
    import numpy as np
    from meshrec.core import io, pipeline, segment
    from meshrec.core.config import load_config

    corsa = tmp_path / "corsa"
    rng_pavimento = np.random.default_rng(3)
    pavimento = np.zeros((2_000, 3))
    pavimento[:, 0] = rng_pavimento.random(2_000) * 30.0
    pavimento[:, 1] = rng_pavimento.random(2_000) * 30.0
    parete_grande = np.random.default_rng(4).random((1_500, 3)) * 10.0 + np.array(
        [0.0, 0.0, 2_000.0]
    )
    parete_piccola = np.random.default_rng(5).random((500, 3)) * 7.0 + np.array(
        [500.0, 0.0, 2_000.0]
    )
    nuvola = np.vstack([pavimento, parete_grande, parete_piccola])

    io.write_cloud(corsa / pipeline.ARTIFACTS[1], nuvola)
    io.write_cloud(corsa / pipeline.ARTIFACTS[2], nuvola)

    attuale = cliente.get("/api/config").json()
    attuale["segment"]["plane_max_count"] = 1
    attuale["segment"]["outlier_std_ratio"] = 1_000_000.0
    # plane_distance_factor piccolo: col predefinito (3.0) la soglia
    # (~5,8 mm, misurato) e' comparabile all'estensione dei cubi delle
    # pareti (10 e 7 mm) e RANSAC trova per rumore un "piano" che ne
    # cattura una fetta — misurato, 1 951 dei 2 025 punti del piano
    # spurio venivano dalle pareti, non dal pavimento. A 0.1 la soglia
    # (~0,04 mm, misurato con questa spaziatura) e' trascurabile rispetto
    # ai cubi e cattura solo il pavimento, che e' esattamente a z=0 e
    # quindi a distanza zero da qualunque soglia positiva.
    attuale["segment"]["plane_distance_factor"] = 0.1
    # cluster_eps_factor piu' largo del predefinito (4): misurato, e'
    # cio' che serve perche' il pavimento denso (30x30 mm, 2000 punti)
    # formi un cluster DBSCAN vero invece di cadere in rumore — la
    # condizione che rende la mutazione (saltare extract_planes) visibile.
    attuale["segment"]["cluster_eps_factor"] = 8.0
    risposta_cfg = cliente.put("/api/config", json=attuale)
    assert risposta_cfg.status_code == 200

    # Oracolo: la clusterizzazione REALE, calcolata fuori dall'endpoint,
    # con la stessa sequenza di segment_cloud quando method='auto'
    # (core/segment.py:146-150): remove_outliers -> crop_box ->
    # extract_planes -> cluster, sullo stesso ingresso grezzo che
    # l'endpoint legge.
    cfg = load_config(tmp_path / "config.yaml")
    grezzi, _normali = io.read_cloud(corsa / pipeline.ARTIFACTS[1])
    spaziatura = io.mean_spacing(grezzi, cfg.input.spacing_sample, cfg.input.seed)
    puliti, _metriche_outlier = segment.remove_outliers(grezzi, cfg.segment)
    ritagliati, _metriche_crop = segment.crop_box(puliti, cfg.segment)
    _piani, residuo, metriche_piani = segment.extract_planes(ritagliati, cfg.segment, spaziatura)
    # Precondizione: il pavimento e' stato estratto come piano vero, e il
    # residuo sono esattamente le due pareti.
    assert metriche_piani["planes_found"] == 1
    assert metriche_piani["residual_points"] == 2_000
    insiemi_reali, metriche_reali = segment.cluster(residuo, cfg.segment, spaziatura)
    assert metriche_reali["clusters_found"] == 2
    assert metriche_reali["cluster_sizes"] == [1_500, 500]

    # Il punto cliccato: un punto della parete piccola, individuato per
    # coordinate nel residuo reale (indice 1 dell'oracolo), non per
    # posizione nell'array di partenza.
    punto_parete_piccola = insiemi_reali[1][0]
    indice_pieno = int(np.where((nuvola == punto_parete_piccola).all(axis=1))[0][0])

    def decimate_file_finto(*_args, **_kwargs):
        return (
            np.zeros((1, 3), dtype=np.float32),
            [np.array([indice_pieno], dtype=np.int64)],
            1.0,
        )

    monkeypatch.setattr(server.viewport, "decimate_file", decimate_file_finto)
    risposta_nuvola = cliente.get("/api/cloud/2?max_points=1")
    assert risposta_nuvola.status_code == 200

    risposta = cliente.post("/api/cluster", json={"punto": 0})
    assert risposta.status_code == 200
    corpo = risposta.json()
    # La prova che conta: l'indice del clic coincide con l'indice che la
    # clusterizzazione REALE assegna allo stesso punto. Prima
    # dell'allineamento l'endpoint avrebbe risposto 2 (la parete piccola e'
    # la terza per numerosita' clusterizzando pavimento+pareti insieme,
    # senza extract_planes): questo test fallisce con quel codice (vedi
    # mutazione nel rapporto).
    assert corpo["cluster_index"] == 1
    assert corpo["cluster_points"] == 500


def _scrivi_volume(corsa: Path, punti, tetraedri) -> None:
    """Un .vtu allo step 9, come lo scriverebbe abaqus.write_vtu."""
    import meshio
    import numpy as np

    from meshrec.core import pipeline

    corsa.mkdir(exist_ok=True)
    meshio.write_points_cells(
        corsa / pipeline.ARTIFACTS[9], np.asarray(punti), [("tetra", np.asarray(tetraedri))]
    )


def _mesh_dalla_risposta(risposta):
    """Vertici e facce ricostruiti dal corpo binario come fa il browser."""
    import numpy as np

    vertici = int(risposta.headers["X-Vertices"])
    triangoli = int(risposta.headers["X-Triangles"])
    # Tre code, non due: posizioni, indici e — dal 04/09/2026 — le normali,
    # che sono un Float32 per componente per vertice come le posizioni.
    assert risposta.headers["X-Normals"] == "1"
    assert len(risposta.content) == (vertici * 3 + triangoli * 3 + vertici * 3) * 4
    return (
        np.frombuffer(risposta.content, dtype="<f4", count=vertici * 3).reshape(vertici, 3),
        # `count` esplicito: senza, la lettura prende anche la coda delle
        # normali e il reshape salta. Il corpo ha tre code, e ognuna va letta
        # con la propria lunghezza.
        np.frombuffer(
            risposta.content, dtype="<u4", offset=vertici * 3 * 4, count=triangoli * 3
        ).reshape(triangoli, 3),
    )


def test_il_contorno_restituisce_gli_indici_dei_nodi_originali(tmp_path):
    """Senza la corrispondenza, un campo per nodo non sa dove va.

    `np.unique(..., return_inverse)` la calcola gia' dentro `_contorno_del_volume`
    e fino alla Fase 5 la buttava via. Riallinearla a valle, in ogni consumatore,
    sarebbe la forma d'errore che la Fase 5 esiste per non commettere: un indice
    che scivola e nessuna metrica che lo smentisce.

    Il nodo isolato (indice 2) resta fuori dal contorno: senza di lui `indici`
    coinciderebbe con `np.arange`, e la mutazione dello step 6 non morderebbe.
    """
    import numpy as np

    punti = np.array(
        [[0.0, 0.0, 0.0], [1.0, 0.0, 0.0], [9.0, 9.0, 9.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]]
    )
    corsa = tmp_path / "corsa"
    _scrivi_volume(corsa, punti, [[0, 1, 3, 4]])

    from meshrec.core import pipeline

    vertici, _facce, indici = server._contorno_del_volume(corsa / pipeline.ARTIFACTS[9])

    assert len(indici) == len(vertici)
    assert vertici == pytest.approx(punti[indici])


def test_una_voce_di_contorno_con_indici_di_lunghezza_sbagliata_e_rifiutata(tmp_path):
    """M10 del giro finale: `_leggi_contorno` negava `facce.max() >= len(vertici)`
    ma non `len(indici) != len(vertici)`.

    `indici` e' l'unico dei tre che indicizza un array **diverso**
    (`griglia.point_data`, non `vertici`), quindi l'argomento del commento
    accanto vale di piu' per lui, non di meno: `/api/campo` lo usa per
    ritagliare il campo sui nodi del contorno. Lungo o corto con valori tutti
    in dominio, numpy non solleva; il colore si posa sfalsato di un nodo e
    nessuno lo dice.

    Mutazione che uccide: togliere la guardia `len(indici) != len(vertici)`.
    Senza, `_leggi_contorno` restituisce la voce e l'assert cade.
    """
    import numpy as np

    vertici = np.zeros((4, 3), dtype="<f4")
    facce = np.array([[0, 1, 2]], dtype="<u4")
    voce = tmp_path / "voce.npz"

    # Corta: tre indici per quattro vertici. Tutti in dominio su point_data.
    np.savez(voce, vertici=vertici, facce=facce, indici=np.array([0, 1, 2], dtype="<u4"))
    assert server._leggi_contorno(voce) is None

    # Lunga: cinque indici per quattro vertici.
    np.savez(voce, vertici=vertici, facce=facce, indici=np.arange(5, dtype="<u4"))
    assert server._leggi_contorno(voce) is None

    # Giusta: la voce sana continua a passare, altrimenti la guardia avrebbe
    # solo spento la cache.
    np.savez(voce, vertici=vertici, facce=facce, indici=np.arange(4, dtype="<u4"))
    assert server._leggi_contorno(voce) is not None


def test_il_contorno_del_volume_porta_solo_i_vertici_che_disegna(cliente, tmp_path):
    """X-Vertices deve contare i vertici che il browser disegna davvero.

    griglia.points contiene anche i nodi interni della tetraedralizzazione,
    che nessuna faccia di contorno tocca: qui il nodo isolato non appartiene ad
    alcun tetraedro, e se finisse nella risposta il conteggio mostrato a video
    non sarebbe sostenuto da nessuna lettura.

    Il nodo isolato sta all'indice 2, in mezzo, e non in coda: con l'intruso in
    fondo la rimappatura sarebbe l'identita' e il test non distinguerebbe una
    mappa corretta da un semplice troncamento della coda dei nodi, che e'
    proprio il modo in cui la compattazione puo' essere disfatta per sbaglio.
    """
    import numpy as np

    punti = np.array(
        [[0.0, 0.0, 0.0], [1.0, 0.0, 0.0], [9.0, 9.0, 9.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]]
    )
    _scrivi_volume(tmp_path / "corsa", punti, [[0, 1, 3, 4]])

    risposta = cliente.get("/api/mesh/9")
    assert risposta.status_code == 200
    # Le quattro facce del solo tetraedro, sui suoi soli quattro nodi.
    assert (risposta.headers["X-Vertices"], risposta.headers["X-Triangles"]) == ("4", "4")
    vertici, facce = _mesh_dalla_risposta(risposta)
    # Le coordinate, non il conteggio: sono i nodi 0, 1, 3, 4 e non i primi
    # quattro dell'array, che comprenderebbero l'intruso.
    assert np.array_equal(vertici, punti[[0, 1, 3, 4]].astype("<f4"))
    # Rimappati sui vertici mandati: un indice fuori intervallo non disegna.
    assert facce.max() < len(vertici)


def test_il_contorno_del_volume_torna_con_le_facce_uscenti(cliente, tmp_path):
    """Il verso delle facce, che np.sort perde e return_index conserva.

    Il criterio e' il volume con segno racchiuso dalle facce restituite: con
    le facce ordinate invece che orientate il conto da' un altro numero (su
    lab_crop, -1.202.490 contro 173.282.926). Il tetraedro e' traslato lontano
    dall'origine apposta: nell'origine mesh_volume vale 1/6 in entrambi i casi
    e il test non morderebbe.
    """
    import numpy as np

    from meshrec.core import quality

    base = np.array([10.0, 10.0, 10.0])
    punti = base + np.array([[0.0, 0.0, 0.0], [1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]])
    _scrivi_volume(tmp_path / "corsa", punti, [[0, 1, 2, 3]])

    risposta = cliente.get("/api/mesh/9")
    assert risposta.status_code == 200
    vertici, facce = _mesh_dalla_risposta(risposta)
    # Positivo e pari al volume del tetraedro: le quattro facce sono uscenti.
    # Con le facce ordinate lo stesso conto darebbe 6,833333.
    assert quality.mesh_volume(vertici, facce) == pytest.approx(1.0 / 6.0)


def test_il_contorno_del_volume_legge_anche_il_tetraedro_quadratico(cliente, tmp_path):
    """C3D10 e' il predefinito di TetConfig.element, e la vista non lo apriva.

    meshio chiama `tetra10` il tetraedro quadratico, e la funzione cercava la
    chiave `tetra`: con l'elemento predefinito del progetto il pannello
    rispondeva «09_volume.vtu non contiene tetraedri: le celle sono
    ['tetra10']» su un file perfettamente valido, e lo stesso accadeva ai campi
    di soluzione dello step 13. Il file lo scrive `abaqus.write_vtu`, non
    meshio a mano: cosi' la prova passa per la convenzione vera del progetto e
    non per una scritta apposta qui.

    Il criterio e' il confronto con il gemello lineare sugli stessi quattro
    vertici: stesso contorno, perche' i nodi di lato stanno a meta' degli
    spigoli e non aggiungono ne' facce ne' adiacenze.
    """
    import numpy as np

    from meshrec.core import abaqus, pipeline, quality

    base = np.array([10.0, 10.0, 10.0])
    angoli = base + np.array(
        [[0.0, 0.0, 0.0], [1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]]
    )
    # I sei nodi di lato nell'ordine di Abaqus, che e' quello di VTK: 4=(0,1),
    # 5=(1,2), 6=(2,0), 7=(0,3), 8=(1,3), 9=(2,3).
    spigoli = [(0, 1), (1, 2), (2, 0), (0, 3), (1, 3), (2, 3)]
    lati = np.array([(angoli[a] + angoli[b]) / 2.0 for a, b in spigoli])
    nodi = np.vstack([angoli, lati])

    corsa = tmp_path / "corsa"
    corsa.mkdir(exist_ok=True)
    abaqus.write_vtu(
        corsa / pipeline.ARTIFACTS[9], nodi, np.arange(10)[None, :], element_type="C3D10"
    )

    risposta = cliente.get("/api/mesh/9")
    assert risposta.status_code == 200
    # I quattro vertici d'angolo e le quattro facce del tetraedro: i sei nodi
    # di lato non disegnano nulla e non devono comparire nel conteggio.
    assert (risposta.headers["X-Vertices"], risposta.headers["X-Triangles"]) == ("4", "4")
    vertici, facce = _mesh_dalla_risposta(risposta)
    assert np.array_equal(vertici, angoli.astype("<f4"))
    # Lo stesso verso uscente del caso lineare, misurato allo stesso modo.
    assert quality.mesh_volume(vertici, facce) == pytest.approx(1.0 / 6.0)
def test_il_contorno_del_volume_rifiuta_un_file_con_due_blocchi_di_celle(cliente, tmp_path):
    """Il ramo `len(tipi) != 1` non aveva una prova che lo attraversasse.

    `abaqus.write_vtu` scrive un blocco solo, ed è per questo che il blocco si
    prende per unicità e non per nome: i nomi sarebbero due (`tetra`,
    `tetra10`) e uno solo è scritto. Un file che ne porta due non è quel file,
    e prenderne uno a caso significherebbe aprire la vista su metà del modello
    senza dirlo.

    Mutazione che uccide: `tetraedri = griglia.cells_dict[tipi[0]]` al posto
    della guardia — la richiesta risponde 200 sul solo blocco `tetra`.
    """
    import meshio
    import numpy as np

    from meshrec.core import pipeline

    corsa = tmp_path / "corsa"
    corsa.mkdir(exist_ok=True)
    punti = np.array(
        [[0.0, 0.0, 0.0], [1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]]
    )
    meshio.write_points_cells(
        corsa / pipeline.ARTIFACTS[9],
        punti,
        [("tetra", np.array([[0, 1, 2, 3]])), ("triangle", np.array([[0, 1, 2]]))],
    )

    risposta = cliente.get("/api/mesh/9")
    assert risposta.status_code == 400
    messaggio = risposta.json()["messaggio"]
    assert "porta 2 blocchi di celle" in messaggio
    assert "09_volume.vtu" in messaggio


def test_il_contorno_del_volume_rifiuta_un_blocco_che_non_e_di_tetraedri(cliente, tmp_path):
    """Il ramo `shape[1] != 4` nemmeno: il blocco è unico ma non è di volume.

    L'unicità dice quale blocco prendere, non che quel blocco sia un maglio di
    tetraedri: un `.vtu` di soli triangoli ne ha uno solo, e le sue celle hanno
    tre colonne. È il controllo che `pipeline._maglio_di_volume` non aveva e
    che ora ha, e questa prova fissa il gemello che ce l'aveva già.

    Mutazione che uccide: togliere la guardia — `quality._TET_FACES` indicizza
    la quarta colonna e la richiesta muore con un `IndexError` invece che con
    un messaggio.
    """
    import meshio
    import numpy as np

    from meshrec.core import pipeline

    corsa = tmp_path / "corsa"
    corsa.mkdir(exist_ok=True)
    punti = np.array(
        [[0.0, 0.0, 0.0], [1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]]
    )
    meshio.write_points_cells(
        corsa / pipeline.ARTIFACTS[9], punti, [("triangle", np.array([[0, 1, 2], [1, 2, 3]]))]
    )

    risposta = cliente.get("/api/mesh/9")
    assert risposta.status_code == 400
    corpo = risposta.json()
    assert corpo["errore"] != "IndexError"
    assert "non contiene tetraedri" in corpo["messaggio"]
    assert "triangle" in corpo["messaggio"]


def _scrivi_volume_quadratico(corsa: Path):
    """Un .vtu di un solo C3D10, scritto dalla stessa funzione dello step 9.

    I sei nodi di lato stanno a metà degli spigoli nell'ordine di Abaqus, che è
    quello di VTK: 4=(0,1), 5=(1,2), 6=(2,0), 7=(0,3), 8=(1,3), 9=(2,3). Il
    tetraedro è lontano dall'origine per la stessa ragione del gemello lineare.
    """
    import numpy as np

    from meshrec.core import abaqus, pipeline

    angoli = np.array([10.0, 10.0, 10.0]) + np.array(
        [[0.0, 0.0, 0.0], [1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]]
    )
    lati = np.array(
        [(angoli[a] + angoli[b]) / 2.0 for a, b in [(0, 1), (1, 2), (2, 0), (0, 3), (1, 3), (2, 3)]]
    )
    corsa.mkdir(exist_ok=True)
    abaqus.write_vtu(
        corsa / pipeline.ARTIFACTS[9],
        np.vstack([angoli, lati]),
        np.arange(10)[None, :],
        element_type="C3D10",
    )
    return angoli


def test_la_seconda_richiesta_del_contorno_quadratico_risponde_dalla_cache(
    cliente, tmp_path, monkeypatch
):
    """La cache del contorno vale per il C3D10 come per il C3D4.

    Il difetto che questa cartella ha appena corretto era di famiglia: il
    blocco di celle cercato per nome (`tetra`) invece che per unicità, e il
    tetraedro quadratico che si chiama `tetra10`. La cache è l'altro pezzo di
    codice che quel percorso attraversa, e una guardia rimasta indietro sul
    nome -- scrivere la voce solo quando il blocco si chiama `tetra` -- non la
    vedrebbe nessuno: il caso lineare continuerebbe a rispondere dalla cache e
    il predefinito del progetto ricomincerebbe da capo a ogni clic, che è
    proprio il costo che la cache esiste per non pagare.

    Il criterio è quello del gemello lineare: la seconda richiesta deve
    riuscire, e rispondere gli stessi byte, anche se leggere il file adesso
    solleva.
    """
    import meshio

    _scrivi_volume_quadratico(tmp_path / "corsa")

    prima = cliente.get("/api/mesh/9")
    assert prima.status_code == 200

    def _non_chiamarmi(*_args, **_kwargs):
        raise AssertionError("il contorno non deve essere riestratto a cache calda")

    monkeypatch.setattr(meshio, "read", _non_chiamarmi)
    poi = cliente.get("/api/mesh/9")
    assert poi.status_code == 200
    assert poi.content == prima.content
    assert (poi.headers["X-Vertices"], poi.headers["X-Triangles"]) == ("4", "4")


def test_un_maglio_con_due_blocchi_di_celle_e_rifiutato_nominandoli(cliente, tmp_path):
    """Lo step 9 scrive un blocco solo, e prenderne uno a caso non è una lettura.

    Da quando il blocco si prende per unicità e non per nome, un file con due
    blocchi non ha più un candidato ovvio, e il conteggio delle colonne non lo
    salva: `quad` ne ha quattro come il tetraedro lineare, quindi prendere il
    primo blocco che capita disegnerebbe dei quadrilateri come se fossero il
    solido, con un 200 e nessun avviso. Il rifiuto nomina quanti blocchi ha
    trovato e quali, che è l'unica cosa che permette a chi legge di capire
    quale file ha aperto.
    """
    import meshio
    import numpy as np

    from meshrec.core import pipeline

    corsa = tmp_path / "corsa"
    corsa.mkdir()
    meshio.write_points_cells(
        corsa / pipeline.ARTIFACTS[9],
        np.array([[0.0, 0.0, 0.0], [1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]]),
        [("tetra", np.array([[0, 1, 2, 3]])), ("quad", np.array([[0, 1, 2, 3]]))],
    )

    risposta = cliente.get("/api/mesh/9")
    assert risposta.status_code == 400
    messaggio = risposta.json()["messaggio"]
    assert "tetra" in messaggio and "quad" in messaggio
    assert "2 blocchi" in messaggio


def test_la_seconda_richiesta_del_contorno_non_riestrae(cliente, tmp_path, monkeypatch):
    """I-3 della revisione: l'estrazione costa 14,9 s e oltre un gigabyte di
    picco su lab_crop, e senza cache si rifa' identica a ogni clic. La prova e'
    osservabile e non temporale, come per /api/cloud: la seconda richiesta deve
    riuscire anche se leggere il file adesso solleva.
    """
    import meshio
    import numpy as np

    punti = np.array(
        [[0.0, 0.0, 0.0], [1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]]
    )
    _scrivi_volume(tmp_path / "corsa", punti, [[0, 1, 2, 3]])

    prima = cliente.get("/api/mesh/9")
    assert prima.status_code == 200

    def _non_chiamarmi(*_args, **_kwargs):
        raise AssertionError("il contorno non deve essere riestratto a cache calda")

    monkeypatch.setattr(meshio, "read", _non_chiamarmi)
    poi = cliente.get("/api/mesh/9")
    assert poi.status_code == 200
    assert poi.content == prima.content
    assert poi.headers["X-Vertices"] == prima.headers["X-Vertices"]
    assert poi.headers["X-Triangles"] == prima.headers["X-Triangles"]


def test_una_voce_di_cache_incoerente_non_arriva_al_browser(cliente, tmp_path):
    """BL-2: una voce formalmente valida ma con un indice oltre i vertici.

    np.load la legge senza un rumore e nessun indice fuori misura solleva in
    numpy: il 200 arriva al browser con una faccia che punta oltre l'array di
    vertici appena mandato, three.js disegna fuori dall'attributo position e
    non lo dice a nessuno. Una voce cosi' si tratta come corrotta e si
    ricalcola, la stessa cura che _leggi_cache da' al suo offsets.
    """
    import numpy as np

    from meshrec.core import pipeline

    punti = np.array([[0.0, 0.0, 0.0], [1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]])
    _scrivi_volume(tmp_path / "corsa", punti, [[0, 1, 2, 3]])
    assert cliente.get("/api/mesh/9").status_code == 200

    voce = server._percorso_contorno(tmp_path / "corsa" / pipeline.ARTIFACTS[9])
    assert voce.exists(), "la prima richiesta non ha scritto la voce che il test avvelena"
    np.savez(
        str(voce),
        vertici=np.zeros((4, 3), dtype="<f4"),
        facce=np.full((1, 3), 99, dtype="<u4"),
    )

    risposta = cliente.get("/api/mesh/9")
    assert risposta.status_code == 200
    vertici, facce = _mesh_dalla_risposta(risposta)
    # Il contorno vero del tetraedro, non la voce avvelenata.
    assert (risposta.headers["X-Vertices"], risposta.headers["X-Triangles"]) == ("4", "4")
    assert facce.max() < len(vertici), "un indice oltre i vertici e' arrivato al browser"


def test_cambiare_la_versione_della_cache_del_contorno_fa_ricalcolare(
    cliente, tmp_path, monkeypatch
):
    """BL-2, l'altra meta': la chiave (sorgente, mtime) non registra il codice.

    Il verso delle facce (quality._TET_FACES) e la regola di compattazione dei
    vertici decidono il risultato e nella chiave non ci sono: se cambiano, ogni
    voce gia' su disco risponde col risultato vecchio per tutta la vita del
    file sorgente. La versione nel nome le sfratta, perche' la pulizia per
    marchio non guarda che cosa segue il marchio.

    La forma osservabile e' quella di test_la_seconda_richiesta_del_contorno_non_riestrae,
    al contrario: con la lettura del volume che solleva, la richiesta deve
    fallire: se riesce, ha riusato la voce della versione precedente.
    """
    import meshio
    import numpy as np

    punti = np.array([[0.0, 0.0, 0.0], [1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]])
    _scrivi_volume(tmp_path / "corsa", punti, [[0, 1, 2, 3]])
    assert cliente.get("/api/mesh/9").status_code == 200

    monkeypatch.setattr(server, "VERSIONE_CONTORNO", server.VERSIONE_CONTORNO + 1)

    def _riestrazione(*_args, **_kwargs):
        raise RuntimeError("riestratto")

    monkeypatch.setattr(meshio, "read", _riestrazione)
    risposta = cliente.get("/api/mesh/9")
    assert risposta.status_code == 400, "la voce della versione precedente e' stata riusata"
    assert risposta.json()["errore"] == "RuntimeError"


def test_un_volume_senza_tetraedri_dice_che_cosa_contiene(cliente, tmp_path):
    """M-2: cells_dict["tetra"] dava un KeyError nudo ("'tetra'"), la stessa
    forma inutile che la guardia sullo step ha appena tolto."""
    import meshio
    import numpy as np

    from meshrec.core import pipeline

    corsa = tmp_path / "corsa"
    corsa.mkdir()
    meshio.write_points_cells(
        corsa / pipeline.ARTIFACTS[9],
        np.array([[0.0, 0.0, 0.0], [1.0, 0.0, 0.0], [0.0, 1.0, 0.0]]),
        [("triangle", np.array([[0, 1, 2]]))],
    )

    risposta = cliente.get("/api/mesh/9")
    assert risposta.status_code == 400
    corpo = risposta.json()
    assert corpo["errore"] != "KeyError"
    assert "tetra" in corpo["messaggio"] and "triangle" in corpo["messaggio"]


def test_una_nuvola_chiesta_come_mesh_e_rifiutata_invece_di_tornare_vuota(cliente, tmp_path):
    """M-3: 01_cloud.ply letto con read_triangle_mesh da' vertici e zero facce.
    Un 200 con X-Triangles: 0 farebbe disegnare un solido vuoto."""
    import numpy as np

    from meshrec.core import io, pipeline

    corsa = tmp_path / "corsa"
    punti = np.random.default_rng(0).random((100, 3)) * 10.0
    io.write_cloud(corsa / pipeline.ARTIFACTS[1], punti)

    risposta = cliente.get("/api/mesh/1")
    assert risposta.status_code == 400
    corpo = risposta.json()
    assert "triangoli" in corpo["messaggio"]
    assert "0 triangoli" in corpo["messaggio"]


def _scrivi_soluzione(corsa: Path, punti, tetraedri, point_data: dict) -> None:
    """13_solution.vtu come lo scriverebbe solve.risolvi (Task 6): stesso
    schema di _scrivi_volume, con i campi per nodo del contratto di solve.py."""
    from meshrec.core import abaqus, pipeline

    corsa.mkdir(exist_ok=True)
    abaqus.write_vtu(corsa / pipeline.ARTIFACTS[13], punti, tetraedri, point_data=point_data)


def test_il_clic_sullo_step_sceglie_fra_nuvola_e_mesh_senza_perdere_il_pannello():
    """Il gestore del clic apre anche il pannello dei parametri (Task 8): una
    riscrittura che ne sostituisce l'intero corpo lo perderebbe in silenzio."""
    from meshrec.app.server import UI_DIR

    testo = (UI_DIR / "app.js").read_text(encoding="utf-8")
    # La fetta finisce dove finisce il gestore. Senza il secondo split prendeva
    # tutto il file che segue, e i due asserti erano vacui tutti e due:
    # `ricaricaVista` chiama `mostraStep` piu' sotto, e `apriDettaglio(numero`
    # trovava la **propria definizione**. Provato: svuotando del tutto il
    # gestore del clic, il test passava lo stesso.
    gestore = testo.split('getElementById("elenco-step").addEventListener', 1)[1]
    gestore = gestore.split("\n});", 1)[0]
    # Dal 10/09/2026 il gestore delega a `scegliStep`, che ha un nome perche'
    # lo chiama anche il giro di «Salva tutti gli step»: si segue quella sola
    # delega, e il corpo di scegliStep e' quello che deve fare le due cose.
    assert re.search(r"scegliStep\(", gestore), gestore
    scelta = _sorgente_di("scegliStep", testo)
    # Il numero d'ordine del giro 2 (I-4) aggiunge un argomento a entrambe: cio'
    # che il test difende e' che il clic le chiami tutte e due sullo step
    # cliccato, non quanti argomenti passi. La geometria passa da ricaricaVista,
    # che e' l'unico punto in cui e' chiesta.
    assert re.search(r"ricaricaVista\(numero[,)]", scelta), scelta
    assert re.search(r"apriDettaglio\(numero[,)]", scelta), scelta


def _sorgente_di(nome: str, testo: str) -> str:
    """Il corpo di una funzione di primo livello, dalla firma alla graffa che la
    chiude in prima colonna. I moduli dell'interfaccia non sono importabili da
    qui (importano percorsi serviti dal server), quindi si estrae il testo.

    `async` va tenuto: senza, il testo estratto resta leggibile ma non e' piu'
    eseguibile — `await` dentro una funzione non asincrona e' un errore di
    sintassi, e il banco che esegue queste funzioni morirebbe prima di provare
    qualcosa.
    """
    corpo = testo.split(f"function {nome}(", 1)[1]
    prefisso = "async " if f"async function {nome}(" in testo else ""
    return f"{prefisso}function {nome}(" + corpo.split("\n}\n", 1)[0] + "\n}"


def test_una_risposta_superata_si_scarta_e_una_corrente_no():
    """I-4. La regola dell'ordine sta in una funzione pura apposta perche' si
    possa provare senza un motore di DOM. Se la sua polarita' si invertisse, o
    ogni risposta verrebbe buttata (la vista non cambierebbe piu') o nessuna (il
    difetto tornerebbe): entrambe passerebbero un test solo testuale."""
    from meshrec.app.server import UI_DIR

    node = shutil.which("node")
    if node is None:
        pytest.skip("node non installato: la regola resta verificata a mano")
    sorgente = _sorgente_di("superata", (UI_DIR / "app.js").read_text(encoding="utf-8"))
    prova = Path(__file__).parent / "_prova_ordine.mjs"
    prova.write_text(
        sorgente + "\n"
        "import assert from 'node:assert/strict';\n"
        # Una risposta partita prima di un clic successivo e' superata.
        "assert.equal(superata(1, 2), true);\n"
        # Quella della generazione in corso passa, ed e' l'unica.
        "assert.equal(superata(2, 2), false);\n"
        # Anche la prima in assoluto, che non deve restare bloccata.
        "assert.equal(superata(1, 1), false);\n",
        encoding="utf-8",
    )
    try:
        esito = subprocess.run([node, str(prova)], capture_output=True, text=True)
        assert esito.returncode == 0, esito.stderr
    finally:
        prova.unlink()


def _corpi_freccia_asincroni(testo: str) -> list[str]:
    """I corpi dei gestori `async (...) => {` e `async x => {`, contando le graffe.

    Il regex delle funzioni nominate non li vede: un gestore inline non ha un
    nome e non chiude in prima colonna, quindi la regola dell'ordine vi
    resterebbe scoperta con l'aria di essere coperta. L'alternanza copre anche
    il parametro singolo senza parentesi, che e' la forma piu' comune delle
    tre che restavano invisibili.

    Il tetto vero, misurato caso per caso (I-2 della revisione), perche' quello
    dichiarato prima non era questo:
    - una graffa **aperta** spaiata in una stringa o in un commento non fa
      finire il corpo nel posto sbagliato: fa sparire la tratta dall'elenco
      senza estrarre niente, in silenzio;
    - una graffa **chiusa** spaiata tronca il corpo, e li' si', la guardia
      potrebbe restare fuori da cio' che si legge;
    - restano invisibili il corpo conciso (`async () => (await f()).json()`) e
      le parentesi dentro i parametri (`async ({ a = (1) }) => {`);
    - le frecce annidate sono contate due volte, quindi l'interna pretende una
      guardia sua anche quando l'esterna ce l'ha.

    La soglia finale `interrogano >= 6` pareggia il numero vero di tratte, e
    copre **una sola** di queste direzioni: se una tratta sparisce dall'elenco,
    per una graffa spaiata o per una cancellazione, il conteggio scende e la
    soglia lo dice. Non copre l'altra, che era il caso di I-2: una tratta
    **aggiunta** in una delle forme invisibili non fa scendere niente —
    `interrogano` resta 6, `>= 6` resta vero, e il test resta verde con un
    gestore senza guardia dentro il modulo. Per quella direzione la rete e' il
    riconoscimento della forma, cioe' l'alternanza qui sopra, e le forme che
    l'alternanza non riconosce restano scoperte.
    """
    corpi = []
    for avvio in re.finditer(r"async\s*(?:\([^)]*\)|\w+)\s*=>\s*\{", testo):
        profondita = 0
        for posizione in range(avvio.end() - 1, len(testo)):
            profondita += {"{": 1, "}": -1}.get(testo[posizione], 0)
            if profondita == 0:
                corpi.append(testo[avvio.start() : posizione + 1])
                break
    return corpi


def test_lo_scanner_vede_anche_la_freccia_senza_parentesi():
    """I-2. `async evento => { ... }` e' la forma piu' comune delle tre che
    restavano invisibili, e un gestore scritto cosi' entrava nel modulo senza
    guardia lasciando il test verde: la tratta non veniva vista e il conteggio
    non cambiava. Il tetto residuo e' dichiarato in _corpi_freccia_asincroni.
    """
    con_parentesi = 'async () => { await fetch("/api/x"); superata(o); }'
    senza_parentesi = 'async evento => { await fetch("/api/y"); esito.textContent = "fatto"; }'
    assert len(_corpi_freccia_asincroni(con_parentesi)) == 1
    assert len(_corpi_freccia_asincroni(senza_parentesi)) == 1, "la freccia senza parentesi e' invisibile"
    # E il corpo estratto arriva intero fino alla graffa che lo chiude: se si
    # fermasse prima, la guardia potrebbe restare fuori da cio' che si legge.
    assert _corpi_freccia_asincroni(senza_parentesi)[0].endswith('"fatto"; }')


def test_ogni_tratta_che_interroga_il_server_si_scarta_se_e_stata_superata():
    """I-4, sulla tratta e non sulla funzione: l'elenco non e' scritto a mano ma
    ricavato dal modulo, cosi' una tratta aggiunta domani vi entra da sola e non
    puo' essere dimenticata. Le funzioni freccia asincrone entrano nell'elenco
    quanto quelle nominate: la meta' dei gestori dell'interfaccia sono inline, e
    lasciarle fuori teneva aperto un buco con l'aria di essere chiuso.
    """
    from meshrec.app.server import UI_DIR

    testo = (UI_DIR / "app.js").read_text(encoding="utf-8")
    # caricaStato e mostraInformazioni partono una volta sola all'avvio della
    # pagina e non da un clic: non c'e' nessuna generazione che possa
    # superarle. annullaLaCorsa non scrive nulla dopo l'attesa, quindi non ha
    # niente da contraddire; ha un nome apposta per poter comparire qui invece
    # di non essere mai incontrata.
    senza_ordine = {"caricaStato", "annullaLaCorsa", "mostraInformazioni"}
    tratte = [
        (nome, _sorgente_di(nome, testo))
        for nome in re.findall(r"^async function (\w+)\(", testo, re.MULTILINE)
        if nome not in senza_ordine
    ]
    tratte += [("una funzione freccia asincrona", corpo) for corpo in _corpi_freccia_asincroni(testo)]
    interrogano = 0
    for nome, sorgente in tratte:
        if "await fetch(" not in sorgente:
            continue
        interrogano += 1
        assert "superata(" in sorgente, f"{nome} scrive senza guardare l'ordine:\n{sorgente}"
    # Senza questo, cancellare le funzioni farebbe passare il test a vuoto. Ed
    # e' anche l'unica rete che resta quando l'estrazione per graffe fallisce
    # (vedi il tetto di _corpi_freccia_asincroni): le tratte reali sono 7
    # nominate (disegnaIngresso, chiediStorico, mostraNuvolaDelloStep,
    # mostraStep, mostraFantasmaDelloStep, scriviValore, apriDettaglio) piu' 5
    # freccia, dodici in tutto -- erano tredici finche' il pannello del
    # materiale portava la propria PUT. La soglia pareggia il numero vero,
    # contato rieseguendo questo stesso algoritmo su app.js. Se ne aggiungi
    # una, alza la soglia invece di lasciarla indietro.
    assert interrogano >= 12, "le tratte attese sono sparite dal modulo"


def test_due_geometrie_in_volo_nella_stessa_generazione_non_si_arbitrano_per_arrivo():
    """Il ricaricamento dal fronte di discesa non apre una generazione — aprirla
    butterebbe via il clic che l'utente ha appena fatto — quindi porta lo stesso
    ordine di una risposta partita prima, e con un contatore solo `superata()`
    non puo' dire quale delle due vince: vince chi arriva ultimo.

    Ingresso concreto: step 9 aperto, «Esegui questo step», e riclic sullo step
    9 mentre gira. Se la risposta del clic — che porta il contorno vecchio —
    arriva per ultima, il viewport torna indietro. E' IM-4 per un'altra strada.

    Sono due requisiti diversi e servono due contatori: la generazione ordina i
    clic, la richiesta di geometria ordina le geometrie. La regola resta
    `superata`, che e' pura e ha gia' il suo test eseguito: qui si sorveglia che
    ogni strada apra esattamente una richiesta e la guardi prima di scrivere.
    """
    from meshrec.app.server import UI_DIR

    testo = (UI_DIR / "app.js").read_text(encoding="utf-8")
    for nome in ("mostraNuvolaDelloStep", "mostraStep"):
        sorgente = _sorgente_di(nome, testo)
        assert sorgente.count("apriGeometria()") == 1, f"{nome} non apre una richiesta sola"
        assert "superata(emissione, ultimaGeometria)" in sorgente, (
            f"{nome} scrive senza guardare se una geometria piu' nuova e' gia' partita"
        )
    # La delega di mostraStep sta prima del contatore: se stesse dopo, la strada
    # della nuvola aprirebbe due richieste e batterebbe se stessa, e nessuna
    # nuvola verrebbe piu' disegnata.
    mostra = _sorgente_di("mostraStep", testo)
    assert mostra.index("mostraNuvolaDelloStep(numero") < mostra.index("apriGeometria()"), mostra
    # E il cursore del taglio si rifa' solo se questa risposta ha scritto: sulla
    # geometria di qualcun altro sarebbe una taratura che nessuna lettura regge.
    ricarica = _sorgente_di("ricaricaVista", testo)
    assert re.search(r"if \(disegnato && !superata\(ordine\)\)", ricarica), ricarica


# Il banco che esegue l'arbitraggio invece di guardarlo. Lo stub finisce qui:
# sotto ci vanno le funzioni vere di app.js, e il caso da riprodurre.
# `generazione` e `ultimaGeometria` sono dichiarate qui perche' in app.js sono
# variabili di modulo e non funzioni: e' la sola parte di stato che il banco
# rifa'. STEP_CON_MESH tiene il solo step 9: __NUMERO__ decide se il caso cade
# dentro (tratta della mesh) o fuori (tratta della nuvola) — e' il medesimo
# banco per tutte e due le tratte, non due banchi.
_BANCO_ORDINE = """import assert from 'node:assert/strict';

let generazione = 1;
let ultimaGeometria = 0;
const STEP_CON_MESH = new Set([9]);
// Come STEP_CON_MESH qui sopra: uno stub deliberato coi soli due step che
// questo banco esercita. Qui si prova l'arbitraggio, non il ripiego -- che la
// tabella vera coincida con pipeline.ARTIFACTS lo verifica
// test_app_js.py::test_gli_step_disegnabili_del_modulo_sono_quelli_del_server.
const STEP_CON_GEOMETRIA = new Set([2, 9]);
// Come i due insiemi qui sopra: uno stub deliberato con la sola coppia che
// questo banco esercita. Che la tabella vera abbia tre coppie e che quella
// dello step 8 venga dal 6 lo verifica
// test_app_js.py::test_il_fantasma_dello_step_8_viene_dal_6_e_non_dal_7.
const FANTASMA_DI = { 2: 1 };
let fantasmaAcceso = true;
let ultimoFantasma = 0;
const scritture = [];
const vista = {
  svuota() {},
  mostraNuvola(vertici) { scritture.push(`nuvola:${vertici.length / 3}`); },
  mostraMesh(vertici) { scritture.push(`mesh:${vertici.length / 3}`); },
  mostraFantasma() { scritture.push('fantasma'); },
  togliFantasma() {},
};
// setAttribute/removeAttribute perche' le funzioni ritagliate toccano attributi
// dell'elemento: senza, la funzione vera cade su un elemento che non sa
// rispondere, e il banco misurerebbe quella caduta invece dell'arbitraggio.
const attributi = {};
const document = {
  getElementById: () => ({
    textContent: '',
    hidden: false,
    setAttribute(nome, valore) { attributi[nome] = valore; },
    removeAttribute(nome) { delete attributi[nome]; },
  }),
};
function riallineaTaglio(numero) { scritture.push(`riallinea:${numero}`); }
function serverMuto() { return undefined; }

// Ogni step col proprio artefatto: qui si prova l'ARBITRAGGIO fra due risposte,
// non il ripiego della vista, e `passoDaMostrare` deve restituire lo step
// chiesto perche' il caso da riprodurre resti quello di prima.
// Vuoto apposta: nomeDelloStep ripiega su `step N`, che a questo banco basta.
// Qui si prova l'ordine delle risposte, non come si chiamano gli step.
const ETICHETTE = {};
const ultimoStato = Array.from({ length: 13 }, (_, i) => ({
  numero: i + 1, chiave: `0${i + 1}`, artefatto: 'scritto',
}));

// Ogni richiesta resta sospesa finche' il banco non la sblocca: l'ordine di
// arrivo e' l'ingresso della prova, non un caso.
const sospese = [];
let partite = 0;
globalThis.fetch = () => {
  const marcatore = ++partite;
  return new Promise((risolvi) => sospese.push(() => risolvi({
    ok: true,
    // Il marcatore viaggia come numero di vertici (tratta della mesh) o come
    // un terzo del numero di numeri in virgola mobile (tratta della nuvola,
    // che legge il buffer intero): sull'una o sull'altra tratta la scrittura
    // nel viewport dice comunque quale delle due geometrie l'ha fatta.
    headers: { get: (nome) => (nome === 'X-Vertices' ? marcatore : 0) },
    arrayBuffer: async () => new ArrayBuffer(marcatore * 12),
  })));
};
const giro = async () => { for (let i = 0; i < 8; i += 1) await Promise.resolve(); };

__FUNZIONI__

// Step __NUMERO__ aperto, «Esegui questo step», riclic sullo stesso step
// mentre gira.
ricaricaVista(__NUMERO__, generazione);   // il clic: apre la richiesta 1
await giro();
ricaricaVista(__NUMERO__);                // il fronte di discesa: stessa generazione, richiesta 2
await giro();
assert.equal(sospese.length, 2, 'le due richieste non sono partite');
sospese[1]();                    // il contorno nuovo arriva per primo
await giro();
sospese[0]();                    // la risposta del clic, col contorno vecchio, arriva per ultima
await giro();

assert.deepEqual(scritture, [__ATTESO__],
  'scritture nel viewport: ' + JSON.stringify(scritture));
"""


@pytest.mark.parametrize(
    ("numero", "atteso"),
    [
        # 9 sta in STEP_CON_MESH del banco: mostraStep gira la tratta della
        # mesh davvero, senza delegare.
        pytest.param(9, "'mesh:2', 'riallinea:9'", id="mesh"),
        # 2 non sta in STEP_CON_MESH del banco: mostraStep delega subito a
        # mostraNuvolaDelloStep, che e' la tratta che il giro 2 non eseguiva
        # mai — il suo banco usava solo lo step 9.
        pytest.param(2, "'nuvola:2', 'riallinea:2'", id="nuvola"),
    ],
)
def test_fra_due_geometrie_della_stessa_generazione_vince_chi_e_partita_dopo(numero, atteso):
    """IMP-1. L'arbitraggio **eseguito**, non letto, su tutte e due le tratte.

    I tre asserti testuali del test qui sopra guardano la forma — una
    `apriGeometria()` per strada, la guardia presente, la delega prima del
    contatore — e restano tutti e tre veri se `const emissione =
    apriGeometria();` si sposta **dopo** la `fetch`, in una tratta o
    nell'altra: `mostraStep` e `mostraNuvolaDelloStep` hanno la stessa forma.
    Ma spostata li' l'emissione smette di essere il numero di **partenza** e
    diventa quello di **arrivo**, cioe' esattamente cio' che il secondo
    contatore doveva togliere di mezzo: le due risposte tornano ad arbitrarsi
    per arrivo e il contorno vecchio si riposa sopra quello nuovo.

    Un banco che esercitasse solo lo step 9 proverebbe solo `mostraStep`:
    lo spostamento nell'altra funzione passerebbe intatto con la suite
    intera verde, perche' nessuna riga eseguirebbe mai
    `mostraNuvolaDelloStep`. Da qui il parametro: stesso banco, uno step
    dentro `STEP_CON_MESH` e uno fuori.

    Qui le funzioni vere girano davvero, sopra una quarantina di righe di stub
    e senza nessun motore di DOM, ed e' lo stesso idioma di
    `test_una_risposta_superata_si_scarta_e_una_corrente_no` e
    `test_l_ingombro_non_conta_il_box_di_ritaglio`. Con quello spostamento, sulla
    tratta toccata, il banco stampa due scritture in piu': la geometria vecchia
    scrive per seconda e il cursore del taglio si rifa' due volte.
    """
    from meshrec.app.server import UI_DIR

    node = shutil.which("node")
    if node is None:
        pytest.skip("node non installato: l'arbitraggio resta verificato a mano")
    testo = (UI_DIR / "app.js").read_text(encoding="utf-8")
    funzioni = "\n".join(
        _sorgente_di(nome, testo)
        for nome in (
            "superata",
            "apriGeometria",
            "didascaliaDellaVista",
            "nomeDelloStep",
            "dichiaraCaricamento",
            "corpoBinarioLetto",
            "ragioneDelRifiuto",
            "messaggioDownloadInterrotto",
            "segnalaArtefattoMancante",
            "mostraNuvolaDelloStep",
            "mostraStep",
            # `ricaricaVista` risolve il ripiego prima di chiedere la geometria:
            # senza questa, il banco cade su un riferimento che non esiste.
            "passoDaMostrare",
            # Il velo del passaggio a monte, VERO e non stubbato: si posa dentro
            # il `then` di mostraStep, cioe' proprio in mezzo alle due richieste
            # che questo banco tiene sospese, e sullo step 2 un fantasma esiste.
            # Qui l'ordine di rilascio e' «arriva prima la nuova», e in
            # quell'ordine un velo che bumpasse `ultimaGeometria` non
            # cambierebbe l'esito: scarterebbe la vecchia, che era gia' da
            # scartare. E' l'ordine opposto che morde, e lo prova
            # test_il_velo_non_arbitra_al_posto_delle_geometrie qui sotto.
            # Vero e non stubbato lo stesso: se un domani il velo aprisse una
            # geometria PRIMA del `then`, e' questo banco a vederlo.
            "apriFantasma",
            "fantasmaHaSenso",
            "comandoDelFantasma",
            "mostraFantasmaDelloStep",
            "ricaricaVista",
            # Il taglio della coda delle normali: `mostraStep` la chiama per
            # passarle alla vista, e senza il ritaglio il banco cade su un
            # riferimento che non esiste — cioe' su nessuna scrittura nel
            # viewport, che e' esattamente cio' che questo banco conta.
            "normaliDellaRisposta",
        )
    )
    banco = (
        _BANCO_ORDINE.replace("__FUNZIONI__", funzioni)
        .replace("__NUMERO__", str(numero))
        .replace("__ATTESO__", atteso)
    )
    # Nome per step: due prove dello stesso modulo, in parallelo con -n, non
    # devono scriversi addosso lo stesso file .mjs.
    prova = Path(__file__).parent / f"_prova_arbitraggio_{numero}.mjs"
    prova.write_text(banco, encoding="utf-8")
    try:
        esito = subprocess.run([node, str(prova)], capture_output=True, text=True)
        assert esito.returncode == 0, esito.stderr
    finally:
        prova.unlink()


def test_la_luce_segue_la_camera_e_non_sta_ferma_nel_mondo():
    """Il difetto che Mario ha visto girando la figura: mezzo giro e il pezzo
    diventa una sagoma grigia uniforme, senza un'ombra, in cui la forma non si
    legge. La luce direzionale stava ferma a `(1, 2, 3)` mentre la camera
    girava, quindi dal lato opposto restava solo l'ambiente.

    Misurato nel browser il 24/08/2026 sul telaio di lab_crop, non dedotto.

    Strutturale e non eseguito: `aggiornaCamera` e' annidata dentro
    `creaViewport`, e il banco di test_app_js.py sa ritagliare solo funzioni di
    primo livello. La prova che conta resta quella a schermo -- questa
    sorveglia la mossa, cioe' che la luce non torni a essere una costante.
    """
    from meshrec.app.server import UI_DIR

    testo = (UI_DIR / "viewport.js").read_text(encoding="utf-8")

    # 1. Nessuna posizione costante: e' esattamente cio' che rendeva buio un lato.
    assert "direzionale.position.set(" not in testo, (
        "la luce e' tornata a una posizione fissa nel mondo"
    )

    # 2. La riposiziona chi muove la camera, non qualcun altro.
    corpo = testo.split("function aggiornaCamera() {", 1)[1].split("\n  }\n", 1)[0]
    assert "direzionale.position.copy(camera.position)" in corpo, (
        "la luce non segue piu' la camera"
    )
    assert "direzionale.target.position.copy(centro)" in corpo, (
        "la luce non punta piu' al centro dell'orbita: sul modello, che sta a "
        "qualche metro dall'origine, lo illuminerebbe di taglio"
    )

    # 3. Scostata dall'asse dello sguardo: una luce sull'occhio non fa ombre,
    #    che e' lo stesso difetto per un'altra strada.
    assert "_destra" in corpo and "_alto" in corpo, (
        "la luce e' finita esattamente sull'occhio: illumina di fronte e non da' rilievo"
    )

    # 4. Il bersaglio dev'essere nel grafo, altrimenti il suo matrixWorld resta
    #    quello con cui e' nato e spostarlo non cambia dove la luce punta.
    assert "scena.add(direzionale.target)" in testo, (
        "il bersaglio della luce non e' nella scena: spostarlo non ha effetto"
    )


def test_svuota_libera_i_buffer_e_non_tocca_i_piani_di_taglio():
    """I-5. gruppo.clear() toglie dalla scena e non libera: senza dispose ogni
    passaggio fra step lascia i suoi buffer sulla scheda. E i piani di taglio
    non sono una risorsa da liberare: sono condivisi apposta perche'
    sopravvivano alla geometria (Task 13), e azzerarli qui farebbe nascere la
    geometria nuova senza taglio mentre il comando lo dichiara attivo."""
    from meshrec.app.server import UI_DIR

    testo = (UI_DIR / "viewport.js").read_text(encoding="utf-8")
    # `function svuota()` nella chiusura di creaViewport, chiusa a due spazi.
    corpo = testo.split("function svuota() {", 1)[1].split("\n  }\n", 1)[0]
    assert "geometry?.dispose()" in corpo
    assert "material?.dispose()" in corpo
    righe = [r for r in corpo.splitlines() if not r.strip().startswith("//")]
    assert not any("pianiTaglio" in r for r in righe), "svuota() tocca i piani di taglio"


def test_l_ingombro_non_conta_il_box_di_ritaglio():
    """I-1. Il Box3Helper sta dentro `gruppo` perche' svuota() lo liberi con gli
    altri, ma `gruppo` e' anche cio' che `ingombro()` e `inquadra()` misurano.
    Contandolo, `ingombro()` smette di restituire l'ingombro della geometria e
    restituisce l'unione con un rettangolo che l'utente allarga a piacere: il
    Task 13 ci tara l'intervallo del cursore del taglio, e `pannelloRitaglio`
    ci riprecompila i sei campi, allargandosi a ogni giro senza tornare
    indietro.

    Eseguito, non letto: `box.visible = false` — la correzione piu' corta che
    la revisione suggeriva — qui si vedrebbe passare, perche'
    `Box3.expandByObject` non guarda `visible` (three.js r180). La
    funzione vera del viewport gira sopra il three.js vendorizzato, che e' lo
    stesso che il browser riceve.
    """
    from meshrec.app.server import UI_DIR

    node = shutil.which("node")
    if node is None:
        pytest.skip("node non installato: l'ingombro resta verificato a mano")
    testo = (UI_DIR / "viewport.js").read_text(encoding="utf-8")
    # scatolaDelGruppo sta dentro creaViewport, quindi non chiude in prima
    # colonna: si taglia sulla graffa al suo livello di rientro.
    sorgente = "function scatolaDelGruppo" + testo.split("function scatolaDelGruppo", 1)[1].split(
        "\n  }\n", 1
    )[0] + "\n  }"
    prova = Path(__file__).parent / "_prova_ingombro.mjs"
    prova.write_text(
        f"import * as THREE from {(UI_DIR / 'vendor' / 'three.core.min.js').as_uri()!r};\n"
        "import assert from 'node:assert/strict';\n"
        "const gruppo = new THREE.Group();\n"
        "const box = new THREE.Box3Helper(new THREE.Box3(), new THREE.Color(0xc4671b));\n"
        "box.box.set(new THREE.Vector3(-1000, -1000, -1000), new THREE.Vector3(1000, 1000, 1000));\n"
        "function punti(coordinate) {\n"
        "  const geometria = new THREE.BufferGeometry();\n"
        "  geometria.setAttribute('position',"
        " new THREE.BufferAttribute(new Float32Array(coordinate), 3));\n"
        "  return new THREE.Points(geometria, new THREE.PointsMaterial());\n"
        "}\n"
        "gruppo.add(punti([0, 0, 0, 10, 20, 30]));\n"
        + sorgente + "\n"
        "const solaNuvola = scatolaDelGruppo();\n"
        "assert.deepEqual(solaNuvola.min.toArray(), [0, 0, 0]);\n"
        "assert.deepEqual(solaNuvola.max.toArray(), [10, 20, 30]);\n"
        # Il box entra nel gruppo e viene reso: e' dopo un fotogramma che
        # Box3Helper.updateMatrixWorld scrive position e scale dal proprio box,
        # ed e' quello che setFromObject leggerebbe.
        "gruppo.add(box);\n"
        "box.updateMatrixWorld(true);\n"
        "const conIlBox = scatolaDelGruppo();\n"
        "assert.deepEqual(conIlBox.min.toArray(), solaNuvola.min.toArray(),"
        " 'il box di ritaglio e entrato nell ingombro');\n"
        "assert.deepEqual(conIlBox.max.toArray(), solaNuvola.max.toArray(),"
        " 'il box di ritaglio e entrato nell ingombro');\n"
        # E cambia quando cambia la geometria: senza questo, un ingombro
        # sempre vuoto passerebbe gli asserti qui sopra.
        "gruppo.add(punti([-5, -5, -5]));\n"
        "assert.deepEqual(scatolaDelGruppo().min.toArray(), [-5, -5, -5],"
        " 'l ingombro non segue piu la geometria');\n",
        encoding="utf-8",
    )
    try:
        esito = subprocess.run([node, str(prova)], capture_output=True, text=True)
        assert esito.returncode == 0, esito.stderr
    finally:
        prova.unlink()


def test_un_campo_del_ritaglio_lasciato_vuoto_non_muove_il_box():
    """M-1. `Number("")` e' 0, non NaN: cancellare il contenuto di «min x»
    portava quell'estremo a zero, il box saltava all'origine e «Applica il
    ritaglio» mandava 0 al server, che lo accettava. Nessun messaggio, e il
    numero che tornava era quello di un box che nessuno aveva disegnato.
    """
    from meshrec.app.server import UI_DIR

    sorgente = _sorgente_di("pannelloRitaglio", (UI_DIR / "app.js").read_text(encoding="utf-8"))
    assert "Number.isFinite" in sorgente, "un campo vuoto o a meta' muove ancora il box"
    assert not re.search(r"valori\[estremo\]\[asse\]\s*=\s*Number\(", sorgente), sorgente


def test_la_riga_d_errore_resta_nell_albero_anche_da_vuota():
    """M-3. La meta' funzionale di R75 vive in una regola di stile.css, file che
    nessun test sorvegliava: se una riscrittura del sistema visivo la perdesse,
    R75 regredirebbe in silenzio e la suite resterebbe verde.

    La regola deve esserci e non deve essere `display: none`: nascondere cosi'
    la regione `role="alert"` la toglie dall'albero di accessibilita', che e'
    esattamente il difetto che R75 chiedeva di chiudere. A contenuto vuoto il
    paragrafo non genera line box e ha altezza zero da solo: alla regola serve
    azzerare il margine, non toglierlo dal flusso.
    """
    from meshrec.app.server import UI_DIR

    foglio = (UI_DIR / "stile.css").read_text(encoding="utf-8")
    assert re.search(r"\.errore:empty\s*\{", foglio), "la regola .errore:empty e' sparita da stile.css"
    regola = foglio.split(".errore:empty", 1)[1].split("}", 1)[0]
    assert "display" not in regola, f"display toglie la regione role=alert dall'albero: {regola}"
    # E nessun ramo del modulo la rimette dietro hidden, che e' la strada per
    # cui il difetto era arrivato la prima volta.
    testo = (UI_DIR / "app.js").read_text(encoding="utf-8")
    assert not re.search(r"rigaErrore\.hidden", testo), "un ramo nasconde di nuovo la riga d'errore"


def test_l_intervallo_del_cursore_di_taglio_esce_da_una_lettura_e_non_da_numeri_scritti():
    """Il cursore del taglio mostra una quota in millimetri: se i suoi estremi
    fossero scritti nel codice sarebbe una cifra che nessuna lettura sostiene, e
    sul muro di riferimento (2470,99 x 231,00 x 1697,00 mm) sarebbe sbagliata
    per due assi su tre. min, max e step devono venire dall'ingombro della
    geometria disegnata, che il viewport misura.

    MI-1 della revisione: la scansione e' testuale e vede solo il corpo di
    riallineaTaglio, quindi copre la cifra scritta accanto all'assegnamento e
    la costante scritta a mano dentro il corpo, che e' il modo naturale in cui
    un numero rientra dopo essere stato tolto. Non copre, e non puo' coprire
    senza interpretare il modulo, un `const QUOTA_MINIMA = 0` dichiarato fuori
    dalla funzione: quello lo prenderebbe solo un test che esegue il codice, e
    l'interfaccia non ha un motore JS sotto test.
    """
    from meshrec.app.server import UI_DIR

    testo = (UI_DIR / "app.js").read_text(encoding="utf-8")
    corpo = testo.split("function riallineaTaglio", 1)[1].split("\n}\n", 1)[0]
    assert "vista.ingombro()" in corpo
    for riga in corpo.splitlines():
        assegnamento = re.search(r"quotaTaglio\.(min|max|step|value)\s*=\s*(.+)", riga)
        if assegnamento:
            assert not re.match(r"-?\d", assegnamento.group(2)), riga
    # Nemmeno dietro un nome: un `const QUOTA_MINIMA = 0;` dichiarato nel corpo
    # e usato due righe sotto passerebbe intatto dalla scansione qui sopra.
    assert not re.search(r"\b(?:const|let|var)\s+\w+\s*=\s*-?\d", corpo), corpo

    # Nemmeno nel markup: scritti li' non li vedrebbe nessun test sul codice.
    pagina = (UI_DIR / "index.html").read_text(encoding="utf-8")
    cursore = pagina.split('id="taglio-quota"', 1)[0].rsplit("<input", 1)[1]
    for attributo in ("min", "max", "step", "value"):
        assert f"{attributo}=" not in cursore, cursore


def test_il_cursore_del_taglio_ha_una_posizione_spenta_e_ci_parte():
    """IM-2. `disattivaTaglio()` esisteva nel viewport e l'interfaccia non la
    raggiungeva: `riallineaTaglio` chiamava `applicaTaglio()` sempre, il taglio
    si accendeva da solo appena il comando compariva e l'unico modo di
    spegnerlo era uscire dallo step. Il primo scatto del cursore e' la
    posizione spenta, ed e' quella da cui si parte: il volume compare intero e
    ci si torna trascinando a sinistra, senza lasciare lo step.

    Spenta e non «un taglio che non toglie niente» (IM-3): alla quota del
    minimo il piano sarebbe complanare alla faccia estrema, e three.js tiene i
    punti con normale . punto + costante > 0. Cosi' invece nessuna quota
    tagliata e' complanare, perche' la prima vale minimo + passo.

    Tutto testuale: il resto e' `quota <= minimo`, un confronto, e una funzione
    pura che lo avvolge proverebbe il segno di minore, non il comportamento.
    Quello resta da guardare a video, e il rapporto dice come.
    """
    from meshrec.app.server import UI_DIR

    testo = (UI_DIR / "app.js").read_text(encoding="utf-8")
    applica = _sorgente_di("applicaTaglio", testo)
    assert "vista.disattivaTaglio()" in applica, "il cursore non puo' spegnere il taglio"
    # Spento e' una posizione del cursore, non un caso a parte: il confronto e'
    # con il minimo del cursore stesso, cosi' vale su ogni asse e ogni geometria.
    assert re.search(r"quotaTaglio\.min\b", applica), applica
    riallinea = _sorgente_di("riallineaTaglio", testo)
    # E si parte da li': min e value sono lo stesso estremo dell'ingombro.
    assert re.search(r"quotaTaglio\.min\s*=\s*minimo\b", riallinea), riallinea
    assert re.search(r"quotaTaglio\.value\s*=\s*minimo\b", riallinea), riallinea


def test_il_fronte_di_discesa_ricarica_anche_la_vista_e_non_solo_il_pannello():
    """IM-4. Si rieseguiva lo step aperto e il pannello mostrava le metriche
    nuove mentre il viewport teneva il contorno vecchio, col cursore del taglio
    tarato su un ingombro che non esisteva piu'. Le due avvertenze del giro 2
    valgono anche qui: il ricaricamento non apre una generazione (prende quella
    in corso, cosi' un clic dell'utente lo batte) e non chiede niente se cio'
    che e' disegnato non puo' essere stato riscritto.
    """
    from meshrec.app.server import UI_DIR

    testo = (UI_DIR / "app.js").read_text(encoding="utf-8")
    # Dal corpo di `aggiornaDaStato` e non piu' da quello del gestore: il
    # gestore adesso e' una riga che delega, e cio' che c'era dentro ha un nome
    # -- che e' il punto, perche' dentro una freccia anonima non lo eseguiva
    # nessun banco. Che il fronte di discesa faccia le due cose lo prova
    # test_app_js.py::test_il_fronte_di_discesa_annuncia_l_esito_e_ricarica,
    # eseguendo; qui restano i tre fatti di FORMA che l'esecuzione non vede --
    # quale generazione si usa, e su quali step si chiede.
    corpo = testo.split("function aggiornaDaStato(stato) {", 1)[1].split("\n}\n", 1)[0]
    assert "apriDettaglio(stepAperto)" in corpo
    assert "ricaricaVista(stepScelto)" in corpo, "la vista resta indietro sul fronte di discesa"
    assert "stepScelto >= stato.step" in corpo, "chiede anche cio' che nessuna corsa ha toccato"
    assert "apriGenerazione" not in corpo, "il fronte di discesa annulla una geometria in volo"
    # Lo stesso punto serve il clic: se il clic smettesse di passarci, il
    # riallineamento del cursore resterebbe scritto per un solo chiamante.
    # Dal 10/09/2026 il clic delega a `scegliStep`, che ha un nome perche' lo
    # chiama anche il giro di «Salva tutti gli step»: si segue quella sola
    # delega. Il solo corpo del gestore, fino alla graffa che lo chiude: sul
    # resto del file la ricerca troverebbe la definizione di ricaricaVista, che
    # sta piu' sotto, e passerebbe anche con un clic che non ci passa piu'.
    gestore = testo.split('getElementById("elenco-step").addEventListener', 1)[1]
    gestore = gestore.split("\n});", 1)[0]
    assert re.search(r"scegliStep\(", gestore), gestore
    assert re.search(r"ricaricaVista\(numero[,)]", _sorgente_di("scegliStep", testo))


def test_i_moduli_dell_interfaccia_sono_sintatticamente_validi():
    """node --check prende gli errori di sintassi che altrimenti si scoprono
    solo aprendo la pagina, dove nessuna suite guarda."""
    from meshrec.app.server import UI_DIR

    node = shutil.which("node")
    if node is None:
        pytest.skip("node non installato: la sintassi resta verificata a mano")
    for percorso in sorted(UI_DIR.rglob("*.js")):
        if "vendor" in percorso.parts:
            continue
        esito = subprocess.run(
            [node, "--check", str(percorso)], capture_output=True, text=True,
        )
        assert esito.returncode == 0, f"{percorso.name}: {esito.stderr}"


#: sha256 dei due file di three.js r180 come stanno nel repo, verificati contro
#: il tarball firmato del registry npm (vedi ui/vendor/README.md). Il controllo
#: precedente era `len(content) > 100_000`, che dice «il file e' grosso» e non
#: «il file e' quello»: un bundle sostituito e' servito con l'origine
#: dell'interfaccia, quindi puo' chiamare da solo ogni /api/, POST
#: /api/step/{n} compresa -- che lancia un sottoprocesso.
IMPRONTE_VENDOR = {
    "three.core.min.js": "61ba0df005b05991361d040d8ff670e1aadfd0ce7aeebd1fdb0725957a8957de",
    "three.module.min.js": "e2b5ee6bccd38fd6d8a2428546b83c5f2426d84b152ef82be8055556e3b40eb6",
}


def test_three_js_e_servito_dal_server_e_non_dalla_rete(cliente):
    for nome, atteso in IMPRONTE_VENDOR.items():
        risposta = cliente.get(f"/ui/vendor/{nome}")
        assert risposta.status_code == 200
        impronta = hashlib.sha256(risposta.content).hexdigest()
        assert impronta == atteso, (
            f"{nome} non e' il bundle verificato: se l'aggiornamento e' voluto, "
            f"rifai la verifica in ui/vendor/README.md e aggiorna l'impronta"
        )


def test_nessun_riferimento_a_una_rete_esterna_nell_interfaccia():
    """Il server e' locale e l'applicazione deve partire senza rete."""
    from meshrec.app.server import UI_DIR

    for percorso in UI_DIR.rglob("*"):
        if percorso.suffix not in {".html", ".js", ".css"} or "vendor" in percorso.parts:
            continue
        testo = percorso.read_text(encoding="utf-8")
        for sospetto in ("https://", "http://", "//cdn.", "unpkg", "jsdelivr"):
            assert sospetto not in testo, f"{percorso.name} punta fuori dalla macchina"


def test_le_metriche_tornano_quelle_scritte_su_disco(cliente, tmp_path):
    from meshrec.core import pipeline

    corsa = tmp_path / "corsa"
    corsa.mkdir()
    (corsa / pipeline.METRICS_FILENAME).write_text(
        json.dumps({"01_load": {"points_kept": 6_329_096}}), encoding="utf-8"
    )
    # Lo stato per primo: con raise_server_exceptions=False un errore diventa
    # un 400 con corpo {"errore", "messaggio"}, e leggere il corpo darebbe un
    # KeyError che non nomina la causa vera (M-6 della revisione).
    risposta = cliente.get("/api/metrics")
    assert risposta.status_code == 200
    assert risposta.json()["01_load"]["points_kept"] == 6_329_096


def test_le_metriche_di_una_corsa_mai_eseguita_sono_vuote_e_non_sollevano(cliente):
    risposta = cliente.get("/api/metrics")
    assert risposta.status_code == 200
    assert risposta.json() == {}


def test_la_rotta_del_catalogo_dei_materiali_non_esiste_piu(cliente):
    """Ingresso degenere: qualcuno chiede ancora `/api/materiali`.

    Il catalogo serviva il pannello del materiale, uscito il 08/09/2026 con la
    PR feat/deck-nudo-analisi: il materiale si assegna in Abaqus sull'`*ELSET`,
    e una tratta che nessuno interroga e' codice che nessun consumatore
    sorveglia.

    Mutazione che lo uccide: rimettere la rotta. La risposta torna 200.
    """
    assert cliente.get("/api/materiali").status_code == 404


def test_lo_schema_dice_quali_parametri_appartengono_a_ogni_step(cliente):
    risposta = cliente.get("/api/schema")
    assert risposta.status_code == 200
    corpo = risposta.json()
    assert corpo["5"]["blocchi"] == ["surface"]
    assert "poisson_depth" in corpo["5"]["campi"]["surface"]
    assert corpo["5"]["campi"]["surface"]["poisson_depth"]["description"]
    # Un campo obbligatorio non ha un predefinito: deve uscire null e non la
    # stringa "PydanticUndefined", che somiglia a un valore (M-5).
    assert corpo["1"]["campi"]["input"]["path"]["default"] is None


def test_lo_schema_dice_di_che_tipo_e_ogni_campo(cliente):
    """Il tipo lo conosce solo il modello, e il pannello ne ha bisogno per
    scegliere la casella: un menu, una spunta, uno slider o una casella di
    testo. Letto dalle annotazioni di pydantic e non da una tabella scritta a
    mano, che sarebbe una seconda verita' da tenere allineata al modello.
    """
    corpo = cliente.get("/api/schema").json()
    assert corpo["5"]["campi"]["surface"]["poisson_depth"]["tipo"] == "intero"
    assert corpo["9"]["campi"]["tet"]["min_ratio"]["tipo"] == "reale"
    assert corpo["8"]["campi"]["simplify"]["enabled"]["tipo"] == "booleano"
    # `Path` e' un tipo composto per python ma una riga di testo per chi la
    # batte: e' il campo piu' importante del pannello dello step 1, e una
    # casella in sola lettura lo renderebbe modificabile solo dal file.
    assert corpo["1"]["campi"]["input"]["path"]["tipo"] == "testo"
    assert corpo["2"]["campi"]["segment"]["method"]["tipo"] == "enumerazione"
    assert corpo["2"]["campi"]["segment"]["method"]["valori"] == ["crop", "auto"]
    # Un `Literal` con un valore solo resta un'enumerazione: e' il pannello a
    # decidere che un menu con una voce sola non e' un menu.
    assert corpo["5"]["campi"]["surface"]["method"]["valori"] == ["poisson"]
    # Una tupla e una lista non si scrivono in una casella di testo.
    assert corpo["1"]["campi"]["input"]["expected_size"]["tipo"] == "composto"
    # Nullabile: il vuoto e' un valore, e nessuno slider ne' nessuna spunta sa
    # esprimerlo. Il pannello ha bisogno di distinguerlo dall'obbligatorio.
    assert corpo["3"]["campi"]["downsample"]["voxel_size"]["nullabile"] is True
    assert corpo["3"]["campi"]["downsample"]["voxel_factor"]["nullabile"] is False


def test_lo_schema_distingue_gli_estremi_inclusi_da_quelli_esclusi(cliente):
    """`ge` e `gt` non sono la stessa cosa: uno slider che li confonde offre
    un valore che il modello rifiuta. Le quattro chiavi portano i nomi dei
    vincoli di pydantic, e ciascuna compare solo dove il modello la dichiara.
    """
    corpo = cliente.get("/api/schema").json()
    quantile = corpo["5"]["campi"]["surface"]["density_quantile"]
    assert quantile["ge"] == 0.0 and quantile["lt"] == 1.0
    assert "gt" not in quantile and "le" not in quantile
    ratio = corpo["2"]["campi"]["segment"]["plane_min_points_ratio"]
    assert ratio["gt"] == 0.0 and ratio["le"] == 1.0
    profondita = corpo["5"]["campi"]["surface"]["poisson_depth"]
    assert profondita["ge"] == 4 and profondita["le"] == 14
    # Un estremo solo resta un estremo solo: il pannello non deve poterne
    # dedurre un fondo scala che il modello non dichiara.
    assert corpo["9"]["campi"]["tet"]["min_ratio"]["gt"] == 0.0
    assert "le" not in corpo["9"]["campi"]["tet"]["min_ratio"]
    assert "lt" not in corpo["9"]["campi"]["tet"]["min_ratio"]


def test_lo_schema_porta_l_etichetta_dove_il_modello_la_dichiara(cliente):
    """«Una chiave non si stampa mai, si stampa la sua etichetta» (PRODUCT.md).

    Il canale e' `title`, che pydantic porta gia' accanto a `description`:
    dove c'e', il pannello la mostra al posto della chiave; dove manca, la
    chiave resta l'unica cosa che si sa e non si inventa una frase.
    """
    corpo = cliente.get("/api/schema").json()
    etichetta = corpo["8"]["campi"]["simplify"]["enabled"]["etichetta"]
    assert etichetta and etichetta != "enabled", (
        "`simplify.enabled` mostra ancora la chiave grezza: dice che si accende "
        "qualcosa senza dire che cosa"
    )
    # Dove il modello non dichiara `title` non si inventa nulla. La prova sta
    # su `_forma_del_campo`, che e' il punto in cui l'etichetta nasce, e non su
    # un campo del pannello: di campi del pannello senza etichetta non ne deve
    # restare nessuno, ed e' il test qui sotto a dirlo.
    from pydantic import BaseModel

    from meshrec.app.server import _forma_del_campo

    class SenzaTitolo(BaseModel):
        anonimo: int = 0

    assert "etichetta" not in _forma_del_campo(SenzaTitolo.model_fields["anonimo"])


def test_nessun_campo_del_pannello_si_mostra_con_la_chiave_grezza(cliente):
    """«Una chiave non si stampa mai, si stampa la sua etichetta» (PRODUCT.md).

    Senza `title` il pannello ripiega sulla chiave, e chi apre il programma
    legge `plane_min_points_ratio`, `density_quantile`, `nobisect`. La regola
    vale per tutti i campi che l'interfaccia mostra e non per quelli che di
    volta in volta se ne ricordano: la prova gira sull'elenco vero di
    `/api/schema`, cosi' un campo aggiunto domani senza etichetta la fa
    cadere.

    Mutazione che lo uccide: togliere `title=` a un campo qualunque di
    `PipelineConfig` fra quelli che uno step mostra.
    """
    corpo = cliente.get("/api/schema").json()
    nudi = {
        f"{blocco}.{nome}"
        for voce in corpo.values()
        for blocco, campi in voce["campi"].items()
        for nome, campo in campi.items()
        if not campo.get("etichetta")
    }
    assert not nudi, "campi senza etichetta, di cui il pannello stampa la chiave: " + ", ".join(
        sorted(nudi)
    )


def test_l_etichetta_non_e_la_chiave_ribattuta(cliente):
    """Un'etichetta che ripete la chiave non e' un'etichetta.

    `title="nobisect"` passerebbe il controllo qui sopra e a video non
    cambierebbe niente: la regola e' che l'etichetta dica la grandezza in
    italiano, non che esista.
    """
    corpo = cliente.get("/api/schema").json()
    ribattute = {
        f"{blocco}.{nome}"
        for voce in corpo.values()
        for blocco, campi in voce["campi"].items()
        for nome, campo in campi.items()
        if campo.get("etichetta", "").strip().lower() == nome.lower()
    }
    assert not ribattute, "etichette che ripetono la chiave: " + ", ".join(sorted(ribattute))


def test_il_pannello_dello_step_11_mostra_solo_i_blocchi_che_comanda(cliente):
    """`STEP_BLOCKS` assegna blocchi interi: e' la tabella da cui discende
    l'invalidazione a valle (`steps.step_fingerprints`), e toglierne un blocco
    sposta le impronte delle corse gia' su disco -- deciso una volta col deck
    nudo, non una manovra di questo endpoint. La correzione di cio' che si
    **vede** e' a grana di campo, dentro `schema()`.

    Lo step 11 esporta il modello: non tetraedrizza (quello e' il 9).
    `regioni` e' un `dict[NomeSet, RegioneConfig]`, cioe' una sezione vuota per
    costruzione: una sezione che non puo' mai contenere nulla non compare.
    """
    from meshrec.core import steps

    assert steps.STEP_BLOCKS[11] == ("tet", "export", "regioni"), (
        "STEP_BLOCKS e' stata cambiata: la catena delle impronte a valle "
        "discende da li'"
    )
    corpo = cliente.get("/api/schema").json()
    assert corpo["11"]["blocchi"] == ["export"]
    assert set(corpo["11"]["campi"]) == {"export"}
    # Il blocco `export` porta una cosa sola: la tolleranza con cui lo step 11
    # estrae i set di faccia. Materiale, gravita', vincolo e passo di carico
    # sono usciti col deck nudo -- il deck non li scrive piu', quindi non c'e'
    # piu' nulla da dichiarare qui.
    assert set(corpo["11"]["campi"]["export"]) == {"set_tolerance_factor"}
    # Il blocco resta intero dove lo step lo comanda davvero.
    assert corpo["9"]["blocchi"] == ["tet"] and corpo["9"]["campi"]["tet"]


def test_reference_ratio_sta_nel_pannello_dello_step_che_lo_usa(cliente):
    """E' il metro con cui lo step 10 conta gli elementi fuori vincolo, e non
    tocca nulla di cio' che lo step 9 fa: nel pannello del 9 sembrerebbe un
    secondo `min_ratio`.
    """
    corpo = cliente.get("/api/schema").json()
    assert "reference_ratio" in corpo["10"]["campi"]["tet"]
    assert "reference_ratio" not in corpo["9"]["campi"]["tet"]
    assert "min_ratio" in corpo["9"]["campi"]["tet"], (
        "lo step 9 ha perso il vincolo che chiede davvero a TetGen"
    )


def test_il_tempo_dello_step_viene_dal_server_e_non_dal_browser(cliente):
    risposta = cliente.get("/api/events?max_eventi=1")
    assert risposta.status_code == 200
    stato = json.loads(risposta.text.split("data: ", 1)[1].split("\n", 1)[0])
    # L'ordine conta: la chiave prima, cosi' che la sua assenza fallisca
    # dicendo cosa manca; poi il valore, che smentisce un tempo inventato
    # mentre non gira nulla (M-7).
    assert "da_secondi" in stato
    assert stato["da_secondi"] is None


def test_il_cronometro_non_puo_tornare_nel_browser():
    """Il tempo trascorso deve venire dal server, dove lo step parte davvero.

    Senza questo controllo una riscrittura futura potrebbe rimettere il
    cronometro nel browser in silenzio, con la suite verde: il tempo
    ripartirebbe da zero a ogni ricarica mentre il calcolo prosegue (M-2).
    """
    from meshrec.app.server import UI_DIR

    for percorso in UI_DIR.rglob("*.js"):
        if "vendor" in percorso.parts:
            continue
        testo = percorso.read_text(encoding="utf-8")
        assert "Date.now" not in testo, f"{percorso.name} misura il tempo nel browser"
        assert "avvioStep" not in testo, f"{percorso.name} ha di nuovo un cronometro locale"


def test_nessun_endpoint_solleva_verso_il_browser(cliente):
    """Il contratto vale sull'elenco intero, derivato dall'applicazione stessa:
    un endpoint aggiunto domani vi entra da solo e non puo' essere dimenticato.
    """
    percorsi = [
        rotta.path
        for rotta in cliente.app.routes
        if getattr(rotta, "methods", None) and "GET" in rotta.methods
    ]
    assert len(percorsi) >= 3
    for percorso in percorsi:
        if "{" in percorso or percorso in STREAMING:
            continue
        risposta = cliente.get(percorso)
        assert risposta.status_code < 500, f"{percorso} ha sollevato verso il browser"


def test_la_cache_del_contorno_non_sfratta_quella_della_nuvola(cliente, tmp_path):
    """Le due cache condividono il marchio, e la pulizia cancella per marchio.

    Il marchio e' l'hash del solo percorso della sorgente, e
    viewport._rimuovi_voci_vecchie elimina ogni altra voce che lo porta. Nella
    stessa cartella, la nuvola e il contorno di uno stesso file si
    sfratterebbero a vicenda ad ogni scrittura, e il ricalcolo tornerebbe senza
    alcun segnale. Oggi non accade perche' read_cloud rifiuta un .vtu, cioe'
    per una ragione che sta in un altro modulo: questo test sorveglia la
    separazione, non quella ragione.
    """
    import numpy as np

    from meshrec.core import viewport

    sorgente = tmp_path / "corsa" / "09_volume.vtu"
    sorgente.parent.mkdir(parents=True, exist_ok=True)
    sorgente.write_bytes(b"non conta il contenuto: contano i nomi delle voci")

    voce_nuvola = viewport._cache_path(sorgente, 400_000, 20_000, 0, server.CACHE_DIR)
    voce_nuvola.parent.mkdir(parents=True, exist_ok=True)
    voce_nuvola.write_bytes(b"voce finta della nuvola")

    voce_contorno = server._percorso_contorno(sorgente)
    server._scrivi_contorno(
        voce_contorno,
        np.zeros((1, 3), dtype="<f4"),
        np.zeros((1, 3), dtype="<u4"),
        np.zeros((1,), dtype="<u4"),
    )
    viewport._rimuovi_voci_vecchie(voce_contorno.parent, voce_contorno)

    assert voce_contorno.exists()
    assert voce_nuvola.exists(), "scrivere il contorno ha cancellato la voce della nuvola"


def _nuvola_con_isolati(seme: int = 0):
    """Un ammasso denso piu' qualche punto isolato: remove_outliers ne toglie
    davvero, quindi la sua presenza o assenza si vede nel conteggio."""
    import numpy as np

    generatore = np.random.default_rng(seme)
    denso = generatore.random((5_000, 3)) * 20.0
    isolati = generatore.random((50, 3)) * 100.0
    return np.vstack([denso, isolati])


def test_l_anteprima_toglie_gli_outlier_prima_di_ritagliare_come_lo_step_2(cliente, tmp_path):
    """B-2. L'ordine e' quello dello step 2: remove_outliers e poi crop_box
    (core/segment.py:142-143). Il secondo asserto e' quello che morde: con un
    box che contiene tutto, saltare la pulizia darebbe il totale del file, cioe'
    un numero piu' alto di quello che lo step 2 produrrebbe."""
    from meshrec.core import io, pipeline, segment
    from meshrec.core.config import SegmentConfig

    punti = _nuvola_con_isolati()
    io.write_cloud(tmp_path / "corsa" / pipeline.ARTIFACTS[1], punti)

    tutto = {"min": [-1.0, -1.0, -1.0], "max": [101.0, 101.0, 101.0]}
    risposta = cliente.post("/api/crop", json=tutto)
    assert risposta.status_code == 200
    dal_server = risposta.json()["points_after"]

    puliti, _metriche = segment.remove_outliers(punti, SegmentConfig())
    assert dal_server == len(puliti)
    assert dal_server < len(punti), "l'anteprima non ha tolto nessun outlier: e' la nuvola grezza"


@pytest.mark.parametrize("metodo", ["crop", "auto"])
def test_l_anteprima_del_ritaglio_dice_esattamente_che_numero_e(cliente, tmp_path, metodo):
    """B-2 e BL-1. Il numero dell'anteprima, confrontato con lo step 2 eseguito.

    Il confronto «endpoint contro metrics.json» del primo giro era una
    tautologia: l'endpoint ritagliava 02_segmented.ply, cioe' l'uscita gia'
    ritagliata dello step 2, e ogni punto di quel file sta dentro il box che
    l'ha prodotto per costruzione. Qui il box chiesto all'anteprima e' piu'
    largo di quello che ha prodotto 02_segmented.ply: leggere l'uscita non puo'
    far tornare indietro i punti che quel file non contiene, quindi i due
    numeri divergono e il test lo dice.

    Lo step 2 viene eseguito davvero, non simulato: e' l'unico modo che il
    confronto ha di non essere un'altra tautologia.

    Parametrizzato su **tutti** i valori di `segment.method`, che e' un campo
    dello stesso pannello dell'anteprima: con `auto` lo step 2 prosegue dopo il
    ritaglio (extract_planes, cluster, `groups[cluster_index]`) e riscrive
    points_after, mentre l'anteprima si ferma al ritaglio. Fino al giro 2 la
    didascalia affermava lo stesso la coincidenza, e il test girava solo sul
    predefinito `crop`, quindi non poteva vederlo. La coincidenza si pretende
    dove esiste; dove non esiste si pretende che `completo` la neghi, e che i
    due numeri **divergano davvero** — senza quest'ultimo asserto una
    dichiarazione di incompletezza sarebbe verde anche su un'anteprima esatta,
    cioe' non direbbe niente.
    """
    from meshrec.core import io, pipeline
    from meshrec.core.config import RunConfig, load_config

    io.write_cloud(tmp_path / "corsa" / pipeline.ARTIFACTS[1], _nuvola_con_isolati())

    def esegui_lo_step_2(cfg) -> int:
        # from_step e to_step si assegnano insieme, con una sola validazione
        # dell'oggetto intero: e' quello che RunConfig documenta.
        cfg.run = RunConfig.model_validate({**cfg.run.model_dump(), "from_step": 2, "to_step": 2})
        return pipeline.run(cfg)["02_segment"]["points_after"]

    # Il metodo entra nella configurazione della corsa prima della richiesta:
    # e' da li' che l'endpoint lo legge, come lo leggerebbe dal pannello.
    scelta = load_config(tmp_path / "config.yaml")
    scelta.segment.method = metodo
    save_config(scelta, tmp_path / "config.yaml")

    # Il box stretto passa sempre da `crop`: serve solo a provare che il box
    # largo e' piu' largo, cioe' che l'anteprima non sta leggendo un artefatto
    # gia' ritagliato. Farlo con `auto` misurerebbe un cluster e non un box.
    stretto = load_config(tmp_path / "config.yaml")
    stretto.segment.method = "crop"
    stretto.segment.crop_min, stretto.segment.crop_max = (0.0, 0.0, 0.0), (10.0, 10.0, 10.0)
    dallo_stretto = esegui_lo_step_2(stretto)

    largo = {"min": [0.0, 0.0, 0.0], "max": [20.0, 20.0, 20.0]}
    risposta = cliente.post("/api/crop", json=largo)
    assert risposta.status_code == 200
    corpo = risposta.json()
    anteprima = corpo["points_after"]
    assert anteprima > dallo_stretto, "il box largo non e' piu' largo: il confronto non morderebbe"

    # /api/crop ha scritto crop_min e crop_max: lo step 2 li rilegge da li',
    # quindi i due lati stanno guardando davvero lo stesso box.
    davvero = esegui_lo_step_2(load_config(tmp_path / "config.yaml"))
    if metodo == "crop":
        assert corpo["completo"] is True
        assert anteprima == davvero
    else:
        assert corpo["completo"] is False, (
            f"l'anteprima si dichiara completa con method={metodo}, "
            f"ma dice {anteprima} dove lo step 2 ne tiene {davvero}"
        )
        assert anteprima != davvero, (
            "l'anteprima coincide con lo step 2 anche con method=auto: "
            "allora la dichiarazione di incompletezza non e' provata da nulla"
        )


def test_un_box_vuoto_non_solleva_ma_lo_dice(cliente, tmp_path):
    """La nuvola va scritta davvero, altrimenti il test passa per la ragione
    sbagliata: senza artefatto la richiesta muore su io.read_cloud e il 400
    arriva da li', anche se il ramo del box vuoto non esistesse. Con la nuvola
    sul posto il rifiuto puo' venire solo da crop_box, e il suo messaggio deve
    arrivare intero fino al browser: e' quello che dice dove guardare.
    """
    from meshrec.core import io, pipeline

    io.write_cloud(tmp_path / "corsa" / pipeline.ARTIFACTS[1], _nuvola_con_isolati())
    risposta = cliente.post("/api/crop", json={"min": [1e9, 1e9, 1e9], "max": [2e9, 2e9, 2e9]})
    assert risposta.status_code == 400
    corpo = risposta.json()
    assert "errore" in corpo
    assert "nelle unità di lavoro (mm)" in corpo["messaggio"]


# Arita' sbagliata, valore non numerico, NaN e chiave mancante: le forme che
# l'endpoint accettava o rifiutava male. L'arita' 1 e' quella che passava del
# tutto, perche' numpy trasmette (N,3) >= (1,) senza lamentarsi.
# I corpi sono JSON grezzo e non dizionari: NaN non e' JSON valido e nessun
# codificatore di Python lo scrive senza forzatura, ma json.loads lo legge, e
# quindi lato server arriva come un float. E' il caso che l'interfaccia non
# produce e che un altro cliente puo' produrre: il confine deve reggerlo.
@pytest.mark.parametrize(
    ("corpo", "campo"),
    [
        ('{"min": [10.0], "max": [60.0, 60.0, 60.0]}', "min"),
        ('{"min": [10.0, 10.0, 10.0], "max": [60.0, 60.0, 60.0, 60.0]}', "max"),
        ('{"min": [10.0, 10.0, "non un numero"], "max": [60.0, 60.0, 60.0]}', "min"),
        ('{"min": [NaN, 10.0, 10.0], "max": [60.0, 60.0, 60.0]}', "min"),
        ('{"min": [Infinity, 10.0, 10.0], "max": [60.0, 60.0, 60.0]}', "min"),
        ('{"min": [10.0, 10.0, 10.0]}', "max"),
        # MIN-1: bool e' sottotipo di int, quindi senza il controllo davanti
        # pydantic scriveva (1.0, 0.0, 1.0) in configurazione e rispondeva 200.
        ('{"min": [true, false, true], "max": [60.0, 60.0, 60.0]}', "min"),
    ],
)
def test_un_box_malformato_e_rifiutato_e_non_tocca_la_configurazione(cliente, tmp_path, corpo, campo):
    """B-1. Il rifiuto non basta: quello che rendeva il difetto permanente era
    la scrittura. `{"min":[10.0],"max":[60.0]}` rispondeva 200 e lasciava sul
    disco una tupla di uno in un campo dichiarato di tre; da li' in poi
    load_config rifiutava, e /api/config, /api/run e /api/crop stessa
    rispondevano 400 finche' qualcuno non riapriva config.yaml a mano.

    La nuvola va scritta davvero, altrimenti il test passa per la ragione
    sbagliata: senza artefatto la richiesta morirebbe comunque prima di
    scrivere, e passerebbe anche senza nessuna validazione al confine.

    Il confronto e' sui byte del file e non sul codice di stato: e' il file che
    governa la corsa, ed e' l'unica cosa che dice se la scrittura c'e' stata.
    """
    from meshrec.core import io, pipeline

    io.write_cloud(tmp_path / "corsa" / pipeline.ARTIFACTS[1], _nuvola_con_isolati())
    prima = (tmp_path / "config.yaml").read_bytes()

    risposta = cliente.post(
        "/api/crop", content=corpo, headers={"content-type": "application/json"}
    )
    assert risposta.status_code != 200, risposta.text
    assert campo in risposta.text, f"il rifiuto non dice quale campo: {risposta.text}"
    assert (tmp_path / "config.yaml").read_bytes() == prima, "il box rifiutato ha scritto lo stesso"
    # E la corsa resta leggibile: e' la conseguenza che rendeva il difetto
    # permanente invece che transitorio.
    assert cliente.get("/api/config").status_code == 200


# --------------------------------------------------------------------------
# La galleria di curazione e' uscita il 03/09/2026: era una finestra sui
# registri di sweep della Fase 2, e chi usa il programma non la apriva. Il
# core dello sweep resta; a sparire sono le rotte e la colonna.
# --------------------------------------------------------------------------


def test_le_rotte_della_galleria_non_esistono_piu(cliente):
    """Una rotta che sopravvive alla propria interfaccia e' codice che nessuno
    esercita e che continua a leggere il disco: va via con lei."""
    assert cliente.get("/api/experiments").status_code == 404
    assert cliente.get("/api/experiments/qualunque").status_code == 404
    assert not any(
        getattr(rotta, "path", "").startswith("/api/experiments")
        for rotta in cliente.app.routes
    )


def _cartella_di_corsa(cliente) -> Path:
    return Path(cliente.get("/api/run").json()["out_dir"])


# --------------------------------------------------------------------------
# L'esportazione del deck: /api/deck consegna il file dello step 11, non una
# sua copia ricalcolata.
# --------------------------------------------------------------------------


def _scrivi_deck(cliente, testo: str = "*HEADING\nmuro\n") -> Path:
    from meshrec.core import pipeline

    corsa = _cartella_di_corsa(cliente)
    corsa.mkdir(parents=True, exist_ok=True)
    percorso = corsa / pipeline.DECK_FILENAME
    percorso.write_text(testo, encoding="utf-8")
    return percorso


def test_il_deck_arriva_col_nome_della_corsa_davanti(cliente):
    """`wall_model.inp` scaricato da tre corse diverse da' tre file
    indistinguibili nella cartella dei download: la provenienza fa parte del
    risultato, e l'unico posto dove sopravvive allo scaricamento e' il nome.

    Il corpo e' il file com'e' su disco, byte per byte: e' quello che porta
    l'impronta nel registro ed e' quello di cui il report parla.
    """
    deck = _scrivi_deck(cliente)

    risposta = cliente.get("/api/deck")

    assert risposta.status_code == 200
    # I byte del file, non il testo: `text` passerebbe da una decodifica e da
    # una normalizzazione degli a capo, e un deck consegnato con gli a capo di
    # un altro sistema non e' piu' il file di cui il registro porta l'impronta.
    assert risposta.content == deck.read_bytes()
    disposizione = risposta.headers["content-disposition"]
    assert disposizione.startswith("attachment")
    assert 'filename="corsa_wall_model.inp"' in disposizione


def test_il_deck_mai_scritto_nomina_lo_step_da_eseguire(cliente):
    """La regola di `pipeline._ingresso_di_ripresa`: chi guarda l'interfaccia
    ragiona per step, non per nomi di file. «file non trovato» non dice a
    nessuno che deve eseguire lo step 11."""
    risposta = cliente.get("/api/deck")

    assert risposta.status_code == 400
    assert "step 11" in risposta.json()["messaggio"]


def test_una_corsa_di_riferimento_consegna_comunque_il_deck(cliente, tmp_path):
    """La sentinella ferma le scritture, non le letture.

    `runs/muro` e `runs/lab_crop` sono le corse di cui il deck serve DAVVERO --
    sono i risultati che finiscono in tesi -- e sono anche le due aperte in
    sola lettura. Una guardia messa qui per simmetria con le altre tratte
    renderebbe inesportabili proprio quelle.

    Mutazione che lo uccide: una chiamata a `non_in_sola_lettura` dentro
    `/api/deck`. Il 200 diventa 400.
    """
    (tmp_path / server.SENTINELLA_SOLA_LETTURA).touch()
    deck = _scrivi_deck(cliente)

    risposta = cliente.get("/api/deck")

    assert risposta.status_code == 200
    assert risposta.content == deck.read_bytes()


def test_un_deck_che_esce_dalla_cartella_della_corsa_non_viene_consegnato(cliente, tmp_path):
    """Il controllo sta DOPO la risoluzione dei collegamenti, non prima.

    Il nome del file non arriva dalla richiesta, ma `run.out_dir` arriva dalla
    configurazione e la cartella della corsa e' scrivibile da chiunque abbia il
    disco: un `wall_model.inp` che e' un collegamento a un altro file lo
    consegnerebbe con la benedizione della tratta. Prima della risoluzione quel
    percorso e' dentro la cartella; dopo, non lo e' piu'.
    """
    from meshrec.core import pipeline

    segreto = tmp_path / "segreto.txt"
    segreto.write_text("non deve uscire di qui", encoding="utf-8")
    corsa = _cartella_di_corsa(cliente)
    corsa.mkdir(parents=True, exist_ok=True)
    try:
        (corsa / pipeline.DECK_FILENAME).symlink_to(segreto)
    except (OSError, NotImplementedError):
        pytest.skip("questo filesystem non concede i collegamenti simbolici")

    risposta = cliente.get("/api/deck")

    assert risposta.status_code == 400
    assert "non deve uscire di qui" not in risposta.text


def test_il_deck_si_scarica_anche_mentre_una_corsa_gira(cliente):
    """Consegnare e' leggere: non prende il lucchetto di nessuno e non lo fa
    prendere. Un'esportazione che aspettasse la fine di uno step lungo
    arriverebbe minuti dopo il clic, senza dire perche'."""
    deck = _scrivi_deck(cliente)
    assert cliente.post("/api/step/1").status_code == 200

    risposta = cliente.get("/api/deck")

    assert risposta.status_code == 200
    assert risposta.content == deck.read_bytes()
    cliente.post("/api/cancel")


def test_lo_step_11_e_il_tetto_di_esegui_da_qui_in_poi(cliente):
    """Il tetto e' una scelta dell'interfaccia (server.py), non un'eredita' dal
    predefinito di RunConfig.to_step -- che ha gia' valso 13, poi 12 dalla Fase
    8 (#140), e ora 11 dal perimetro del prodotto. Il tetto qui adesso lo
    segue: 11 e' il deck, dove si chiude il perimetro del prodotto (PRODUCT.md)
    e dove finisce una corsa da riga di comando. Il prior (12) resta
    raggiungibile con `meshrec wall` e con `POST /api/step/12`, ma non parte
    da un bottone che non lo nomina."""
    risposta = cliente.post("/api/step/9/from")

    assert risposta.json()["fino_a"] == 11


def test_da_qui_in_giu_si_ferma_al_deck(cliente, monkeypatch):
    """PRODUCT.md: il prior non gira per difetto, e la colonna non lo mostra.
    Farlo partire da un bottone che non lo nomina e' uno step invisibile che
    l'utente paga."""
    avviati = []
    monkeypatch.setattr(server.Worker, "start", lambda self, *argomenti: avviati.append(argomenti))
    assert cliente.post("/api/step/3/from").json() == {"avviato": 3, "fino_a": 11}
    assert avviati[0][2] == 11
    # Il messaggio nomina le due strade che restano, perche' il rifiuto qui non
    # e' «numero fuori dominio»: lo step 12 esiste e si puo' chiedere. Il
    # messaggio del dominio 1..12 direbbe «chiesto 12, fino a 11», cioe' una
    # frase che smentisce se stessa davanti a chi l'ha appena chiesto.
    rifiuto = cliente.post("/api/step/12/from")
    assert rifiuto.status_code == 400
    assert rifiuto.json()["messaggio"] == (
        "«Esegui da qui fino al deck» si ferma all'11: per il prior usa "
        "`meshrec wall` oppure lo step 12 da solo"
    )


def test_lo_step_12_da_solo_parte(cliente, monkeypatch):
    """Il prior sta fuori dal perimetro del prodotto ma resta raggiungibile
    chiedendolo per nome: e' `POST /api/step/12`, non un bottone che non lo
    nomina."""
    avviati = []
    monkeypatch.setattr(server.Worker, "start", lambda self, *argomenti: avviati.append(argomenti))
    risposta = cliente.post("/api/step/12")
    assert risposta.status_code == 200
    assert risposta.json() == {"avviato": 12, "fino_a": 12}
    assert avviati[0][1:] == (12, 12)


def test_avviare_mentre_gira_non_deposita_una_versione(cliente, tmp_path, monkeypatch):
    """Il rifiuto sta sotto lo stesso lucchetto del deposito e PRIMA di esso:
    depositare e poi rifiutare lascerebbe nello storico un'esecuzione che non
    e' mai partita, cioe' un «annulla» che sposta artefatti a caso."""
    from meshrec.app import storico

    monkeypatch.setattr(server.Worker, "start", lambda self, *argomenti: None)
    assert cliente.post("/api/step/1").status_code == 200
    out_dir = tmp_path / "corsa"
    prima = storico.cursore(out_dir)

    monkeypatch.setattr(server.Worker, "is_running", lambda self: True)
    rifiuto = cliente.post("/api/step/2")
    assert rifiuto.status_code == 400
    assert "sta già girando" in rifiuto.json()["messaggio"]
    assert storico.cursore(out_dir) == prima


def test_lo_stream_riparte_dalla_prima_riga_quando_il_registro_si_svuota(cliente, monkeypatch):
    """`Worker.start` svuota `_righe` a ogni avvio (worker.py). Il generatore
    teneva solo il conteggio di quelle gia' mandate, e sul fotogramma in cui il
    registro si accorcia quel conteggio e' piu' alto di quante righe ci sono:
    le prime della corsa nuova cadono nel taglio e nessun fotogramma successivo
    le ripesca. Sono proprio quelle che #esito legge quando la corsa fallisce
    subito, e il pannello diceva «nessun dettaglio» su una corsa che aveva
    parlato."""
    passate = iter([["prima", "corsa", "vecchia"], ["nuova"], ["nuova", "seconda"]])
    stato = {"ultima": []}

    def righe(self):
        stato["ultima"] = next(passate, stato["ultima"])
        return stato["ultima"]

    monkeypatch.setattr(server.Worker, "righe", righe)
    testo = cliente.get("/api/events?max_eventi=3").text
    assert '"nuova"' in testo, "la prima riga della corsa nuova non deve cadere nel taglio"
    assert '"seconda"' in testo
    assert testo.count("event: riga") == 5, "nessuna riga mandata due volte"


def test_lo_stream_riparte_con_lidentita_anche_se_le_righe_non_calano(cliente, monkeypatch):
    """worker.py:97-115: `Worker.start` incrementa `avvii` subito dopo aver
    svuotato `_righe`. Due corse ravvicinate nello stesso poll possono
    lasciare la corsa nuova con lo stesso numero di righe della vecchia (o di
    piu'): la guardia sul solo conteggio (`len(righe) < inviate`) non se ne
    accorge, e la prima riga della corsa nuova si perde per sempre.
    L'identita' della corsa deve bastare da sola, a prescindere dal
    conteggio."""
    turni = [
        (0, ["vecchia"]),             # corsa A: 1 riga, gia' mandata
        (1, ["nuova-1", "nuova-2"]),  # corsa B: avvii cambiato, 2 righe (>= della vecchia)
    ]
    turno = {"i": 0}

    def avvii(self):
        # Letta prima di righe() nel generatore: deve vedere il turno
        # corrente, non quello gia' avanzato da righe().
        return turni[turno["i"]][0]

    def righe(self):
        risultato = turni[turno["i"]][1]
        turno["i"] = min(turno["i"] + 1, len(turni) - 1)
        return risultato

    monkeypatch.setattr(
        server.Worker, "avvii", property(avvii, lambda self, valore: None), raising=False
    )
    monkeypatch.setattr(server.Worker, "righe", righe)

    testo = cliente.get("/api/events?max_eventi=2").text
    assert '"nuova-1"' in testo, "la prima riga della corsa nuova non deve cadere nel taglio"
    assert '"nuova-2"' in testo




# Il banco del velo. Gemello di _BANCO_ORDINE, con una differenza sola e
# deliberata: le due risposte si rilasciano nell'ordine OPPOSTO, prima la
# vecchia. E' l'ordine in cui un velo che arbitrasse al posto delle geometrie
# farebbe vincere la piu' vecchia, e quello che _BANCO_ORDINE non esercita.
_BANCO_VELO = """import assert from 'node:assert/strict';

let generazione = 1;
let ultimaGeometria = 0;
let ultimoFantasma = 0;
const STEP_CON_MESH = new Set([9]);
const STEP_CON_GEOMETRIA = new Set([1, 2]);
// Lo step 2 ha un fantasma e viene dall'1: e' la coppia vera, non uno stub di
// comodo. Le altre due della tabella non servono a questo caso.
const FANTASMA_DI = { 2: 1 };
let fantasmaAcceso = true;
const scritture = [];
const vista = {
  svuota() {},
  mostraNuvola(vertici) { scritture.push(`nuvola:${vertici.length / 3}`); },
  mostraMesh(vertici) { scritture.push(`mesh:${vertici.length / 3}`); },
  mostraFantasma() { scritture.push('velo'); },
  togliFantasma() {},
};
// setAttribute/removeAttribute perche' le funzioni ritagliate toccano attributi
// dell'elemento: senza, la funzione vera cade su un elemento che non sa
// rispondere, e il banco misurerebbe quella caduta invece dell'arbitraggio.
const attributi = {};
const document = {
  getElementById: () => ({
    textContent: '',
    hidden: false,
    setAttribute(nome, valore) { attributi[nome] = valore; },
    removeAttribute(nome) { delete attributi[nome]; },
  }),
};
function riallineaTaglio(numero) { scritture.push(`riallinea:${numero}`); }
function serverMuto() { return undefined; }
function didascaliaDellaVista() { return { textContent: '' }; }

// Vuoto apposta: nomeDelloStep ripiega su `step N`, che a questo banco basta.
// Qui si prova l'ordine delle risposte, non come si chiamano gli step.
const ETICHETTE = {};
const ultimoStato = Array.from({ length: 13 }, (_, i) => ({
  numero: i + 1, chiave: `0${i + 1}`, artefatto: 'scritto',
}));

// Le richieste della GEOMETRIA restano sospese; quella del VELO no. Il velo
// parte da solo dentro il `then` e qui non e' cio' che si sta arbitrando: se
// restasse sospeso anche lui, il banco misurerebbe l'ordine di rilascio invece
// del contatore.
const sospese = [];
let partite = 0;
globalThis.fetch = (indirizzo) => {
  if (indirizzo.startsWith('/api/cloud/1')) {
    return Promise.resolve({
      ok: true,
      headers: { get: () => 0 },
      arrayBuffer: async () => new ArrayBuffer(12),
    });
  }
  const marcatore = ++partite;
  return new Promise((risolvi) => sospese.push(() => risolvi({
    ok: true,
    headers: { get: (nome) => (nome === 'X-Vertices' ? marcatore : 0) },
    arrayBuffer: async () => new ArrayBuffer(marcatore * 12),
  })));
};
const giro = async () => { for (let i = 0; i < 12; i += 1) await Promise.resolve(); };

__FUNZIONI__

ricaricaVista(2, generazione);   // il clic: apre la richiesta 1
await giro();
ricaricaVista(2);                // il fronte di discesa: apre la richiesta 2
await giro();
assert.equal(sospese.length, 2, 'le due richieste della geometria non sono partite');
sospese[0]();                    // la VECCHIA arriva per prima: disegna, e fa partire il suo velo
await giro();
sospese[1]();                    // la nuova arriva dopo, e deve vincere lei
await giro();

// La nuova ha disegnato: e' l'ultima nuvola scritta, e porta il marcatore 2.
const nuvole = scritture.filter((riga) => riga.startsWith('nuvola:'));
assert.equal(
  nuvole[nuvole.length - 1], 'nuvola:2',
  'a video e\\' rimasta la geometria vecchia: il velo ha arbitrato al posto delle '
  + 'geometrie. Scritture: ' + JSON.stringify(scritture),
);
"""


def test_il_velo_non_arbitra_al_posto_delle_geometrie():
    """Il velo ha un contatore suo, e questo lo esegue invece di leggerlo.

    `ultimaGeometria` decide quale di due geometrie della stessa generazione
    resta a video: vince quella partita dopo. Il velo del passaggio a monte si
    posa dentro il `then` di `mostraStep`, cioe' proprio in mezzo a due
    richieste che possono essere ancora tutt'e due in volo -- il clic e il
    fronte di discesa condividono la generazione, ed e' il caso che
    `test_fra_due_geometrie_della_stessa_generazione_vince_chi_e_partita_dopo`
    tiene sospeso.

    Quel banco pero' rilascia prima la richiesta NUOVA, e in quell'ordine un
    velo che bumpasse `ultimaGeometria` non cambierebbe l'esito: scarterebbe la
    vecchia, che era gia' da scartare. Verificato, resta verde con la
    mutazione. Qui l'ordine e' rovesciato -- arriva prima la vecchia, disegna,
    e il suo velo parte -- ed e' li' che il bump scarta la richiesta nuova e a
    video resta la geometria di prima, senza che niente lo dica.

    Mutazione che lo uccide: in `mostraFantasmaDelloStep`, rimettere
    `const emissione = apriGeometria();` al posto di `apriFantasma()`.
    """
    from meshrec.app.server import UI_DIR

    node = shutil.which("node")
    if node is None:
        pytest.skip("node non installato: il contatore del velo resta verificato a mano")
    testo = (UI_DIR / "app.js").read_text(encoding="utf-8")
    funzioni = "\n".join(
        _sorgente_di(nome, testo)
        for nome in (
            "superata",
            "apriGeometria",
            "apriFantasma",
            "nomeDelloStep",
            "dichiaraCaricamento",
            "corpoBinarioLetto",
            "ragioneDelRifiuto",
            "messaggioDownloadInterrotto",
            "segnalaArtefattoMancante",
            "mostraNuvolaDelloStep",
            "mostraStep",
            "passoDaMostrare",
            "fantasmaHaSenso",
            "comandoDelFantasma",
            "mostraFantasmaDelloStep",
            "ricaricaVista",
        )
    )
    prova = Path(__file__).parent / "_prova_velo.mjs"
    prova.write_text(_BANCO_VELO.replace("__FUNZIONI__", funzioni), encoding="utf-8")
    try:
        esito = subprocess.run([node, str(prova)], capture_output=True, text=True)
        assert esito.returncode == 0, esito.stderr
    finally:
        prova.unlink()


def test_annullare_e_rifare_una_modifica_riportano_il_file_com_era(cliente, tmp_path):
    """Il giro completo, per HTTP: modifica, Ctrl+Z, Ctrl+Maiusc+Z.

    La versione di partenza si deposita pigramente alla PRIMA modifica: senza,
    il primo «indietro» non avrebbe niente a cui tornare e la prima modifica
    sarebbe l'unica non annullabile.

    **Cosa NON prova, e dove sta invece:** che il ripristino riscriva il testo
    grezzo invece di ripassare dal modello. Qui non lo distingue nulla, ed e'
    stato misurato: sostituendo la scrittura atomica con
    `save_config(candidata, config_path)` questo controllo resta VERDE. Il
    motivo e' che le versioni depositate dall'interfaccia le ha scritte
    `save_config`, quindi riserializzarle da' gli stessi byte. La differenza
    esiste solo dove il testo depositato NON viene da li' -- la modifica fatta
    a mano, che porta i commenti dell'editor -- e la prova
    `test_l_undo_di_una_modifica_a_mano_non_riscrive_il_file_a_modo_proprio`.

    Mutazione che lo uccide: rispondere `{"annullato": True}` senza riscrivere
    `config.yaml`.
    """
    percorso = tmp_path / "config.yaml"
    prima = percorso.read_text(encoding="utf-8")

    corpo = cliente.get("/api/config").json()
    corpo["tet"]["min_ratio"] = 1.9
    assert cliente.put("/api/config", json=corpo).status_code == 200
    dopo = percorso.read_text(encoding="utf-8")
    assert dopo != prima

    indietro = cliente.post("/api/storico/indietro").json()
    assert indietro["annullato"] is True
    assert percorso.read_text(encoding="utf-8") == prima, "l'undo non ha reso il file identico"
    assert isinstance(indietro["steps"], list), "il ritorno non dice che cosa e' cambiato"

    avanti = cliente.post("/api/storico/avanti").json()
    assert avanti["annullato"] is True
    assert percorso.read_text(encoding="utf-8") == dopo, "il redo non ha reso il file identico"


def test_un_gesto_a_vuoto_lo_dice_invece_di_tacere(cliente):
    """Un silenzio identico fra riuscita e nulla-da-fare e' gia' stato prodotto
    e corretto una volta su questo progetto: era il bottone «Annulla», che a
    corsa ferma tornava `{"annullato": false}` e il browser lo scartava.

    E i due rifiuti si distinguono: `guasto` separa il caso normale di chi preme
    Ctrl+Z una volta di troppo da un deposito rotto, che chiede invece di
    mettere le mani dentro `.storico`. Non e' un codice di stato perche' la
    richiesta e' formata bene -- e' lo stato sul disco a essere rotto.

    Mutazione che lo uccide: rispondere `{"annullato": False}` senza `perche`.
    """
    vuoto = cliente.post("/api/storico/indietro").json()
    assert vuoto["annullato"] is False
    assert vuoto["guasto"] is False, "un gesto a vuoto e' stato annunciato come un guasto"
    assert vuoto["perche"], "il gesto a vuoto tace, come faceva il bottone Annulla"


def test_una_modifica_fatta_a_mano_non_si_perde_nell_annullamento(cliente, tmp_path):
    """Il progetto e' nato CLI-first e le Fasi 1 e 2 si lavorano da editor.

    Col server acceso, un parametro cambiato a mano in `config.yaml` non sta in
    nessuna versione, e un «indietro» lo sovrascriverebbe senza che ne esista
    una copia da nessuna parte: e' l'unica perdita irrecuperabile di questa
    superficie, e basta depositarlo per chiuderla.

    Depositato, e' l'ultima scrittura: «indietro» la toglie e «avanti» la
    rimette. E' cio' che chi preme Ctrl+Z si aspetta senza dover leggere niente.

    Mutazione che lo uccide: togliere la chiamata a
    `_deposita_le_modifiche_fatte_a_mano` da `/api/storico/indietro`.
    """
    percorso = tmp_path / "config.yaml"

    corpo = cliente.get("/api/config").json()
    corpo["tet"]["min_ratio"] = 1.9
    cliente.put("/api/config", json=corpo)

    # Ora l'editor, fuori dall'interfaccia.
    a_mano = percorso.read_text(encoding="utf-8").replace("min_ratio: 1.9", "min_ratio: 2.5")
    assert "2.5" in a_mano, "il testo di prova non ha sostituito niente"
    percorso.write_text(a_mano, encoding="utf-8")

    assert cliente.post("/api/storico/indietro").json()["annullato"] is True
    assert percorso.read_text(encoding="utf-8") != a_mano

    # E si rifa': la modifica fatta a mano e' una versione come le altre.
    assert cliente.post("/api/storico/avanti").json()["annullato"] is True
    assert percorso.read_text(encoding="utf-8") == a_mano, (
        "la modifica fatta dall'editor e' sparita senza che ne esista una copia"
    )


def test_una_versione_che_punta_a_un_altra_corsa_viene_respinta(cliente, tmp_path):
    """Il caso peggiore e' quello che NON solleva.

    Una versione con un altro `out_dir` e' una configurazione valida, e
    accettarla ripunterebbe l'applicazione su un'altra corsa in silenzio: il
    prossimo «esegui step» scriverebbe i suoi artefatti la' dentro, e se e' una
    corsa di riferimento e' il danno che l'intero progetto vieta -- PRODUCT.md
    dichiara `runs/muro` e `runs/lab_crop` di sola lettura.

    E il cursore torna indietro: `storico.indietro` lo ha gia' spostato quando
    il rifiuto arriva, e lasciarlo li' farebbe saltare una versione al
    tentativo successivo.

    Mutazione che lo uccide: togliere il confronto su `run.out_dir` da
    `_ripristina`.
    """
    from meshrec.app import storico

    percorso = tmp_path / "config.yaml"
    corpo = cliente.get("/api/config").json()
    corpo["tet"]["min_ratio"] = 1.9
    cliente.put("/api/config", json=corpo)
    dopo = percorso.read_text(encoding="utf-8")

    # Si avvelena la versione 1 con un out_dir diverso, come farebbe una
    # cartella .storico copiata da un'altra corsa.
    out_dir = Path(corpo["run"]["out_dir"])
    veleno = storico._percorso(out_dir, 1)
    veleno.write_text(
        veleno.read_text(encoding="utf-8").replace(
            out_dir.as_posix(), (tmp_path / "un-altra-corsa").as_posix()
        ),
        encoding="utf-8",
    )

    esito = cliente.post("/api/storico/indietro").json()
    assert esito["annullato"] is False
    assert esito["guasto"] is True
    assert "un'altra corsa" in esito["perche"]
    assert percorso.read_text(encoding="utf-8") == dopo, "il config e' stato ripuntato altrove"
    # Il cursore e' tornato dov'era: il tentativo successivo non salta nulla.
    assert storico._cursore(out_dir) == 2


def test_il_registro_dello_storico_nomina_i_campi_e_non_i_blocchi(cliente, tmp_path):
    """`registro.jsonl` non si pota mai: cio' che vi si scrive resta per sempre.

    Elencare i blocchi di primo livello a ogni scrittura sarebbe precisione
    inventata proprio nel file che dovra' rispondere «da dove viene questa
    versione». Il vocabolario e' quello che gia' registrano `POST /api/crop` e
    `POST /api/cluster`: `segment.crop_min`, non `segment`.

    Mutazione che lo uccide: in `_campi_cambiati`, smettere di ricorrere nei
    dizionari e restituire la sola chiave di primo livello.
    """
    import json as _json

    from meshrec.app import storico

    corpo = cliente.get("/api/config").json()
    corpo["tet"]["min_ratio"] = 1.9
    cliente.put("/api/config", json=corpo)

    out_dir = Path(corpo["run"]["out_dir"])
    righe = [
        _json.loads(r)
        for r in (out_dir / storico.CARTELLA / "registro.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
        if r.strip()
    ]
    assert righe[0]["endpoint"] == "avvio", "la versione di partenza non e' stata depositata"
    assert righe[-1]["endpoint"] == "PUT /api/config"
    assert righe[-1]["campi"] == ["tet.min_ratio"], righe[-1]["campi"]


def test_l_undo_di_una_modifica_a_mano_non_riscrive_il_file_a_modo_proprio(cliente, tmp_path):
    """Il testo si riscrive tale e quale, senza ripassare dal modello.

    Sulle versioni scritte dall'interfaccia la differenza non si vede -- le ha
    prodotte `save_config`, quindi riserializzarle da' gli stessi byte, e
    misurato: il controllo del giro completo resta verde con la mutazione. Si
    vede dove il testo depositato viene da FUORI: il progetto e' nato CLI-first
    e le Fasi 1 e 2 si lavorano da editor, quindi il file porta commenti e un
    ordine che nessun `model_dump` conserva.

    Un redo che rende «una configurazione equivalente» invece del file che
    l'utente aveva scritto gli cancella i commenti senza dirglielo, ed e'
    esattamente il genere di modifica invisibile contro cui esiste tutta questa
    superficie.

    Mutazione che lo uccide: in `_ripristina`, scrivere
    `save_config(candidata, config_path)` al posto della scrittura atomica del
    testo.
    """
    percorso = tmp_path / "config.yaml"

    corpo = cliente.get("/api/config").json()
    corpo["tet"]["min_ratio"] = 1.9
    cliente.put("/api/config", json=corpo)

    # L'editor: un commento che nessun model_dump sa riprodurre.
    a_mano = (
        "# la taglia la decide la geometria del provino, non il predefinito\n"
        + percorso.read_text(encoding="utf-8").replace("min_ratio: 1.9", "min_ratio: 2.5")
    )
    percorso.write_text(a_mano, encoding="utf-8")

    assert cliente.post("/api/storico/indietro").json()["annullato"] is True
    assert cliente.post("/api/storico/avanti").json()["annullato"] is True

    tornato = percorso.read_text(encoding="utf-8")
    assert tornato == a_mano, "il redo ha reso una configurazione equivalente, non il file"
    assert "# la taglia la decide" in tornato, "il commento dell'editor e' sparito in silenzio"


def test_la_modifica_fatta_a_mano_si_deposita_anche_quando_a_scrivere_e_l_interfaccia(
    cliente, tmp_path
):
    """La stessa perdita irrecuperabile, entrata dalla porta accanto.

    Il deposito della modifica fuori dall'interfaccia stava sui soli due
    endpoint dello storico. Ma `scriviParametro` rimanda l'INTERA copia che il
    browser ha in memoria, non il campo toccato: una riga cambiata dall'editor
    nel frattempo viene sovrascritta per intero dalla PUT successiva. Senza il
    deposito anche qui, quel valore non finiva in nessuna versione e non
    esisteva piu' da nessuna parte -- ne' su disco, ne' nello storico, ne'
    annullabile.

    E' il progetto nato CLI-first che rende lo scenario normale invece che di
    laboratorio: le Fasi 1 e 2 si lavorano da editor col server acceso.

    Mutazione che lo uccide: togliere la chiamata a
    `_deposita_le_modifiche_fatte_a_mano` da `scrivi_config`.
    """
    percorso = tmp_path / "config.yaml"

    corpo = cliente.get("/api/config").json()
    corpo["tet"]["min_ratio"] = 1.5
    cliente.put("/api/config", json=corpo)

    # L'editor, col server acceso: un valore che il browser non ha mai visto.
    percorso.write_text(
        percorso.read_text(encoding="utf-8").replace("min_ratio: 1.5", "min_ratio: 9.99"),
        encoding="utf-8",
    )

    # L'interfaccia scrive: manda la propria copia, che porta ancora 1.5.
    corpo["tet"]["min_ratio"] = 1.7
    assert cliente.put("/api/config", json=corpo).status_code == 200
    assert "9.99" not in percorso.read_text(encoding="utf-8"), "premessa: la PUT sovrascrive"

    # Un solo «indietro» deve riportare il 9.99, non il 1.5: la modifica a mano
    # e' l'ultima cosa che c'era prima di questa scrittura.
    assert cliente.post("/api/storico/indietro").json()["annullato"] is True
    assert "min_ratio: 9.99" in percorso.read_text(encoding="utf-8"), (
        "il valore scritto dall'editor non sta in nessuna versione: e' perso"
    )


def test_una_versione_con_due_chiavi_omonime_non_arriva_su_config_yaml(cliente, tmp_path):
    """La prova in anticipo deve usare LO STESSO lettore del controllo vero.

    `yaml.safe_load` tiene l'ultima di due chiavi omonime e non dice niente;
    `carica_yaml` -- quello che rileggera' il file -- le rifiuta. Con due
    lettori diversi la validazione qui era piu' permissiva del controllo a
    valle: la versione passava, finiva su config.yaml, e la respingeva
    `load_config` DOPO la scrittura. Da quel momento ogni tratta che chiama
    `corrente()` fallisce, compresi i due endpoint dello storico, cioe' lo
    strumento di recupero moriva insieme al resto.

    E' l'unico ingresso degenere senza altro sintomo -- gli altri almeno
    sollevano subito -- ed e' la ragione per cui `_LoaderChiaviUniche` esiste.

    Mutazione che lo uccide: rimettere `yaml.safe_load(testo)` al posto di
    `carica_yaml_da_testo(testo)` in `_ripristina`.
    """
    percorso = tmp_path / "config.yaml"

    corpo = cliente.get("/api/config").json()
    corpo["tet"]["min_ratio"] = 1.5
    cliente.put("/api/config", json=corpo)
    intatto = percorso.read_text(encoding="utf-8")

    # Un editor dentro .storico: la versione 1 acquista un secondo blocco `tet`.
    #
    # `tet` e non `run`: una chiave `run` doppia la prenderebbe comunque la
    # guardia sull'out_dir, cioe' il test resterebbe rosso sotto mutazione ma
    # per il motivo sbagliato, e non proverebbe niente sul lettore. Su `tet`
    # nessun'altra guardia interviene: con il lettore di serie vince la seconda,
    # la configurazione e' valida, l'out_dir combacia, e il testo arriva su
    # config.yaml -- dove `load_config`, che il loader stretto ce l'ha, lo
    # rifiuta da li' in avanti per sempre.
    versione = tmp_path / "corsa" / ".storico" / "0001.yaml"
    versione.write_text(
        versione.read_text(encoding="utf-8") + "\ntet:\n  min_ratio: 1.8\n",
        encoding="utf-8",
    )

    risposta = cliente.post("/api/storico/indietro").json()
    assert risposta["annullato"] is False
    assert risposta["guasto"] is True
    assert "leggibile" in risposta["perche"]
    # E soprattutto: config.yaml non e' stato toccato, quindi il server e' ancora
    # in piedi e lo storico ancora raggiungibile. Sotto mutazione e' qui che si
    # vede il danno vero: il file riscritto e ogni tratta successiva a 400.
    assert percorso.read_text(encoding="utf-8") == intatto
    assert cliente.get("/api/config").status_code == 200
    assert cliente.post("/api/storico/avanti").status_code == 200


def test_una_post_partita_da_un_altro_sito_non_riavvolge_la_configurazione(cliente):
    """CSRF sulle tratte senza corpo, che il preflight non protegge.

    Una POST senza corpo non porta `Content-Type`: e' una richiesta
    CORS-safelisted, il browser non fa il preflight, e l'`Host` che arriva e'
    `127.0.0.1`, quindi la guardia sul nome locale la lascia passare. La
    risposta resta opaca -- niente CORSMiddleware qui -- ma l'effetto
    collaterale succede lo stesso, e un `<form method=POST>` auto-inviato non
    ha bisogno nemmeno di JavaScript.

    Sono otto le tratte cosi': le due dello storico, cinque che c'erano gia' e
    quella del solutore; cinque di loro lanciano sottoprocessi.

    Mutazione che lo uccide: togliere il controllo su `Sec-Fetch-Site` dal
    middleware.
    """
    risposta = cliente.post(
        "/api/storico/indietro", headers={"Sec-Fetch-Site": "cross-site"}
    )
    assert risposta.status_code == 403
    assert risposta.json()["errore"] == "RichiestaDaUnAltroSito"


def test_l_interfaccia_e_la_riga_di_comando_passano_lo_stesso(cliente):
    """La controprova: la guardia non deve chiudere la porta a chi ha diritto.

    `same-origin` e' l'interfaccia che chiama il proprio server. `none` e' la
    navigazione diretta, cioe' l'indirizzo battuto a mano o il segnalibro con
    cui questa applicazione si apre. Assente vuol dire che a chiamare non e' un
    browser -- `curl`, la suite -- e chi non ha un browser non ha nemmeno una
    vittima da far cliccare, che e' il presupposto del CSRF.

    Senza questa controprova la guardia piu' stretta possibile (rifiuta tutto)
    passerebbe il test qui sopra.
    """
    assert cliente.get("/api/config", headers={"Sec-Fetch-Site": "same-origin"}).status_code == 200
    assert cliente.get("/api/config", headers={"Sec-Fetch-Site": "none"}).status_code == 200
    assert cliente.get("/api/config").status_code == 200


def test_una_corsa_di_riferimento_non_prende_uno_storico(cliente, tmp_path):
    """La sentinella ferma anche la superficie nuova.

    `runs/muro` e `runs/lab_crop` sono le corse di riferimento della tesi,
    dichiarate di sola lettura da PRODUCT.md. Lo storico e' una scrittura nuova
    dentro la cartella della corsa -- una `.storico/` accanto agli artefatti --
    e prima di questo controllo nessun test la sorvegliava su nessuna delle
    cinque tratte che scrivono.

    CHE COSA QUESTO CONTROLLO PROVA DAVVERO, misurato e non dedotto. La guardia
    sta in due posti: sull'endpoint e -- da adesso -- anche dentro
    `scrivi_config`, il punto condiviso. Togliendone UNA il controllo resta
    VERDE in tutti e due i versi: provato, prima levandola dall'endpoint, poi
    dal punto condiviso. E' il senso della difesa in profondita', e vuol dire
    che quello che si sorveglia qui e' «la corsa di riferimento resta intatta»,
    non «questa riga esiste».

    L'una senza l'altra non e' isolabile dall'esterno: i tre chiamanti di oggi
    la propria ce l'hanno gia', e `scrivi_config` e' una chiusura dentro
    `create_app`, quindi da qui non la si chiama. Quella condivisa esiste per il
    quarto chiamante, che ancora non c'e'; il giorno che arriva, e' lui a
    portarsi il controllo che la mette alla prova.

    Mutazione che lo uccide: togliere `non_in_sola_lettura` da ENTRAMBI --
    dall'endpoint e da `scrivi_config`. Misurata: 400 diventa 200 e la corsa di
    riferimento si prende la sua `.storico/`.
    """
    (tmp_path / server.SENTINELLA_SOLA_LETTURA).touch()

    corpo = cliente.get("/api/config").json()
    corpo["tet"]["min_ratio"] = 1.5
    assert cliente.put("/api/config", json=corpo).status_code == 400

    assert not (tmp_path / "corsa" / ".storico").exists(), (
        "una corsa di riferimento ha preso un deposito"
    )
    assert cliente.post("/api/storico/indietro").status_code == 400
    assert cliente.post("/api/storico/avanti").status_code == 400


@pytest.fixture()
def cliente_con_regioni(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    """Come `cliente`, ma con una regione dichiarata nel config sul disco."""
    cfg = PipelineConfig(
        input=InputConfig(path=tmp_path / "nuvola.ply"),
        regioni={"pilastro": {"membratura": 0}},
    )
    cfg.run.out_dir = tmp_path / "corsa"
    # pydantic ignora i campi che il modello non ha: senza questa riga il
    # banco «con regioni» sarebbe indistinguibile da quello senza, e il test
    # resterebbe verde per il motivo sbagliato.
    assert set(cfg.regioni) == {"pilastro"}
    save_config(cfg, tmp_path / "config.yaml")
    monkeypatch.setattr(server, "CACHE_DIR", tmp_path / "cache")
    return TestClient(
        create_app(
            tmp_path / "config.yaml",
            radice_corse=tmp_path / "runs",
        ),
        base_url="http://127.0.0.1",
        raise_server_exceptions=False,
    )


def test_una_regione_col_materiale_nel_corpo_della_put_e_rifiutata_dicendo_quale(cliente):
    """Ingresso degenere: `PUT /api/config` con un `regioni.X.materiale`.

    E' la via vera per cui una configurazione vecchia rientra dopo che il campo
    e' uscito: il pannello rimanda indietro cio' che ha letto. Senza il
    validatore la chiave in piu' viene ignorata e la PUT risponde 200 su una
    configurazione che dice una cosa che il programma non fa piu'.

    Mutazione che lo uccide: togliere il validatore `before` da
    `RegioneConfig`.
    """
    corpo = cliente.get("/api/config").json()
    corpo["regioni"] = {
        "pilastro": {
            "membratura": 0,
            "materiale": {
                "material": {
                    "name": "CLS", "young": 31476.0, "poisson": 0.2, "density": 2.5e-9,
                },
                "provenienza": "a_mano",
                "norma": "NTC 2018 Tab. 4.1.I",
            },
        }
    }

    risposta = cliente.put("/api/config", json=corpo)

    assert risposta.status_code == 422
    detto = risposta.json()["messaggio"]
    # Con dodici regioni dichiarate, un rifiuto che non dice quale manda a
    # cercare a mano.
    assert "pilastro" in detto, detto
    assert "materiale" in detto, detto


@pytest.mark.parametrize("banco", ["cliente", "cliente_con_regioni"])
def test_lo_schema_non_esplode_sul_blocco_regioni(banco, request):
    """`regioni` (STEP_BLOCKS[11]) e' un `dict[NomeSet, RegioneConfig]`, non un
    modello: senza la guardia su `hasattr(annidato, "model_fields")` in
    `schema()`, l'annotazione del blocco -- `dict[NomeSet, RegioneConfig]` --
    si vede chiedere `model_fields`, con l'`AttributeError` fuori vista che
    spegne il pannello dello step 11. E' il difetto di `5d4d24b`, ripetuto su
    un blocco nuovo.

    Le due varianti del banco perche' l'oracolo del brief le chiede entrambe,
    con regioni popolate e senza. Vale la pena dichiarare che oggi esercitano
    lo stesso codice: `/api/schema` descrive i **modelli**, non la
    configurazione corrente, e non legge il config del disco. Restano perche'
    il giorno in cui l'endpoint cominciasse a leggerlo -- il pannello che
    elenca le regioni dichiarate -- la variante popolata e' la sola che se ne
    accorgerebbe.

    Il blocco non compare: le sue chiavi le sceglie l'operatore, non ci sono
    campi fissi da descrivere, e una sezione che per costruzione non puo'
    contenere nulla non si mostra.
    """
    from meshrec.core import steps

    assert "regioni" in steps.STEP_BLOCKS[11], (
        "senza il blocco fra quelli dello step 11 questo test non esercita "
        "nulla: `schema()` non lo guarderebbe affatto"
    )
    cliente = request.getfixturevalue(banco)

    risposta = cliente.get("/api/schema")
    assert risposta.status_code == 200
    corpo = risposta.json()
    assert "regioni" not in corpo["11"]["blocchi"]
    assert "regioni" not in corpo["11"]["campi"]
    # Lo step 11 risponde comunque: la guardia non deve spegnere il pannello.
    assert corpo["11"]["campi"]["export"]


# --------------------------------------------------------------------------
# /api/analisi: cio' che i quattro stadi della schermata dell'analisi mostrano.
#
# Una tratta sola e non quattro: la schermata si apre tutta insieme, e ogni
# fetch in piu' e' un modo in piu' di restare vuoti in silenzio. Quello che si
# poteva gia' leggere da /api/wall, /api/metrics e /api/config passa di qui
# riletto e non ricalcolato; quello che non esisteva -- la disponibilita' vera
# dei solutori, il verdetto per stazione, le categorie d'uso, le azioni
# dichiarate -- lo produce il core, mai l'interfaccia.
# --------------------------------------------------------------------------


def _corsa_con_prior(cliente, prior: dict) -> Path:
    """Scrive `12_wall.json` nella cartella della corsa aperta."""
    from meshrec.core import pipeline

    corsa = _cartella_di_corsa(cliente)
    corsa.mkdir(parents=True, exist_ok=True)
    (corsa / pipeline.WALL_FILENAME).write_text(
        json.dumps(prior, default=float), encoding="utf-8"
    )
    return corsa


def _membratura_di_prova(**campi) -> dict:
    """Una membratura del prior con i soli campi che /api/analisi legge."""
    voce = {
        "lunghezza": 3000.0,
        "sezione": [300.0, 500.0],
        "sezioni_fette": [[300.0, 500.0], [300.0, 480.0]],
        "quote_fette": [0.0, 1500.0],
        "riempimento": {
            "stato": "pieno", "valore": 0.91, "soglia": 0.6,
            "affidabile": True, "unita": "frazione",
        },
    }
    voce.update(campi)
    return voce


def _dichiara_regione(cliente, nome: str, membratura: int, armatura: dict | None) -> None:
    """Scrive una regione con la propria sezione nella configurazione della corsa."""
    corpo = cliente.get("/api/config").json()
    corpo["regioni"] = {
        nome: {
            "membratura": membratura,
            "sezione": {
                "calcestruzzo_confinato": {
                    "material": {"name": "C25_30", "young": 31476.0,
                                 "poisson": 0.2, "density": 2.5e-9},
                    "classe": "C25/30", "norma": "NTC 2018 Tab. 4.1.I", "provenienza": "catalogo",
                },
                "calcestruzzo_copriferro": {
                    "material": {"name": "C25_30_COPRI", "young": 31476.0,
                                 "poisson": 0.2, "density": 2.5e-9},
                    "classe": "C25/30", "norma": "NTC 2018 Tab. 4.1.I", "provenienza": "catalogo",
                },
                "acciaio": {
                    "material": {"name": "B450C", "young": 210000.0,
                                 "poisson": 0.3, "density": 7.85e-9},
                    "classe": "B450C", "norma": "NTC 2018 §11.3.2", "provenienza": "catalogo",
                },
                "armatura": armatura,
            },
        }
    }
    risposta = cliente.put("/api/config", json=corpo)
    assert risposta.status_code == 200, risposta.text


_ARMATURA_DUTTILE = {
    "classe_calcestruzzo": "C25/30", "classe_acciaio": "B450C",
    "barre_tese": 4, "diametro_teso": 16,
    "barre_compresse": 2, "diametro_compresso": 12,
    "diametro_staffe": 8, "passo_staffe": 150.0, "copriferro_nominale": 30.0,
}


def _percorso_del_solutore(radice: Path, percorso: Path) -> None:
    """Scrive `solutore.percorso` nel config della corsa aperta.

    Il config si rilegge a ogni richiesta (`corrente()` chiama `load_config`),
    quindi riscriverlo qui basta a descrivere la corsa che arriva da fuori: una
    cartella di laboratorio che nomina un eseguibile qualunque.
    """
    cfg = load_config(radice / "config.yaml")
    cfg.solutore.percorso = percorso
    save_config(cfg, radice / "config.yaml")


def test_il_selettore_file_non_cade_su_un_percorso_scritto_nella_codepage(monkeypatch, cliente):
    """Il difetto che ha fermato l'utente, il 30/08/2026.

    Il figlio scriveva il percorso con `sys.stdout.write`, che su Windows usa
    la codepage locale: «Università» esce con `0xe0`. Il padre leggeva con
    `text=True` e nessuna codifica dichiarata, cioe' con quella preferita
    dalla macchina, e dove quella e' utf-8 -- come qui -- `0xe0` non e' una
    continuazione valida. L'utente vedeva `UnicodeDecodeError` al posto del
    file appena scelto.

    Il banco riproduce il figlio VECCHIO, che scrive cp1252, e prova che il
    padre nuovo non cade piu': `errors="replace"` toglie la classe. Il
    percorso esce storto -- e' inevitabile, quei byte quella lettera non la
    portano in utf-8 -- ma storto si vede e si corregge, mentre un'eccezione
    si mangia la scelta.
    """
    import subprocess as _subprocess

    percorso = "C:\\Users\\mario\\OneDrive - Università degli Studi di Perugia\\nuvola.pcd"

    def figlio_vecchio(argomenti, **chiavi):
        grezzo = percorso.encode("cp1252")
        return _subprocess.CompletedProcess(
            argomenti, 0,
            stdout=grezzo.decode(chiavi["encoding"], errors=chiavi["errors"]),
            stderr="",
        )

    monkeypatch.setattr(server.subprocess, "run", figlio_vecchio)

    risposta = cliente.post("/api/sfoglia", json={"iniziale": ""})

    assert risposta.status_code == 200
    assert risposta.json()["percorso"].endswith("nuvola.pcd")


def test_il_selettore_file_consegna_intero_un_percorso_con_accenti(monkeypatch, cliente):
    """E il figlio NUOVO lo consegna intero, accento compreso.

    Il test di sopra prova che non si cade; questo prova che si legge. Sono
    due cose diverse e servono tutte e due: senza il secondo, scrivere il
    percorso in latin-1 su tutte e due le parti passerebbe il primo e
    consegnerebbe una lettera sbagliata.
    """
    import subprocess as _subprocess

    percorso = "C:\\Users\\mario\\OneDrive - Università degli Studi di Perugia\\nuvola.pcd"

    def figlio_nuovo(argomenti, **chiavi):
        # `sys.stdout.buffer.write(scelto.encode("utf-8"))`, come lo scrive ora
        grezzo = percorso.encode("utf-8")
        return _subprocess.CompletedProcess(
            argomenti, 0,
            stdout=grezzo.decode(chiavi["encoding"], errors=chiavi["errors"]),
            stderr="",
        )

    monkeypatch.setattr(server.subprocess, "run", figlio_nuovo)

    risposta = cliente.post("/api/sfoglia", json={"iniziale": ""})

    assert risposta.status_code == 200
    assert risposta.json()["percorso"] == percorso


def test_le_due_parti_del_selettore_dichiarano_la_stessa_codifica(monkeypatch, cliente):
    """Nessuna delle due si affida alla macchina.

    I due test di sopra passano da un sottoprocesso finto, quindi non vedono
    che cosa il codice vero chiede: questo lo guarda. Il figlio scrive byte
    utf-8 espliciti, il padre li legge dichiarando utf-8, e la macchina non
    entra nella decisione.
    """
    visto: dict[str, object] = {}

    def spia(argomenti, **chiavi):
        import subprocess as _subprocess

        visto.update(chiavi)
        return _subprocess.CompletedProcess(argomenti, 0, stdout="", stderr="")

    monkeypatch.setattr(server.subprocess, "run", spia)
    cliente.post("/api/sfoglia", json={"iniziale": ""})

    assert visto["encoding"] == "utf-8"
    assert visto["errors"] == "replace"
    assert "sys.stdout.buffer.write" in server._SELETTORE
    assert 'encode("utf-8")' in server._SELETTORE


def test_un_valore_fuori_dominio_e_rifiutato_in_italiano_e_per_etichetta(cliente):
    """Trovato guardando in Chrome, non eseguendo: battuto 99 nella casella
    accanto al cursore di `poisson_depth`, sotto il campo compariva
    «surface.poisson_depth: Input should be less than or equal to 14».

    Due cose sbagliate in una riga. La chiave grezza, che PRODUCT.md vieta di
    stampare -- ed e' la stessa regola per cui ogni campo ha adesso la propria
    etichetta. E l'inglese di pydantic, in un programma che parla italiano.

    Mutazione che lo uccide: tornare a comporre il messaggio dal `loc`
    dell'errore e dal `msg` di pydantic senza tradurli.
    """
    corrente = cliente.get("/api/config").json()
    corrente["surface"]["poisson_depth"] = 99

    risposta = cliente.put("/api/config", json=corrente)

    # 422 e non 400: un corpo che non passa i modelli lo ferma FastAPI prima
    # dell'endpoint, e il gestore di RequestValidationError gli da' la forma
    # {errore, messaggio} degli altri rifiuti.
    assert risposta.status_code == 422
    detto = risposta.json()["messaggio"]
    assert "poisson_depth" not in detto, f"il rifiuto stampa la chiave grezza: {detto}"
    assert "profondità dell'ottree di Poisson" in detto, (
        f"il rifiuto non nomina il campo con la sua etichetta: {detto}"
    )
    assert "Input should be" not in detto, f"il rifiuto e' in inglese: {detto}"
    assert "14" in detto, f"il rifiuto non dice l'estremo violato: {detto}"


def test_il_nome_fuori_dai_caratteri_ammessi_e_rifiutato_in_italiano_senza_la_regex(cliente):
    """Ingresso degenere: si nomina una regione con una barra.

    Il banco era il nome del materiale, e «C25/30» era il primo nome che a chi
    sceglie una classe veniva in mente; il materiale e' uscito dalla
    configurazione l'08/09/2026, ma la stessa barra su un nome di regione
    percorre la stessa `NomeSet` e la stessa traduzione. Il rifiuto era «name:
    String should match pattern '^[A-Za-z0-9_.-]+$'»: inglese, chiave grezza, e
    una regex in faccia a chi sta nominando un pezzo di muro. La forma non era
    in `_RIFIUTI_TRADOTTI`, quindi usciva come pydantic la scrive.

    Mutazione che lo uccide: togliere la riga del pattern dalla tabella.
    """
    corrente = cliente.get("/api/config").json()
    corrente["regioni"] = {"C25/30": {"membratura": 0}}

    risposta = cliente.put("/api/config", json=corrente)

    assert risposta.status_code == 422
    detto = risposta.json()["messaggio"]
    assert "String should match" not in detto, f"il rifiuto e' in inglese: {detto}"
    assert "[A-Za-z0-9" not in detto and "pattern" not in detto, (
        f"il rifiuto stampa la regex a chi nomina una regione: {detto}"
    )
    assert "trattino basso" in detto, (
        f"il rifiuto non dice quali caratteri il nome ammette: {detto}"
    )


def test_un_rifiuto_su_un_campo_senza_etichetta_resta_la_chiave(cliente):
    """Dove il modello non dichiara `title` non si inventa una frase: la
    chiave e' l'unica cosa che si sa. E' la stessa regola del pannello.
    """
    from pydantic import BaseModel, Field, ValidationError

    from meshrec.app.server import _rifiuto_leggibile

    class Riga(BaseModel):
        anonimo: int = Field(default=0, le=3)

    with pytest.raises(ValidationError) as caduta:
        Riga(anonimo=9)
    assert "anonimo" in _rifiuto_leggibile(caduta.value)


def test_l_aiuto_non_ripete_l_etichetta(cliente):
    """L'etichetta dice che cos'è il campo, l'aiuto dice il resto: sono due
    cose diverse, e a video stanno una sotto l'altra.

    Trovato guardando in Chrome: sotto «elemento del maglio di volume» c'era
    scritto «elemento del maglio di volume. C3D10 è il tetraedro quadratico...»
    -- la stessa frase due volte, una dentro l'altra.
    """
    corpo = cliente.get("/api/schema").json()
    doppioni = set()
    for voce in corpo.values():
        for blocco, campi in voce["campi"].items():
            for nome, campo in campi.items():
                etichetta = (campo.get("etichetta") or "").strip().lower()
                aiuto = (campo.get("description") or "").strip().lower()
                if etichetta and aiuto and aiuto.startswith(etichetta[: max(len(etichetta) - 6, 8)]):
                    doppioni.add(f"{blocco}.{nome}")
    assert not doppioni, "l'aiuto ricomincia con l'etichetta: " + ", ".join(sorted(doppioni))


def test_nessun_aiuto_mostra_un_letterale_di_python(cliente):
    """`None` e `True` sono come si scrivono in python, non come si legge una
    casella vuota: nell'aiuto di `voxel_size` c'era «None = 2 x spaziatura
    media», e chi apre il programma non ha nessun modo di battere `None`.
    """
    corpo = cliente.get("/api/schema").json()
    guasti = {
        f"{blocco}.{nome}"
        for voce in corpo.values()
        for blocco, campi in voce["campi"].items()
        for nome, campo in campi.items()
        if re.search(r"\b(None|True|False)\b", campo.get("description") or "")
    }
    assert not guasti, "un letterale di python nell'aiuto: " + ", ".join(sorted(guasti))


def _corsa_con_lo_step_2_eseguito(tmp_path: Path) -> Path:
    """Una corsa con un artefatto e uno stato scritti a mano, come li lascia
    un'esecuzione riuscita dello step 2. Senza worker: qui si prova il deposito
    e lo scambio, non la pipeline."""
    from meshrec.core import steps

    out_dir = tmp_path / "corsa"
    out_dir.mkdir(exist_ok=True)
    (out_dir / "02_segmented.ply").write_bytes(b"voxel 2")
    cfg = load_config(tmp_path / "config.yaml")
    impronte = steps.step_fingerprints(cfg)
    steps.write_state(out_dir, 1, impronte[1], "riuscito", "01_cloud.ply", 1.0)
    steps.write_state(out_dir, 2, impronte[2], "riuscito", "02_segmented.ply", 1.0)
    (out_dir / "metrics.json").write_text(
        json.dumps({"01_load": {"points_kept": 10}, "02_segment": {"points_after": 5}}),
        encoding="utf-8",
    )
    return out_dir


def test_eseguire_uno_step_deposita_prima_di_avviare(cliente, tmp_path, monkeypatch):
    """Il deposito sta PRIMA di `lavoratore.start`: un'esecuzione senza deposito
    e' un'esecuzione non annullabile, ed e' proprio il caso da togliere."""
    from meshrec.app import storico

    out_dir = _corsa_con_lo_step_2_eseguito(tmp_path)
    avviati = []
    monkeypatch.setattr(server.Worker, "start", lambda self, *argomenti: avviati.append(argomenti))
    assert cliente.post("/api/step/2").status_code == 200
    assert avviati == [(tmp_path / "config.yaml", 2, 2)]
    numero = storico.cursore(out_dir)
    cartella = out_dir / storico.CARTELLA / f"{numero:04d}"
    assert (cartella / "02_segmented.ply").read_bytes() == b"voxel 2"
    assert not (out_dir / "02_segmented.ply").exists()
    dichiarato = json.loads((cartella / storico.SCAMBIO).read_text(encoding="utf-8"))
    assert dichiarato["da"] == 2 and dichiarato["a"] == 2
    assert dichiarato["file"][-1] == "steps.json", "steps.json va scambiato per ultimo"
    stato = json.loads((out_dir / "steps.json").read_text(encoding="utf-8"))
    assert "02_segment" not in stato and "01_load" in stato
    metriche = json.loads((out_dir / "metrics.json").read_text(encoding="utf-8"))
    assert "02_segment" not in metriche and "01_load" in metriche


def test_un_deposito_che_solleva_non_avvia_il_worker(cliente, tmp_path, monkeypatch):
    from meshrec.app import storico

    _corsa_con_lo_step_2_eseguito(tmp_path)
    avviati = []
    monkeypatch.setattr(server.Worker, "start", lambda self, *argomenti: avviati.append(argomenti))

    def esplode(*_argomenti, **_parole):
        raise OSError("disco pieno")

    monkeypatch.setattr(storico, "deposita", esplode)
    risposta = cliente.post("/api/step/2")
    assert risposta.status_code == 400
    assert "disco pieno" in risposta.json()["messaggio"]
    assert avviati == []


def test_annullare_un_esecuzione_rimette_artefatto_stato_e_metriche(cliente, tmp_path, monkeypatch):
    out_dir = _corsa_con_lo_step_2_eseguito(tmp_path)
    monkeypatch.setattr(server.Worker, "start", lambda self, *argomenti: None)
    assert cliente.post("/api/step/2").status_code == 200
    # L'esecuzione «finisce»: scrive l'artefatto nuovo e lo stato nuovo.
    from meshrec.core import steps

    cfg = load_config(tmp_path / "config.yaml")
    (out_dir / "02_segmented.ply").write_bytes(b"voxel 5")
    steps.write_state(
        out_dir, 2, steps.step_fingerprints(cfg)[2], "riuscito", "02_segmented.ply", 2.0
    )
    (out_dir / "metrics.json").write_text(
        json.dumps({"01_load": {"points_kept": 10}, "02_segment": {"points_after": 3}}),
        encoding="utf-8",
    )

    indietro = cliente.post("/api/storico/indietro").json()
    assert indietro["annullato"] is True
    assert indietro["tipo"] == "esecuzione"
    assert (indietro["da"], indietro["a"]) == (2, 2)
    assert (out_dir / "02_segmented.ply").read_bytes() == b"voxel 2"
    assert json.loads((out_dir / "metrics.json").read_text(encoding="utf-8"))["02_segment"] == {
        "points_after": 5
    }
    stato = next(voce for voce in indietro["steps"] if voce["numero"] == 2)
    assert stato["secondi"] == 1.0, "lo stato rimesso e' quello di prima"

    avanti = cliente.post("/api/storico/avanti").json()
    assert avanti["annullato"] is True and avanti["tipo"] == "esecuzione"
    assert (out_dir / "02_segmented.ply").read_bytes() == b"voxel 5"


def test_annullare_un_esecuzione_fallita_rimette_lo_stato_di_prima(cliente, tmp_path, monkeypatch):
    out_dir = _corsa_con_lo_step_2_eseguito(tmp_path)
    monkeypatch.setattr(server.Worker, "start", lambda self, *argomenti: None)
    assert cliente.post("/api/step/2").status_code == 200
    from meshrec.core import steps

    cfg = load_config(tmp_path / "config.yaml")
    steps.write_state(out_dir, 2, steps.step_fingerprints(cfg)[2], "fallito", None, 0.0)
    (out_dir / "metrics.partial.json").write_text("{}", encoding="utf-8")

    indietro = cliente.post("/api/storico/indietro").json()
    assert indietro["annullato"] is True
    assert (out_dir / "02_segmented.ply").read_bytes() == b"voxel 2"
    assert not (out_dir / "metrics.partial.json").exists()
    assert next(voce for voce in indietro["steps"] if voce["numero"] == 2)["stato"] == "valido"


def test_annullare_una_configurazione_dice_il_proprio_tipo(cliente):
    corpo = cliente.get("/api/config").json()
    corpo["tet"]["min_ratio"] = 1.9
    assert cliente.put("/api/config", json=corpo).status_code == 200
    indietro = cliente.post("/api/storico/indietro").json()
    assert indietro["tipo"] == "configurazione"
    assert "da" not in indietro


def test_uno_step_fuori_intervallo_e_rifiutato_prima_del_deposito(cliente, tmp_path, monkeypatch):
    """Senza guardia `steps.dimentica(range(0, 1))` fa `STEP_KEYS[-1]` e toglie
    in silenzio la voce del prior; 13 solleva `IndexError` a versione già
    depositata. Il rifiuto sta prima del deposito: nessuna versione nuova."""
    from meshrec.app import storico

    out_dir = _corsa_con_lo_step_2_eseguito(tmp_path)
    avviati = []
    monkeypatch.setattr(server.Worker, "start", lambda self, *argomenti: avviati.append(argomenti))
    for percorso in ("/api/step/0", "/api/step/13", "/api/step/13/from"):
        risposta = cliente.post(percorso)
        assert risposta.status_code == 400, percorso
        assert "fra 1 e 12" in risposta.json()["messaggio"]
    assert not storico.esiste(out_dir)
    assert avviati == []


def test_lo_storico_rifiuta_con_409_mentre_un_worker_gira(cliente, tmp_path, monkeypatch):
    """Scambiare file sotto un processo che li sta scrivendo non ha un esito
    buono. 409 e non 400: la richiesta e' formata bene, e' il momento sbagliato.
    Il rifiuto e' completo: cursore fermo e nessun file mosso."""
    from meshrec.app import storico

    out_dir = _corsa_con_lo_step_2_eseguito(tmp_path)
    storico.deposita(out_dir, "uno\n", "avvio", [])
    prima = storico.cursore(out_dir)
    monkeypatch.setattr(server.Worker, "is_running", lambda self: True)
    for verso in ("indietro", "avanti"):
        risposta = cliente.post(f"/api/storico/{verso}")
        assert risposta.status_code == 409, verso
        assert "interrompi il calcolo" in risposta.json()["messaggio"]
        assert storico.cursore(out_dir) == prima, verso
        assert (out_dir / "02_segmented.ply").read_bytes() == b"voxel 2", verso


@pytest.mark.parametrize(
    "rotte",
    [b"{tronc", b"\xff\xfe non utf-8", b'["non", "un", "oggetto"]'],
    ids=["troncato", "non-utf8", "non-oggetto"],
)
def test_metriche_illeggibili_non_fermano_l_esecuzione(cliente, tmp_path, monkeypatch, rotte):
    """`_dimentica_metriche` non riscrive cio' che non ha saputo leggere: la
    copia nella cartella e' quella rotta, e l'esecuzione parte lo stesso."""
    from meshrec.app import storico

    out_dir = _corsa_con_lo_step_2_eseguito(tmp_path)
    (out_dir / "metrics.json").write_bytes(rotte)
    avviati = []
    monkeypatch.setattr(server.Worker, "start", lambda self, *argomenti: avviati.append(argomenti))
    assert cliente.post("/api/step/2").status_code == 200
    assert avviati == [(tmp_path / "config.yaml", 2, 2)]
    assert (out_dir / "metrics.json").read_bytes() == rotte
    cartella = out_dir / storico.CARTELLA / f"{storico.cursore(out_dir):04d}"
    assert (cartella / "metrics.json").read_bytes() == rotte


def test_una_corsa_senza_metriche_ne_stato_si_deposita_lo_stesso(cliente, tmp_path, monkeypatch):
    """Prima esecuzione: metrics.json e steps.json non esistono ancora, e
    nessuno dei due va creato per poterli dimenticare."""
    out_dir = tmp_path / "corsa"
    out_dir.mkdir()
    avviati = []
    monkeypatch.setattr(server.Worker, "start", lambda self, *argomenti: avviati.append(argomenti))
    assert cliente.post("/api/step/1").status_code == 200
    assert avviati == [(tmp_path / "config.yaml", 1, 1)]
    assert not (out_dir / "metrics.json").exists()
    assert not (out_dir / "steps.json").exists()


def test_annullare_un_esecuzione_senza_cartella_dice_configurazione(cliente, tmp_path, monkeypatch):
    """`.storico/` si cancella a mano quando serve spazio: la versione resta,
    la sua cartella no, e l'annullamento vale per la sola configurazione."""
    from meshrec.app import storico

    out_dir = _corsa_con_lo_step_2_eseguito(tmp_path)
    monkeypatch.setattr(server.Worker, "start", lambda self, *argomenti: None)
    assert cliente.post("/api/step/2").status_code == 200
    shutil.rmtree(out_dir / storico.CARTELLA / f"{storico.cursore(out_dir):04d}")
    indietro = cliente.post("/api/storico/indietro").json()
    assert indietro["annullato"] is True
    assert indietro["tipo"] == "configurazione"
    assert "da" not in indietro


def test_una_versione_illeggibile_non_scambia_niente(cliente, tmp_path, monkeypatch):
    """Lo scambio parte solo dopo la scrittura di config.yaml: un rifiuto di
    `_ripristina` lascia i file dove stanno."""
    from meshrec.app import storico

    out_dir = _corsa_con_lo_step_2_eseguito(tmp_path)
    monkeypatch.setattr(server.Worker, "start", lambda self, *argomenti: None)
    assert cliente.post("/api/step/2").status_code == 200
    (out_dir / "02_segmented.ply").write_bytes(b"voxel 5")
    numero = storico.cursore(out_dir)
    (out_dir / storico.CARTELLA / f"{numero - 1:04d}.yaml").write_text(
        "input: [non una mappa", encoding="utf-8"
    )
    risposta = cliente.post("/api/storico/indietro").json()
    assert risposta["annullato"] is False and risposta["guasto"] is True
    assert (out_dir / "02_segmented.ply").read_bytes() == b"voxel 5"
    cartella = out_dir / storico.CARTELLA / f"{numero:04d}"
    assert (cartella / "02_segmented.ply").read_bytes() == b"voxel 2"


def test_a_corsa_finita_le_nuvole_sono_gia_decimate(cliente, tmp_path, monkeypatch):
    """Il primo clic su uno step-nuvola non deve pagare la decimazione a freddo.

    E' l'unica attesa dell'interfaccia che superi la soglia di un gesto.
    Misurata il 04/09/2026 su una nuvola sintetica da 1.505.012 punti, con lo
    stesso giro fatto due volte a minuti di distanza sulla stessa macchina:
    1,132 s al primo clic dopo una riesecuzione senza questo meccanismo, 0,084 s
    con. Dal secondo clic in poi le due strade coincidono (0,071 contro 0,072),
    che e' il modo in cui si vede che a cambiare e' soltanto CHI paga il freddo.

    Il difetto che questo controllo ferma non e' «lo scaldacache e' sparito» --
    quello si vedrebbe -- ma il suo gemello silenzioso: scaldare una voce che
    poi la richiesta non ritrova. La chiave della cache porta dentro budget,
    campione e seme (`viewport.decimate_file`), quindi basta che il thread e la
    rotta li leggano da due posti diversi, o che uno dei due cambi, perche' il
    lavoro venga fatto due volte -- una a vuoto -- senza che niente diventi
    rosso e senza che l'attesa torni a farsi notare in un banco.

    Percio' l'asserzione non guarda il nome del file ne' chiama una funzione
    privata: fotografa la cartella della cache dopo la corsa, chiede la nuvola,
    e pretende che non sia comparso niente di nuovo. Se la voce scaldata fosse
    quella sbagliata, la richiesta ne scriverebbe una sua e il confronto lo
    direbbe.
    """
    import numpy as np
    from meshrec.core import io, pipeline

    corsa = tmp_path / "corsa"
    punti = np.random.default_rng(0).random((60_000, 3)) * 100.0
    io.write_cloud(corsa / pipeline.ARTIFACTS[1], punti)

    # Nessun sottoprocesso: qui si prova che il server scalda cio' che poi
    # serve, non che la pipeline giri. Il lavoratore dichiara una corsa finita
    # bene, che e' l'unica condizione in cui scaldare ha senso.
    def start_finto(self, *argomenti) -> None:
        # L'artefatto lo riscrive il finto avvio, e non e' una comodita': la
        # rotta DEPOSITA prima di partire, cioe' porta via da out_dir il file
        # dello step che sta per rifare. Senza questa riga il thread non
        # troverebbe niente da decimare e il banco misurerebbe il proprio
        # allestimento invece del meccanismo.
        io.write_cloud(corsa / pipeline.ARTIFACTS[1], punti)
        # Lo stato che il lavoratore vero lascia a corsa riuscita, scritto
        # sull'istanza: `exit_code` e `annullato` nascono in `__init__`, quindi
        # posati sulla classe li coprirebbe comunque il valore dell'istanza.
        self.exit_code = 0
        self.annullato = False

    monkeypatch.setattr(server.Worker, "start", start_finto)
    monkeypatch.setattr(server.Worker, "is_running", lambda self: False)

    assert cliente.post("/api/step/1").status_code == 200

    # `.tmp` escluso, e non e' pedanteria: `scrivi_atomico` scrive su
    # `<nome>.tmp.npz` e poi rinomina (core/io.py), quindi un `glob("*.npz")`
    # cattura anche il temporaneo mentre la scrittura e' in corso. Fotografato
    # li', l'elenco porta il nome temporaneo; un istante dopo il rename lo fa
    # sparire, e il confronto in fondo trova due elenchi diversi accusando la
    # rotta di aver scritto una voce sua. E' successo davvero, sul banco di
    # macOS del 04/09/2026 e non in locale: una corsa fra il thread che scalda
    # e il banco che guarda, che sulla macchina piu' lenta si apre e su quella
    # piu' veloce no. Il difetto era del controllo, non del meccanismo.
    def voci() -> list[str]:
        return sorted(f.name for f in cache.glob("*.npz") if ".tmp." not in f.name)

    cache = tmp_path / "cache"
    for _ in range(200):
        if cache.exists() and voci():
            break
        time.sleep(0.05)
    scaldate = voci()
    assert scaldate, (
        "a corsa finita nessuna nuvola e' stata decimata in anticipo: il primo "
        "clic sullo step 1 torna a pagare la decimazione a freddo"
    )

    assert cliente.get("/api/cloud/1").status_code == 200
    assert voci() == scaldate, (
        "la richiesta ha scritto una voce di cache sua: quella scaldata a fine "
        "corsa e' stata calcolata con parametri che la rotta non chiede, quindi "
        "il lavoro e' stato fatto due volte e l'attesa e' rimasta dov'era"
    )


def test_il_blocco_analysis_nel_corpo_della_put_e_un_rifiuto_leggibile(cliente):
    """La PUT accetta un `PipelineConfig` intero: e' la via per cui un blocco
    tolto arriva al programma da un pannello vecchio o da un client scritto a
    mano. Il rifiuto deve nominare il blocco, non uscire come 500.

    Mutazione che lo uccide: togliere `analysis` da `BLOCCHI_RIMOSSI`.
    """
    corpo = cliente.get("/api/config").json()
    corpo["analysis"] = None

    risposta = cliente.put("/api/config", json=corpo)

    assert risposta.status_code == 422
    assert "analysis" in risposta.json()["messaggio"]


def test_una_corsa_col_blocco_analysis_resta_in_elenco_col_suo_errore(cliente, tmp_path):
    """Ingresso degenere: le corse gia' su disco portano `analysis:`.

    L'elenco non e' il posto dove si rifiuta: una corsa vecchia perde la
    propria riga, non l'intero elenco. `load_config` sta gia' dentro il `try`
    che riempie `voce["errore"]`, e il rifiuto nominato ci arriva come tutti
    gli altri.

    Mutazione che lo uccide: far uscire `load_config` dal `try` dell'elenco.
    """
    vecchia = tmp_path / "runs" / "vecchia"
    vecchia.mkdir(parents=True)
    (vecchia / "config.yaml").write_text(
        "input:\n  path: nuvola.ply\nanalysis: null\n", encoding="utf-8"
    )

    risposta = cliente.get("/api/corse")

    assert risposta.status_code == 200
    voce = next(v for v in risposta.json()["corse"] if v["nome"] == "vecchia")
    assert "analysis" in voce["errore"]


PNG_MINIMO_B64 = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg=="


def _corpo_immagine(**cambi):
    corpo = {"numero": 5, "nome": "Superficie", "didascalia": "vista dall'alto",
             "dati": "data:image/png;base64," + PNG_MINIMO_B64}
    corpo.update(cambi)
    return corpo


def test_l_immagine_si_salva_accanto_alla_corsa(cliente, tmp_path):
    risposta = cliente.post("/api/immagine", json=_corpo_immagine())
    assert risposta.status_code == 200, risposta.text
    percorso = Path(risposta.json()["percorso"])
    assert percorso == tmp_path / "corsa" / "immagini" / "corsa-05-superficie-vista-dall-alto.png"
    assert percorso.read_bytes().startswith(b"\x89PNG")


def test_una_didascalia_lunga_si_salva_col_nome_tagliato(cliente, tmp_path):
    # Stessa regressione di test_immagini.py, verificata sopra la rotta.
    risposta = cliente.post("/api/immagine", json=_corpo_immagine(didascalia="x" * 300))
    assert risposta.status_code == 200, risposta.text
    percorso = Path(risposta.json()["percorso"])
    assert percorso.exists()
    assert len(percorso.name) <= 124


def test_senza_corsa_legata_l_immagine_non_si_salva(tmp_path, monkeypatch):
    monkeypatch.setattr(server, "CACHE_DIR", tmp_path / "cache")
    slegato = TestClient(create_app(None, radice_corse=tmp_path / "runs"),
                         base_url="http://127.0.0.1", raise_server_exceptions=False)
    risposta = slegato.post("/api/immagine", json=_corpo_immagine())
    assert risposta.status_code == 409
    assert risposta.json()["errore"] == "NessunaCorsa"
    assert risposta.json()["messaggio"] == (
        "nessuna corsa aperta: apri o crea una corsa prima di salvare l'immagine"
    )
    assert not (tmp_path / "runs").exists()


@pytest.mark.parametrize("dati", [
    "", "data:image/jpeg;base64,AAAA", "data:image/png;base64,***",
    "data:image/png;base64," + "R0lGODlh",
])
def test_un_corpo_che_non_e_un_png_e_rifiutato_senza_scrivere(cliente, tmp_path, dati):
    risposta = cliente.post("/api/immagine", json=_corpo_immagine(dati=dati))
    assert risposta.status_code == 400
    assert risposta.json()["errore"] == "ImmagineNonValida"
    assert not (tmp_path / "corsa" / "immagini").exists()


def test_un_corpo_sopra_il_limite_e_rifiutato_con_413(cliente, tmp_path):
    from meshrec.app.immagini import LIMITE_BYTE
    grande = "data:image/png;base64," + "A" * (LIMITE_BYTE + 1)
    risposta = cliente.post("/api/immagine", json=_corpo_immagine(dati=grande))
    assert risposta.status_code == 413
    assert risposta.json()["errore"] == "ImmagineTroppoGrande"
    assert risposta.json()["messaggio"] == "il corpo della richiesta supera i 50 MB"
    assert not (tmp_path / "corsa" / "immagini").exists()


def test_un_corpo_sopra_il_limite_senza_content_length_dichiarato_e_rifiutato_con_413(
    cliente, tmp_path, monkeypatch
):
    """Il test sopra passa sempre dal controllo sul Content-Length dichiarato,
    perche' TestClient lo calcola da solo su json=. Qui il corpo va senza
    quell'header (un generatore forza l'invio chunked), cosi' a decidere e' il
    secondo controllo, su len(corpo) dopo la lettura. LIMITE_BYTE e' patchato
    a un valore piccolo per non scrivere decine di MB in un test."""
    monkeypatch.setattr(immagini, "LIMITE_BYTE", 64)

    def corpo_a_pezzi():
        yield b"x" * 100

    risposta = cliente.post(
        "/api/immagine",
        content=corpo_a_pezzi(),
        headers={"Content-Type": "application/json"},
    )
    assert risposta.status_code == 413
    assert risposta.json()["errore"] == "ImmagineTroppoGrande"
    assert not (tmp_path / "corsa" / "immagini").exists()


def test_un_corpo_senza_i_campi_attesi_e_rifiutato(cliente):
    risposta = cliente.post("/api/immagine", json={"numero": "cinque"})
    assert risposta.status_code == 400
    assert risposta.json()["errore"] == "ImmagineNonValida"
    assert risposta.json()["messaggio"] == (
        "l'immagine non si è potuta leggere: il corpo non ha i campi attesi "
        "(numero, nome, didascalia, dati)"
    )


def test_il_nome_lo_decide_il_server_e_resta_dentro_immagini(cliente, tmp_path):
    risposta = cliente.post("/api/immagine", json=_corpo_immagine(nome="../../fuori", didascalia="/x"))
    assert risposta.status_code == 200, risposta.text
    percorso = Path(risposta.json()["percorso"])
    assert percorso.parent == tmp_path / "corsa" / "immagini"
    assert percorso.name == "corsa-05-fuori-x.png"


def test_lo_stesso_nome_sovrascrive(cliente, tmp_path):
    cliente.post("/api/immagine", json=_corpo_immagine())
    risposta = cliente.post("/api/immagine", json=_corpo_immagine())
    assert risposta.status_code == 200
    assert len(list((tmp_path / "corsa" / "immagini").iterdir())) == 1


def test_una_corsa_in_sola_lettura_accetta_le_immagini(cliente, tmp_path):
    # Le corse di riferimento sono quelle di cui servono le figure in appendice.
    (tmp_path / "SOLA_LETTURA").write_text("")
    risposta = cliente.post("/api/immagine", json=_corpo_immagine())
    assert risposta.status_code == 200, risposta.text


def test_immagini_che_e_un_file_torna_un_messaggio_col_percorso(cliente, tmp_path):
    (tmp_path / "corsa").mkdir()
    (tmp_path / "corsa" / "immagini").write_text("")
    risposta = cliente.post("/api/immagine", json=_corpo_immagine())
    assert risposta.status_code == 400
    assert str(tmp_path / "corsa" / "immagini") in risposta.json()["messaggio"]


def test_api_info_risponde_sempre(cliente):
    risposta = cliente.get("/api/info")
    assert risposta.status_code == 200
    assert set(risposta.json()) == {"nome", "versione", "commit", "licenza", "doi", "doi_url", "repository"}


def test_il_favicon_e_un_file_servito_e_non_un_data_uri(cliente):
    pagina = cliente.get("/").text
    assert 'href="/ui/icona-32.png"' in pagina
    assert "data:image/png;base64" not in pagina
    assert cliente.get("/ui/icona-32.png").status_code == 200


def test_su_macos_il_selettore_non_passa_parent_altrove_si(monkeypatch, tmp_path):
    """Su macOS un `askopenfilename(parent=...)` nasce come sheet agganciato
    alla radice -- che qui e' `withdraw()`, mai mostrata, ferma nell'angolo di
    default: lo sheet esce tagliato sul bordo e gli sheet non si trascinano.
    Su Windows/Linux il parent serve solo a modalita' e posizione, resta.
    """
    import io
    import sys
    import types

    radice_finta = types.SimpleNamespace(
        withdraw=lambda: None,
        attributes=lambda *a: None,
        destroy=lambda: None,
    )
    tk_finto = types.ModuleType("tkinter")
    tk_finto.Tk = lambda: radice_finta
    filedialog_finto = types.ModuleType("tkinter.filedialog")
    catturati: dict[str, object] = {}

    def askopenfilename_finto(**kwargs):
        catturati.update(kwargs)
        return ""

    filedialog_finto.askopenfilename = askopenfilename_finto
    tk_finto.filedialog = filedialog_finto

    monkeypatch.setattr(sys, "argv", ["selettore", str(tmp_path)])
    monkeypatch.setitem(sys.modules, "tkinter", tk_finto)
    monkeypatch.setitem(sys.modules, "tkinter.filedialog", filedialog_finto)
    monkeypatch.setattr(sys, "stdout", io.TextIOWrapper(io.BytesIO()))

    monkeypatch.setattr(sys, "platform", "darwin")
    exec(server._SELETTORE, {})
    assert "parent" not in catturati

    catturati.clear()
    monkeypatch.setattr(sys, "platform", "win32")
    exec(server._SELETTORE, {})
    assert catturati["parent"] is radice_finta


def test_lo_shutdown_ferma_lo_step_in_corso(tmp_path, monkeypatch):
    """Punto 1 fix wave: chiusura dell'app (finestra, --app, Ctrl-C,
    --no-browser) non deve lasciare lo step orfano. TestClient esegue lo
    shutdown del lifespan solo se usato come context manager."""
    cfg = PipelineConfig(input=InputConfig(path=tmp_path / "nuvola.ply"))
    cfg.run.out_dir = tmp_path / "corsa"
    save_config(cfg, tmp_path / "config.yaml")
    monkeypatch.setattr(server, "CACHE_DIR", tmp_path / "cache")

    chiamate = []
    monkeypatch.setattr(server.Worker, "cancel", lambda self: chiamate.append(self) or False)

    with TestClient(
        create_app(tmp_path / "config.yaml", radice_corse=tmp_path / "runs"),
        base_url="http://127.0.0.1",
        raise_server_exceptions=False,
    ):
        pass

    assert len(chiamate) == 1


def test_cancel_senza_step_in_corso_non_solleva():
    """Ingresso degenere: nessuno step in esecuzione -> torna False, niente
    eccezione (gia' cosi', si verifica che resti tale)."""
    from meshrec.app.worker import Worker

    assert Worker().cancel() is False
