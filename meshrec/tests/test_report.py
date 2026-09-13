"""Il report si genera dal registro e non da altro."""

import html as marcatura
import inspect
import json
import re
import struct
import sys
import zlib
from datetime import date, datetime
from pathlib import Path
from typing import get_args

import pytest

from meshrec.core import pipeline, report, steps, sweep
from meshrec.core.config import InputConfig, PipelineConfig, load_config, save_config
from corse_finte import _tre_cartelle_finte


def _png_minimo() -> bytes:
    """Un PNG 1x1 vero, costruito qui: la sola firma non e' un'immagine.

    La fixture precedente scriveva gli otto byte della firma, e il report li
    incorporava: un riquadro rotto stampato in appendice. Un PNG minimo lo si
    costruisce con la libreria standard, senza dipendenze e senza blob opachi.
    """

    def pezzo(tipo: bytes, dati: bytes) -> bytes:
        lunghezza = struct.pack(">I", len(dati))
        return lunghezza + tipo + dati + struct.pack(">I", zlib.crc32(tipo + dati))

    intestazione = struct.pack(">IIBBBBB", 1, 1, 8, 0, 0, 0, 0)
    return (
        b"\x89PNG\r\n\x1a\n"
        + pezzo(b"IHDR", intestazione)
        + pezzo(b"IDAT", zlib.compress(b"\x00\x00", 0))
        + pezzo(b"IEND", b"")
    )


def _celle_bianche(testo: str) -> list[str]:
    """Le celle che stampate non mostrano niente, non solo quelle vuote.

    `"<td></td>" not in testo` e' un confronto letterale: una cella che
    contiene uno spazio lo soddisfa e sulla carta e' bianca identica. La
    guardia deve guardare come la cella si stampa, non come si scrive.
    """
    return re.findall(r"<td>\s*</td>", testo)


def _paragrafo(testo: str, ago: str) -> str:
    """Il solo paragrafo che contiene `ago`.

    Cercare un nome di step in tutto il documento non prova niente: compare
    anche nelle intestazioni delle metriche. Le asserzioni sui conteggi devono
    guardare dentro un paragrafo solo.
    """
    prima, dopo = testo.split(ago, 1)
    return prima.rsplit("<p", 1)[1] + ago + dopo.split("</p>", 1)[0]


def _glosse(paragrafo: str) -> dict[str, str]:
    """Le glosse del modulo che compaiono nel paragrafo, per stato.

    Serve a pretendere l'uguaglianza con gli stati elencati: una glossa in piu'
    spiega uno stato che li' non c'e', una in meno lascia una parentesi muta.
    """
    return {stato: glossa for stato, glossa in report.GLOSSA.items() if glossa in paragrafo}


def _visibile(testo: str) -> str:
    """Tutto quello che la sezione «Metriche per step» mostra a chi legge.

    Un paragrafo solo non basta come perimetro: la stessa frase spostata di due
    righe — nell'altro paragrafo, in un <div>, dietro un <h3>, dentro una cella
    — torna a dire il contrario e nessuna asserzione la vede. Il perimetro e'
    la sezione intera.

    Le tabelle restano dentro: toglierle lascerebbe una cella libera di
    contraddire le intestazioni sopra di se'. Gli attributi che il browser
    stampa (title, alt) valgono come testo, perche' stampati lo sono.
    """
    sezione = testo.split("<h2>Metriche per step</h2>", 1)[1].split("<h2>", 1)[0]
    mostrati = re.findall(r"\b(?:title|alt)\s*=\s*[\"']([^\"']*)[\"']", sezione)
    return re.sub(r"<[^>]*>", " ", sezione) + " " + " ".join(mostrati)


def _residuo(sezione: str, pezzi: list[str]) -> str:
    """La sezione tolto, un'occorrenza per pezzo, quello che viene da una lettura.

    Quel che resta e' prosa scritta a mano che parla degli step senza
    rispondere a nessuna lettura, ed e' la forma con cui questo difetto e'
    tornato quattro volte: sempre una frase sola, ogni volta con parole
    diverse, ogni volta in un punto diverso della sezione. Cercare le parole
    sbagliate e' una lista che non finisce mai; pretendere che non ne resti
    nessuna e' una condizione sola.

    Un'occorrenza per pezzo, non tutte: `replace` senza limite cancella anche
    la frase stampata due volte, e una frase ripetuta e' prosa che nessuna
    lettura giustifica. Le ripetizioni legittime — la glossa di uno stato che
    compare in due paragrafi — stanno nell'elenco due volte.

    Le cifre spariscono con la punteggiatura: sono conteggi, e i conteggi li
    provano gli altri test. Qui si guarda solo la prosa.
    """
    resto = sezione
    for pezzo in sorted(pezzi, key=len, reverse=True):
        resto = resto.replace(pezzo, " ", 1)
    return re.sub(r"[\s.,:\d]", "", resto)


def _prosa_della_coerenza(atteso: dict[str, str]) -> list[str]:
    """Quello che il paragrafo della coerenza ha diritto di dire, per questa corsa.

    Senza steps.json non si e' letto niente, e allora quel paragrafo dichiara
    di non poter verificare: gli stati che il documento scrive sono tutti
    «stato ignoto». Con steps.json letto dichiara invece il conteggio, nomina
    i guasti e li glossa. Sono due paragrafi diversi, e nessuno dei due puo'
    portare la prosa dell'altro.
    """
    if report.STATO_IGNOTO in atteso.values():
        return [
            "corrispondenza fra parametri e metriche non verificabile",
            f"{steps.STATE_FILENAME} assente",
            "nessuna traccia delle impronte",
        ]
    guasti = [
        chiave
        for chiave, stato in atteso.items()
        if stato not in (report.VALIDO, report.MAI_ESEGUITO)
    ]
    pezzi = ["step su", "coerenti con i parametri mostrati", "no:"]
    pezzi += [f"{chiave} ({atteso[chiave]})" for chiave in guasti]
    pezzi += [f"{stato}: {report.GLOSSA[stato]}" for stato in {atteso[c] for c in guasti}]
    if report.MAI_ESEGUITO in atteso.values():
        pezzi += ["step", "non ancora eseguiti restano fuori dal conteggio"]
    return pezzi


def _affermazioni_coerenti(
    testo: str, atteso: dict[str, str], mancanti: list[str], voci: list[str]
) -> None:
    """Nessuno step riceve, nello stesso documento, due descrizioni incompatibili.

    Non cerca una sottostringa: raccoglie dal documento reso tutto quello che
    il documento afferma di ogni step — lo stato accanto al nome, dovunque
    compaia, e la glossa che quello stato riceve — e pretende che sia una cosa
    sola, e che nella sezione intera non resti altra prosa. Gli stati non sono
    scritti qui: arrivano da run_state. `voci` sono i nomi di metrica che la
    fixture ha scritto sul disco, cioe' il contenuto delle tabelle.

    La prosa ammessa e' ricopiata a mano, qui e in _prosa_della_coerenza. E'
    l'unica duplicazione di questo file, e sta qui apposta: e' la sola prosa
    che il documento aggiunge ai dati, e leggerla dalle costanti del modulo
    renderebbe invisibile proprio la mutazione che ha riportato quattro volte
    il difetto — la frase riscritta al posto suo, che il test seguirebbe.
    Cambiare una di queste frasi vuol dire riscriverla qui, e rileggerla.

    Il perimetro non e' piu' un paragrafo ma la sezione: la frase di troppo
    non ha piu' un posto dove spostarsi restando dentro il documento.
    """
    for chiave, stato in atteso.items():
        trovati = re.findall(rf"{chiave} \(([^)]*)\)|{chiave} \[([^\]]*)\]", testo)
        assert trovati, f"{chiave} non compare da nessuna parte nel documento"
        assert all(set(coppia) <= {stato, ""} for coppia in trovati), (chiave, trovati)

    senza = _paragrafo(testo, "step senza metriche:")
    for chiave in mancanti:
        assert f"{chiave} ({atteso[chiave]})" in senza

    stati = {atteso[chiave] for chiave in mancanti}
    # ogni stato elencato e' spiegato dove e' elencato, e nessun altro lo e':
    # il residuo vede la glossa di troppo, non la glossa nel paragrafo sbagliato
    assert _glosse(senza) == {stato: report.GLOSSA[stato] for stato in stati}

    pezzi = list(voci) + _prosa_della_coerenza(atteso)
    pezzi += [f"{chiave} [{atteso[chiave]}]" for chiave in atteso if chiave not in mancanti]
    pezzi.append("step senza metriche:")
    pezzi += [f"{chiave} ({atteso[chiave]})" for chiave in mancanti]
    pezzi += [f"{stato}: {report.GLOSSA[stato]}" for stato in stati]
    assert _residuo(_visibile(testo), pezzi) == "", _residuo(_visibile(testo), pezzi)


def test_the_report_lists_every_row_and_marks_the_front(tmp_path):
    registry = tmp_path / "registro.jsonl"
    for mark, error, tets, on_front in (("aaa", 2.0, 1000, True), ("bbb", 40.0, 9000, False)):
        sweep.append_row(
            registry,
            {
                "fingerprint": mark,
                "axes": {"tet.min_ratio": 1.8},
                "outcome": "riuscito",
                "complete": True,
                "on_front": on_front,
                "thickness_error": error,
                "duration_s": 12.0,
                "metrics": {
                    "10_volume_quality": {
                        "tets": tets,
                        "radius_edge_over_reference": 0.08,
                        "min_dihedral_deg": {"median": 38.0},
                    }
                },
            },
        )

    out = report.write_report(registry, tmp_path / "report.html")
    html = out.read_text(encoding="utf-8")

    assert "aaa" in html and "bbb" in html
    # "fronte" compare anche nella prosa statica del report: contare la
    # parola non prova che la marcatura funzioni. tr.fronte e' la classe che
    # write_report assegna solo alle righe con on_front=True (report.py:85),
    # quindi contarne le occorrenze e' l'unica prova che una riga (aaa) e'
    # marcata e l'altra (bbb) no.
    assert html.count("<tr class='fronte'>") == 1
    assert "<svg" in html


def test_the_histogram_is_svg_without_any_chart_library():
    svg = report.histogram_svg([1.0, 2.0, 2.0, 3.0], title="prova", bins=3)

    assert svg.startswith("<svg")
    assert svg.count("<rect") >= 3
    assert "prova" in svg


def test_the_histogram_handles_no_values():
    svg = report.histogram_svg([], title="vuoto", bins=3)

    assert svg.startswith("<svg")
    assert "vuoto" in svg


def test_the_histogram_handles_a_single_value():
    svg = report.histogram_svg([5.0], title="singolo", bins=3)

    assert svg.startswith("<svg")
    assert "<rect" in svg


def test_the_histogram_handles_a_constant_axis():
    svg = report.histogram_svg([5.0, 5.0, 5.0], title="costante", bins=3)

    assert svg.startswith("<svg")
    assert "<rect" in svg


# --- report di una singola corsa ------------------------------------------
#
# Un generatore di documenti si sbaglia producendo qualcosa che *sembra*
# completo: un riquadro vuoto, una riga mancante che si legge come uno zero.
# Nessuno di questi test si ferma a `percorso.exists()`, che passerebbe anche
# con un file vuoto: ognuno smentisce una forma precisa di buco silenzioso.


def _corsa(tmp_path, metriche=None, configurazione=None):
    """Cartella di corsa con i soli file richiesti dal caso in prova."""
    corsa = tmp_path / "corsa"
    corsa.mkdir()
    if metriche is not None:
        (corsa / pipeline.METRICS_FILENAME).write_text(
            json.dumps(metriche), encoding="utf-8"
        )
    if configurazione is not None:
        (corsa / report.CONFIG_FILENAME).write_text(configurazione, encoding="utf-8")
    return corsa


def test_il_report_dichiara_le_viste_assenti(tmp_path):
    corsa = _corsa(tmp_path, metriche={"01_load": {"points_kept": 10}})

    percorso = report.write_run_report(corsa, viste=[])
    testo = percorso.read_text(encoding="utf-8")

    assert "nessuna vista catturata" in testo


def test_il_report_esce_anche_senza_metriche_e_lo_dichiara(tmp_path):
    """Una corsa mai eseguita non deve produrre un report che tace il fatto."""
    corsa = _corsa(tmp_path, configurazione="tet:\n  min_ratio: 1.8\n")

    testo = report.write_run_report(corsa, viste=[]).read_text(encoding="utf-8")

    assert f"{pipeline.METRICS_FILENAME} assente" in testo
    # nessuno step puo' comparire con una casella vuota, che si leggerebbe
    # come una metrica pari a zero invece che come una metrica mai misurata
    assert _celle_bianche(testo) == []


def test_il_report_esce_anche_senza_configurazione_e_lo_dichiara(tmp_path):
    corsa = _corsa(tmp_path, metriche={"01_load": {"points_kept": 10}})

    testo = report.write_run_report(corsa, viste=[]).read_text(encoding="utf-8")

    assert f"{report.CONFIG_FILENAME} assente" in testo
    assert "points_kept" in testo


def test_il_report_elenca_gli_step_senza_metriche(tmp_path):
    """Il caso normale dell'interfaccia: uno step alla volta, gli altri mai."""
    corsa = _corsa(tmp_path, metriche={"01_load": {"points_kept": 10}})

    testo = report.write_run_report(corsa, viste=[]).read_text(encoding="utf-8")

    _, dichiarazione = testo.split(report.SENZA_METRICHE, 1)
    dichiarazione = dichiarazione.split("</p>", 1)[0]
    mancanti = [chiave for chiave in steps.STEP_KEYS if chiave != "01_load"]
    assert all(chiave in dichiarazione for chiave in mancanti)
    assert "01_load" not in dichiarazione


def test_una_vista_il_cui_file_non_esiste_non_diventa_immagine_rotta(tmp_path):
    """Un <img> che non carica e' un buco silenzioso stampato su carta."""
    corsa = _corsa(tmp_path, metriche={"01_load": {"points_kept": 10}})

    testo = report.write_run_report(
        corsa, viste=[corsa / "viste" / "fronte.png"]
    ).read_text(encoding="utf-8")

    assert "<img" not in testo
    assert "fronte.png" in testo and "assente" in testo
    assert "1 attese" in testo and "0 presenti" in testo


def test_le_viste_presenti_hanno_percorsi_relativi_al_report(tmp_path):
    """Il report deve restare apribile se la cartella viene spostata."""
    corsa = _corsa(tmp_path, metriche={"01_load": {"points_kept": 10}})
    (corsa / "viste").mkdir()
    (corsa / "viste" / "fronte.png").write_bytes(_png_minimo())

    testo = report.write_run_report(
        corsa, viste=[corsa / "viste" / "fronte.png"]
    ).read_text(encoding="utf-8")

    assert 'src="viste/fronte.png"' in testo
    # non in tutto il documento: la riga di provenienza porta apposta il
    # percorso assoluto della corsa, ed e' l'unico posto dove ci va
    assert str(corsa) not in testo.split("<h2>Viste</h2>", 1)[1]
    assert "1 attese" in testo and "1 presenti" in testo


def test_una_vista_su_un_altra_unita_non_fa_fallire_il_report(tmp_path, monkeypatch):
    """Su Windows relpath solleva fra unita' diverse: il report esce lo stesso."""
    corsa = _corsa(tmp_path, metriche={"01_load": {"points_kept": 10}})
    (corsa / "viste").mkdir()
    vista = corsa / "viste" / "fronte.png"
    vista.write_bytes(_png_minimo())

    def _solleva(*_):
        raise ValueError("percorsi su unita' diverse")

    monkeypatch.setattr(report.os.path, "relpath", _solleva)
    testo = report.write_run_report(corsa, viste=[vista]).read_text(encoding="utf-8")

    assert f'src="{vista.as_posix()}"' in testo
    assert "1 presenti" in testo


def test_ogni_cifra_delle_metriche_viene_riletta_dal_disco(tmp_path):
    """Il quinto principio: derivata da una lettura, non ricordata.

    Due corse con lo stesso nome di metrica e valori diversi devono dare due
    report diversi: se il numero fosse scritto nel codice, il secondo report
    conterrebbe ancora il primo valore.
    """
    corsa = _corsa(tmp_path, metriche={"01_load": {"points_kept": 6329096}})
    primo = report.write_run_report(corsa, viste=[]).read_text(encoding="utf-8")

    (corsa / pipeline.METRICS_FILENAME).write_text(
        json.dumps({"01_load": {"points_kept": 41}}), encoding="utf-8"
    )
    secondo = report.write_run_report(corsa, viste=[]).read_text(encoding="utf-8")

    # Il perimetro e' la sezione delle metriche, non il documento intero: "41"
    # e' un ago di due caratteri, e la riga di provenienza sotto il titolone
    # porta l'ora dell'orologio della macchina. Dentro il minuto :41 il
    # documento contiene "41" comunque, e cercandolo li' dentro le due
    # asserzioni mentono in due modi opposti: la prima colora di rosso un
    # report giusto, la seconda resta verde anche se il report avesse
    # dimenticato il numero. Lette nella sola sezione, rispondono di nuovo
    # alla domanda vera, cioe' se la cifra viene dal disco.
    assert "6.329.096" in _visibile(primo) and "41" not in _visibile(primo)
    assert "41" in _visibile(secondo) and "6.329.096" not in _visibile(secondo)


def test_lo_stesso_documento_al_minuto_41(tmp_path, monkeypatch):
    """Regressione: il test qui sopra dipendeva dall'orologio, non solo dal disco.

    `_provenienza` stampa `datetime.now().strftime("%Y-%m-%d %H:%M")` nella riga
    sotto il titolone (core/report.py). Finche' l'ago "41" veniva cercato in
    tutto il documento, riga di provenienza compresa, nei sessanta secondi del
    minuto :41 la stessa identica revisione falliva su qualunque macchina e nei
    cinquantanove minuti restanti passava: il fallimento intermittente visto in
    CI, con i lavori dello stesso run rossi insieme e il run successivo verde.

    Qui l'orologio e' fissato dentro quel minuto, quindi la condizione non e'
    piu' intermittente: la provenienza contiene "41" a ogni esecuzione, e il
    contratto regge solo perche' sta fuori dal perimetro delle metriche.
    """

    class _Fermo(datetime):
        @classmethod
        def now(cls, tz=None):
            return cls(2026, 8, 31, 14, 41)

    monkeypatch.setattr(report, "datetime", _Fermo)
    corsa = _corsa(tmp_path, metriche={"01_load": {"points_kept": 6329096}})
    primo = report.write_run_report(corsa, viste=[]).read_text(encoding="utf-8")

    (corsa / pipeline.METRICS_FILENAME).write_text(
        json.dumps({"01_load": {"points_kept": 41}}), encoding="utf-8"
    )
    secondo = report.write_run_report(corsa, viste=[]).read_text(encoding="utf-8")

    assert "14:41" in primo and "14:41" in secondo
    assert "6.329.096" in _visibile(primo) and "41" not in _visibile(primo)
    assert "41" in _visibile(secondo) and "6.329.096" not in _visibile(secondo)


def test_ogni_parametro_viene_riletto_da_config_yaml(tmp_path):
    corsa = _corsa(tmp_path, configurazione="tet:\n  min_ratio: 1.8\n")
    primo = report.write_run_report(corsa, viste=[]).read_text(encoding="utf-8")

    (corsa / report.CONFIG_FILENAME).write_text(
        "tet:\n  min_ratio: 2.7\n", encoding="utf-8"
    )
    secondo = report.write_run_report(corsa, viste=[]).read_text(encoding="utf-8")

    etichetta = PipelineConfig.model_fields["tet"].annotation.model_fields["min_ratio"].title
    assert etichetta in primo
    assert "1,8" in primo and "2,7" not in primo
    assert "2,7" in secondo and "1,8" not in secondo


def test_gli_istogrammi_nascono_dalle_liste_trovate_nelle_metriche(tmp_path):
    corsa = _corsa(
        tmp_path,
        metriche={"06_repair": {"hole_areas": [42120.4, 33986.0, 31702.6, 12231.8]}},
    )

    testo = report.write_run_report(corsa, viste=[]).read_text(encoding="utf-8")

    assert "06_repair.hole_areas" in testo
    # non basta un <svg>: histogram_svg restituisce un riquadro con la sola
    # scritta "vuoto" quando non ha valori, e quel riquadro non ha barre
    assert "<rect" in testo


def test_la_firma_del_report_di_corsa_non_ha_predefiniti():
    """Regola del progetto: i predefiniti stanno in config.py, non nelle firme."""
    parametri = inspect.signature(report.write_run_report).parameters

    assert [nome for nome in parametri] == ["out_dir", "viste"]
    assert all(
        parametro.default is inspect.Parameter.empty for parametro in parametri.values()
    )


# --- coerenza fra i parametri mostrati e le metriche mostrate --------------
#
# metrics.json e' cumulativo: pipeline.run fonde le metriche di una corsa
# parziale con quelle precedenti. Una tabella di parametri affiancata a righe
# prodotte da parametri diversi afferma un legame che non esiste, e su carta
# nessuno puo' accorgersene. steps.json porta l'impronta con cui ogni step e'
# stato prodotto: e' quella la smentita.


def _corsa_con_impronte(tmp_path, impronte_scritte, chiavi=steps.STEP_KEYS, esiti=None):
    """Corsa con config.yaml valido e uno steps.json costruito a mano.

    `impronte_scritte` mappa la chiave di uno step all'impronta da salvare:
    scriverne una diversa da quella ricalcolata simula uno step prodotto con
    parametri che nel config.yaml corrente non ci sono piu'.

    `chiavi` sono le sole voci scritte, in steps.json e in metrics.json.
    Scrivendole sempre tutte e undici, il caso normale dell'interfaccia — uno
    step eseguito e gli altri mai — non si presenta in nessun test.
    `esiti` mappa la chiave all'esito salvato; per il resto vale "riuscito".
    """
    cfg = PipelineConfig(input=InputConfig(path=tmp_path / "nuvola.ply"))
    corsa = tmp_path / "corsa"
    corsa.mkdir()
    save_config(cfg, corsa / report.CONFIG_FILENAME)
    (corsa / pipeline.METRICS_FILENAME).write_text(
        json.dumps({chiave: {"misura": 1} for chiave in chiavi}), encoding="utf-8"
    )
    attese = dict(zip(steps.STEP_KEYS, steps.step_fingerprints(cfg).values()))
    (corsa / steps.STATE_FILENAME).write_text(
        json.dumps(
            {
                chiave: {
                    "impronta": impronte_scritte(chiave, attese[chiave]),
                    "esito": (esiti or {}).get(chiave, "riuscito"),
                    "artefatto": None,
                    "secondi": 1.0,
                }
                for chiave in chiavi
            }
        ),
        encoding="utf-8",
    )
    return corsa


def test_il_report_dichiara_quanti_step_sono_coerenti_con_i_parametri(tmp_path):
    corsa = _corsa_con_impronte(tmp_path, lambda _chiave, attesa: attesa)

    testo = report.write_run_report(corsa, viste=[]).read_text(encoding="utf-8")

    totale = len(steps.STEP_KEYS)
    assert f"{totale} step su {totale} {report.COERENTI}." in testo
    assert report.NON_VERIFICABILE not in testo


def test_il_report_nomina_lo_step_prodotto_con_altri_parametri(tmp_path):
    """Il conteggio da solo passerebbe anche marcando lo step sbagliato."""
    corsa = _corsa_con_impronte(
        tmp_path,
        lambda chiave, attesa: "impronta-di-un-altra-corsa"
        if chiave == "03_downsample"
        else attesa,
    )

    testo = report.write_run_report(corsa, viste=[]).read_text(encoding="utf-8")

    totale = len(steps.STEP_KEYS)
    assert f"{totale - 1} step su {totale} {report.COERENTI}, 1 no:" in testo
    assert "03_downsample (non valido)" in testo
    assert "01_load (non valido)" not in testo
    # lo stato viaggia con la riga di metrica, non solo nel conteggio in cima
    assert "<h3>03_downsample [non valido]</h3>" in testo
    assert "<h3>01_load [valido]</h3>" in testo


def test_una_configurazione_non_valida_rende_la_coerenza_non_verificabile(tmp_path):
    """yaml.safe_load mostra comunque i parametri grezzi: il report non sparisce."""
    corsa = _corsa(
        tmp_path,
        metriche={"01_load": {"points_kept": 10}},
        configurazione="tet:\n  min_ratio: 1.8\n",
    )
    (corsa / steps.STATE_FILENAME).write_text("{}", encoding="utf-8")

    testo = report.write_run_report(corsa, viste=[]).read_text(encoding="utf-8")

    etichetta = PipelineConfig.model_fields["tet"].annotation.model_fields["min_ratio"].title
    assert f"{report.NON_VERIFICABILE}: {report.CONFIG_FILENAME}" in testo
    assert etichetta in testo and "1,8" in testo
    assert report.COERENTI not in testo


def test_senza_steps_json_la_coerenza_non_e_verificabile(tmp_path):
    """Ogni corsa anteriore a steps.json cade qui: non e' un caso teorico."""
    cfg = PipelineConfig(input=InputConfig(path=tmp_path / "nuvola.ply"))
    corsa = _corsa(tmp_path, metriche={"01_load": {"points_kept": 10}})
    save_config(cfg, corsa / report.CONFIG_FILENAME)

    testo = report.write_run_report(corsa, viste=[]).read_text(encoding="utf-8")

    assert f"{report.NON_VERIFICABILE}: {steps.STATE_FILENAME}" in testo
    assert report.COERENTI not in testo


def test_senza_config_yaml_la_coerenza_non_lo_chiama_invalido(tmp_path):
    """Un file che non c'e' e un file che non si valida sono due fatti diversi.

    La sezione Parametri dice «config.yaml assente». Chiamarlo, due righe
    sotto, «non e' una configurazione valida» manda a cercare un errore di
    scrittura dentro un file che sul disco non c'e'.
    """
    corsa = _corsa(tmp_path, metriche={"01_load": {"misura": 1}})
    (corsa / steps.STATE_FILENAME).write_text("{}", encoding="utf-8")

    testo = report.write_run_report(corsa, viste=[]).read_text(encoding="utf-8")

    assert f"{report.NON_VERIFICABILE}: {report.CONFIG_FILENAME} assente" in testo
    # qualunque cosa il documento dica di config.yaml, la dice una sola
    detti = set(re.findall(rf"{re.escape(report.CONFIG_FILENAME)} ([a-z' ]+?)[:.,]", testo))
    assert detti == {"assente"}


def test_il_report_di_corsa_porta_gli_accenti_italiani_veri(tmp_path):
    """Il rovescio del controllo che stava qui, e il rovescio e' la regola.

    Questo test pretendeva `testo.isascii()`. La regola del giro 3 dice l'una
    cosa e l'altra, e la distinzione e' proprio questa: «Sorgenti in ASCII, con
    una sola eccezione dichiarata: le stringhe **mostrate all'utente** portano
    gli accenti italiani veri. I commenti, i nomi e il resto del codice restano
    ASCII». Il report e' l'unica superficie dove il difetto diventa
    **permanente**: PRODUCT.md lo manda in un'appendice cartacea, e «qualita'»
    stampato in una tesi si legge come un refuso, non come una convenzione di
    sorgente.

    Non e' un vincolo tecnico che si allenta: il documento dichiara
    `<meta charset="utf-8">` e passa da `html.escape`, che le lettere accentate
    non le tocca. Verificato qui sotto, perche' un accento scritto in un
    documento che non dichiara la propria codifica e' peggio dell'accento
    mancante -- diventa un mojibake che nessuno sa piu' da dove viene.

    Mutazione che lo uccide: rimettere `assert testo.isascii()`, che adesso e'
    falso; oppure togliere il `<meta charset>` dal generatore.
    """
    corsa = _corsa(
        tmp_path,
        metriche={"01_load": {"points_kept": 10}},
        configurazione="tet:\n  min_ratio: 1.8\n",
    )

    testo = report.write_run_report(corsa, viste=[Path("mancante.png")]).read_text(
        encoding="utf-8"
    )

    assert 'charset="utf-8"' in testo, "il documento non dichiara piu' la propria codifica"
    assert not testo.isascii(), "il report e' tornato in ASCII: le parole hanno perso l'accento"
    # E non restano parole tronche NELLA PROSA. I valori degli attributi sono
    # esclusi: `class='assente'` ha l'aspetto esatto di una parola tronca, e
    # sono undici casi nel solo generatore -- una passata meccanica li avrebbe
    # accentati, scrivendo `class='assentè'` dentro l'HTML.
    prosa = re.sub(r"<[^<>]*>", "", testo)
    tronche = {p for p in re.findall(r"\b[A-Za-z]*[aeiou]'(?![A-Za-zàèéìòù])", prosa) if p != "po'"}
    assert not tronche, f"parole tronche nel documento stampato: {sorted(tronche)}"


# --- tre categorie, non due -----------------------------------------------
#
# run_state restituisce quattro stati, non due: "mai eseguito", "fallito",
# "non valido", "valido". Contarli come "valido" contro "tutto il resto" fa
# dire al documento che le metriche di uno step mai eseguito vengono da altri
# parametri, mentre quelle metriche non esistono affatto.


def test_uno_step_mai_eseguito_non_e_anche_incoerente(tmp_path):
    """Il caso normale dell'interfaccia: uno step eseguito, gli altri mai.

    Un documento che chiama lo stesso step incoerente in un paragrafo e mai
    eseguito due paragrafi dopo si contraddice, e stampato non si corregge.
    """
    corsa = _corsa_con_impronte(
        tmp_path, lambda _chiave, attesa: attesa, chiavi=("01_load",)
    )

    testo = report.write_run_report(corsa, viste=[]).read_text(encoding="utf-8")

    coerenza = _paragrafo(testo, report.COERENTI)
    mai = len(steps.STEP_KEYS) - 1
    assert f"1 step su 1 {report.COERENTI}." in coerenza
    assert f"{mai} step {report.NON_ESEGUITI}" in coerenza
    # nessuno step mai eseguito puo' comparire fra quelli che non tornano
    assert all(chiave not in coerenza for chiave in steps.STEP_KEYS[1:])
    # e la dichiarazione che gia' esiste piu' sotto resta l'unica a nominarli
    assert "02_segment" in _paragrafo(testo, report.SENZA_METRICHE)


def test_uno_step_fallito_non_e_uno_step_prodotto_con_altri_parametri(tmp_path):
    """«fallito» e «non valido» sono due stati diversi di run_state."""
    corsa = _corsa_con_impronte(
        tmp_path,
        lambda _chiave, attesa: attesa,
        esiti={"05_reconstruct": "fallito"},
    )

    testo = report.write_run_report(corsa, viste=[]).read_text(encoding="utf-8")

    coerenza = _paragrafo(testo, report.COERENTI)
    totale = len(steps.STEP_KEYS)
    assert f"{totale - 1} step su {totale} {report.COERENTI}, 1 no:" in coerenza
    assert "05_reconstruct (fallito)" in coerenza
    assert "05_reconstruct (non valido)" not in coerenza
    assert "<h3>05_reconstruct [fallito]</h3>" in testo
    # con un solo stato guasto si spiega quello, e non anche l'altro: una
    # frase che li elenca tutti e due dice di questo step quel che vale per
    # un altro, che e' il difetto in miniatura
    assert _glosse(coerenza) == {report.FALLITO: report.GLOSSA[report.FALLITO]}


def test_una_lista_vuota_non_diventa_una_cella_bianca(tmp_path):
    """Zero fori oltre soglia e' il risultato migliore possibile, non un buco.

    Stampata, una cella vuota accanto a holes_over_threshold non si distingue
    da un dato mancante. Le due liste sempre vuote compaiono in ogni
    metrics.json dell'albero: e' il caso normale, non un caso di laboratorio.
    """
    corsa = _corsa(
        tmp_path, metriche={"06_repair": {"holes_over_threshold": [], "buchi": 0}}
    )

    testo = report.write_run_report(corsa, viste=[]).read_text(encoding="utf-8")

    assert _celle_bianche(testo) == []
    assert f"<th>holes_over_threshold</th><td>{report.LISTA_VUOTA}</td>" in testo
    # una lista vuota e uno zero numerico non sono la stessa cosa
    assert "<th>buchi</th><td>0</td>" in testo


def test_un_file_illeggibile_non_viene_dichiarato_assente(tmp_path):
    """steps.read_state documenta il processo ucciso a meta' scrittura.

    Un file troncato dichiarato assente manda il lettore a cercare una corsa
    mai fatta invece che un file da riscrivere.
    """
    corsa = _corsa(tmp_path, configurazione="a: [1, 2\n")
    (corsa / pipeline.METRICS_FILENAME).write_text("{non json", encoding="utf-8")

    testo = report.write_run_report(corsa, viste=[]).read_text(encoding="utf-8")

    assert f"{report.CONFIG_FILENAME} assente" not in testo
    assert f"{pipeline.METRICS_FILENAME} assente" not in testo
    assert f"{report.CONFIG_FILENAME} {report.ILLEGGIBILE}" in testo
    assert f"{pipeline.METRICS_FILENAME} {report.ILLEGGIBILE}" in testo


def test_un_file_di_forma_inattesa_non_viene_dichiarato_assente(tmp_path):
    """config.yaml che contiene «ciao», metrics.json che contiene una lista."""
    corsa = _corsa(tmp_path, configurazione="ciao\n")
    (corsa / pipeline.METRICS_FILENAME).write_text("[1,2,3]", encoding="utf-8")

    testo = report.write_run_report(corsa, viste=[]).read_text(encoding="utf-8")

    assert f"{report.CONFIG_FILENAME} assente" not in testo
    assert f"{pipeline.METRICS_FILENAME} assente" not in testo
    assert f"{report.CONFIG_FILENAME} {report.FORMA_INATTESA}" in testo
    assert f"{pipeline.METRICS_FILENAME} {report.FORMA_INATTESA}" in testo


def test_una_lista_troppo_corta_per_un_istogramma_viene_dichiarata(tmp_path):
    """runs/sweep/lab_crop/51de6c2c9145 ha hole_areas con tre valori soli.

    E' una distribuzione vera, scartata perche' lunga come una terna di
    coordinate: la soglia resta dov'e', ma l'esclusione va detta.
    """
    corsa = _corsa(
        tmp_path, metriche={"06_repair": {"hole_areas": [42120.4, 33986.0, 31702.6]}}
    )

    testo = report.write_run_report(corsa, viste=[]).read_text(encoding="utf-8")

    assert "<rect" not in testo
    assert report.ESCLUSE_CORTE in testo
    assert "06_repair.hole_areas" in _paragrafo(testo, report.ESCLUSE_CORTE)


def test_una_vista_che_non_e_un_png_leggibile_non_diventa_immagine_rotta(tmp_path):
    """Otto byte di firma passano exists() e in appendice sono un riquadro rotto."""
    corsa = _corsa(tmp_path, metriche={"01_load": {"points_kept": 10}})
    (corsa / "viste").mkdir()
    vista = corsa / "viste" / "fronte.png"
    vista.write_bytes(b"\x89PNG\r\n\x1a\n")

    testo = report.write_run_report(corsa, viste=[vista]).read_text(encoding="utf-8")

    assert "<img" not in testo
    assert f"vista fronte.png: {report.PNG_NON_LEGGIBILE}" in testo


def test_i_valori_logici_e_quelli_mancanti_sono_in_italiano(tmp_path):
    """None, True e False in un documento italiano sono lingua sbagliata, non dato.

    `simplify.enabled: false` sta nel config.yaml di ogni corsa dell'albero:
    il ramo falso e' quello percorso davvero, non un caso di laboratorio.
    """
    corsa = _corsa(
        tmp_path,
        configurazione="tet:\n  max_volume: null\n  nobisect: true\nsimplify:\n  enabled: false\n",
    )

    testo = report.write_run_report(corsa, viste=[]).read_text(encoding="utf-8")

    def etichetta(blocco: str, campo: str) -> str:
        campi = PipelineConfig.model_fields[blocco].annotation.model_fields
        return marcatura.escape(campi[campo].title)

    assert "None" not in testo and "True" not in testo and "False" not in testo
    assert (
        f"<th>{etichetta('tet', 'max_volume')}</th><td>{report.NON_IMPOSTATO}</td>" in testo
    )
    assert f"<th>{etichetta('tet', 'nobisect')}</th><td>si</td>" in testo
    assert f"<th>{etichetta('simplify', 'enabled')}</th><td>no</td>" in testo


def test_un_numero_grande_non_passa_alla_notazione_esponenziale(tmp_path):
    """In una tabella stampata 1.68846e+08 si legge peggio dell'intero."""
    corsa = _corsa(
        tmp_path, metriche={"10_volume_quality": {"volume_mm3": 168845511.10290658}}
    )

    testo = report.write_run_report(corsa, viste=[]).read_text(encoding="utf-8")

    assert "e+08" not in testo
    assert "168.846.000" in testo


# --- eseguito e misurato sono due domande diverse --------------------------
#
# pipeline.run scrive lo stato "fallito" in steps.json e nel finally salva solo
# metrics.partial.json: uno step fallito e' partito davvero e non lascia una
# riga in metrics.json. Dedurre da quell'assenza che lo step non e' stato
# eseguito smentisce il paragrafo di coerenza, che lo conta fra gli eseguiti.


def test_nessuno_step_riceve_due_descrizioni_incompatibili(tmp_path):
    """Tutti e quattro gli stati di run_state nello stesso documento.

    E' la terza volta che questa contraddizione torna cambiando stato: «mai
    eseguito», poi «fallito», poi «stato ignoto». Ogni volta il test guardava
    la forma della correzione — la parentesi giusta — e lasciava libera la
    frase che le accompagna, che e' l'altra meta' del difetto. Qui la verifica
    e' la proprieta': vedi _affermazioni_coerenti.
    """
    corsa = _corsa_con_impronte(
        tmp_path,
        lambda chiave, attesa: "impronta-di-un-altra-corsa"
        if chiave == "03_downsample"
        else attesa,
        chiavi=("01_load", "02_segment", "03_downsample"),
        esiti={"02_segment": "fallito"},
    )
    # la tratta di produzione: solo lo step arrivato in fondo lascia metriche
    (corsa / pipeline.METRICS_FILENAME).write_text(
        json.dumps({"01_load": {"misura": 1}}), encoding="utf-8"
    )

    testo = report.write_run_report(corsa, viste=[]).read_text(encoding="utf-8")

    letto = {
        str(voce["chiave"]): str(voce["stato"])
        for voce in steps.run_state(corsa, load_config(corsa / report.CONFIG_FILENAME))
    }
    assert set(letto.values()) == {"valido", "fallito", "non valido", "mai eseguito"}
    # ogni stato che run_state sa produrre ha la sua glossa, e nessuno stato
    # spiegato manca dal documento perche' il modulo non lo conosce
    assert set(report.GLOSSA) == set(letto.values()) | {report.STATO_IGNOTO}
    # lo stato scritto quando non c'e' niente da leggere non e' nessuno dei
    # quattro: dirne uno sarebbe riferire una lettura mai avvenuta
    assert report.STATO_IGNOTO not in letto.values()

    _affermazioni_coerenti(
        testo, letto, [chiave for chiave in letto if chiave != "01_load"], ["misura"]
    )

    # anche il paragrafo di coerenza spiega gli stati che nomina, e non altri
    coerenza = _paragrafo(testo, report.COERENTI)
    guasti = {
        stato for stato in letto.values() if stato not in (report.VALIDO, report.MAI_ESEGUITO)
    }
    assert _glosse(coerenza) == {stato: report.GLOSSA[stato] for stato in guasti}


def test_senza_steps_json_nessuna_frase_riferisce_una_lettura_che_non_c_e(tmp_path):
    """Le corse di riferimento della tesi sono cosi': runs/muro e runs/lab_crop.

    Il documento dichiarava steps.json assente e due paragrafi sotto scriveva
    «fra parentesi lo stato letto da steps.json». E' la stessa contraddizione
    sul quinto caso, che non e' uno stato ma l'assenza del file, e basta una
    chiave in meno in metrics.json — cioe' una corsa parziale, il caso normale
    dell'interfaccia — perche' esca.
    """
    cfg = PipelineConfig(input=InputConfig(path=tmp_path / "nuvola.ply"))
    corsa = _corsa(tmp_path, metriche={"01_load": {"misura": 1}})
    save_config(cfg, corsa / report.CONFIG_FILENAME)

    testo = report.write_run_report(corsa, viste=[]).read_text(encoding="utf-8")

    assert f"{report.NON_VERIFICABILE}: {steps.STATE_FILENAME} assente" in testo
    _affermazioni_coerenti(
        testo,
        {chiave: report.STATO_IGNOTO for chiave in steps.STEP_KEYS},
        list(steps.STEP_KEYS[1:]),
        ["misura"],
    )


def test_ogni_stato_si_spiega_da_solo():
    """Una glossa che nomina uno stato e' la vecchia frase fissa travestita.

    La frase che elencava gli stati possibili poteva dire, di uno step
    fallito, quello che vale per uno mai eseguito: erano nella stessa riga.
    Se nessuna glossa nomina uno stato — lo scrive davanti chi la stampa, e lo
    prende da run_state — quella confusione non e' piu' esprimibile.
    """
    assert len(set(report.GLOSSA.values())) == len(report.GLOSSA)
    for stato, glossa in report.GLOSSA.items():
        assert all(altro not in glossa for altro in report.GLOSSA), (stato, glossa)


def test_ogni_dichiarazione_ha_una_frase_sua():
    """Due dati diversi dichiarati con la stessa frase si confondono in silenzio.

    Le asserzioni degli altri test puntano alla costante del modulo — la
    regola che impedisce alla copia scritta nel test di divergere — e proprio
    per questo non possono accorgersi di due costanti diventate una stringa
    sola: una mappa vuota dichiarata «lista vuota» le soddisfa tutte.
    """
    dichiarazioni = [
        report.LISTA_VUOTA,
        report.MAPPA_VUOTA,
        report.VUOTO,
        report.SOLI_SPAZI,
        report.NON_IMPOSTATO,
        report.NON_UN_NUMERO,
        report.INFINITO,
        report.SENZA_NOME,
    ]

    assert len(set(dichiarazioni)) == len(dichiarazioni)


def test_una_corsa_senza_step_eseguiti_non_stampa_zero_su_zero(tmp_path):
    """Ogni corsa appena creata dall'interfaccia passa di qui: steps.json vuoto.

    Il caso lo verifica a mano il revisore a ogni giro perche' nessun test lo
    guarda: «0 su 0» e' un rapporto che non si puo' leggere, e «restano fuori
    dal conteggio» nomina un conteggio che non c'e'.
    """
    cfg = PipelineConfig(input=InputConfig(path=tmp_path / "nuvola.ply"))
    corsa = _corsa(tmp_path, metriche={})
    save_config(cfg, corsa / report.CONFIG_FILENAME)
    (corsa / steps.STATE_FILENAME).write_text("{}", encoding="utf-8")

    testo = report.write_run_report(corsa, viste=[]).read_text(encoding="utf-8")

    assert report.NESSUNO_ESEGUITO in testo
    assert f"0 step su 0 {report.COERENTI}" not in testo
    assert report.NON_ESEGUITI not in testo


def test_le_viste_dichiarate_presenti_sono_quelle_che_diventano_immagini(tmp_path):
    """Il conteggio e l'incorporazione devono leggere lo stesso insieme.

    Contate con exists() e incorporate con _e_png, due viste rotte danno «2
    presenti» e zero figure, su fondo bianco perche' nessuna risulta assente.
    Chi conta le figure in appendice non ritrova il numero dichiarato.
    """
    corsa = _corsa(tmp_path, metriche={"01_load": {"points_kept": 10}})
    (corsa / "viste").mkdir()
    buona = corsa / "viste" / "fronte.png"
    buona.write_bytes(_png_minimo())
    # due immagini buone, non una: con una sola, il numero delle immagini
    # scritto nel codice come costante 1 soddisfa l'asserzione qui sotto
    seconda = corsa / "viste" / "lato.png"
    seconda.write_bytes(_png_minimo())
    rotta = corsa / "viste" / "retro.png"
    rotta.write_bytes(b"\x89PNG\r\n\x1a\n")
    mancante = corsa / "viste" / "alto.png"

    testo = report.write_run_report(
        corsa, viste=[buona, seconda, rotta, mancante]
    ).read_text(encoding="utf-8")

    conteggio = _paragrafo(testo, " attese,")
    assert "4 attese, 3 presenti, 1 assenti" in conteggio
    assert f"1 {report.NON_INCORPORABILI}" in conteggio
    # il numero dichiarato e' quello contato nel documento, non uno detto a parte
    assert testo.count("<img") == 2
    assert f"{report.IMMAGINI_NEL_DOCUMENTO} {testo.count('<img')}" in conteggio
    assert "class='assente'" in conteggio


def test_viste_tutte_presenti_e_una_non_incorporabile_non_sono_tutto_a_posto(tmp_path):
    """Zero assenti e una rotta: il caso che il fondo colorato deve dichiarare.

    Con una vista assente il fondo scatta comunque, e la promessa — sul fondo
    bianco non si legge piu' «tutto a posto» — resta non provata proprio nel
    caso che l'ha fatta nascere.
    """
    corsa = _corsa(tmp_path, metriche={"01_load": {"points_kept": 10}})
    (corsa / "viste").mkdir()
    buona = corsa / "viste" / "fronte.png"
    buona.write_bytes(_png_minimo())
    rotta = corsa / "viste" / "retro.png"
    rotta.write_bytes(b"\x89PNG\r\n\x1a\n")

    testo = report.write_run_report(corsa, viste=[buona, rotta]).read_text(encoding="utf-8")

    conteggio = _paragrafo(testo, " attese,")
    assert "2 attese, 2 presenti, 0 assenti" in conteggio
    assert f"1 {report.NON_INCORPORABILI}" in conteggio
    assert f"{report.IMMAGINI_NEL_DOCUMENTO} {testo.count('<img')}" in conteggio
    assert "class='assente'" in conteggio


def test_una_mappa_vuota_annidata_non_fa_sparire_la_riga(tmp_path):
    """Una riga che sparisce e' la cella vuota senza nemmeno il buco visibile."""
    corsa = _corsa(
        tmp_path,
        metriche={
            "01_load": {"dettagli": {}, "annidato": {"dentro": {}}, "punti": 10},
            "02_segment": {},
            # uno step il cui valore non e' una mappa non porta nomi di voce:
            # senza dichiararlo, l'intestazione esce vuota come una cella bianca
            "03_downsample": 5,
        },
    )

    testo = report.write_run_report(corsa, viste=[]).read_text(encoding="utf-8")

    assert f"<th>dettagli</th><td>{report.MAPPA_VUOTA}</td>" in testo
    assert f"<th>annidato.dentro</th><td>{report.MAPPA_VUOTA}</td>" in testo
    assert "<th>punti</th><td>10</td>" in testo
    assert f"<th>{report.SENZA_NOME}</th><td>5</td>" in testo
    # uno step le cui metriche sono una mappa vuota resta dichiarato com'era:
    # una riga senza nome sarebbe il buco appena tolto, rimesso altrove
    assert "<p>nessuna voce.</p>" in testo
    assert "<th></th>" not in testo


def test_una_cella_di_soli_spazi_non_e_una_cella_bianca(tmp_path):
    """Stampato, <td>   </td> e' bianco esattamente come <td></td>."""
    corsa = _corsa(tmp_path, metriche={"01_load": {"spazi": "   ", "vuota": ""}})

    testo = report.write_run_report(corsa, viste=[]).read_text(encoding="utf-8")

    assert _celle_bianche(testo) == []
    assert f"<th>spazi</th><td>{report.SOLI_SPAZI}</td>" in testo
    assert f"<th>vuota</th><td>{report.VUOTO}</td>" in testo


def test_la_riga_delle_liste_escluse_non_nomina_quelle_che_hanno_l_istogramma(tmp_path):
    """La corsa vera ha hole_areas con sei valori ed extent con tre.

    Una fixture con la sola lista corta non distingue «le corte» da «tutte»:
    la riga puo' dichiarare troppo corta, sotto il suo stesso istogramma, una
    lista che l'istogramma ce l'ha.
    """
    corsa = _corsa(
        tmp_path,
        metriche={
            "06_repair": {
                "hole_areas": [42120.5, 33986.0, 31702.6, 12231.8, 8784.52, 2659.27],
                "extent": [1.0, 2.0, 3.0],
            }
        },
    )

    testo = report.write_run_report(corsa, viste=[]).read_text(encoding="utf-8")

    escluse = _paragrafo(testo, report.ESCLUSE_CORTE)
    assert "<rect" in testo
    assert "06_repair.extent" in escluse
    assert "hole_areas" not in escluse


def test_i_valori_non_finiti_escono_in_italiano(tmp_path):
    """json.dump scrive NaN e Infinity, e json.load li rilegge come float.

    `nan` e `inf` non sono numeri da formattare ma esiti da dichiarare, e
    scritti cosi' restano due parole inglesi in un documento italiano.
    """
    corsa = _corsa(
        tmp_path,
        metriche={
            "10_volume_quality": {
                "a": float("nan"),
                "b": float("inf"),
                "c": float("-inf"),
            }
        },
    )

    testo = report.write_run_report(corsa, viste=[]).read_text(encoding="utf-8")

    assert f"<th>a</th><td>{report.NON_UN_NUMERO}</td>" in testo
    assert f"<th>b</th><td>{report.INFINITO}</td>" in testo
    assert f"<th>c</th><td>-{report.INFINITO}</td>" in testo
    assert "<td>nan</td>" not in testo and "<td>inf</td>" not in testo


def test_il_confronto_di_tre_modelli_dice_quali_grandezze_lo_sono(tmp_path):
    """Quasi nessuna metrica e' confrontabile fra i tre modelli senza mentire.
    La tabella deve dire quale lo e', invece di allineare colonne che non si
    parlano.

    Le quattro asserzioni sotto rileggono la costante `report.CONFRONTABILI`
    che `confronta` copia cosi' com'e': sorvegliano la costante, non un
    calcolo, e nessuna mutazione della logica di `confronta` le farebbe
    fallire.
    """
    cartelle = _tre_cartelle_finte(tmp_path)

    confronto = report.confronta(cartelle)

    assert set(confronto["modelli"]) == {"as-built", "estruso", "primitive"}
    assert confronto["confrontabili"]["volume"] is True
    assert confronto["confrontabili"]["scostamento_nuvola"] is True
    assert confronto["confrontabili"]["qualita_elementi"] is False
    assert confronto["confrontabili"]["rigidezza"] is False


def test_la_qualita_degli_elementi_sta_in_due_colonne_e_mai_in_una_differenza(tmp_path):
    """radius_edge_ratio per i tetraedri, Jacobiano scalato per gli esaedri: due
    colonne separate, mai una differenza fra le due. (Non min_ratio: nel
    progetto quel nome e' il vincolo chiesto a TetGen, cfg.tet.min_ratio, non
    la distribuzione misurata da quality.volume_metrics.)

    Mutazione che deve morire: in `confronta`, rinominare la chiave del ramo
    esaedri da `scaled_jacobian` a `differenza` -- verificata: muore
    sull'asserzione `"scaled_jacobian" in qualita["estruso"]`, prima ancora
    di arrivare al blocco che cerca la parola "differenza" fra le chiavi.
    """
    cartelle = _tre_cartelle_finte(tmp_path)

    confronto = report.confronta(cartelle)

    qualita = confronto["qualita"]
    assert "radius_edge_ratio" in qualita["as-built"]
    assert "scaled_jacobian" in qualita["estruso"]
    assert "radius_edge_ratio" not in qualita["estruso"]
    for colonna in qualita.values():
        assert not (set(colonna) & {"differenza", "delta", "scarto"}), (
            "il rapporto raggio-spigolo e il Jacobiano scalato non si sottraggono"
        )
    assert set(qualita["estruso"]) & set(qualita["as-built"]) == set()


def test_con_due_modelli_su_tre_il_confronto_dice_quale_manca(tmp_path):
    """Nessuna colonna con un trattino che somigli a un valore, nessuna
    differenza calcolata contro un modello assente."""
    cartelle = _tre_cartelle_finte(tmp_path)[:2]

    confronto = report.confronta(cartelle)

    assert confronto["mancanti"] == ["primitive"]
    assert "primitive" not in confronto["volume"]
    testo = report.write_comparison_report(cartelle, tmp_path / "confronto.html").read_text(
        encoding="utf-8"
    )
    assert "primitive" in testo
    assert "non generato" in testo


def test_con_un_modello_solo_il_confronto_diventa_una_scheda_e_lo_dichiara(tmp_path):
    cartelle = _tre_cartelle_finte(tmp_path)[:1]

    confronto = report.confronta(cartelle)

    assert confronto["scheda_singola"] is True
    testo = report.write_comparison_report(cartelle, tmp_path / "solo.html").read_text(
        encoding="utf-8"
    )
    assert "scheda singola" in testo


def test_il_report_dichiara_le_tre_cose_che_non_derivano_dalla_geometria(tmp_path):
    """Senza queste righe una differenza nata dal *TIE verrebbe letta come
    effetto della forma, la base sembrerebbe una faccia del pezzo e il modello
    passerebbe per un telaio in cemento armato completo."""
    cartelle = _tre_cartelle_finte(tmp_path)

    testo = report.write_comparison_report(cartelle, tmp_path / "confronto.html").read_text(
        encoding="utf-8"
    )

    assert "as-built monolitico" in testo
    assert "vincolati alle giunzioni" in testo
    assert "armatura" in testo
    assert "dove abbiamo tagliato" in testo


def test_lo_scostamento_dell_as_built_legge_mesh_to_cloud_non_cloud_to_mesh(tmp_path):
    """quality.vertex_deviation, che pipeline.genera_modello usa per lo
    scostamento_nuvola dei modelli parametrici (pipeline.py:202,211-216),
    riproduce esattamente il verso mesh_to_cloud di geometric_error, non
    cloud_to_mesh -- lo dice quality.py:458-464 ("la misura che questa
    funzione non replica e' cloud_to_mesh"). La chiave e' anche maiuscola,
    RMS, non rms (quality.py:428). Leggere il verso o la chiave sbagliata
    metterebbe in colonna due misure diverse sotto lo stesso nome, l'errore
    esatto che questo task esiste per evitare -- e la fixture li tiene
    apposta a valori diversi (4.9 contro 3.1) perche' un errore cosi' non
    passi inosservato.

    Mutazione che deve morire: in `confronta`, tornare a
    `.get("cloud_to_mesh", {}).get("rms")` per il ramo as-built -- questa
    asserzione leggerebbe 4.9 (o None, con la chiave minuscola) invece di 3.1.
    """
    cartelle = _tre_cartelle_finte(tmp_path)

    confronto = report.confronta(cartelle)

    assert confronto["scostamento_nuvola"]["as-built"] == 3.1


def test_un_modello_json_piu_vecchio_senza_scostamento_nuvola_non_fa_crashare_il_report(tmp_path):
    """D1: una chiave presente ma valorizzata None passa la guardia
    `nome in confronto[grandezza]` -- `_numero` comincia con `math.isnan(valore)`
    e su None solleva `TypeError: must be real number, not NoneType`. Un
    modello.json scritto da una versione precedente del Task 10, prima che
    scostamento_nuvola esistesse, e' esattamente questo caso.

    Mutazione che deve morire: in `write_comparison_report`, tornare a
    `_numero(confronto[grandezza][nome])` al posto di
    `_testo(confronto[grandezza][nome])` -- questa chiamata rilancerebbe il
    TypeError invece di restituire la pagina.
    """
    import json

    from meshrec.core import pipeline

    cartelle = _tre_cartelle_finte(tmp_path)
    percorso_modello = cartelle[1] / pipeline.MODEL_FILENAME
    dati = json.loads(percorso_modello.read_text(encoding="utf-8"))
    del dati["scostamento_nuvola"]
    percorso_modello.write_text(json.dumps(dati), encoding="utf-8")

    confronto = report.confronta(cartelle)
    assert confronto["scostamento_nuvola"]["estruso"] is None

    testo = report.write_comparison_report(cartelle, tmp_path / "confronto.html").read_text(
        encoding="utf-8"
    )
    assert report.NON_IMPOSTATO in testo


def test_i_vincoli_alle_giunzioni_sono_quattro_numeri_distinti_e_non_applicabili_per_l_as_built(
    tmp_path,
):
    """Task 8: un modello parametrico con parte dei giunti non vincolati e'
    piu' cedevole del vero, ed e' un limite noto della mesh non conforme fra
    blocchi. Il confronto deve portarlo o attribuira' alla geometria una
    differenza che viene dal vincolo. as-built e' monolitico: nessuna delle
    quattro righe gli si applica, e "non applicabile" non e' zero ne' "non
    generato".

    Mutazione che deve morire: in `confronta`, sommare `giunzioni` e `ties`
    in una sola chiave invece di tenerli distinti -- verificata: muore con
    `KeyError: 'giunzioni'` sulla seconda asserzione.
    """
    cartelle = _tre_cartelle_finte(tmp_path)

    confronto = report.confronta(cartelle)
    vincoli = confronto["vincoli_giunzioni"]

    assert vincoli["as-built"] == "non applicabile"
    assert vincoli["estruso"]["giunzioni"] == 3
    assert vincoli["estruso"]["ties"] == 2
    assert vincoli["estruso"]["nodi_dipendenti_legati"] == 18
    assert vincoli["estruso"]["nodi_dipendenti_totali"] == 24


def test_la_nota_delle_giunzioni_viene_letta_da_modello_json_non_riscritta(tmp_path):
    """D6: il testo dell'avvertenza lo scrive il Task 10 in modello.json
    (nota_giunzioni), il confronto lo legge e basta -- riscriverlo qui
    duplicherebbe una fonte che puo' divergere in silenzio.

    Mutazione che deve morire: in `confronta`, sostituire la lettura di
    `nota_giunzioni` con una stringa scritta in report.py -- questa
    asserzione, che cerca un testo presente solo nella fixture di questo
    test e in nessun altro posto del codice, non lo troverebbe piu'.
    """
    import json

    from meshrec.core import pipeline

    cartelle = _tre_cartelle_finte(tmp_path)
    percorso_modello = cartelle[1] / pipeline.MODEL_FILENAME
    dati = json.loads(percorso_modello.read_text(encoding="utf-8"))
    dati["nota_giunzioni"] = "MARCATORE UNICO DEL TEST -- non deriva dalla geometria"
    percorso_modello.write_text(json.dumps(dati), encoding="utf-8")

    confronto = report.confronta(cartelle)

    assert confronto["note_non_geometriche"][0] == (
        "MARCATORE UNICO DEL TEST -- non deriva dalla geometria"
    )


def test_una_cartella_senza_modello_json_ne_12_wall_json_non_diventa_un_as_built_fantasma(tmp_path):
    """Rilievo del revisore: confronta distingueva l'as-built dal parametrico
    solo per assenza di modello.json, un segnale negativo. Una cartella vuota
    (percorso sbagliato, o corsa parametrica fallita a meta' che non ha mai
    scritto modello.json) finiva classificata come l'as-built vero, con tutte
    le celle 'non impostato' e nessun segnale. Serve un segno positivo: la
    corsa madre ha 12_wall.json (pipeline.WALL_FILENAME) leggibile.
    """
    vuota = tmp_path / "vuota"
    vuota.mkdir()

    with pytest.raises(ValueError, match="vuota"):
        report.confronta([vuota])


def test_legge_json_non_crolla_su_un_file_mal_codificato(tmp_path):
    """F4 del giro di correzione finale: `UnicodeDecodeError` e' sottoclasse
    di `ValueError`, non di `json.JSONDecodeError` -- `except (OSError,
    json.JSONDecodeError)` non la copre. Un `modello.json` con un byte 0xff
    (non UTF-8 valido) la solleva durante la lettura, non durante il parse,
    e senza questo test esce non gestita, portando giu' /api/compare.

    Mutazione che deve morire: tornare a `except (OSError,
    json.JSONDecodeError)` in `_legge_json` -- questa asserzione
    solleverebbe `UnicodeDecodeError` invece di ricevere `None`.
    """
    percorso = tmp_path / "modello.json"
    percorso.write_bytes(b'{"tipo": "estruso", "nota": "\xff"}')

    assert report._legge_json(percorso) is None


def test_la_nota_delle_giunzioni_letta_da_un_json_esterno_si_scrive_con_l_escape_html(tmp_path):
    """nota_giunzioni e' testo libero letto da modello.json -- il campo piu'
    esposto del confronto, perche' viene da un file su disco e non da una
    costante del codice -- e deve passare da html.escape come il resto del
    modulo (vedi _tabella, report.py:323), altrimenti '<' e '&' scritti li'
    dentro rompono la pagina.
    """
    cartelle = _tre_cartelle_finte(tmp_path)
    percorso_modello = cartelle[1] / pipeline.MODEL_FILENAME
    dati = json.loads(percorso_modello.read_text(encoding="utf-8"))
    dati["nota_giunzioni"] = "giunto <b>critico</b> & non lineare"
    percorso_modello.write_text(json.dumps(dati), encoding="utf-8")

    testo = report.write_comparison_report(cartelle, tmp_path / "confronto.html").read_text(
        encoding="utf-8"
    )

    assert "<b>critico</b>" not in testo
    assert "&lt;b&gt;critico&lt;/b&gt;" in testo


def test_confronta_espone_la_chiusura_volume_del_prior(tmp_path):
    """F2 del giro di correzione finale: chiusura_volume e' il controllo che
    wall.py dichiara vedere "un errore che nessuna metrica di qualita' della
    mesh vedrebbe" (somma dei volumi delle membrature contro il volume della
    loro unione, alle giunzioni). Oggi non compariva fuori da 12_wall.json:
    ne' nel confronto ne' nel pannello del browser. `confronta` la legge
    dalla corsa madre e la espone, cosi' l'interfaccia puo' mostrarla.

    Mutazione che deve morire: in `confronta`, non leggere `chiusura_volume`
    dal wall.json della madre -- la chiave sparirebbe dal payload e questa
    asserzione fallirebbe.
    """
    cartelle = _tre_cartelle_finte(tmp_path)

    confronto = report.confronta(cartelle)

    assert confronto["chiusura_volume"]["passato"] is True
    assert confronto["chiusura_volume"]["scarto_relativo"] == 0.0


def test_testo_di_un_dizionario_non_vuoto_non_e_il_repr_python(tmp_path):
    """F15 del giro di correzione finale: `_testo` non aveva un ramo per un
    dizionario non vuoto e cadeva su `str(valore)`, che per un dict e' il
    repr Python -- apici singoli e le cifre intere del float, in una pagina
    dove ogni altra riga passa da `_numero`. E' la sezione 'qualita' degli
    elementi, quella che il vincolo 3 mette in evidenza.

    Mutazione che deve morire: in `_testo`, togliere il ramo per il
    dizionario non vuoto -- questa asserzione troverebbe apici singoli e
    Python invece di una coppia chiave/valore leggibile.
    """
    testo = report._testo({"radius_edge_ratio": {"min": 0.6243550092909288}})

    assert "'" not in testo
    assert "radius_edge_ratio" in testo


def test_i_gradi_di_liberta_dichiarati_confrontabili_compaiono_nella_tabella(tmp_path):
    """CONFRONTABILI['gradi_di_liberta'] e' True: se la tabella 'grandezze
    confrontabili' non mostra la riga, la dichiarazione e la pagina sono in
    disaccordo -- esattamente il tipo di bugia silenziosa che questo task
    esiste per non fare.
    """
    cartelle = _tre_cartelle_finte(tmp_path)

    testo = report.write_comparison_report(cartelle, tmp_path / "confronto.html").read_text(
        encoding="utf-8"
    )

    assert "<th>nodi e tipo di elemento</th>" in testo
    assert "C3D8I" in testo  # element_type del ramo esaedri, dentro la riga


def test_le_grandezze_si_intitolano_con_l_etichetta_non_con_la_chiave(tmp_path):
    """L'appendice cartacea la legge un umano: una riga intitolata
    `gradi_di_liberta` si legge come un refuso di tesi, non come una chiave.

    Mutazione che deve morire: rimettere `{grandezza}` al posto di
    `{html.escape(etichetta)}` nel `<th>` di write_comparison_report.
    """
    cartelle = _tre_cartelle_finte(tmp_path)

    testo = report.write_comparison_report(cartelle, tmp_path / "confronto.html").read_text(
        encoding="utf-8"
    )

    for _, etichetta in report._ETICHETTE_GRANDEZZE:
        assert f"<th>{etichetta}</th>" in testo
    # `volume` e' chiave ed etichetta insieme e non prova niente: mordono solo
    # le due che differiscono.
    assert "gradi_di_liberta" not in testo
    assert "scostamento_nuvola" not in testo


def test_ogni_grandezza_dichiarata_confrontabile_ha_la_sua_etichetta():
    """La mappa e' la sorgente del ciclo, quindi una chiave senza etichetta non
    puo' finire stampata nuda: puo' pero' sparire dalla tabella in silenzio, o
    comparirci pur essendo dichiarata non confrontabile. Le due dichiarazioni
    devono dire la stessa cosa.

    Mutazione che deve morire: togliere la coppia `gradi_di_liberta` dalle
    etichette lasciando `CONFRONTABILI['gradi_di_liberta'] = True`.
    """
    assert {chiave for chiave, _ in report._ETICHETTE_GRANDEZZE} == {
        chiave for chiave, si in report.CONFRONTABILI.items() if si
    }


def test_un_etichetta_con_caratteri_html_passa_da_escape(tmp_path, monkeypatch):
    """L'etichetta finisce in un `<th>` esattamente come il valore finisce in un
    `<td>`, e il valore passa gia' da html.escape. Se un giorno un'etichetta
    portera' un `<` o una `&`, deve uscire dalla stessa porta.

    Mutazione che deve morire: togliere html.escape dall'etichetta nel `<th>`.
    """
    monkeypatch.setattr(report, "_ETICHETTE_GRANDEZZE", (("volume", "volume <b> & 1"),))
    cartelle = _tre_cartelle_finte(tmp_path)

    testo = report.write_comparison_report(cartelle, tmp_path / "confronto.html").read_text(
        encoding="utf-8"
    )

    assert "<th>volume &lt;b&gt; &amp; 1</th>" in testo


def test_due_cartelle_dello_stesso_tipo_si_segnalano_invece_di_sovrascriversi(tmp_path):
    """`presenti[chiave] = {...}` dentro un ciclo sovrascriveva in silenzio se
    due cartelle dichiaravano lo stesso tipo (es. due 'estruso' per un
    percorso sbagliato). Deve segnalare, non tenere solo l'ultima.
    """
    cartelle = _tre_cartelle_finte(tmp_path)
    originale = cartelle[1]  # madre-estruso
    duplicato = tmp_path / "duplicato-estruso"
    duplicato.mkdir()
    (duplicato / "modello.json").write_text(
        (originale / pipeline.MODEL_FILENAME).read_text(encoding="utf-8"), encoding="utf-8"
    )
    (duplicato / "metrics.json").write_text(
        (originale / "metrics.json").read_text(encoding="utf-8"), encoding="utf-8"
    )

    with pytest.raises(ValueError, match="estruso"):
        report.confronta([cartelle[0], originale, duplicato])


def _righe_grandezze(testo: str) -> list[tuple[str, list[str]]]:
    """Le righe della prima tabella, come (intestazione, celle)."""
    return [
        (intestazione, re.findall(r"<td>(.*?)</td>", celle))
        for intestazione, celle in re.findall(r"<tr><th>([^<]+)</th>((?:<td>.*?</td>)+)</tr>", testo)
    ]


def test_l_etichetta_della_riga_nomina_cio_che_la_cella_contiene(tmp_path):
    """Un'etichetta piu' credibile della cella e' peggio della chiave nuda.

    `gradi di liberta'` sopra `nodi 1000, elemento C3D4` prometteva una
    grandezza che la cella non porta -- i gradi di liberta' sarebbero 3 x nodi
    per un solido a spostamenti, e quel numero non e' scritto da nessuna parte.
    Con la chiave nuda in testa il lettore scartava la riga; con l'italiano di
    appendice ci crede. L'etichetta deve nominare cio' che `confronta` mette
    davvero nella cella.

    Mutazione che deve morire: rimettere "gradi di liberta'" (accentato) come
    etichetta della riga sopra una cella di nodi e tipo di elemento.
    """
    cartelle = _tre_cartelle_finte(tmp_path)
    confronto = report.confronta(cartelle)
    testo = report.write_comparison_report(cartelle, tmp_path / "confronto.html").read_text(
        encoding="utf-8"
    )

    etichetta = dict(report._ETICHETTE_GRANDEZZE)["gradi_di_liberta"]
    dentro = confronto["gradi_di_liberta"]["as-built"]

    for campo in dentro:
        assert campo in etichetta, (
            f"la cella porta il campo '{campo}' e l'etichetta «{etichetta}» non lo nomina: "
            "l'intestazione promette una grandezza diversa da quella stampata"
        )
    celle = [
        "nodi 1.000, elemento C3D4",
        "nodi 7.000, elemento C3D8I",
        "nodi 7.000, elemento C3D8I",
    ]
    assert (etichetta, celle) in _righe_grandezze(testo)


def test_una_massa_gia_sul_disco_non_torna_nella_tabella(tmp_path):
    """Le corse fatte prima del deck nudo portano ancora `mass` nei loro file.

    `metrics.json` la scrive sotto `11_export`, `modello.json` sotto `export`:
    due chiavi che nessuna riga legge piu'. Il confronto le deve ignorare --
    non sollevare, e non far ricomparire una riga «massa» calcolata con una
    densita' che il deck di oggi non dichiara.

    Mutazione che deve morire: rimettere `massa` in `CONFRONTABILI` o in
    `_ETICHETTE_GRANDEZZE`.
    """
    cartelle = _tre_cartelle_finte(tmp_path)
    for cartella in cartelle:
        for nome, dentro in (("metrics.json", "11_export"), (pipeline.MODEL_FILENAME, "export")):
            percorso = cartella / nome
            if not percorso.exists():
                continue
            dati = json.loads(percorso.read_text(encoding="utf-8"))
            dati[dentro]["mass"] = 0.25
            percorso.write_text(json.dumps(dati), encoding="utf-8")

    esito = report.confronta(cartelle)
    testo = report.write_comparison_report(cartelle, tmp_path / "confronto.html").read_text(
        encoding="utf-8"
    )

    assert "massa" not in esito
    assert "massa" not in esito["confrontabili"]
    assert not [i for i, _celle in _righe_grandezze(testo) if "massa" in i]


def test_ogni_grandezza_numerica_porta_l_unita_nell_etichetta(tmp_path):
    """Un numero senza unita' in un'appendice cartacea non si ricostruisce.

    Una colonna «volume» con dentro 100.000.000 non dice se sono millimetri
    cubi o metri cubi, e il lettore non ha il codice sotto mano. Il precedente
    e' _COLUMNS, che scrive ("thickness_error", "errore di spessore [mm]").
    Nessun elenco tenuto a mano: e' numerica la riga le cui celle sono tutte
    numeri.

    Mutazione che deve morire: togliere `[mm^3]` da volume.
    """
    cartelle = _tre_cartelle_finte(tmp_path)
    testo = report.write_comparison_report(cartelle, tmp_path / "confronto.html").read_text(
        encoding="utf-8"
    )

    numeriche = [
        intestazione
        for intestazione, celle in _righe_grandezze(testo)
        if celle and all(re.fullmatch(r"-?[\d.,]+", c) for c in celle)
    ]
    assert len(numeriche) == 2, f"righe di soli numeri trovate: {numeriche}"
    senza = [i for i in numeriche if "[" not in i]
    assert not senza, f"grandezze numeriche senza unita' nell'etichetta: {senza}"


# --- il rivestimento: quello che i tre documenti devono reggere stampati ----
#
# I tre documenti finiscono nell'appendice della tesi: si aprono da disco,
# viaggiano allegati e vengono stampati, spesso da una macchina in bianco e
# nero. Un foglio di stile che regge solo a schermo e' un difetto che nessun
# test sulla prosa vede, perche' la prosa resta giusta mentre il documento
# stampato diventa illeggibile. Questi test guardano il rivestimento con lo
# stesso metro con cui gli altri guardano i dati: non che sia bello, ma che
# ogni cosa che il documento afferma con il colore la affermi anche senza.


def _foglio(testo: str) -> str:
    """Il contenuto del solo <style> del documento."""
    return "".join(re.findall(r"<style>(.*?)</style>", testo, re.S))


def _regola(foglio: str, selettore: str) -> str:
    """Le dichiarazioni della regola che ha esattamente quel selettore.

    Non `selettore in foglio`: un selettore che compare dentro un gruppo piu'
    largo o dentro un commento non dice niente su quali proprieta' porti. Qui
    serve il corpo, perche' l'asserzione riguarda i canali dichiarati.
    """
    trovate = re.findall(
        rf"(?:^|[}}\n])\s*{re.escape(selettore)}\s*\{{([^}}]*)\}}", foglio, re.M
    )
    assert trovate, f"nessuna regola con selettore «{selettore}» nel foglio"
    return " ".join(trovate)


def _tre_documenti(tmp_path):
    """I tre documenti che il modulo genera, in un caso normale ciascuno."""
    registro = tmp_path / "sweep" / "registro.jsonl"
    registro.parent.mkdir()
    sweep.append_row(
        registro,
        {
            "fingerprint": "aaa",
            "axes": {"tet.min_ratio": 1.8},
            "outcome": "riuscito",
            "complete": True,
            "on_front": True,
            "thickness_error": 2.0,
            "duration_s": 12.0,
            "metrics": {
                "10_volume_quality": {
                    "tets": 1000,
                    "radius_edge_over_reference": 0.08,
                    "min_dihedral_deg": {"min": 0.162, "median": 38.0},
                }
            },
        },
    )
    corsa = _corsa(
        tmp_path,
        metriche={"06_repair": {"hole_areas": [42120.4, 33986.0, 31702.6, 12231.8]}},
    )
    # una sola cartella: e' il caso che accende <p class='avviso'>, la scheda
    # singola, cioe' la classe che il foglio non ha mai vestito
    singola = _tre_cartelle_finte(tmp_path)[:1]
    return [
        report.write_report(registro, tmp_path / "sweep.html").read_text(encoding="utf-8"),
        report.write_run_report(corsa, viste=[]).read_text(encoding="utf-8"),
        report.write_comparison_report(singola, tmp_path / "confronto.html").read_text(
            encoding="utf-8"
        ),
    ]


def test_un_registro_vuoto_non_produce_una_tabella_senza_righe(tmp_path):
    """Zero candidati e' un dato: va detto, non lasciato come tabella vuota.

    Una tabella con le sole intestazioni e nessuna riga, stampata, si legge
    come un guasto del generatore invece che come uno sweep che non ha ancora
    prodotto niente. Il documento esce lo stesso e dichiara il vuoto.
    """
    registro = tmp_path / "esperimento" / "registro.jsonl"
    registro.parent.mkdir()
    registro.write_text("", encoding="utf-8")

    testo = report.write_report(registro, tmp_path / "report.html").read_text(
        encoding="utf-8"
    )

    assert report.NESSUN_CANDIDATO in testo
    assert "<tbody></tbody>" not in testo
    assert "<thead>" not in testo, "la tabella esce comunque, con le sole intestazioni"


def test_ogni_classe_scritta_nei_documenti_ha_una_regola_nel_foglio(tmp_path):
    """Una classe senza regola e' una dichiarazione che il documento non fa.

    `p.avviso` — la scheda singola del confronto — e' scritta nel documento da
    sempre e non compare in nessuna regola: il paragrafo che avverte «questa
    non e' una tabella di confronto» esce identico al testo intorno. Il
    generatore crede di averlo marcato, il lettore non lo vede.
    """
    for testo in _tre_documenti(tmp_path):
        foglio = _foglio(testo)
        classi = {c for c in re.findall(r"class=['\"]([^'\"]*)['\"]", testo) if c.strip()}
        # Il nome intero e non un prefisso: `".avviso" in foglio` è vero anche
        # se l'unica regola che lo nomina si chiama `.avvisone`, e quella classe
        # resta svestita esattamente come prima. Misurato il 31/08/2026
        # rinominando `p.avviso` in `p.avvisone`: tutti e 71 i test di questo
        # file restavano verdi.
        senza = sorted(
            c for c in classi if not re.search(rf"\.{re.escape(c)}(?![\w-])", foglio)
        )
        assert not senza, f"classi scritte e mai vestite: {senza}"


@pytest.mark.skipif(sys.platform == "win32", reason="NTFS vieta < e > nei nomi: su Windows la cartella non puo' esistere")
def test_un_nome_di_cartella_con_caratteri_html_arriva_come_testo(tmp_path):
    """I nomi di cartella li sceglie chi lancia la corsa, non il programma.

    `<`, `>` e `&` in un nome sono legittimi su disco e diventano marcatura in
    un documento che li scriva crudi. Vale per due dei tre generatori, perche'
    entrambi mettono un nome di cartella nel titolo e nel titolone.
    """
    cattivo = "a<b>&c"
    registro = tmp_path / cattivo / "registro.jsonl"
    registro.parent.mkdir()
    registro.write_text("", encoding="utf-8")
    corsa = tmp_path / f"corsa {cattivo}"
    corsa.mkdir()

    documenti = [
        report.write_report(registro, tmp_path / "sweep.html").read_text(encoding="utf-8"),
        report.write_run_report(corsa, viste=[]).read_text(encoding="utf-8"),
    ]

    for testo in documenti:
        assert cattivo not in testo, "il nome della cartella e' entrato crudo nel documento"
        assert "a&lt;b&gt;&amp;c" in testo


def test_il_foglio_ripete_l_intestazione_e_non_spezza_le_righe_in_stampa(tmp_path):
    """Una tabella lunga finisce su piu' pagine, e la carta non si scorre.

    Senza `table-header-group` la seconda pagina porta colonne di numeri senza
    nomi; senza `break-inside: avoid` una riga si taglia a meta' fra due
    fogli. Sono due difetti che a schermo non esistono e in appendice sono
    permanenti.
    """
    for testo in _tre_documenti(tmp_path):
        foglio = _foglio(testo)
        assert "@media print" in foglio, "il documento non ha nessuna resa per la stampa"
        stampa = foglio.split("@media print", 1)[1]
        assert "table-header-group" in stampa
        assert "break-inside: avoid" in stampa


def test_il_fronte_di_pareto_si_distingue_anche_senza_colore(tmp_path):
    """Il fronte e' il risultato principale della tabella, e va stampato.

    Il fondo verde chiaro non arriva sulla carta: i browser non stampano i
    fondi se non glielo si chiede, e su una laser in bianco e nero diventa
    comunque un grigio indistinguibile. Il fronte deve portare un canale che
    la stampa conserva — un filetto — oltre al peso e al colore.
    """
    testo = _tre_documenti(tmp_path)[0]
    regola = _regola(_foglio(testo), "tr.fronte td")

    assert "font-weight" in regola
    assert "border" in regola, (
        "il fronte si distingue solo per fondo e peso: stampato senza fondi "
        "resta il solo peso, su un corpo di 0,8rem"
    )


def test_i_documenti_non_chiedono_niente_alla_rete(tmp_path):
    """Si aprono da disco, anche staccati: nessuna risorsa esterna.

    Un carattere scaricato da un CDN e' un titolo che cambia faccia sulla
    macchina di chi legge, e una richiesta in uscita da un documento che
    dovrebbe essere un file solo. Le pile di caratteri sono locali per
    obbligo, non per scelta di stile.
    """
    for testo in _tre_documenti(tmp_path):
        assert "http" not in testo
        assert "@import" not in testo
        assert "<link" not in testo
        assert "url(" not in _foglio(testo)


# --- che cosa i tre documenti dicono, non come sono vestiti -----------------
#
# I tre documenti finiscono stampati nell'appendice e vengono discussi mesi
# dopo essere stati generati. Chi li legge non ha il registro sotto mano, non
# ha il codice e non puo' chiedere niente al foglio: tutto quello che serve a
# capire che cosa afferma una cella deve stare nella cella o nell'intestazione
# sopra di essa. Questi test guardano proprio quello.


def _registro(tmp_path, righe: list[dict]) -> Path:
    """Un registro con le righe date, ognuna completata col minimo che serve."""
    registro = tmp_path / "esperimento" / "registro.jsonl"
    registro.parent.mkdir(exist_ok=True)
    for indice, riga in enumerate(righe):
        sweep.append_row(
            registro,
            {
                "fingerprint": f"impronta{indice}",
                "axes": {"tet.min_ratio": 1.8},
                "duration_s": 12.0,
                **riga,
            },
        )
    return registro


def _riuscito(tets: int, over: float = 0.08, errore: float = 2.0) -> dict:
    return {
        "outcome": "riuscito",
        "complete": True,
        "on_front": False,
        "thickness_error": errore,
        "metrics": {
            "10_volume_quality": {
                "tets": tets,
                "radius_edge_over_reference": over,
                "min_dihedral_deg": {"min": 0.162, "median": 38.0},
            }
        },
    }


def _fallito(errore: float = 0.0) -> dict:
    """Un candidato che non e' arrivato in fondo: nessuna misura, nemmeno vuota.

    E' la forma che le quattro righe `fallito` hanno in experiments/muro:
    thickness_error c'e' (0 oppure 9,125) e 10_volume_quality no.
    """
    return {
        "outcome": "fallito",
        "complete": False,
        "on_front": False,
        "thickness_error": errore,
        "metrics": {},
    }


def _corpo_sweep(testo: str) -> list[list[str]]:
    """Le celle di ogni riga del corpo della tabella dello sweep."""
    corpo = testo.split("<tbody>", 1)[1].split("</tbody>", 1)[0]
    return [re.findall(r"<td>(.*?)</td>", riga) for riga in re.findall(r"<tr[^>]*>.*?</tr>", corpo)]


def test_un_candidato_fallito_dichiara_le_misure_che_non_ha(tmp_path):
    """Quattro righe su undici, in experiments/muro, escono con tre celle bianche.

    Un candidato `fallito` non ha 10_volume_quality: tetraedri, fuori vincolo e
    diedro non esistono. Stampate bianche, quelle celle non dicono se manca il
    dato o se il generatore ha saltato una colonna, e chi guarda 132 righe su
    23 pagine non ha modo di chiederlo. Il modulo ha gia' la regola scritta
    (LISTA_VUOTA, NON_IMPOSTATO, VUOTO, SOLI_SPAZI, MAPPA_VUOTA) e `_cell` non
    la applicava.

    Niente trattino: write_comparison_report ha gia' deciso che «un trattino in
    mezzo ai numeri somiglia a un valore».

    Mutazione che uccide questo test: rimettere `else ""` in coda a `_cell`.
    """
    registro = _registro(tmp_path, [_riuscito(tets=1000), _fallito()])

    testo = report.write_report(registro, tmp_path / "sweep.html").read_text(encoding="utf-8")

    assert _celle_bianche(testo) == []
    assert testo.count(f"<td>{report.NON_MISURATO}</td>") == 3
    assert "-" not in report.NON_MISURATO


def test_una_misura_a_zero_non_si_confonde_con_una_misura_assente(tmp_path):
    """Zero tetraedri e' un dato; nessun tetraedro misurato e' un altro fatto.

    Nella stessa tabella un candidato fallito mostra «errore di spessore 0»,
    che letto da solo somiglia al risultato perfetto: la distinzione fra un
    valore misurato e una misura che non c'e' deve stare nella cella.

    Mutazione che uccide questo test: far tornare NON_MISURATO anche per i
    valori falsi (`if not value` invece di `if value is not None`).
    """
    registro = _registro(tmp_path, [_riuscito(tets=0, over=0.0), _fallito()])

    testo = report.write_report(registro, tmp_path / "sweep.html").read_text(encoding="utf-8")

    righe = _corpo_sweep(testo)
    misurata, assente = righe[0], righe[1]
    assert "0" in misurata and report.NON_MISURATO not in misurata
    assert report.NON_MISURATO in assente


def test_gli_istogrammi_dello_sweep_non_mescolano_riusciti_e_falliti(tmp_path):
    """Un candidato fallito porta un thickness_error che non misura nessuna mesh.

    Sul registro di experiments/muro quattro falliti portano 0 oppure 9,125 e
    finivano nella distribuzione insieme ai riusciti. La popolazione degli
    istogrammi e' la stessa del fronte di Pareto — `sweep.objectives`, cioe' i
    confrontabili — e il titolo lo dichiara, altrimenti la selezione e' una
    scelta invisibile.

    Mutazione che uccide questo test: togliere il filtro e ricostruire `errors`
    da tutte le righe.
    """
    registro = _registro(
        tmp_path,
        [_riuscito(tets=1000, errore=2.0), _riuscito(tets=9000, errore=3.0), _fallito(errore=99.0)],
    )

    testo = report.write_report(registro, tmp_path / "sweep.html").read_text(encoding="utf-8")

    titoli = re.findall(r"<title>([^<]*)</title>", testo)
    distribuzioni = [t for t in titoli if report.SOLO_CONFRONTABILI in t]
    assert len(distribuzioni) == 2, titoli
    # il conteggio sta nel paragrafo e non nel titolo: dentro il riquadro da
    # 320 unita' una riga piu' lunga di una quarantina di caratteri esce dal
    # viewBox e stampata si taglia
    assert "2 su 3" in _paragrafo(testo, report.SOLO_CONFRONTABILI)
    # 99 e' l'errore del candidato fallito: nell'istogramma segnerebbe l'estremo
    assert "99" not in testo.split("<h2>Distribuzioni</h2>", 1)[1]


def test_un_registro_di_soli_falliti_non_afferma_una_distribuzione(tmp_path):
    """Zero candidati confrontabili: due riquadri con dentro «vuoto» sono peggio.

    Stampati sono due rettangoli bianchi da cinque centimetri che ripetono, in
    forma di grafico, quello che una riga di prosa dice meglio.

    Mutazione che uccide questo test: chiamare histogram_svg anche con la lista
    vuota invece di dichiarare il vuoto.
    """
    registro = _registro(tmp_path, [_fallito(), _fallito(errore=9.125)])

    testo = report.write_report(registro, tmp_path / "sweep.html").read_text(encoding="utf-8")

    assert report.NESSUN_CONFRONTABILE in testo
    assert "<rect" not in testo
    assert "<svg" not in testo


def test_un_registro_vuoto_non_lascia_riquadri_vuoti_dopo_la_dichiarazione(tmp_path):
    """Il paragrafo «registro vuoto» dice tutto; i due SVG che seguono ripetono peggio.

    Mutazione che uccide questo test: rimettere la sezione delle distribuzioni
    fuori dalla condizione su `rows`.
    """
    registro = tmp_path / "esperimento" / "registro.jsonl"
    registro.parent.mkdir()
    registro.write_text("", encoding="utf-8")

    testo = report.write_report(registro, tmp_path / "sweep.html").read_text(encoding="utf-8")

    assert report.NESSUN_CANDIDATO in testo
    assert "<svg" not in testo
    assert "Distribuzioni" not in testo


def test_ogni_colonna_di_misure_dello_sweep_porta_l_unita(tmp_path):
    """Una colonna di numeri senza unita', in appendice, non si ricostruisce.

    `fuori vincolo` esce come 0.08098 — una frazione, che altrove il progetto
    scrive come percentuale — e `diedro min. [peggiore / mediana]` esce come
    «0.0025 / 38.26», che sono gradi: l'intestazione dichiara quali due
    statistiche ma mai di che cosa. Il precedente e' nella stessa tupla:
    ("thickness_error", "errore di spessore [mm]"). Nessun elenco tenuto a
    mano: e' una colonna di misure quella le cui celle sono tutte numeri, o
    coppie di numeri.

    I dati non si toccano: 0.08098 resta una frazione e l'etichetta dice
    frazione, perche' scriverci «[%]» sopra un numero non moltiplicato e' la
    stessa bugia con un sintomo peggiore.

    Mutazione che uccide questo test: togliere l'unita' da `fuori vincolo` o
    da `diedro min.`.
    """
    registro = _registro(
        tmp_path,
        [
            {**_riuscito(tets=1000, errore=2.5), "duration_s": 12.5},
            {**_riuscito(tets=9000, errore=3.5), "duration_s": 30.5},
        ],
    )

    testo = report.write_report(registro, tmp_path / "sweep.html").read_text(encoding="utf-8")

    # I numeri dei documenti sono in italiano: virgola sui decimali e punto
    # ogni tre cifre. Un riconoscitore che ammette il solo punto vedrebbe
    # «0,08098» come una cella non numerica e la colonna sparirebbe dal conto
    # invece di pretendere la sua unita'.
    numero = r"-?[\d.,]+(?:e[+-]?\d+)?"
    colonne = list(zip(*_corpo_sweep(testo)))
    etichette = [etichetta for _, etichetta in report._COLUMNS]
    misure = [
        etichette[indice]
        for indice, celle in enumerate(colonne)
        if all(re.fullmatch(rf"{numero}(?: / {numero})?", cella) for cella in celle)
        # un conteggio non ha unita': «tetraedri [pezzi]» sarebbe rumore.
        # Sono le grandezze misurate a doverla portare
        and not all(re.fullmatch(r"-?\d{1,3}(?:\.\d{3})*", cella) for cella in celle)
    ]
    assert len(misure) == 4, f"colonne di misure trovate: {misure}"
    senza = [etichetta for etichetta in misure if "[" not in etichetta]
    assert not senza, f"colonne di misure senza unita' nell'etichetta: {senza}"


def _blocchi_dei_parametri(testo: str) -> dict[str, list[tuple[str, str]]]:
    """Le righe della sezione «Parametri», raggruppate sotto la loro intestazione."""
    sezione = testo.split("<h2>Parametri</h2>", 1)[1].split("<h2>", 1)[0]
    blocchi = {}
    for pezzo in sezione.split("<h3>")[1:]:
        nome, resto = pezzo.split("</h3>", 1)
        blocchi[nome] = re.findall(r"<th>(.*?)</th><td>(.*?)</td>", resto)
    return blocchi


def test_un_parametro_con_title_si_stampa_con_la_sua_etichetta(tmp_path):
    """«Una chiave non si stampa mai, si stampa la sua etichetta» (PRODUCT.md).

    `input.max_points 20000000` non dice niente a chi legge l'appendice, e le
    etichette esistono gia': sono i `title` dei campi di PipelineConfig, messi
    li' apposta per il pannello. La stessa logica di
    `server._etichetta_del_percorso`, riscritta qui perche' quel modulo e'
    l'interfaccia e questo il generatore dei documenti.

    Mutazione che uccide questo test: ripiegare sempre sulla chiave, ignorando
    il `title`.
    """
    corsa = _corsa(tmp_path, configurazione="input:\n  max_points: 20000000\n")

    testo = report.write_run_report(corsa, viste=[]).read_text(encoding="utf-8")

    etichetta = PipelineConfig.model_fields["input"].annotation.model_fields["max_points"].title
    assert etichetta, "il campo non ha piu' un title: la prova non prova piu' niente"
    assert _blocchi_dei_parametri(testo)["input"] == [(etichetta, "20.000.000")]
    assert "max_points" not in testo


def test_un_parametro_senza_title_si_stampa_con_la_chiave(tmp_path):
    """Dove il modello non dichiara un `title` la chiave e' l'unica cosa che si sa.

    Non si inventa una frase, e non si lascia la cella al suo posto vuota: e'
    la stessa regola che `server._etichetta_del_percorso` scrive per il
    rifiuto del validatore. Vale sia per un campo senza `title`
    (`model.target_size`) sia per una chiave che il modello non conosce
    affatto, che un config.yaml piu' vecchio puo' ancora portare.

    Mutazione che uccide questo test: stampare `None` — cioe' il title
    mancante — invece della chiave.

    Il campo scelto e' cambiato il 31/08/2026. Era `analysis.material.density`,
    e la prova portava con se' la propria data di scadenza: un `assert not
    ...title` che si dichiarava obsoleto se qualcuno avesse dato un'etichetta a
    quel campo. Qualcuno l'ha fatto, nello stesso giorno e su un altro ramo --
    i quattro campi di `Material` avevano ricevuto il `title` che il pannello
    gia' mostrava, e la classe e' poi uscita col deck nudo -- e la guardia ha morso al primo merge. Il campo nuovo non e'
    piu' sicuro del vecchio: e' semplicemente uno dei cinquantaquattro ancora
    senza etichetta, e quando toccherà a lui la guardia dirà di nuovo dove
    guardare.
    """
    corsa = _corsa(
        tmp_path,
        configurazione="model:\n  target_size: 12.5\nbislacco:\n  chiave: 3\n",
    )

    testo = report.write_run_report(corsa, viste=[]).read_text(encoding="utf-8")

    blocchi = _blocchi_dei_parametri(testo)
    modello = PipelineConfig.model_fields["model"].annotation
    modello = next(t for t in get_args(modello) or (modello,) if t is not type(None))
    assert not modello.model_fields["target_size"].title, (
        "il campo ha un title: la prova non prova piu' niente"
    )
    assert ("target_size", "12,5") in blocchi["model"]
    assert blocchi["bislacco"] == [("chiave", "3")]
    assert "None" not in testo


def test_la_tabella_dei_parametri_e_spezzata_per_blocco(tmp_path):
    """Novanta righe di seguito non si leggono: un'intestazione per blocco le spezza.

    E' la forma che «Metriche per step» ha gia' — un <h3> e la sua tabella —
    riusata invece di inventarne una seconda.

    Mutazione che uccide questo test: tornare a una tabella sola con le chiavi
    puntate.
    """
    corsa = _corsa(
        tmp_path,
        configurazione="input:\n  max_points: 20000000\n  seed: 0\ntet:\n  min_ratio: 1.8\n",
    )

    testo = report.write_run_report(corsa, viste=[]).read_text(encoding="utf-8")

    blocchi = _blocchi_dei_parametri(testo)
    assert list(blocchi) == ["input", "tet"]
    assert len(blocchi["input"]) == 2 and len(blocchi["tet"]) == 1


def test_ogni_documento_dice_da_quale_sorgente_e_da_quando_viene(tmp_path):
    """Quarto principio di prodotto: la provenienza e' parte del risultato.

    Stampati, i tre documenti diventano fogli che nessuno puo' ricondurre a una
    corsa: «Sweep — muro» e basta, «Corsa: lab_crop» e basta. Sotto il titolone
    ci va il percorso della sorgente e la data di generazione, perche' il
    documento si discute mesi dopo essere stato scritto.

    Mutazione che uccide questo test: togliere la riga di provenienza da uno
    solo dei tre documenti.
    """
    registro = _registro(tmp_path, [_riuscito(tets=1000)])
    corsa = _corsa(tmp_path, metriche={"01_load": {"points_kept": 10}})
    cartelle = _tre_cartelle_finte(tmp_path)
    oggi = date.today().isoformat()

    documenti = [
        (report.write_report(registro, tmp_path / "sweep.html"), [str(registro)]),
        (report.write_run_report(corsa, viste=[]), [str(corsa)]),
        (
            report.write_comparison_report(cartelle, tmp_path / "confronto.html"),
            [str(c) for c in cartelle],
        ),
    ]
    for percorso, sorgenti in documenti:
        testo = percorso.read_text(encoding="utf-8")
        riga = _paragrafo(testo, report.GENERATO)
        assert oggi in riga, riga
        for sorgente in sorgenti:
            assert marcatura.escape(sorgente) in riga, (sorgente, riga)


def test_il_documento_dello_sweep_porta_il_commit_scritto_nel_registro(tmp_path):
    """Il commit e' gia' in ogni riga, sotto `provenance`: non ce n'e' da cercare.

    Mutazione che uccide questo test: scrivere il commit del processo che
    genera il documento invece di quello registrato dalle corse.
    """
    riga = _riuscito(tets=1000)
    riga["provenance"] = {"commit": "10e15a0b3ebc1c169b1732dea68dc652517b6065", "dirty": True}
    registro = _registro(tmp_path, [riga])

    testo = report.write_report(registro, tmp_path / "sweep.html").read_text(encoding="utf-8")

    assert "10e15a0b3ebc1c169b1732dea68dc652517b6065" in _paragrafo(testo, report.GENERATO)


def test_l_intestazione_della_qualita_descrive_la_tabella_che_ha_sotto(tmp_path):
    """Il titolo prometteva due colonne sopra una tabella che ne ha una.

    Il ragionamento e' giusto — radius_edge_ratio e Jacobiano scalato non si
    sottraggono — ma la forma descritta non e' quella del documento: sotto c'e'
    una riga per modello, e la colonna dei valori non aveva nome.

    Mutazione che uccide questo test: rimettere «due colonne» nel titolo, o
    togliere il <thead> alla tabella.
    """
    cartelle = _tre_cartelle_finte(tmp_path)

    testo = report.write_comparison_report(cartelle, tmp_path / "confronto.html").read_text(
        encoding="utf-8"
    )

    titolo, sezione = testo.split("<h2>Qualità degli elementi", 1)[1].split("</h2>", 1)
    sezione = sezione.split("<h2>", 1)[0]
    assert "due colonne" not in titolo
    intestazioni = re.findall(r"<th>(.*?)</th>", sezione.split("<tbody>", 1)[0])
    corpo = sezione.split("<tbody>", 1)[1]
    assert len(intestazioni) == 2, intestazioni
    assert all(riga.count("<t") == 2 for riga in re.findall(r"<tr>(.*?)</tr>", corpo))


def test_i_documenti_non_mescolano_due_ortografie_nello_stesso_elenco(tmp_path):
    """`E'` con l'apostrofo e `è` con l'accento, due righe piu' sotto, nello stesso <ul>.

    Va in appendice cartacea, e il controllo degli accenti non vede la maiuscola
    tronca: TRONCA cerca `[aeiou]'` minuscole. Il <title> del confronto usa il
    doppio trattino ASCII mentre gli altri due usano l'em dash, e quel titolo
    finisce nell'intestazione di pagina quando si stampa in PDF dal browser.

    Mutazione che uccide questo test: rimettere `E'` in NOTE_STATICHE o `--`
    nel <title> del confronto.
    """
    assert not [nota for nota in report.NOTE_STATICHE if "E'" in nota]

    for testo in _tre_documenti(tmp_path):
        titolo = re.search(r"<title>(.*?)</title>", testo).group(1)
        assert "--" not in titolo, titolo
def _regole(foglio: str) -> list[tuple[str, str]]:
    """Coppie (selettori, dichiarazioni) di ogni regola del foglio.

    Il blocco `@media print` non si presenta come regola -- il suo corpo
    contiene graffe -- e le regole che ha dentro compaiono qui come tutte le
    altre. È esattamente ciò che serve: la domanda che questi test fanno non è
    dove sta scritta una dichiarazione, ma su che cosa cade.
    """
    return [(sel.strip(), corpo) for sel, corpo in re.findall(r"([^{}@]+)\{([^{}]*)\}", foglio)]


def _cade_su(selettori: str, elemento: str) -> bool:
    """Vero se almeno uno dei selettori termina su quell'elemento.

    Il confronto è sull'ultimo elemento semplice, spogliato di discendenza,
    figlio e pseudo-classi: `tr`, `tbody tr` e `.sweep > tr:hover` cadono tutti
    su `tr`. Una riscrittura del foglio può cambiare il selettore quanto vuole,
    finché la dichiarazione continua a cadere dove la garanzia la vuole.
    """
    return any(
        parte.split()[-1].split(">")[-1].split(":")[0].strip() == elemento
        for parte in selettori.split(",")
        if parte.strip()
    )


def _dichiarano(foglio: str, proprieta: str, valore: str) -> list[str]:
    """I selettori delle regole che dichiarano quella proprietà con quel valore."""
    return [
        sel
        for sel, corpo in _regole(foglio)
        if re.search(rf"\b{proprieta}\s*:\s*{valore}\b", corpo)
    ]


def test_le_due_garanzie_di_stampa_cadono_sulle_righe_e_sulle_intestazioni(tmp_path):
    """Non che le due dichiarazioni esistano: che cadano dove servono.

    `test_il_foglio_ripete_l_intestazione_e_non_spezza_le_righe_in_stampa`
    cerca le due stringhe dentro tutto il blocco `@media print`, e una stringa
    non ha un bersaglio. Misurato il 31/08/2026 spostando `display:
    table-header-group` da `thead` a `caption` e `break-inside: avoid` da `tr,
    figure, .istogramma` a `h4`: le due garanzie spariscono dal documento
    stampato -- la seconda pagina torna a portare colonne di numeri senza nomi
    e le righe a spezzarsi fra due fogli -- e tutti e 69 i test di questo file
    restano verdi.

    Qui il bersaglio è l'elemento, non il selettore: `thead`, `table thead` e
    `.sweep thead` valgono uguale, e una riscrittura del foglio non fa cadere
    il test finché la garanzia resta.
    """
    for testo in _tre_documenti(tmp_path):
        stampa = _foglio(testo).split("@media print", 1)[1]
        intestazioni = _dichiarano(stampa, "display", "table-header-group")
        assert any(_cade_su(sel, "thead") for sel in intestazioni), (
            f"nessuna regola ripete l'intestazione sulle pagine dopo la prima: {intestazioni}"
        )
        righe = _dichiarano(stampa, "break-inside", "avoid")
        assert any(_cade_su(sel, "tr") for sel in righe), (
            f"nessuna regola tiene insieme una riga fra due fogli: {righe}"
        )


def test_il_filetto_del_fronte_lascia_inchiostro_sulla_carta(tmp_path):
    """Un filetto dichiarato `none` è un filetto che non c'è.

    `test_il_fronte_di_pareto_si_distingue_anche_senza_colore` chiede che la
    regola del fronte nomini `border`, e `border: none` la nomina: misurato il
    31/08/2026 sostituendo i due filetti di `tr.fronte td` con `border: none`,
    il fronte perde sulla carta tutto tranne il peso di un corpo di 0,8rem e
    tutti e 69 i test di questo file restano verdi.

    Qui la domanda è se il filetto lasci inchiostro: nessuna regola del fronte
    può annullarlo, e almeno una deve dichiararlo con una larghezza vera.
    """
    testo = _tre_documenti(tmp_path)[0]
    filetti = [
        (sel, proprieta, valore.strip())
        for sel, corpo in _regole(_foglio(testo))
        if ".fronte" in sel
        for proprieta, valore in re.findall(r"\b(border[a-z-]*)\s*:\s*([^;]+)", corpo)
    ]

    assert filetti, "il fronte non dichiara nessun filetto: stampato resta il solo peso"
    spenti = [voce for voce in filetti if voce[2] in ("none", "0", "0px")]
    assert not spenti, f"il fronte dichiara filetti che non lasciano inchiostro: {spenti}"


# --- i numeri dei tre documenti si leggono in italiano ---------------------
#
# I documenti sono un'appendice italiana stampata, e la prosa del progetto
# scrive gia' «8,10%» e «1.752.795 tetraedri». Le tabelle scrivevano invece
# `1.1943` e `0.08098`: in un documento italiano `1.1943` si legge
# «milleduecento», cioe' il segno dice l'opposto di quel che significa.
#
# La regola applicata sta in `report._SEGNI_ITALIANI` e nei suoi due usi:
# virgola sui decimali, punto ogni tre cifre a sinistra della virgola. Il
# raggruppamento vale per le grandezze, non per gli identificatori.


def test_un_intero_di_nove_cifre_porta_i_punti_delle_migliaia():
    """Mutazione che deve morire: togliere il ramo `int` di `_testo` -- il
    volume tornerebbe `477700000`, nove cifre di seguito che stampate si
    contano col dito.
    """
    assert report._testo(477700000) == "477.700.000"


def test_il_raggruppamento_comincia_gia_dalla_quarta_cifra():
    """Una regola sola per tutta l'appendice: dalle migliaia in su si
    raggruppa sempre, intero o decimale che sia. La regola opposta -- lasciare
    intatti i numeri di quattro cifre -- e' altrettanto in uso, ma due regole
    nella stessa colonna fanno sembrare `1234` e `12.345` due formati diversi
    dello stesso dato.

    Mutazione che deve morire: togliere la virgola dalla specifica di formato
    (`:,.10f` diventa `:.10f`) -- `1234` e `1234,5` passerebbero senza punto.
    """
    assert report._testo(1234) == "1.234"
    assert report._testo(1234.5) == "1.234,5"


def test_un_decimale_sotto_l_unita_prende_la_virgola_e_nessun_separatore():
    """Mutazione che deve morire: togliere `.translate(_SEGNI_ITALIANI)` dal
    ramo decimale di `_numero` -- resterebbe `0.08098`.
    """
    assert report._testo(0.08098) == "0,08098"
    assert report._testo(1.1943) == "1,1943"
    assert report._testo(38.26) == "38,26"


def test_l_esponenziale_prende_la_virgola_sulla_mantissa_e_lascia_l_esponente():
    """Fuori da 1e-4 .. 1e12 `_numero` passa alla notazione esponenziale, e li'
    la resa e' dichiarata invece che casuale: la mantissa e' una grandezza e
    prende la virgola, l'esponente e' la potenza di dieci che la scala e resta
    come si scrive. Un punto ogni tre cifre dentro `e-09` non separerebbe
    niente.

    2,5493e-09 e' la densita' del C25/30 in t/mm^3, che sta in ogni corsa.

    Mutazione che deve morire: togliere `.translate(_SEGNI_ITALIANI)` dal ramo
    esponenziale -- la mantissa tornerebbe col punto in mezzo a una pagina di
    virgole.
    """
    assert report._testo(2.5493e-09) == "2,5493e-09"
    assert report._testo(4.2e18) == "4,2e+18"


def test_non_un_numero_e_infinito_restano_le_parole_gia_scritte():
    """Le due costanti vengono prima di ogni formattazione: `nan` e `inf` non
    sono numeri da rendere in italiano ma esiti da dichiarare.

    Mutazione che deve morire: spostare le due guardie dopo la formattazione --
    `float('nan')` non ha ne' migliaia ne' decimali e uscirebbe come `nan`.
    """
    assert report._testo(float("nan")) == report.NON_UN_NUMERO
    assert report._testo(float("inf")) == report.INFINITO
    assert report._testo(float("-inf")) == f"-{report.INFINITO}"


def test_un_negativo_porta_insieme_il_segno_i_punti_e_la_virgola():
    """Il segno non e' un separatore e non deve raccoglierne uno: `-1.234,57`
    e non `-.1234,57`. Le sei cifre significative valgono come sempre, il
    segno non conta come cifra.

    Mutazione che deve morire: raggruppare a mano contando le cifre da destra
    sulla stringa intera, segno compreso.
    """
    assert report._testo(-1234.5678) == "-1.234,57"
    assert report._testo(-477700000) == "-477.700.000"


def test_lo_zero_resta_uno_zero():
    """Mutazione che deve morire: togliere `.rstrip("0").rstrip(".")` --
    lo zero uscirebbe `0,0000000000`, che stampato afferma dieci decimali
    misurati.
    """
    assert report._testo(0) == "0"
    assert report._testo(0.0) == "0"


def test_quello_che_non_e_una_grandezza_non_viene_raggruppato():
    """Il separatore va sulle grandezze. Un'impronta, un anno, un numero di
    versione, un codice di elemento non sono grandezze: raggrupparli
    spezzerebbe un identificatore in tre pezzi che non si rimettono insieme.

    Nei tre documenti tutti gli identificatori arrivano gia' come stringhe --
    l'impronta esadecimale del registro, `C3D10`, `C25_30`, il commit della
    provenienza -- e il ramo che li stampa non tocca nessun separatore.

    Mutazione che deve morire: raggruppare in `_testo` prima di distinguere
    stringa da numero (per esempio su `str(valore)` con una regex sulle cifre)
    -- l'anno diventerebbe `2.026` e l'impronta si spezzerebbe.
    """
    assert report._testo("2026") == "2026"
    assert report._testo("1.10.2") == "1.10.2"
    # L'impronta in tabella si scrive troncata alle prime dodici cifre, ma
    # nessuna delle due -- ne' l'intera ne' la troncata -- passa da un
    # separatore: sono cifre di un identificatore, non di una grandezza.
    impronta = "34fde846646a49c15db339663ce8e7d84ad64a8c5f9c8cbd7551176a4b4a47df"
    assert report._testo(impronta) == impronta
    assert report._cell({"fingerprint": impronta}, "fingerprint") == "34fde846646a"


def test_la_tabella_dello_sweep_raggruppa_i_tetraedri_e_lascia_stare_l_impronta(tmp_path):
    """La stessa riga che l'appendice della tesi stampa: `_cell` la formatta
    una volta sola, e la mutazione sotto la romperebbe li'.

    Mutazione che deve morire: togliere il ramo `int` di `_cell` -- i
    tetraedri, che nel registro sono interi e non passano da `_numero`,
    tornerebbero `1752795`.
    """
    registro = _registro(tmp_path, [_riuscito(tets=1752795, over=0.08098)])

    testo = report.write_report(registro, tmp_path / "sweep.html").read_text(encoding="utf-8")

    assert "<td>1.752.795</td>" in testo
    assert "<td>0,08098</td>" in testo
    assert "1752795" not in testo
    # l'impronta e' un identificatore e attraversa la tabella intatta
    assert "<td>impronta0</td>" in testo


def test_il_registro_resta_col_punto_dopo_che_il_documento_e_stato_scritto(tmp_path):
    """La formattazione e' del documento, non del dato: il `.jsonl` e' la
    rappresentazione leggibile a macchina e resta in notazione neutra.

    Mutazione che deve morire: formattare in `sweep.append_row` invece che in
    `report` -- il registro porterebbe le virgole e nessun lettore JSON lo
    rileggerebbe.
    """
    registro = _registro(tmp_path, [_riuscito(tets=1752795, over=0.08098)])
    prima = registro.read_bytes()

    report.write_report(registro, tmp_path / "sweep.html")

    assert registro.read_bytes() == prima
    riga = json.loads(prima.decode("utf-8").splitlines()[0])
    assert riga["metrics"]["10_volume_quality"]["radius_edge_over_reference"] == 0.08098
    assert "0.08098" in prima.decode("utf-8")


def test_i_tetraedri_raggruppati_non_allargano_la_loro_colonna(tmp_path):
    """Il separatore costa due caratteri sul numero piu' lungo della tabella, e
    la tabella dello sweep viene stampata: la domanda non e' estetica, e' se le
    colonne di destra restano sul foglio.

    Misurato in Chrome (--headless, regole di `@media print` applicate, finestra
    a 717px cioe' la larghezza stampabile di un A4 con margini da 1cm) sul
    registro di experiments/muro: le otto colonne misurano
    86,0 | 244,9 | 84,9 | 86,0 | 115,4 | 115,4 | 145,9 | 70,5 px prima del
    cambiamento e le stesse otto dopo. Zero pixel aggiunti, perche' la colonna
    dei tetraedri e' larga quanto la parola «TETRAEDRI» che la intesta, e
    `1.752.795` ha esattamente le nove battute di quella parola.

    Questo test e' la guardia in caratteri di quella misura: e' la cella piu'
    larga della tabella a decidere la colonna, e finche' non supera la propria
    intestazione la colonna non cresce.

    Mutazione che deve morire: raggruppare a due cifre invece che a tre, o
    separare con qualcosa di piu' largo di un punto -- `1.75.27.95` sfonderebbe
    l'intestazione e con essa il bordo del foglio.
    """
    intestazione = dict(report._COLUMNS)["tets"]
    riga = _riuscito(tets=1752795)

    assert report._cell(riga, "tets") == "1.752.795"
    assert len(report._cell(riga, "tets")) <= len(intestazione)


# --- l'impronta in appendice: dodici cifre, non sessantaquattro --------------


_IMPRONTA_VERA = "2e93bb8095dbb8e79d5b1a3ba52ff3c9ee0f0c4b48f7f4e1d8a4a5cbb1e5c0aa"


def test_l_impronta_in_tabella_si_scrive_con_le_prime_dodici_cifre(tmp_path):
    """L'impronta in appendice si scrive con le prime dodici cifre.

    Dodici non e' un numero scelto qui: la cartella di ogni candidato si chiama
    gia' `fingerprint(cfg)[:12]` e i documenti della Fase 2 citano le impronte
    gia' troncate. Chi legge l'appendice ritrova la cartella sul disco leggendo
    la cella, invece di contare sessantaquattro cifre spezzate su cinque righe.

    Non e' una cura per la larghezza di stampa, e il test non la promette:
    misurata in Chrome sul registro di experiments/muro con le regole di
    `@media print` applicate e la finestra a 717 px, la colonna dell'impronta
    stava in 86,0 px prima e sta in 86,0 px adesso, perche' le sessantaquattro
    cifre andavano gia' a capo dentro il `max-width` del foglio.

    Mutazione che deve morire: togliere il troncamento in `_cell` -- la cella
    tornerebbe di sessantaquattro cifre e la tabella di 951 px.
    """
    assert report._cell({"fingerprint": _IMPRONTA_VERA}, "fingerprint") == "2e93bb8095db"

    registro = _registro(tmp_path, [{**_riuscito(tets=1000), "fingerprint": _IMPRONTA_VERA}])
    testo = report.write_report(registro, tmp_path / "sweep.html").read_text(encoding="utf-8")

    assert "<td>2e93bb8095db</td>" in testo
    assert _IMPRONTA_VERA not in testo


def test_l_intestazione_dell_impronta_dichiara_che_e_un_troncamento():
    """Chi legge l'appendice non ha il registro sotto mano: una colonna di dodici
    cifre intestata «impronta» si legge come l'impronta intera, e non lo e'.

    Mutazione che deve morire: rimettere l'etichetta a «impronta» -- la cella
    resterebbe troncata e l'intestazione affermerebbe il contrario.
    """
    assert dict(report._COLUMNS)["fingerprint"] == "impronta (prime 12 cifre)"


def test_una_riga_senza_impronta_dichiara_cio_che_manca():
    """Il troncamento e' una fetta di stringa, e una fetta di `None` esplode. La
    cella vuota deve continuare a dire «non misurato» come tutte le altre.

    Mutazione che deve morire: troncare prima di distinguere la stringa
    dall'assenza -- la riga senza impronta alzerebbe un TypeError, oppure
    stamperebbe `None` come se fosse un valore letto.
    """
    assert report._cell({}, "fingerprint") == report.NON_MISURATO
    assert report._cell({"fingerprint": None}, "fingerprint") == report.NON_MISURATO


def test_un_impronta_piu_corta_di_dodici_cifre_resta_quella_che_e():
    """I registri di prova di questa suite portano impronte finte e corte. Il
    troncamento non deve ne' rompersi ne' inventare cifre che nel dato non ci
    sono.

    Mutazione che deve morire: riempire la cella fino a dodici caratteri
    (uno zfill, un ljust) -- la cella affermerebbe cifre mai calcolate.
    """
    assert report._cell({"fingerprint": "aaa"}, "fingerprint") == "aaa"
    assert report._cell({"fingerprint": "impronta0"}, "fingerprint") == "impronta0"


def test_dodici_cifre_distinguono_le_ventidue_righe_dei_registri_veri():
    """Un troncamento che facesse collidere due righe renderebbe la tabella
    ambigua proprio dove serve: due candidati diversi, la stessa cella.

    Le ventidue righe di experiments/muro e experiments/lab_crop sono la
    provenienza della tabella sperimentale della tesi. Su quelle si misura, non
    su impronte inventate: dodici cifre le distinguono tutte, e ogni cella
    coincide con il nome della cartella del candidato -- che e' l'ancoraggio con
    cui si ritrova la corsa sul disco.

    Mutazione che deve morire: troncare a meno cifre, o troncare dalla coda
    invece che dalla testa -- la cella smetterebbe di nominare la cartella.
    """
    radice = Path(__file__).resolve().parents[1] / "experiments"
    celle = []
    for registro in sorted(radice.glob("*/registro.jsonl")):
        for numero, riga in enumerate(registro.read_text(encoding="utf-8").splitlines(), 1):
            if not riga.strip():
                continue
            voce = json.loads(riga)
            cella = report._cell(voce, "fingerprint")
            cartella = voce["out_dir"].replace("\\", "/").rstrip("/").rsplit("/", 1)[-1]
            assert cella == cartella, (
                f"{registro.parent.name}/registro.jsonl riga {numero}: la cella "
                f"'{cella}' non nomina la cartella '{cartella}'"
            )
            celle.append(cella)

    assert len(celle) == 22, f"attese 22 righe nei due registri, trovate {len(celle)}"
    assert len(set(celle)) == 22, "due righe collidono sulle prime dodici cifre"
