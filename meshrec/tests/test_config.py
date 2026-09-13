"""La configurazione e l'unico luogo dei valori predefiniti, e sopravvive al round-trip YAML."""

from pathlib import Path

import numpy as np
import pytest
import yaml
from pydantic import ValidationError

from meshrec.core import config
from meshrec.core.config import PipelineConfig


def test_defaults_are_in_working_units():
    cfg = config.PipelineConfig(input=config.InputConfig(path="nuvola.ply"))
    assert cfg.export.set_tolerance_factor == pytest.approx(6.0)
    assert cfg.input.scale == pytest.approx(1.0)


def test_yaml_round_trip_preserves_every_field(tmp_path):
    cfg = config.PipelineConfig(
        input=config.InputConfig(path="nuvola.ply", scale=1000.0),
        surface=config.SurfaceConfig(poisson_depth=11, density_quantile=0.1),
        tet=config.TetConfig(min_ratio=1.4, max_volume=250.0),
    )
    path = tmp_path / "config.yaml"
    config.save_config(cfg, path)
    assert config.load_config(path) == cfg


def test_invalid_values_are_rejected():
    with pytest.raises(ValueError):
        config.InputConfig(path="nuvola.ply", scale=0.0)
    with pytest.raises(ValueError):
        config.SurfaceConfig(density_quantile=1.5)


def test_experiment_round_trip_and_defaults(tmp_path):
    """L'esperimento sopravvive al round-trip e i suoi predefiniti vivono qui."""
    import yaml

    experiment = config.ExperimentConfig(
        name="muro_ricostruzione",
        base=Path("muro.yaml"),
        axes=[config.AxisSpec(path="tet.min_ratio", values=[1.7, 1.8, 2.0])],
        known_thickness=1245.7,
    )
    assert experiment.sweep.workers == 4
    assert experiment.sweep.timeout_s == 1800
    assert experiment.sweep.keep_dominated_artifacts is False

    path = tmp_path / "esperimento.yaml"
    path.write_text(
        yaml.safe_dump(experiment.model_dump(mode="json"), sort_keys=False), encoding="utf-8"
    )
    assert config.load_experiment(path) == experiment


def test_an_axis_with_no_values_is_rejected():
    with pytest.raises(ValueError):
        config.AxisSpec(path="tet.min_ratio", values=[])


def test_due_chiavi_omonime_nello_yaml_sono_rifiutate(tmp_path):
    """`safe_load` tiene l'ultima e la prima sparisce senza un segnale.

    E' l'unico ingresso degenere senza sintomo: gli altri almeno risolvono
    zero elementi. Una regione corretta e riscritta sotto lo stesso nome
    verrebbe scritta nel deck nella versione che l'operatore credeva di aver
    sostituito.

    Mutazione che lo uccide: tornare a `yaml.safe_load`. Il file viene letto,
    `membratura` vale 1 e nessuno sa che lo 0 c'era.
    """
    percorso = tmp_path / "config.yaml"
    percorso.write_text(
        "input:\n  path: nuvola.ply\n"
        "tet:\n  min_ratio: 1.4\n  max_volume: 250.0\n"
        "regioni:\n"
        "  pilastro:\n    membratura: 0\n"
        "  pilastro:\n    membratura: 1\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="pilastro"):
        config.load_config(percorso)


def test_un_tag_python_object_nello_yaml_solleva(tmp_path):
    """Il loader e' sicuro per costruzione (`_LoaderChiaviUniche` eredita da
    `yaml.SafeLoader`), ma nessun test lo asserisce ancora: questo lo fa.

    Un `!!python/object/apply:...` con `yaml.Loader`/`yaml.UnsafeLoader`
    esegue la chiamata alla lettura del file; con un loader derivato da
    `SafeLoader` non c'e' alcun costruttore per quel tag, e `yaml.load`
    solleva prima di costruire nulla.

    Mutazione che lo uccide: sostituire `_LoaderChiaviUniche(yaml.SafeLoader)`
    con `_LoaderChiaviUniche(yaml.UnsafeLoader)` in `carica_yaml` -- il tag
    verrebbe costruito (ed eseguito) invece di sollevare.
    """
    percorso = tmp_path / "config.yaml"
    percorso.write_text(
        'input:\n  path: !!python/object/apply:os.system ["echo pwned"]\n',
        encoding="utf-8",
    )
    with pytest.raises(yaml.YAMLError):
        config.carica_yaml(percorso)


def test_anche_il_registro_degli_esperimenti_rifiuta_le_chiavi_omonime(tmp_path):
    """La stessa falla sta su due safe_load: si chiude in un punto e si usa in due.

    Il `name` duplicato e' la forma minima: `axes` e' una lista, e le
    chiavi omonime esistono solo dentro una mappa.

    Mutazione che lo uccide: passare il loader solo a `load_config`.
    Questo test cade, l'altro passa.
    """
    percorso = tmp_path / "experiment.yaml"
    percorso.write_text(
        "name: primo\n"
        "name: secondo\n"
        "base: base.yaml\n"
        "axes:\n  - path: tet.min_ratio\n    values: [1.6, 1.8]\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="name"):
        config.load_experiment(percorso)


# La difesa sta sulla base comune e non su un singolo model_config scritto a
# mano dove il difetto e' stato visto.
@pytest.mark.parametrize("grafia", ["1e999", "Infinity", "inf", "nan", "NaN"])
def test_un_infinito_o_nan_su_tet_max_volume_e_rifiutato(grafia):
    with pytest.raises(ValueError, match="finite number"):
        config.TetConfig(max_volume=grafia)


def test_i_valori_decimali_normali_arrivano_ancora_a_destinazione():
    """Il controllo che smentisce: un vincolo che rifiuta tutto passerebbe il test sopra."""
    assert config.TetConfig(max_volume="2.5").max_volume == pytest.approx(2.5)
    assert config.TetConfig(max_volume="1e3").max_volume == pytest.approx(1000.0)


def test_un_inf_gia_scritto_su_disco_non_si_rilegge(tmp_path):
    """Il verso della lettura: una configurazione con .inf non deve poter tornare dentro."""
    path = tmp_path / "config.yaml"
    path.write_text(
        "input:\n  path: nuvola.ply\ndownsample:\n  voxel_size: .inf\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="finite number"):
        config.load_config(path)


def test_lo_schema_non_sposta_l_impronta_dei_registri_in_silenzio():
    """Due sorveglianze sulle 22 righe della tabella sperimentale, non una.

    **Riga per riga**: la cartella di un candidato e' `fingerprint(cfg)[:12]`
    (`core/sweep.py`), quindi il basename di `out_dir` ancora l'impronta
    registrata alla riga che la porta. Regge a qualunque schema, perche' non
    ricalcola niente: cade se qualcuno scambia due config fra righe, o
    riscrive a mano un `fingerprint`.

    **In sequenza**: l'aggregato delle impronte che lo schema **corrente**
    produce da quelle stesse configurazioni, nell'ordine in cui le righe
    stanno sul disco. Cade se un campo entra o esce da un blocco dentro
    l'impronta, e cade anche se due config vengono scambiate fra righe.

    L'ordine non e' un dettaglio di resa: e' l'unica cosa che distingue le 22
    impronte da un mucchio. Ordinarle prima di hasharle -- come faceva la
    prima stesura di questa guardia -- rende il digest invariante allo
    scambio, e lo scambio e' proprio la mutazione che il legame per-riga,
    morto col cambio di schema, sorvegliava.

    Il campo `fingerprint` delle righe non si riscrive: e' un dato misurato.
    L'aggregato invece si aggiorna quando lo schema cambia apposta, e allora
    lo si dice nel commit. **Aggiornato due volte l'08/09/2026**: prima perche'
    il blocco `export` e' entrato in `PipelineConfig` -- ogni configurazione ne
    porta uno anche dove lo YAML non lo dichiara -- poi perche' `analysis` ne e'
    uscito. Le ventidue impronte si sono mosse tutte e due le volte.

    Le righe registrate portano `analysis`, ed erano scritte quando il blocco
    esisteva: sono un dato misurato e non si riscrivono. Lo schema di oggi le
    rifiuterebbe per nome, quindi il lettore toglie i blocchi usciti prima di
    rivalidarle -- e cosi' facendo asserisce anche che `BLOCCHI_RIMOSSI` nomina
    davvero cio' che quelle righe portano.
    """
    import hashlib
    import json

    from meshrec.core.sweep import fingerprint

    radice = Path(__file__).resolve().parents[1] / "experiments"
    marchi = []
    for registro in sorted(radice.glob("*/registro.jsonl")):
        for numero, riga in enumerate(registro.read_text(encoding="utf-8").splitlines(), 1):
            if not riga.strip():
                continue
            voce = json.loads(riga)
            dove = f"{registro.parent.name}/registro.jsonl riga {numero}"
            assert "config" in voce, f"{dove}: la riga non porta la configurazione"
            # `out_dir` e' scritto dalla piattaforma che ha girato lo sweep e
            # puo' portare separatori di Windows: il basename si isola a mano.
            cartella = voce["out_dir"].replace("\\", "/").rstrip("/").rsplit("/", 1)[-1]
            assert cartella == voce["fingerprint"][:12], (
                f"{dove}: la cartella '{cartella}' non e' quella che l'impronta "
                f"registrata nomina ({voce['fingerprint'][:12]})"
            )
            vecchia = {
                blocco: valore
                for blocco, valore in voce["config"].items()
                if blocco not in config.BLOCCHI_RIMOSSI
            }
            marchi.append(fingerprint(PipelineConfig.model_validate(vecchia)))

    assert len(marchi) == 22, f"attese 22 righe nei due registri, trovate {len(marchi)}"
    aggregato = hashlib.sha256("\n".join(marchi).encode("utf-8")).hexdigest()
    assert aggregato == "1465833323a77a9a2eeacdd891cc811cdba4e291a3fb14bff174e35fa78eaad1", (
        "lo schema della configurazione ha spostato l'impronta delle righe "
        "registrate: se e' voluto, aggiorna l'aggregato e dillo nel commit"
    )


@pytest.mark.parametrize(
    ("caso", "impronta"),
    [
        ("lab.yaml", "594edc5c2334706a757f8a965b2b3d8c94579aeb1feabae81885c99e23a4aa5c"),
        ("muro.yaml", "65efdb8ff0ac3c5f37f98e2e2dbaf9d288274d08d031ff96c4780335d32a7ac2"),
    ],
)
def test_l_impronta_delle_configurazioni_del_caso_studio_e_quella_misurata(caso, impronta):
    """Le due configurazioni da cui partono gli sweep di tesi, fissate al valore
    misurato dopo il taglio di `bpa`/`alpha`/`decimate`.

    Il test sopra rilegge i registri e non se ne accorgerebbe: ogni riga porta
    dentro di se' la configurazione con cui e' stata calcolata, quindi resta
    derivabile anche se la base da cui e' nata cambia. Una modifica a
    `casi/lab.yaml` o a `casi/muro.yaml` sposterebbe in silenzio le corse
    future fuori dalle cartelle di quelle gia' registrate: qui lo dice.

    **L'impronta di `lab.yaml` e' cambiata apposta il 30/08/2026**, e questo e'
    il posto in cui si dichiara. La densita' del calcestruzzo e' passata da
    2,5e-9 a 2,5493e-9 t/mm^3, che e' il valore di norma per il calcestruzzo
    ARMATO (NTC 2018 Tab. 3.1.I, 25,0 kN/m^3) e quello che il catalogo dei
    materiali gia' porta: il provino di `lab_frame` e' un telaio in cemento
    armato, quindi il valore di prima era quello sbagliato di 1,972%. Deciso
    dall'utente.

    Il prezzo, e va saputo: uno sweep lanciato da oggi su questa base produce
    cartelle diverse da quelle delle ventidue righe gia' registrate. Le righe
    restano valide e leggibili -- ognuna porta la propria configurazione -- ma
    non si rigenerano piu' da qui. `casi/muro.yaml` non e' toccato: e'
    muratura, e 1,8e-9 e' il suo valore giusto.

    **Le due impronte sono cambiate due volte l'08/09/2026**, e per una ragione
    di schema e non di valori: prima il blocco `export` e' entrato in
    `PipelineConfig` con la tolleranza degli insiemi di faccia, che stava in
    `analysis`; poi `analysis` e' uscito dalla configurazione e dai due YAML,
    e con lui il materiale che entrava nell'impronta.
    """
    from meshrec.core.sweep import fingerprint

    percorso = Path(__file__).resolve().parents[1] / "casi" / caso

    assert fingerprint(config.load_config(percorso)) == impronta


def test_i_blocchi_nuovi_stanno_in_pipelineconfig_e_nella_lista_di_esclusione_giusta():
    """I blocchi che viaggiano con la configurazione ma non entrano
    nell'impronta allo stesso modo.

    `wall` e `model` ne restano sempre fuori: nessun asse della Fase 2 li tocca
    e non cambiano il deck.

    L'ultima asserzione e' quella che smentisce: un blocco nelle due liste
    insieme sarebbe una contraddizione, "sempre fuori" e "fuori solo se vuoto".

    `solutore` stava nell'esclusione **secca** ed e' uscito col blocco (mappa
    #161): l'esclusione era secca, quindi la sua uscita non muove le ventidue
    righe -- che e' precisamente la ragione per cui ci stava.

    `regioni` (#135, #141, #136) e' l'unico rimasto nell'esclusione
    **condizionata**: STEP_BLOCKS[11] lo legge e cambia il deck, quindi due
    candidati con regioni diverse sono esperimenti diversi. E' un `dict` che
    nasce `{}` -- cioe' falso -- ed e' per questo che il blocco e' un
    dizionario a chiavi libere e non un modello con campi: un modello
    porterebbe i propri predefiniti, e basta un campo truthy fra quelli perche'
    l'omissione non scatti mai. Misurato il 22/08/2026 sulle 22 righe di
    experiments/muro e experiments/lab_crop: l'esclusione condizionata ne
    cambia 0 su 22, l'inclusione secca 22 su 22.
    """
    from meshrec.core.sweep import BLOCCHI_FUORI_IMPRONTA, BLOCCHI_VUOTI_FUORI_IMPRONTA

    campi = set(PipelineConfig.model_fields)
    assert {"wall", "model"} <= campi
    assert set(BLOCCHI_FUORI_IMPRONTA) == {"run", "wall", "model"}
    assert set(BLOCCHI_VUOTI_FUORI_IMPRONTA) == {"regioni"}
    assert set(BLOCCHI_FUORI_IMPRONTA) <= campi
    assert set(BLOCCHI_VUOTI_FUORI_IMPRONTA) <= campi
    assert not set(BLOCCHI_FUORI_IMPRONTA) & set(BLOCCHI_VUOTI_FUORI_IMPRONTA)


def test_export_ha_la_tolleranza_e_rifiuta_zero(tmp_path):
    """Il blocco dello step 11: un campo solo, con un dominio.

    La tolleranza degli insiemi di faccia era in `analysis`, dove stava
    accanto al materiale e al passo di carico -- cose che il deck nudo non
    scrive piu'. Qui e' sola, ed e' l'unica cosa che lo step 11 comanda.

    Il predefinito si legge da uno YAML che il blocco non lo porta affatto:
    una corsa nata prima di questo blocco deve scrivere il deck di sempre,
    non fermarsi su un campo obbligatorio.

    Mutazione che lo uccide: togliere `gt=0.0` dal campo. Con tolleranza nulla
    `build_node_sets` non trova un solo nodo e la corsa muore a mesh gia'
    costruita, che e' precisamente cio' che la validazione esiste per anticipare.
    """
    percorso = tmp_path / "senza-export.yaml"
    percorso.write_text("input:\n  path: nuvola.ply\n", encoding="utf-8")

    assert config.load_config(percorso).export.set_tolerance_factor == pytest.approx(6.0)

    for cattivo in (0.0, -1.0, float("inf"), float("nan")):
        with pytest.raises(ValidationError):
            config.ExportConfig(set_tolerance_factor=cattivo)


def test_i_sei_nomi_dichiarati_sono_quelli_che_il_deck_fabbrica():
    """La costante e build_node_sets non possono divergere in silenzio.

    Verifica la corrispondenza semantica, non solo l'insieme e l'ordine
    delle chiavi: ogni nodo di controllo sta all'estremo giusto su un solo
    asse, quindi finisce in un solo set atteso. Un controllo che guardasse
    solo `set(insiemi) == set(NOMI_SET_DI_FACCIA)` non lo scoprirebbe.

    Mutazione che lo uccide: scambiare due nomi adiacenti in
    NOMI_SET_DI_FACCIA senza toccare `criteri` in build_node_sets. Le
    chiavi restano le stesse sei nello stesso ordine, ma ciascuna riceve
    il criterio del vicino: BASE prenderebbe i nodi a z massima invece
    che minima, e solo un controllo per contenuto lo nota.
    """
    from meshrec.core import abaqus

    nodi = np.array([
        [5.0, 5.0, 0.0],  # z minima, altrove al centro -> solo BASE
        [5.0, 5.0, 10.0],  # z massima, altrove al centro -> solo TOP
        [0.0, 5.0, 5.0],  # x minima, altrove al centro -> solo FACE_FRONT
        [10.0, 5.0, 5.0],  # x massima, altrove al centro -> solo FACE_BACK
        [5.0, 0.0, 5.0],  # y minima, altrove al centro -> solo SIDE_LEFT
        [5.0, 10.0, 5.0],  # y massima, altrove al centro -> solo SIDE_RIGHT
        [5.0, 5.0, 5.0],  # centro su tutti e tre gli assi: in nessun set
    ])
    atteso = {
        "BASE": [0], "TOP": [1], "FACE_FRONT": [2], "FACE_BACK": [3],
        "SIDE_LEFT": [4], "SIDE_RIGHT": [5],
    }
    insiemi = abaqus.build_node_sets(nodi, 0.01)
    assert tuple(insiemi) == config.NOMI_SET_DI_FACCIA
    for nome, indici in atteso.items():
        assert sorted(insiemi[nome].tolist()) == indici, nome


def test_il_quadratico_e_dichiarabile_ed_e_il_predefinito():
    """Il writer ha imparato a scrivere i dieci nodi (#45), e il rifiuto cade.

    Questo test sostituisce `test_c3d10_non_e_dichiarabile_finche_il_writer_non_lo_gestisce`,
    il cui stesso nome dichiarava di essere temporaneo. Il rifiuto era giusto
    finche' un deck C3D10 sarebbe uscito muto invece che sbagliato; ora la
    connettivita' passa per `volume.TETGEN_A_ABAQUS` e i nodi di lato finiscono
    dove il solutore li aspetta.

    Il predefinito e' il **quadratico**: il manuale CalculiX dice del lineare
    «not suited for structural calculations... the element is too stiff», e la
    suite di verifica ufficiale non contiene un solo deck C3D4 su 610.

    Mutazione che lo uccide: riportare il predefinito a `C3D4`.
    """
    assert config.TetConfig().element == "C3D10"
    assert config.TetConfig(element="C3D4").element == "C3D4", (
        "il lineare resta dichiarabile: serve a misurare quanto la sua rigidita' costi"
    )


def test_un_elemento_che_il_deck_non_sa_scrivere_e_rifiutato_prima_della_corsa():
    """Il rifiuto sta nella validazione della configurazione, non a valle.

    E' la meta' buona di `66b526d`, da non perdere: un tipo sconosciuto
    fermava la corsa **dopo** l'intera tetraedrizzazione, cioe' al punto di
    massimo spreco.
    """
    for sconosciuto in ("C3D20", "C3D10M", "TET4", ""):
        with pytest.raises(ValidationError):
            config.TetConfig(element=sconosciuto)


def test_una_configurazione_si_rilegge_con_e_senza_i_blocchi_che_non_esistono_piu(tmp_path):
    """La cerniera regge in tutte e due i versi, ma non allo stesso modo.

    Un blocco **aggiunto** non puo' rendere illeggibile cio' che e' gia' stato
    scritto: e' la regola dell'omissione che tiene ferme le 22 righe dei
    registri.

    Un blocco **tolto** si divide in due, e la divisione e' la decisione di
    questa PR. `carichi:` e `selettori:` dichiaravano cose che il deck non
    scrive piu': un file che le porta ancora cambierebbe significato in
    silenzio, e viene rifiutato per nome. `solutore:` (mappa #161) e le due
    chiavi laterali dentro `model:` restano **ignorati**: nessun parametro e'
    migrato altrove, non c'e' un «dove sta ora» da dire, e un rifiuto che
    nessun file sul disco puo' innescare sarebbe codice senza consumatore.

    Mutazione che lo uccide, sulla meta' ignorata: `extra="forbid"` su
    `_ModelloBase`. Sull'altra meta': togliere `carichi`/`selettori` da
    `BLOCCHI_RIMOSSI`.
    """
    minima = tmp_path / "minima.yaml"
    minima.write_text("input:\n  path: nuvola.ply\n", encoding="utf-8")
    cfg = config.load_config(minima)
    assert cfg.regioni == {}

    # I blocchi ignorati, come li scrivono le corse gia' fatte.
    vecchia = tmp_path / "vecchia.yaml"
    vecchia.write_text(
        "input:\n  path: nuvola.ply\n"
        "solutore:\n  nome: calculix\n  percorso: null\n"
        "model:\n  lateral_nset: LATO\n  lateral_pressure: 0.05\n",
        encoding="utf-8",
    )
    riletta = config.load_config(vecchia)
    assert not hasattr(riletta, "solutore")
    assert not hasattr(riletta.model, "lateral_nset")
    assert not hasattr(riletta.model, "lateral_pressure")
    assert riletta.regioni == {}

    # I blocchi rifiutati, dallo stesso file di corsa.
    for uscito, corpo in (
        ("carichi", "carichi:\n  spinta:\n    coefficiente: 0.1\n    asse: y\n"),
        ("selettori", "selettori:\n  angolo:\n    tipo: sfera\n    raggio: 5.0\n"),
    ):
        rifiutata = tmp_path / f"con_{uscito}.yaml"
        rifiutata.write_text("input:\n  path: nuvola.ply\n" + corpo, encoding="utf-8")
        with pytest.raises(ValueError) as errore:
            config.load_config(rifiutata)
        assert uscito in str(errore.value)


def test_le_due_chiavi_laterali_a_null_si_rileggono_come_quelle_valorizzate(tmp_path):
    """`null` non e' un valore piu' facile da ignorare degli altri.

    La riletta con valori concreti (`LATO`, `0.05`) e' gia' provata sopra. Il
    `null` merita la sua riga perche' e' cio' che una `config.yaml` scritta
    dall'interfaccia porta quando i due campi restavano vuoti, ed e' la forma
    che arriva davvero dalle corse gia' su disco. Il meccanismo -- `extra`
    ignorato di default su `_ModelloBase` -- e' indifferente al valore, ma
    nessuna riga lo esercitava alla lettera.

    Mutazione che lo uccide: `extra="forbid"` su `_ModelloBase`. `load_config`
    solleva invece di rendere un `ModelConfig` costruito.
    """
    vecchia = tmp_path / "vecchia_null.yaml"
    vecchia.write_text(
        "input:\n  path: nuvola.ply\n"
        "model:\n  lateral_nset: null\n  lateral_pressure: null\n",
        encoding="utf-8",
    )
    riletta = config.load_config(vecchia)
    assert not hasattr(riletta.model, "lateral_nset")
    assert not hasattr(riletta.model, "lateral_pressure")


def _regione(**campi) -> dict:
    return {"membratura": 0, **campi}


def test_le_regioni_vuote_escono_dall_impronta_e_dal_payload():
    """`regioni` nasce `{}`, cioe' falso: e' la ragione per cui il blocco e' un
    dizionario e non un modello con campi.

    Il predicato di `sweep.fingerprint` e' `not any(payload[blocco].values())`:
    un modello con anche un solo campo dal predefinito truthy renderebbe il
    blocco sempre non vuoto, l'omissione non scatterebbe mai, e le ventidue
    righe dei registri si muoverebbero.
    """
    from meshrec.core.sweep import fingerprint

    cfg = config.PipelineConfig(input=config.InputConfig(path="nuvola.ply"))

    assert cfg.regioni == {}
    assert cfg.model_dump(mode="json")["regioni"] == {}
    # Il blocco esce dal payload che l'impronta hasha: e' l'omissione a
    # tenere ferme le ventidue righe, non un caso.
    assert "regioni" not in _payload_dell_impronta(cfg)
    assert fingerprint(cfg) == fingerprint(config.PipelineConfig.model_validate(
        {k: v for k, v in cfg.model_dump(mode="json").items() if k != "regioni"}
    ))


def _payload_dell_impronta(cfg) -> dict:
    """I blocchi che `sweep.fingerprint` hasha davvero, ricostruiti come li' dentro."""
    from meshrec.core.sweep import BLOCCHI_FUORI_IMPRONTA, BLOCCHI_VUOTI_FUORI_IMPRONTA

    payload = cfg.model_dump(mode="json")
    for blocco in BLOCCHI_FUORI_IMPRONTA:
        payload.pop(blocco, None)
    for blocco in BLOCCHI_VUOTI_FUORI_IMPRONTA:
        if not any((payload.get(blocco) or {}).values()):
            payload.pop(blocco, None)
    return payload


def test_una_regione_dichiarata_entra_nell_impronta():
    """L'altra meta' dell'omissione: il blocco che porta qualcosa conta.

    Due candidati con regioni diverse sono esperimenti diversi -- lo step 11
    li legge e il deck cambia -- e senza questa distinzione il secondo
    sovrascriverebbe il primo in silenzio, con la stessa cartella
    `fingerprint(cfg)[:12]`.
    """
    from meshrec.core.sweep import fingerprint

    vuota = config.PipelineConfig(input=config.InputConfig(path="nuvola.ply"))
    piena = config.PipelineConfig(input=config.InputConfig(path="nuvola.ply"), regioni={"pilastro": _regione()})

    assert "regioni" in _payload_dell_impronta(piena)
    assert fingerprint(piena) != fingerprint(vuota)


def test_una_regione_e_la_sola_membratura():
    """Un campo e basta: quale prisma. Il materiale non c'e' piu' -- si assegna
    in Abaqus sull'`*ELSET` che il deck scrive (08/09/2026, PR
    feat/deck-nudo-analisi).

    L'insieme esatto dei campi, non la sola assenza di `materiale`: un campo
    che facesse la stessa cosa sotto un altro nome passerebbe un `not in` e non
    passa questo.

    Mutazione che lo uccide: rimettere un campo qualsiasi su `RegioneConfig`.
    """
    cfg = config.PipelineConfig(
        input=config.InputConfig(path="nuvola.ply"),
        regioni={"trave": _regione()},
    )

    assert cfg.regioni["trave"].membratura == 0
    assert set(config.RegioneConfig.model_fields) == {"membratura"}


def test_una_regione_che_dichiara_ancora_un_materiale_e_rifiutata_per_nome(tmp_path):
    """Ingresso degenere: un `config.yaml` scritto prima del 08/09/2026.

    Senza il validatore la chiave non e' un errore: pydantic ignora le chiavi
    in piu', la corsa parte e il materiale dichiarato non arriva in nessun
    deck. Un file che cambia significato in silenzio e' il difetto preciso che
    il rifiuto nominato esiste per impedire.

    Mutazione che lo uccide: togliere il validatore `before` da
    `RegioneConfig`. La `load_config` torna una `PipelineConfig` buona.
    """
    percorso = tmp_path / "config.yaml"
    percorso.write_text(
        "input:\n  path: nuvola.ply\n"
        "regioni:\n"
        "  pilastro:\n"
        "    membratura: 0\n"
        "    materiale:\n"
        "      material:\n"
        "        name: CLS\n        young: 31476.0\n"
        "        poisson: 0.2\n        density: 2.5e-9\n"
        "      provenienza: a_mano\n"
        "      norma: NTC 2018 Tab. 4.1.I\n",
        encoding="utf-8",
    )

    with pytest.raises(ValidationError) as rifiuto:
        config.load_config(percorso)

    detto = str(rifiuto.value)
    assert "materiale" in detto
    assert "08/09/2026" in detto
    # Il percorso dice **quale** regione: con dodici regioni dichiarate, un
    # messaggio senza il nome manda a cercare a mano.
    percorsi = [".".join(str(v) for v in errore["loc"]) for errore in rifiuto.value.errors()]
    assert any(p.startswith("regioni.pilastro") for p in percorsi), percorsi


def test_due_regioni_che_differiscono_solo_per_maiuscole_sono_rifiutate():
    """Misurata in docs/fase-6-cantiere/sonda-caso-nomi/: `ccx` risolve i nomi di insieme
    senza distinguere le maiuscole, quindi due chiavi distinte nel dizionario
    python sono un solo nome nel deck.
    """
    with pytest.raises(ValidationError, match="maiuscole") as rifiuto:
        config.PipelineConfig(
            input=config.InputConfig(path="nuvola.ply"),
            regioni={"pilastro": _regione(), "PILASTRO": _regione(membratura=1)},
        )
    assert "le regioni" in str(rifiuto.value)


@pytest.mark.parametrize("nome", ["ALL_WALL", "all_wall", "All_Wall"])
def test_una_regione_che_collide_con_lelset_fabbricato_e_rifiutata(nome):
    """`ALL_WALL` e' l'unico `*ELSET` che il deck fabbrica da se'
    (`abaqus.write_inp`, parametro `elset`, scritto in `*ELEMENT` e in
    `*SOLID SECTION`): e' l'insieme che le regioni partizionano, e una regione
    omonima farebbe prendere alla `*SOLID SECTION` la partizione sbagliata --
    il muro intero riceverebbe il materiale di una regione.

    Mutazione che lo uccide: rimettere `NOMI_SET_DI_FACCIA` come lista
    confrontata anche per gli `*ELSET`. Tutte e tre le varianti passano.
    """
    with pytest.raises(ValidationError, match="collide") as rifiuto:
        config.PipelineConfig(
            input=config.InputConfig(path="nuvola.ply"),
            regioni={nome: _regione()},
        )
    # Il messaggio si legge a video, in `/api/config`: «il regione» no.
    assert "la regione" in str(rifiuto.value)
    assert "*ELSET" in str(rifiuto.value)
    assert "ALL_WALL" in str(rifiuto.value)


@pytest.mark.parametrize("nome", ["BASE", "top", "Side_Left"])
def test_una_regione_puo_chiamarsi_come_un_set_di_faccia(nome):
    """I sei di faccia sono `*NSET` e una regione e' un `*ELSET`: nel deck sono
    due spazi di nomi distinti, e rifiutare qui il nome innocuo mentre passava
    `ALL_WALL` era il controllo esattamente rovesciato.

    Sta accanto al test del rifiuto apposta: senza, «confronta con i nomi
    fabbricati del proprio tipo di set» e «confronta con tutti i nomi
    fabbricati» sarebbero indistinguibili.
    """
    cfg = config.PipelineConfig(
        input=config.InputConfig(path="nuvola.ply"),
        regioni={nome: _regione()},
    )
    assert nome in cfg.regioni


@pytest.mark.parametrize("nome", ["", "pi lastro", "regione!"])
def test_un_nome_di_regione_con_spazio_o_simbolo_e_rifiutato(nome):
    """Il nome di una regione finisce interpolato in un deck ascii, come
    `*ELSET`, e otto rami lo leggeranno.

    Mutazione che lo uccide: ritipare `regioni` da `dict[NomeSet, ...]` a
    `dict[str, ...]`. Il rifiuto oggi viene dal tipo e da nessuna prova.
    """
    with pytest.raises(ValidationError):
        config.PipelineConfig(
            input=config.InputConfig(path="nuvola.ply"),
            regioni={nome: _regione()},
        )


def test_una_membratura_negativa_e_rifiutata_dalla_configurazione():
    """`membratura` e' un indice nel prior: negativo non e' un indice.

    Il tetto -- quante membrature il prior ha trovato davvero -- **non** e'
    verificabile qui: `12_wall.json` non e' visibile alla configurazione, che
    nasce prima che lo step 12 giri. Il rifiuto dell'indice fuori intervallo
    spetta a chi legge il prior, e questa configurazione non puo' fingere di
    saperlo.
    """
    with pytest.raises(ValidationError):
        config.RegioneConfig.model_validate(_regione(membratura=-1))
    assert config.RegioneConfig.model_validate(_regione(membratura=99)).membratura == 99


def test_le_regioni_sopravvivono_al_giro_su_disco(tmp_path):
    percorso = tmp_path / "config.yaml"
    cfg = config.PipelineConfig(
        input=config.InputConfig(path="nuvola.ply"),
        regioni={"pilastro": _regione()},
    )
    config.save_config(cfg, percorso)

    riletta = config.load_config(percorso)

    assert riletta.model_dump() == cfg.model_dump()


def test_una_corsa_di_pipeline_finisce_allo_step_11_e_il_tetto_e_il_dodici():
    """Il predefinito segue il perimetro del prodotto, non il tetto.

    Il prodotto va dalla nuvola al deck `.inp` e si chiude li', mentre il prior
    geometrico dello step 12 misura la scansione e sta fuori dal perimetro: il
    predefinito e' 11.

    Il tetto e' 12 da quando il solutore e' uscito con la mappa #161. Chi
    chiede il prior esplicitamente lo ottiene ancora: la capacita' non si
    perde, smette solo di essere cio' che accade senza chiederlo.

    `run` sta in BLOCCHI_FUORI_IMPRONTA, quindi questo cambio non puo' muovere
    l'impronta delle ventidue righe: lo verificano i due test dell'impronta,
    con i loro numeri intatti.

    Mutazione che lo uccide: riportare il predefinito a 12. Una corsa senza
    argomenti tornerebbe a calcolare il prior, che i documenti dichiarano fuori
    perimetro.
    """
    predefinito = config.RunConfig()

    assert predefinito.to_step == 11
    assert config.RunConfig(to_step=12).to_step == 12
    with pytest.raises(ValidationError):
        config.RunConfig(to_step=13)
    # from_step e to_step uguali eseguono soltanto quello step.
    solo_il_dodici = config.RunConfig(from_step=9, to_step=9)
    assert solo_il_dodici.from_step == solo_il_dodici.to_step == 9

    descrizione = config.RunConfig.model_fields["to_step"].description
    assert "il predefinito coincide con esso" not in descrizione, (
        "la descrizione afferma ancora una coincidenza col tetto che non c'e' piu'"
    )


def test_pipeline_config_non_ha_piu_carichi_ne_selettori():
    """Dalla PR 1 del deck nudo la configurazione non porta piu' carichi,
    selettori ne' pressione laterale: le classi stesse escono dal modulo."""
    campi = set(config.PipelineConfig.model_fields)

    assert "carichi" not in campi
    assert "selettori" not in campi
    assert not hasattr(config, "CarichiConfig")
    assert not hasattr(config, "Selettore")
    assert "lateral_pressure" not in config.ModelConfig.model_fields


def _yaml_vecchia(tmp_path: Path, coda: str) -> Path:
    """Un `config.yaml` gia' su disco: la nuvola, piu' i blocchi usciti."""
    percorso = tmp_path / "vecchia.yaml"
    percorso.write_text("input:\n  path: nuvola.ply\n" + coda, encoding="utf-8")
    return percorso


BLOCCO_ANALYSIS = (
    "analysis:\n"
    "  material:\n    name: MURATURA\n    young: 1500.0\n"
    "    poisson: 0.2\n    density: 1.8e-09\n"
    "  gravity: 9810.0\n  fixed_nset: BASE\n  step_name: GRAVITA\n"
    "  set_tolerance_factor: 6.0\n"
)
BLOCCO_CARICHI = "carichi:\n  spinta:\n    coefficiente: 0.1\n    asse: y\n"


def test_uno_yaml_con_analysis_e_rifiutato_per_nome(tmp_path):
    """Un blocco tolto non si ignora: cambierebbe significato in silenzio.

    `analysis` dichiarava il materiale, il vincolo e la gravita'. Col deck
    nudo quei tre non li scrive piu' nessuno, e un `config.yaml` che li porta
    ancora descrive una corsa che il programma non esegue piu': ignorarlo
    darebbe un deck diverso da quello che il file dichiara, senza un segnale.
    Il rifiuto nomina il blocco, la data e dove il solo parametro sopravvissuto
    e' andato a stare.

    Mutazione che lo uccide: togliere `analysis` da `BLOCCHI_RIMOSSI`.
    """
    with pytest.raises(ValueError) as rifiuto:
        config.load_config(_yaml_vecchia(tmp_path, BLOCCO_ANALYSIS))

    messaggio = str(rifiuto.value)
    assert "analysis" in messaggio
    assert "08/09/2026" in messaggio
    assert "set_tolerance_factor" in messaggio
    assert "export" in messaggio


def test_analysis_a_null_e_rifiutato_quanto_analysis_valorizzato(tmp_path):
    """Conta la chiave, non il valore.

    `analysis: null` e' la forma che ogni corsa nata dall'interfaccia porta su
    disco -- il materiale restava assente finche' non lo dichiarava chi
    analizza. E' il caso piu' frequente, non il piu' raro, e un rifiuto che
    guardasse il valore lo lascerebbe passare.

    Mutazione che lo uccide: `if dati.get(blocco) is not None` al posto di
    `if blocco in dati`.
    """
    with pytest.raises(ValueError) as rifiuto:
        config.load_config(_yaml_vecchia(tmp_path, "analysis: null\n"))

    assert "analysis" in str(rifiuto.value)


@pytest.mark.parametrize("blocco", ["carichi", "selettori"])
def test_i_blocchi_della_prima_pr_del_deck_nudo_sono_rifiutati_citando_la_pr(tmp_path, blocco):
    """`carichi` e `selettori` erano gia' usciti col deck nudo, ma erano ignorati.

    Ignorati valeva finche' nessun altro blocco veniva rifiutato: adesso che il
    rifiuto nominato esiste, tenerli fuori direbbe a chi ha entrambi i blocchi
    che uno solo dei due e' un problema.

    Mutazione che lo uccide: togliere il blocco da `BLOCCHI_RIMOSSI`.
    """
    with pytest.raises(ValueError) as rifiuto:
        config.load_config(_yaml_vecchia(tmp_path, f"{blocco}:\n  voce: {{}}\n"))

    messaggio = str(rifiuto.value)
    assert blocco in messaggio
    assert "#190" in messaggio


def test_due_blocchi_usciti_danno_un_rifiuto_solo_che_li_nomina_entrambi(tmp_path):
    """`runs/geoandgeo-lab/config.yaml` porta `analysis:` e `carichi:`.

    Un rifiuto per blocco costa una corsa a blocco: si toglie il primo, si
    rilancia, si scopre il secondo. Il validatore li raccoglie tutti e li
    nomina in un messaggio solo.

    Mutazione che lo uccide: `raise` dentro il ciclo invece che dopo.
    """
    with pytest.raises(ValueError) as rifiuto:
        config.load_config(_yaml_vecchia(tmp_path, BLOCCO_ANALYSIS + BLOCCO_CARICHI))

    messaggio = str(rifiuto.value)
    assert "analysis" in messaggio
    assert "carichi" in messaggio
    # Un rifiuto solo, non due: e' pydantic a contarli.
    assert rifiuto.value.error_count() == 1


def test_tre_blocchi_usciti_danno_un_rifiuto_solo_e_non_nominano_un_blocco_vivo(tmp_path):
    """`analysis`, `carichi` e `selettori` sono tre voci di `BLOCCHI_RIMOSSI`:
    un `config.yaml` che porta tutti e tre, piu' un blocco mai esistito
    (`solutore`), riceve un rifiuto solo che nomina i tre tolti e non
    `solutore` -- il validatore raccoglie solo cio' che sta in
    `BLOCCHI_RIMOSSI`, non ogni chiave sconosciuta.

    Mutazione che lo uccide: iterare `dati` invece di `BLOCCHI_RIMOSSI.items()`.
    """
    with pytest.raises(ValueError) as rifiuto:
        config.load_config(
            _yaml_vecchia(
                tmp_path, BLOCCO_ANALYSIS + BLOCCO_CARICHI + "selettori:\n  voce: {}\n" + "solutore:\n  voce: {}\n"
            )
        )

    # `str(rifiuto.value)` di pydantic riecheggia l'input grezzo nel
    # `input_value=...` del rendering di debug, "solutore" incluso: il
    # messaggio da controllare e' quello composto dal validatore, non
    # quel rendering.
    messaggio = rifiuto.value.errors()[0]["msg"]
    assert "analysis" in messaggio
    assert "carichi" in messaggio
    assert "selettori" in messaggio
    assert "solutore" not in messaggio
    assert rifiuto.value.error_count() == 1


def test_la_configurazione_non_esporta_piu_i_simboli_dell_analisi():
    """Col deck nudo il materiale, la gravita' e il passo di carico escono dal modulo.

    Non basta togliere il campo da `PipelineConfig`: le classi lasciate nel
    modulo si ricostruiscono a mano e tornano dentro per un'altra porta.

    Mutazione che lo uccide: rimettere `Material` o `AnalysisConfig` in
    `config.py`.
    """
    assert "analysis" not in config.PipelineConfig.model_fields
    assert not hasattr(config, "Material")
    assert not hasattr(config, "AnalysisConfig")
    assert not hasattr(config, "GRAVITY_MM_S2")
    assert not hasattr(config.PipelineConfig, "analisi_dichiarata")


# Percorsi fra Windows e macOS (13/09/2026). Mario apre le stesse corse sulle due
# macchine: un `\` scritto da Windows, su macOS, e' un carattere del nome.


@pytest.mark.parametrize(
    ("scritto", "atteso"),
    [
        (r"runs\geoandgeo\01_cloud.ply", "runs/geoandgeo/01_cloud.ply"),
        (r"runs\città vecchia\nuvola 01.ply", "runs/città vecchia/nuvola 01.ply"),
        (r"C:\Users\mario\nuvola.ply", "C:/Users/mario/nuvola.ply"),
    ],
)
def test_la_configurazione_salvata_non_porta_separatori_di_windows(tmp_path, scritto, atteso):
    from pathlib import PureWindowsPath

    for valore in (scritto, PureWindowsPath(scritto)):
        cfg = PipelineConfig(
            input=config.InputConfig(path=valore),
            run=config.RunConfig(out_dir=type(valore)(r"runs\città vecchia")),
        )
        percorso = tmp_path / "config.yaml"
        config.save_config(cfg, percorso)

        testo = percorso.read_text(encoding="utf-8")
        assert "\\" not in testo
        dati = yaml.safe_load(testo)
        assert dati["input"]["path"] == atteso
        assert dati["run"]["out_dir"] == "runs/città vecchia"


def test_un_percorso_relativo_scritto_da_windows_apre_il_file_su_ogni_piattaforma(
    tmp_path, monkeypatch
):
    nuvola = tmp_path / "runs" / "geoandgeo" / "01_cloud.ply"
    nuvola.parent.mkdir(parents=True)
    nuvola.write_text("ply\n", encoding="utf-8")
    percorso = tmp_path / "config.yaml"
    percorso.write_text("input:\n  path: runs\\geoandgeo\\01_cloud.ply\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    cfg = config.load_config(percorso)

    assert cfg.input.path.is_file()
    assert cfg.input.path.resolve() == nuvola.resolve()


def test_un_percorso_assoluto_di_windows_su_un_altra_macchina_e_un_file_assente(tmp_path):
    from meshrec.core import io

    percorso = tmp_path / "config.yaml"
    percorso.write_text("input:\n  path: C:\\Users\\mario\\nuvola.ply\n", encoding="utf-8")

    cfg = config.load_config(percorso)

    with pytest.raises(ValueError, match="file assente"):
        io.read_cloud(cfg.input.path)


def test_un_percorso_unc_resta_unc_dopo_salvataggio_e_ricarica(tmp_path):
    from pathlib import PureWindowsPath

    unc = PureWindowsPath(r"\\server\share\x.ply")
    percorso = tmp_path / "config.yaml"
    config.save_config(PipelineConfig(input=config.InputConfig(path=str(unc))), percorso)

    riletto = PureWindowsPath(str(config.load_config(percorso).input.path))

    assert riletto == unc
    assert riletto.drive == r"\\server\share"


def test_l_impronta_non_dipende_dal_separatore():
    from meshrec.core import steps
    from meshrec.core.sweep import fingerprint

    windows = PipelineConfig(input=config.InputConfig(path=r"..\Nuvole di punti\muro.ply"))
    posix = PipelineConfig(input=config.InputConfig(path="../Nuvole di punti/muro.ply"))

    assert fingerprint(windows) == fingerprint(posix)
    assert steps.step_fingerprints(windows) == steps.step_fingerprints(posix)
