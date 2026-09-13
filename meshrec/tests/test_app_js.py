"""L'interfaccia dalla parte del browser: le funzioni vere di `app.js`, eseguite.

Due famiglie di controlli, e la seconda esiste per il limite della prima.

**Le mosse.** Lo stesso difetto — l'annuncio del rifiuto non garantito — e'
tornato tre volte per tre strade diverse: `hidden` sulla regione `role="alert"`,
una regola di stile che la nascondeva, e `replaceChildren()` su `#dettaglio` che
la distruggeva a ogni apertura di pannello. La quarta strada e' sempre la stessa
mossa: rimettere la regione sotto qualcosa che la puo' distruggere o generare.
Quei controlli guardano la mossa, non il sintomo.

**Il comportamento.** Un controllo che cerca una sottostringa nel sorgente passa
anche quando la logica e' capovolta, e su questo ramo e' successo: una guardia
resa inerte con `|| true` lasciava la sottostringa al suo posto e il controllo
restava verde mentre il difetto era riaperto. Percio' tutto cio' che e' logica —
il marchio dello step, il tetto del registro, il valore che dai tasti finisce
nella configurazione, la didascalia del ritaglio — si prova **eseguendo le
funzioni vere ritagliate da `app.js`** su un DOM finto, con `node`. Il DOM finto
non e' un browser: e' il minimo che quelle funzioni toccano, e sta qui sotto.

Non stanno in `tests/test_server.py` per la stessa ragione per cui non ci sta
`test_stile.py`: quel file e' in mano ad altri, e metterlo nell'indice
porterebbe nel commit righe che non sono mie.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from meshrec.app.server import UI_DIR, create_app
from meshrec.core import report
from meshrec.core.config import InputConfig, PipelineConfig, save_config

# Il server risponde solo a un nome locale (middleware
# `solo_dal_calcolatore_locale` in server.py, contro il DNS rebinding). Il
# predefinito di TestClient e' `http://testserver`, che quel middleware rifiuta
# con 403 -- ed e' giusto: i banchi devono parlare col server come ci parla il
# browser vero.
BASE_LOCALE = "http://127.0.0.1"


def _markup() -> str:
    return (UI_DIR / "index.html").read_text(encoding="utf-8")


def _modulo() -> str:
    return (UI_DIR / "app.js").read_text(encoding="utf-8")


def _foglio() -> str:
    return (UI_DIR / "stile.css").read_text(encoding="utf-8")


def _senza_commenti_html(markup: str) -> str:
    """Il markup senza i commenti. Un commento che nomina un attributo non e'
    quell'attributo: schermato dietro `<!-- id="errore" role="alert" -->` scritto
    sopra la regione vera, il primo controllo di questo file restava verde
    mentre la regione perdeva il proprio ruolo. Provato, era verde davvero."""
    return re.sub(r"<!--.*?-->", "", markup, flags=re.DOTALL)


def _senza_commenti_js(modulo: str) -> str:
    """Il modulo senza le righe di commento. Serve al contrario: `role="alert"`
    compare per iscritto nei commenti che spiegano perche' la regione sta dove
    sta, e cercare la forma di codice dentro la spiegazione la vieterebbe."""
    return "\n".join(r for r in modulo.splitlines() if not r.lstrip().startswith("//"))


def _elemento(markup: str, identificativo: str) -> str:
    """Il tag di apertura dell'elemento con quell'id, non la prima riga che ne
    contiene il nome."""
    trovato = re.search(rf"<[a-z]+[^>]*\bid=\"{identificativo}\"[^>]*>", markup)
    assert trovato is not None, f"nessun elemento con id={identificativo} nel markup"
    return trovato.group(0)


def _sorgente_di(nome: str, testo: str) -> str:
    """Il corpo di una funzione di primo livello, dalla firma alla graffa che la
    chiude in prima colonna. I moduli dell'interfaccia non sono importabili da
    qui (importano percorsi serviti dal server), quindi si estrae il testo.

    `async` va tenuto: senza, il testo estratto resta leggibile ma non e' piu'
    eseguibile.
    """
    corpo = testo.split(f"function {nome}(", 1)[1]
    prefisso = "async " if f"async function {nome}(" in testo else ""
    return f"{prefisso}function {nome}(" + corpo.split("\n}\n", 1)[0] + "\n}"


def _costruzione_pannello_modello() -> str:
    """`aggiornaModello` non e' piu' una funzione di primo livello di app.js:
    vive dentro la factory `creaPannelloModello` di modello.js, con il proprio
    contatore (`apriModello`) chiuso li' dentro e non piu' estraibile da solo.
    Un banco che chiede `aggiornaModello` si porta dietro l'importazione vera
    e la costruzione, con le dipendenze che ogni richiesta di `aggiornaModello`
    porta gia' con se' (`superata`, `serverMuto`, `corpoLetto`,
    `valoreDellaMetrica` -- sempre nella stessa lista, vedi `_COLONNA`) piu'
    quelle che `_DOM` dichiara per tutti (`elemento`, `ETICHETTE`,
    `STEP_DEL_PRIOR`, `fetch`).

    `fetch` passa per un involucro apposta: i banchi riassegnano
    `globalThis.fetch` DOPO questa riga (per simulare una risposta), e una
    presa diretta del legame lo congelerebbe al mutismo predefinito di `_DOM`.
    """
    percorso = (UI_DIR / "modello.js").resolve().as_uri()
    return (
        f"import {{ creaPannelloModello }} from {percorso!r};\n"
        "const { aggiornaModello } = creaPannelloModello({\n"
        "  fetch: (...args) => fetch(...args), elemento, superata, serverMuto,\n"
        "  corpoLetto, valoreDellaMetrica, ETICHETTE, STEP_DEL_PRIOR,\n"
        "});\n"
    )


def _funzioni(*nomi: str) -> str:
    """Le funzioni chieste, una volta sola ciascuna e nell'ordine dato.

    Senza la deduplica un banco che elencasse `corpoLetto` per conto proprio e
    poi anche `*_COLONNA`, che se lo porta dietro, otterrebbe due `function
    corpoLetto` nello stesso modulo: `node` si ferma su un SyntaxError, cioe' un
    rosso che non parla del comportamento. Una funzione elencata due volte e' la
    stessa funzione, non due.

    Cerca prima in app.js e, se non la trova li', in modello.js: dopo la
    seconda mappa alcune di queste funzioni (`fronteDelloStato`,
    `chiaveDelFronte`, `righeDelModello`) sono uscite di li'. `aggiornaModello`
    e' un caso a parte, perche' non e' piu' una funzione di primo livello da
    nessuna parte: vedi `_costruzione_pannello_modello`.
    """
    testo_app = _modulo()
    testo_modello = _modulo_modello()
    pezzi = []
    for nome in dict.fromkeys(nomi):
        if nome == "aggiornaModello":
            pezzi.append(_costruzione_pannello_modello())
        elif f"function {nome}(" in testo_app:
            pezzi.append(_sorgente_di(nome, testo_app))
        else:
            pezzi.append(_sorgente_di(nome, testo_modello))
    return "\n".join(pezzi)


# Le funzioni che disegnano la colonna degli step, in un elenco solo.
#
# Un banco che ne dimenticasse una non fallirebbe sul comportamento ma su un
# ReferenceError, cioe' con un rosso che non insegna niente: elencate qui una
# volta, non c'e' un elenco per banco da tenere allineato.
_COLONNA = (
    "segnaStepAperto", "nuovaRiga",
    # La frase di stato del pannello aperto: disegnaStep la riscrive se cambia.
    "fraseDelloStato",
    "superata", "serverMuto", "ragioneDelRifiuto", "corpoLetto",
    # Il pannello del modello, che `disegnaStep` chiama in coda: senza queste
    # tre il banco della colonna cade su un ReferenceError. Nel banco non
    # c'e' server, quindi il pannello percorre il proprio ramo di rifiuto --
    # ed e' cio' che deve fare quando /api/metrics non risponde.
    "fronteDelloStato", "chiaveDelFronte", "righeDelModello", "valoreDellaMetrica",
    "aggiornaModello",
    "disegnaStep",
)


def _importa(percorso: Path, corpo: str) -> str:
    """Esegue con `node` un'importazione ES vera di un modulo dell'interfaccia
    (etichette.js, modello.js) e restituisce lo stdout. A differenza di
    `_sorgente_di`/`_costante`, che ritagliano testo da un modulo che non si
    puo' importare cosi' com'e' (app.js porta percorsi assoluti dal server),
    questi moduli nuovi non hanno quel problema: si possono importare per
    davvero, e importarli e' anche il banco che li tiene valutabili da soli."""
    esito = subprocess.run(
        [_node(), "--input-type=module", "-e", f"import * as modulo from {percorso.resolve().as_uri()!r};\n" + corpo],
        capture_output=True, text=True, encoding="utf-8",
    )
    assert esito.returncode == 0, esito.stderr
    return esito.stdout


def _etichette_metriche() -> dict:
    """La tabella `ETICHETTE_METRICHE` di `etichette.js`, letta importando
    davvero il modulo: una copia scritta qui lascerebbe che banco e modulo
    divergano in silenzio, ed e' proprio la tabella su cui il banco deve dire
    qualcosa."""
    return json.loads(_importa(UI_DIR / "etichette.js", "console.log(JSON.stringify(modulo.ETICHETTE_METRICHE));"))


def _costante(nome: str) -> str:
    """La riga di una costante di modulo, presa dal sorgente vero.

    Le costanti non sono funzioni e `_sorgente_di` non le vede. Dichiararne una
    copia nel banco lascerebbe che banco e modulo divergano in silenzio, che e'
    la famiglia di difetti per cui questo file esegue invece di leggere.
    """
    trovato = re.search(rf"^const {nome} = .*;$", _modulo(), flags=re.MULTILINE)
    assert trovato is not None, f"nessuna costante {nome} in app.js"
    return trovato.group(0)


def _tabella_del_modello() -> str:
    """Le costanti del pannello del modello, prese dal sorgente vero: da `const
    NON_MISURATO` alla riga prima di `righeDelModello`, cioe' NON_MISURATO,
    valoreDelModello, RIGHE_DELLA_SUPERFICIE e RIGHE_DEL_MODELLO.

    Non passa da `_costante`, che vede una riga sola. Le due ancore si
    controllano prima di tagliare: un'ancora sparita darebbe un taglio vuoto o
    lungo mezzo modulo, e il banco fallirebbe dicendo qualcosa sul
    comportamento invece che sull'estrazione che si e' rotta.

    Sorgente `modello.js` e non piu' `app.js`: la tratta del pannello del
    modello ci e' uscita.
    """
    inizio, fine = "const NON_MISURATO = ", "\n// Le righe del pannello"
    testo = _modulo_modello()
    assert inizio in testo, f"ancora d'inizio assente: {inizio}"
    coda = testo.split(inizio, 1)[1]
    assert fine in coda, f"ancora di fine assente: {fine}"
    return inizio + coda.split(fine, 1)[0] + "\n"


def _modulo_modello() -> str:
    """Il sorgente di `modello.js`. Gemella di `_modulo()` e `_modulo_viewport()`."""
    return (UI_DIR / "modello.js").read_text(encoding="utf-8")

def _costante_viewport(nome: str) -> str:
    """La riga di una costante di `viewport.js`, presa dal sorgente vero.

    Gemella di `_costante`, che legge `app.js`, e per la stessa ragione: una
    copia scritta nel banco lascerebbe che banco e modulo divergano in silenzio.
    Qui pesa il doppio -- la costante e' la rampa dei colori, e un banco che
    provasse una rampa diversa da quella dipinta direbbe verde su una legenda
    sbagliata.
    """
    trovato = re.search(rf"^export const {nome} = .*;$", _modulo_viewport(), flags=re.MULTILINE)
    assert trovato is not None, f"nessuna costante {nome} in viewport.js"
    return trovato.group(0)


def _modulo_viewport() -> str:
    """Il sorgente di `viewport.js`. Gemella di `_modulo()`, che legge `app.js`.

    Serve da quando le decisioni numeriche del campo di colore vivono li': la
    scala e l'amplificazione sono logica, e la logica di questo progetto si
    prova eseguendola.
    """
    return (UI_DIR / "viewport.js").read_text(encoding="utf-8")


def _funzioni_viewport(*nomi: str) -> str:
    testo = _modulo_viewport()
    return "\n".join(_sorgente_di(nome, testo) for nome in nomi)


def _node() -> str:
    percorso = shutil.which("node")
    if percorso is None:
        pytest.skip("node non installato: la logica resta verificata a mano")
    return percorso


def _esegui(tmp_path: Path, sorgente: str) -> str:
    """Il banco: scrive il modulo di prova e lo esegue. Rosso e' l'assert di
    `node` che salta, e il suo messaggio arriva qui dentro."""
    prova = tmp_path / "prova.mjs"
    prova.write_text(sorgente, encoding="utf-8")
    esito = subprocess.run([_node(), str(prova)], capture_output=True, text=True, encoding="utf-8")
    assert esito.returncode == 0, esito.stderr
    return esito.stdout


# Il minimo di DOM che le funzioni vere toccano: nodi, figli, classi, attributi,
# dataset, e le due proprieta' di scorrimento del registro. Non e' un browser e
# non pretende di esserlo — quello che si sta provando e' la logica del modulo,
# non il motore che ci sta sotto.
_DOM = """import assert from 'node:assert/strict';

class Elemento {
  constructor(tag) {
    this.tag = tag;
    this.figli = [];
    this.className = "";
    this.dataset = {};
    // Il modulo ci scrive il gradiente della chiave della scala. Un oggetto
    // nudo basta: qui non si prova il rendering, si prova che il valore scritto
    // venga dalla costante che colora i vertici e non da una seconda copia.
    this.style = {};
    this.attributi = {};
    this.testo = "";
    this.scrollTop = 0;
    this.padre = null;
    this.gestori = {};
    this.classList = {
      add: (nome) => this.classList.toggle(nome, true),
      toggle: (nome, attivo) => {
        const classi = new Set(this.className.split(" ").filter(Boolean));
        if (attivo) classi.add(nome); else classi.delete(nome);
        this.className = [...classi].join(" ");
      },
    };
  }
  addEventListener(tipo, gestore) { (this.gestori[tipo] ??= []).push(gestore); }
  // «Riporta» scatena `change` sul comando invece di scrivere per conto
  // proprio: il gesto passa dal gestore che gia' salva, e il banco deve poter
  // percorrere quella stessa strada.
  dispatchEvent(evento) { return this.scatena(evento.type); }
  // Il salvataggio dell'immagine fabbrica un <a download> e lo clicca: e' il
  // browser che scrive il file, e il banco deve poter vedere quel clic.
  click() {
    this.cliccato = true;
    // Il padre AL MOMENTO del clic: un <a download> che non sta nell'albero
    // Firefox lo ignora in silenzio, e dopo il clic il modulo lo toglie.
    this.padreAlClic = this.padre;
    return this.scatena("click");
  }
  // Il gestore vero, eseguito: e' cio' che mancava al banco. `await` perche' il
  // gestore del campo e' asincrono, e senza aspettarlo il controllo guarderebbe
  // lo stato di prima della risposta.
  async scatena(tipo) {
    // Un comando spento non riceve il clic, e il banco lo deve modellare: nel
    // browser il gesto su un `disabled` non arriva a nessun gestore. Senza
    // questa riga il banco dichiarava verde un doppio clic che il browser non
    // consegna, e rosso un codice che si difende proprio spegnendo il bottone.
    if (this.disabled && tipo === "click") return;
    for (const gestore of this.gestori[tipo] ?? []) await gestore();
  }
  get children() { return this.figli; }
  get childElementCount() { return this.figli.length; }
  get firstElementChild() { return this.figli[0] ?? null; }
  get lastElementChild() { return this.figli[this.figli.length - 1] ?? null; }
  get scrollHeight() { return this.figli.length; }
  // Il proprio testo PIU' quello dei figli, come il DOM vero. Tornava il solo
  // `this.testo`, e quella differenza non era innocua: `marcaLeMetricheCambiate` appende
  // dentro il `dd` il valore di prima e poi rilegge `textContent` al giro
  // dopo, quindi il banco non poteva vedere il difetto in cui la rilettura
  // torna i due numeri attaccati e ogni riga risulta cambiata per sempre. Una
  // finta DOM piu' comoda del vero e' una finta DOM che nasconde una classe di
  // difetti.
  get textContent() { return this.testo + this.figli.map((f) => f.textContent).join(""); }
  set textContent(valore) { this.testo = String(valore); }
  append(...nodi) { for (const nodo of nodi) { nodo.padre = this; this.figli.push(nodo); } }
  replaceChildren(...nodi) { this.figli = []; this.append(...nodi); }
  remove() { this.padre.figli.splice(this.padre.figli.indexOf(this), 1); }
  // Il fuoco non e' un effetto grafico: e' l'unico canale con cui chi naviga da
  // sola tastiera sa dove si trova dopo che una schermata ha nascosto quella che
  // teneva il cursore. Il banco lo registra invece di disegnarlo.
  focus() { aFuoco = this; }
  setAttribute(nome, valore) { this.attributi[nome] = String(valore); }
  removeAttribute(nome) { delete this.attributi[nome]; }
  getAttribute(nome) { return this.attributi[nome] ?? null; }
  discendenti() { return this.figli.flatMap((f) => [f, ...f.discendenti()]); }
  querySelectorAll(selettore) {
    const classe = selettore.slice(1);
    return this.discendenti().filter((e) => e.className.split(" ").includes(classe));
  }
}

let aFuoco = null;
const radice = new Elemento("body");
const perId = new Map();
const document = {
  createElement: (tag) => new Elemento(tag),
  getElementById(id) {
    if (!perId.has(id)) {
      const nodo = new Elemento("div");
      radice.append(nodo);
      perId.set(id, nodo);
    }
    return perId.get(id);
  },
  querySelectorAll: (selettore) => radice.querySelectorAll(selettore),
  // La radice del DOM finto e' il <body>: il salvataggio dell'immagine ci
  // attacca il proprio collegamento prima di cliccarlo.
  body: radice,
};
// Globale davvero, non solo un legame di questo modulo di prova: modello.js
// si importa per davvero (e' un modulo a se', non un ritaglio incollato qui
// dentro), e un `document` bare al suo interno lo trova solo passando da
// `globalThis`.
globalThis.document = document;

// Il costruttore che il browser porta per <option>, e che `pannelloCampo` usa.
// Reso come un <option> del DOM finto e non come un oggetto a parte: cosi' un
// menu costruito con `new Option` si legge come tutti gli altri nodi.
globalThis.Option = function (testo, valore) {
  const opzione = document.createElement("option");
  opzione.textContent = testo;
  opzione.value = valore;
  return opzione;
};

const ETICHETTE = {};
// Vuoti apposta, come ETICHETTE: chi prova i nomi se li scrive dentro. Una
// chiave assente non prende una frase inventata, ed e' proprio la regola che
// intestazioneDelloStep deve rispettare.
const PROPOSITI = {};
const rigaErrore = document.getElementById("errore");
let stepAperto = null;
// Le due variabili di modulo che le funzioni estratte leggono e scrivono:
// senza, il banco proverebbe una copia che non e' quella del modulo.
let configurazione = null;
let generazione = 0;
// Lo stato degli step che `disegnaStep` scrive e `passoDaMostrare` legge: senza,
// il banco proverebbe una copia che non e' quella del modulo.
let ultimoStato = [];
// Le due variabili del pannello del modello, che `disegnaStep` fa girare a ogni
// passata: `fronteMostrato` e' la terna gia' sullo schermo, `ultimoModello`
// l'ordine delle riletture. Senza, il banco della colonna cadrebbe su un
// ReferenceError invece di dire qualcosa sulla colonna.
let fronteMostrato = "";
let ultimoModello = 0;
// Le variabili di modulo dell'analisi. `datiAnalisi` e `motivoAnalisi` a null
// sono «non ancora chiesta», che e' lo stato in cui le quattro schede non si
// toccano: senza, il banco proverebbe una copia che non e' quella del modulo.
let datiAnalisi = null;
let motivoAnalisi = null;
let firmaAnalisi = null;
let ultimaAnalisi = 0;
let ultimaVerifica = 0;
// Un banco non ha un server. Il fetch predefinito e' quello che il browser
// incontra col server spento -- solleva -- cosi' la tratta dell'analisi
// percorre il proprio ramo di rifiuto invece di rompersi su un identificatore
// che non c'e'. I banchi che provano una tratta lo sovrascrivono.
globalThis.fetch = async () => { throw new Error("nessun server nel banco"); };
const elenco = document.getElementById("elenco-step");
const STEPS = [
  { numero: 1, chiave: "01_load", stato: "valido" },
  { numero: 2, chiave: "02_segment", stato: "in corso" },
  { numero: 3, chiave: "03_downsample", stato: "mai eseguito" },
];
const marcati = () =>
  document.querySelectorAll(".step")
    .filter((c) => c.getAttribute("aria-current") === "true")
    .map((c) => Number(c.dataset.numero));
// Tutto il testo di un sottoalbero, per leggere una scheda come la legge chi
// guarda: le funzioni dell'analisi rendono nodi, e il testo sta sparso sulle
// foglie. Nessuna scorciatoia sul textContent del padre: il DOM finto non lo
// propaga, e propagarlo qui vorrebbe dire scrivere un secondo browser.
const testoDi = (nodi) => []
  .concat(nodi)
  .flatMap((nodo) => [nodo.testo, ...nodo.discendenti().map((figlio) => figlio.testo)])
  .join(" ");
"""
# `elemento` e' un legame di modulo che quasi ogni funzione estratta chiama, e
# le funzioni arrivano al banco senza cio' che sta loro attorno. Preso dal
# sorgente vero e non riscritto qui: e' la ragione per cui `_costante` esiste.
_DOM += _costante("elemento") + "\n"
# Le due chiavi degli step che stanno fuori dalla colonna. `disegnaStep` le
# legge tutte e due nello stesso filtro, quindi ogni banco che disegna la
# colonna le vuole. Prese dal sorgente vero e non riscritte qui, per la stessa
# ragione di `elemento`.
_DOM += _costante("STEP_DEL_PRIOR") + "\n"
# Il rimedio in coda ai rifiuti che l'interfaccia non sa spiegare: lo usano
# `caricaStato` e `apriDettaglio`, che stanno in banchi diversi.
_DOM += _costante("RIMEDIO") + "\n"
# I titoli dei gruppi di parametri: `gruppoDelBlocco` la legge a ogni pannello.
_DOM += _costante("ETICHETTE_DEI_BLOCCHI") + "\n"
# Le costanti del pannello del modello, per la stessa ragione delle due qui
# sopra: `disegnaStep` chiama `aggiornaModello` in coda, e ogni banco che
# disegna la colonna se le porta dietro.
_DOM += _tabella_del_modello()
# Le chiavi il cui «sì» e' una contraddizione. Sta qui e non nei singoli banchi
# perche' `righeDelModello` la legge, e `aggiornaModello` in coda a `disegnaStep`
# la porta dentro ogni banco che disegna la colonna. Dal modulo vero e non da
# `_costante`: la costante e' finita in etichette.js, che _importa_ (non
# ritaglia) -- lo stesso Set non si scrive due volte a mano.
_DOM += "const METRICHE_D_ALLARME = new Set(" + _importa(
    UI_DIR / "etichette.js", "console.log(JSON.stringify([...modulo.METRICHE_D_ALLARME]));",
).strip() + ");\n"


# --------------------------------------------------------------------------
# La regione role="alert": la mossa, non il sintomo.
# --------------------------------------------------------------------------


def test_la_regione_d_errore_esiste_nel_markup_e_non_nasce_nascosta():
    """Strada 1. Nel markup e non creata da codice: deve preesistere a cio' che
    annuncia. E senza `hidden`, che la toglierebbe dall'albero."""
    elemento = _elemento(_senza_commenti_html(_markup()), "errore")
    assert 'role="alert"' in elemento, f"la regione ha perso il proprio ruolo: {elemento}"
    assert "hidden" not in elemento, f"hidden la toglie dall'albero: {elemento}"


def test_il_pie_di_pagina_tace_le_voci_nulle_e_porta_il_link_al_repository(tmp_path):
    sorgente = _DOM + _funzioni("righeDelleInformazioni") + """
const piene = righeDelleInformazioni({nome: "MeshRec", versione: "1.0.0", commit: "abc1234", licenza: "MIT", doi: "10.5281/zenodo.99", doi_url: "https://doi.org/10.5281/zenodo.99", repository: "https://github.com/maeurong/meshrec"});
assert.deepEqual(piene.map((r) => r.testo), ["MeshRec 1.0.0", "abc1234", "MIT", "doi 10.5281/zenodo.99", "come citare"]);
assert.equal(piene[4].href, "https://github.com/maeurong/meshrec");
assert.equal(piene[3].href, "https://doi.org/10.5281/zenodo.99");
const vuote = righeDelleInformazioni({nome: "MeshRec", versione: "sorgente", commit: null, licenza: "MIT", doi: null, doi_url: null, repository: "https://github.com/maeurong/meshrec"});
assert.deepEqual(vuote.map((r) => r.testo), ["MeshRec sorgente", "MIT", "come citare"]);
assert.ok(!JSON.stringify(vuote).includes("null"));
"""
    _esegui(tmp_path, sorgente)


def test_mostra_informazioni_con_fetch_che_rigetta_non_solleva(tmp_path):
    """Punto 7 fix wave (test mancante): se /api/info rigetta, `mostraInformazioni`
    non deve sollevare e il footer resta vuoto (uccide la rimozione di
    `.catch(serverMuto)` o dell'early return). `_DOM` fa gia' rigettare
    `fetch` di default: e' il caso "nessun server nel banco"."""
    sorgente = _DOM + _funzioni(
        "mostraInformazioni", "serverMuto", "corpoLetto", "righeDelleInformazioni"
    ) + """
await mostraInformazioni();
assert.equal(document.getElementById("informazioni").children.length, 0);
"""
    _esegui(tmp_path, sorgente)


def test_il_pie_di_pagina_esiste_nel_markup():
    markup = _senza_commenti_html(_markup())
    assert '<footer class="informazioni" id="informazioni"' in markup


def test_il_pie_di_pagina_sta_fuori_dal_div_di_lavoro():
    """Il piè si vede anche con la schermata d'ingresso a video (#lavoro porta
    `hidden`): deve stare fuori dal div che quell'attributo nasconde, non
    dentro. Una sottostringa da sola non lo direbbe: un refactor che spostasse
    `<footer>` dentro `#lavoro` lo farebbe sparire insieme alla zona nascosta,
    e `test_il_pie_di_pagina_esiste_nel_markup` resterebbe verde lo stesso."""
    markup = _senza_commenti_html(_markup())
    apertura = markup.index('<div class="tre-zone" id="lavoro"')
    profondita = 0
    chiusura = None
    for tag in re.finditer(r"<div\b|</div>", markup[apertura:]):
        profondita += 1 if tag.group() == "<div" else -1
        if profondita == 0:
            chiusura = apertura + tag.end()
            break
    assert chiusura is not None, "il div di #lavoro non si chiude mai"
    indice_footer = markup.index('<footer class="informazioni"')
    assert indice_footer > chiusura, (
        "il pie' di pagina e' finito dentro #lavoro: sparirebbe con hidden"
    )


def test_la_regione_d_errore_sta_fuori_da_cio_che_viene_riscritto():
    """Strada 3. `#dettaglio` viene svuotato con replaceChildren() a ogni
    apertura di pannello: la regione dentro di li' non sopravvive a un clic."""
    markup = _senza_commenti_html(_markup())
    assert markup.index('id="errore"') < markup.index('id="dettaglio"'), (
        "la regione e' finita dentro il pannello che viene riscritto"
    )
    dentro = markup.split('<div id="dettaglio"', 1)[1]
    assert 'id="errore"' not in dentro, "la regione e' finita dentro #dettaglio"


def test_il_modulo_scrive_nella_regione_invece_di_fabbricarne_una():
    """La quarta strada. Un ramo che si crea la propria regione `role="alert"`
    riapre il difetto con l'aria di risolverlo: il codice sembra piu' completo,
    e l'annuncio smette di essere garantito.

    Si guarda la **forma di codice** e non la stringa — `role="alert"` compare
    per iscritto nei commenti, e vietare la stringa vieterebbe la spiegazione —
    ma tutte le forme, non una sola grafia: `setAttribute` con gli apici in
    entrambi i versi e con qualunque spaziatura, la proprieta' riflessa
    `.role =` (Chrome 119+), e `Object.assign(p, { role: … })`. Le tre che
    mancavano erano verdi, ed erano equivalenti a quella sorvegliata.
    """
    modulo = _modulo()
    codice = _senza_commenti_js(modulo)
    assert 'getElementById("errore")' in modulo, "il modulo non e' piu' agganciato alla regione"
    forme = re.findall(
        r"""setAttribute\(\s*["']role["']|\.role\s*=|\brole\s*:""", codice
    )
    assert forme == [], f"un ramo fabbrica di nuovo la propria regione role=alert: {forme}"


# --------------------------------------------------------------------------
# L'elenco degli step: comando, aggiornamento sul posto, marchio.
# --------------------------------------------------------------------------


def test_ogni_step_e_un_comando_e_non_una_riga_cliccabile():
    """Undici `li` con un gestore di click erano l'intera interfaccia
    pilotabile col solo mouse (WCAG 2.1.1, livello A). Il rischio della
    ricaduta e' concreto: il `li` torna comodo appena qualcuno vuole
    aggiungerci sopra un'altra riga."""
    riga = _modulo().split("function nuovaRiga(", 1)[1].split("\n}\n", 1)[0]
    assert 'createElement("button")' in riga, "lo step e' tornato una riga senza ruolo"
    assert 'comando.type = "button"' in riga, "senza type, dentro un form il bottone invia"
    assert 'className = "step"' in riga, "il foglio si aggancia a .step: il nome non cambia"


def test_ogni_riga_porta_il_numero_dello_step_che_le_istruzioni_nominano(tmp_path):
    """L'interfaccia parla per numeri e la colonna non ne mostrava nessuno.

    «esegui lo step 1», «e' lo step 12», «lo step 11 si ferma finche' questi
    quattro valori non ci sono», «step 5 in corso»: tutte istruzioni che
    indicano una coordinata che a video non c'era: l'elenco ha
    `list-style: none` e la riga portava il solo nome. Chi apre il programma
    per la prima volta -- il lettore dichiarato in PRODUCT.md -- leggeva
    «esegui lo step 1» davanti a undici parole e nessun modo di contarle.

    Il numero viene da `voce.numero`, cioe' dal server, e non dalla posizione
    nell'elenco: un contatore CSS lo indovinerebbe dalla riga e stamperebbe
    comunque un numero -- quello sbagliato -- il giorno in cui l'elenco non
    partisse da uno. Il banco chiede 4 e 12 alle posizioni 0 e 1 apposta: un
    numero letto dalla posizione direbbe 1 e 2 e cadrebbe qui.

    L'11 e non il 12, che era la coppia di prima, e prima ancora il 13: ogni
    volta che il fondo della colonna si e' alzato, il numero alto del banco e'
    dovuto scendere sotto di esso. Una riga con un numero che il filtro toglie
    non esiste piu' li' dentro, e il banco proverebbe il filtro invece del
    numero. Oggi il fondo e' l'11, il deck, dove si chiude il perimetro del
    prodotto.
    """
    _esegui(tmp_path, _DOM + _funzioni(*_COLONNA) + """
disegnaStep([
  { numero: 4, chiave: "04_normals", stato: "valido" },
  { numero: 11, chiave: "11_export", stato: "mai eseguito" },
]);
const primi = elenco.children.map((riga) => riga.firstElementChild.firstElementChild);
assert.deepEqual(
  primi.map((e) => e.textContent), ["4", "11"],
  "la riga non porta il numero dello step, o lo legge dalla posizione nell'elenco",
);
assert.deepEqual(
  primi.map((e) => e.className), ["step-numero", "step-numero"],
  "il numero non e' piu' il primo figlio della riga: il foglio gli da' la colonna per nome",
);
""")


def test_l_elenco_degli_step_si_aggiorna_e_non_si_ricostruisce(tmp_path):
    """Il difetto e' nato dalla correzione che lo precede.

    Finche' gli step erano `li` inerti, riscrivere l'elenco a ogni evento non
    costava niente. Reso ciascuno un `<button>`, la stessa riscrittura — due
    volte al secondo mentre la pipeline gira — distrugge l'elemento che ha il
    fuoco una sessantina di volte durante uno step da 34 secondi.

    Provato **eseguendo** `disegnaStep` due volte e guardando l'identita' dei
    nodi, non la guardia per iscritto: la guardia resa inerte con `|| true`
    lascia la sottostringa al suo posto, ricostruisce l'elenco a ogni evento, e
    un controllo testuale resta verde. Questo diventa rosso.
    """
    _esegui(tmp_path, _DOM + _funzioni(*_COLONNA) + """
disegnaStep(STEPS);
const prima = elenco.children.map((riga) => riga.firstElementChild);
assert.equal(prima.length, 3, "l'elenco non viene piu' costruito");
assert.deepEqual(prima.map((c) => c.className), ["step", "step", "step"]);
disegnaStep(STEPS.map((voce) => ({ ...voce, stato: "fallito" })));
const dopo = elenco.children.map((riga) => riga.firstElementChild);
assert.deepEqual(
  prima.map((c, i) => c === dopo[i]), [true, true, true],
  "l'elenco si ricostruisce a ogni evento: il fuoco da tastiera non sopravvive",
);
assert.deepEqual(
  elenco.children.map((riga) => riga.className),
  ["stato-fallito", "stato-fallito", "stato-fallito"],
  "lo stato non arriva piu' alla riga",
);
disegnaStep([...STEPS, { numero: 4, chiave: "04_normals", stato: "valido" }]);
assert.equal(elenco.childElementCount, 4, "cambiata la lunghezza, l'elenco non la segue");
""")


def test_solo_lo_step_aperto_porta_il_marchio(tmp_path):
    """Correzione 2. Quale step e' aperto lo sapeva solo una variabile di
    modulo: a video non lo diceva niente, e chi non vede il fondo evidenziato
    non aveva **nessun** canale. `aria-current` e non una classe, perche' e'
    l'attributo che porta il significato e il foglio ci si aggancia sopra.

    Due proprieta', ed entrambe si rompono in silenzio: mai due marchi insieme
    (due «stai guardando questo» sono peggio di nessuno), e il marchio sparisce
    quando nessun pannello e' aperto.
    """
    _esegui(tmp_path, _DOM + _funzioni(*_COLONNA) + """
disegnaStep(STEPS);
segnaStepAperto(2);
assert.deepEqual(marcati(), [2], "il marchio non e' sullo step aperto, o non e' solo suo");
segnaStepAperto(3);
assert.deepEqual(marcati(), [3], "il marchio precedente resta: due step aperti insieme");
segnaStepAperto(null);
assert.deepEqual(marcati(), [], "nessun pannello aperto e il marchio resta appeso");
""")
    assert '.step[aria-current="true"]' in _foglio(), (
        "il foglio non si aggancia piu' ad aria-current: il marchio resta senza fondo"
    )


def test_il_marchio_non_resta_su_uno_step_che_nessun_pannello_mostra(tmp_path):
    """`apriDettaglio` ha due uscite d'errore, e nessuna delle due toccava il
    marchio: aperto lo step 3, cliccato il 5, `/api/config` che risponde 500, il
    pannello si svuotava, la riga d'errore parlava del 5, il viewport mostrava
    il 5 — e `aria-current` restava sul 3. L'unico canale che dice «stai
    guardando questo» nominava lo step sbagliato.
    """
    testo = _modulo()
    assert testo.count("fallisciDettaglio(dettaglio, ragione);") == 2, (
        "una delle due uscite d'errore di apriDettaglio non passa piu' di qui"
    )
    _esegui(tmp_path, _DOM + _funzioni(
        *_COLONNA, "dichiaraErrore", "fallisciDettaglio",
    ) + """
const dettaglio = document.getElementById("dettaglio");
disegnaStep(STEPS);
stepAperto = 3;
segnaStepAperto(3);
dettaglio.append(document.createElement("p"));
fallisciDettaglio(dettaglio, "il server ha risposto 500");
assert.deepEqual(marcati(), [], "il marchio resta su uno step che nessun pannello mostra");
assert.equal(stepAperto, null, "a fine corsa si ricaricherebbe un pannello che non c'e'");
assert.equal(dettaglio.childElementCount, 0, "il pannello non e' stato svuotato");
assert.equal(rigaErrore.textContent, "il server ha risposto 500", "la ragione non e' a video");
""")


# --------------------------------------------------------------------------
# Il registro: tappa di tabulazione, non regione viva, e con un tetto.
# --------------------------------------------------------------------------


def test_il_registro_e_una_tappa_di_tabulazione():
    """Il registro e' alto 14rem, scorre, e dentro non c'e' niente su cui il
    fuoco possa posarsi: senza `tabindex` Chrome non lo rende raggiungibile da
    tastiera e le righe uscite dall'alto non si rileggono senza il mouse
    (WCAG 2.1.1, livello A). Firefox mette il fuoco sui contenitori che
    scorrono da se', Chrome no."""
    elemento = _elemento(_senza_commenti_html(_markup()), "registro")
    assert 'tabindex="0"' in elemento, f"il registro non e' piu' raggiungibile: {elemento}"


def test_il_registro_non_e_una_regione_viva():
    """`role="log"` porta con se' una regione viva, e qui dentro finisce tutto
    lo stdout del sottoprocesso: un lettore di schermo leggeva ad alta voce ogni
    riga di TetGen per i 34 secondi di uno step, coprendo l'unica cosa che va
    davvero sentita, il `role="alert"` della riga d'errore."""
    elemento = _elemento(_senza_commenti_html(_markup()), "registro")
    assert 'aria-live="off"' in elemento, (
        f"il registro torna a parlare sopra la riga d'errore: {elemento}"
    )


def test_il_registro_scarta_la_riga_piu_vecchia_e_mai_la_piu_recente(tmp_path):
    """Il registro cresceva senza tetto. Il tetto va provato **al confine** e
    sul verso: un `>=` al posto del `>` tiene una riga di meno, e togliere
    `firstElementChild` invece di quello butta via l'ultima arrivata, che e'
    l'unica che si sta guardando. Nessuna delle due si vede leggendo.
    """
    testo = _modulo()
    tetto = int(re.search(r"const RIGHE_DEL_REGISTRO = (\d+);", testo).group(1))
    corpo = testo.split('flusso.addEventListener("riga", (evento) => {', 1)[1]
    corpo = corpo.split("\n});", 1)[0]
    _esegui(tmp_path, _DOM + f"const RIGHE_DEL_REGISTRO = {tetto};\n"
            "function aggiungiRiga(evento) {" + corpo + "}\n" + f"""
const registro = document.getElementById("registro");
const scrivi = (n) => aggiungiRiga({{ data: JSON.stringify(`riga ${{n}}`) }});
for (let n = 1; n <= {tetto}; n += 1) scrivi(n);
assert.equal(registro.childElementCount, {tetto}, "il tetto taglia prima di esserci arrivato");
assert.equal(registro.firstElementChild.textContent, "riga 1", "ha buttato via una riga di troppo");
assert.equal(registro.lastElementChild.textContent, "riga {tetto}");
scrivi({tetto} + 1);
assert.equal(registro.childElementCount, {tetto}, "il tetto non tiene: il registro cresce ancora");
assert.equal(
  registro.firstElementChild.textContent, "riga 2",
  "non esce la piu' vecchia",
);
assert.equal(
  registro.lastElementChild.textContent, "riga {tetto + 1}",
  "esce la piu' recente, cioe' l'unica che si sta guardando",
);
""")


# --------------------------------------------------------------------------
# Il fuoco da tastiera si deve vedere.
# --------------------------------------------------------------------------


def test_il_fuoco_da_tastiera_si_vede_su_ogni_comando():
    """Chi naviga da tastiera senza un contorno di fuoco non sa dove si trova
    (WCAG 2.4.7). `:focus-visible` e non `:focus`, cosi' il contorno non compare
    al clic del mouse; e nessun `outline: none`, che e' il modo in cui questo
    difetto rientra di solito."""
    foglio = _foglio()
    # `h2` ci sta da quando le due intestazioni delle schermate ricevono il fuoco
    # per programma (tabindex="-1"): senza la loro regola il passaggio fra pipeline
    # e analisi posa il cursore in un punto che non si vede.
    for comando in (".bottone", ".step", ".registro", ".campo input", "h2"):
        assert f"{comando}:focus-visible" in foglio, (
            f"{comando} non mostra piu' dove si trova il fuoco"
        )
    regole = re.findall(r":focus-visible[^{]*\{([^}]*)\}", foglio)
    assert regole, "nessuna regola di fuoco nel foglio"
    for regola in regole:
        assert "outline" in regola and "outline: none" not in regola, (
            f"la regola di fuoco non disegna nulla: {regola}"
        )


# --------------------------------------------------------------------------
# Lo scanner strutturale: ogni gestore che scrive dopo un'attesa fetch si
# difende con un contatore fresco o un disable, non solo con `ordine`.
#
# La proprieta' e' generica, non di dominio: un `addEventListener` agganciato
# una volta puo' rifirare piu' volte (due clic, non un solo evento), e un
# contatore catturato nella chiusura esterna (`ordine` = la generazione del
# pannello) non si aggiorna fra un clic e l'altro. Applicato al file prima di
# questo giro lo scanner sotto avrebbe segnalato **entrambi** i bottoni che
# questo giro corregge — riga del ritaglio e righe dei due «Esegui» — insieme
# a `scriviParametro`, gia' corretto in un giro precedente: la quarta istanza
# senza che nessuno la trovasse leggendo a mano.
# --------------------------------------------------------------------------


_GESTORE_NOMINATO = re.compile(r"^\w+$")
_DELEGA_A_UNA_FUNZIONE = re.compile(r"^\([^)]*\)\s*=>\s*(\w+)\(")
_CONTATORE_FRESCO = re.compile(r"\bapri\w*\(")
# Due forme riconosciute, non una sola: `.disabled = true` e
# `.setAttribute("disabled", ...)` disabilitano l'elemento allo stesso modo
# (un attributo booleano HTML, il valore del secondo argomento non conta).
# Prima di questa riga solo la prima forma era riconosciuta, e la seconda —
# una difesa legittima quanto la prima — veniva segnalata come vulnerabile:
# un falso positivo che disattiva chi lo incontra invece di proteggerlo.
_DISABLE_ELEMENTO = re.compile(r"""\.disabled\s*=\s*true\b|\.setAttribute\(\s*["']disabled["']""")
_SCRITTURA = re.compile(r"(?<![=!<>])=(?!=|>)")


def _corpo_del_gestore(gestore: str, modulo: str) -> str:
    """Risolve il testo del gestore per un solo livello di delega: un
    riferimento nominato (`annullaLaCorsa`) o una singola espressione di
    chiamata (`() => scriviParametro(...)`) vengono seguiti fino al corpo
    della funzione richiamata. Non piu' in la': un gestore che delega a una
    funzione che a sua volta delega a quella che apre il contatore non viene
    risolto — e' il primo confine dichiarato piu' sotto, nel corpo del test.
    """
    gestore = gestore.strip()
    if _GESTORE_NOMINATO.match(gestore):
        try:
            return _sorgente_di(gestore, modulo)
        except (IndexError, ValueError):
            return gestore
    apertura = gestore.find("{")
    if apertura != -1:
        profondita = 0
        for indice in range(apertura, len(gestore)):
            if gestore[indice] == "{":
                profondita += 1
            elif gestore[indice] == "}":
                profondita -= 1
                if profondita == 0:
                    return gestore[apertura + 1 : indice]
        return gestore[apertura + 1 :]
    delega = _DELEGA_A_UNA_FUNZIONE.match(gestore)
    if delega:
        try:
            return _sorgente_di(delega.group(1), modulo)
        except (IndexError, ValueError):
            return gestore
    return gestore


def _fine_chiamata(testo: str, apertura: int) -> int:
    """Indice appena dopo la ')' che chiude la chiamata la cui '(' sta a
    `apertura`, contando la profondita' delle parentesi."""
    profondita = 1
    indice = apertura + 1
    while indice < len(testo) and profondita > 0:
        if testo[indice] == "(":
            profondita += 1
        elif testo[indice] == ")":
            profondita -= 1
        indice += 1
    return indice


def _file_js_dell_interfaccia(base: Path = UI_DIR) -> list[Path]:
    """Ogni `.js` sotto `base`, in qualunque sottocartella, derivato con un
    glob e non elencato a mano: uno scanner che leggesse un percorso
    letterale (`base / "app.js"`) lascerebbe un secondo file con un gestore
    vulnerabile invisibile in silenzio — e un elenco a mano dei nomi avrebbe
    lo stesso difetto un livello piu' in la', perche' un file nuovo non
    finirebbe nell'elenco. Un glob non ricorsivo ha lo stesso difetto ancora
    un livello piu' in la': cattura un file nuovo a fianco di `app.js` ma non
    uno nato domani in una sottocartella (`ui/pannelli/qualcosa.js`), e tace
    esattamente come i due difetti precedenti — percio' `rglob`, non `glob`.

    `vendor/` resta fuori per nome, non perche' un glob ricorsivo non ci
    arrivi: ci arriverebbe, ed e' filtrato apposta, perche' non e' nostro
    codice. Fuori raggio anche cio' che non finisce in `.js` — `index.html`,
    `stile.css` — dichiarato qui e non lasciato implicito: quei file hanno le
    proprie prove altrove in questo modulo, non questo scanner."""
    return sorted(
        p for p in base.rglob("*.js") if "vendor" not in p.relative_to(base).parts
    )


def _addEventListener_del_modulo(modulo: str) -> list[dict]:
    """Ogni `.addEventListener(evento, gestore)` a livello di modulo, con la
    riga sorgente e il testo grezzo (non ancora risolto) del gestore."""
    risultati = []
    for trovato in re.finditer(r'\.addEventListener\(\s*["\'](\w+)["\']\s*,\s*', modulo):
        evento = trovato.group(1)
        apertura = modulo.index("(", trovato.start())
        fine = _fine_chiamata(modulo, apertura)
        gestore = modulo[trovato.end() : fine - 1]
        riga = modulo.count("\n", 0, trovato.start()) + 1
        risultati.append({"riga": riga, "evento": evento, "gestore": gestore})
    return risultati


def _vulnerabile(corpo: str) -> tuple[bool, str]:
    """La proprieta': un corpo che attende `fetch` e scrive dopo, senza aprire
    un contatore fresco (`apri\\w*(`, la famiglia di apriGenerazione /
    apriGeometria / apriBattuta / apriRichiesta / apriAzione) ne'
    disabilitare l'elemento (`.disabled = true`) **prima** dell'attesa, e'
    vulnerabile all'ordine invertito di due chiamate sovrapposte."""
    indice = corpo.find("await fetch(")
    if indice == -1:
        return False, "nessuna await fetch nel corpo risolto"
    apertura = corpo.index("(", indice)
    dopo = corpo[_fine_chiamata(corpo, apertura) :]
    if not _SCRITTURA.search(dopo):
        return False, "nessuna scrittura dopo l'attesa"
    prima = corpo[:indice]
    if _CONTATORE_FRESCO.search(prima) or _DISABLE_ELEMENTO.search(prima):
        return False, "contatore fresco o disable aperti prima dell'attesa"
    return True, "nessun contatore fresco ne' disable prima dell'attesa fetch, e scrive dopo"


def _segnalazioni(base: Path = UI_DIR) -> list[str]:
    """Applica la proprieta' `_vulnerabile` a ogni gestore di ogni file
    trovato da `_file_js_dell_interfaccia(base)`. Estratta a parte cosi' la
    portata (quali file entrano nella scansione) e la proprieta' (cosa rende
    un gestore vulnerabile) si provano insieme, con la stessa funzione, sia
    sull'interfaccia vera sia su una directory finta."""
    segnalati = []
    for percorso in _file_js_dell_interfaccia(base):
        modulo = percorso.read_text(encoding="utf-8")
        for voce in _addEventListener_del_modulo(modulo):
            corpo = _corpo_del_gestore(voce["gestore"], modulo)
            vulnerabile, ragione = _vulnerabile(corpo)
            if vulnerabile:
                segnalati.append(f"{percorso.name}, riga {voce['riga']} (evento {voce['evento']}): {ragione}")
    return segnalati


def test_ogni_gestore_che_scrive_dopo_un_attesa_si_difende():
    """Lo scanner strutturale che chiude la serie — il cuore di questo giro.
    Vedi il commento di sezione qui sopra per la proprieta'; qui sotto, per
    iscritto e non taciuto, il confine di quello che questo scanner NON vede
    — tacerlo ripeterebbe esattamente il difetto del test sui `.json()`, che
    scandiva la sola sottostringa letterale ed e' stato aggirato in tre modi:

    - **un solo livello di delega.** Un gestore che delega a una funzione la
      quale a sua volta delega a un'altra che apre il contatore non viene
      risolto: passerebbe per «nessuna await fetch nel corpo risolto» anche
      se in realta' ne contiene una, due chiamate piu' in la'.
    - **solo la stringa letterale `await fetch(`.** Un gestore che attende
      una funzione intermedia (`await ricaricaVistaAsync()`) che al suo
      interno fa la fetch non viene riconosciuto come «attende» da questo
      scanner, anche se il gestore risolto la contiene per intero.
    - **controllo posizionale sul testo, non sul flusso di controllo.** Il
      contatore o il disable devono comparire testualmente prima della prima
      `await fetch(`: una chiamata `apriX()` scritta dentro un `if` che a
      runtime puo' non eseguirsi affatto prima della fetch supera comunque
      questo controllo, perche' lo scanner non sa se quel ramo si esegue
      davvero.
    - **il contatore va solo aperto, non controllato.** Lo scanner guarda se
      `apri\\w*(` compare nel testo prima della fetch — non se il valore che
      restituisce viene davvero letto da una `superata(...)`. Una
      `apriRichiesta()` lasciata li' per decorazione, con la guardia vera
      tolta subito dopo, resta invisibile: verificato mutando cosi' il
      bottone del ritaglio nel worktree di lavoro — lo scanner e' rimasto
      verde, e solo il test comportamentale sui due clic sovrapposti (sotto)
      e' diventato rosso. E' il motivo per cui questo giro non si ferma allo
      scanner: la coppia struttura+comportamento e' quella che chiude,
      nessuna delle due da sola.
    - **due forme di disable riconosciute, non tutte.** `.disabled = true` e
      `.setAttribute("disabled", ...)` (qualunque secondo argomento: e' un
      attributo booleano HTML) contano come difesa. Un `readOnly = true`, o
      togliere l'elemento dal DOM per la durata dell'attesa, restano non
      riconosciuti: un gestore disabilitato in una di queste due forme
      risulterebbe un falso vulnerabile (innocuo qui: nessuno dei due casi e'
      nel file oggi, verificato leggendolo). Fino alla correzione di questo
      giro solo `.disabled = true` era riconosciuta, e `setAttribute` — una
      difesa legittima quanto l'altra — veniva segnalata a torto: un falso
      positivo che disattiva chi lo incontra, verificato in
      `test_lo_scanner_riconosce_anche_setAttribute_disabled_come_disable_legittimo`.
    - **«scrive dopo l'attesa» e' un `=` di assegnazione nel testo dopo la
      fetch** (che non sia `==`, `===` ne' `=>`). Conta anche una `const x =
      ...` puramente locale che non scrive mai fuori dal gestore — puo'
      quindi sovrastimare (falso vulnerabile) — ma non vede una scrittura per
      side-effect senza `=` dopo la fetch, come una `Array.push(...)` o una
      chiamata a un setter senza segno `=` visibile — puo' quindi
      sottostimare (falso sicuro) in quel caso specifico, non presente oggi
      in questo file, verificato leggendolo.

    - **la portata era un percorso letterale, non dichiarata.** Fino alla
      correzione di questo giro lo scanner leggeva solo `UI_DIR / "app.js"`:
      un secondo file dell'interfaccia con un gestore vulnerabile restava
      invisibile in silenzio, il difetto peggiore per un test strutturale
      perche' non fallisce e non avverte. Ora scandisce ogni `.js` derivato
      da `_file_js_dell_interfaccia()` (oggi: `app.js` e `viewport.js`;
      `vendor/` resta fuori) — verificato che il glob deriva l'insieme giusto
      in `test_l_insieme_dei_file_scanditi_e_derivato_non_elencato_a_mano`.
      `viewport.js` oggi non contiene nessuna `fetch(`: scandirlo non
      aggiunge segnalazioni, ma lo mette nel raggio se un giorno ne
      aggiungesse una.

    La parte che resta vera della dichiarazione di limite del giro precedente:
    questa proprieta' cattura la guardia **assente o troppo grossolana in una
    forma riconoscibile** — non stabilisce quale sia la grana giusta (per
    campo? per clic? per pannello?), quella resta una decisione di dominio.
    """
    assert _segnalazioni() == [], (
        "gestori senza contatore fresco (apri\\w*()) ne' disable riconosciuto "
        '(.disabled = true, oppure .setAttribute("disabled", ...)) prima dell\'attesa:\n'
        + "\n".join(_segnalazioni())
    )


def test_l_insieme_dei_file_scanditi_e_derivato_non_elencato_a_mano(tmp_path):
    """Il limite trovato dal revisore: lo scanner leggeva `UI_DIR / "app.js"`,
    un percorso letterale. Un secondo file dell'interfaccia con un gestore
    vulnerabile restava invisibile in silenzio — provato dal revisore
    creandone uno vero in un worktree isolato e vedendo lo scanner non
    accorgersene.

    Qui si prova la derivazione da sola, su una directory finta: un elenco a
    mano dei nomi (`["app.js", "viewport.js"]`) avrebbe risolto il caso di
    oggi ma avrebbe lo stesso identico difetto un livello piu' in la' — un
    terzo file futuro resterebbe fuori dall'elenco esattamente come restava
    fuori dal percorso letterale. Il glob non ha questo problema: qualunque
    `.js`, a qualunque profondita' sotto la directory, ci entra da solo —
    `pannelli/qualcosa.js` qui sotto non esiste oggi in `UI_DIR`: e' il caso
    futuro che un glob non ricorsivo lasciava fuori in silenzio.
    """
    finto = tmp_path / "ui"
    finto.mkdir()
    (finto / "app.js").write_text("", encoding="utf-8")
    (finto / "altro.js").write_text("", encoding="utf-8")
    (finto / "vendor").mkdir()
    (finto / "vendor" / "three.module.min.js").write_text("", encoding="utf-8")
    (finto / "pannelli").mkdir()
    (finto / "pannelli" / "qualcosa.js").write_text("", encoding="utf-8")
    trovati = {p.relative_to(finto) for p in _file_js_dell_interfaccia(finto)}
    assert trovati == {Path("app.js"), Path("altro.js"), Path("pannelli/qualcosa.js")}, (
        f"il glob non scende nelle sottocartelle, o non esclude vendor/: {trovati}"
    )


def test_un_gestore_vulnerabile_in_una_sottocartella_futura_viene_visto(tmp_path):
    """Dai alla portata un test proprio, non solo all'insieme dei nomi qui
    sopra: qui il file in sottocartella non e' vuoto, contiene un gestore
    vulnerabile per davvero — la stessa proprieta' di
    `test_ogni_gestore_che_scrive_dopo_un_attesa_si_difende`, applicata a un
    file che oggi non esiste in `UI_DIR` (`pannelli/qualcosa.js`) ma
    domani potrebbe. Morde: con `base.glob("*.js")` al posto di
    `base.rglob("*.js")` questo file resta fuori e `_segnalazioni` torna
    vuota nonostante il gestore sotto sia vulnerabile — verificato a mano
    ripristinando temporaneamente il glob non ricorsivo nel worktree di
    lavoro, vedi il rapporto.
    """
    finto = tmp_path / "ui"
    (finto / "pannelli").mkdir(parents=True)
    (finto / "pannelli" / "qualcosa.js").write_text(
        'bottone.addEventListener("click", async () => {\n'
        '  const risposta = await fetch("/api/qualcosa");\n'
        '  esito.textContent = risposta.status;\n'
        "});\n",
        encoding="utf-8",
    )
    segnalati = _segnalazioni(finto)
    assert segnalati != [], (
        "un gestore vulnerabile in sottocartella resta invisibile allo scanner"
    )
    assert segnalati[0].startswith("qualcosa.js"), segnalati


def test_lo_scanner_riconosce_anche_setAttribute_disabled_come_disable_legittimo():
    """Il falso positivo trovato dal revisore: `setAttribute("disabled", "")`
    disabilita l'elemento tanto quanto `.disabled = true` — e' lo stesso
    attributo booleano HTML, letto da entrambe le forme — ma prima di questa
    correzione lo scanner riconosceva solo la seconda e segnalava la prima
    come vulnerabile. Un test strutturale che grida al lupo per una difesa
    legittima si disattiva al primo che ha fretta, e allora non protegge piu'
    niente."""
    corpo = """
      bottone.setAttribute("disabled", "");
      const risposta = await fetch("/api/qualcosa");
      esito.textContent = risposta.status;
    """
    vulnerabile, ragione = _vulnerabile(corpo)
    assert not vulnerabile, f"setAttribute('disabled', ...) e' una difesa legittima, segnalata comunque: {ragione}"


# --------------------------------------------------------------------------
# Rilievo 1, quarta istanza: `ultimaGeometria`. Il buco principale trovato
# dalla revisione di questo giro. Le quattro guardie (righe 218, 232, 257,
# 269) esistono gia' e sono corrette — il difetto non e' nel codice, e' nella
# copertura: nessun test le provava, e rese decorative (`apriGeometria()`
# lasciata a chiamare, la lettura tolta) la suite intera restava 36 passed su
# 36, in un worktree isolato. Questi due test chiudono quel buco.
# --------------------------------------------------------------------------


def _banco_di_geometria() -> str:
    """`mostraNuvolaDelloStep` e `mostraStep`, con `vista` finta: e' dove sta
    il quarto contatore del censimento, `ultimaGeometria`, condiviso fra la
    tratta della nuvola e quella della mesh — il fronte di discesa ricarica
    la vista senza aprire una nuova generazione, quindi puo' gareggiare con
    una risposta partita prima portando lo stesso `ordine`; solo
    `ultimaGeometria` li distingue.
    """
    return _DOM + _funzioni(
        "apriGeometria",
        "superata",
        # L'attesa dichiarata e la strada dell'artefatto che non arriva, VERE e
        # non stubbate: sono dentro le due tratte che questo banco esercita, e
        # stubbarle toglierebbe di mezzo proprio cio' che puo' rompersi -- un
        # caricamento che non si chiude, o che si chiude mentre un'altra lettura
        # e' ancora in volo.
        "nomeDelloStep",
        "dichiaraCaricamento",
        "corpoBinarioLetto",
        "serverMuto",
        "ragioneDelRifiuto",
        "messaggioDownloadInterrotto",
        "segnalaArtefattoMancante",
        "mostraNuvolaDelloStep",
        "mostraStep",
        # Il taglio della coda delle normali dal corpo di /api/mesh: `caricaMesh`
        # la chiama, e senza il ritaglio il banco cade su un riferimento che non
        # esiste invece di provare l'arbitraggio che esiste per provare.
        "normaliDellaRisposta",
    ) + """
let ultimaGeometria = 0;
const STEP_CON_MESH = new Set([5, 6, 8, 9]);
const vista = {
  svuotate: 0,
  disegnato: null,
  svuota() { this.svuotate += 1; },
  mostraNuvola(dati) { this.disegnato = { tipo: "nuvola", lunghezza: dati.length }; },
  mostraMesh(vertici) { this.disegnato = { tipo: "mesh", lunghezza: vertici.length }; },
};
let risponde = [];
let chiamata = 0;
globalThis.fetch = async () => risponde[chiamata++]();
"""


def test_due_richieste_di_nuvola_sovrapposte_con_lo_stesso_ordine_non_fanno_vincere_la_vecchia(tmp_path):
    """La tratta della nuvola. Due richieste con lo stesso `ordine` — il caso
    del fronte di discesa in gara con una risposta partita prima, righe
    195-206 del modulo — invertite: quella piu' recente arriva per prima e
    disegna, quella piu' vecchia rientra dopo e non deve scrivere sopra."""
    _esegui(tmp_path, _banco_di_geometria() + """
let risolvi1, risolvi2;
risponde = [
  () => new Promise((r) => { risolvi1 = r; }),
  () => new Promise((r) => { risolvi2 = r; }),
];

const vecchia = mostraNuvolaDelloStep(9, generazione);
const nuova = mostraNuvolaDelloStep(9, generazione);

// La piu' recente arriva per prima.
risolvi2({
  ok: true,
  headers: { get: (nome) => ({ "X-Points-Drawn": "20", "X-Points-Total": "20" }[nome]) },
  arrayBuffer: async () => new ArrayBuffer(80),
});
assert.equal(await nuova, true, "la richiesta piu' recente non risulta disegnata");
assert.equal(vista.disegnato.lunghezza, 20, "il disegno a video non e' quello della richiesta recente");
assert.equal(vista.svuotate, 1, "la vista si e' svuotata piu' volte del dovuto finora");

// La piu' vecchia, rimasta in volo, rientra per ultima.
risolvi1({
  ok: true,
  headers: { get: (nome) => ({ "X-Points-Drawn": "5", "X-Points-Total": "5" }[nome]) },
  arrayBuffer: async () => new ArrayBuffer(20),
});
assert.equal(await vecchia, false, "la richiesta vecchia risulta disegnata: doveva essere scartata");
assert.equal(vista.disegnato.lunghezza, 20,
  "la risposta vecchia, arrivata per ultima, ha scritto sopra la nuvola piu' recente");
assert.equal(vista.svuotate, 1,
  "la vista vecchia e' stata svuotata di nuovo dopo essere gia' aggiornata dalla richiesta recente");
""")


def test_due_richieste_di_mesh_sovrapposte_con_lo_stesso_ordine_non_fanno_vincere_la_vecchia(tmp_path):
    """Stessa istanza sul ramo della mesh (righe 254-269 del modulo): stesso
    contatore `ultimaGeometria`, stessa guardia ripetuta due volte. Provata a
    parte perche' la mutazione decorativa del giro precedente ha svuotato
    tutte e quattro le guardie insieme, e un solo test sulla nuvola non
    proverebbe che anche questo ramo si difende per davvero."""
    _esegui(tmp_path, _banco_di_geometria() + """
let risolvi1, risolvi2;
risponde = [
  () => new Promise((r) => { risolvi1 = r; }),
  () => new Promise((r) => { risolvi2 = r; }),
];

const vecchia = mostraStep(9, generazione);
const nuova = mostraStep(9, generazione);

// La piu' recente arriva per prima: 7 vertici, 0 triangoli.
risolvi2({
  ok: true,
  headers: { get: (nome) => ({ "X-Vertices": "7", "X-Triangles": "0" }[nome]) },
  arrayBuffer: async () => new ArrayBuffer(84),
});
assert.equal(await nuova, true, "la richiesta piu' recente non risulta disegnata");
assert.equal(vista.disegnato.lunghezza, 21, "il disegno a video non e' quello della mesh recente");

// La piu' vecchia, rimasta in volo, rientra per ultima: 2 vertici.
risolvi1({
  ok: true,
  headers: { get: (nome) => ({ "X-Vertices": "2", "X-Triangles": "0" }[nome]) },
  arrayBuffer: async () => new ArrayBuffer(24),
});
assert.equal(await vecchia, false, "la mesh vecchia risulta disegnata: doveva essere scartata");
assert.equal(vista.disegnato.lunghezza, 21,
  "la mesh vecchia, arrivata per ultima, ha scritto sopra quella piu' recente");
""")


# --------------------------------------------------------------------------
# BL-1: dai tasti al disco.
# --------------------------------------------------------------------------


def test_il_campo_parametro_prende_il_tipo_dallo_schema_e_non_dal_valore(tmp_path):
    """La radice del difetto. Il tipo veniva da `typeof` del valore corrente,
    cioe' indovinato: i quattro campi numerici nullabili scalari erano una
    casella di testo finche' valevano `None` e una numerica appena valevano
    qualcosa, e con `type="number"` Chrome sanifica cio' che non sa leggere —
    `.value` torna `""` mentre a video resta scritto `1e`. Il tipo lo conosce
    solo il modello, e adesso `/api/schema` lo manda.

    L'intento del controllo non cambia — il valore non decide il tipo — ma la
    fonte si': lo stesso valore, con due schemi diversi, deve dare due caselle
    diverse. Un controllo che guardasse solo il sorgente passerebbe anche a
    logica capovolta, quindi la parte che decide si esegue.

    I sei campi del ritaglio restano `type="number"`, e non e' un'incoerenza:
    li' il tipo non e' indovinato, sono le coordinate dell'ingombro e sono
    numeri per costruzione, con la loro guardia sul campo vuoto.
    """
    campo = _sorgente_di("campoParametro", _modulo())
    assert "typeof valore ===" not in campo, "il tipo del campo torna a dipendere dal valore"
    assert 'input.type = "number"' not in campo, (
        'type="number" sanifica in silenzio: cio\' che il browser non legge diventa ""'
    )
    assert 'input.step = "any"' not in campo, "step=any toglie il passo unitario agli interi"
    _esegui(tmp_path, _banco_del_campo() + """
// Lo stesso valore, due schemi: la forma cambia col tipo dichiarato, non col
// valore che c'e' dentro.
configurazione = { finto: { uguale: 1 } };
const testo = campoParametro("finto", "uguale", { description: "" }, generazione);
assert.equal(testo.children[1].type ?? "text", "text",
  "senza tipo dichiarato la casella non e' piu' di testo");
const cursore = campoParametro(
  "finto", "uguale", { description: "", tipo: "intero", ge: 0, le: 10 }, generazione);
assert.equal(cursore.children[1].type, "range",
  "il tipo dichiarato dallo schema non cambia la forma della casella");

// E il verso opposto: due valori diversi, lo stesso schema, la stessa forma.
// E' il caso che il difetto rompeva -- un nullabile valeva testo finche' era
// null e numero appena valeva qualcosa.
configurazione = { finto: { vuoto: null, pieno: 3.5 } };
const forma = (nome) => campoParametro(
  "finto", nome, { description: "", tipo: "reale", nullabile: true }, generazione,
).children[1];
assert.equal(forma("vuoto").tag, forma("pieno").tag,
  "un campo nullabile cambia forma a seconda che valga null o un numero");
""")


def test_una_durata_misurata_non_diventa_uno_zero_ne_un_minuto_di_sessanta(tmp_path):
    """La funzione che legge un tempo misurato, eseguita sui valori veri.

    Due estremi, entrambi presi da dati reali e non ipotizzati.

    Sotto: `runs/prova/steps.json` registra per lo step 8, a semplificazione
    disabilitata, `secondi: 1.3042008504271507e-05`. Arrotondato varrebbe «0 s»,
    e uno zero accanto agli altri tempi si legge «non e' partito» invece di «e'
    finito prima che si potesse misurare». E' il terzo principio di prodotto
    citato alla lettera: nessuno zero che significa «sotto la risoluzione della
    misura» presentato come «esatto».

    Sopra: dividere prima di arrotondare produce «1 min 60 s». 119,6 secondi
    danno `Math.floor(119.6 / 60)` uguale a 1 e un resto di 59,6 che
    l'arrotondamento porta a 60. Il controllo spazza un intervallo intero
    invece di fidarsi del caso singolo, perche' il difetto si ripresenta a ogni
    confine di minuto.
    """
    _esegui(tmp_path, "import assert from 'node:assert/strict';\n"
            + _funzioni("durataMisurata") + """
assert.equal(durataMisurata(0.000013042008504271507), "meno di 1 s",
  "lo step 8 a semplificazione spenta si legge «0 s», cioe' «non e' partito»");
assert.equal(durataMisurata(0), "meno di 1 s");
assert.equal(durataMisurata(0.9), "meno di 1 s");
assert.equal(durataMisurata(1), "1 s");
assert.equal(durataMisurata(32.98888658406213), "33 s", "il tempo misurato dello step 7");
assert.equal(durataMisurata(14.536296917009167), "15 s", "il tempo misurato dello step 2");
assert.equal(durataMisurata(89), "89 s", "sotto il minuto e mezzo i secondi bastano");
assert.equal(durataMisurata(89.6), "1 min 30 s");
assert.equal(durataMisurata(125), "2 min 5 s");

// Nessun minuto di sessanta secondi, a nessun confine.
for (let decimi = 900; decimi <= 6000; decimi += 1) {
  const letto = durataMisurata(decimi / 10);
  assert.ok(!/ 60 s$/.test(letto), `${decimi / 10} s si legge ${letto}`);
}
""")


def test_lo_zero_di_uno_step_fallito_non_viene_mostrato_come_una_misura(tmp_path):
    """`pipeline.py:574` registra `0.0` fisso quando uno step fallisce.

    Non e' un cronometro ma un segnaposto: uno step morto dopo venti secondi di
    lavoro lascia su disco `"secondi": 0.0`, e in `runs/prova/steps.json` lo
    step 9 e' esattamente cosi'. Mostrarlo scriverebbe «l'ultima volta 0 s»
    accanto a un tempo vero, cioe' un numero che nessuna misura sostiene messo
    dove sembra misurato -- il primo principio di prodotto letto al contrario.

    E la guardia non deve mangiare il caso che serve di piu': "non valido"
    significa che i parametri sono cambiati dopo l'esecuzione, non che quella
    esecuzione non sia avvenuta. Quel tempo e' misurato eccome, ed e' proprio
    lo step che si sta per rieseguire.
    """
    _esegui(tmp_path, "import assert from 'node:assert/strict';\n"
            + _funzioni("durataMisurata", "ultimaDurata") + """
assert.equal(ultimaDurata({ numero: 9, stato: "fallito", secondi: 0.0 }), null,
  "lo zero segnaposto di uno step fallito arriva a video come una misura");
assert.equal(ultimaDurata({ numero: 7, stato: "valido", secondi: 32.98888658406213 }), "33 s");
assert.equal(ultimaDurata({ numero: 2, stato: "non valido", secondi: 14.536296917009167 }), "15 s",
  "un tempo misurato sotto un'altra configurazione resta un tempo misurato");
assert.equal(ultimaDurata({ numero: 3, stato: "mai eseguito" }), null,
  "uno step mai eseguito non ha un tempo, e non ne inventa uno");
assert.equal(ultimaDurata({ numero: 3, stato: "valido", secondi: null }), null);
assert.equal(ultimaDurata(undefined), null, "uno step che il flusso non porta ancora");
assert.equal(ultimaDurata(null), null);
""")


def test_una_battuta_illeggibile_resta_quella_battuta(tmp_path):
    """La funzione che trasforma dei tasti in un dato persistito, eseguita.

    `1e`, `-`, `1.2.3` non si leggono come numeri e restano la stringa battuta:
    il modello le rifiuta con un 422 leggibile, che e' l'unico posto dove il
    tipo vero si conosce. Diventassero `null` sarebbero accettate in silenzio
    sui quattro campi numerici nullabili. E lo spazio non vale zero:
    `Number(" ")` e' `0`, e un campo che a video sembra vuoto scriveva `0`.
    """
    _esegui(tmp_path, "import assert from 'node:assert/strict';\n" + _funzioni("valoreScritto") + """
for (const battuto of ["1e", "-", "1.2.3", "abc", "1,5"]) {
  assert.equal(valoreScritto(battuto), battuto,
    `${battuto} non arriva al modello: viene inghiottito qui`);
}
assert.equal(valoreScritto(" "), null, "uno spazio scrive zero in un campo che sembra vuoto");
assert.equal(valoreScritto(""), null);
assert.equal(valoreScritto("2.5"), 2.5, "un valore buono non arriva piu' a destinazione");
assert.equal(valoreScritto(" 2.5 "), 2.5);
assert.equal(valoreScritto("true"), true);
assert.equal(valoreScritto("false"), false);
""")


def test_il_fuori_scala_non_diventa_un_numero(tmp_path):
    """Il confine della guardia. `Number("1e999")` e `Number("Infinity")` non
    sono `NaN`: passavano come numeri, e `JSON.stringify` li scrive **`null`**.
    Il corpo della PUT partiva gia' azzerato, il server accettava, e su un
    campo numerico nullabile — `tet.max_volume`, dove `null` significa
    «nessun limite», o `wall.membrature_attese`, dove significa «non
    dichiarato» — chi batteva `1e999` si vedeva scrivere l'assenza al posto
    del proprio numero, con un 200 e lo schermo muto. Qui il campo intero
    serve a provare che il rifiuto arriva prima del disco, non a rappresentare
    un tetto.

    Col controllo che lo smentisce: `1e3` e' notazione esponenziale legittima e
    deve continuare a valere `1000`, altrimenti la guardia rifiuta tutto e
    l'assenza di difetti e' solo l'assenza dell'interfaccia.
    """
    _esegui(tmp_path, "import assert from 'node:assert/strict';\n" + _funzioni("valoreScritto")
            + """
for (const battuto of ["Infinity", "-Infinity", "1e999", "2e400"]) {
  assert.equal(valoreScritto(battuto), battuto,
    `${battuto} diventa un numero, e JSON.stringify lo scrive null`);
}
assert.equal(valoreScritto("  Infinity  "), "Infinity", "il trim non basta: resta un non finito");
assert.equal(valoreScritto("1e3"), 1000, "la notazione esponenziale legittima non passa piu'");
assert.equal(valoreScritto("2.5"), 2.5);
assert.equal(valoreScritto("-3"), -3);
""")


def test_il_fuori_scala_non_scrive_null_sul_disco(tmp_path):
    """La stessa cosa letta dal disco, che e' dove il danno si misura.

    `null` non e' piu' cio' che parte dal browser: la battuta arriva al modello,
    che su un intero la rifiuta con un 422 e lascia il file com'era. Su un
    decimale nullabile il modello oggi la **accetta** come infinito e scrive
    `.inf`: e' un residuo che sta nel modello e non qui — `allow_inf_nan=False`
    in `core/config.py`, misurato nel rapporto — e questo controllo afferma cio'
    che vale in tutti e due i casi, cosi' che quella correzione non lo rompa: il
    fronte non fabbrica piu' un `null` che nessuno ha battuto.
    """
    percorso = tmp_path / "config.yaml"
    cfg = PipelineConfig(input=InputConfig(path=tmp_path / "nuvola.ply"))
    cfg.run.out_dir = tmp_path / "corsa"
    cfg.downsample.voxel_size = 25.0
    cfg.wall.membrature_attese = 8
    save_config(cfg, percorso)
    cliente = TestClient(create_app(percorso), base_url=BASE_LOCALE, raise_server_exceptions=False)

    uscita = _esegui(tmp_path, "import assert from 'node:assert/strict';\n"
                     + _funzioni("valoreScritto")
                     + 'process.stdout.write(JSON.stringify(valoreScritto("1e999")));')
    assert json.loads(uscita) == "1e999", (
        "il browser manda un valore che nessuno ha battuto: JSON.stringify scrive null"
    )

    configurazione = cliente.get("/api/config").json()
    prima = percorso.read_bytes()

    configurazione["wall"]["membrature_attese"] = json.loads(uscita)
    rifiuto = cliente.put("/api/config", json=configurazione)
    assert rifiuto.status_code == 422, "il fuori scala e' stato accettato su un intero"
    assert percorso.read_bytes() == prima, "il conto atteso delle membrature e' cambiato su disco"

    configurazione = cliente.get("/api/config").json()
    configurazione["downsample"]["voxel_size"] = json.loads(uscita)
    cliente.put("/api/config", json=configurazione)
    assert "voxel_size: null" not in percorso.read_text(encoding="utf-8"), (
        "il campo e' stato azzerato dal browser, non dal modello"
    )


def test_una_battuta_illeggibile_non_cambia_la_configurazione_su_disco(tmp_path):
    """La catena intera, dai tasti al file: il valore lo produce la funzione
    vera di `app.js` in `node`, la PUT e' quella vera del server, e il file e'
    quello della corsa. La regressione era esattamente qui — `voxel_size` che
    tornava a `None`, la configurazione scritta su disco, e a video niente.

    Il caso simmetrico e' nello stesso controllo apposta: un rifiuto che
    rifiuta tutto passerebbe la prima meta' e lascerebbe l'interfaccia inutile.
    """
    percorso = tmp_path / "config.yaml"
    cfg = PipelineConfig(input=InputConfig(path=tmp_path / "nuvola.ply"))
    cfg.run.out_dir = tmp_path / "corsa"
    save_config(cfg, percorso)
    cliente = TestClient(create_app(percorso), base_url=BASE_LOCALE, raise_server_exceptions=False)

    def scritto(battuto: str) -> object:
        uscita = _esegui(tmp_path, "import assert from 'node:assert/strict';\n"
                         + _funzioni("valoreScritto")
                         + "process.stdout.write(JSON.stringify(valoreScritto("
                         + json.dumps(battuto) + ")));")
        return json.loads(uscita)

    configurazione = cliente.get("/api/config").json()
    prima = percorso.read_bytes()

    configurazione["downsample"]["voxel_size"] = scritto("1e")
    rifiuto = cliente.put("/api/config", json=configurazione)
    assert rifiuto.status_code == 422, "il valore illeggibile e' stato accettato"
    assert percorso.read_bytes() == prima, "la configurazione della corsa e' cambiata su disco"

    # La ragione che finisce a video la ricava la funzione vera del modulo dal
    # corpo vero del rifiuto: senza questo pezzo il rifiuto ci sarebbe e non si
    # vedrebbe, che e' meta' del difetto.
    ragione = _esegui(tmp_path, "import assert from 'node:assert/strict';\n"
                      + _funzioni("ragioneDelRifiuto")
                      + "const risposta = { status: 422, text: async () => "
                      + json.dumps(rifiuto.text) + " };\n"
                      "process.stdout.write(await ragioneDelRifiuto(risposta));")
    # Il campo per etichetta e non per chiave, e la ragione in italiano: la
    # regola di PRODUCT.md vale anche sotto la casella, non solo sopra.
    assert "lato del voxel" in ragione and "numero" in ragione, (
        f"la ragione non nomina il campo o non dice perche': {ragione}"
    )
    assert "voxel_size" not in ragione, f"la ragione stampa la chiave grezza: {ragione}"

    configurazione["downsample"]["voxel_size"] = scritto("2.5")
    buono = cliente.put("/api/config", json=configurazione)
    assert buono.status_code == 200, buono.text
    assert cliente.get("/api/config").json()["downsample"]["voxel_size"] == 2.5, (
        "un valore legittimo non arriva piu' a destinazione"
    )
    assert percorso.read_bytes() != prima, "il valore buono non e' stato scritto su disco"



def test_una_corsa_illeggibile_resta_nell_elenco_d_ingresso_e_non_si_apre(tmp_path):
    """La schermata d'ingresso, eseguita, sul caso che il server dichiara rotto.

    Le tre meta' sono una decisione sola: la riga resta (una corsa sparita e'
    indistinguibile da una mai esistita), non si apre (legarla lascerebbe ogni
    pannello su un percorso che nessun endpoint sa caricare), e resta
    raggiungibile da tastiera e annunciata -- e' l'unica voce che porta una
    spiegazione, e `disabled` la toglierebbe proprio a chi quella spiegazione
    serve di piu'. Percio' `aria-disabled` e un gestore che si ferma da se'.
    """
    _esegui(tmp_path, _DOM + _funzioni(
        "ragioneDelRifiuto", "serverMuto", "superata", "corpoLetto",
        "apriIngresso", "disegnaIngresso",
    ) + """
const rigaErroreIngresso = document.getElementById("ingresso-errore");
let ultimoIngresso = 0;
let chiamate = 0;
globalThis.fetch = async () => {
  chiamate += 1;
  return { ok: true, status: 200, json: async () => ({
    radice: "runs", corrente: "sana", corse: [
      { nome: "sana", nuvola: "scansione.ply",
        riferimento: false, modificata: 20, errore: null },
      { nome: "rotta", nuvola: null,
        riferimento: false, modificata: 10,
        errore: "input.path: Field required" },
    ],
  }) };
};

await disegnaIngresso();

const voci = document.getElementById("corse-elenco").children;
assert.deepEqual(voci.map((v) => v.dataset.nome), ["sana", "rotta"],
  "una corsa rotta sparita dall'elenco e' indistinguibile da una mai esistita");
assert.equal(voci[0].getAttribute("aria-disabled"), null, "una corsa buona non si apre piu'");
assert.equal(voci[1].getAttribute("aria-disabled"), "true",
  "una corsa illeggibile si lascia aprire");
assert.equal(voci[1].disabled, undefined,
  "disabled scritto sulla riga la toglie da tastiera e lettore di schermo");
assert.equal(voci[0].getAttribute("aria-current"), "true", "la corsa aperta non e' marcata");
// La sola nuvola, e niente altro: il deck e' nudo e la corsa non dichiara piu'
// un materiale. Una voce che non porta la chiave dava «— materiale non
// dichiarato», e la stessa riga con una chiave presente e vuota dava
// «undefined» appeso al percorso.
assert.equal(voci[0].children[1].textContent, "scansione.ply",
  "la riga della corsa dice ancora qualcosa sul materiale");
assert.match(voci[1].children[1].textContent, /input\\.path/,
  "la riga rotta non dice che cosa il server non e' riuscito a leggere");
assert.equal(document.getElementById("corse-vuoto").hidden, true,
  "l'elenco ha due voci e mostra lo stato vuoto");

// Il gestore della riga rotta si ferma prima della fetch: senza il ritorno in
// testa, aria-disabled sarebbe decorazione e il clic legherebbe comunque.
const prima = chiamate;
await voci[1].scatena("click");
assert.equal(chiamate, prima, "il clic su una corsa illeggibile parte lo stesso");
""")


# --------------------------------------------------------------------------
# BL-2: il gestore del campo, eseguito.
# --------------------------------------------------------------------------


def _banco_del_campo() -> str:
    """Il gestore vero del campo, con le sue dipendenze, su un DOM finto e con
    una `fetch` che decide il banco.

    Fino a ieri qui non arrivava niente: il gestore era una funzione anonima
    dentro un ciclo dentro `apriDettaglio`, e nessun banco la raggiungeva.
    Quello che si vedeva provato era la catena ricucita a mano — `valoreScritto`
    piu' `TestClient` — che e' la catena giusta ma **non e' il gestore**: il
    ripristino del valore di prima e il ramo del campo nullabile si potevano
    togliere e la suite restava verde. Adesso `campoParametro` costruisce la
    riga vera e `scriviParametro` la scrive, entrambe di primo livello apposta.
    """
    return _DOM + _funzioni(
        "valoreScritto", "ragioneDelRifiuto", "serverMuto", "superata", "corpoLetto",
        "segnalaCampo", "apriBattuta", "scriviValore", "scriviParametro",
        "testoDellAiuto", "campoParametro",
    ) + """
// Il terzo contatore di Rilievo 1, per campo: scriviParametro lo legge dal
// modulo per nome, non da un parametro, quindi il banco deve ricrearlo tale e
// quale a `generazione` e `configurazione` qui sopra.
let ultimaBattutaDelCampo = new Map();
const CAMPO = { description: "la spaziatura del voxel" };
const richieste = [];
let risponde = null;
globalThis.fetch = async (percorso, opzioni) => {
  richieste.push({ percorso, corpo: JSON.parse(opzioni.body) });
  return risponde(percorso, opzioni);
};
const accetta = (canonica) => async () => ({ ok: true, status: 200, json: async () => canonica });
const rifiuta = (corpo) => async () => ({
  ok: false, status: 422, text: async () => JSON.stringify(corpo),
});
// Il server che non risponde: `fetch` non torna un 500, solleva.
const cade = () => { throw new TypeError("fetch failed"); };
function apriCampo(blocco, nome) {
  const riga = campoParametro(blocco, nome, CAMPO, generazione);
  const [, input, , messaggio] = riga.children;
  assert.equal(input.tag, "input", "la riga non e' piu' fatta come il banco crede");
  assert.equal(messaggio.className, "errore-campo", "il messaggio non e' piu' il quarto figlio");
  return { input, messaggio };
}
"""


def test_il_nome_della_casella_e_il_nome_del_parametro_e_nient_altro(tmp_path):
    """L'aiuto stava dentro la <label> che avvolgeva la casella.

    Una <label> che avvolge nomina con tutto il proprio sottoalbero: il campo
    si annunciava «voxel_size la spaziatura del voxel» a ogni fuoco e a ogni
    tabulazione, e col rifiuto a video si accodava anche quello. La lezione era
    gia' scritta nell'ingresso -- il <small> di #nuova-nome sta fuori dalla
    <label> apposta, e il commento nel markup dice perche' -- e non aveva mai
    raggiunto i campi che il modulo costruisce da se'.

    Il banco calcola il nome come lo calcola il browser: dall'etichetta che
    punta alla casella per `for` se c'e', altrimenti da tutto il sottoalbero
    della <label> che la contiene. Cosi' il controllo non guarda che forma ha
    la riga -- puo' cambiare -- ma cio' che verrebbe letto ad alta voce.
    """
    _esegui(tmp_path, _banco_del_campo() + """
configurazione = { downsample: { voxel_size: 25 } };
const riga = campoParametro("downsample", "voxel_size", CAMPO, generazione);
const [, input, aiuto, messaggio] = riga.children;

const testoProfondo = (e) => [e.textContent, ...e.figli.map(testoProfondo)].join(" ").trim();
// Tutte le etichette associate, non la prima: una casella e' nominata sia da
// una <label for> sia da ogni <label> che la contiene, e il browser le
// concatena. Prendere solo la prima farebbe passare per corretta una riga che
// le ha entrambe -- cioe' esattamente la ricaduta da sorvegliare.
function nomeAccessibile(radice, casella) {
  const candidati = [radice, ...radice.discendenti()];
  return candidati
    .filter((e) => e.tag === "label"
      && (e.getAttribute("for") === casella.id || e.discendenti().includes(casella)))
    .map(testoProfondo)
    .join(" ")
    .trim();
}

assert.equal(
  nomeAccessibile(riga, input), "voxel_size",
  "il nome accessibile della casella si porta dietro l'aiuto: descritto e' cio' che serve, nominato no",
);
assert.equal(
  input.getAttribute("aria-describedby"), aiuto.id,
  "l'aiuto e' uscito dalla label e nessun describedby lo lega: adesso non lo annuncia piu' nessuno",
);
// Il rifiuto e' la seconda meta' dello stesso difetto: compare dentro la riga
// mentre la casella ha il fuoco, ed e' il momento in cui il nome viene riletto.
segnalaCampo(input, messaggio, "e' troppo grande");
assert.equal(
  nomeAccessibile(riga, input), "voxel_size",
  "il messaggio di rifiuto entra nel nome della casella invece di restarne la descrizione",
);
""")


def test_un_campo_nullabile_vuoto_non_mostra_la_stringa_null(tmp_path):
    """`String(null)` e' `"null"`: quattro parole in una casella dove `null`
    significa «lascia decidere alla misura», e chi la riscrive senza toccarla
    manda al modello la stringa `null`, che non e' un numero.
    """
    _esegui(tmp_path, _banco_del_campo() + """
configurazione = {
  downsample: { voxel_size: null },
  segment: { crop_min: [1, 2, 3], crop_max: null },
};
const { input } = apriCampo("downsample", "voxel_size");
assert.equal(input.value, "", "un campo nullabile vuoto mostra la stringa null");
// Anche dove il tipo lo dichiara lo schema: `crop_max` e' una tupla
// nullabile, e `JSON.stringify(null)` e' la stringa "null" -- le stesse
// quattro lettere in un campo che e' vuoto.
const composto = campoParametro("segment", "crop_max",
  { description: "", tipo: "composto", nullabile: true }, generazione);
assert.equal(composto.children[1].value, "",
  "un composto nullabile vuoto mostra la stringa null");
// Una tupla non e' scritta in una casella di testo: String() la renderebbe
// "1,2,3", cioe' un testo che nessuna lettura produce. readOnly e non disabled,
// che la toglierebbe anche dal lettore di schermo.
const tupla = apriCampo("segment", "crop_min");
assert.equal(tupla.input.value, "[1,2,3]", "la lista finisce nel campo come testo di nessuno");
assert.equal(tupla.input.readOnly, true, "una lista diventa modificabile e ogni modifica e' rifiutata");
assert.equal((tupla.input.gestori.change ?? []).length, 0, "la lista manda una PUT a ogni battuta");
""")


def test_un_enumerazione_diventa_un_menu_e_un_valore_solo_una_casella_bloccata(tmp_path):
    """I valori ammessi li conosce il modello e adesso lo schema li porta: una
    casella di testo dove si puo' battere di tutto rimanda al 422 una scelta
    che era gia' nota qui.

    Un `Literal` con un valore solo non prende un menu: un menu che non offre
    scelte e' un menu che mente. Resta il valore, in un campo bloccato.
    """
    _esegui(tmp_path, _banco_del_campo() + """
configurazione = { segment: { method: "auto" }, surface: { method: "poisson" } };
const menu = campoParametro("segment", "method",
  { description: "", tipo: "enumerazione", valori: ["crop", "auto"], nullabile: false }, generazione);
const scelta = menu.children[1];
assert.equal(scelta.tag, "select",
  "un'enumerazione resta una casella dove si puo' battere qualunque cosa");
assert.deepEqual(scelta.figli.map((o) => o.value), ["crop", "auto"],
  "il menu non offre i valori che il modello ammette");
assert.equal(scelta.value, "auto", "il menu non parte dal valore della configurazione");

scelta.value = "crop";
risponde = accetta({ segment: { method: "crop" }, surface: { method: "poisson" } });
await scelta.scatena("change");
assert.deepEqual(richieste.map((r) => r.corpo.segment.method), ["crop"],
  "la scelta dal menu non arriva al disco");

const unico = campoParametro("surface", "method",
  { description: "", tipo: "enumerazione", valori: ["poisson"], nullabile: false }, generazione);
const bloccato = unico.children[1];
assert.notEqual(bloccato.tag, "select", "un menu con una voce sola offre una scelta che non c'e'");
assert.equal(bloccato.value, "poisson", "il campo bloccato non mostra il valore");
assert.equal(bloccato.readOnly, true, "il campo bloccato si lascia scrivere");
assert.equal((bloccato.gestori.change ?? []).length, 0, "il campo bloccato manda comunque una PUT");
""")


def test_un_booleano_diventa_una_spunta_e_l_etichetta_viene_dallo_schema(tmp_path):
    """«Una chiave non si stampa mai, si stampa la sua etichetta»: dove lo
    schema porta un'etichetta la casella la mostra, dove non c'e' resta la
    chiave, che e' l'unica cosa che si sa.

    La spunta scrive un booleano vero e non la stringa «true»: e' il valore
    che `valoreScritto` produce dal testo lasciato nel campo, e la spunta deve
    lasciarcelo.
    """
    _esegui(tmp_path, _banco_del_campo() + """
configurazione = { simplify: { enabled: false, taubin_iterations: 0 } };
const riga = campoParametro("simplify", "enabled", {
  description: "", tipo: "booleano", nullabile: false,
  etichetta: "rifà i triangoli a misura uniforme",
}, generazione);
const [etichetta, spunta] = riga.children;
assert.equal(etichetta.textContent, "rifà i triangoli a misura uniforme",
  "la riga stampa la chiave grezza anche dove lo schema porta un'etichetta");
assert.equal(spunta.type, "checkbox", "un booleano resta una casella dove si batte true o false");
assert.equal(spunta.checked, false, "la spunta non parte dal valore della configurazione");

spunta.checked = true;
risponde = accetta({ simplify: { enabled: true, taubin_iterations: 0 } });
await spunta.scatena("change");
assert.deepEqual(richieste.map((r) => r.corpo.simplify.enabled), [true],
  "la spunta non scrive un booleano");

// Senza etichetta la chiave resta la chiave: nessuna frase inventata.
const senza = campoParametro("simplify", "taubin_iterations",
  { description: "", tipo: "intero", ge: 0, nullabile: false }, generazione);
assert.equal(senza.children[0].textContent, "taubin_iterations",
  "un campo senza etichetta ne prende una inventata");
""")


def test_un_numero_con_due_estremi_prende_lo_slider_e_i_due_versi_restano_uniti(tmp_path):
    """Lo slider da solo non basta: non sa mostrare il valore esatto e non sa
    rappresentare un valore fuori dal proprio intervallo. La casella accanto
    e' quella che scrive, e i due versi si tengono uniti.

    Il passo lo chiede il tipo: un intero si muove di 1, un reale fra 0 e 1
    no. E l'inclusivita' conta: `lt` non e' `le`, e un cursore che li
    confondesse offrirebbe un valore che il modello rifiuta.

    La casella accanto non e' `type="number"`: e' la sanificazione silenziosa
    di Chrome — battuto `1e`, `.value` torna `""` — che aveva azzerato la
    configurazione di una corsa senza dirlo.
    """
    _esegui(tmp_path, _banco_del_campo() + """
configurazione = { surface: { density_quantile: 0.05, poisson_depth: 9 } };
const riga = campoParametro("surface", "density_quantile",
  { description: "", tipo: "reale", ge: 0.0, lt: 1.0, nullabile: false }, generazione);
const [, cursore, casella, , messaggio] = riga.children;
assert.equal(cursore.type, "range", "un numero con entrambi gli estremi non prende il cursore");
assert.notEqual(casella.type, "number",
  'type="number" sanifica in silenzio: cio\\' che il browser non legge diventa ""');
assert.equal(Number(cursore.step), 0.01, "il cursore di un reale fra 0 e 1 si muove di 1");
assert.equal(Number(cursore.min), 0, "un estremo incluso e' stato spostato come se fosse escluso");
assert.equal(Number(cursore.max), 0.99, "il cursore offre 1.0, che `lt` esclude e il modello rifiuta");
assert.equal(cursore.value, "0.05", "il cursore non parte dal valore della configurazione");

// Dal cursore alla casella, e da li' al disco.
cursore.value = "0.5";
await cursore.scatena("input");
assert.equal(casella.value, "0.5", "la casella non segue il cursore");
risponde = accetta({ surface: { density_quantile: 0.5, poisson_depth: 9 } });
await cursore.scatena("change");
assert.deepEqual(richieste.map((r) => r.corpo.surface.density_quantile), [0.5],
  "il cursore non scrive niente sul disco");

// E il verso opposto: battuto nella casella, il cursore si sposta.
casella.value = "0.2";
risponde = accetta({ surface: { density_quantile: 0.2, poisson_depth: 9 } });
await casella.scatena("change");
assert.equal(cursore.value, "0.2", "il cursore resta fermo su un valore che non c'e' piu'");
assert.equal(messaggio.hidden, true, "un valore accettato porta un messaggio d'errore");

// Un intero si muove di 1.
const intero = campoParametro("surface", "poisson_depth",
  { description: "", tipo: "intero", ge: 4, le: 14, nullabile: false }, generazione);
assert.equal(Number(intero.children[1].step), 1, "il cursore di un intero non si muove di 1");
""")


def test_senza_due_estremi_o_col_vuoto_ammesso_la_casella_resta_di_testo(tmp_path):
    """Tre casi che il cursore non sa reggere, e la casella di testo si'.

    Un estremo solo: un cursore senza fondo scala e' un cursore su un
    intervallo inventato. Un nullabile: il vuoto significa «decidi tu», e
    nessuna posizione del cursore lo esprime — `voxel_size` e `max_hole_area`
    sono esattamente questo, e devono poter tornare vuoti. Un tipo che lo
    schema non dichiara, o che il pannello non riconosce: casella di testo e
    nessuna eccezione, perche' una forma sconosciuta non deve spegnere il
    pannello.
    """
    _esegui(tmp_path, _banco_del_campo() + """
configurazione = { normals: { knn: 30 }, downsample: { voxel_size: 3.0 }, ignoto: { boh: "x" } };

const solo = campoParametro("normals", "knn",
  { description: "", tipo: "intero", gt: 2, nullabile: false }, generazione);
assert.equal(solo.children[1].type ?? "text", "text",
  "un cursore senza fondo scala e' un cursore su un intervallo inventato");

const nullabile = campoParametro("downsample", "voxel_size",
  { description: "", tipo: "reale", gt: 0.0, le: 100.0, nullabile: true }, generazione);
const casella = nullabile.children[1];
assert.equal(casella.type ?? "text", "text", "il cursore non sa esprimere il vuoto");
// E il vuoto deve poterci tornare: e' il valore che dice «decidi tu».
casella.value = "";
risponde = accetta({ normals: { knn: 30 }, downsample: { voxel_size: null }, ignoto: { boh: "x" } });
await casella.scatena("change");
assert.deepEqual(richieste.map((r) => r.corpo.downsample.voxel_size), [null],
  "un campo nullabile svuotato non torna a null");
assert.equal(casella.value, "", "il campo vuoto mostra la stringa null");

const ignoto = campoParametro("ignoto", "boh",
  { description: "", tipo: "quadrimensionale", nullabile: false }, generazione);
assert.equal(ignoto.children[1].type ?? "text", "text",
  "un tipo che il pannello non riconosce non ricade sulla casella di testo");
assert.equal(ignoto.children[1].value, "x");
assert.notEqual(ignoto.children[1].readOnly, true, "un tipo sconosciuto diventa di sola lettura");
""")


def test_una_forma_che_non_sa_mostrare_il_valore_gia_scritto_non_lo_cancella(tmp_path):
    """La configurazione di una corsa vecchia puo' portare un valore che il
    dominio di oggi non ammette piu'. Un `<select>` non ha una voce per
    mostrarlo e una spunta non ha una terza posizione: sceglierli lo
    cancellerebbe alla prima riscrittura del pannello, in silenzio. Chi apre
    quella corsa deve vedere che cosa c'e' scritto, non un campo azzerato.
    """
    _esegui(tmp_path, _banco_del_campo() + """
configurazione = { segment: { method: "kmeans" }, simplify: { enabled: "forse" } };
const fuori = campoParametro("segment", "method",
  { description: "", tipo: "enumerazione", valori: ["crop", "auto"], nullabile: false }, generazione);
assert.notEqual(fuori.children[1].tag, "select",
  "il menu non ha una voce per «kmeans»: il valore scritto sparisce dallo schermo");
assert.equal(fuori.children[1].value, "kmeans", "il valore gia' scritto e' stato cancellato");

const spunta = campoParametro("simplify", "enabled",
  { description: "", tipo: "booleano", nullabile: false }, generazione);
assert.notEqual(spunta.children[1].type, "checkbox",
  "una spunta non ha una posizione per «forse»: il valore scritto sparisce dallo schermo");
assert.equal(spunta.children[1].value, "forse", "il valore gia' scritto e' stato cancellato");
""")


def test_i_campi_di_un_blocco_assente_restano_in_sola_lettura(tmp_path):
    """Un campo di un blocco che la configurazione non porta non si scrive uno
    alla volta: la PUT manderebbe un blocco a meta'. Il blocco intero si
    dichiara dal file di configurazione, e qui la casella resta in sola
    lettura — anche dove il tipo, da solo, chiederebbe un cursore o una
    spunta.
    """
    _esegui(tmp_path, _banco_del_campo() + """
configurazione = { simplify: { enabled: true } };
const riga = campoParametro("analysis", "set_tolerance_factor",
  { description: "", tipo: "reale", gt: 0.0, le: 20.0, nullabile: false }, generazione);
assert.equal(riga.childElementCount, 4, "un blocco assente ha comunque preso il cursore");
const casella = riga.children[1];
assert.equal(casella.readOnly, true, "un campo di un blocco assente si lascia scrivere");
assert.equal((casella.gestori.change ?? []).length, 0,
  "un campo di un blocco assente manda una PUT con il blocco a meta'");
""")


def test_il_campo_mostra_il_valore_che_il_server_ha_accettato(tmp_path):
    """Il campo continuava a mostrare la battuta anche quando sul disco era
    finito un altro numero: `1_0` diventa `10.0`, `1e1_0` diventa dieci
    miliardi, `0x10` diventa `16.0`, `9.0` su un intero diventa `9`, `no`
    diventa `false`. Tutte con 200 e schermo muto.

    Riscrivere la casella con cio' che il server ha risposto le rende visibili
    in blocco, invece che una difesa per ogni grafia: a video finisce cio' che
    e' stato salvato.
    """
    _esegui(tmp_path, _banco_del_campo() + """
configurazione = { downsample: { voxel_size: 25 }, normals: { knn: 30 } };
const { input, messaggio } = apriCampo("downsample", "voxel_size");
assert.equal(input.value, "25", "il campo non parte dal valore della configurazione");
input.value = "1_0";
risponde = accetta({ downsample: { voxel_size: 10.0 }, normals: { knn: 30 } });
await input.scatena("change");
assert.deepEqual(
  richieste.map((r) => [r.percorso, r.corpo.downsample.voxel_size]), [["/api/config", "1_0"]],
  "cio' che il browser non legge non arriva piu' al modello, che e' l'unico che lo sa leggere",
);
assert.equal(input.value, "10", "il campo mostra la battuta e sul disco c'e' un altro numero");
assert.equal(configurazione.downsample.voxel_size, 10, "in memoria resta la battuta");
assert.equal(messaggio.hidden, true, "un campo accettato porta un messaggio d'errore");
assert.equal(input.getAttribute("aria-invalid"), null);
assert.ok(!input.className.includes("campo-rifiutato"));
""")


def test_il_valore_rifiutato_non_resta_nella_configurazione(tmp_path):
    """La PUT manda l'**intera** configurazione: un valore rifiutato lasciato
    dentro farebbe rifiutare ogni modifica successiva accusando il campo
    sbagliato. E il rifiuto va detto su tre canali, perche' due su tre lasciano
    fuori qualcuno.
    """
    _esegui(tmp_path, _banco_del_campo() + """
configurazione = { downsample: { voxel_size: 25 } };
const { input, messaggio } = apriCampo("downsample", "voxel_size");
input.value = "1e";
risponde = rifiuta({ detail: [
  { loc: ["body", "downsample", "voxel_size"], msg: "Input should be a valid number" },
] });
await input.scatena("change");
assert.equal(configurazione.downsample.voxel_size, 25,
  "il valore rifiutato resta in memoria: la prossima modifica sara' accusata al posto suo");
assert.equal(input.value, "1e", "la battuta rifiutata sparisce: non si vede piu' che correggere");
assert.match(messaggio.textContent, /downsample\\.voxel_size: Input should be a valid number/);
assert.equal(messaggio.hidden, false, "la ragione c'e' ma resta nascosta");
assert.equal(input.getAttribute("aria-invalid"), "true");
assert.equal(input.getAttribute("aria-errormessage"), messaggio.id,
  "aria-invalid da solo dice che c'e' un errore, mai quale");
assert.ok(input.className.includes("campo-rifiutato"));
""")


def test_il_server_caduto_non_manda_il_valore_con_la_modifica_di_un_altro_campo(tmp_path):
    """Il bloccante peggiore, perche' il valore trasportato e' arbitrario.

    `fetch` **solleva** quando il server non risponde — fermo, riavviato, la
    rete caduta — e l'eccezione usciva dal gestore: niente messaggio a video, e
    niente ripristino, che stava solo nel ramo del rifiuto. Il valore restava in
    `configurazione`, che e' di modulo, e partiva con la PUT successiva, quella
    di un altro campo. L'utente toccava `knn` e sul disco cambiava anche
    `voxel_size`, senza che nulla lo avesse mai detto.
    """
    _esegui(tmp_path, _banco_del_campo() + """
configurazione = { downsample: { voxel_size: 25 }, normals: { knn: 30 } };
const voxel = apriCampo("downsample", "voxel_size");
const knn = apriCampo("normals", "knn");

voxel.input.value = "3.5";
risponde = cade;
await voxel.input.scatena("change");
assert.equal(configurazione.downsample.voxel_size, 25,
  "il valore resta in memoria e lo portera' su disco la prima modifica riuscita");
assert.equal(voxel.messaggio.hidden, false, "il server non ha risposto e lo schermo tace");
assert.match(voxel.messaggio.textContent, /il server non ha risposto/);
assert.equal(voxel.input.getAttribute("aria-invalid"), "true");

knn.input.value = "31";
risponde = accetta({ downsample: { voxel_size: 25 }, normals: { knn: 31 } });
await knn.input.scatena("change");
assert.equal(richieste.length, 2, "il banco non ha mandato le due PUT che sta guardando");
const ultima = richieste[1].corpo;
assert.equal(ultima.normals.knn, 31, "la modifica dell'utente non arriva piu' a destinazione");
assert.equal(ultima.downsample.voxel_size, 25,
  "l'utente ha toccato knn e sul disco cambia anche voxel_size, che non ha mai visto");
""")


# --------------------------------------------------------------------------
# La didascalia del ritaglio.
# --------------------------------------------------------------------------


def test_la_didascalia_del_ritaglio_dice_di_quale_numero_si_tratta(tmp_path):
    """`/api/crop` dice fin dove arriva l'anteprima con `completo`. Quando lo
    step 2 prosegue oltre il ritaglio con i piani e i cluster ne tiene molti
    meno — 5 602 di anteprima contro 84 su una nuvola di prova — quindi
    affermare li' che quello e' il conteggio dello step 2 e' un numero falso con
    una didascalia che lo garantisce.

    Il controllo guarda le due affermazioni, non le parole con cui sono fatte:
    incompleta deve dire che lo step prosegue **e non** affermare la
    coincidenza; completa deve affermarla e non parlare di seguito. La
    didascalia unica di prima — quella che afferma sempre — fallisce il primo
    caso, che e' esattamente il difetto che questa riga chiude.
    """
    pezzi = [p.split(";", 1)[0] for p in _modulo().split("esito.textContent =")[1:]]
    espressione = next(p for p in pezzi if "points_after" in p)
    uscita = _esegui(tmp_path, "import assert from 'node:assert/strict';\n"
                     # Le parentesi non sono ornamento: l'espressione comincia
                     # con un a capo, e `return` seguito da un a capo torna
                     # undefined invece di quello che c'e' scritto sotto.
                     "function didascalia(corpo) { return (" + espressione + "); }\n" + """
const parziale = didascalia({ points_after: 5602, completo: false });
const intero = didascalia({ points_after: 84, completo: true });
const COINCIDENZA = /\u00e8 quanti ne terrebbe lo step 2/;
const SEGUITO = /prosegue/;
assert.match(parziale, SEGUITO,
  "l'anteprima non e' tutto lo step 2 e la didascalia non dice che lo step prosegue");
assert.doesNotMatch(parziale, COINCIDENZA,
  "l'anteprima non e' tutto lo step 2 e la didascalia la spaccia per tale");
assert.match(intero, COINCIDENZA,
  "l'anteprima e' tutto lo step 2 e la didascalia non lo dice piu'");
assert.doesNotMatch(intero, SEGUITO,
  "l'anteprima e' tutto lo step 2 e la didascalia se ne scusa");
assert.ok(parziale.includes((5602).toLocaleString("it")), "il numero non compare");
assert.ok(intero.includes((84).toLocaleString("it")), "il numero non compare");
for (const testo of [parziale, intero]) {
  assert.match(testo, /spigoli del box sono stati scritti/,
    "il bottone dice Applica: chi lo preme deve sapere che ha scritto");
  assert.doesNotMatch(testo, /crop_min|crop_max/,
    "la didascalia stampa la chiave grezza invece dell'etichetta");
}
""")
    assert uscita == ""


# --------------------------------------------------------------------------
# L'esportazione: il comando che porta fuori il deck, nel pannello dello step
# che lo ha scritto.
# --------------------------------------------------------------------------


def _banco_del_deck(voce: dict) -> str:
    """Il pannello costruito dalla funzione vera su una sola voce di registro.

    E' il registro a dire tutto quello che il pannello decide: se il deck e'
    stato scritto (`artefatto`) e se lo e' stato con i parametri di adesso
    (`stato`, che vale "non valido" quando l'impronta salvata non coincide piu'
    con quella della configurazione corrente -- vedi `steps.run_state`).
    """
    return _DOM + _costante("STEP_CON_DECK") + _funzioni("pannelloDeck") + f"""
ultimoStato = [{json.dumps(voce)}];
const pannello = pannelloDeck();
const collegamenti = pannello.discendenti().filter((e) => e.tag === "a");
const testo = pannello.discendenti().map((e) => e.textContent).join(" ");
const AVVISO = /parametri diversi/;
"""


def test_il_deck_scritto_si_scarica_dal_pannello_dello_step_11(tmp_path):
    """Un collegamento vero a `/api/deck`, non un bottone che fabbrica il file
    in memoria: e' il browser a scaricare, ed e' la tratta a dire con che nome.

    Nessun avviso quando l'impronta coincide: un cartello che comparisse sempre
    smetterebbe di dire qualcosa il giorno in cui e' vero.
    """
    _esegui(tmp_path, _banco_del_deck(
        {"numero": 11, "chiave": "11_export", "stato": "valido", "artefatto": "wall_model.inp"},
    ) + """
assert.equal(collegamenti.length, 1, "il pannello dello step 11 non porta il comando");
assert.equal(collegamenti[0].href, "/api/deck");
assert.doesNotMatch(testo, AVVISO, "il deck coincide coi parametri e il pannello se ne scusa");
""")


def test_senza_deck_scritto_il_pannello_nomina_lo_step_invece_del_file(tmp_path):
    """Ingresso degenere: lo step 11 non e' mai stato eseguito.

    Il comando non c'e' -- un collegamento a un file che non esiste porterebbe
    su un corpo d'errore invece che su un file -- e al suo posto c'e' la riga
    che dice quale step lo scrive. Chi guarda l'interfaccia ragiona per step.
    """
    _esegui(tmp_path, _banco_del_deck(
        {"numero": 11, "chiave": "11_export", "stato": "mai eseguito", "artefatto": None},
    ) + """
assert.equal(collegamenti.length, 0, "il pannello offre un deck che non e' stato scritto");
assert.match(testo, /step 11/, "il pannello non dice quale step scrive il deck");
""")


def test_un_deck_piu_vecchio_dei_parametri_si_scarica_e_lo_dichiara(tmp_path):
    """Ingresso degenere: il deck su disco e' stato scritto da una
    configurazione diversa da quella a video.

    Si consegna lo stesso -- e' il file che sta sul disco, quello di cui il
    registro porta l'impronta -- ma il pannello non lo puo' spacciare per il
    modello dei parametri mostrati accanto. L'interfaccia non lo deduce: e' lo
    stato "non valido" del registro, cioe' l'impronta che non coincide piu'.
    """
    _esegui(tmp_path, _banco_del_deck(
        {"numero": 11, "chiave": "11_export", "stato": "non valido",
         "artefatto": "wall_model.inp"},
    ) + """
assert.equal(collegamenti.length, 1, "un deck scritto resta scaricabile com'e'");
assert.match(testo, AVVISO, "il pannello spaccia per corrente un deck che non lo e'");
""")


# --------------------------------------------------------------------------
# Rilievo 1 (giro 2): l'ordine fra risposte, alla granularita' del campo.
#
# `superata(ordine)` lega la guardia alla generazione del clic che ha aperto
# il pannello: due battute sullo stesso campo, nello stesso pannello, portano
# lo stesso `ordine`, e la guardia non le distingue. E' il terzo requisito
# dello stesso difetto gia' corretto due volte su questo file (`generazione`
# per i clic, `ultimaGeometria` per le richieste di geometria) — qui la
# granularita' giusta e' il campo, non il pannello.
# --------------------------------------------------------------------------


def test_apriBattuta_apre_in_ordine_e_non_confonde_due_campi(tmp_path):
    """La meta' pura della guardia, eseguita da sola: sale di uno per campo,
    comincia da 1, e due campi diversi non condividono il contatore. L'altra
    meta' — l'uso vero dentro `scriviParametro` — e' nel banco piu' sotto."""
    _esegui(tmp_path, "import assert from 'node:assert/strict';\n"
            "let ultimaBattutaDelCampo = new Map();\n"
            + _funzioni("apriBattuta") + """
assert.equal(apriBattuta("downsample.voxel_size"), 1, "la prima battuta di un campo non parte da 1");
assert.equal(apriBattuta("downsample.voxel_size"), 2, "la battuta sullo stesso campo non sale");
assert.equal(apriBattuta("normals.knn"), 1, "due campi diversi condividono il contatore");
assert.equal(ultimaBattutaDelCampo.get("downsample.voxel_size"), 2,
  "la mappa non tiene l'ultima battuta registrata per quel campo");
assert.equal(ultimaBattutaDelCampo.get("normals.knn"), 1);
""")


def test_scriviparametro_guarda_anche_la_battuta_del_campo_per_iscritto():
    """Il contratto per iscritto, cosi' una modifica futura che tolga la
    guardia lo dice senza dover eseguire `node`. Non basta da solo — una
    guardia scritta e resa inerte passerebbe questo controllo — percio' il
    controllo che conta e' quello che esegue, subito sotto."""
    # `scriviValore` e non `scriviParametro`: la parte che parla col server e'
    # una sola, e da li' passano anche i due comandi composti dello step 1.
    corpo = _sorgente_di("scriviValore", _modulo())
    assert "apriBattuta(chiave)" in corpo, "la battuta non si apre piu' per campo"
    assert "superata(battuta, ultimaBattutaDelCampo.get(chiave))" in corpo, (
        "la guardia sulla battuta del campo e' sparita: due scritture sullo stesso "
        "campo tornano a condividere solo l'ordine del pannello, ed e' esattamente "
        "il difetto tornato una quarta volta"
    )


def test_la_risposta_della_battuta_piu_vecchia_sullo_stesso_campo_non_vince(tmp_path):
    """L'ingresso concreto di Rilievo 1. Due battute sullo stesso campo, nello
    stesso pannello aperto (stesso `ordine`): la prima e' lenta, la seconda
    parte dopo e arriva prima. Senza la guardia per campo, la risposta della
    prima — che descrive un valore piu' vecchio di quello che l'utente ha gia'
    scritto — vince perche' arriva per ultima, e la prossima PUT su un altro
    campo la riporterebbe sul disco sopra il valore vero.

    Il controllo che smentisce e' nello stesso banco: due scritture in ordine
    normale (nessun accavallamento) devono continuare a funzionare, altrimenti
    la guardia rifiuta tutto e non e' una correzione.
    """
    _esegui(tmp_path, _banco_del_campo() + """
// --- il caso che rompeva: risposte invertite -------------------------------
configurazione = { downsample: { voxel_size: 1 } };
const campo = apriCampo("downsample", "voxel_size");

let risolvi1, risolvi2;
const risposte = [
  new Promise((r) => { risolvi1 = r; }),
  new Promise((r) => { risolvi2 = r; }),
];
let chiamata = 0;
globalThis.fetch = async (percorso, opzioni) => {
  richieste.push({ percorso, corpo: JSON.parse(opzioni.body) });
  return risposte[chiamata++];
};

campo.input.value = "1";
const primaBattuta = scriviParametro("downsample", "voxel_size", campo.input, campo.messaggio, generazione);
campo.input.value = "2";
const secondaBattuta = scriviParametro("downsample", "voxel_size", campo.input, campo.messaggio, generazione);

// La risposta della seconda battuta (l'ultima che l'utente ha davvero
// scritto) arriva per prima; quella della prima, piu' vecchia, rientra dopo.
risolvi2({ ok: true, status: 200, json: async () => ({ downsample: { voxel_size: 2 } }) });
await secondaBattuta;
risolvi1({ ok: true, status: 200, json: async () => ({ downsample: { voxel_size: 1 } }) });
await primaBattuta;

assert.equal(configurazione.downsample.voxel_size, 2,
  "la risposta della battuta vecchia ha scritto sopra quella nuova in memoria");
assert.equal(campo.input.value, "2",
  "il campo torna a mostrare la battuta vecchia dopo che l'utente ha gia' scritto la nuova");

// --- il controllo che smentisce: ordine normale, nessun accavallamento -----
globalThis.fetch = async (percorso, opzioni) => {
  richieste.push({ percorso, corpo: JSON.parse(opzioni.body) });
  return { ok: true, status: 200, json: async () => ({ downsample: { voxel_size: 3 } }) };
};
campo.input.value = "3";
await scriviParametro("downsample", "voxel_size", campo.input, campo.messaggio, generazione);
assert.equal(configurazione.downsample.voxel_size, 3,
  "una scrittura normale, senza accavallamento, smette di funzionare");
assert.equal(campo.input.value, "3");
""")


def test_scriviparametro_200_illeggibile_non_va_in_crash_ne_ripristina_ne_cachea(tmp_path):
    """Rilievo 2 sul terzo `.json()`: la conferma di una PUT accettata. Tre
    corpi spazzatura — JSON invalido, JSON valido ma senza il blocco appena
    scritto, e il `null` letterale — non devono far sollevare il gestore, non
    devono ripristinare `precedente` (la PUT e' stata accettata: il valore
    vecchio in memoria scriverebbe sopra quello vero alla prossima modifica di
    un altro campo, lo stesso guasto di BL-2), e non devono entrare in
    `configurazione`.

    Il `null` letterale e' il caso che la correzione di questo giro chiude:
    prima, `salvata === undefined` lasciava passare `null`, e
    `salvata[blocco]` (senza `?.` sul primo livello — solo il secondo,
    `?.[nome]`, era protetto) sollevava fuori da ogni catch.
    """
    _esegui(tmp_path, _banco_del_campo() + """
for (const corpoRotto of [
  async () => { throw new SyntaxError("non e' JSON"); },
  async () => ({ normals: { knn: 30 } }),  // valido, ma senza il blocco downsample
  async () => null,                        // null letterale: mai legittimo qui
]) {
  configurazione = { downsample: { voxel_size: 9 } };
  const campo = apriCampo("downsample", "voxel_size");
  campo.input.value = "12";
  risponde = async () => ({ ok: true, status: 200, json: corpoRotto });
  await campo.input.scatena("change");
  assert.equal(configurazione.downsample.voxel_size, 12,
    "un 200 accettato ma illeggibile ripristina un valore che il server ha gia' scritto");
  assert.equal(campo.messaggio.hidden, false, "un 200 illeggibile non deve restare muto");
  assert.match(campo.messaggio.textContent, /non ne ha confermato/);
}
""")


# --------------------------------------------------------------------------
# Rilievo 2, il resto del censimento: caricaStato e apriDettaglio.
# --------------------------------------------------------------------------


def test_corpoLetto_distingue_illeggibile_da_null(tmp_path):
    """La difesa unica che protegge i sei punti di `app.js` che leggevano
    `risposta.json()` senza guardia (il censimento e' nel rapporto). `undefined`
    marca "non si legge"; `null` resta `null`, perche' e' cio' che il server ha
    davvero risposto — la stessa distinzione che `valoreScritto` fa sui campi
    nullabili."""
    _esegui(tmp_path, "import assert from 'node:assert/strict';\n" + _funzioni("corpoLetto") + """
const buono = { json: async () => ({ a: 1 }) };
assert.deepEqual(await corpoLetto(buono), { a: 1 }, "un corpo buono non arriva piu' intatto");
const nullo = { json: async () => null };
assert.equal(await corpoLetto(nullo), null, "un null vero diventa qualcos'altro");
const rotto = { json: async () => { throw new SyntaxError("non e' JSON"); } };
assert.equal(await corpoLetto(rotto), undefined, "il corpo illeggibile continua a sollevare fuori da qui");
""")


def test_ogni_lettura_di_un_corpo_passa_da_corpoLetto():
    """Il censimento per iscritto: `corpoLetto()` e' la difesa unica, e ogni
    punto che legge un corpo deve passare da li'. Un settimo punto aggiunto
    domani con `.json()` diretto invece di `corpoLetto()` torna a rompere il
    gestore su un 200 spazzatura senza che nessuno se ne accorga leggendo — e
    questo controllo lo dice senza dover eseguire `node`.

    La sottostringa letterale `.json()` si aggira scrivendo `r.json\\n()` (la
    chiamata avviene lo stesso, verificato eseguendo in node): il controllo
    tollera spazi e a capo fra `.json` e le parentesi, cosi' quella grafia
    specifica non passa piu' inosservata. Restano fuori — dichiarato, non
    taciuto — l'accesso indicizzato (`r["json"]()`, `r[j]()`) e la chiamata
    indiretta (`r.json.call(r)`), che nessuna forma testuale di questo
    controllo puo' distinguere da codice legittimo che non tocca affatto
    `.json`. Il bypass piu' realistico non e' nessuno di questi tre — e' il
    modello `.text()` + `JSON.parse()` gia' presente in `ragioneDelRifiuto`,
    copiato su un settimo punto: lo controlla il test qui sotto.
    """
    modulo = _modulo()
    corpo_funzione = _sorgente_di("corpoLetto", modulo)
    resto = modulo.replace(corpo_funzione, "", 1)
    assert resto != modulo, "corpoLetto() e' sparita dal modulo: non si estrae piu' il suo corpo"
    codice = _senza_commenti_js(resto)
    assert not re.search(r"\.json\s*\(\s*\)", codice), (
        "un punto legge risposta.json() direttamente invece di passare da corpoLetto()"
    )


def test_nessun_punto_oltre_ragioneDelRifiuto_legge_un_corpo_con_text():
    """Il bypass realistico del controllo sopra: non una grafia equivalente
    di `.json()` scritta apposta per aggirarlo, ma il modello gia' presente
    nello stesso file — `ragioneDelRifiuto` legge con `.text()` piu'
    `JSON.parse()`, non con `.json()` — copiato domani su un settimo punto,
    naturalmente, perche' e' li' e nello stesso stile. Se quel settimo punto
    dimenticasse il `try/catch` che `ragioneDelRifiuto` ha, romperebbe il
    gestore esattamente come il difetto che questo giro chiude, senza che
    lo scanner sui `.json()` se ne accorga: quello scanner non contiene
    `.json()` in nessuna forma.

    Il controllo e' grosso apposta: vieta `.text()` fuori da `corpoLetto` e
    `ragioneDelRifiuto` senza distinguere se prosegue con `JSON.parse()` o
    no, perche' la distinzione fine e' esattamente il punto cieco che ha
    aggirato la versione precedente — un settimo punto scritto con `.text()`
    e basta, senza `JSON.parse()`, sarebbe comunque un modo nuovo di leggere
    un corpo fuori dalla difesa unica.
    """
    modulo = _modulo()
    corpo_corpoLetto = _sorgente_di("corpoLetto", modulo)
    corpo_ragione = _sorgente_di("ragioneDelRifiuto", modulo)
    resto = modulo.replace(corpo_corpoLetto, "", 1).replace(corpo_ragione, "", 1)
    assert resto != modulo, "una delle due funzioni ammesse e' sparita: non si estrae piu' il suo corpo"
    codice = _senza_commenti_js(resto)
    assert ".text(" not in codice, (
        "un punto fuori da corpoLetto e ragioneDelRifiuto legge un corpo con .text(): "
        "se prosegue con JSON.parse() senza il try/catch di ragioneDelRifiuto, e' lo stesso "
        "difetto che questo giro doveva chiudere, per una grafia diversa da .json()"
    )


def _banco_di_caricaStato() -> str:
    """`caricaStato` e' l'unica tratta senza `ordine` (parte una volta sola
    all'avvio, non da un clic — vedi `test_ogni_tratta_che_interroga_il_server`
    in `test_server.py`, che la esclude per lo stesso motivo): qui si guarda
    solo che il suo `.json()`, il primo del censimento, non faccia cadere la
    pagina su un 200 spazzatura. `corpoLetto` e' estratta **dopo** `caricaStato`
    nello stesso ordine del file vero: se lo hoisting non reggesse, questo
    banco lo direbbe eseguendo, non ragionandoci sopra.
    """
    return _DOM + _funzioni(
        "caricaStato", "mostraSchermata", *_COLONNA, "dichiaraErrore", "mostraEsito", "corpoLetto",
    ) + """
let risponde = null;
globalThis.fetch = async () => risponde();
// Aperta una corsa, `caricaStato` chiede da se' la geometria piu' avanzata che
// la corsa possiede, invece di lasciare il centro dello schermo bianco fino al
// primo clic. Qui non si prova il disegno -- ha il suo banco -- ma si registra
// che cosa e' stato chiesto: e' l'unico modo di distinguere «non ha chiesto
// niente» da «ha chiesto la coda della pipeline».
let chiesto = "mai";
let stepScelto = null;
function ricaricaVista(numero) { chiesto = numero; }
// La vista si azzera quando la corsa cambia, e solo allora: il banco conta.
const vista = { azzerate: 0, azzera() { this.azzerate += 1; } };
// La schermata d'ingresso ha i propri banchi: qui serve solo che il ramo
// "nessuna corsa aperta" arrivi in fondo, per poter guardare che da li' NON
// parta nessuna richiesta di geometria.
function mostraIngresso() {}
"""


def test_una_corsa_nuova_azzera_la_vista_e_la_stessa_corsa_no(tmp_path):
    """La camera e l'orientamento a mano sono un riferimento della corsa
    (viewport.js, azzera()): cambiando corsa il pezzo e' un altro e il
    riferimento non vale piu', quindi si azzera e la prima geometria si
    rinquadra da se'. Lo stato della STESSA corsa torna da caricaStato anche
    dopo «Annulla» (annullaLaCorsa la richiama con lo stesso out_dir), e
    azzerare li' butterebbe via il gesto dell'utente a ogni ritorno.

    Mutazione che lo uccide: chiamare `vista.azzera()` senza confrontare
    `out_dir` con la corsa a video.
    """
    _esegui(tmp_path, _banco_di_caricaStato() + """
risponde = async () => ({ ok: true, status: 200, json: async () => ({ out_dir: "/tmp/corsa", steps: STEPS }) });
await caricaStato();
assert.equal(vista.azzerate, 1, "la prima corsa aperta non azzera la vista");
await caricaStato();
assert.equal(vista.azzerate, 1, "la stessa corsa riletta azzera la vista: il gesto dell'utente se ne va a ogni «Annulla»");
risponde = async () => ({ ok: true, status: 200, json: async () => ({ out_dir: "/tmp/altra", steps: STEPS }) });
await caricaStato();
assert.equal(vista.azzerate, 2, "una corsa diversa non azzera la vista: il pezzo nuovo nasce con l'orientamento del vecchio");
""")


def test_aprire_una_corsa_mostra_da_se_l_artefatto_piu_avanzato(tmp_path):
    """Il vuoto piu' grande dell'interfaccia, e l'unico che non diceva niente.

    Aperta una corsa, il centro dello schermo restava bianco -- 856x640 px
    misurati a 1568 -- finche' qualcuno non cliccava uno step. Gli artefatti
    erano gia' sul disco: non mostrarli era chiedere un gesto per far vedere che
    il programma funziona, e PRODUCT.md dichiara vincolante che l'utente
    successivo la pipeline non l'abbia mai vista.

    Si chiede la CODA della pipeline, non uno step scelto a mano:
    `passoDaMostrare` cammina a monte da li' e si ferma sul primo disegnabile,
    quindi una corsa arrivata a meta' mostra la propria meta' e una corsa vuota
    cade nel ramo che scrive «esegui lo step 1». Nessuna delle due strade e'
    nuova. E il numero viene da quanti step il server ha dichiarato, non da un
    13 battuto nel modulo: un quattordicesimo step non richiederebbe di tornare
    qui.

    `stepScelto` va scritto insieme alla richiesta: il cambio d'asse del taglio
    chiama `passoDaMostrare(stepScelto)`, e lasciandolo a null il comando del
    taglio sparirebbe al primo cambio d'asse su una geometria visibile.
    """
    _esegui(tmp_path, _banco_di_caricaStato() + """
risponde = async () => ({ ok: true, status: 200, json: async () => ({ out_dir: "/tmp/corsa", steps: STEPS }) });
await caricaStato();
assert.equal(chiesto, STEPS.length,
  "aperta una corsa non si chiede nessuna geometria: il centro resta bianco fino al primo clic");
assert.equal(stepScelto, STEPS.length,
  "stepScelto resta null: al primo cambio d'asse il comando del taglio sparisce");

// --- il controllo che smentisce: senza corsa non si chiede niente.
chiesto = "mai";
risponde = async () => ({ ok: true, status: 200, json: async () => ({ legata: false }) });
await caricaStato();
assert.equal(chiesto, "mai",
  "si chiede una geometria anche a nessuna corsa aperta, dove la schermata d'ingresso e' l'unica a video");

chiesto = "mai";
risponde = async () => ({ ok: true, status: 200, json: async () => null });
await caricaStato();
assert.equal(chiesto, "mai", "un corpo illeggibile fa comunque partire una richiesta di geometria");
""")


def test_lo_stato_vuoto_della_vista_compare_solo_dove_non_c_e_niente(tmp_path):
    """Le due meta' del vuoto, che non devono ripetersi ne' contraddirsi.

    I conteggi in alto a sinistra portano il fatto («nessuno step ha ancora
    prodotto un artefatto»); la scatola al centro porta il modello
    d'interazione, che il fatto non puo' dire: undici righe con un pallino e
    una parola somigliano a un elenco di stato molto piu' che a undici bottoni.

    E la scatola deve sparire appena si chiede una geometria, non appena una
    geometria arriva: `ricaricaVista` e' l'unico imbuto per cui la vista cambia,
    quindi si nasconde li' e si riscopre solo dal ramo in cui non c'e' proprio
    niente a monte. Lasciata accesa, la frase resterebbe stampata sopra il pezzo.
    """
    _esegui(tmp_path, _DOM + _costante("STEP_CON_GEOMETRIA") + _funzioni(
        "didascaliaDellaVista", "superata", "passoDaMostrare", "nomeDelloStep", "comandoDelFantasma", "ricaricaVista"
    ) + """
// Il velo del passaggio a monte fa una fetch e questo banco prova altro:
// stub, come riallineaTaglio e mostraStep qui accanto. Che il velo taccia
// dove la geometria a video e' gia' di un altro passaggio lo provano
// test_il_fantasma_tace_... e test_il_fantasma_dello_step_8_..., eseguendo.
function mostraFantasmaDelloStep() {}
const vuoto = document.getElementById("vista-vuota");
let allineato = "mai";
const vista = { svuota: () => {} };
function riallineaTaglio(n) { allineato = n; }
let chiesto = null;
async function mostraStep(n) { chiesto = n; return true; }

// Niente a monte: la scatola si accende.
ultimoStato = [
  { numero: 1, chiave: "01_load", artefatto: null },
  { numero: 2, chiave: "02_segment", artefatto: null },
];
ricaricaVista(2, generazione);
assert.equal(vuoto.hidden, false, "non c'e' niente a monte e il centro dello schermo resta muto");
assert.equal(
  document.getElementById("conteggi").textContent,
  "nessuno step ha ancora prodotto un artefatto: esegui lo step 1",
  "le due meta' del vuoto non si dividono piu' il lavoro");

// Un artefatto c'e': la scatola se ne va, e se ne va SUBITO, non a disegno
// finito.
ultimoStato = [
  { numero: 1, chiave: "01_load", artefatto: "01_cloud.ply" },
  { numero: 2, chiave: "02_segment", artefatto: null },
];
ricaricaVista(2, generazione);
assert.equal(vuoto.hidden, true, "la frase resta stampata sopra il pezzo che sta arrivando");
assert.equal(chiesto, 1, "il ripiego a monte non chiede piu' lo step giusto");
""")


def test_caricaStato_non_crolla_su_un_corpo_che_non_si_legge(tmp_path):
    """Tre grafie di spazzatura su un 200: JSON invalido, JSON valido ma
    senza `steps`, e il `null` letterale. Nessuna delle tre deve far
    sollevare `caricaStato` (la pagina cadrebbe bianca all'avvio, prima
    ancora che l'elenco degli step compaia) e le prime due devono dirlo a
    video, con lo stesso canale degli altri rifiuti. Il controllo che
    smentisce e' nello stesso banco: un corpo buono deve continuare a
    disegnare gli step.

    Il `null` letterale e' un caso a parte: `corpoLetto` lo lascia passare
    intatto per contratto (e' cio' che il server ha davvero risposto), ma un
    corpo `null` per intero non e' mai una risposta legittima di `/api/run` —
    solo un campo nullabile innestato lo sarebbe. Prima della correzione,
    `corpo === undefined` lasciava passare `null`, e `!Array.isArray(null.steps)`
    sollevava fuori da ogni catch.
    """
    _esegui(tmp_path, _banco_di_caricaStato() + """
risponde = async () => ({ ok: true, status: 200, json: async () => { throw new SyntaxError("boom"); } });
await caricaStato();
// In testata (#esito) e non in #errore: all'avvio le tre schermate sono
// nascoste e #errore sta dentro una di loro.
const esito = document.getElementById("esito");
assert.match(esito.textContent, /non si legge/, "il corpo illeggibile non dice niente a video");
assert.match(esito.textContent, /Ricarica la pagina/, "un guasto fra server e pagina va detto con il rimedio");
assert.equal(document.getElementById("corsa").textContent, "",
  "un corpo illeggibile non deve scrivere corsa");

esito.textContent = "";
risponde = async () => ({ ok: true, status: 200, json: async () => null });
await caricaStato();
assert.match(esito.textContent, /non si legge/, "un null letterale fa sollevare caricaStato fuori da ogni catch");
assert.equal(document.getElementById("corsa").textContent, "",
  "un null letterale non deve scrivere corsa");

esito.textContent = "";
risponde = async () => ({ ok: true, status: 200, json: async () => ({ out_dir: "/tmp/corsa" }) });
await caricaStato();
assert.match(esito.textContent, /non si legge/,
  "un corpo senza l'elenco degli step non dice niente a video");

// --- il controllo che smentisce: un corpo buono deve continuare a funzionare
esito.textContent = "";
risponde = async () => ({ ok: true, status: 200, json: async () => ({ out_dir: "/tmp/corsa", steps: STEPS }) });
await caricaStato();
assert.equal(rigaErrore.textContent, "", "un corpo buono non deve mostrare errore");
assert.equal(document.getElementById("corsa").textContent, "/tmp/corsa");
assert.equal(elenco.childElementCount, 3, "un corpo buono deve continuare a disegnare gli step");
""")


def _banco_di_apriDettaglio() -> str:
    """`apriDettaglio` intero, con le sue dipendenze vere: e' il punto in cui
    stanno quattro dei sei `.json()` del censimento (schema, config, metriche
    — le ultime due nella stessa guardia). `campoParametro`/`scriviParametro`
    servono solo perche' il ramo buono del pannello li chiama costruendo le
    righe; nessun banco qui li scatena.
    """
    return _DOM + _funzioni(
        *_COLONNA, "dichiaraErrore", "fallisciDettaglio",
        "ragioneDelRifiuto", "serverMuto", "superata", "corpoLetto", "valoreScritto",
        "segnalaCampo", "apriBattuta", "scriviValore", "scriviParametro",
        "testoDellAiuto", "campoParametro", "apriDettaglio",
        "durataMisurata", "ultimaDurata",
        # L'intestazione e il gruppo che richiude i predefiniti: il pannello li
        # costruisce a ogni apertura, quindi il banco li incontra comunque.
        "intestazioneDelloStep", "fraseDelloStato", "reso", "cambiatoDalPredefinito", "gruppoDelBlocco",
        # Il pannello va a video in un colpo solo, dentro una transizione di
        # vista dove c'e': qui non c'e', e riscrivi cambia il DOM sul posto.
        "riscrivi",
    ) + """
// Vera mentre una corsa gira: i due «Esegui» nascono spenti se lo e'. Falsa
// qui, che e' lo stato in cui un pannello si apre normalmente.
let corsaInCorso = false;
let ultimaBattutaDelCampo = new Map();
let schemaParametri = null;
const richieste = [];
let risponde = {};
globalThis.fetch = async (percorso) => {
  richieste.push(percorso);
  return risponde[percorso]();
};
// Letto e non chiamato in questi banchi (numero e' sempre 1): apriDettaglio
// li confronta comunque a ogni apertura, quindi devono esistere. pannelloCampo
// e pannelloDeck sono provati per conto proprio: qui bastano stub, questi
// banchi non aprono mai lo step 11 ne' il 13.
const STEP_CON_RITAGLIO = 2;
const STEP_CON_CAMPO = 13;
const STEP_CON_DECK = 11;
const STEP_CON_SCARTO = 7;
function pannelloCampo() { return document.createElement("fieldset"); }
function pannelloDeck() { return document.createElement("fieldset"); }
const SCHEMA_BUONO = { "1": { blocchi: ["input"], campi: { input: { path: { description: "percorso" } } } } };
const CONFIG_BUONA = { input: { path: "nuvola.ply" } };
const METRICHE_BUONE = {};
"""


def test_apriDettaglio_schema_illeggibile_non_avvelena_la_cache(tmp_path):
    """Il caso che l'addendum nomina esplicitamente: uno schema mezzo letto
    resterebbe in memoria per tutta la vita della pagina, perche'
    `schemaParametri` non e' piu' `null` e nessun clic successivo ritenterebbe
    la richiesta. Il controllo che smentisce e' nello stesso banco: dopo un
    fallimento, un secondo clic con uno schema buono deve ancora funzionare —
    provato solo perche' la cache e' rimasta vuota.

    Ripetuto anche sul `null` letterale: prima della correzione,
    `corpo === undefined` lasciava passare `null`, `schemaParametri = null`
    veniva assegnato comunque (la guardia non se ne accorgeva), e il primo
    clic successivo andava in crash differito su `schemaParametri[...]`
    invece di ritentare la richiesta.
    """
    _esegui(tmp_path, _banco_di_apriDettaglio() + """
// Lo stato dello step 1, per la riga che il pannello aggiunge sotto l'intestazione.
ultimoStato = [{ numero: 1, chiave: "01_load", stato: "non valido" }];
risponde = {
  "/api/schema": async () => ({ ok: true, status: 200, json: async () => { throw new SyntaxError("boom"); } }),
};
await apriDettaglio(1);
assert.match(rigaErrore.textContent, /schema/, "il corpo illeggibile non nomina lo schema a video");
assert.equal(schemaParametri, null,
  "un corpo illeggibile e' finito comunque in cache: nessun clic successivo ritentera'");
assert.equal(document.getElementById("dettaglio").childElementCount, 0,
  "il pannello non e' stato svuotato dopo il fallimento");

risponde = {
  "/api/schema": async () => ({ ok: true, status: 200, json: async () => null }),
};
await apriDettaglio(1);
assert.match(rigaErrore.textContent, /schema/, "un null letterale non nomina lo schema a video");
assert.equal(schemaParametri, null, "un null letterale e' finito in cache: nessun clic successivo ritentera'");

risponde = {
  "/api/schema": async () => ({ ok: true, status: 200, json: async () => SCHEMA_BUONO }),
  "/api/config": async () => ({ ok: true, status: 200, json: async () => CONFIG_BUONA }),
  "/api/metrics": async () => ({ ok: true, status: 200, json: async () => METRICHE_BUONE }),
};
await apriDettaglio(1);
assert.equal(schemaParametri, SCHEMA_BUONO, "lo schema buono non e' stato memorizzato");
const rigaDiStato = document.getElementById("dettaglio").figli.find((n) => n.className === "aiuto stato-dello-step");
assert.ok(rigaDiStato, "il pannello non spiega lo stato dello step");
assert.match(rigaDiStato.textContent, /parametri diversi da quelli correnti/);
assert.ok(document.getElementById("dettaglio").childElementCount > 0,
  "il pannello non si e' ripreso con uno schema buono, dopo che il primo era fallito");
""")


def test_apriDettaglio_config_illeggibile_non_scrive_la_configurazione_di_modulo(tmp_path):
    """Un rischio in piu' rispetto a quanto l'addendum nomina: `configurazione`
    e' anch'essa una variabile di modulo che sopravvive fra un'apertura e
    l'altra, ed e' quella da cui riparte la prossima PUT di `scriviParametro`.
    Un corpo illeggibile non deve entrarci, altrimenti la prossima modifica di
    un campo qualsiasi partirebbe da un valore rotto invece che da quello
    dell'apertura precedente.

    Ripetuto sul `null` letterale: prima della correzione,
    `corpoConfig === undefined` lasciava passare `null`,
    `configurazione = null` veniva assegnato comunque, e la prossima
    `scriviParametro` sarebbe andata in crash differito su
    `configurazione[blocco]` invece di ripartire da un valore buono.
    """
    _esegui(tmp_path, _banco_di_apriDettaglio() + """
configurazione = { input: { path: "valore-precedente.ply" } };
risponde = {
  "/api/schema": async () => ({ ok: true, status: 200, json: async () => SCHEMA_BUONO }),
  "/api/config": async () => ({ ok: true, status: 200, json: async () => { throw new SyntaxError("boom"); } }),
  "/api/metrics": async () => ({ ok: true, status: 200, json: async () => METRICHE_BUONE }),
};
await apriDettaglio(1);
assert.match(rigaErrore.textContent, /non si legge/, "il corpo illeggibile non dice niente a video");
assert.equal(configurazione.input.path, "valore-precedente.ply",
  "la configurazione di modulo e' stata sovrascritta da un corpo che non si legge: " +
  "la prossima PUT partirebbe da un valore rotto");
assert.equal(schemaParametri, SCHEMA_BUONO, "lo schema, gia' buono, non doveva essere ritoccato");

rigaErrore.textContent = "";
risponde = {
  "/api/schema": async () => ({ ok: true, status: 200, json: async () => SCHEMA_BUONO }),
  "/api/config": async () => ({ ok: true, status: 200, json: async () => null }),
  "/api/metrics": async () => ({ ok: true, status: 200, json: async () => METRICHE_BUONE }),
};
await apriDettaglio(1);
assert.match(rigaErrore.textContent, /non si legge/, "un null letterale non dice niente a video");
assert.equal(configurazione.input.path, "valore-precedente.ply",
  "un null letterale ha sovrascritto la configurazione di modulo");
""")


def test_apriDettaglio_metriche_illeggibili_non_scrivono_la_configurazione_di_modulo(tmp_path):
    """Il verso simmetrico del controllo sopra. La guardia e' una condizione
    sola con un `||` fra `corpoConfig` e `corpoMetriche`: un mutante che
    rompesse solo il lato destro non si vedrebbe da un controllo dove a
    fallire e' la config. Qui la config e' buona e sono le metriche a essere
    spazzatura, comprese le metriche `null` per intero.
    """
    _esegui(tmp_path, _banco_di_apriDettaglio() + """
configurazione = { input: { path: "valore-precedente.ply" } };
risponde = {
  "/api/schema": async () => ({ ok: true, status: 200, json: async () => SCHEMA_BUONO }),
  "/api/config": async () => ({ ok: true, status: 200, json: async () => CONFIG_BUONA }),
  "/api/metrics": async () => ({ ok: true, status: 200, json: async () => { throw new SyntaxError("boom"); } }),
};
await apriDettaglio(1);
assert.match(rigaErrore.textContent, /non si legge/, "il corpo illeggibile non dice niente a video");
assert.equal(configurazione.input.path, "valore-precedente.ply",
  "la configurazione di modulo e' stata sovrascritta anche se solo le metriche erano illeggibili");

rigaErrore.textContent = "";
risponde = {
  "/api/schema": async () => ({ ok: true, status: 200, json: async () => SCHEMA_BUONO }),
  "/api/config": async () => ({ ok: true, status: 200, json: async () => CONFIG_BUONA }),
  "/api/metrics": async () => ({ ok: true, status: 200, json: async () => null }),
};
await apriDettaglio(1);
assert.match(rigaErrore.textContent, /non si legge/, "metriche null letterale non dicono niente a video");
assert.equal(configurazione.input.path, "valore-precedente.ply",
  "la configurazione di modulo e' stata sovrascritta anche se solo le metriche erano null");
""")


# --------------------------------------------------------------------------
# La quinta e la sesta tratta nella stessa condizione di `ultimaGeometria`:
# i rami di `apriDettaglio` che leggono schema e config+metriche hanno solo
# `ordine`/`generazione` come guardia — nessun contatore locale, quindi
# niente da rendere decorativo — ma quella guardia stessa non era mai stata
# provata da un test che aprisse davvero due pannelli sovrapposti.
# Verificato rimuovendola (worktree isolato): la suite intera restava 36
# passed su 36.
# --------------------------------------------------------------------------


def test_apriDettaglio_due_pannelli_sovrapposti_lo_schema_vecchio_non_scrive_sopra_il_nuovo(tmp_path):
    """`schemaParametri` e' una cache di modulo che parte `null`: il primo
    pannello aperto la va sempre a prendere. Se un secondo step si apre prima
    che la risposta arrivi, e la prima e' un rifiuto arrivato tardi, senza la
    guardia `fallisciDettaglio` svuoterebbe il pannello del secondo step gia'
    disegnato e gli toglierebbe il marchio — la stessa famiglia "risposta
    vecchia vince", per una strada diversa da `ultimaGeometria`.
    """
    _esegui(tmp_path, _banco_di_apriDettaglio() + """
// Serve una voce anche per lo step 3: SCHEMA_BUONO del banco ne ha una sola,
// per lo step 1. Non lo step 2: e' STEP_CON_RITAGLIO nel banco, e farebbe
// costruire anche il pannello del ritaglio, non extratto qui.
const SCHEMA_DUE_STEP = { "1": SCHEMA_BUONO["1"], "3": SCHEMA_BUONO["1"] };
let filaSchema = [];
globalThis.fetch = async (percorso) => {
  if (percorso === "/api/schema") return new Promise((r) => filaSchema.push(r));
  return risponde[percorso]();
};
risponde = {
  "/api/config": async () => ({ ok: true, status: 200, json: async () => CONFIG_BUONA }),
  "/api/metrics": async () => ({ ok: true, status: 200, json: async () => METRICHE_BUONE }),
};

// Primo pannello (step 1): schema non ancora in cache, resta in attesa.
const primoPannello = apriDettaglio(1);
// Secondo pannello (step 2), un clic dopo: schema ancora null quando parte,
// resta in attesa anche lui, con la propria richiesta.
generazione += 1;
const secondoPannello = apriDettaglio(3, generazione);
assert.equal(filaSchema.length, 2, "il secondo pannello non ha aperto una propria richiesta di schema");

// Lo schema del secondo pannello, il piu' recente, arriva per primo.
filaSchema[1]({ ok: true, status: 200, json: async () => SCHEMA_DUE_STEP });
await secondoPannello;
assert.equal(stepAperto, 3, "il secondo pannello non risulta aperto");
assert.ok(document.getElementById("dettaglio").childElementCount > 0,
  "il secondo pannello non si e' disegnato");

// Lo schema del primo, il piu' vecchio, rientra per ultimo: un rifiuto.
filaSchema[0]({ ok: false, status: 500, text: async () => JSON.stringify({ messaggio: "schema vecchio" }) });
await primoPannello;
assert.equal(stepAperto, 3,
  "il rifiuto dello schema del pannello vecchio ha tolto il marchio dal pannello nuovo");
assert.ok(document.getElementById("dettaglio").childElementCount > 0,
  "il rifiuto dello schema del pannello vecchio ha svuotato il pannello nuovo gia' disegnato");
""")


def test_apriDettaglio_due_pannelli_sovrapposti_la_config_vecchia_non_scrive_sopra_la_nuova(tmp_path):
    """Lo stesso caso sul ramo di config+metriche di `apriDettaglio`: schema
    gia' in cache per isolare la guardia sotto esame, e la config a
    gareggiare."""
    _esegui(tmp_path, _banco_di_apriDettaglio() + """
// Serve una voce anche per lo step 3: SCHEMA_BUONO del banco ne ha una sola,
// per lo step 1. Non lo step 2: e' STEP_CON_RITAGLIO nel banco, e farebbe
// costruire anche il pannello del ritaglio, non extratto qui.
schemaParametri = { "1": SCHEMA_BUONO["1"], "3": SCHEMA_BUONO["1"] };
let filaConfig = [];
globalThis.fetch = async (percorso) => {
  if (percorso === "/api/config") return new Promise((r) => filaConfig.push(r));
  return risponde[percorso]();
};
risponde = {
  "/api/metrics": async () => ({ ok: true, status: 200, json: async () => METRICHE_BUONE }),
};

const primoPannello = apriDettaglio(1);
generazione += 1;
const secondoPannello = apriDettaglio(3, generazione);
assert.equal(filaConfig.length, 2, "il secondo pannello non ha aperto una propria richiesta di config");

filaConfig[1]({ ok: true, status: 200, json: async () => CONFIG_BUONA });
await secondoPannello;
assert.equal(stepAperto, 3, "il secondo pannello non risulta aperto");
assert.ok(document.getElementById("dettaglio").childElementCount > 0,
  "il secondo pannello non si e' disegnato");

filaConfig[0]({ ok: false, status: 500, text: async () => JSON.stringify({ messaggio: "config vecchia" }) });
await primoPannello;
assert.equal(stepAperto, 3,
  "il rifiuto della config del pannello vecchio ha tolto il marchio dal pannello nuovo");
assert.ok(document.getElementById("dettaglio").childElementCount > 0,
  "il rifiuto della config del pannello vecchio ha svuotato il pannello nuovo gia' disegnato");
""")


def test_i_bottoni_esegui_due_clic_sovrapposti_non_lasciano_vincere_il_rifiuto_vecchio(tmp_path):
    """Riga 836 di `app.js`: la seconda istanza che lo scanner strutturale
    segnala, mai nominata come buco distinto prima di questo giro. I due
    bottoni («Esegui questo step», «Esegui da qui in giu'») condividono
    `ordine` (la generazione del pannello, non del clic) e la stessa
    `rigaErrore`: cliccato uno, poi — mentre e' ancora in volo — l'altro, con
    le risposte invertite, il rifiuto del clic piu' vecchio arriverebbe per
    ultimo e scriverebbe sopra il messaggio del clic piu' recente, accusando
    l'azione sbagliata. Un contatore condiviso dai due bottoni, aperto a ogni
    clic su uno qualunque dei due, li distingue.
    """
    _esegui(tmp_path, _banco_di_apriDettaglio() + """
risponde = {
  "/api/schema": async () => ({ ok: true, status: 200, json: async () => SCHEMA_BUONO }),
  "/api/config": async () => ({ ok: true, status: 200, json: async () => CONFIG_BUONA }),
  "/api/metrics": async () => ({ ok: true, status: 200, json: async () => METRICHE_BUONE }),
};
await apriDettaglio(1);
// Per classe e non per posizione: `figli[0]` era il contenitore dei bottoni
// finche' il pannello si apriva su di loro, e adesso davanti c'e'
// l'intestazione dello step. Un indice qui lega il controllo all'ORDINE del
// pannello, che non e' cio' che sta provando.
const [azioni] = document.getElementById("dettaglio").querySelectorAll(".azioni");
const [questo, daQui] = azioni.figli;

let risolvi1, risolvi2;
const risposte = [
  new Promise((r) => { risolvi1 = r; }),
  new Promise((r) => { risolvi2 = r; }),
];
let chiamata = 0;
globalThis.fetch = async () => risposte[chiamata++];

// Clic 1 (piu' vecchio) su "questo step", poi clic 2 (piu' recente) su
// "da qui in giu'", mentre il primo e' ancora in volo.
const primoClic = questo.scatena("click");
const secondoClic = daQui.scatena("click");

// Il secondo clic e' rifiutato e arriva per primo.
risolvi2({ ok: false, status: 500, text: async () => JSON.stringify({ messaggio: "errore nuovo" }) });
await secondoClic;
assert.match(rigaErrore.textContent, /errore nuovo/, "il rifiuto del clic piu' recente non arriva a video");

// Il primo clic, piu' vecchio, e' rifiutato anche lui ma rientra per ultimo.
risolvi1({ ok: false, status: 500, text: async () => JSON.stringify({ messaggio: "errore vecchio" }) });
await primoClic;
assert.match(rigaErrore.textContent, /errore nuovo/,
  "il rifiuto del clic vecchio, arrivato per ultimo, ha scritto sopra quello nuovo");
assert.doesNotMatch(rigaErrore.textContent, /errore vecchio/,
  "il messaggio a video accusa un clic che l'utente ha gia' superato");

// --- il controllo che smentisce: un clic normale, senza accavallamento -----
chiamata = 0;
rigaErrore.textContent = "";
globalThis.fetch = async () => (
  { ok: false, status: 500, text: async () => JSON.stringify({ messaggio: "guasto" }) }
);
await questo.scatena("click");
assert.match(rigaErrore.textContent, /guasto/, "un clic normale, senza accavallamento, smette di funzionare");
""")


# --------------------------------------------------------------------------
# Il sesto punto del censimento: la conferma di /api/crop.
# --------------------------------------------------------------------------


def _banco_del_ritaglio() -> str:
    return _DOM + _funzioni(
        "superata", "ragioneDelRifiuto", "serverMuto", "corpoLetto", "dichiaraErrore", "pannelloRitaglio",
    ) + """
const vista = {
  ingombro: () => ({ min: [0, 0, 0], max: [1, 1, 1] }),
  ultimoBox: null,
  mostraBox(min, max) { this.ultimoBox = { min: [...min], max: [...max] }; },
};
// Come nel modulo vero: configurazione e' gia' popolata quando il pannello si
// costruisce, con crop_min/crop_max al loro default (null, core/config.py)
// finche' nessun ritaglio e' stato applicato.
configurazione = { segment: { crop_min: null, crop_max: null } };
let risponde = null;
globalThis.fetch = async () => risponde();
function apriPannello(ordine) {
  const contenitore = pannelloRitaglio(ordine);
  const applica = contenitore.figli.find((f) => f.tag === "button");
  const esito = contenitore.figli[contenitore.figli.length - 1];
  return { applica, esito };
}
"""


def test_il_pannello_del_ritaglio_mostra_il_box_persistito_quando_c_e(tmp_path):
    """Rimasto aperto da due revisioni: il pannello leggeva solo
    `vista.ingombro()`, il box **disegnato**, e mai
    `configurazione.segment.crop_min/max`, quello **scritto su disco**. Anche
    dopo che i due clic sovrapposti non si scavalcano piu' (il test sopra),
    l'utente non aveva modo di vedere che cosa fosse davvero persistito.

    I due valori possono divergere legittimamente, e il pannello li distingue
    cosi': `crop_min`/`crop_max` sono `null` (il default del modello,
    core/config.py) finche' nessun ritaglio e' mai stato applicato — solo
    allora l'ingombro disegnato e' l'unico punto di partenza sensato, ed e'
    quello che il primo blocco sotto prova. Una volta valorizzati, sono la
    fonte anche se la nuvola nel frattempo e' la stessa: e' cio' che il
    server ha davvero scritto, non una nuova lettura dell'ingombro — il
    secondo blocco lo dimostra con numeri apposta diversi dall'ingombro finto,
    cosi' un pannello che leggesse ancora `vista.ingombro()` per errore li
    tradirebbe.
    """
    _esegui(tmp_path, _banco_del_ritaglio() + """
// Prima di ogni applicazione: crop_min/crop_max sono null, il pannello
// riparte dall'ingombro disegnato.
apriPannello(generazione);
assert.deepEqual(vista.ultimoBox, { min: [0, 0, 0], max: [1, 1, 1] },
  "senza un ritaglio persistito il pannello non riparte piu' dall'ingombro disegnato");

// Dopo un'applicazione riuscita (o alla riapertura con una configurazione
// gia' scritta): il pannello mostra il persistito, non l'ingombro — apposta
// diverso qui sotto, per non poter combaciare per caso.
configurazione = { segment: { crop_min: [5, 6, 7], crop_max: [8, 9, 10] } };
apriPannello(generazione);
assert.deepEqual(vista.ultimoBox, { min: [5, 6, 7], max: [8, 9, 10] },
  "il pannello riaperto non mostra il box persistito nella configurazione, mostra ancora l'ingombro disegnato");
""")


def test_applica_il_ritaglio_200_illeggibile_non_va_in_crash(tmp_path):
    """Il sesto `.json()` del censimento: la conferma di `/api/crop`. Un 200
    illeggibile, o senza `points_after`, non deve far sollevare il gestore del
    bottone — il testo "ritaglio in corso" scritto poco prima (`esito`)
    resterebbe a video per sempre, il silenzio peggiore perche' promette una
    fine che non arriva mai. Lo stesso canale delle altre due uscite d'errore
    di questo bottone: `dichiaraErrore`, non `esito`.

    Il terzo caso e' il `null` letterale: `corpoLetto` lo lascia passare
    intatto per contratto (e' cio' che il server ha davvero risposto), ma un
    corpo `null` per intero non e' mai una risposta legittima di /api/crop —
    solo un campo nullabile innestato lo sarebbe. Prima della correzione,
    `corpo === undefined` lasciava passare `null` e la riga sotto
    (`corpo.points_after`) sollevava fuori da ogni catch.
    """
    _esegui(tmp_path, _banco_del_ritaglio() + """
for (const corpoRotto of [
  async () => { throw new SyntaxError("non e' JSON"); },
  async () => ({ completo: true }),  // valido, ma senza points_after
  async () => null,                  // null letterale: mai legittimo qui
]) {
  rigaErrore.textContent = "";
  const { applica } = apriPannello(generazione);
  risponde = async () => ({ ok: true, status: 200, json: corpoRotto });
  await applica.scatena("click");
  assert.match(rigaErrore.textContent, /non descrive il ritaglio/,
    "un 200 illeggibile non dice niente a video, e il bottone resta muto per sempre");
}
""")


def test_applica_il_ritaglio_fallito_non_lascia_il_messaggio_in_corso_a_video(tmp_path):
    """Rilievo 2 di questo giro. Nel ramo di fallimento `esito` conservava
    «ritaglio in corso: la prima volta rilegge la nuvola piena, circa mezzo
    minuto.» scritto poco prima del `fetch`, mentre `rigaErrore` mostrava gia'
    il rifiuto: l'utente leggeva insieme "sto lavorando" e "e' fallito".
    Provato sulle due uscite d'errore del bottone (il rifiuto del server e il
    200 il cui corpo non descrive il ritaglio applicato), non solo su una:
    la stessa dimenticanza poteva ripetersi identica sulla seconda.
    """
    _esegui(tmp_path, _banco_del_ritaglio() + """
{
  const { applica, esito } = apriPannello(generazione);
  risponde = async () => (
    { ok: false, status: 422, text: async () => JSON.stringify({ messaggio: "box non valido" }) }
  );
  await applica.scatena("click");
  assert.equal(esito.textContent, "",
    "'ritaglio in corso' resta a video accanto all'errore del server");
  assert.match(rigaErrore.textContent, /box non valido/, "il rifiuto del server non arriva a video");
}
{
  const { applica, esito } = apriPannello(generazione);
  risponde = async () => ({ ok: true, status: 200, json: async () => ({ completo: true }) });
  await applica.scatena("click");
  assert.equal(esito.textContent, "",
    "'ritaglio in corso' resta a video accanto all'errore sul corpo illeggibile");
  assert.match(rigaErrore.textContent, /non descrive il ritaglio/, "il corpo illeggibile non arriva a video");
}
""")


def test_applica_il_ritaglio_due_clic_sovrapposti_lascia_vincere_l_ultimo(tmp_path):
    """Rilievo 1, terza istanza sullo stesso file. `ordine` e' la generazione
    del pannello, condivisa da tutti i clic fatti mentre il pannello resta
    aperto: regolare il box e ricliccare «Applica» per affinarlo e' il flusso
    normale, non un incidente — e senza un contatore per clic la risposta del
    clic vecchio, arrivata per ultima, scrive sopra l'esito del clic nuovo.
    Stessa meccanica di `apriBattuta`: un contatore locale al pannello,
    aperto a ogni clic.
    """
    _esegui(tmp_path, _banco_del_ritaglio() + """
const { applica, esito } = apriPannello(generazione);

let risolvi1, risolvi2;
const risposte = [
  new Promise((r) => { risolvi1 = r; }),
  new Promise((r) => { risolvi2 = r; }),
];
let chiamata = 0;
globalThis.fetch = async () => risposte[chiamata++];

const primoClic = applica.scatena("click");
const secondoClic = applica.scatena("click");

// La risposta del secondo clic (l'ultimo box che l'utente ha davvero
// battuto) arriva per prima; quella del primo, piu' vecchio, rientra dopo.
risolvi2({ ok: true, status: 200, json: async () => ({ points_after: 99, completo: true }) });
await secondoClic;
risolvi1({ ok: true, status: 200, json: async () => ({ points_after: 1, completo: true }) });
await primoClic;

assert.match(esito.textContent, /^99\\s+punti/,
  "la risposta del clic vecchio ha scritto sopra l'esito del clic nuovo");
assert.doesNotMatch(esito.textContent, /^1\\s+punti/,
  "l'esito mostra ancora il numero del clic superato");

// --- il controllo che smentisce: un clic normale, senza accavallamento -----
chiamata = 0;
globalThis.fetch = async () => ({ ok: true, status: 200, json: async () => ({ points_after: 7, completo: true }) });
await applica.scatena("click");
assert.match(esito.textContent, /^7\\s+punti/, "un clic normale, senza accavallamento, smette di funzionare");
""")


# --------------------------------------------------------------------------
# Task 14: step 12, caselle dei modelli, prior geometrico e confronto.
# --------------------------------------------------------------------------






def test_la_didascalia_della_vista_sta_dentro_la_vista_e_non_nella_terza_colonna():
    """C14 del giro finale, guardato nel browser il 22/08/2026 su
    runs/lab_telaio_v2.

    `legenda` e `didascalia` erano due `<p class="aiuto">` appesi al fieldset
    di `pannelloCampo`, cioe' dentro `#dettaglio`, cioe' nella terza colonna —
    e sotto i gruppi TET e ANALYSIS: ventidue tacche di rotella per portarle in
    vista. Fotografata o proiettata, l'immagine non portava ne' il caso di
    carico, ne' la grandezza, ne' il massimo; l'unica cosa sovrapposta alla
    vista era il conteggio dei triangoli.

    Mutazione che uccide: rimettere il `<p>` dentro `#dettaglio`, oppure
    ridargli `class="aiuto"` (--tipo-nota, 13 px, --tenue).
    """
    markup = _senza_commenti_html(_markup())
    # La chiusura *della vista*, non la prima del documento: cercata dall'inizio
    # bastava una qualunque altra `<section>` piu' in alto nella pagina (la
    # schermata d'ingresso, per esempio) per far ritagliare una fetta vuota e
    # far fallire il test su un markup corretto.
    apre = markup.index('class="zona zona-vista"')
    vista = markup[apre:markup.index("</section>", apre)]
    assert 'id="didascalia-vista"' in vista, (
        "la didascalia della vista non sta dentro la zona della vista"
    )
    dettaglio = markup[markup.index('id="dettaglio"'):]
    assert 'id="didascalia-vista"' not in dettaglio

    # Il foglio dichiara 13px come pavimento «perche' questa interfaccia viene
    # proiettata in discussione e va letta dal fondo della stanza». La frase che
    # dice che cosa si sta guardando non puo' stare su quel pavimento, e non
    # puo' essere grigio tenue: e' il titolo della figura, non un aiuto.
    foglio = _foglio()
    regola = foglio[foglio.index(".didascalia-vista {"):]
    regola = regola[:regola.index("}")]
    assert "var(--tipo-nota)" not in regola, f"la didascalia sta al pavimento della scala: {regola}"
    assert "var(--tipo-corpo)" in regola, regola
    assert "var(--tenue)" not in regola, f"la didascalia della figura in grigio tenue: {regola}"

    # E non la fabbrica il modulo: sta nel markup, come la riga d'errore e lo
    # stato vuoto del prior, cosi' nessun replaceChildren() la puo' distruggere.
    corpo = _sorgente_di("didascaliaDellaVista", _senza_commenti_js(_modulo()))
    assert 'getElementById("didascalia-vista")' in corpo
    assert "createElement" not in corpo


def test_la_didascalia_della_vista_si_svuota_lasciando_lo_step_del_campo(tmp_path):
    """Nel markup la didascalia sopravvive al cambio di step: senza pulirla,
    lasciato lo step 13 resterebbe «GRAVITA — tensione equivalente ...» scritta
    sotto la nuvola dello step 2. E' la stessa classe di «la vista contraddice
    la sua didascalia» che questo ramo ha gia' pagato tre volte.

    Mutazione che uccide: togliere la riga che la svuota in `ricaricaVista`.
    """
    _esegui(tmp_path, _DOM + _costante("STEP_CON_GEOMETRIA") + _funzioni(
        "didascaliaDellaVista", "superata", "passoDaMostrare", "nomeDelloStep", "comandoDelFantasma", "ricaricaVista"
    ) + """
// Il velo del passaggio a monte fa una fetch e questo banco prova altro:
// stub, come riallineaTaglio e mostraStep qui accanto. Che il velo taccia
// dove la geometria a video e' gia' di un altro passaggio lo provano
// test_il_fantasma_tace_... e test_il_fantasma_dello_step_8_..., eseguendo.
function mostraFantasmaDelloStep() {}
// Lo step 2 il proprio artefatto ce l'ha: cosi' ricaricaVista prende la strada
// normale e non il ramo «nessuno step ha ancora prodotto un artefatto», che
// non e' cio' che questo controllo guarda.
ultimoStato = [{ numero: 2, chiave: "02_segment", artefatto: "02_segmented.ply" }];
async function mostraStep() { return true; }
function riallineaTaglio() {}
document.getElementById("didascalia-vista").textContent =
  "GRAVITA — tensione equivalente: scala tagliata a 0,2321 MPa (p99), 109 nodi sopra";
ricaricaVista(2, generazione);
assert.equal(document.getElementById("didascalia-vista").textContent, "",
  "la didascalia del campo e' rimasta sotto la vista di un altro step");
""")


_RIPIEGO = """
// Il velo del passaggio a monte fa una fetch e questo banco prova altro:
// stub, come riallineaTaglio e mostraStep qui accanto. Che il velo taccia
// dove la geometria a video e' gia' di un altro passaggio lo provano
// test_il_fantasma_tace_... e test_il_fantasma_dello_step_8_..., eseguendo.
function mostraFantasmaDelloStep() {}

// Il registro di una corsa arrivata allo step 9 con la semplificazione SPENTA:
// e' il caso predefinito del programma, e i suoi buchi sono quelli veri.
// Lo step 7 e il 10 misurano, l'8 non scrive perche' e' disabilitato, l'11 e il
// 12 non hanno ancora girato.
ultimoStato = [
  { numero: 1, chiave: "01_load", artefatto: "01_cloud.ply" },
  { numero: 2, chiave: "02_segment", artefatto: "02_segmented.ply" },
  { numero: 3, chiave: "03_downsample", artefatto: "03_downsampled.ply" },
  { numero: 4, chiave: "04_normals", artefatto: "04_normals.ply" },
  { numero: 5, chiave: "05_reconstruct", artefatto: "05_surface.ply" },
  { numero: 6, chiave: "06_repair", artefatto: "06_repaired.ply" },
  { numero: 7, chiave: "07_surface_quality", artefatto: null },
  { numero: 8, chiave: "08_simplify", artefatto: null },
  { numero: 9, chiave: "09_tetrahedralize", artefatto: "09_volume.vtu" },
  { numero: 10, chiave: "10_volume_quality", artefatto: null },
  // NON nullo, e non e' un dettaglio: e' cio' che `runs/lab_crop/steps.json`
  // contiene davvero. Lo step 11 un artefatto ce l'ha -- un deck di calcolo --
  // e non e' geometria che il viewport sappia disegnare.
  { numero: 11, chiave: "11_export", artefatto: "wall_model.inp" },
  { numero: 12, chiave: "12_wall", artefatto: null },
];
"""


def test_uno_step_che_non_scolpisce_ripiega_sull_ultimo_artefatto_a_monte(tmp_path):
    """Il difetto che Mario ha riportato: cambiando step compariva «nessun
    artefatto per questo step» e la nuvola lavorata negli step precedenti
    spariva dallo schermo.

    Quattro step su dodici non scrivono geometria per costruzione (il 7 e il
    10 misurano, l'11 scrive un deck, il 12 un prior), piu' l'8 quando la
    semplificazione e' spenta, che e' il predefinito. Cinque righe su dodici
    svuotavano il viewport.

    Il ripiego si prova sui numeri veri del registro, non sulla riga per
    iscritto: e' una funzione pura e va eseguita.
    """
    _esegui(tmp_path, _DOM + _costante("STEP_CON_GEOMETRIA") + _funzioni("passoDaMostrare") + _RIPIEGO + """
assert.equal(passoDaMostrare(7), 6, "lo step 7 misura: deve mostrare la superficie del 6");
assert.equal(passoDaMostrare(10), 9, "lo step 10 misura: deve mostrare il volume del 9");
assert.equal(passoDaMostrare(11), 9, "lo step 11 scrive un deck, non geometria");
assert.equal(passoDaMostrare(12), 9, "lo step 12 scrive un prior, non geometria");
// Chi l'artefatto ce l'ha resta se stesso: il ripiego non deve spostare nulla
// quando non c'e' niente da ripiegare.
assert.equal(passoDaMostrare(9), 9);
assert.equal(passoDaMostrare(1), 1);
""")


def test_prima_che_arrivi_il_primo_stato_il_ripiego_non_indovina(tmp_path):
    """`ultimoStato` resta vuoto finche' il primo `run_state` non arriva, e il
    cambio d'asse ci passa gia' da li': `asseTaglio` sta nella pagina dal
    caricamento, e cambiarlo prima che l'elenco esista chiama `passoDaMostrare`
    su un elenco vuoto e con `stepMostrato` ancora `null`.

    Deve rispondere `null` -- cioe' «niente da mostrare» -- e non inciampare.
    """
    _esegui(tmp_path, _DOM + _costante("STEP_CON_GEOMETRIA") + _funzioni("passoDaMostrare") + """
assert.deepEqual(ultimoStato, [], "il banco non parte piu' da un elenco vuoto");
assert.equal(passoDaMostrare(12), null, "il ripiego indovina uno step su un elenco vuoto");
assert.equal(passoDaMostrare(null), null, "nessuno step ancora mostrato non e' uno step");
""")


def test_gli_step_disegnabili_del_modulo_sono_quelli_del_server():
    """L'unica tabella che il modulo rispecchia dal server, e il controllo che
    ne impedisce la deriva.

    `STEP_CON_GEOMETRIA` deve coincidere con `pipeline.ARTIFACTS`, che e' cio'
    contro cui /api/cloud e /api/mesh validano il numero chiesto: uno step in
    piu' qui e la vista chiede una geometria che il server rifiuta, uno in meno
    e ripiega piu' indietro del necessario. Letta dalla tabella vera, non
    ricopiata: una copia in questo file avrebbe la stessa deriva del modulo.
    """
    from meshrec.core import pipeline

    dichiarati = re.search(
        r"^const STEP_CON_GEOMETRIA = new Set\(\[([^\]]*)\]\);$", _modulo(), flags=re.MULTILINE
    )
    assert dichiarati is not None, "STEP_CON_GEOMETRIA non e' piu' una costante di modulo"
    assert [int(n) for n in dichiarati.group(1).split(",")] == sorted(pipeline.ARTIFACTS)

    # E la tratta della mesh e' un sottoinsieme: uno step che disegna una mesh
    # senza essere disegnabile sarebbe una richiesta che il server rifiuta.
    mesh = re.search(r"^const STEP_CON_MESH = new Set\(\[([^\]]*)\]\);$", _modulo(), flags=re.MULTILINE)
    assert mesh is not None
    assert set(int(n) for n in mesh.group(1).split(",")) <= set(pipeline.ARTIFACTS)


def test_uno_step_con_un_artefatto_che_non_si_disegna_non_ferma_il_ripiego(tmp_path):
    """Il difetto trovato leggendo un registro vero, non ragionando.

    In `runs/lab_crop/steps.json` lo step 11 ha `artefatto: wall_model.inp`:
    NON nullo. Un ripiego che si fermasse al solo campo `artefatto` lo
    prenderebbe per buono e chiederebbe /api/cloud/11, che il server rifiuta
    perche' l'11 non e' fra le chiavi di pipeline.ARTIFACTS -- cioe' di nuovo
    lo schermo vuoto, per una strada nuova.

    Servono due condizioni: aver scritto, e aver scritto qualcosa di
    disegnabile.
    """
    _esegui(tmp_path, _DOM + _costante("STEP_CON_GEOMETRIA") + _funzioni("passoDaMostrare") + _RIPIEGO + """
assert.equal(
  ultimoStato[10].artefatto, "wall_model.inp",
  "il registro di prova non riproduce piu' il caso vero dello step 11",
);
assert.equal(passoDaMostrare(11), 9, "il deck dello step 11 e' stato preso per geometria");
assert.equal(passoDaMostrare(12), 9, "il prior dello step 12 e' stato preso per geometria");
""")


def test_il_ripiego_legge_il_registro_e_non_una_tabella_scritta_a_mano(tmp_path):
    """Lo step 8 scrive `08_simplified.ply` SOLO a semplificazione abilitata
    (`registra(8, ..., None)` altrimenti, pipeline.py), che e' il predefinito.

    Una tabella step -> artefatto scritta nel modulo direbbe che l'8 un
    artefatto ce l'ha e manderebbe a chiedere un file che non esiste. Il campo
    `artefatto` del registro dice cio' che quello step ha SCRITTO, e distingue
    i due casi da solo.
    """
    _esegui(tmp_path, _DOM + _costante("STEP_CON_GEOMETRIA") + _funzioni("passoDaMostrare") + _RIPIEGO + """
assert.equal(passoDaMostrare(8), 6, "semplificazione spenta: l'8 non ha scritto niente");
// Accesa, lo stesso numero risponde se stesso. Nessuna riga del modulo cambia:
// cambia il registro.
ultimoStato[7].artefatto = "08_simplified.ply";
assert.equal(passoDaMostrare(8), 8, "semplificazione accesa: l'artefatto dell'8 esiste");
""")


def test_senza_niente_a_monte_la_vista_non_incolpa_lo_step_scelto(tmp_path):
    """L'unico caso in cui svuotare resta onesto: la corsa non e' mai partita.

    Ma il testo non deve dire «nessun artefatto per QUESTO step», che da' la
    colpa allo step cliccato: non e' lui che manca, e' che non e' stato
    eseguito ancora niente. E deve dire cosa fare.
    """
    _esegui(tmp_path, _DOM + _costante("STEP_CON_GEOMETRIA") + _funzioni(
        "didascaliaDellaVista", "superata", "passoDaMostrare", "nomeDelloStep", "comandoDelFantasma", "ricaricaVista"
    ) + """
// Il velo del passaggio a monte fa una fetch e questo banco prova altro:
// stub, come riallineaTaglio e mostraStep qui accanto. Che il velo taccia
// dove la geometria a video e' gia' di un altro passaggio lo provano
// test_il_fantasma_tace_... e test_il_fantasma_dello_step_8_..., eseguendo.
function mostraFantasmaDelloStep() {}
ultimoStato = [
  { numero: 1, chiave: "01_load", artefatto: null },
  { numero: 2, chiave: "02_segment", artefatto: null },
];
let svuotata = 0;
let allineato = "mai";
const vista = { svuota: () => { svuotata += 1; } };
function riallineaTaglio(n) { allineato = n; }
async function mostraStep() { throw new Error("non si deve chiedere nessuna geometria"); }

ricaricaVista(2, generazione);
assert.equal(svuotata, 1, "la vista non e' stata svuotata quando non c'e' proprio niente");
assert.equal(
  document.getElementById("conteggi").textContent,
  "nessuno step ha ancora prodotto un artefatto: esegui lo step 1",
);
assert.equal(allineato, null, "il cursore del taglio resta appeso a una geometria che non c'e'");
""")


def test_la_vista_che_ripiega_dichiara_a_quale_step_appartiene(tmp_path):
    """Senza la coda si torna al difetto che `vista.svuota()` voleva evitare:
    una geometria sullo schermo che la didascalia attribuisce a chi non l'ha
    prodotta. Cliccato l'11 si vede il volume del 9, e lo schermo lo dice.

    Mutazione che uccide: togliere la coda, o metterla senza la guardia
    `mostrato !== numero` (che la scriverebbe anche sullo step giusto).
    """
    _esegui(tmp_path, _DOM + _costante("STEP_CON_GEOMETRIA") + _funzioni(
        "didascaliaDellaVista", "superata", "passoDaMostrare", "nomeDelloStep", "comandoDelFantasma", "ricaricaVista"
    ) + _RIPIEGO + """
ETICHETTE["09_tetrahedralize"] = "Tetraedri";
let chiesto = null;
let allineato = "mai";
const vista = { svuota: () => {} };
function riallineaTaglio(n) { allineato = n; }
async function mostraStep(numero) {
  chiesto = numero;
  document.getElementById("conteggi").textContent = "94.663 vertici, 189.322 triangoli";
  return true;
}

await ricaricaVista(11, generazione);
await new Promise((r) => setTimeout(r, 0));
assert.equal(chiesto, 9, "cliccato l'11, la geometria chiesta non e' quella del 9");
assert.equal(
  document.getElementById("conteggi").textContent,
  "94.663 vertici, 189.322 triangoli \u2014 artefatto dello step 9 (Tetraedri)",
  "la vista non dichiara a quale step appartiene cio' che mostra",
);
// Lo step MOSTRATO e non quello scelto: il cursore del taglio si rifa'
// sull'ingombro di cio' che e' disegnato.
assert.equal(allineato, 9, "il cursore del taglio segue lo step scelto invece della geometria");

// Sullo step che l'artefatto ce l'ha, nessuna coda: sarebbe rumore che ripete
// il numero gia' evidenziato nella colonna.
document.getElementById("conteggi").textContent = "94.663 vertici, 189.322 triangoli";
await ricaricaVista(9, generazione);
await new Promise((r) => setTimeout(r, 0));
assert.equal(
  document.getElementById("conteggi").textContent, "94.663 vertici, 189.322 triangoli",
  "la coda compare anche quando lo step mostrato e' quello scelto",
);
""")


def test_la_coda_del_ripiego_non_si_attacca_a_un_rifiuto(tmp_path):
    """`mostraStep` scrive da due rami: quando disegna, e quando dichiara che
    l'artefatto non c'e'. Guardando il solo valore di verita' la coda si
    attaccava anche al secondo, e a schermo usciva

        l'artefatto dello step 9 non c'e' piu' sul disco: riesegui lo step 9
        — artefatto dello step 9 (Tetraedri)

    cioe' il ripiego dichiarava la paternita' di una geometria che sullo
    schermo non c'e'. E' il difetto che `vista.svuota()` esisteva per chiudere,
    riaperto dalla correzione che lo chiudeva.

    Da qui il tri-stato: `"vuoto"` resta truthy -- la risposta non e' stata
    scartata, e il cursore del taglio deve comunque rifarsi, che sulla vista
    vuota vuol dire nascondersi -- ma non e' `true`.
    """
    _esegui(tmp_path, _DOM + _costante("STEP_CON_GEOMETRIA") + _funzioni(
        "didascaliaDellaVista", "superata", "passoDaMostrare", "nomeDelloStep", "comandoDelFantasma", "ricaricaVista"
    ) + _RIPIEGO + """
const rifiuto = "l'artefatto dello step 9 non c'e' piu' sul disco: riesegui lo step 9";
let allineato = "mai";
const vista = { svuota: () => {} };
function riallineaTaglio(numero) { allineato = numero; }
async function mostraStep() {
  document.getElementById("conteggi").textContent = rifiuto;
  return "vuoto";
}

await ricaricaVista(11, generazione);
await new Promise((r) => setTimeout(r, 0));
assert.equal(
  document.getElementById("conteggi").textContent, rifiuto,
  "la coda si e' attaccata al messaggio che dice che l'artefatto non c'e'",
);
// Il cursore si rifa' lo stesso: sulla vista vuota ingombro() torna null e il
// comando si nasconde, che e' cio' che deve succedere.
assert.equal(allineato, 9, "una vista vuota lascia il cursore del taglio come stava");
""")


def test_ricarica_vista_risolve_con_l_esito_della_geometria(tmp_path):
    """Il giro «Salva tutti gli step» deve sapere quando la geometria e' a video
    prima di catturare la tela, e se e' arrivata davvero: ricaricaVista era
    l'unico imbuto e non restituiva niente. Ora risolve con cio' che mostraStep
    ha risposto -- true, "vuoto", false -- e con false quando la catena cade.

    Mutazione che lo uccide: togliere il `return` davanti alla catena di
    mostraStep, o non rendere `disegnato` dal `.then`.
    """
    _esegui(tmp_path, _DOM + _costante("STEP_CON_GEOMETRIA") + _funzioni(
        "didascaliaDellaVista", "superata", "passoDaMostrare", "nomeDelloStep", "comandoDelFantasma",
        "segnalaArtefattoMancante", "ricaricaVista"
    ) + _RIPIEGO + """
const vista = { svuota: () => {} };
function riallineaTaglio() {}
let risposta = true;
async function mostraStep() { if (risposta instanceof Error) throw risposta; return risposta; }

assert.equal(await ricaricaVista(9, generazione), true, "una geometria disegnata non risolve true");
risposta = "vuoto";
assert.equal(await ricaricaVista(9, generazione), "vuoto", "un artefatto mancante non risolve «vuoto»");
risposta = new RangeError("corpo corto");
assert.equal(await ricaricaVista(9, generazione), false, "una catena caduta non risolve false");
""")


def test_una_generazione_superata_non_scrive_la_coda_del_ripiego(tmp_path):
    """La coda e' una scrittura dopo un'attesa, quindi risponde alla regola
    dell'ordine come ogni altra: due clic di seguito e la risposta del primo
    non deve posarsi sulla didascalia del secondo.
    """
    _esegui(tmp_path, _DOM + _costante("STEP_CON_GEOMETRIA") + _funzioni(
        "didascaliaDellaVista", "superata", "passoDaMostrare", "nomeDelloStep", "comandoDelFantasma", "ricaricaVista"
    ) + _RIPIEGO + """
const vista = { svuota: () => {} };
let allineato = "mai";
function riallineaTaglio(n) { allineato = n; }
async function mostraStep() {
  document.getElementById("conteggi").textContent = "94.663 vertici, 189.322 triangoli";
  return true;
}

const vecchia = generazione;
generazione += 1;   // un secondo clic e' partito mentre la prima risposta arrivava
await ricaricaVista(11, vecchia);
await new Promise((r) => setTimeout(r, 0));
assert.equal(
  document.getElementById("conteggi").textContent, "94.663 vertici, 189.322 triangoli",
  "una risposta superata ha scritto la propria coda sulla vista di un altro step",
);
assert.equal(allineato, "mai", "una risposta superata ha rifatto il cursore del taglio");
""")


def test_una_metrica_annidata_diventa_una_riga_per_foglia(tmp_path):
    """`geometric_error` e' annidato DUE livelli (`cloud_to_mesh` -> `mean`,
    `max`, ...): e' il collaudo per cui lo step 7 esiste, e finiva a video come
    una riga di JSON crudo.

    Provato sulla forma vera che `quality.geometric_error` restituisce.
    """
    _esegui(tmp_path, _DOM + _costante("VALORE_LARGO") + "\n" + _costante("CLASSE_VALORE_LARGO")
        + "\n" + _funzioni("righeDellaMetrica", "valoreDellaMetrica") + """
const righe = righeDellaMetrica("geometric_error", {
  cloud_to_mesh: { mean: 4.41, max: 72.2, non_finite: 0 },
  mesh_to_cloud: { mean: 3.02, max: 55.1, non_finite: 0 },
  hausdorff: 72.2,
});
const coppie = [];
for (let i = 0; i < righe.length; i += 2) coppie.push([righe[i].textContent, righe[i + 1].textContent]);

// Virgola e non punto: sullo stesso schermo, due funzioni piu' su, si legge
// gia' `19.314 triangoli` all'italiana. Due convenzioni numeriche a un palmo di
// distanza erano il difetto.
assert.deepEqual(coppie, [
  ["geometric_error \u00b7 cloud_to_mesh \u00b7 mean", "4,41"],
  ["geometric_error \u00b7 cloud_to_mesh \u00b7 max", "72,2"],
  ["geometric_error \u00b7 cloud_to_mesh \u00b7 non_finite", "0"],
  ["geometric_error \u00b7 mesh_to_cloud \u00b7 mean", "3,02"],
  ["geometric_error \u00b7 mesh_to_cloud \u00b7 max", "55,1"],
  ["geometric_error \u00b7 mesh_to_cloud \u00b7 non_finite", "0"],
  ["geometric_error \u00b7 hausdorff", "72,2"],
]);
// Sedici cifre non si leggono e non aggiungono niente: metrics.json conserva la
// precisione piena, ed e' da li' che si citano i numeri della tesi.
assert.deepEqual(
  righeDellaMetrica("mean", 4.442869663238525).map((n) => n.textContent),
  ["mean", "4,44287"],
);
// Ma un CONTEGGIO non si arrotonda: e' il difetto che le sole sei cifre
// significative introducevano, trovato a schermo e non in suite. 6.329.096
// diventava 6.329.100, mentre #conteggi due centimetri sotto la vista scriveva
// il numero giusto: due numeri per la stessa quantita' sullo stesso schermo.
assert.deepEqual(
  righeDellaMetrica("points_read", 6329096).map((n) => n.textContent),
  ["points_read", "6.329.096"],
);
// Nessuna graffa a video: era il difetto.
assert.ok(!coppie.some(([, v]) => v.includes("{")), "una metrica e' rimasta in JSON");

// Uno scalare resta una riga sola, e un dizionario vuoto non ne lascia
// nessuna: «{}» a video non e' una misura.
assert.deepEqual(
  righeDellaMetrica("watertight", true).map((n) => n.textContent), ["watertight", "sì"],
);
assert.deepEqual(righeDellaMetrica("niente", {}), []);
// `null` e' un valore, non un dizionario: _distribution lo restituisce quando
// nessun valore finito resta, e va letto come tale.
assert.deepEqual(
  righeDellaMetrica("min", null).map((n) => n.textContent), ["min", "null"],
);
""")


def test_una_metrica_che_e_una_lista_resta_una_riga_sola(tmp_path):
    """Le liste ci sono davvero, contro quanto diceva il commento sopra
    `righeDellaMetrica` prima che lo si correggesse.

    Misurate su `runs/lab_crop/metrics.json` il 24/08/2026: otto, fra cui
    `01_load.extent` (tre numeri), `06_repair.hole_areas` (sei) e
    `11_export.transform`, che e' una matrice quattro per quattro.

    Aperte darebbero una riga per elemento -- e per la matrice una riga per
    riga di matrice -- al posto di una. La guardia `!Array.isArray` e' cio' che
    lo impedisce, ed era l'unica parte di quella funzione che nessun controllo
    teneva: tolta, `790 passed`.
    """
    _esegui(tmp_path, _DOM + _costante("VALORE_LARGO") + "\n" + _costante("CLASSE_VALORE_LARGO")
        + "\n" + _funzioni("righeDellaMetrica", "valoreDellaMetrica") + """
const righe = righeDellaMetrica("extent", [2.759, 0.785, 2.0]);
assert.equal(righe.length, 2, "una lista si e' aperta in una riga per elemento");
assert.equal(righe[0].textContent, "extent");
// JSON e non formato all'italiana: dentro le parentesi non c'e' prosa, c'e' un
// valore che si copia.
assert.equal(righe[1].textContent, "[2.759,0.785,2]");
// Anche annidata, che e' la forma vera: `hole_areas` sta dentro lo step 6.
assert.deepEqual(
  righeDellaMetrica("06_repair", { hole_areas: [1.33, 0.1] }).map((n) => n.textContent),
  ["06_repair \u00b7 hole_areas", "[1.33,0.1]"],
);
""")


def test_lo_stato_che_il_ripiego_legge_e_quello_che_l_elenco_ha_appena_disegnato(tmp_path):
    """`disegnaStep` e' l'unico canale per cui `ultimoStato` si riempie, e ogni
    controllo sul ripiego lo scrive a mano: la giuntura fra i due non la
    guardava nessuno.

    Tolta la riga che aggiorna `ultimoStato`, `passoDaMostrare` risponde `null`
    per ogni step -- cioe' la vista si svuota sempre, che e' esattamente il
    difetto di partenza -- e la suite resta verde. Misurato il 24/08/2026:
    `790 passed`.
    """
    _esegui(tmp_path, _DOM + _costante("STEP_CON_GEOMETRIA") + _funzioni(
        *_COLONNA, "passoDaMostrare"
    ) + """
disegnaStep([
  { numero: 1, chiave: "01_load", stato: "valido", artefatto: "01_cloud.ply" },
  { numero: 2, chiave: "02_segment", stato: "valido", artefatto: "02_segmented.ply" },
  { numero: 3, chiave: "03_downsample", stato: "mai eseguito", artefatto: null },
]);
assert.equal(
  passoDaMostrare(3), 2,
  "il ripiego non vede lo stato che l'elenco ha appena disegnato",
);

// E lo tiene fresco: il fronte di discesa manda run_state di nuovo, e cio' che
// e' stato scritto nel frattempo deve contare.
disegnaStep([
  { numero: 1, chiave: "01_load", stato: "valido", artefatto: "01_cloud.ply" },
  { numero: 2, chiave: "02_segment", stato: "valido", artefatto: "02_segmented.ply" },
  { numero: 3, chiave: "03_downsample", stato: "valido", artefatto: "03_downsampled.ply" },
]);
assert.equal(passoDaMostrare(3), 3, "il ripiego risponde sullo stato di un evento fa");
""")


def test_il_cambio_d_asse_riallinea_il_taglio_sulla_geometria_mostrata(tmp_path):
    """Il ripiego cambia anche il gestore del cursore del taglio, e li' non
    arrivava nessun controllo.

    Scelto lo step 11 il viewport porta il volume dello step 9: passare 11 a
    `riallineaTaglio` spegne il comando del taglio sotto una geometria che si
    puo' tagliare -- lo stesso difetto di prima, spostato sul comando.
    Misurato il 24/08/2026: rimesso `riallineaTaglio(stepMostrato)`, la suite
    resta verde.

    Il gestore e' una riga di registrazione e non una funzione, quindi si
    prende dal sorgente vero e si esegue: una ricerca testuale passerebbe anche
    con l'argomento capovolto, che e' il difetto per cui questo file esegue.
    """
    registrazione = re.search(
        r"^asseTaglio\.addEventListener\(.*\);$", _modulo(), flags=re.MULTILINE
    )
    assert registrazione is not None, "il gestore del cambio d'asse non e' piu' una riga sola"

    _esegui(tmp_path, _DOM + _costante("STEP_CON_GEOMETRIA") + _funzioni("passoDaMostrare")
            + _RIPIEGO + """
let allineato = "mai";
function riallineaTaglio(numero) { allineato = numero; }
const asseTaglio = document.getElementById("taglio-asse");
let stepScelto = 11;
""" + registrazione.group(0) + """
await asseTaglio.scatena("change");
assert.equal(
  allineato, 9,
  "il cambio d'asse riallinea il taglio sullo step scelto invece che su quello mostrato",
);
""")






def test_nessuna_lettura_di_illeggibile_nel_modulo():
    """F1 del giro di correzione: `illeggibile` non e' mai stato un
    identificatore di `app.js` — compariva una volta sola, dentro un
    commento. `corpo === illeggibile` avrebbe sollevato un `ReferenceError`
    alla prima risposta ricevuta da `caricaPrior` o `caricaConfronto`. Il
    sentinella vero e' `corpo == null`, l'idioma gia' in uso nel resto del
    file (`app.js:598`, `:822`)."""
    modulo = _senza_commenti_js(_modulo())
    assert "illeggibile" not in modulo


_BANCO_PRIOR_CONFRONTO = """import assert from 'node:assert/strict';

class Elemento {
  constructor() { this.figli = []; this.testo = ""; this.hidden = false; this.dataset = {}; }
  get childElementCount() { return this.figli.length; }
  set textContent(valore) { this.testo = String(valore); }
  get textContent() { return this.testo; }
  append(...nodi) { this.figli.push(...nodi); }
  replaceChildren(...nodi) { this.figli = nodi; }
}
const perId = new Map();
const document = {
  createElement: () => new Elemento(),
  getElementById(id) {
    if (!perId.has(id)) perId.set(id, new Elemento());
    return perId.get(id);
  },
};
let generazione = 0;
function superata(ordine, corrente = generazione) { return ordine !== corrente; }
async function corpoLetto(risposta) {
  try { return await risposta.json(); } catch { return undefined; }
}
let ultimaGeometria = 0;
function apriGeometria() { ultimaGeometria += 1; return ultimaGeometria; }
let taglioRiallineato = null;
function riallineaTaglio(numero) { taglioRiallineato = numero; }
const vista = {
  svuotate: 0,
  disegnato: null,
  svuota() { this.svuotate += 1; },
  mostraNuvolaPerMembratura(punti, etichette) { this.disegnato = { punti, etichette }; },
};
let risponde = {};
globalThis.fetch = async (url) => risponde[url]();
"""


def _banco_di_caricaPrior() -> str:
    """`caricaPrior` intero, con `mostraMembratureNelViewport`: le due
    condividono `apriGeometria`/`ultimaGeometria`, lo stesso arbitro gia'
    provato su `mostraStep` — non un contatore nuovo per la stessa domanda
    (chi scrive per ultimo nel viewport)."""
    return _BANCO_PRIOR_CONFRONTO + _funzioni(
        "caricaPrior", "disegnaMembrature", "disegnaScartate", "mostraMembratureNelViewport",
    )






















def test_la_scala_del_campo_si_taglia_al_p99_e_non_al_massimo(tmp_path):
    """Un nodo non decide la scala di tutti gli altri.

    Misurato il 22/08/2026 su runs/lab_telaio_v2 sotto peso proprio: il rapporto
    fra il massimo della von Mises e il suo p99 vale 2,18. Una scala lineare
    fino al massimo schiaccia in fondo i 10.968 nodi del contorno perche' uno
    solo sta in cima — non quattordicimila: 14.103 sono i nodi dell'intero
    volume, e alla scala colore non arrivano mai. Chi supera il taglio prende un
    colore dichiarato e la didascalia lo dice: e' un'informazione, non un buco.
    """
    uscita = _esegui(tmp_path, "import assert from 'node:assert/strict';\n"
        + _funzioni_viewport("scalaDelCampo") + """
const valori = new Float32Array(1000);
for (let i = 0; i < 1000; i += 1) valori[i] = 1.0;
valori[999] = 50.0;                       // il nodo isolato in cima
const { taglio, sopraTaglio } = scalaDelCampo(valori);
assert.ok(taglio < 2.0, `il taglio ha seguito il massimo: ${taglio}`);
// Uno solo supera davvero il taglio: gli altri 999 sono legati a 1,0, cioe'
// al taglio stesso. Il rango direbbe 10 (l'1% di mille) e mentirebbe.
assert.equal(sopraTaglio, 1);
console.log("ok");
""")
    assert uscita.strip() == "ok"


def test_i_nodi_sopra_il_taglio_si_contano_per_valore_e_non_per_rango(tmp_path):
    """Giro 1: `n - 1 - indice` e' una quota fissa, non un conteggio.

    Su un campo costante e su un campo tutto a zero nessun nodo supera il
    taglio, eppure la didascalia (e l'aria-label che porta lo stesso testo)
    dichiarava cinque nodi sopra una soglia che nessuno supera. Sotto, la
    definizione e' `valori > taglio`, contati. Il server non ne ha una propria
    da tenere allineata: `X-Sopra-P99` e' stato tolto in f7190bb, e questo e'
    l'unico posto in cui il conteggio esiste.
    """
    uscita = _esegui(tmp_path, "import assert from 'node:assert/strict';\n"
        + _funzioni_viewport("scalaDelCampo") + """
const casi = [
  ["costante", new Float32Array(500).fill(3.5), 0],
  ["zeri", new Float32Array(500), 0],
  ["cinque picchi", Float32Array.from({ length: 500 }, (_v, i) => (i < 495 ? 1 : 50)), 5],
];
for (const [nome, valori, atteso] of casi) {
  const { sopraTaglio } = scalaDelCampo(valori);
  assert.equal(sopraTaglio, atteso, `${nome}: ${sopraTaglio} invece di ${atteso}`);
}
console.log("ok");
""")
    assert uscita.strip() == "ok"


def test_la_frazione_del_campo_non_si_lascia_corrompere_da_un_residuo_non_finito(tmp_path):
    """T1 del giro finale: `mostraMeshPerCampo` non era eseguita da nessun
    test — dovunque la si esercitasse, `vista.mostraMeshPerCampo` era un finto
    che registrava gli argomenti. Le due guardie del colore vivevano dentro
    quella funzione, cioe' dentro three.js, e restavano provate a sottostringa.

    Mutazione che sopravviveva: togliere `Number.isFinite(valore) ? ... : 0` e
    lasciare `Math.min(1, Math.max(0, valore / soglia))`. Applicata davvero
    dopo la separazione, questo controllo cade: il nodo con NaN esce NaN invece
    di 0.
    """
    uscita = _esegui(tmp_path, "import assert from 'node:assert/strict';\n"
        + _funzioni_viewport("frazioneDelCampo") + """
// Un residuo non finito resta al fondo della scala, dichiarato zero.
for (const anomalo of [NaN, Infinity, -Infinity, undefined]) {
  const frazione = frazioneDelCampo(anomalo, 2.0);
  assert.equal(frazione, 0, `${anomalo} non e' finito al fondo della scala: ${frazione}`);
}
// E non tocca il nodo prima ne' quello dopo: la rampa e' senza memoria.
const riga = [1.0, NaN, 2.0].map((v) => frazioneDelCampo(v, 2.0));
assert.deepEqual(riga, [0.5, 0, 1.0], `un NaN ha corrotto i vicini: ${riga}`);
console.log("ok");
""")
    assert uscita.strip() == "ok"


def test_la_frazione_del_campo_non_divide_per_un_taglio_nullo(tmp_path):
    """Ingresso degenere: campo costante a zero, quindi taglio zero. Senza la
    guardia `taglio > 0 ? taglio : 1` la divisione da' NaN (0/0) o Infinity, e
    la rampa esce fuori dai due estremi invece di restare un colore solo.

    Mutazione che uccide: sostituire la guardia con `taglio`. Il primo
    `assert.equal` cade con NaN.
    """
    uscita = _esegui(tmp_path, "import assert from 'node:assert/strict';\n"
        + _funzioni_viewport("frazioneDelCampo") + """
assert.equal(frazioneDelCampo(0, 0), 0, "0/0 e' passato");
assert.equal(frazioneDelCampo(3.5, 0), 1, "un valore su un taglio nullo deve saturare, non esplodere");
// Chi sta al taglio o oltre satura all'estremo scuro, chi sta sotto no.
assert.equal(frazioneDelCampo(2.0, 2.0), 1);
assert.equal(frazioneDelCampo(50.0, 2.0), 1, "la frazione e' uscita oltre 1");
assert.equal(frazioneDelCampo(-3.0, 2.0), 0, "un valore negativo e' uscito sotto 0");
console.log("ok");
""")
    assert uscita.strip() == "ok"


def test_ogni_metrica_delle_due_tabelle_di_qualita_ha_la_sua_etichetta():
    """`core/report.py` porta la regola scritta -- «una chiave non si stampa mai,
    si stampa la sua etichetta», con l'unita' dentro l'etichetta perche' un
    numero senza unita' non si ricostruisce -- e il pannello dell'interfaccia
    era l'unica superficie a non rispettarla. Proprio quella che si proietta in
    discussione: `geometric_error · cloud_to_mesh · mean` accanto a `4,41`,
    senza dire se sono millimetri.

    Il controllo non legge un elenco scritto a mano: **esegue** le funzioni che
    le metriche le producono e appiattisce quello che tornano, esattamente come
    fa `righeDellaMetrica`. Una grandezza nuova aggiunta a `surface_metrics` o a
    `volume_metrics` -- o una chiave nuova che PyMeshLab cominci a restituire
    dentro `geometric_error` -- fa diventare rosso questo banco invece di
    comparire a video come chiave nuda, che e' il modo silenzioso di sbagliare.

    Le chiavi senza etichetta non spariscono e non prendono un nome inventato:
    `righeDellaMetrica` stampa la chiave. Questo banco esiste perche' quel
    ripiego resti un ripiego e non diventi lo stato normale delle due tabelle
    su cui si decide se una configurazione va tenuta.
    """
    import numpy as np
    import open3d as o3d

    from meshrec.core import quality

    def appiattite(dizionario: dict, prefisso: str = "") -> list[str]:
        chiavi = []
        for nome, valore in dizionario.items():
            intero = f"{prefisso}{nome}"
            if isinstance(valore, dict) and valore:
                chiavi += appiattite(valore, f"{intero} · ")
            else:
                chiavi.append(intero)
        return chiavi

    # Dal modulo vero e non da un ritaglio di testo: `07_surface_quality`
    # prende le sue sei righe base e le cinque `aspect_ratio` da `SUPERFICIE`
    # con `...SUPERFICIE` (etichette.js), quindi non stanno piu' scritte
    # dentro il blocco del passo -- una regione di testo le direbbe mancanti
    # mentre l'oggetto vero le porta.
    etichette_metriche = _etichette_metriche()

    cubo = o3d.geometry.TriangleMesh.create_box(1.0, 1.0, 1.0)
    vertici = np.asarray(cubo.vertices)
    facce = np.asarray(cubo.triangles)
    # La nuvola sono i vertici stessi: lo scarto vale zero, e non importa --
    # qui si guardano le CHIAVI che il dizionario porta, non i numeri.
    misure7 = quality.surface_metrics(vertici, facce)
    misure7["geometric_error"] = quality.geometric_error(vertici, facce, vertici)

    nodi = np.array([[0.0, 0.0, 0.0], [1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]])
    misure10 = quality.volume_metrics(nodi, np.array([[0, 1, 2, 3]]), 2.0)

    for step, misure in (("07_surface_quality", misure7), ("10_volume_quality", misure10)):
        mancanti = [c for c in appiattite(misure) if c not in etichette_metriche.get(step, {})]
        assert mancanti == [], (
            f"{step}: queste grandezze finiscono a video come chiave nuda, "
            f"senza nome e senza unità: {mancanti}"
        )


def test_un_booleano_non_si_stampa_in_inglese(tmp_path):
    """`String(true)` dava «true» sotto un'etichetta italiana, in
    un'interfaccia la cui lingua e' un impegno dichiarato in PRODUCT.md.

    Provato eseguendo `valoreDellaMetrica`: la stessa correzione scritta come
    `if (valore === true)` lascerebbe `false` in inglese, e leggere il sorgente
    non lo mostrerebbe.
    """
    _esegui(tmp_path, "import assert from 'node:assert/strict';\n"
        + _funzioni("valoreDellaMetrica") + """
assert.equal(valoreDellaMetrica(true), "sì");
assert.equal(valoreDellaMetrica(false), "no");
// I numeri non ci passano in mezzo: 0 e 1 non sono «no» e «sì», sono conteggi.
assert.equal(valoreDellaMetrica(0), "0");
assert.equal(valoreDellaMetrica(1), "1");
// E le stringhe restano quello che sono: il server ne manda gia' di italiane
// («non richiesto»), e tradurle qui vorrebbe dire una seconda tabella.
assert.equal(valoreDellaMetrica("crop"), "crop");
""")


def test_la_chiave_della_scala_vive_solo_dove_il_colore_e_una_misura(tmp_path):
    """Una rampa di colore senza chiave non e' una misura: e' una macchia. Le
    immagini di questa vista finiscono in appendice a un documento stampato,
    staccate da tutto il resto, e la didascalia da sola dice i numeri ma non
    dice quale colore vale quale numero.

    Il contrario e' peggio, ed e' il motivo per cui questo banco esiste: una
    barra rimasta accesa sotto una nuvola grigia dichiara che quel grigio vale
    qualcosa. Per questo la chiave si spegne in `apriGeometria`, cioe' in testa
    a OGNI strada che disegna, e la riaccendono solo le due che colorano per
    misura -- come `togliFantasma` sta in testa a `svuota()` e per la stessa
    ragione.

    Il terzo caso e' il campo che non ha una scala scrivibile: la didascalia
    dice gia' «scala non disponibile», e una barra colorata sotto quella frase
    la contraddirebbe.

    Il gradiente viene dalla costante che colora i vertici, non da una copia:
    e' l'unico modo perche' la chiave non dichiari una scala che il pezzo non ha.
    """
    _esegui(tmp_path, _DOM + _costante_viewport("RAMPA") + "\n"
        + _funzioni_viewport("numeroDelCampo")
        + _funzioni("scalaDellaVista", "mostraLaScala", "apriGeometria") + """
let ultimaGeometria = 0;
const chiave = document.getElementById("scala");
const massimo = document.getElementById("scala-massimo");

mostraLaScala(12.5, "mm");
assert.equal(chiave.hidden, false, "la chiave non si accende dove il colore misura");
assert.equal(massimo.textContent, "12,5 mm", "la chiave non porta il taglio con la sua unità");
assert.equal(document.getElementById("scala-minimo").textContent, "0",
  "l'estremo chiaro non e' lo zero: frazioneDelCampo divide per il taglio e blocca sotto zero");
const dipinto = document.getElementById("scala-rampa").style.background;
assert.ok(dipinto.includes(RAMPA.chiaro) && dipinto.includes(RAMPA.scuro),
  `la chiave dichiara una rampa diversa da quella dipinta: ${dipinto}`);

// Una strada qualunque che disegna: la chiave se ne va con la vista di prima.
apriGeometria();
assert.equal(chiave.hidden, true,
  "la chiave sopravvive al disegno seguente: una barra sotto una nuvola grigia "
  + "dichiara che quel grigio vale qualcosa");

// Un campo senza scala scrivibile: resta spenta, non mostra due trattini.
mostraLaScala(NaN, "mm");
assert.equal(chiave.hidden, true, "senza un taglio scrivibile la chiave si accende comunque");

// E l'unita' segue la grandezza, non e' sempre mm.
mostraLaScala(0.2321, "MPa");
assert.ok(massimo.textContent.endsWith(" MPa"), massimo.textContent);
""")


def test_il_modificatore_sceglie_un_asse_del_mondo_e_uno_solo(tmp_path):
    """I tre modificatori vincolano il trascinamento a un asse: alt attorno a z,
    ctrl attorno a x, shift attorno a y. Senza modificatore resta l'orbita
    libera di sempre, e `null` e' proprio il segnale che la sceglie.

    Due cose che leggere il sorgente non mostra:

    1. **Ogni asse e' un versore, non un asse a caso.** Un vettore sbagliato non
       solleva niente: il modello gira attorno a una direzione obliqua e il
       gesto smette di essere ripetibile, che e' l'unica cosa per cui il vincolo
       esiste.
    2. **Piu' modificatori insieme hanno un esito dichiarato.** Le combinazioni
       si premono per sbaglio; cadere nell'orbita libera proprio mentre si sta
       cercando di vincolare il gesto sarebbe il contrario del vincolo. La
       priorita' e' alt, ctrl, shift -- non e' piu' giusta di un'altra, ma e'
       una, ed e' provata qui.
    """
    _esegui(tmp_path, "import assert from 'node:assert/strict';\n"
        + _funzioni_viewport("asseDelGesto") + """
const nudo = { altKey: false, ctrlKey: false, shiftKey: false };
assert.equal(asseDelGesto(nudo), null, "senza modificatori l'orbita libera sparisce");

assert.deepEqual(asseDelGesto({ ...nudo, altKey: true }), [0, 0, 1], "alt non gira attorno a z");
assert.deepEqual(asseDelGesto({ ...nudo, ctrlKey: true }), [1, 0, 0], "ctrl non gira attorno a x");
assert.deepEqual(asseDelGesto({ ...nudo, shiftKey: true }), [0, 1, 0], "shift non gira attorno a y");

// Versori: una componente a 1, le altre a zero. Un vettore non normalizzato
// gira lo stesso, e di un angolo diverso da quello del gesto.
for (const evento of [{ altKey: true }, { ctrlKey: true }, { shiftKey: true }]) {
  const asse = asseDelGesto({ ...nudo, ...evento });
  assert.equal(asse.filter((c) => c === 1).length, 1, `non e' un versore: ${asse}`);
  assert.equal(asse.filter((c) => c === 0).length, 2, `non e' un versore: ${asse}`);
}

// Due insieme: uno vince, e vince sempre lo stesso.
assert.deepEqual(asseDelGesto({ ...nudo, altKey: true, ctrlKey: true }), [0, 0, 1]);
assert.deepEqual(asseDelGesto({ ...nudo, ctrlKey: true, shiftKey: true }), [1, 0, 0]);
assert.deepEqual(asseDelGesto({ ...nudo, altKey: true, shiftKey: true }), [0, 0, 1]);
// E tutti e tre non cade nell'orbita libera.
assert.notEqual(asseDelGesto({ altKey: true, ctrlKey: true, shiftKey: true }), null);
""")


def test_la_didascalia_dello_scarto_dichiara_sempre_il_proprio_limite(tmp_path):
    """La mappa dello scarto campiona i SOLI vertici, nel verso dalla superficie
    alla nuvola: dove la ricostruzione sbaglia FRA un vertice e l'altro non lo
    vede, e non e' cloud_to_mesh, che sulla stessa corsa da' un numero piu'
    grande (4,897 mm contro 3,898 su lab_crop).

    Il limite sta nella didascalia e non solo nella docstring del server perche'
    l'immagine finisce in appendice a un documento stampato, staccata dalla
    tabella delle metriche: li' la frase e' l'unica cosa che dice che cosa e'
    quel colore. Una mappa diagnostica presentata senza il proprio verso si
    legge come una misura di fedelta', ed e' esattamente il numero mostrato
    senza il controllo che lo smentisce.

    Vale su tutti e tre i rami, quello muto compreso: e' quando la scala non si
    puo' scrivere che la frase resta sola a dire che cosa si sta guardando.
    """
    uscita = _esegui(tmp_path, "import assert from 'node:assert/strict';\n"
        + _funzioni_viewport("numeroDelCampo", "didascaliaDelloScarto") + """
const pieno = didascaliaDelloScarto({ massimo: 72.2, taglio: 12.5, sopraTaglio: 148 });
assert.ok(/sui soli vertici/.test(pieno), `il limite non c'e': ${pieno}`);
assert.ok(/dalla superficie alla nuvola/.test(pieno), `il verso non c'e': ${pieno}`);
assert.ok(pieno.includes("72,2") && pieno.includes("12,5"), pieno);
assert.ok(pieno.includes("148 vertici sopra"), pieno);
// Il massimo sta oltre il taglio della scala: chi guarda la macchia piu' scura
// non sta guardando 72,2, e la didascalia lo dice.
assert.ok(pieno.includes("fuori scala"), pieno);

// Un campo costante: massimo e taglio coincidono, e "fuori scala" sarebbe falso.
const costante = didascaliaDelloScarto({ massimo: 3, taglio: 3, sopraTaglio: 0 });
assert.ok(!costante.includes("fuori scala"), costante);
assert.ok(/sui soli vertici/.test(costante), costante);

// Tutti i valori non finiti: nessuna scala scrivibile, e nessuno zero al posto
// suo -- uno zero qui si leggerebbe "ricostruzione esatta".
const muto = didascaliaDelloScarto({ massimo: NaN, taglio: 0, sopraTaglio: 0 });
assert.ok(muto.includes("massimo non disponibile"), muto);
assert.ok(!/\bmassimo 0\b/.test(muto), muto);
assert.ok(/sui soli vertici/.test(muto), `il limite sparisce sul ramo muto: ${muto}`);
console.log("ok");
""")
    assert uscita.strip() == "ok"


# --------------------------------------------------------------------------
# Ingressi degeneri della scala e dei testi.
#
# Giro 1: la tabella, non un elenco tenuto a mente. Questo progetto ha gia'
# pagato sei giri sulla stessa classe di guasto -- un valore non finito che
# attraversa un controllo -- chiusa quattro volte un caso alla volta prima che
# qualcuno enumerasse. Qui l'elenco e' esplicito: chi aggiunge un testo a video
# lo aggiunge in questa tabella, non lo tiene a mente. Oggi il solo testo con
# numeri dentro e' la didascalia dello scarto dello step 7; quella del campo
# dello step 13 e' uscita con la mappa #161.
# `undefined` sta fra i valori anomali perche' e' cio' che arriva davvero da
# un'intestazione assente.
# --------------------------------------------------------------------------


_TESTI_CHE_FINISCONO_A_VIDEO = [
    ("scarto/massimo",
     'didascaliaDelloScarto({ massimo: VALORE, taglio: 1.5, sopraTaglio: 7 })',
     "4.41"),
    ("scarto/taglio",
     'didascaliaDelloScarto({ massimo: 4.41, taglio: VALORE, sopraTaglio: 7 })',
     "1.5"),
    ("scarto/sopraTaglio",
     'didascaliaDelloScarto({ massimo: 4.41, taglio: 1.5, sopraTaglio: VALORE })',
     "7"),
]

def _banco_dei_testi() -> str:
    return (
        "import assert from 'node:assert/strict';\n"
        + _funzioni_viewport("numeroDelCampo", "didascaliaDelloScarto")
        + "\n"
    )


@pytest.mark.parametrize(
    "nome,espressione,_sano", _TESTI_CHE_FINISCONO_A_VIDEO,
    ids=[nome for nome, _e, _s in _TESTI_CHE_FINISCONO_A_VIDEO],
)
@pytest.mark.parametrize(
    "anomalo", ["NaN", "Infinity", "-Infinity", "undefined"],
    ids=["nan", "+inf", "-inf", "assente"],
)
def test_ogni_numero_che_finisce_a_video_dichiara_invece_di_scrivere_nan(
    tmp_path, nome, espressione, _sano, anomalo,
):
    """20 combinazioni (5 numeri a video x 4 valori che non si possono scrivere).

    L'oracolo e' lo stesso per tutte: un testo non vuoto, e dentro nessun
    "NaN", "Infinity", "undefined", "null" o "∞" -- l'ultimo perche'
    `(Infinity).toLocaleString("it")` non scrive "Infinity", scrive "∞"
    (misurato in node): un oracolo che cercasse solo la parola lascerebbe
    passare meta' dei valori anomali della tabella. Prima di questo giro ne
    sopravvivevano otto: `massimo` non era guardato affatto (a video usciva
    «massimo reale NaN mm» e «massimo Infinity MPa», riprodotto eseguendo), e
    `sopraTaglio` nemmeno — il commento diceva che esce sempre finito da
    `scalaDelCampo`, che e' vero per quel chiamante e non per la funzione.
    """
    uscita = _esegui(tmp_path, _banco_dei_testi() + f"""
const testo = {espressione.replace("VALORE", anomalo)};
assert.ok(typeof testo === "string" && testo.length > 0, `testo vuoto o non stringa: ${{testo}}`);
assert.ok(!/NaN|Infinity|∞|undefined|null/.test(testo), testo);
console.log("ok");
""")
    assert uscita.strip() == "ok"


@pytest.mark.parametrize(
    "nome,espressione,sano", _TESTI_CHE_FINISCONO_A_VIDEO,
    ids=[nome for nome, _e, _s in _TESTI_CHE_FINISCONO_A_VIDEO],
)
def test_lo_stesso_numero_con_un_valore_scrivibile_si_legge(tmp_path, nome, espressione, sano):
    """Controprova della tabella sopra: un valore finito nello stesso posto
    deve arrivare a video davvero, altrimenti la guardia sarebbe cosi' larga da
    dichiarare "non disponibile" anche cio' che si puo' scrivere."""
    uscita = _esegui(tmp_path, _banco_dei_testi() + f"""
const testo = {espressione.replace("VALORE", sano)};
assert.ok(/\\d/.test(testo), `nessun numero nel testo: ${{testo}}`);
assert.ok(!/NaN|Infinity|∞|undefined|null|non disponibile/.test(testo), testo);
console.log("ok");
""")
    assert uscita.strip() == "ok"


def test_la_scala_del_campo_su_un_campo_costante_non_degenera(tmp_path):
    """max == min: nessuna divisione per zero, nessun taglio NaN. La legenda
    resta leggibile anche quando non c'e' nessun picco da isolare."""
    uscita = _esegui(tmp_path, "import assert from 'node:assert/strict';\n"
        + _funzioni_viewport("scalaDelCampo") + """
const costante = new Float32Array(500).fill(3.5);
const { taglio, sopraTaglio } = scalaDelCampo(costante);
assert.ok(Number.isFinite(taglio), `il taglio non e' finito su un campo costante: ${taglio}`);
assert.equal(taglio, 3.5);
assert.equal(sopraTaglio, 0, "nessun nodo supera un taglio pari al valore di tutti");
console.log("ok");
""")
    assert uscita.strip() == "ok"


def test_la_scala_del_campo_ignora_nan_e_infinito_senza_incantarsi(tmp_path):
    """NaN e Infinity in mezzo ai valori non devono decidere la scala in
    silenzio: filtrati, il taglio resta quello dei valori finiti."""
    uscita = _esegui(tmp_path, "import assert from 'node:assert/strict';\n"
        + _funzioni_viewport("scalaDelCampo") + """
const valori = new Float64Array(100).fill(1.0);
valori[0] = NaN;
valori[1] = Infinity;
valori[2] = -Infinity;
const { taglio, sopraTaglio } = scalaDelCampo(valori);
assert.ok(Number.isFinite(taglio), `NaN/Infinity hanno prodotto un taglio non finito: ${taglio}`);
assert.equal(taglio, 1.0, "i tre valori non finiti non dovevano contribuire al taglio");
assert.equal(sopraTaglio, 0, "nessun valore finito supera 1,0");
console.log("ok");
""")
    assert uscita.strip() == "ok"


def test_il_bottone_dello_scarto_non_fa_costruire_due_volte_lo_stesso_albero(tmp_path):
    """Dall'altra parte di quel clic c'e' un albero costruito sulla nuvola
    segmentata -- 4.229.538 punti su lab_crop -- e la memoria del server tiene
    UNA voce, scritta solo a conto finito. Due clic di seguito lo fanno
    costruire due volte: secondi di attesa e un centinaio di megabyte spesi per
    un risultato identico, che l'arbitrato butterebbe via comunque.

    E il primo clic deve dire che sta succedendo qualcosa. Senza, su una nuvola
    vera lo schermo resta identico per qualche secondo, che e' esattamente ciò
    che un bottone rotto fa vedere. La riga dice l'operazione e non quanto
    manca: nessuno cronometra un albero prima di costruirlo, ed e' la stessa
    regola per cui l'attesa di uno step non porta una percentuale.

    Il bottone torna acceso comunque, anche quando la richiesta finisce male:
    lasciato spento su un errore, l'unica via per riprovare sarebbe riaprire il
    pannello.
    """
    _esegui(tmp_path, _DOM
        + _funzioni_viewport("numeroDelCampo")
        + _funzioni("didascaliaDellaVista", "scalaDellaVista", "mostraLaScala", "pannelloScarto")
        + """
const STEP_CON_SUPERFICIE = 6;
// `ultimoStato` lo dichiara gia' _DOM, ed e' proprio la variabile di modulo che
// il banco deve condividere invece di copiarne una sua.
ultimoStato = [
  { numero: 2, artefatto: "02_segmented.ply" },
  { numero: 6, artefatto: "06_repaired.ply" },
];
// Il posto di mostraScartoDelloStep: qui si prova il bottone, non il disegno.
let corse = 0;
let sblocca;
async function mostraScartoDelloStep() {
  corse += 1;
  await new Promise((risolvi) => { sblocca = risolvi; });
  return true;
}

const pannello = pannelloScarto(0);
const bottone = pannello.figli[pannello.figli.length - 1];
assert.equal(bottone.tag, "button", "il pannello non finisce col proprio comando");
assert.equal(bottone.disabled, undefined, "il bottone nasce spento");

const primo = bottone.scatena("click");
assert.equal(corse, 1);
assert.equal(bottone.disabled, true, "il bottone resta premibile mentre la misura gira");
assert.ok(didascaliaDellaVista().textContent.includes("in corso"),
  `l'attesa non si dichiara: ${didascaliaDellaVista().textContent}`);
// La riga dice l'operazione, non quanto manca: una percentuale qui sarebbe
// inventata.
assert.ok(!/%|\bmancano\b/.test(didascaliaDellaVista().textContent),
  "l'attesa fabbrica un avanzamento che nessuno misura");

// Il secondo clic mentre il primo e' in volo.
await bottone.scatena("click");
assert.equal(corse, 1, "il doppio clic fa costruire l'albero due volte");

sblocca();
await primo;
assert.equal(bottone.disabled, false, "il bottone resta spento dopo la misura");
""")


def _banco_del_campo_dello_step() -> str:
    """`mostraCampoDelloStep`, con `vista` finta e le sue dipendenze vere: la
    stessa arbitrazione (`apriGeometria`/`ultimaGeometria`) gia' provata su
    `mostraNuvolaDelloStep`, applicata alla coppia mesh+campo che questa
    funzione richiede insieme con `Promise.all`.
    """
    return (
        _DOM
        + _costante_viewport("RAMPA") + "\n"
        + _funzioni_viewport("scalaDelCampo", "numeroDelCampo", "didascaliaDelCampo", "unitaDelCampo")
        + _funzioni(
            "didascaliaDellaVista", "ragioneDelRifiuto", "serverMuto", "apriGeometria", "superata",
            "scalaDellaVista", "mostraLaScala", "mostraCampoDelloStep",
        )
        + """
const STEP_CON_CAMPO = 13;
let ultimaGeometria = 0;
const vista = {
  svuotate: 0,
  disegnato: null,
  svuota() { this.svuotate += 1; },
  mostraMeshPerCampo(vertici, facce, valori, scala) {
    this.disegnato = { vertici: vertici.length, facce: facce.length, valori: valori.length, scala };
  },
};
// La didascalia non e' piu' un argomento: sta nel markup, dentro la zona della
// vista, e il modulo la trova per id come fa con #conteggi.
const didascalia = document.getElementById("didascalia-vista");
let risponde = [];
let chiamata = 0;
globalThis.fetch = async () => risponde[chiamata++]();
"""
    )








def _durata_dell_arrivo() -> str:
    """La costante vera di `viewport.js`, non una copia scritta nel banco.

    Gemella di `_costante`, che legge `app.js`. Senza, il banco proverebbe una
    durata che il modulo non usa piu' e resterebbe verde."""
    trovato = re.search(
        r"^export const DURATA_ARRIVO = .*;$", _modulo_viewport(), flags=re.MULTILINE
    )
    assert trovato is not None, "nessuna costante DURATA_ARRIVO in viewport.js"
    return trovato.group(0).removeprefix("export ")



def test_l_arrivo_finisce_e_non_lascia_la_camera_in_un_punto_che_non_esiste(tmp_path):
    """Le due proprieta' che tengono in piedi l'assestamento dell'inquadratura.

    **Finisce.** `disegna()` smonta la transizione sul confronto `frazione >= 1`:
    una frazione che si avvicina a 1 senza arrivarci lascerebbe acceso un
    `aggiornaCamera` per ogni fotogramma, per tutta la durata della sessione, e
    una pagina che resta aperta ore non lo direbbe con nessun sintomo.

    **Non produce NaN.** La frazione moltiplica il raggio e interpola il centro:
    un NaN qui porta la camera in una posizione che non esiste e la scena
    sparisce, senza un errore in console e senza una riga nel registro. Le due
    strade sono una durata nulla (divisione per zero) e un trascorso non finito.
    """
    uscita = _esegui(tmp_path, "import assert from 'node:assert/strict';\n"
        + _durata_dell_arrivo() + "\n"
        + _funzioni_viewport("frazioneDellArrivo") + """
assert.equal(frazioneDellArrivo(0), 0, "l'arrivo non parte dall'inquadratura di prima");
assert.equal(frazioneDellArrivo(DURATA_ARRIVO), 1, "a tempo scaduto la transizione non si smonta");
assert.equal(frazioneDellArrivo(DURATA_ARRIVO * 10), 1, "oltre la durata la frazione scappa");
assert.equal(frazioneDellArrivo(-50), 0, "un trascorso negativo tira la camera all'indietro");

// Monotona e chiusa: un'inquadratura che oltrepassa e torna indietro mostra un
// pezzo piu' grande di quello che e'.
let scorso = -1;
for (let t = 0; t <= DURATA_ARRIVO; t += 5) {
  const frazione = frazioneDellArrivo(t);
  assert.ok(frazione >= scorso, `la frazione torna indietro a ${t} ms`);
  assert.ok(frazione >= 0 && frazione <= 1, `frazione fuori da [0, 1] a ${t} ms: ${frazione}`);
  scorso = frazione;
}

// Le tre strade per il NaN, che nessuna delle due guardie qui sopra vede.
for (const [nome, valore] of [["NaN", NaN], ["Infinity", Infinity], ["assente", undefined]]) {
  assert.equal(frazioneDellArrivo(valore), 1, `un trascorso ${nome} non finisce l'arrivo`);
}
assert.equal(frazioneDellArrivo(10, 0), 1, "durata nulla: la frazione divide per zero");
assert.equal(frazioneDellArrivo(10, -1), 1, "durata negativa: la frazione esce dall'intervallo");
console.log("ok");
""")
    assert uscita.strip() == "ok"


def test_l_elevazione_scavalca_il_polo_invece_di_fermarsi_prima(tmp_path):
    """Il giro verticale si fermava un soffio prima dei due poli.

    `phi` era stretto fra 0,01 e pi greco meno 0,01 da due `Math.min`/`Math.max`,
    uno nel trascinamento e uno nelle frecce. Ogni lato del pezzo restava
    raggiungibile -- l'azimut non ha fermi -- ma il gesto si bloccava senza dire
    perche', e un gesto che si blocca in silenzio si legge come un guasto.

    Le tre cose che questo controllo tiene ferme, e che la correzione poteva
    rompere una per una:

    - il giro si chiude, in avanti e all'indietro. Senza la normalizzazione
      `phi` cresce senza fine, e dopo qualche giro la precisione dei
      trigonometrici si mangia il passo del trascinamento;
    - i due poli si scavalcano, e la misura e' la distanza dall'asse e non
      l'uguaglianza a zero: `Math.sin(Math.PI)` vale 1,22e-16, quindi un
      confronto con zero non vedrebbe il polo non scavalcato. La' `up` e'
      parallelo allo sguardo, il prodotto vettoriale e' lungo 1e-32 e
      normalizzarlo amplifica il solo arrotondamento: l'inquadratura esce a
      caso, o NaN, e la scena sparisce senza un errore. Non e' un caso di
      scuola --
      `phi` nasce a 1,0 e la freccia in su lo scala di 0,1, quindi dieci battute
      ci arrivano esatte, ed e' la strada che il banco percorre davvero;
    - oltre il polo il seno cambia segno. E' cio' che `aggiornaCamera` legge per
      capovolgere `up`, e senza quel cambio di segno il giro resta possibile ma
      l'immagine si ribalta di scatto nel punto in cui dovrebbe essere piu'
      continua.
    """
    uscita = _esegui(tmp_path, "import assert from 'node:assert/strict';\n"
        + _funzioni_viewport("oltreIlPolo") + """
const GIRO = Math.PI * 2;
const vicino = (a, b) => Math.abs(a - b) < 1e-9;

// Lontano dai poli il passo arriva dove deve, nei due versi.
assert.ok(vicino(oltreIlPolo(1.0, 0.2), 1.2), "il passo in avanti non arriva dove chiede");
assert.ok(vicino(oltreIlPolo(1.0, -0.2), 0.8), "il passo all'indietro non arriva dove chiede");

// Il giro si chiude nei due versi. Senza, l'elevazione cresce senza fine e dopo
// qualche giro la precisione dei trigonometrici si mangia il passo del gesto.
assert.ok(vicino(oltreIlPolo(GIRO - 0.1, 0.2), 0.1), "il giro non si chiude in avanti");
assert.ok(vicino(oltreIlPolo(0.1, -0.2), GIRO - 0.1), "il giro non si chiude all'indietro");

// I poli. La misura e' la distanza dall'asse e non l'uguaglianza a zero:
// `Math.sin(Math.PI)` vale 1,22e-16 e il modulo non restituisce mai pi greco
// esatto, quindi un confronto con zero passerebbe anche col polo non
// scavalcato. E non serve l'esattezza per fare danno: a 1e-16 dall'asse il
// prodotto vettoriale con `up` e' lungo 1e-32, e normalizzarlo amplifica il
// solo arrotondamento. La soglia sta mille volte sotto lo scavalcamento vero
// (1e-3) e dieci ordini sopra il rumore.
const LONTANO_DALL_ASSE = 1e-6;
const dallAsse = (phi, passo) => Math.abs(Math.sin(oltreIlPolo(phi, passo)));
assert.ok(dallAsse(0.1, -0.1) > LONTANO_DALL_ASSE, "il polo nord lascia la camera sull'asse");
assert.ok(dallAsse(Math.PI - 0.1, 0.1) > LONTANO_DALL_ASSE, "il polo sud lascia la camera sull'asse");
assert.ok(dallAsse(GIRO - 0.1, 0.1) > LONTANO_DALL_ASSE, "il polo raggiunto girando non viene scavalcato");
// La fascia appena SOTTO il giro intero, che e' lo stesso polo visto dall'altra
// parte: un passo negativo minuscolo da un'elevazione quasi nulla ci finisce
// dentro, e da 0 quel valore dista un giro intero. Guardando solo 0 e pi greco
// non lo vedrebbe nessuno, e la camera resterebbe a un ulp dall'asse.
assert.ok(dallAsse(1e-15, -2e-15) > LONTANO_DALL_ASSE, "il polo appena sotto il giro intero non viene visto");

// La strada vera, e non un caso di scuola: l'elevazione nasce a 1,0 e la freccia
// in su la scala di 0,1, quindi dieci battute ci arrivano sopra.
let phi = 1.0;
for (let i = 0; i < 10; i += 1) phi = oltreIlPolo(phi, -0.1);
assert.ok(Math.abs(Math.sin(phi)) > LONTANO_DALL_ASSE, "dieci frecce in su portano la camera sull'asse");

// Il gesto non si ferma MAI: e' il difetto che questa funzione esiste per
// chiudere. Duecento battute nello stesso verso sono piu' di tre giri interi, e
// nessuna deve lasciare l'elevazione dov'era -- ne' fermandosi contro un fermo,
// ne' uscendo dalla fascia del polo dalla parte da cui si sta arrivando.
let corrente = 1.0;
for (let i = 0; i < 200; i += 1) {
  const dopo = oltreIlPolo(corrente, -0.1);
  assert.notEqual(dopo, corrente, `il gesto si e' fermato alla battuta ${i}, a phi ${corrente}`);
  assert.ok(Math.abs(Math.sin(dopo)) > LONTANO_DALL_ASSE, `la camera finisce sull'asse alla battuta ${i}`);
  corrente = dopo;
}

// Di la' dal polo l'alto del mondo e' dall'altra parte, ed e' il segno del seno
// che aggiornaCamera legge per capovolgere `up`. Senza il cambio di segno il
// giro resta possibile ma l'immagine si ribalta di scatto.
assert.ok(Math.sin(oltreIlPolo(Math.PI - 0.05, 0.1)) < 0, "scavalcato il polo il seno non cambia segno");
assert.ok(Math.sin(oltreIlPolo(Math.PI - 0.05, -0.1)) > 0, "prima del polo il seno non e' positivo");

// E all'incontrario: SFIORARE un polo senza volerlo scavalcare non deve
// capovolgere niente. Chi si ferma dentro la fascia ne esce dalla parte da cui
// stava andando, non da quella opposta -- uscire sempre in avanti farebbe
// ribaltare l'immagine per un movimento che non si vede. Il passo qui e' piu'
// piccolo di un pixel di trascinamento, quindi la difesa e' preventiva: il
// gesto vero non ci arriva, ma la funzione non deve dipendere da questo.
assert.ok(Math.sin(oltreIlPolo(Math.PI - 0.0005, -0.0001)) > 0, "sfiorare il polo da sotto capovolge l'immagine");
assert.ok(Math.sin(oltreIlPolo(Math.PI + 0.0005, 0.0001)) < 0, "sfiorare il polo da sopra capovolge l'immagine");

// E lo scavalcamento non si vede: nessuna battuta sposta l'elevazione piu' di un
// millesimo di radiante -- sei centesimi di grado -- oltre cio' che il gesto ha
// chiesto.
for (const [da, passo] of [[0.1, -0.1], [Math.PI - 0.1, 0.1], [GIRO - 0.05, 0.05], [1.0, 0.3]]) {
  const chiesto = (((da + passo) % GIRO) + GIRO) % GIRO;
  const avuto = oltreIlPolo(da, passo);
  const salto = Math.min(Math.abs(avuto - chiesto), GIRO - Math.abs(avuto - chiesto));
  assert.ok(salto <= 1e-3 + 1e-12, `lo scavalcamento sposta di ${salto} rad, e si vede`);
}
console.log("ok");
""")
    assert uscita.strip() == "ok"


def test_i_due_gesti_dell_elevazione_passano_dalla_stessa_funzione():
    """Il fermo stava in DUE posti, il trascinamento e le frecce, e toglierlo da
    uno solo lo lascia raggiungibile dall'altro. Qui non si esegue niente: le
    due righe vivono dentro gestori annidati in `creaViewport`, che tocca
    three.js e non si monta in un banco. Il controllo guarda che nessuna delle
    due riscriva `orbita.phi` per conto proprio.
    """
    sorgente = _modulo_viewport()
    scritture = re.findall(r"orbita\.phi = ([^;\n]+)", sorgente)
    assert len(scritture) >= 3, f"solo {len(scritture)} scritture di orbita.phi: il regex non morde piu'"
    fuori = [s for s in scritture if "oltreIlPolo(" not in s]
    assert not fuori, f"l'elevazione viene scritta senza scavalcare il polo: {fuori}"


def test_l_alto_del_mondo_segue_il_polo_scavalcato():
    """Meta' della correzione sta dove nessun banco arriva.

    `aggiornaCamera` vive dentro `creaViewport`, che tocca three.js e non si
    monta: qui non si esegue niente, si guarda l'ordine di due righe. Ed e'
    l'ordine il punto -- `lookAt` legge `camera.up` nell'istante in cui viene
    chiamata, quindi scriverlo dopo non ha alcun effetto e non lascia nessun
    sintomo: la scena resta, e si capovolge di scatto solo scavalcando un polo.
    Senza il segno del seno il giro completo resta possibile ma illeggibile.
    """
    corpo = _sorgente_di("aggiornaCamera", _modulo_viewport())
    assert "camera.up.set(" in corpo, "`up` non viene piu' scritto: oltre il polo l'immagine si ribalta"
    alto = corpo.index("camera.up.set(")
    guarda = corpo.index("camera.lookAt(")
    assert alto < guarda, "`up` viene scritto dopo lookAt, che l'aveva gia' letto"
    assert "Math.sin(phi)" in corpo[alto:guarda], "`up` non segue piu' il segno del seno dell'elevazione"


def test_un_valore_troppo_lungo_per_la_colonna_del_numero_viene_marcato(tmp_path):
    """Il difetto misurato a schermo: «339.710» reso a una cifra per riga.

    La tabella ha due colonne, e in una zona da 22rem non ci stanno. Lo step 7
    annida due dizionari dentro `geometric_error` e questa funzione appiattisce
    il percorso in un'etichetta sola: «geometric_error · cloud_to_mesh ·
    diag_mesh_1» sono 44 caratteri. Con `grid-template-columns: auto 1fr` la
    colonna dell'etichetta si prendeva 298 dei 319 pixel disponibili, misurati
    nel browser, e al valore ne restavano 8,98 -- una cifra. Non sbordava,
    perche' `overflow-wrap: anywhere` da' al numero il permesso di spezzarsi
    ovunque: invece di reclamare spazio, scendeva in verticale.

    Meta' della correzione e' nel foglio (la colonna del valore ora e'
    dichiarata) e la sorveglia test_stile. Questa meta' e' qui: i valori che in
    quella colonna non ci stanno comunque -- una lista chiusa da JSON.stringify
    -- vanno marcati, perche' passino sotto la propria etichetta a tutta
    larghezza invece di stringersi in colonna.
    """
    _esegui(tmp_path, _DOM + _costante("VALORE_LARGO") + "\n"
        + _costante("CLASSE_VALORE_LARGO") + "\n"
        + _funzioni("valoreDellaMetrica", "righeDellaMetrica") + """
const corta = righeDellaMetrica("vertices", 339710);
assert.equal(corta[1].textContent, "339.710", "il numero non passa piu' da toLocaleString");
assert.equal(corta[1].className, "", "un numero che nella colonna ci sta viene mandato sotto l'etichetta");

// Il caso vero, non inventato: `06_repair · hole_areas` e' una lista di
// ventiquattro aree, 540 caratteri chiusi da JSON.stringify. In colonna sono
// trentanove righe; a tutta larghezza dodici.
const aree = Array.from({ length: 24 }, (_, i) => 1.330381131055531 / (i + 1));
const lunga = righeDellaMetrica("hole_areas", aree);
assert.ok(lunga[1].textContent.length > 400, "il banco non sta piu' provando una lista lunga davvero");
assert.equal(
  lunga[1].className, CLASSE_VALORE_LARGO,
  "una lista da 540 caratteri resta nella colonna del numero, a un carattere per riga",
);

// Il confine, dai due lati, ed e' la larghezza dichiarata della colonna: non un
// numero scelto qui.
assert.equal(
  righeDellaMetrica("x", "a".repeat(VALORE_LARGO))[1].className, "",
  "un valore che ci sta esatto viene mandato sotto l'etichetta lo stesso",
);
assert.equal(
  righeDellaMetrica("x", "a".repeat(VALORE_LARGO + 1))[1].className, CLASSE_VALORE_LARGO,
  "un valore piu' lungo della colonna ci resta dentro e si spezza",
);

// L'annidamento non e' cambiato: il percorso resta appiattito nell'etichetta, ed
// e' proprio lui a rendere l'etichetta lunga.
const annidata = righeDellaMetrica("geometric_error", { cloud_to_mesh: { RMS: 3.8984 } });
assert.equal(annidata.length, 2, "un dizionario di dizionari non produce piu' una riga sola");
assert.equal(
  annidata[0].textContent, "geometric_error \u00b7 cloud_to_mesh \u00b7 RMS",
  "il percorso non e' piu' appiattito nell'etichetta",
);
""")


def test_le_stringhe_mostrate_portano_gli_accenti_italiani():
    """La regola sta scritta nel piano del giro 3 e non era mai stata eseguita.

    «Sorgenti in ASCII, con una sola eccezione dichiarata: le stringhe mostrate
    all'utente portano gli accenti italiani veri.» I commenti, i nomi e il resto
    del codice restano ASCII; cio' che finisce a video no. Il motivo non e'
    ortografico ma di prodotto: PRODUCT.md dichiara che questa interfaccia viene
    proiettata durante la discussione e che le viste finiscono in un'appendice
    cartacea, e «Qualita'» su un muro davanti alla commissione si legge come un
    refuso di tesi, non come una convenzione di sorgente. Nella stessa frase
    convivevano gia' le virgolette caporali e la lineetta lunga: l'apostrofo al
    posto dell'accento era l'unico segno rimasto indietro.

    Questo controllo esiste perche' la deriva e' gia' successa in questa
    direzione: una passata sul testo ha «corretto» `Qualita` in `Qualita'`
    allineandolo ai commenti, che la regola esclude. Guarda le sole regioni
    mostrate -- il testo fra i tag, gli attributi che portano testo, e i
    letterali sulle righe di codice -- e lascia in pace tutto il resto.

    **Confine dichiarato:** questo controllo copre i tre file dell'interfaccia,
    non le stringhe che arrivano dal server. Quelle sono un'altra superficie e
    sono molte -- 275 parole tronche in quindici moduli Python, fra cui le
    descrizioni dei parametri di `core/config.py`, che il pannello mostra, e
    `core/report.py`, che finisce nell'appendice cartacea. Finche' non vengono
    fatte anche quelle, nella colonna di destra convivono le due grafie.
    """
    tronca = re.compile(r"\b[A-Za-z]*[aeiou]'(?![A-Za-z\u00e0\u00e8\u00e9\u00ec\u00f2\u00f9])")
    # `po'` e' un troncamento corretto, non un accento mancante: se comparira'
    # non e' un difetto. Nessun'altra parola tronca lo e'.
    lecite = {"po'"}

    def tronche(testo):
        return {p for p in tronca.findall(testo) if p not in lecite}

    markup = _markup()
    senza_commenti = re.sub(r"<!--.*?-->", "", markup, flags=re.S)
    mostrate = re.findall(r">([^<>]+)<", senza_commenti)
    # Il testo che vive in un attributo si vede quanto quello fra i tag:
    # `data-testo-vuoto` e' cio' da cui app.js RIPRISTINA lo stato vuoto, e
    # lasciarlo indietro fa ricomparire la vecchia grafia dopo un ripristino.
    mostrate += re.findall(r'(?:placeholder|aria-label|title|data-testo-vuoto)="([^"]*)"', senza_commenti)

    letterale = re.compile(r"`[^`]*`|\"[^\"\\]*\"|'[^'\\]*'")
    for sorgente in (_modulo(), _modulo_viewport()):
        for riga in sorgente.split("\n"):
            if riga.strip().startswith(("//", "*", "/*")):
                continue
            taglio = riga.find(" // ")
            codice = riga[:taglio] if taglio >= 0 else riga
            mostrate += [m[1:-1] for m in letterale.findall(codice)]

    assert len(mostrate) > 100, f"solo {len(mostrate)} regioni mostrate: l'estrazione non morde piu'"
    guasti = {p for testo in mostrate for p in tronche(testo)}
    assert not guasti, (
        "stringhe mostrate con l'apostrofo al posto dell'accento: "
        + ", ".join(sorted(guasti))
    )


def test_il_marchio_del_cambio_sta_solo_sulle_righe_che_sono_cambiate(tmp_path):
    """Il marchio e' un evento, e un evento dichiarato dove non e' successo
    niente e' un numero mostrato senza un controllo che lo smentisca.

    Tre modi di romperlo, tutti invisibili guardando la colonna ferma:

    1. **La prima passata.** Confrontato con niente, ogni step risulta cambiato:
       all'avvio la colonna si accenderebbe tutta dicendo che e' appena successo
       qualcosa che era gia' cosi'.
    2. **Lo stato che non cambia.** Gli eventi arrivano due volte al secondo per
       tutta la corsa: un marchio che non guarda il valore precedente
       lampeggerebbe su undici righe per i trentaquattro secondi di uno step.
    3. **Il marchio che resta attaccato.** Tolto solo al cambio successivo,
       l'animazione girerebbe una volta e mai piu', perche' e' l'attributo che
       ricompare a farla ripartire.

    Provato eseguendo `disegnaStep`, non cercando `data-cambiato` nel sorgente:
    la stessa guardia scritta al contrario lascia la sottostringa al suo posto.
    """
    _esegui(tmp_path, _DOM + _funzioni(*_COLONNA) + """
const marchiati = () =>
  elenco.children.flatMap((riga, i) => ("cambiato" in riga.dataset ? [i] : []));

disegnaStep(STEPS);
assert.deepEqual(marchiati(), [], "alla prima passata la colonna si accende tutta");

// Lo stesso stato, di nuovo: e' cio' che arriva due volte al secondo.
disegnaStep(STEPS);
assert.deepEqual(marchiati(), [], "uno stato che non cambia si dichiara cambiato");

// Solo il secondo step finisce.
disegnaStep(STEPS.map((v) => (v.numero === 2 ? { ...v, stato: "valido" } : v)));
assert.deepEqual(marchiati(), [1], "il marchio non e' sulla riga cambiata, o non e' solo sua");
assert.equal(elenco.children[1].className, "stato-valido",
  "il marchio e' finito dentro la classe di stato: due canali diventati uno");

// L'evento dopo, mezzo secondo piu' tardi: niente e' cambiato di nuovo.
disegnaStep(STEPS.map((v) => (v.numero === 2 ? { ...v, stato: "valido" } : v)));
assert.deepEqual(marchiati(), [],
  "il marchio resta attaccato: l'animazione non puo' piu' ripartire");

// E riparte quando lo stato cambia davvero un'altra volta.
disegnaStep(STEPS.map((v) => (v.numero === 2 ? { ...v, stato: "fallito" } : v)));
assert.deepEqual(marchiati(), [1], "il secondo cambio sulla stessa riga non si vede");
""")
    assert ".elenco-step [data-cambiato]" in _foglio(), (
        "il foglio non si aggancia piu' a data-cambiato: il marchio resta senza animazione"
    )


def test_il_marchio_sui_numeri_sta_solo_sulle_metriche_che_sono_cambiate(tmp_path):
    """Gemello del banco qui sopra, sull'altra meta' dello schermo.

    Il fatto che lo rende necessario: quando una corsa finisce, `apriDettaglio`
    riscrive da sola le metriche dello step aperto -- nessuno le ha chieste in
    quel momento -- e un valore sostituito in silenzio e' a video identico a
    quello di prima.

    I tre modi di sbagliarlo sono i tre modi di dichiarare un evento che non e'
    successo, e nessuno si vede guardando il pannello fermo:

    1. **La prima apertura.** Confrontato con niente, ogni numero risulta
       cambiato e il pannello si accende tutto appena lo si apre.
    2. **La riapertura.** Riaprire lo stesso step e' il gesto piu' frequente
       della colonna, e li' non e' cambiato niente.
    3. **Lo step diverso.** Cambiando pannello a cambiare e' il soggetto: un
       numero guardato per la prima volta non e' un numero cambiato. Stessa
       ragione per la metrica che compare adesso, che e' nata, non cambiata.

    Provato eseguendo la funzione, non cercando `data-cambiato` nel sorgente: la
    stessa guardia scritta al contrario lascia la sottostringa al suo posto.
    """
    _esegui(tmp_path, _DOM + _costante("VALORE_LARGO") + "\n" + _costante("CLASSE_VALORE_LARGO")
        + "\nlet metricheMostrate = { numero: null, valori: new Map() };\n"
        + _funzioni("righeDellaMetrica", "valoreDellaMetrica", "marcaLeMetricheCambiate") + """
// La stessa composizione del pannello: le famiglie appiattite tutte insieme e
// poi marcate, che e' l'ordine in cui apriDettaglio le costruisce.
const disegna = (numero, metriche) => marcaLeMetricheCambiate(
  numero,
  Object.entries(metriche).flatMap(([nome, valore]) => righeDellaMetrica(nome, valore)),
);
const accesi = (righe) =>
  righe.flatMap((n) => ("cambiato" in n.dataset ? [n.textContent] : []));
// Il valore di prima e' un `dd` FRATELLO con la classe `prima`, non un figlio
// del valore: cosi' il `dd` del valore resta intatto e questa stessa funzione
// lo puo' rileggere al giro dopo per il confronto.
const storia = (righe) =>
  righe.flatMap((n) => (n.className === "prima" ? [n.textContent] : []));

// Annidata apposta: e' la forma vera dello step 7, e la chiave con cui si
// confronta e' l'etichetta appiattita, non il nome della famiglia.
const PRIMA = { vertices: 19314, geometric_error: { mean: 4.41, max: 72.2 } };
assert.deepEqual(accesi(disegna(7, PRIMA)), [],
  "alla prima apertura il pannello si accende tutto");

assert.deepEqual(accesi(disegna(7, PRIMA)), [],
  "una riapertura senza cambiamenti dichiara un cambiamento");

// Una corsa finisce: un solo numero e' diverso, e la famiglia accanto no.
const DOPO = { vertices: 19314, geometric_error: { mean: 3.9, max: 72.2 } };
// Una passata sola, guardata da due parti: chiamare `disegna` due volte
// consumerebbe il confronto, perche' la seconda troverebbe i valori che la
// prima ha appena memorizzato e non marcherebbe piu' niente.
const passata = disegna(7, DOPO);
assert.deepEqual(accesi(passata), ["3,9"],
  "il marchio non e' sul solo numero cambiato, o non e' solo suo");

// Il numero di prima e' quello vero, e viaggia in una riga sua.
assert.deepEqual(storia(passata), ["l'ultima volta 4,41"],
  "la riga marcata non porta il valore che aveva l'ultima volta");

// Il `dd` del valore non e' stato toccato: se il valore di prima gli finisse
// dentro, `textContent` tornerebbe i due numeri e il confronto del giro dopo
// non combacerebbe piu' con niente.
assert.deepEqual(accesi(passata), ["3,9"],
  "il valore di prima e' finito DENTRO il valore di adesso");

// IL TRANELLO, ed e' la ragione per cui questo banco esiste nella forma che
// ha. `marcaLeMetricheCambiate` appende il valore di prima DENTRO il `dd` e al
// giro seguente rilegge il `dd` per confrontarlo. Rileggendolo dopo l'append,
// la chiave memorizzata sarebbe "3,9prima 4,41" invece di "3,9", e alla
// passata dopo NIENTE combacerebbe piu': ogni riga risulterebbe cambiata per
// sempre e il marchio, che esiste per dire «guarda questo», si accenderebbe su
// tutto. Due passate identiche di fila sono l'unico modo di vederlo: la prima
// appende, la seconda dice se cio' che e' stato memorizzato era il valore o il
// valore piu' la sua storia.
assert.deepEqual(accesi(disegna(7, DOPO)), [],
  "ripetuta identica, la passata dichiara cambiato tutto: il valore memorizzato "
  + "porta dentro anche quello di prima");

assert.deepEqual(accesi(disegna(10, { vertices: 1 })), [],
  "cambiando step si dichiara cambiato un numero solo guardato per la prima volta");

assert.deepEqual(accesi(disegna(10, { vertices: 1, min_ratio: 0.21 })), [],
  "una metrica che compare adesso si dichiara cambiata invece che nata");
""")
    assert ".metriche dd[data-cambiato]" in _foglio(), (
        "il foglio non veste piu' il marchio sui numeri: il cambio resta senza animazione"
    )
    assert ".metriche dd.prima" in _foglio(), (
        "il foglio non veste piu' il valore di prima: senza `grid-column: 1 / -1` finisce\n        nella colonna da 14ch del valore, che esiste apposta perche' un numero non\n        si spezzi, e il volume racchiuso ci va a capo due volte"
    )


def test_l_esito_della_corsa_arriva_con_la_stessa_comparsa_dell_errore():
    """Le due righe che arrivano senza che nessuno le chieda hanno lo stesso
    segno d'arrivo.

    `#esito` e' `aria-live="polite"` proprio perche' il suo testo compare da
    solo a fine corsa, dopo attese di decine di secondi: chi guarda lo schermo
    non ha lo stesso canale di chi lo ascolta, e in una regione ferma un testo
    nuovo non si distingue da uno che stava li' da prima.

    Sulla stessa regola del foglio e non su una propria: due animazioni gemelle
    scritte separate divergono alla prima modifica di una delle due.
    """
    regola = next(
        (r for r in _foglio().split("\n") if "animation: comparsa" in r),
        None,
    )
    assert regola is not None, "nessuna regola usa piu' la comparsa"
    assert ".esito:not(:empty)" in regola, (
        f"l'esito arriva senza segno d'arrivo: {regola}"
    )


def test_ogni_elemento_che_il_modulo_cerca_esiste_nel_markup():
    """`getElementById` non solleva: restituisce `null`.

    Il difetto sta tutto qui. Rinominato o tolto un `id` da `index.html`, il
    modulo non si accorge di niente finche' qualcuno non tocca quel `null` — e
    il `TypeError` arriva dentro una funzione asincrona, cioe' in una promessa
    che nessuno guarda: la sezione resta vuota e la pagina non dice nulla. E'
    esattamente la forma di guasto che questa interfaccia non deve avere,
    perche' «vuoto» qui e' anche un esito legittimo.

    Solo le chiamate con una stringa letterale: quelle costruite con un
    template (`errore-${blocco}-${nome}`, app.js:1466) puntano a elementi che
    il modulo stesso fabbrica, e non hanno un `id` da trovare nel markup.
    """
    modulo = _modulo()
    chiesti = set(re.findall(r'getElementById\("([^"]+)"\)', modulo))
    # Se il regex smette di trovare qualcosa il controllo diventa cieco invece
    # che rosso: il modulo ne cerca decine, zero significa che e' cambiata la
    # forma della chiamata, non che il difetto e' sparito.
    assert len(chiesti) > 20, f"solo {len(chiesti)} getElementById letterali: il regex non morde piu'"
    presenti = set(re.findall(r'id="([^"]+)"', _markup()))
    mancanti = sorted(chiesti - presenti)
    assert not mancanti, f"il modulo cerca elementi che il markup non ha: {mancanti}"


def test_il_fantasma_tace_dove_la_geometria_a_video_e_gia_di_un_altro_passaggio(tmp_path):
    """La regola del velo, eseguita: non basta che lo step abbia un passaggio a
    monte, deve anche essere lui quello a video.

    Scelto lo step 8 su una corsa senza semplificazione, `passoDaMostrare`
    ripiega sul 6 e a video c'e' gia' la geometria del 6. Sovrapporgliela di
    nuovo disegnerebbe due volte la stessa cosa, e il conteggio del velo
    ripeterebbe quello sotto: due numeri identici accostati come se misurassero
    un prima e un dopo.

    Il predicato e' uno solo apposta e decide sia se il velo si disegna sia se
    la casella si mostra. Con due -- una tabella per mostrare, questo per
    disegnare -- la casella comparirebbe spuntata su quello step e toccarla nei
    due versi non farebbe nulla.

    Mutazione che lo uccide: togliere `sorgente === chiesto` da
    `fantasmaHaSenso` e lasciare la sola tabella.
    """
    banco = _DOM + _costante("FANTASMA_DI") + "\n" + _funzioni("fantasmaHaSenso") + """
// Lo step chiesto e' anche quello a video: il velo ha senso.
assert.equal(fantasmaHaSenso(2, 2), true);
assert.equal(fantasmaHaSenso(3, 3), true);
assert.equal(fantasmaHaSenso(8, 8), true);
// A video c'e' gia' la geometria di un altro passaggio: tace.
assert.equal(fantasmaHaSenso(8, 6), false);
assert.equal(fantasmaHaSenso(3, 2), false);
// Step senza un passaggio a monte da cui il conteggio cali: tace comunque.
for (const numero of [1, 4, 5, 6, 7, 9, 10, 11, 12, 13]) {
  assert.equal(fantasmaHaSenso(numero, numero), false, `lo step ${numero} non ha un fantasma`);
}
console.log("ok");
"""
    assert _esegui(tmp_path, banco).strip() == "ok"


def test_il_fantasma_dello_step_8_viene_dal_6_e_non_dal_7():
    """Le coppie sono scritte a mano perche' `numero - 1` sarebbe sbagliato.

    Lo step 7 misura la superficie e non produce geometria propria: il
    passaggio con cui l'8 va confrontato e' il 6. Calcolata, la coppia dell'8
    chiederebbe `/api/mesh/7`, che non esiste -- e il velo sparirebbe in
    silenzio, perche' un fantasma che non arriva non e' un errore da
    annunciare.

    Le tre coppie sono anche le sole in cui il conteggio cala davvero: il
    ritaglio, lo sfoltimento, la semplificazione. Fuori di li' due geometrie
    sovrapposte fanno z-fighting e non informano nessuno.

    Mutazione che lo uccide: scrivere `{ 2: 1, 3: 2, 8: 7 }`.
    """
    coppie = _costante("FANTASMA_DI")
    assert "8: 6" in coppie, f"la coppia dello step 8 non viene piu' dal 6: {coppie}"
    assert "8: 7" not in coppie
    # Il velo esiste solo dove il conteggio cala: tre coppie, non undici.
    assert re.findall(r"(\d+): (\d+)", coppie) == [("2", "1"), ("3", "2"), ("8", "6")]


def test_un_download_caduto_a_meta_lo_dice_invece_di_restare_in_caricamento(tmp_path):
    """Il buco che il modulo aveva su tutte e due le tratte della geometria.

    `await risposta.arrayBuffer()` era nudo. Su una nuvola vera il corpo dura
    secondi -- 6,3 milioni di punti sulla scansione di riferimento -- e la rete
    puo' cadere in quella finestra tanto quanto prima della prima risposta. Il
    rigetto usciva da una funzione asincrona il cui esito `ricaricaVista`
    consuma con `.then` e nessuno con `.catch`: nessun messaggio, l'attesa mai
    chiusa, e a video la geometria dello step di prima sotto la scritta
    «caricamento di ...». Indistinguibile da una lettura lenta, per sempre.

    `undefined` e non un buffer vuoto: un ArrayBuffer di zero byte e' un dato
    legittimo, e confonderli tratterebbe una mesh vuota come un guasto di rete.

    Mutazione che lo uccide: rimettere `await risposta.arrayBuffer()` al posto
    di `corpoBinarioLetto(risposta)`.
    """
    _esegui(tmp_path, _banco_di_geometria() + """
const viewport = document.getElementById("viewport");
const conteggi = document.getElementById("conteggi");
risponde = [() => ({
  ok: true,
  headers: { get: (nome) => ({ "X-Points-Drawn": "20", "X-Points-Total": "20" }[nome]) },
  arrayBuffer: async () => { throw new TypeError("Failed to fetch"); },
})];

const esito = await mostraNuvolaDelloStep(2, generazione);

assert.equal(esito, "vuoto", "un download caduto non e' ne' un disegno ne' una risposta scartata");
assert.ok(
  !conteggi.textContent.includes("caricamento"),
  "l'attesa e' rimasta scritta per sempre: " + conteggi.textContent,
);
assert.match(
  conteggi.textContent, /il server non ha risposto/,
  "il download caduto non dice niente: " + conteggi.textContent,
);
assert.ok(vista.svuotate > 0, "la geometria di prima e' rimasta sotto un testo che la smentisce");
""")


def test_una_lettura_superata_non_cancella_l_annuncio_di_quella_che_l_ha_superata(tmp_path):
    """Chi e' stato superato non tocca la scritta dell'attesa: a riscriverla e'
    chi lo ha superato, quando arriva.

    Le due richieste della stessa generazione sono il caso normale, non un caso
    limite: il fronte di discesa ricarica la vista senza aprire una generazione,
    quindi puo' gareggiare con una risposta partita prima. Se la piu' vecchia,
    rientrando, scrivesse i propri conteggi, a video comparirebbero i numeri di
    una lettura scartata mentre quella buona e' ancora in volo -- e su una
    scansione vera quella finestra dura decine di secondi.

    E' il contratto che prima era affidato ad `aria-busy`, tolto perche'
    #conteggi e' figlio di #viewport (index.html:135-136): l'attributo
    sull'antenato zittiva la regione viva invece di descriverla. Qui si misura
    la cosa vera -- che cosa c'e' scritto -- invece del suo surrogato.

    Mutazione che lo uccide: togliere la guardia `if (superata(...)) return
    false` che sta sopra la scrittura dei conteggi.
    """
    _esegui(tmp_path, _banco_di_geometria() + """
const conteggi = document.getElementById("conteggi");
ETICHETTE["02_segment"] = "Segmentazione";
ultimoStato = [{ numero: 2, chiave: "02_segment" }];
let risolvi1, risolvi2;
risponde = [
  () => new Promise((r) => { risolvi1 = r; }),
  () => new Promise((r) => { risolvi2 = r; }),
];
const corpo = (n) => ({
  ok: true,
  headers: { get: (nome) => ({ "X-Points-Drawn": String(n), "X-Points-Total": String(n) }[nome]) },
  arrayBuffer: async () => new ArrayBuffer(n * 12),
});

const vecchia = mostraNuvolaDelloStep(2, generazione);
const nuova = mostraNuvolaDelloStep(2, generazione);
assert.equal(
  conteggi.textContent, "caricamento di Segmentazione...",
  "l'attesa non e' stata dichiarata",
);

// La VECCHIA rientra per prima: e' superata, e la nuova e' ancora in volo.
risolvi1(corpo(1));
assert.equal(await vecchia, false, "la richiesta vecchia ha scritto");
assert.equal(
  conteggi.textContent, "caricamento di Segmentazione...",
  "la richiesta superata ha cancellato l'annuncio di quella che l'ha superata: "
  + conteggi.textContent,
);

risolvi2(corpo(2));
assert.equal(await nuova, true);
assert.match(
  conteggi.textContent, /\\b2\\b/,
  "chi ha disegnato non ha sostituito l'attesa coi propri numeri: " + conteggi.textContent,
);
assert.ok(
  !conteggi.textContent.includes("caricamento"),
  "l'attesa e' rimasta scritta dopo che la geometria era a video",
);
""")


def test_l_attesa_dice_quale_step_sta_leggendo_e_non_inventa_una_percentuale(tmp_path):
    """Che cosa si sta leggendo e' un fatto; quanto manca sarebbe una stima.

    Le librerie non danno un avanzamento, e PRODUCT.md vieta di fabbricare
    precisione che non esiste: una percentuale scritta qui sarebbe un numero che
    nessuna misura sostiene. Si dichiara il nome dello step, che il modulo
    conosce gia'.

    E il nome, non il numero: la colonna mostra «Segmentazione», e «caricamento
    dello step 2» costringerebbe a contare le righe per capire di quale si
    parla -- la stessa ragione per cui la coda della didascalia porta il nome.

    Mutazione che lo uccide: togliere la chiamata a `dichiaraCaricamento` da
    `mostraNuvolaDelloStep`.
    """
    _esegui(tmp_path, _banco_di_geometria() + """
const viewport = document.getElementById("viewport");
const conteggi = document.getElementById("conteggi");
ETICHETTE["02_segment"] = "Segmentazione";
ultimoStato = [{ numero: 2, chiave: "02_segment" }];
// Mai risolta: qui si guarda la finestra dell'attesa, non il suo esito.
risponde = [() => new Promise(() => {})];

mostraNuvolaDelloStep(2, generazione);
await Promise.resolve();

assert.equal(conteggi.textContent, "caricamento di Segmentazione...");
assert.ok(!conteggi.textContent.includes("%"), "l'attesa ha inventato un avanzamento");
assert.equal(
  viewport.getAttribute("aria-busy"), null,
  "aria-busy su #viewport zittisce #conteggi, che gli sta dentro ed e' la regione viva",
);
""")


def _banco_di_esito() -> str:
    """`aggiornaDaStato` e le tre funzioni dell'esito, con il resto stubbato.

    Le quattro sono ritagliate vere: la decisione su come finisce una corsa e'
    pura, ma il CABLAGGIO -- quale regione riceve il testo e chi la svuota
    subito dopo -- e' la meta' che restava fuori dai test finche' viveva dentro
    una freccia anonima.
    """
    return _DOM + _costante("STEP_CON_DECK") + "\n" + _funzioni(
        "nomeDelloStep",
        "durataMisurata",
        "ultimaDurata",
        "durataDellaCorsa",
        "descrizioneDellaCorsa",
        "ultimaRigaDelRegistro",
        "esitoDellaCorsa",
        "mostraEsito",
        # Il titolo della scheda e la notifica: aggiornaDaStato le chiama sul
        # fronte di discesa, e senza il banco cadrebbe su un ReferenceError.
        "titoloConEsito",
        "notificaFuoriDallaScheda",
        # I due «Esegui» seguono la corsa dallo stesso carico di «Annulla»:
        # aggiornaDaStato la chiama, quindi il banco la incontra.
        "spegniLeEsecuzioni",
        "avanzamentoDellaCorsa",
        # L'intervallo in esecuzione sulla colonna: aggiornaDaStato lo segna a
        # ogni frame, e qui la colonna e' vuota (disegnaStep e' stubbato).
        "segnaIntervalloInEsecuzione",
        "aggiornaDaStato",
    ) + """
let corsaInCorso = false;
let eraInCorso = false;
// `stepAperto` no: lo dichiara gia' _DOM, ed e' proprio la variabile di modulo
// che il banco deve condividere invece di copiarne una sua.
let stepScelto = null;
const ricaricate = [];
const riaperte = [];
function disegnaStep(steps) { ultimoStato = steps; }
function apriDettaglio(n) { riaperte.push(n); }
function ricaricaVista(n) { ricaricate.push(n); }
const esito = document.getElementById("esito");
"""


def test_una_corsa_che_finisce_dice_come_e_finita(tmp_path):
    """I tre esiti sono tre fatti diversi, e l'interfaccia non ne diceva nessuno.

    Il fronte di discesa riapriva il pannello e ricaricava la vista, e basta:
    una corsa fallita e una riuscita lasciavano lo schermo nello stesso stato.
    Il registro portava il motivo, ma bisognava sapere di doverlo leggere.

    Un annullamento NON e' un fallimento: e' una scelta di chi guarda. Arriva
    pero' con un codice d'uscita non nullo -- il segnale che lo ha fermato --
    quindi va guardato per primo, altrimenti ogni annullamento si annuncerebbe
    come un guasto. E' l'ordine dei rami, ed e' la cosa che si sbaglia.

    Il soggetto e' «esecuzione» e non il nome dello step: nove degli undici
    nomi sono femminili e due no, quindi nessun participio accorda con tutti e
    «Lettura concluso» sarebbe sbagliato in nove casi su undici.

    Mutazione che lo uccide: spostare il ramo di `annullato` sotto quello di
    `exit_code !== 0`.
    """
    _esegui(tmp_path, _banco_di_esito() + """
ETICHETTE["01_load"] = "Lettura";
const steps = [{ numero: 1, chiave: "01_load", stato: "valido", secondi: 12 }];
// nomeDelloStep legge la variabile di modulo, non l'argomento: e' quella che
// disegnaStep riempie a ogni frame.
ultimoStato = steps;
const base = { in_corso: false, step: 1, a_step: 1, steps, annullato: false };

assert.deepEqual(
  esitoDellaCorsa({ ...base, exit_code: 0 }),
  { errore: null, esito: "Lettura: esecuzione conclusa in 12 s" },
);
assert.deepEqual(
  esitoDellaCorsa({ ...base, exit_code: 1 }),
  {
    errore: "Lettura: esecuzione fallita (codice 1). Il motivo è nel registro, in fondo alla colonna Dettaglio.",
    esito: null,
  },
);
// Annullato, e col codice d'uscita del segnale che lo ha fermato.
assert.deepEqual(
  esitoDellaCorsa({ ...base, exit_code: -15, annullato: true }),
  { errore: null, esito: "Lettura: esecuzione interrotta" },
);
// Ferma senza codice: si tace. Dirlo «conclusa» annuncerebbe riuscita una
// corsa mai partita.
assert.deepEqual(
  esitoDellaCorsa({ ...base, exit_code: null }),
  { errore: null, esito: null },
);
""")


def test_una_corsa_di_piu_step_non_si_annuncia_col_nome_del_primo(tmp_path):
    """`stato.step` e' il capo di PARTENZA e non avanza mai: worker.start lo
    fissa una volta e resta li'.

    Finche' la riga portava il solo capo, una corsa da 1 a 11 si annunciava
    «Lettura in corso» dall'inizio alla fine -- a quattro secondi dall'avvio
    diceva ancora Lettura, che ne era durata 0,03.

    E sull'intervallo la durata non e' quella del capo di partenza: `secondi` e'
    il tempo del solo step 1, e appiccicarlo a una corsa di undici lo
    dichiarerebbe durata dell'intera corsa. Era il numero piu' in vista
    dell'applicazione, e diceva 0,03 s per una corsa che ne aveva impiegati
    dieci.

    La misura giusta adesso c'e' e viene dal lavoratore -- `worker.durata`, il
    tempo del sottoprocesso -- ma il pericolo e' rimasto lo stesso, ed e' su
    quello che questo banco morde: due numeri, uno solo dei due descrive
    l'attesa che c'e' stata.

    Mutazione che lo uccide: togliere il ramo di `unoSolo` da
    `esitoDellaCorsa`, cosi' la durata del capo di partenza torna a valere per
    tutta la corsa.
    """
    _esegui(tmp_path, _banco_di_esito() + """
ETICHETTE["01_load"] = "Lettura";
ETICHETTE["11_export"] = "Esportazione";
const steps = [
  { numero: 1, chiave: "01_load", stato: "valido", secondi: 0.03 },
  { numero: 11, chiave: "11_export", stato: "valido", secondi: 4 },
];
ultimoStato = steps;

assert.deepEqual(
  descrizioneDellaCorsa({ step: 1, a_step: 11, steps }),
  { testo: "da Lettura a Esportazione", unoSolo: false },
);
assert.deepEqual(
  descrizioneDellaCorsa({ step: 1, a_step: 1, steps }),
  { testo: "Lettura", unoSolo: true },
);
// a_step assente: si torna al nome del capo, che non e' un'invenzione.
assert.deepEqual(
  descrizioneDellaCorsa({ step: 1, steps }),
  { testo: "Lettura", unoSolo: true },
);

const intervallo = esitoDellaCorsa({
  in_corso: false, step: 1, a_step: 11, steps, annullato: false, exit_code: 0,
  durata_secondi: 401,
});
assert.ok(
  intervallo.esito.startsWith("da Lettura a Esportazione: esecuzione conclusa in 6 min 41 s"),
  "l'intervallo non porta la durata del lavoratore: " + intervallo.esito,
);
assert.ok(
  !intervallo.esito.includes("0,03"),
  "la durata del primo step si e' spacciata per quella dell'intera corsa: " + intervallo.esito,
);

// Un frame senza il numero -- un server piu' vecchio del foglio, o una corsa
// aperta prima che il lavoratore ne conservasse uno -- tace invece di mettere
// uno zero: e' la stessa regola per cui `ultimaDurata` non formatta un trattino.
const muto = esitoDellaCorsa({
  in_corso: false, step: 1, a_step: 11, steps, annullato: false, exit_code: 0,
});
assert.equal(
  muto.esito, "da Lettura a Esportazione: esecuzione conclusa",
  "senza durata l'esito ne fabbrica una",
);
""")


def test_il_deck_si_annuncia_solo_quando_e_questa_corsa_a_scriverlo(tmp_path):
    """Lo step 11 e' il perimetro dichiarato del prodotto -- dalla nuvola di
    punti al deck `.inp`, e li' si ferma -- e finiva con la stessa riga di uno
    step qualunque.

    Le due strade per cui l'annuncio diventa una bugia, e nessuna delle due si
    vede leggendo la riga:

    1. **Il deck di ieri.** Un `11_export` valido resta sul disco fra una corsa
       e l'altra. Una corsa da 1 a 6 che finisse dicendo «il deck e' pronto»
       daterebbe col proprio momento un fatto vecchio di giorni.
    2. **Il deck che non c'e'.** Arrivare allo step 11 non basta: la voce porta
       `artefatto` a null finche' il file non e' stato scritto, e indicare un
       bottone di scarico che restituisce un 404 e' peggio del silenzio.

    Nessun numero nella riga, e non e' una svista. A questo istante
    `corpoMetriche` e' ancora quello della corsa precedente -- `apriDettaglio`
    rilegge le metriche dopo, ed e' un ordine voluto -- quindi un conteggio di
    elementi preso da li' descriverebbe la corsa di prima con la data di questa.
    """
    _esegui(tmp_path, _banco_di_esito() + """
ETICHETTE["01_load"] = "Lettura";
ETICHETTE["06_repair"] = "Riparazione";
ETICHETTE["11_export"] = "Esportazione";
const conDeck = [
  { numero: 1, chiave: "01_load", stato: "valido", secondi: 0.03 },
  { numero: 11, chiave: "11_export", stato: "valido", secondi: 4, artefatto: "deck.inp" },
];
ultimoStato = conDeck;

const arrivata = esitoDellaCorsa({
  in_corso: false, step: 1, a_step: 11, steps: conDeck,
  annullato: false, exit_code: 0, durata_secondi: 401,
});
assert.ok(arrivata.esito.includes("il deck è pronto"),
  "la corsa arriva al deck e non lo dice: " + arrivata.esito);
assert.ok(arrivata.esito.includes("6 min 41 s"),
  "la coda del deck ha mangiato la durata: " + arrivata.esito);

// La stessa cartella, ma la corsa si ferma alla riparazione: il deck sul disco
// e' quello di prima.
const fermata = esitoDellaCorsa({
  in_corso: false, step: 1, a_step: 6, steps: conDeck,
  annullato: false, exit_code: 0, durata_secondi: 120,
});
assert.ok(!fermata.esito.includes("deck"),
  "un deck di una corsa precedente si annuncia come appena scritto: " + fermata.esito);

// Arrivata all'11 ma senza artefatto: niente da scaricare.
const senzaFile = esitoDellaCorsa({
  in_corso: false, step: 1, a_step: 11, annullato: false, exit_code: 0, durata_secondi: 401,
  steps: [{ numero: 11, chiave: "11_export", stato: "valido", secondi: 4, artefatto: null }],
});
assert.ok(!senzaFile.esito.includes("deck"),
  "si annuncia un deck che non e' stato scritto: " + senzaFile.esito);

// Fallita sull'11: il ramo dell'errore esce prima, e un fallimento che
// annunciasse un deck pronto sarebbe il falso successo peggiore di tutti.
const fallita = esitoDellaCorsa({
  in_corso: false, step: 1, a_step: 11, steps: conDeck,
  annullato: false, exit_code: 1, durata_secondi: 401,
});
assert.equal(fallita.esito, null, "una corsa fallita passa dal ramo dell'esito");
assert.ok(!fallita.errore.includes("deck"),
  "un fallimento annuncia il deck pronto: " + fallita.errore);

// Lo step 11 da solo: e' questa corsa a scriverlo, e `a_step` manca.
const soloUndici = esitoDellaCorsa({
  in_corso: false, step: 11, steps: conDeck, annullato: false, exit_code: 0,
});
assert.ok(soloUndici.esito.includes("il deck è pronto"),
  "lo step 11 eseguito da solo non annuncia il deck: " + soloUndici.esito);
""")


def test_il_fronte_di_discesa_annuncia_l_esito_e_ricarica(tmp_path):
    """Il cablaggio, eseguito: chi riceve il testo, e in che ordine.

    L'esito va scritto PRIMA che `apriDettaglio` riapra il pannello, e in una
    regione che il pannello non tocca. #errore vive nella colonna del
    dettaglio e apriDettaglio la svuota a ogni apertura: annunciato la', il
    fallimento sparirebbe due righe piu' sotto nella stessa passata, e a video
    resterebbe qualcosa di indistinguibile da una corsa riuscita.

    E sul fronte di SALITA l'esito di prima se ne va: lasciato li',
    «esecuzione fallita» resterebbe sopra la corsa nuova partita proprio per
    correggere quel fallimento -- il piu' vecchio dei due testi a descrivere il
    piu' recente dei due fatti.

    Mutazione che lo uccide: togliere `mostraEsito(null, null)` dal fronte di
    salita.
    """
    _esegui(tmp_path, _banco_di_esito() + """
ETICHETTE["01_load"] = "Lettura";
const steps = [{ numero: 1, chiave: "01_load", stato: "fallito" }];
stepAperto = 1;
stepScelto = 1;

// Parte.
aggiornaDaStato({ in_corso: true, step: 1, a_step: 1, steps, da_secondi: 0.5, annullato: false, exit_code: null });
assert.equal(esito.textContent, "", "una corsa che parte non ha ancora un esito");

// Finisce male.
aggiornaDaStato({ in_corso: false, step: 1, a_step: 1, steps, da_secondi: null, annullato: false, exit_code: 2 });
assert.match(esito.textContent, /esecuzione fallita \\(codice 2\\)/);
assert.ok(esito.className.includes("esito-fallito"), "il fallimento non ha il proprio peso");
assert.deepEqual(riaperte, [1], "il pannello non e' stato riaperto");
assert.deepEqual(ricaricate, [1], "la vista e' rimasta indietro");
// Il registro si apre da solo: c'e' un motivo da leggere.
const dettagli = document.getElementById("registro-dettagli");
assert.equal(dettagli.open, true, "un fallimento non ha aperto il registro");

// Riparte: l'esito di prima se ne va, e con lui la sua classe.
aggiornaDaStato({ in_corso: true, step: 1, a_step: 1, steps, da_secondi: 0.1, annullato: false, exit_code: null });
assert.equal(esito.textContent, "", "l'esito vecchio e' rimasto sopra la corsa nuova");
assert.ok(!esito.className.includes("esito-fallito"), "la classe del fallimento e' sopravvissuta");

// Una corsa riuscita non tocca il registro: ne' lo apre da chiuso, ne' lo
// richiude se l'utente l'aveva gia' aperto.
dettagli.open = false;
aggiornaDaStato({ in_corso: false, step: 1, a_step: 1, steps, da_secondi: null, annullato: false, exit_code: 0 });
assert.equal(dettagli.open, false, "una corsa riuscita ha aperto il registro da sola");

// Il fronte di salita chiude sempre il registro (corsa nuova, righe vecchie):
// l'apertura a mano va dopo, mentre la corsa gia' gira, per provare che sia
// il SUCCESSO a non richiuderla e non il fronte di salita a non averlo fatto.
aggiornaDaStato({ in_corso: true, step: 1, a_step: 1, steps, da_secondi: 0.1, annullato: false, exit_code: null });
dettagli.open = true;
aggiornaDaStato({ in_corso: false, step: 1, a_step: 1, steps, da_secondi: null, annullato: false, exit_code: 0 });
assert.equal(dettagli.open, true, "una corsa riuscita ha richiuso il registro che l'utente aveva aperto");
""")


def test_il_pannello_dice_quale_step_si_sta_guardando(tmp_path):
    """Il pannello si apriva su «Esegui questo step» senza dire quale.

    Il solo canale che lo nominava era il marchio nella colonna a sinistra, a
    1100 px di distanza su uno schermo largo: per sapere che cosa si stava per
    eseguire bisognava riattraversare lo schermo. Adesso il titolo sta in testa,
    prima dei due bottoni, che e' l'ordine in cui la domanda si pone.

    Il numero E il nome, non uno dei due: il numero e' come lo step si chiama
    negli artefatti sul disco e nei messaggi del server, il nome e' come si
    chiama nella colonna. Chi legge il pannello ha bisogno di tutti e due per
    collegare le due lingue.

    Uno step di cui non si conosce la chiave non prende un nome inventato --
    resta il numero, che e' l'unica cosa che si sa -- e uno senza proposito non
    prende una frase: e' la stessa regola di nomeDelloStep.

    Mutazione che lo uccide: far cadere `intestazioneDelloStep` sul solo nome
    (`textContent = nome`), che perde il numero.
    """
    _esegui(tmp_path, _DOM + _funzioni("intestazioneDelloStep") + """
ETICHETTE["09_tetrahedralize"] = "Tetraedri";
PROPOSITI["09_tetrahedralize"] = "Riempie il volume di tetraedri.";
ultimoStato = [
  { numero: 9, chiave: "09_tetrahedralize" },
  { numero: 12, chiave: "12_ignota" },
];

const [titolo, proposito] = intestazioneDelloStep(9);
assert.equal(titolo.tag, "h3");
assert.equal(titolo.textContent, "Step 9 · Tetraedri");
assert.equal(proposito.textContent, "Riempie il volume di tetraedri.");
assert.equal(proposito.className, "aiuto");

// Chiave che nessuna tabella nomina: niente nome inventato, niente frase.
const soloTitolo = intestazioneDelloStep(12);
assert.equal(soloTitolo.length, 1, "una chiave sconosciuta ha preso una frase inventata");
assert.equal(soloTitolo[0].textContent, "Step 12");

// Step che lo stato non conosce affatto.
assert.deepEqual(intestazioneDelloStep(99).map((n) => n.textContent), ["Step 99"]);
""")


def test_i_parametri_al_predefinito_si_richiudono_e_gli_altri_no(tmp_path):
    """`segment` rende undici campi e `surface` nove: molto oltre i quattro che
    si tengono in mente insieme, e senza nessun ordine dentro.

    Il taglio fra cio' che resta aperto e cio' che si richiude non lo decide il
    gusto: e' cio' che QUESTA corsa ha spostato dal predefinito. Un elenco
    base/avanzato scritto nel modulo sarebbe una classificazione che nessun dato
    sostiene, e i nomi dei parametri non ne portano una.

    Un obbligatorio resta in vista anche se il suo valore coincide col
    predefinito nullo: nella piega finirebbe sotto un titolo che dice «al valore
    predefinito», e un predefinito non ce l'ha. E' anche il campo che di solito
    conta di piu' -- `input.path` e' la nuvola su cui gira tutto il resto.

    Il predefinito da solo non basta a riconoscerlo: un campo obbligatorio
    arriva `default: null`, ma anche un nullabile il cui predefinito e' None.
    Per questo lo schema manda `obbligatorio`.

    Mutazione che lo uccide: togliere `campo.obbligatorio ||` dalla condizione,
    cosi' il campo che chiede una risposta finisce nella piega.
    """
    _esegui(tmp_path, _DOM + _funzioni(
        "nuovaRiga", "segnalaCampo", "valoreScritto", "apriBattuta", "scriviParametro",
        "testoDellAiuto", "campoParametro", "reso", "cambiatoDalPredefinito", "gruppoDelBlocco",
    ) + """
let ultimaBattutaDelCampo = new Map();
// `configurazione` la dichiara gia' _DOM: e' la variabile di modulo che il
// banco deve CONDIVIDERE, non una copia sua.
configurazione = {
  segment: { method: "crop", outlier_neighbors: 40, crop_min: null, path: null },
};
const campi = {
  method: { description: "", default: "crop", obbligatorio: false },
  outlier_neighbors: { description: "", default: 20, obbligatorio: false },
  crop_min: { description: "", default: null, obbligatorio: false },
  path: { description: "", default: null, obbligatorio: true },
};

const gruppo = gruppoDelBlocco("segment", campi, generazione);
// Il titolo del gruppo e' l'etichetta del blocco, non la chiave.
assert.equal(gruppo.figli.find((n) => n.tag === "legend").textContent, "segmentazione",
  "la legend stampa la chiave grezza del blocco");
const pieghe = gruppo.figli.filter((n) => n.tag === "details");
assert.equal(pieghe.length, 1, "la piega non e' stata costruita");
const [piega] = pieghe;

// In vista: quello spostato (outlier_neighbors) e l'obbligatorio (path).
const inVista = gruppo.figli.filter((n) => n.className === "campo").length;
assert.equal(inVista, 2, "in vista non ci sono i due che contano: " + inVista);
// Richiusi: quelli fermi al predefinito, method e crop_min.
const richiusi = piega.figli.filter((n) => n.className === "campo").length;
assert.equal(richiusi, 2, "nella piega non ci sono i due fermi: " + richiusi);
assert.equal(piega.figli[0].textContent, "2 parametri al valore predefinito");
assert.ok(!piega.open, "la piega e' nata aperta con dei campi in vista sopra");
""")


def test_la_legenda_del_blocco_export_e_l_etichetta_e_non_la_chiave(tmp_path):
    """Lo step 11 dichiara `export` e non piu' `analysis`.

    Il deck e' nudo — materiale, vincoli e carichi si assegnano in Abaqus —
    quindi `export` e' rimasto il solo blocco proprio dello step, e senza la
    sua voce nella tabella il gruppo titolerebbe «export», cioe' la chiave del
    file di configurazione: «una chiave non si stampa mai, si stampa la sua
    etichetta» (PRODUCT.md).

    Mutazione che lo uccide: togliere `export: "esportazione"` da
    ETICHETTE_DEI_BLOCCHI.
    """
    _esegui(tmp_path, _DOM + _funzioni(
        "nuovaRiga", "segnalaCampo", "valoreScritto", "apriBattuta", "scriviParametro",
        "testoDellAiuto", "campoParametro", "reso", "cambiatoDalPredefinito", "gruppoDelBlocco",
    ) + """
let ultimaBattutaDelCampo = new Map();
configurazione = { export: { set_tolerance_factor: 1.5 } };
const gruppo = gruppoDelBlocco("export", {
  set_tolerance_factor: { description: "", default: 1.5, obbligatorio: false },
}, generazione);
assert.equal(gruppo.figli.find((n) => n.tag === "legend").textContent, "esportazione",
  "il gruppo dello step 11 stampa la chiave grezza del blocco");
""")


def test_con_tutto_al_predefinito_la_piega_nasce_aperta(tmp_path):
    """Alla prima corsa nessun parametro e' stato spostato.

    Un pannello che mostra solo una riga da cliccare non insegna niente a chi
    apre lo step per la prima volta: e' il caso in cui la piega serve meno, ed
    e' esattamente quello in cui la si troverebbe chiusa se la regola guardasse
    solo il numero dei fermi.

    Mutazione che lo uccide: togliere `if (cambiati.length === 0) piega.open = true`.
    """
    _esegui(tmp_path, _DOM + _funzioni(
        "nuovaRiga", "segnalaCampo", "valoreScritto", "apriBattuta", "scriviParametro",
        "testoDellAiuto", "campoParametro", "reso", "cambiatoDalPredefinito", "gruppoDelBlocco",
    ) + """
let ultimaBattutaDelCampo = new Map();
configurazione = { tet: { min_ratio: 1.8, nobisect: false } };
const campi = {
  min_ratio: { description: "", default: 1.8, obbligatorio: false },
  nobisect: { description: "", default: false, obbligatorio: false },
};

const gruppo = gruppoDelBlocco("tet", campi, generazione);
const [piega] = gruppo.figli.filter((n) => n.tag === "details");
assert.ok(piega.open, "tutto al predefinito e il pannello e' solo una riga da cliccare");
assert.equal(gruppo.figli.filter((n) => n.className === "campo").length, 0);
""")


def test_una_tupla_e_una_lista_con_gli_stessi_numeri_non_sono_un_cambiamento(tmp_path):
    """Il predefinito e il valore corrente arrivano da due strade diverse.

    Lo schema li rende con `default=str` per i tipi che JSON non porta (un
    `Path`, una tupla), la configurazione della corsa arriva dal suo yaml: la
    stessa cosa puo' presentarsi in due forme. Un `!==` diretto le direbbe
    diverse e terrebbe in vista un campo che nessuno ha toccato -- cioe' la
    piega si svuoterebbe da sola e smetterebbe di servire.

    Mutazione che lo uccide: confrontare `valore !== predefinito` invece di
    passare da `reso`.
    """
    _esegui(tmp_path, _DOM + _funzioni("reso", "cambiatoDalPredefinito") + """
// La stessa terna, in due forme che JSON.stringify riporta alla stessa.
assert.equal(cambiatoDalPredefinito([1, 2, 3], [1, 2, 3]), false);
// null e undefined sono la stessa assenza: un campo mai scritto contro un
// predefinito nullo non e' uno spostamento.
assert.equal(cambiatoDalPredefinito(undefined, null), false);
assert.equal(cambiatoDalPredefinito(null, null), false);
// Il numero e la stringa che lo rende: lo schema manda i Path come stringhe.
assert.equal(cambiatoDalPredefinito("2", 2), false);
// E i cambiamenti veri restano cambiamenti.
assert.equal(cambiatoDalPredefinito(40, 20), true);
assert.equal(cambiatoDalPredefinito([1, 2, 3], [1, 2, 4]), true);
assert.equal(cambiatoDalPredefinito("nuvola.ply", null), true);
""")


def test_i_due_esegui_seguono_la_corsa_come_annulla(tmp_path):
    """Un bottone che risponde «no» non si distingue da uno che non ha fatto
    niente.

    I due «Esegui» restavano vivi durante una corsa e si affidavano al 400 del
    worker: un rifiuto che si poteva evitare, ed e' lo stesso difetto per cui
    «Annulla» era gia' stato legato allo stato. Dallo stesso carico e nel verso
    opposto -- «Annulla» vive mentre la corsa gira, loro mentre e' ferma.

    E un pannello aperto IN MEZZO a una corsa nasce coi bottoni spenti: il
    fronte di salita che li spegne e' gia' passato, e quell'apertura non lo
    saprebbe.

    Mutazione che lo uccide: togliere `bottone.disabled = corsaInCorso` dalla
    costruzione dei due bottoni.
    """
    _esegui(tmp_path, _banco_di_esito() + """
const finti = ["a", "b"].map(() => {
  const b = document.createElement("button");
  b.className = "bottone esecuzione";
  return b;
});
document.getElementById("dettaglio").append(...finti);
const steps = [{ numero: 1, chiave: "01_load", stato: "valido" }];

aggiornaDaStato({ in_corso: true, step: 1, a_step: 1, steps, da_secondi: 1, annullato: false, exit_code: null });
assert.ok(finti.every((b) => b.disabled), "i due «Esegui» sono vivi mentre la corsa gira");
assert.ok(corsaInCorso, "un pannello aperto adesso nascerebbe coi bottoni vivi");

aggiornaDaStato({ in_corso: false, step: 1, a_step: 1, steps, da_secondi: null, annullato: false, exit_code: 0 });
assert.ok(finti.every((b) => !b.disabled), "i due «Esegui» sono rimasti spenti a corsa ferma");
assert.ok(!corsaInCorso);
""")


def test_un_pannello_aperto_in_mezzo_a_una_corsa_nasce_coi_bottoni_spenti(tmp_path):
    """`spegniLeEsecuzioni` spegne cio' che TROVA, e questo pannello non c'era.

    Il fronte di salita passa una volta sola, all'avvio della corsa. Un pannello
    aperto dopo -- si clicca un altro step mentre gira -- costruisce due bottoni
    nuovi, che quella passata non ha mai visto: nascevano vivi, e un clic
    sarebbe finito sul 400 del worker. Un bottone che risponde «no» non si
    distingue da uno che non ha fatto niente, ed e' esattamente il difetto per
    cui «Annulla» era gia' stato legato allo stato.

    Si chiede allo stesso stato che lo scorrere degli eventi tiene, invece di
    dedurlo: `corsaInCorso` e' l'unica cosa che sa se una corsa gira, e questo
    e' l'unico punto in cui un bottone nasce.

    Mutazione che lo uccide: togliere `bottone.disabled = corsaInCorso` dalla
    costruzione dei due bottoni.
    """
    _esegui(tmp_path, _banco_di_apriDettaglio() + """
risponde = {
  "/api/schema": async () => ({ ok: true, status: 200, json: async () => SCHEMA_BUONO }),
  "/api/config": async () => ({ ok: true, status: 200, json: async () => CONFIG_BUONA }),
  "/api/metrics": async () => ({ ok: true, status: 200, json: async () => METRICHE_BUONE }),
};

// A corsa ferma nascono vivi: e' la controprova, senza la quale il controllo
// passerebbe anche con due bottoni spenti per sempre.
corsaInCorso = false;
await apriDettaglio(1);
const aFermo = document.getElementById("dettaglio").discendenti()
  .filter((n) => n.className.includes("esecuzione"));
assert.equal(aFermo.length, 2, "i due «Esegui» non si trovano piu' per classe");
assert.ok(aFermo.every((b) => !b.disabled), "a corsa ferma i due «Esegui» nascono spenti");

// Aperto mentre una corsa gia' gira: il fronte di salita e' passato prima che
// questi due bottoni esistessero.
corsaInCorso = true;
await apriDettaglio(1);
const inCorsa = document.getElementById("dettaglio").discendenti()
  .filter((n) => n.className.includes("esecuzione"));
assert.equal(inCorsa.length, 2);
assert.ok(
  inCorsa.every((b) => b.disabled),
  "un pannello aperto in mezzo a una corsa nasce coi bottoni vivi: il clic finira' sul 400",
);
""")


def test_il_gesto_non_ruba_l_undo_a_chi_sta_scrivendo(tmp_path):
    """Ctrl+Z dentro un campo e' gia' preso, e da chi ha piu' diritto.

    L'ascoltatore sta sul documento e vedrebbe comunque il tasto; scavalcarlo
    toglierebbe l'undo del TESTO per darne uno che ripristina un'altra cosa --
    e sui campi dei parametri quella «altra cosa» e' proprio la modifica che si
    sta scrivendo a mano.

    Per TIPO e non per tag: la casella del fantasma e il cursore del taglio sono
    <input> anche loro, ma un undo nativo non ce l'hanno, e lasciare li' il
    gesto lo renderebbe un tasto morto proprio sui due comandi che si toccano di
    continuo.

    E la ripetizione automatica non passa: il tasto tenuto premuto batte una
    trentina di eventi al secondo, e ognuno qui e' un POST che riscrive
    config.yaml davvero -- un secondo riavvolgerebbe lo storico fino all'avvio.
    La guardia dell'ordine non limita quel danno, lo NASCONDE.

    Mutazione che lo uccide: togliere il ramo su `CAMPI_SCRITTI`.
    """
    _esegui(tmp_path, _DOM + _costante("CAMPI_SCRITTI") + _funzioni("gestoDelloStorico") + """
const tasto = (extra = {}) => ({ ctrlKey: true, key: "z", repeat: false, target: null, ...extra });

assert.equal(gestoDelloStorico(tasto()), "indietro");
assert.equal(gestoDelloStorico(tasto({ shiftKey: true })), "avanti");
// Su macOS il gesto e' cmd+z.
assert.equal(gestoDelloStorico(tasto({ ctrlKey: false, metaKey: true })), "indietro");
// Col maiusc il browser riporta "Z": legato alla sola minuscola, il rifare non
// risponderebbe mai.
assert.equal(gestoDelloStorico(tasto({ key: "Z", shiftKey: true })), "avanti");

// Niente modificatore, altro tasto, ripetizione automatica.
assert.equal(gestoDelloStorico(tasto({ ctrlKey: false })), null);
assert.equal(gestoDelloStorico(tasto({ key: "y" })), null);
assert.equal(gestoDelloStorico(tasto({ repeat: true })), null, "il tasto tenuto premuto riavvolge tutto");

// Dentro cio' che ha un undo suo: si lascia stare.
for (const tipo of ["text", "number", "search", "password"]) {
  assert.equal(
    gestoDelloStorico(tasto({ target: { tagName: "INPUT", type: tipo } })), null,
    `il gesto ha rubato l'undo a un <input type="${tipo}">`,
  );
}
// Un <input> senza type e' un campo di testo, che e' cio' che il DOM stesso dice.
assert.equal(gestoDelloStorico(tasto({ target: { tagName: "INPUT" } })), null);
assert.equal(gestoDelloStorico(tasto({ target: { tagName: "TEXTAREA" } })), null);
assert.equal(gestoDelloStorico(tasto({ target: { isContentEditable: true } })), null);

// Ma sui comandi che un undo non ce l'hanno il gesto resta vivo: sono <input>
// anche loro, e per tag sarebbero due tasti morti.
assert.equal(gestoDelloStorico(tasto({ target: { tagName: "INPUT", type: "checkbox" } })), "indietro");
assert.equal(gestoDelloStorico(tasto({ target: { tagName: "INPUT", type: "range" } })), "indietro");
""")


def test_il_ritorno_dice_quali_step_cambiano_stato_e_li_nomina(tmp_path):
    """Un ritorno che cambia in silenzio lo stato di sette step e' una modifica
    invisibile.

    Il server manda lo stato INTERO e non un elenco di cambiamenti, e il calcolo
    sta nel browser perche' li' ci sono tutti e due i termini. Un campo
    `invalidati` col solo elenco degli step passati a «non valido» era stato
    provato e tolto: nel flusso che si usa -- cambio un parametro, poi Ctrl+Z --
    quegli step erano gia' non validi per via della modifica, e l'undo li fa
    tornare VALIDI. Sarebbe arrivato vuoto, e la frase avrebbe detto «nessuno
    step cambia stato» mentre a sinistra le righe passano da rosso a verde: il
    caso dominante, e falso.

    I nomi e non i numeri: la colonna mostra i nomi, e «step 2» sono le due
    lingue per la stessa cosa che nomeDelloStep esiste per togliere.

    Mutazione che lo uccide: guardare i soli step passati a «non valido»,
    togliendo il ramo dei tornati validi.
    """
    _esegui(tmp_path, _DOM + _funzioni("fraseDelRitorno") + """
ETICHETTE["02_segment"] = "Segmentazione";
ETICHETTE["03_downsample"] = "Riduzione";
ETICHETTE["09_tetrahedralize"] = "Tetraedri";

// Il caso dominante: si annulla una modifica, e gli step tornano validi.
const prima = [
  { numero: 2, chiave: "02_segment", stato: "non valido" },
  { numero: 3, chiave: "03_downsample", stato: "non valido" },
  { numero: 9, chiave: "09_tetrahedralize", stato: "valido" },
];
const dopo = [
  { numero: 2, chiave: "02_segment", stato: "valido" },
  { numero: 3, chiave: "03_downsample", stato: "valido" },
  { numero: 9, chiave: "09_tetrahedralize", stato: "valido" },
];
assert.equal(
  fraseDelRitorno(prima, dopo),
  "configurazione ripristinata: Segmentazione, Riduzione tornano «validi»",
);

// Il verso opposto, e al singolare.
assert.equal(
  fraseDelRitorno(dopo, [
    { numero: 2, chiave: "02_segment", stato: "valido" },
    { numero: 3, chiave: "03_downsample", stato: "valido" },
    { numero: 9, chiave: "09_tetrahedralize", stato: "non valido" },
  ]),
  "configurazione ripristinata: Tetraedri passa a «non valido»",
);

// Nessun cambiamento si dice, non si tace.
assert.equal(fraseDelRitorno(dopo, dopo), "configurazione ripristinata: nessuno step cambia stato");

// Una chiave che nessuna tabella nomina ripiega sul numero, non su un nome
// inventato.
assert.match(
  fraseDelRitorno(
    [{ numero: 7, chiave: "07_ignoto", stato: "non valido" }],
    [{ numero: 7, chiave: "07_ignoto", stato: "valido" }],
  ),
  /step 7 torna/,
);
""")


def test_un_comando_fuori_pipeline_non_si_annuncia_come_step_null(tmp_path):
    """«Ricalcola il prior» e «Ricostruisci il modello» non hanno un numero.

    `worker.start_comando` lascia `step` e `a_step` a null, e il carico SSE non
    porta un'etichetta. `nomeDelloStep(null)` ripiega sulla forma «step
    <numero>», quindi la testata annunciava alla lettera, misurato:

        step null: esecuzione conclusa
        step null: esecuzione fallita (codice 1). ...
        step null: esecuzione interrotta

    La riga che pulsa il caso lo trattava gia' -- dice «un comando è in corso»
    -- ed e' l'esito che non lo trattava. Due superfici che descrivono la stessa
    cosa e una sola delle due sa che il caso esiste.

    Mutazione che lo uccide: togliere il ramo `stato.step === null` da
    `descrizioneDellaCorsa`.
    """
    _esegui(tmp_path, _banco_di_esito() + """
ultimoStato = [];
const base = { in_corso: false, step: null, a_step: null, steps: [], annullato: false };

assert.deepEqual(
  esitoDellaCorsa({ ...base, exit_code: 0 }),
  { errore: null, esito: "il comando: esecuzione conclusa" },
);
assert.deepEqual(
  esitoDellaCorsa({ ...base, exit_code: -15, annullato: true }),
  { errore: null, esito: "il comando: esecuzione interrotta" },
);
const fallito = esitoDellaCorsa({ ...base, exit_code: 1 });
assert.ok(
  !fallito.errore.includes("null"),
  "l'esito nomina uno step che non esiste: " + fallito.errore,
);
""")


def test_l_esito_si_annuncia_anche_se_il_codice_arriva_dopo_la_fine(tmp_path):
    """La finestra fra «non gira piu'» e «ecco com'e' finita».

    `is_running()` e' `poll() is None`, mentre `exit_code` lo fissa `_leggi`
    DOPO aver svuotato stdout: esiste un frame -- il drain della pipe -- in cui
    la corsa e' gia' dichiarata ferma e il codice non c'e' ancora.

    Consumando il fronte li', al frame dopo `eraInCorso` era gia' falso e per
    quella corsa l'esito non si annunciava MAI: ne' conclusa, ne' fallita, ne'
    annullata. `esitoDellaCorsa` taceva correttamente, e proprio per questo il
    fronte veniva bruciato in silenzio -- il rigetto muto che tutta questa
    superficie esiste per togliere.

    Mutazione che lo uccide: rimettere `eraInCorso = stato.in_corso;`
    incondizionato in fondo ad `aggiornaDaStato`.
    """
    _esegui(tmp_path, _banco_di_esito() + """
ETICHETTE["01_load"] = "Lettura";
const steps = [{ numero: 1, chiave: "01_load", stato: "valido", secondi: 12 }];
const base = { step: 1, a_step: 1, steps, annullato: false };

// La corsa gira.
aggiornaDaStato({ ...base, in_corso: true, exit_code: null });
assert.equal(esito.textContent, "", "a corsa in moto non c'e' un esito da dire");

// Il frame di mezzo: ferma, ma il codice non e' ancora stato letto.
aggiornaDaStato({ ...base, in_corso: false, exit_code: null });
assert.equal(esito.textContent, "", "ha inventato un esito senza codice");

// Il frame dopo porta il codice: e' adesso che l'esito si annuncia.
aggiornaDaStato({ ...base, in_corso: false, exit_code: 0 });
assert.equal(esito.textContent, "Lettura: esecuzione conclusa in 12 s");

// E una volta sola: il fronte si e' consumato qui, non prima.
esito.textContent = "";
aggiornaDaStato({ ...base, in_corso: false, exit_code: 0 });
assert.equal(esito.textContent, "", "il fronte si e' ripetuto a ogni frame");
""")


# --------------------------------------------------------------------------
# Le due schermate: la colonna a dodici, il passaggio, e i quattro stadi vuoti.
#
# Lo step 13 resta lo step 13 e resta nello stato che il server manda -- e'
# `passoDaMostrare` a leggerlo, e STEP_CON_GEOMETRIA lo elenca. Cio' che cambia
# e' dove si comanda: non piu' una riga in fondo alla colonna della pipeline,
# ma una schermata sua. La colonna, quindi, si ferma al dodici.
# --------------------------------------------------------------------------

# Le dodici chiavi come il server le manda, scritte per esteso: il confine fra
# la colonna e il prior e' una CHIAVE, non un numero, e un banco che fabbricasse
# le chiavi da un contatore non proverebbe piu' quel confine.
_DODICI = """
const CHIAVI = ["01_load", "02_segment", "03_downsample", "04_normals",
  "05_reconstruct", "06_repair", "07_surface_quality", "08_simplify",
  "09_tetrahedralize", "10_volume_quality", "11_export", "12_wall"];
const dodici = (stato = "valido") =>
  CHIAVI.map((chiave, i) => ({ numero: i + 1, chiave, stato }));
"""


def test_la_colonna_si_ferma_all_undici_e_non_perde_lo_stato_degli_altri_due(tmp_path):
    """Due meta' che si contraddirebbero se una sola fosse fatta.

    La colonna arriva a 11, il deck: e' li' che si chiude il perimetro del
    prodotto. Il prior geometrico resta eseguibile -- `meshrec wall`, e
    l'artefatto sul disco -- ma non ha interfaccia, quindi sta fuori dalla
    colonna. Il fondo si e' alzato due volte: 13 fino a #140, poi 12, e ora 11.

    Ma `ultimoStato` deve continuare a portarli tutti: `passoDaMostrare` cammina
    a monte da `corpo.steps.length`, e STEP_CON_GEOMETRIA elenca anche gli step
    che la colonna non mostra. Filtrando lo stato invece della sola vista, la
    geometria del prior diventerebbe irraggiungibile per una strada che nessuno
    guarda -- ed e' la meta' che vale di piu', perche' e' quella che distingue
    «fuori dalla colonna» da «fuori dal programma».
    """
    _esegui(tmp_path, _DOM + _funzioni(
        *_COLONNA,
    ) + _DODICI + """
disegnaStep(dodici());
assert.equal(elenco.childElementCount, 11,
  "la colonna della pipeline non si ferma all'undici");
assert.deepEqual(
  elenco.children.map((riga) => riga.firstElementChild.dataset.numero),
  [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11],
  "la colonna non porta piu' gli undici step del perimetro, o li rinumera");
assert.equal(ultimoStato.length, 12,
  "il 12 e' sparito anche dallo stato: fuori dalla colonna e non fuori dal"
  + " programma e' esattamente cio' che distingue questa scelta, e"
  + " passoDaMostrare non lo troverebbe piu'");
""")








def test_il_collegamento_perso_col_server_si_dichiara(tmp_path):
    """Una schermata che non si aggiorna piu' non deve fingere di essere fresca.

    Tutto cio' che le due schermate mostrano viene dal flusso degli eventi. Caduto
    il server, l'ultimo stato ricevuto resta stampato e nessuno dice che e'
    vecchio: la colonna continua a dichiarare «valido» e lo stadio del modello
    continua a dichiarare uno stato che nessuno sta piu' confermando.

    Le due funzioni sono di primo livello e non frecce dentro
    `addEventListener`, per la stessa ragione di `aggiornaDaStato`: dentro la
    freccia non le esegue nessun banco.
    """
    _esegui(tmp_path, _DOM + _funzioni(
        "perdiIlCollegamento", "riprendiIlCollegamento",
    ) + """
const riga = document.getElementById("collegamento-perso");
riga.hidden = true;
perdiIlCollegamento();
assert.equal(riga.hidden, false, "il server caduto non si dichiara");
riprendiIlCollegamento();
assert.equal(riga.hidden, true, "riconnesso, l'avviso resta acceso e diventa un cartello inerte");
""")
    modulo = _senza_commenti_js(_modulo())
    for evento, gestore in (("error", "perdiIlCollegamento"), ("open", "riprendiIlCollegamento")):
        assert f'flusso.addEventListener("{evento}", {gestore})' in modulo, (
            f"nessuno lega {gestore} all'evento «{evento}» del flusso: la funzione non gira mai"
        )


























































def test_il_proposito_dello_step_2_nomina_le_tre_cose_che_lo_step_fa():
    """La riga descriveva solo la meta' di pre-processing.

    `docs/validazione/ricerca-terminologia-segmentazione.md` (28/08/2026) da'
    ragione in parte al tutore: togliere gli outlier e ritagliare non sono
    segmentazione in nessuna tassonomia, mentre l'estrazione di piani (RANSAC)
    e il raggruppamento (DBSCAN) lo sono senza ambiguita'. La frase vecchia
    -- «toglie il rumore e ritaglia via il resto della stanza» -- taceva
    proprio le due meta' che il nome dello step giustificano, e chi legge il
    pannello non sapeva che lo step estrae piani e raggruppa.

    Mutazione che lo uccide: rimettere la frase vecchia.
    """
    modulo = _senza_commenti_js(_modulo())
    # Dentro PROPOSITI e non nel modulo intero: ETICHETTE e PROPOSITI portano
    # le stesse chiavi, e ETICHETTE viene prima.
    blocco = re.search(r"const PROPOSITI = \{(.*?)\n\};", modulo, flags=re.DOTALL)
    assert blocco is not None, "PROPOSITI non e' piu' un oggetto letterale"
    trovata = re.search(r'"02_segment":\s*"([^"]+)"', blocco.group(1))
    assert trovata is not None, "PROPOSITI non ha piu' una voce per 02_segment"
    frase = trovata.group(1).lower()
    for parola in ("rumore", "ritagl", "pian", "grupp"):
        assert parola in frase, f"il proposito dello step 2 non nomina «{parola}»: {frase}"


def test_nessun_proposito_nomina_una_chiave_del_modello():
    """«Una chiave non si stampa mai, si stampa la sua etichetta» vale anche
    per la prosa: il proposito dello step 8 citava «enabled», che dallo step 8
    in poi non e' piu' il nome che il pannello mostra.
    """
    modulo = _senza_commenti_js(_modulo())
    blocco = re.search(r"const PROPOSITI = \{(.*?)\n\};", modulo, flags=re.DOTALL)
    assert blocco is not None
    for chiave in ("enabled", "largest_component_only", "poisson_depth", "nobisect"):
        assert chiave not in blocco.group(1), (
            f"il proposito di uno step nomina la chiave «{chiave}» invece della sua etichetta"
        )


def _banco_della_scala() -> str:
    """Il banco del campo, piu' le due composizioni dello step 1.

    `scale` e `expected_size` non sono campi scalari: sono due comandi che
    scrivono un valore solo, e la logica che compone e scompone e' logica --
    si prova eseguendola, come tutto il resto di questo file.
    """
    costanti = "\n".join(
        _costante(nome) for nome in
        ("FATTORI_DI_SCALA", "UNITA_DI_SCALA", "ASSI_DELLE_DIMENSIONI")
    )
    return _DOM + costanti + "\n" + _funzioni(
        "valoreScritto", "ragioneDelRifiuto", "serverMuto", "superata",
        "corpoLetto", "segnalaCampo", "apriBattuta", "scriviValore", "scriviParametro",
        "coppiaDiScala", "unitaDellaScala", "rigaComposta", "campoScala",
        "campoDimensioniAttese",
    ) + """
// `configurazione` e `generazione` sono gia' del DOM finto: il banco le usa,
// non le ridichiara. `ultimaBattutaDelCampo` invece e' del modulo, e
// `scriviValore` la legge per nome.
generazione = 1;
let ultimaBattutaDelCampo = new Map();
const richieste = [];
let risponde = null;
globalThis.fetch = async (percorso, opzioni) => {
  richieste.push({ percorso, corpo: JSON.parse(opzioni.body) });
  return risponde(percorso, opzioni);
};
const accetta = (canonica) => async () => ({ ok: true, status: 200, json: async () => canonica });
"""


def test_la_scala_si_compone_da_due_menu_e_scrive_un_numero_solo(tmp_path):
    """Fattore 1 e unita' cm: «la nuvola e' gia' in centimetri e ci resta».

    I due menu non sono due campi del modello: `input.scale` resta il numero
    che e' -- vive nei config.yaml delle corse registrate e dentro l'impronta,
    e due campi nuovi sposterebbero l'impronta di ventidue righe di registro.
    La composizione sta nell'interfaccia, e il numero che ne esce e' uno solo.

    Mutazione che lo uccide: comporre moltiplicando per l'unita' sbagliata.
    """
    _esegui(tmp_path, _banco_della_scala() + """
configurazione = { input: { scale: 10 } };
const riga = campoScala("input", "scale", { etichetta: "fattore di scala", description: "" }, 1);
const [fattore, unita] = riga.children[1].children;
assert.equal(fattore.value, "1", `il fattore letto da scale=10 non e' 1: ${fattore.value}`);
assert.equal(unita.value, "cm", `l'unita' letta da scale=10 non e' cm: ${unita.value}`);

// La coppia scelta scrive un numero solo, e nient'altro cambia nel blocco.
risponde = accetta({ input: { scale: 1000 } });
fattore.value = "1";
unita.value = "m";
await unita.scatena("change");
assert.equal(richieste.length, 1, "la coppia non ha scritto niente");
assert.equal(richieste[0].corpo.input.scale, 1000,
  `1 in metri non fa 1000 millimetri: ${richieste[0].corpo.input.scale}`);
assert.equal(Object.keys(richieste[0].corpo.input).length, 1,
  "i due menu hanno scritto piu' di un campo");

// E riaperto il pannello i due menu tornano su quella coppia.
const riaperta = campoScala("input", "scale", { etichetta: "fattore di scala", description: "" }, 1);
const [dopoFattore, dopoUnita] = riaperta.children[1].children;
assert.equal(dopoFattore.value, "1", "il fattore non torna su quello scelto");
assert.equal(dopoUnita.value, "m", "l'unita' non torna su quella scelta");
""")


def test_una_scala_che_nessuna_coppia_produce_resta_il_numero_che_e(tmp_path):
    """Ingresso degenere: un `config.yaml` con `scale: 3`.

    Nessuna coppia fattore-unita' lo produce. Arrotondarlo alla coppia piu'
    vicina cambierebbe in silenzio la scala di una corsa gia' registrata: il
    numero resta, si vede, e la riga dice perche' i due menu non ci sono.
    """
    _esegui(tmp_path, _banco_della_scala() + """
configurazione = { input: { scale: 3 } };
const riga = campoScala("input", "scale", { etichetta: "fattore di scala", description: "" }, 1);
const caselle = riga.children.filter((f) => f.tag === "select");
assert.equal(caselle.length, 0, "i due menu compaiono su un valore che non sanno rappresentare");
const casella = riga.children.find((f) => f.tag === "input");
assert.equal(casella.value, "3", `il valore e' stato riscritto: ${casella.value}`);
const detto = riga.children.map((f) => f.textContent).join(" ");
assert.match(detto, /3/, `il numero fuori coppia non e' nominato: ${detto}`);
assert.match(detto, /coppia|fattore/, `la riga non dice perche' i menu non ci sono: ${detto}`);
""")


def test_le_dimensioni_attese_vuote_valgono_nessun_controllo_di_scala(tmp_path):
    """Le tre caselle vuote sono il predefinito di oggi (`expected_size = None`),
    non un errore: il controllo di scala non e' richiesto.
    """
    _esegui(tmp_path, _banco_della_scala() + """
configurazione = { input: { scale: 1000, expected_size: [2000, 250, 1200] } };
const riga = campoDimensioniAttese("input", "expected_size", { etichetta: "dimensioni", description: "" }, 1);
const caselle = riga.children[1].children.filter((f) => f.tag === "input");
assert.equal(caselle.length, 3, `le misure non sono tre: ${caselle.length}`);
// Scritte nell'unita' scelta in scale: 2000 mm con l'unita' m sono 2.
assert.equal(caselle[0].value, "2", `la misura non e' nell'unita' della scala: ${caselle[0].value}`);

risponde = accetta({ input: { scale: 1000, expected_size: null } });
for (const casella of caselle) casella.value = "";
await caselle[0].scatena("change");
assert.equal(richieste.length, 1, "le tre caselle vuote non hanno scritto niente");
assert.equal(richieste[0].corpo.input.expected_size, null,
  `tre caselle vuote non danno «nessun controllo»: ${JSON.stringify(richieste[0].corpo.input.expected_size)}`);
""")


def test_una_sola_dimensione_attesa_e_un_rifiuto_detto(tmp_path):
    """Ingresso degenere: una casella riempita e due vuote.

    Il modello pretende una terna o niente. Mandare al server due vuoti e un
    numero darebbe un 422 sul tipo, che non dice all'operatore che cosa
    manca: il rifiuto si dice qui, con la regola.
    """
    _esegui(tmp_path, _banco_della_scala() + """
configurazione = { input: { scale: 1, expected_size: null } };
const riga = campoDimensioniAttese("input", "expected_size", { etichetta: "dimensioni", description: "" }, 1);
const caselle = riga.children[1].children.filter((f) => f.tag === "input");
const messaggio = riga.children[riga.children.length - 1];
caselle[0].value = "2000";
await caselle[0].scatena("change");
assert.equal(richieste.length, 0, "una terna a meta' e' partita verso il server");
assert.equal(messaggio.hidden, false, "il rifiuto non si vede");
assert.match(messaggio.textContent, /tre/,
  `il rifiuto non dice che le misure vanno tutte e tre: ${messaggio.textContent}`);
""")


def test_una_dimensione_attesa_non_numerica_e_un_rifiuto_detto(tmp_path):
    """Ingresso degenere: «due metri» battuto in una casella.

    Senza guardia la stringa finisce nella terna e torna un errore di
    validazione grezzo di pydantic, cioe' cinque righe sul tipo interno.
    """
    _esegui(tmp_path, _banco_della_scala() + """
configurazione = { input: { scale: 1, expected_size: null } };
const riga = campoDimensioniAttese("input", "expected_size", { etichetta: "dimensioni", description: "" }, 1);
const caselle = riga.children[1].children.filter((f) => f.tag === "input");
const messaggio = riga.children[riga.children.length - 1];
caselle[0].value = "due metri";
caselle[1].value = "250";
caselle[2].value = "1200";
await caselle[0].scatena("change");
assert.equal(richieste.length, 0, "una misura non numerica e' partita verso il server");
assert.equal(messaggio.hidden, false, "il rifiuto non si vede");
assert.match(messaggio.textContent, /numero/,
  `il rifiuto non dice che serve un numero: ${messaggio.textContent}`);
""")


def test_uno_step_senza_parametri_e_senza_metriche_lo_dichiara(tmp_path):
    """Ingresso degenere del pannello: lo step 7 non ha parametri propri
    (`STEP_BLOCKS[7]` e' vuota), e finche' non e' stato eseguito non ha
    nemmeno metriche. Restano i due bottoni e basta, e un riquadro quasi
    vuoto non distingue «niente da mostrare» da «non ha caricato».

    Mutazione che lo uccide: togliere il ramo finale di `apriDettaglio` che
    scrive la riga quando non c'e' ne' un blocco ne' una chiave di metriche.
    """
    _esegui(tmp_path, _banco_di_apriDettaglio() + """
risponde = {
  "/api/schema": async () => ({ ok: true, status: 200, json: async () => ({
    "1": { blocchi: [], campi: {} },
  }) }),
  "/api/config": async () => ({ ok: true, status: 200, json: async () => CONFIG_BUONA }),
  "/api/metrics": async () => ({ ok: true, status: 200, json: async () => ({}) }),
};
await apriDettaglio(1);
const dettaglio = document.getElementById("dettaglio");
const detto = [...dettaglio.discendenti(), ...dettaglio.figli]
  .map((n) => n.testo).join(" ");
assert.match(detto, /non ha parametri/,
  `uno step senza parametri e senza metriche non lo dichiara: ${detto}`);
""")



# --------------------------------------------------------------------------
# Il pannello «Modello»: descrive il fronte, cioe' lo step valido di numero
# piu' alto, con i numeri che metrics.json porta gia'.
# --------------------------------------------------------------------------


def test_il_fronte_e_lo_step_valido_di_numero_piu_alto(tmp_path):
    _esegui(tmp_path, _DOM + _funzioni("fronteDelloStato") + """
const steps = [
  { numero: 1, chiave: "01_load", stato: "valido" },
  { numero: 2, chiave: "02_segment", stato: "valido" },
  { numero: 3, chiave: "03_downsample", stato: "non valido" },
  { numero: 4, chiave: "04_normals", stato: "valido" },
  { numero: 5, chiave: "05_reconstruct", stato: "fallito" },
  { numero: 12, chiave: "12_wall", stato: "valido" },
];
assert.equal(fronteDelloStato(steps, STEP_DEL_PRIOR).numero, 4, "il fronte e' il valido piu' alto, prior escluso");
assert.equal(fronteDelloStato(steps.map((v) => ({ ...v, stato: "mai eseguito" })), STEP_DEL_PRIOR), null);
assert.equal(fronteDelloStato([], STEP_DEL_PRIOR), null);
""")


def test_le_righe_del_modello_leggono_le_chiavi_vere_e_dicono_non_misurato(tmp_path):
    _esegui(tmp_path, _DOM + _funzioni("righeDelModello", "valoreDellaMetrica") + """
const metriche = {
  "05_reconstruct": { vertices: 1234, triangles: 2468, watertight: false, boundary_edges: 12, area: 1.5, volume: 0 },
  "01_load": { points_kept: 1000000, spacing: 1.1934567, extent: [2759, 785, 2000] },
  // I due versi hanno numeri diversi apposta: e' l'unico modo di vedere quale
  // dei due il pannello sta davvero leggendo.
  "07_surface_quality": { geometric_error: { cloud_to_mesh: { RMS: 111, max: 222 }, mesh_to_cloud: { RMS: 333, max: 444 } } },
};
const superficie = righeDelModello({ numero: 5, chiave: "05_reconstruct" }, metriche, valoreDellaMetrica);
const perNome = Object.fromEntries(superficie);
// "1234" e non "1.234": in italiano CLDR non raggruppa a quattro cifre
// (minimumGroupingDigits vale 2), e questo pannello formatta come la colonna
// del dettaglio -- stesso toLocaleString("it"), stesso esito. Un milione, sotto,
// il punto ce l'ha.
assert.equal(perNome["vertici"], "1234");
assert.equal(perNome["superficie"], "aperta");
assert.equal(perNome["spigoli di bordo"], "12");
const nuvola = Object.fromEntries(righeDelModello({ numero: 1, chiave: "01_load" }, metriche, valoreDellaMetrica));
assert.equal(nuvola["punti"], "1.000.000");
// Sei cifre significative, come valoreDellaMetrica: la colonna del dettaglio e
// questo pannello mostrano la stessa quantita' a due passi di distanza, e due
// arrotondamenti diversi sarebbero due numeri diversi per la stessa cosa.
assert.equal(nuvola["spaziatura media [mm]"], "1,19346");
assert.equal(nuvola["ingombro [mm]"], "2759 × 785 × 2000");
// Un ingombro senza numeri non e' un ingombro: un array vuoto non deve
// diventare la stringa vuota, che a schermo si legge «misurato e nullo».
const senzaIngombro = Object.fromEntries(righeDelModello({ numero: 1, chiave: "01_load" }, { "01_load": { extent: [] } }, valoreDellaMetrica));
assert.equal(senzaIngombro["ingombro [mm]"], "non misurato");
// Lo scarto si legge nel verso mesh_to_cloud, che e' quello che il progetto
// chiama «scarto dalla nuvola» (report.py, quality.py, e la legenda della
// vista, alimentata dal verso per-vertice). Leggere cloud_to_mesh metterebbe
// sotto lo stesso nome una misura diversa da quella gia' pubblicata.
const scarto = Object.fromEntries(righeDelModello({ numero: 7, chiave: "07_surface_quality" }, metriche, valoreDellaMetrica));
assert.equal(scarto["scarto dalla nuvola, RMS [mm]"], "333");
assert.equal(scarto["scarto dalla nuvola, massimo [mm]"], "444");
const vecchia = Object.fromEntries(righeDelModello({ numero: 6, chiave: "06_repair" }, { "06_repair": { vertices: 3 } }, valoreDellaMetrica));
assert.equal(vecchia["vertici"], "3");
assert.equal(vecchia["superficie"], "non misurato", "una corsa vecchia non inventa la chiusura");
assert.deepEqual(righeDelModello({ numero: 7, chiave: "07_surface_quality" }, {}, valoreDellaMetrica).map(([, v]) => v).every((v) => v === "non misurato"), true);
// Un percorso annidato interrotto a meta': `geometric_error` c'e' ma non e' un
// oggetto. Camminarci dentro senza guardare che cosa si sta aprendo solleverebbe.
const rotto = Object.fromEntries(righeDelModello({ numero: 7, chiave: "07_surface_quality" }, { "07_surface_quality": { geometric_error: 3 } }, valoreDellaMetrica));
assert.equal(rotto["scarto dalla nuvola, RMS [mm]"], "non misurato");
// Una chiave che la tabella non conosce non ha righe, e non e' un errore: il
// 12 e' escluso a monte, ma una chiave futura passerebbe di qui.
assert.deepEqual(righeDelModello({ numero: 13, chiave: "13_futuro" }, {}, valoreDellaMetrica), []);
// Cio' che non e' ne' numero ne' booleano si scrive com'e': C3D4 e' un
// identificatore, non un numero da formattare.
const deck = Object.fromEntries(righeDelModello({ numero: 11, chiave: "11_export" }, { "11_export": { element_type: "C3D4" } }, valoreDellaMetrica));
assert.equal(deck["tipo di elemento"], "C3D4");
""")


def test_il_pannello_del_modello_sta_nel_markup_con_il_proprio_vuoto():
    markup = _senza_commenti_html(_markup())
    assert 'id="modello"' in markup
    vuoto = _elemento(markup, "modello-vuoto")
    assert "hidden" not in vuoto, "lo stato vuoto nasce visibile: a corsa aperta il fronte non c'e' ancora"
    assert 'id="modello-righe"' in markup
    sezione = _elemento(markup, "modello")
    assert "aria-labelledby" not in sezione, (
        f"una <section> con un nome accessibile e' un landmark dentro il <nav>: {sezione}"
    )


def test_il_modello_si_rilegge_solo_quando_il_fronte_cambia(tmp_path):
    """Il flusso SSE arriva ogni mezzo secondo; una fetch a ogni fotogramma
    sarebbero due richieste al secondo per niente. La terna (numero, impronta,
    secondi) e' cio' che cambia nei tre casi che contano: esecuzione finita,
    annullamento, parametro modificato."""
    _esegui(tmp_path, _DOM + _funzioni("fronteDelloStato", "chiaveDelFronte") + """
const a = { numero: 6, impronta: "abc", secondi: 12.5 };
assert.equal(chiaveDelFronte(a), chiaveDelFronte({ ...a }));
assert.notEqual(chiaveDelFronte(a), chiaveDelFronte({ ...a, secondi: 13 }));
assert.notEqual(chiaveDelFronte(a), chiaveDelFronte({ ...a, impronta: "abd" }));
assert.equal(chiaveDelFronte(null), "");
// Uno step valido mai cronometrato non ha ne' impronta ne' secondi: la terna
// resta una stringa, e il confronto con la precedente non solleva.
assert.equal(typeof chiaveDelFronte({ numero: 6 }), "string");
assert.notEqual(chiaveDelFronte({ numero: 6 }), chiaveDelFronte(a));
""")


def test_il_pannello_del_modello_non_chiede_le_metriche_quando_non_c_e_un_fronte(tmp_path):
    """Le tre condizioni d'ingresso che si vedono solo facendo girare la
    tratta: nessuno step valido non chiede niente al server, la stessa terna
    non rilegge, e un corpo che non e' un oggetto lascia il fronte scritto ma
    le righe nascoste."""
    _esegui(tmp_path, _DOM + _funzioni(
        "fronteDelloStato", "chiaveDelFronte", "righeDelModello", "valoreDellaMetrica",
        "aggiornaModello", "superata", "serverMuto", "corpoLetto",
    ) + """
let richieste = 0;
let risponde = async () => ({ ok: true, status: 200, json: async () => ({ "01_load": { points_kept: 5 } }) });
globalThis.fetch = async () => { richieste += 1; return risponde(); };
const vuoto = document.getElementById("modello-vuoto");
const righe = document.getElementById("modello-righe");
const fronte = document.getElementById("modello-fronte");

// Nessuno step valido, e il solo prior valido: due strade per lo stesso vuoto.
await aggiornaModello([]);
await aggiornaModello([{ numero: 1, chiave: "01_load", stato: "mai eseguito" }]);
await aggiornaModello([{ numero: 12, chiave: "12_wall", stato: "valido", impronta: "w", secondi: 1 }]);
assert.equal(richieste, 0, "senza un fronte non si chiede niente a /api/metrics");

const uno = { numero: 1, chiave: "01_load", stato: "valido", impronta: "a", secondi: 1 };
await aggiornaModello([uno]);
assert.equal(richieste, 1);
assert.equal(righe.hidden, false, "le righe restano nascoste su un corpo buono");
await aggiornaModello([{ ...uno }]);
assert.equal(richieste, 1, "la stessa terna rilegge le metriche a ogni fotogramma");
await aggiornaModello([{ ...uno, secondi: 2 }]);
assert.equal(richieste, 2, "una terna nuova non rilegge");

// Torna a non avere fronte: il pannello si svuota da se' e non chiede niente.
await aggiornaModello([]);
assert.equal(richieste, 2);
assert.equal(righe.hidden, true);
assert.match(vuoto.textContent, /esegui lo step 1/);

// Un corpo che non e' un oggetto, e una fetch che non risponde affatto.
for (const guasto of [
  async () => ({ ok: true, status: 200, json: async () => null }),
  async () => ({ ok: true, status: 200, json: async () => "spazzatura" }),
  async () => { throw new TypeError("server spento"); },
]) {
  risponde = guasto;
  await aggiornaModello([{ numero: 5, chiave: "05_reconstruct", stato: "valido", impronta: guasto.name || String(Math.random()), secondi: 3 }]);
  assert.match(vuoto.textContent, /non si leggono/);
  assert.equal(vuoto.hidden, false);
  assert.equal(righe.hidden, true);
  assert.match(fronte.textContent, /dopo lo step 5/, "il fronte si dice comunque");
}
""")


def test_il_pannello_del_modello_marca_lo_steiner_saturato(tmp_path):
    """Spec §4.1: la saturazione dei punti di Steiner e' la «mesh troncata in
    silenzio» del primo principio di prodotto. Nella colonna del dettaglio
    l'avviso c'era gia'; qui la stessa misura si leggeva come tredicesima riga
    uguale alle altre, e chi guarda il pannello del modello non guarda l'altra
    colonna."""
    _esegui(tmp_path, _DOM + _funzioni(
        "fronteDelloStato", "chiaveDelFronte", "righeDelModello", "valoreDellaMetrica",
        "aggiornaModello", "superata", "serverMuto", "corpoLetto",
    ) + """
let metriche = { "09_tetrahedralize": { nodes: 10, tets: 20, steiner_points: 3, steiner_saturated: true } };
globalThis.fetch = async () => ({ ok: true, status: 200, json: async () => metriche });
const righe = document.getElementById("modello-righe");
const nono = { numero: 9, chiave: "09_tetrahedralize", stato: "valido", impronta: "a", secondi: 1 };

await aggiornaModello([nono]);
const avvisate = righe.querySelectorAll(".metrica-avviso");
assert.equal(avvisate.length, 1, "una riga sola, e non tutti i booleani veri");
// L'etichetta e' il fratello prima: il marchio deve stare sul valore giusto,
// non su una riga qualunque del pannello.
assert.equal(righe.children[righe.children.indexOf(avvisate[0]) - 1].textContent, "punti di Steiner esauriti: mesh troncata");

// Falso e' la buona notizia: nessun marchio. E' il set a decidere, non il tipo.
metriche = { "09_tetrahedralize": { nodes: 10, tets: 20, steiner_points: 3, steiner_saturated: false } };
await aggiornaModello([{ ...nono, impronta: "b" }]);
assert.equal(righe.querySelectorAll(".metrica-avviso").length, 0);
""")


def test_la_rilettura_del_modello_superata_non_riscrive_il_pannello(tmp_path):
    """Due cambi di fronte ravvicinati, e la prima risposta che arriva dopo la
    seconda. Stessa regola d'ordine delle altre tratte: vince chi e' partito
    per ultimo, non chi arriva per ultimo."""
    _esegui(tmp_path, _DOM + _funzioni(
        "fronteDelloStato", "chiaveDelFronte", "righeDelModello", "valoreDellaMetrica",
        "aggiornaModello", "superata", "serverMuto", "corpoLetto",
    ) + """
const inVolo = [];
globalThis.fetch = async () => new Promise((risolvi) => inVolo.push(risolvi));
const primo = aggiornaModello([{ numero: 6, chiave: "06_repair", stato: "valido", impronta: "x", secondi: 1 }]);
const secondo = aggiornaModello([{ numero: 8, chiave: "08_simplify", stato: "valido", impronta: "y", secondi: 2 }]);
assert.equal(inVolo.length, 2, "le due riletture non sono partite tutte e due");
// La seconda rilettura arriva e si scrive per intero; solo dopo arriva la
// prima. Aspettare `secondo` prima di sbloccare l'altra non e' pignoleria del
// banco: senza, le due tratte finiscono nello stesso giro di microtask e
// l'ordine di scrittura lo decide il motore, non il difetto che si prova.
inVolo[1]({ ok: true, status: 200, json: async () => ({ "08_simplify": { vertices: 8 } }) });
await secondo;
inVolo[0]({ ok: true, status: 200, json: async () => ({ "06_repair": { vertices: 6 } }) });
await primo;
const fronte = document.getElementById("modello-fronte");
assert.match(fronte.textContent, /dopo lo step 8/, "la risposta vecchia ha riscritto il pannello");
const righe = document.getElementById("modello-righe");
assert.ok(righe.figli.map((f) => f.testo).includes("8"),
  `le righe non sono quelle dello step 8: ${righe.figli.map((f) => f.testo).join("|")}`);
""")


def test_una_risposta_vecchia_non_riscrive_il_pannello_gia_svuotato(tmp_path):
    """Il fronte sparisce mentre una rilettura e' in volo -- si annulla una
    corsa, si cambia un parametro, si lega un'altra cartella.

    Se l'ordine si apre solo nel ramo con fronte, il ramo del vuoto esce senza
    invalidare cio' che sta arrivando: la risposta vecchia ripopola un pannello
    che nel frattempo e' stato svuotato. E siccome il vuoto ha segnato la
    propria terna (la stringa vuota), ogni fotogramma successivo senza fronte
    esce subito e quei numeri restano li' a descrivere un modello che non c'e'
    piu'.
    """
    _esegui(tmp_path, _DOM + _funzioni(
        "fronteDelloStato", "chiaveDelFronte", "righeDelModello", "valoreDellaMetrica",
        "aggiornaModello", "superata", "serverMuto", "corpoLetto",
    ) + """
const inVolo = [];
globalThis.fetch = async () => new Promise((risolvi) => inVolo.push(risolvi));
const righe = document.getElementById("modello-righe");
const vuoto = document.getElementById("modello-vuoto");

const primo = aggiornaModello([{ numero: 6, chiave: "06_repair", stato: "valido", impronta: "x", secondi: 1 }]);
assert.equal(inVolo.length, 1, "la prima rilettura non e' partita");
// Il fronte sparisce prima che la risposta arrivi.
await aggiornaModello([]);
assert.equal(righe.hidden, true);
inVolo[0]({ ok: true, status: 200, json: async () => ({ "06_repair": { vertices: 6 } }) });
await primo;
assert.equal(righe.hidden, true, "la risposta vecchia ha ripopolato un pannello svuotato");
assert.match(vuoto.textContent, /esegui lo step 1/);

// Il fotogramma dopo, ancora senza fronte: senza l'ordine aperto in cima, qui
// il pannello resterebbe incastrato sui numeri di un fronte che non c'e' piu'.
await aggiornaModello([]);
assert.equal(righe.hidden, true);
""")


def test_un_guasto_nella_rilettura_non_incastra_il_pannello(tmp_path):
    """`disegnaStep` lancia la rilettura e non l'aspetta. Se quella promessa
    viene rigettata dopo che la terna e' stata segnata come mostrata, il
    pannello resta con il contenuto vecchio e la terna nuova: nessun fotogramma
    successivo lo ripara, perche' la terna non cambia piu'.

    Il guasto qui e' una risposta che solleva quando la si guarda: `.catch` sta
    sulla fetch, non su cio' che viene dopo, quindi il rigetto esce davvero
    dalla tratta.
    """
    _esegui(tmp_path, _DOM + _funzioni(*_COLONNA) + """
let risponde = () => ({ get ok() { throw new Error("risposta rotta"); } });
globalThis.fetch = async () => risponde();
const steps = [{ numero: 1, chiave: "01_load", stato: "valido", impronta: "a", secondi: 1 }];
const respira = () => new Promise((risolvi) => setTimeout(risolvi, 0));
const righe = document.getElementById("modello-righe");

disegnaStep(steps);
await respira();
assert.equal(righe.figli.length, 0, "controprova: il guasto non e' arrivato al pannello");

// Il fotogramma dopo, stesso fronte e server tornato in se'.
risponde = () => ({ ok: true, status: 200, json: async () => ({ "01_load": { points_kept: 7 } }) });
disegnaStep(steps);
await respira();
assert.equal(righe.hidden, false, "dopo un guasto il pannello non si ripara piu': la terna resta segnata");
assert.ok(righe.figli.map((f) => f.testo).includes("7"),
  `le righe non portano il numero riletto: ${righe.figli.map((f) => f.testo).join("|")}`);
""")


def test_il_registro_sta_in_un_details_chiuso_alla_nascita():
    """Chiuso e non tolto: serve ancora a leggere perche' uno step e' fallito,
    ma a riposo non deve occupare quattordici righe della colonna."""
    markup = _senza_commenti_html(_markup())
    dettagli = _elemento(markup, "registro-dettagli")
    assert dettagli.startswith("<details"), dettagli
    assert " open" not in dettagli, "il registro nasce chiuso"
    assert 'tabindex="0"' in _elemento(markup, "registro")


def test_la_testata_nomina_le_esecuzioni_fra_le_cose_che_ctrl_z_annulla():
    assert "annulla l'ultima modifica o esecuzione" in _markup()


def test_la_frase_del_ritorno_antepone_l_esecuzione_annullata(tmp_path):
    # ETICHETTE e' gia' dichiarata (vuota) in _DOM, come per ogni altro banco
    # di questo file: si popola la stessa chiave con `ETICHETTE[...] = ...`,
    # non con una seconda `const ETICHETTE`, che in JS sarebbe un
    # SyntaxError su un identificatore ridichiarato.
    _esegui(tmp_path, _DOM + _funzioni("fraseDelRitorno") + """
ETICHETTE["02_segment"] = "Segmentazione";
const prima = [{ numero: 2, chiave: "02_segment", stato: "non valido" }];
const dopo = [{ numero: 2, chiave: "02_segment", stato: "valido" }];
assert.match(fraseDelRitorno(prima, dopo), /^configurazione ripristinata/);
assert.match(fraseDelRitorno(prima, dopo, { da: 2, a: 2 }), /^esecuzione dello step 2 annullata/);
assert.match(fraseDelRitorno(prima, dopo, { da: 2, a: 5 }), /^esecuzione dallo step 2 al 5 annullata/);
assert.match(fraseDelRitorno(prima, dopo, { da: 2, a: 11 }), /^esecuzione dallo step 2 all'11 annullata/);
// «Avanti» rifa' cio' che «indietro» aveva annullato: chiamarlo «annullata»
// dice all'utente il contrario di cio' che ha appena premuto. La
// configurazione invece si «ripristina» nei due versi, perche' e' quello che
// succede: torna a essere quella di un'altra volta.
assert.match(fraseDelRitorno(prima, dopo, { da: 2, a: 5 }, "avanti"), /^esecuzione dallo step 2 al 5 rifatta/);
assert.match(fraseDelRitorno(prima, dopo, null, "avanti"), /^configurazione ripristinata/);
assert.match(fraseDelRitorno(prima, dopo, { da: 2, a: 5 }, "indietro"), /^esecuzione dallo step 2 al 5 annullata/);
""")


def test_un_fallimento_porta_l_ultima_riga_del_registro_e_lo_apre(tmp_path):
    _esegui(tmp_path, _DOM + _funzioni("esitoDellaCorsa", "ultimaRigaDelRegistro", "descrizioneDellaCorsa", "nomeDelloStep") + """
const registro = document.getElementById("registro");
for (const testo of ["Traceback", "", "ValueError: nessun punto"]) {
  const riga = document.createElement("div"); riga.textContent = testo; registro.append(riga);
}
assert.equal(ultimaRigaDelRegistro(), "ValueError: nessun punto");
const { errore } = esitoDellaCorsa({ exit_code: 1, annullato: false, step: 2, a_step: 2, steps: [] });
assert.match(errore, /ValueError: nessun punto/);
assert.match(errore, /nel registro/);
""")
    # Sole righe bianche: nessuna parla, e la frase resta completa invece di
    # rompersi su un ultimo dettaglio inventato.
    _esegui(tmp_path, _DOM + _funzioni("esitoDellaCorsa", "ultimaRigaDelRegistro", "descrizioneDellaCorsa", "nomeDelloStep") + """
const registro = document.getElementById("registro");
for (const testo of ["", "   "]) {
  const riga = document.createElement("div"); riga.textContent = testo; registro.append(riga);
}
assert.equal(ultimaRigaDelRegistro(), "");
const { errore } = esitoDellaCorsa({ exit_code: 1, annullato: false, step: 2, a_step: 2, steps: [] });
// Senza una riga, la frase si chiude senza inventare un dettaglio assente:
// la riga puo' arrivare un giro dopo, dallo stesso flusso.
assert.match(errore, /colonna Dettaglio\.$/);
assert.ok(!/nessun dettaglio/.test(errore));
""")


def test_una_corsa_nuova_svuota_il_registro_della_precedente(tmp_path):
    """`#registro` non si svuotava da solo fra due corse: solo `#esito` lo fa,
    sul fronte di salita. La corsa 1 falliva con «ValueError: X»; l'utente la
    rilanciava e la corsa 2 moriva prima di scrivere una riga sua; `#esito`
    diceva ancora «...: ValueError: X» -- della corsa 1. Prima la frase era
    generica e la riga stantia non si vedeva; ora cita l'ultima riga per
    intero, e la riga stantia e' un dato falso.

    Mutazione che lo uccide: togliere lo svuotamento del registro dal fronte
    di salita di `aggiornaDaStato`.
    """
    _esegui(tmp_path, _banco_di_esito() + """
ETICHETTE["01_load"] = "Lettura";
const steps = [{ numero: 1, chiave: "01_load", stato: "valido", secondi: 12 }];
const base = { step: 1, a_step: 1, steps, annullato: false };

// La corsa 1 fallisce e lascia una riga nel registro, aperto.
const registro = document.getElementById("registro");
const dettagli = document.getElementById("registro-dettagli");
const riga = document.createElement("div"); riga.textContent = "ValueError: X"; registro.append(riga);
dettagli.open = true;

// La corsa 2 parte: il fronte di salita svuota e richiude il registro della
// corsa precedente, prima che quella nuova abbia scritto niente.
aggiornaDaStato({ ...base, in_corso: true, exit_code: null });
assert.equal(registro.childElementCount, 0, "il registro della corsa vecchia e' rimasto");
assert.equal(dettagli.open, false, "il registro della corsa vecchia e' rimasto aperto");

// E muore subito, prima di scrivere una riga sua.
aggiornaDaStato({ ...base, in_corso: false, exit_code: 1 });
assert.match(esito.textContent, /colonna Dettaglio\.$/);
assert.ok(!esito.textContent.includes("ValueError"), "l'esito cita ancora la corsa precedente: " + esito.textContent);
""")


# --------------------------------------------------------------------------
# Il predefinito del campo: detto sotto la casella, e rimesso da un bottone.
# --------------------------------------------------------------------------


def test_l_aiuto_del_campo_dice_il_predefinito(tmp_path):
    """`/api/schema` manda gia' `default` per ogni campo, e il pannello lo
    usava solo per decidere quali righe piegare: chi ha girato `min_ratio` tre
    volte non aveva piu' modo di sapere da dove era partito.

    Il controllo e' `!== undefined && !== null` e non `if (campo.default)`:
    `0`, `false` e la stringa vuota sono predefiniti veri, e un `if` sul valore
    li nasconderebbe proprio dove servono di piu'.
    """
    _esegui(tmp_path, _DOM + _funzioni("testoDellAiuto") + """
assert.equal(testoDellAiuto({ description: "profondità dell'albero", default: 8 }, true, false), "profondità dell'albero — predefinito: 8");
assert.equal(testoDellAiuto({ default: null }, true, false), "");
assert.equal(testoDellAiuto({ description: "x" }, false, false), "x — si modifica dal file di configurazione");
// I falsi che sono predefiniti veri.
assert.equal(testoDellAiuto({ default: 0 }, true, false), "predefinito: 0");
assert.equal(testoDellAiuto({ default: false }, true, false), "predefinito: false");
assert.equal(testoDellAiuto({ default: "" }, true, false), "predefinito: ");
// Senza description non resta un « — » pendente in testa.
assert.equal(testoDellAiuto({ default: 8 }, true, false), "predefinito: 8");
""")


def test_riporta_rimette_il_predefinito_dello_schema_e_lo_scrive(tmp_path):
    """Il bottone accanto alla casella, e solo dove ha senso.

    Rimettere il predefinito passa dal gestore `change` che gia' salva, non da
    una seconda strada verso il server: e' la stessa scrittura di una battuta a
    mano, con lo stesso ripristino e lo stesso rifiuto a video. Su una corsa in
    sola lettura il server dice di no, e il no si legge nella riga del campo.

    Mutazione che lo uccide: `if (campo.default)` al posto del confronto con
    undefined e null -- `0` e `false` sono predefiniti veri e perderebbero il
    bottone.
    """
    _esegui(tmp_path, _banco_del_campo() + """
configurazione = { downsample: { voxel_size: 25 }, segment: { crop_max: null } };
const riporta = (riga) => riga.children.filter((f) => f.className.includes("riporta"));
const campoCon = (schema) => campoParametro("downsample", "voxel_size", schema, generazione);

// Senza predefinito non c'e' niente da rimettere, e `null` non e' un valore.
assert.equal(riporta(campoCon({ description: "x" })).length, 0, "un bottone senza predefinito da rimettere");
assert.equal(riporta(campoCon({ description: "x", default: null })).length, 0, "null preso per un predefinito");
// I falsi che sono predefiniti veri: qui il bottone serve piu' che altrove.
assert.equal(riporta(campoCon({ description: "x", default: 0 })).length, 1, "predefinito 0 senza bottone");
assert.equal(riporta(campoCon({ description: "x", default: false })).length, 1, "predefinito false senza bottone");
// Un composto non si scrive da qui: la casella e' in sola lettura e non c'e'
// nessun gestore da scatenare.
const composto = campoParametro("segment", "crop_max",
  { description: "x", tipo: "composto", nullabile: true, default: [0, 0, 0] }, generazione);
assert.equal(riporta(composto).length, 0, "un composto in sola lettura ha preso un bottone che scrive");

// Il clic scrive, per la strada della battuta a mano.
const riga = campoCon({ description: "x", default: 30 });
const [, input] = riga.children;
const [bottone] = riporta(riga);
const messaggio = riga.children.find((f) => f.className === "errore-campo");
assert.equal(bottone.textContent, "Riporta");
assert.match(bottone.title, /30/, "il bottone non dice a che valore riporta");
// Venti «Riporta» in un pannello sono venti bottoni identici per chi ascolta:
// il nome accessibile porta il campo, e il campo si nomina con la propria
// etichetta, non con la chiave.
assert.match(bottone.ariaLabel, /voxel_size/,
  "il bottone non dice quale campo riporta: " + bottone.ariaLabel);
input.value = "25";
risponde = accetta({ downsample: { voxel_size: 30 } });
await bottone.scatena("click");
await new Promise((r) => setTimeout(r, 0));
assert.equal(richieste.at(-1).corpo.downsample.voxel_size, 30, "il predefinito non e' arrivato al server");
assert.equal(input.value, "30", "la casella non mostra il valore rimesso");

// La corsa registrata e' in sola lettura: il no del server si legge nella riga.
risponde = rifiuta({ detail: "la corsa e' registrata: sola lettura" });
await bottone.scatena("click");
await new Promise((r) => setTimeout(r, 0));
assert.match(messaggio.textContent, /sola lettura/, "il rifiuto del server non arriva a video: " + messaggio.textContent);
assert.equal(configurazione.downsample.voxel_size, 30, "il valore rifiutato resta in memoria");
""")


# --------------------------------------------------------------------------
# La fine della corsa fuori dalla scheda: il titolo, e la notifica.
# --------------------------------------------------------------------------


def test_il_titolo_della_scheda_porta_l_esito(tmp_path):
    """Uno step dura minuti, e chi aspetta cambia finestra. Il titolo della
    scheda e' l'unico segnale che arriva a chi non sta guardando la pagina."""
    _esegui(tmp_path, _DOM + _funzioni("titoloConEsito") + """
assert.equal(titoloConEsito(null, null), "MeshRec");
assert.equal(titoloConEsito(null, "Segmentazione: conclusa"), "✓ MeshRec");
assert.equal(titoloConEsito("Segmentazione: fallita", null), "✗ MeshRec");
""")


def test_la_notifica_non_parte_a_pagina_a_fuoco_ne_senza_permesso_ne_vuota(tmp_path):
    """Una notifica a pagina aperta ripete cio' che sta gia' a video due righe
    sotto il titolo; una notifica vuota e' un rumore che non dice niente.

    Mutazione che lo uccide: togliere la guardia su `document.hasFocus()`.
    """
    _esegui(tmp_path, _DOM + _funzioni("notificaFuoriDallaScheda") + """
const mandate = [];
globalThis.Notification = class { constructor(titolo, opzioni) { mandate.push([titolo, opzioni.body]); } };
Notification.permission = "granted";
document.hasFocus = () => true;

notificaFuoriDallaScheda("Segmentazione: conclusa");
assert.deepEqual(mandate, [], "notifica mandata a pagina a fuoco");

document.hasFocus = () => false;
notificaFuoriDallaScheda("");
assert.deepEqual(mandate, [], "notifica vuota mandata");

notificaFuoriDallaScheda("Segmentazione: conclusa");
assert.deepEqual(mandate, [["MeshRec", "Segmentazione: conclusa"]]);

Notification.permission = "denied";
notificaFuoriDallaScheda("Riparazione: fallita");
assert.equal(mandate.length, 1, "notifica mandata senza permesso");
""")


def test_il_permesso_di_notifica_si_chiede_con_un_bottone_e_mai_da_solo(tmp_path):
    """La finestra del permesso chiesta da sola all'apertura e' quella che ogni
    sito apre senza motivo, e che si nega per riflesso. Qui la chiede un
    bottone, e il bottone sparisce con la risposta -- qualunque sia, tranne la
    finestra chiusa senza scegliere, che lascia tutto com'era.

    Un browser senza l'API (o il DOM finto di `node`) non e' un caso di
    guasto: il bottone si nasconde e il resto della pagina non se ne accorge.
    """
    assert 'id="notifiche"' in _senza_commenti_html(_markup())
    _esegui(tmp_path, _DOM + _funzioni("preparaLeNotifiche") + """
const bottone = document.getElementById("notifiche");

// Senza l'API: il bottone sparisce e non promette niente.
delete globalThis.Notification;
preparaLeNotifiche(bottone);
assert.equal(bottone.hidden, true, "il bottone resta a video in un browser senza notifiche");
assert.equal((bottone.gestori.click ?? []).length, 0, "un gestore attaccato dove l'API non c'e'");

// Permesso gia' negato: niente da chiedere una seconda volta.
globalThis.Notification = { permission: "denied", requestPermission: async () => "denied" };
preparaLeNotifiche(bottone);
assert.equal(bottone.hidden, true, "il bottone chiede un permesso gia' negato");

// Da decidere: il bottone c'e', e il clic chiede.
let risposta = "granted";
globalThis.Notification = { permission: "default", requestPermission: async () => risposta };
preparaLeNotifiche(bottone);
assert.equal(bottone.hidden, false, "il bottone non compare dove il permesso e' ancora da chiedere");
await bottone.scatena("click");
assert.equal(bottone.hidden, true, "il bottone resta dopo che il permesso e' stato dato");

// Finestra chiusa senza scegliere: si potra' chiedere di nuovo.
risposta = "default";
preparaLeNotifiche(bottone);
await bottone.scatena("click");
assert.equal(bottone.hidden, false, "la finestra chiusa senza scegliere si porta via il bottone");
""")


def test_il_fronte_di_discesa_scrive_l_esito_anche_nel_titolo_della_scheda(tmp_path):
    """Il cablaggio, non la sola funzione pura: il segno nel titolo deve
    arrivarci dal fronte di discesa, che e' l'unico punto in cui si sa che una
    corsa e' finita.

    Mutazione che lo uccide: togliere `document.title = titoloConEsito(...)`
    dal fronte di discesa.
    """
    _esegui(tmp_path, _banco_di_esito() + """
ETICHETTE["01_load"] = "Lettura";
const steps = [{ numero: 1, chiave: "01_load", stato: "valido", secondi: 12 }];
const base = { step: 1, a_step: 1, steps, annullato: false };

aggiornaDaStato({ ...base, in_corso: true, exit_code: null });
aggiornaDaStato({ ...base, in_corso: false, exit_code: 0 });
assert.equal(document.title, "✓ MeshRec", "la corsa conclusa non si vede dalla barra delle schede");

aggiornaDaStato({ ...base, in_corso: true, exit_code: null });
aggiornaDaStato({ ...base, in_corso: false, exit_code: 1 });
assert.equal(document.title, "✗ MeshRec", "il fallimento non si vede dalla barra delle schede");
""")


# --------------------------------------------------------------------------
# I due comandi della vista: inquadra, e salva il PNG.
# --------------------------------------------------------------------------


def test_i_tre_comandi_della_vista_stanno_nel_markup():
    markup = _senza_commenti_html(_markup())
    assert 'id="inquadra"' in markup and 'id="salva-immagine"' in markup
    assert 'id="salva-tutti"' in markup, "il tasto «Salva un'immagine per step» non e' nel markup"
    # «Salva tutti gli step» si leggeva come «salva la configurazione degli
    # step»: il nome dice che cosa esce, un'immagine, e quante, una per step.
    assert _elemento(markup, "salva-tutti") + "Salva un'immagine per step</button>" in markup, (
        "il tasto del giro non si chiama «Salva un'immagine per step»"
    )
    assert 'getElementById("salva-tutti").addEventListener("click", salvaTuttiGliStep)' in _modulo(), (
        "il tasto «Salva un'immagine per step» non e' collegato al giro"
    )
    # L'esito del giro ha una regione viva nel markup, come #collegamento-perso:
    # sei file che partono senza una riga che lo dica si sentono solo come sei
    # cambi di #conteggi.
    assert re.search(r'<p[^>]*id="esito-salvataggio"', markup), "manca la regione dell'esito del giro"
    assert 'role="status"' in _elemento(markup, "esito-salvataggio"), (
        "l'esito del giro non e' una regione di stato: chi ascolta non lo sente"
    )


def _banco_dei_comandi_della_vista() -> str:
    """`salvaImmagine` con la vista finta e i tre elementi che legge."""
    return _DOM + _costante("STEP_CON_GEOMETRIA") + "\n" + _funzioni("nomeDellaCorsa", "didascaliaDellaVista", "passoDaMostrare", "schedaDiProvenienza", "valoreDellaMetrica", "blocchiDeiParametri", "superata", "spezzaInRighe", "immagineConProvenienza", "dichiaraErrore", "serverMuto", "ragioneDelRifiuto", "corpoLetto", "consegnaImmagine", "salvaImmagine") + """
let schemaParametri = null;
// Un server che serve schema e configurazione: senza, il cartiglio non puo'
// dire i parametri e il comando dichiara l'errore. I banchi che provano quel
// ramo lo sovrascrivono.
const SCHEMA_DEL_BANCO = { "6": { blocchi: ["repair"], campi: { repair: { max_hole_area: { etichetta: "area massima del buco [mm²]", default: null } } } } };
// La consegna al server: la fetch finta registra ogni POST a /api/immagine
// (corpo JSON parsato). Il nome del file lo decide il server (immagini.py,
// provato in test_immagini.py); qui il percorso e' una stringa fissa, e i
// test controllano il corpo consegnato (numero, nome, didascalia), non un
// nome sintetizzato lato JS.
const consegne = [];
globalThis.fetch = async (percorso, opzioni) => {
  if (percorso === "/api/immagine") {
    const corpo = JSON.parse(opzioni.body);
    const percorsoScritto = "runs/lab/immagini/x.png";
    consegne.push({ ...corpo, percorso: percorsoScritto });
    return { ok: true, status: 200, json: async () => ({ percorso: percorsoScritto }) };
  }
  return { ok: true, status: 200, json: async () => percorso === "/api/schema" ? SCHEMA_DEL_BANCO : { repair: { max_hole_area: null } } };
};
const creati = [];
const creaVero = document.createElement;
document.createElement = (tag) => { const nodo = creaVero(tag); creati.push(nodo); return nodo; };
const vista = { catture: 0, cattura() { this.catture += 1; return "data:image/png;base64,AAA"; } };
let stepScelto = null;
document.getElementById("corsa").textContent = "runs/lab_crop";
document.getElementById("didascalia-vista").textContent = "scarto RMS 9,5 mm";
ETICHETTE["06_repair"] = "Riparazione";
ultimoStato = [{ numero: 6, chiave: "06_repair", stato: "valido" }];
// L'ultima consegna al server: prima leggeva l'<a download> scaricato dal
// browser, ora legge la POST /api/immagine registrata dalla fetch finta.
const scaricato = () => consegne.at(-1);
"""


def test_salva_immagine_scrive_un_png_col_nome_della_corsa(tmp_path):
    """Il PNG va al server, in runs/<corsa>/immagini/: nessuno ZIP, nessun
    pannello «Salva» per ogni figura.

    Senza uno step scelto non c'e' niente da consegnare, e il comando non
    fabbrica un file vuoto col nome di nessuna corsa. Uno step che lo stato
    non conosce prende il proprio numero, non «undefined».
    """
    _esegui(tmp_path, _banco_dei_comandi_della_vista() + """
// Nessuno step scelto: nessuna consegna, nessuna cattura.
await salvaImmagine();
assert.equal(scaricato(), undefined, "una consegna senza uno step scelto");
assert.equal(vista.catture, 0, "la tela e' stata catturata senza uno step scelto");

stepScelto = 6;
await salvaImmagine();
assert.equal(scaricato().numero, 6);
assert.equal(scaricato().nome, "Riparazione");
assert.equal(scaricato().didascalia, "scarto RMS 9,5 mm");
assert.equal(scaricato().dati, "data:image/png;base64,AAA", "la consegna non porta la tela catturata");

// Uno step che lo stato non conosce: il numero, non «undefined».
ultimoStato = [];
await salvaImmagine();
assert.equal(scaricato().numero, 6);
assert.equal(scaricato().nome, "step 6", "uno step che lo stato non conosce prende il proprio numero, non «undefined»");
""")


def test_l_ingresso_e_un_form_e_invio_lo_manda():
    """Battuto il nome e il percorso, Invio non faceva niente: bisognava
    lasciare i tasti e cercare il bottone. Due caselle e un bottone di invio
    sono un form, e il form Invio lo manda da se'.

    `novalidate` perche' la validazione la fa `ragioneLocale`, che scrive nella
    riga `role="alert"`: la bolla del browser la coprirebbe con un messaggio
    che non e' nemmeno nella lingua dell'interfaccia.
    """
    markup = _senza_commenti_html(_markup())
    assert re.search(r'<form[^>]*id="nuova-corsa"', markup), (
        "i due campi e il bottone non stanno in un <form>: Invio non manda niente"
    )
    assert "novalidate" in _elemento(markup, "nuova-corsa"), (
        "senza novalidate la bolla del browser copre la riga d'errore"
    )
    assert 'type="submit"' in _elemento(markup, "crea-corsa")
    assert 'getElementById("nuova-corsa").addEventListener("submit"' in _modulo(), (
        "il gestore sta ancora sul clic del bottone: da tastiera non lo raggiunge nessuno"
    )


# --------------------------------------------------------------------------
# Le metriche degli altri step: un nome, e l'avviso su cio' che contraddice.
# --------------------------------------------------------------------------


def test_le_metriche_che_contraddicono_hanno_un_etichetta_e_l_avviso(tmp_path):
    """«Una chiave non si stampa mai, si stampa la sua etichetta» (PRODUCT.md):
    la tabella copriva due step sugli undici che hanno un pannello -- dodici
    sono gli step della pipeline, ma il prior geometrico non si apre da qui --
    e sugli altri nove il pannello
    mostrava `points_dropped` e `holes_over_threshold` cosi' com'erano.

    `steiner_saturated` vero e' la «mesh troncata in silenzio» del primo
    principio di prodotto, e non sta fra tredici righe uguali. Il canale non e'
    solo il colore: l'etichetta stessa dice «mesh troncata».

    Il set decide, non il tipo del valore: `watertight` vero e' una buona
    notizia, e un avviso su ogni booleano vero direbbe il contrario.
    """
    _esegui(tmp_path, _DOM + "\n".join(
        _costante(nome) for nome in ("VALORE_LARGO", "CLASSE_VALORE_LARGO")
    ) + "\n" + _funzioni("righeDellaMetrica", "valoreDellaMetrica") + f"""
const ETICHETTE_METRICHE = {json.dumps(_etichette_metriche())};
const righe = righeDellaMetrica("steiner_saturated", true, ETICHETTE_METRICHE["09_tetrahedralize"]);
assert.equal(righe[0].textContent, "punti di Steiner esauriti: mesh troncata");
assert.equal(righe[1].className, "metrica-avviso");
const quiete = righeDellaMetrica("steiner_saturated", false, ETICHETTE_METRICHE["09_tetrahedralize"]);
assert.equal(quiete[1].className, "", "il falso prende l'avviso del vero");
// Un booleano vero che NON e' d'allarme resta quieto: decide il set.
for (const [chiave, tabella] of [["watertight", "05_reconstruct"], ["enabled", "08_simplify"]]) {{
  const buona = righeDellaMetrica(chiave, true, ETICHETTE_METRICHE[tabella]);
  assert.equal(buona[1].className, "", `${{chiave}} vero e' diventato un avviso`);
}}
// Uno step senza tabella, e una chiave che la tabella non conosce: la chiave
// grezza, non «undefined», e nessuna eccezione.
const ignota = righeDellaMetrica("metrica_di_domani", 3, ETICHETTE_METRICHE["99_mai_esistito"]);
assert.equal(ignota[0].textContent, "metrica_di_domani");
// Le chiavi che il pannello mostrava grezze, una per step.
for (const [chiave, nome] of [["01_load", "size_check"], ["06_repair", "watertight_after"], ["06_repair", "holes_over_threshold"], ["11_export", "fixed_nset_coverage"], ["02_segment", "points_after"], ["03_downsample", "voxel_size"], ["09_tetrahedralize", "steiner_points"]]) {{
  assert.ok(ETICHETTE_METRICHE[chiave]?.[nome], `${{chiave}}.${{nome}} senza etichetta`);
}}
// Le cinque righe annidate dell'aspetto: 05, 06 e 08 portano la stessa
// distribuzione dello step 7 (pipeline._con_le_misure_della_superficie).
for (const chiave of ["05_reconstruct", "06_repair", "08_simplify"]) {{
  for (const dentro of ["min", "median", "mean", "max", "non_finite"]) {{
    assert.ok(ETICHETTE_METRICHE[chiave]?.[`aspect_ratio · ${{dentro}}`],
      `${{chiave}} non etichetta aspect_ratio · ${{dentro}}`);
  }}
}}
""")


def test_etichette_js_non_importa_niente():
    """`etichette.js` deve restare valutabile da solo con `node -e`: e' cosi'
    che `_etichette_metriche()` lo legge, senza un server che gli serva un
    secondo modulo. Un `import` lo romperebbe in silenzio per chi lo valuta
    isolato."""
    testo = _senza_commenti_js((UI_DIR / "etichette.js").read_text(encoding="utf-8"))
    assert re.search(r"\bimport\b", testo) is None, (
        "etichette.js importa qualcosa: non e' piu' valutabile da solo"
    )


def test_le_funzioni_pure_del_modello_girano_senza_un_dom():
    """`fronteDelloStato`, `chiaveDelFronte` e `righeDelModello` sono pure:
    prese da un node nudo, senza `document` ne' `fetch`, devono girare lo
    stesso. Se una di loro toccasse un globale da browser questo banco
    cadrebbe su un ReferenceError che lo nomina."""
    uscita = _importa(UI_DIR / "modello.js", """
const fronte = modulo.fronteDelloStato(
  [{ numero: 1, chiave: "01_load", stato: "valido" }], "12_wall",
);
const chiave = modulo.chiaveDelFronte(fronte);
const righe = modulo.righeDelModello(fronte, { "01_load": { points_kept: 5 } }, String);
console.log(JSON.stringify({ numero: fronte.numero, chiave, punti: righe[0][1] }));
""")
    esito = json.loads(uscita)
    assert esito == {"numero": 1, "chiave": "1|undefined|undefined", "punti": "5"}


def test_creaPannelloModello_senza_una_dipendenza_solleva_subito(tmp_path):
    """La factory deve accorgersi di una dipendenza mancante alla
    costruzione, non al primo `aggiornaModello(...)`: un `TypeError` col nome
    di chi manca, non un crash al primo fotogramma disegnato."""
    percorso = (UI_DIR / "modello.js").resolve().as_uri()
    _esegui(tmp_path, f"""
import assert from 'node:assert/strict';
import {{ creaPannelloModello }} from {percorso!r};
const dipendenze = {{
  fetch: () => {{}}, elemento: () => {{}}, superata: () => {{}}, serverMuto: () => {{}},
  corpoLetto: () => {{}}, valoreDellaMetrica: () => {{}}, ETICHETTE: {{}}, STEP_DEL_PRIOR: "12_wall",
}};
for (const nome of Object.keys(dipendenze)) {{
  const incomplete = {{ ...dipendenze }};
  delete incomplete[nome];
  assert.throws(() => creaPannelloModello(incomplete), new RegExp(nome),
    `senza ${{nome}} la factory doveva sollevare nominandolo`);
}}
creaPannelloModello(dipendenze);
""")


def test_un_guasto_dopo_la_lettura_non_incastra_il_pannello(tmp_path):
    """Non solo un guasto sulla fetch/lettura del corpo (gia' provato altrove):
    anche un throw DOPO, nel rendering (`elemento` che rompe), deve azzerare
    `fronteMostrato` invece di lasciare la terna segnata con il pannello
    incastrato. Prima lo garantiva il `.catch` su `aggiornaModello(steps)` in
    app.js, che avvolgeva l'intera chiamata; azzerarla solo sul guasto
    fetch/corpo (comune ma non l'unico) lasciava scoperto tutto cio' che sta
    dopo."""
    percorso = (UI_DIR / "modello.js").resolve().as_uri()
    _esegui(tmp_path, f"""
import assert from 'node:assert/strict';
import {{ creaPannelloModello }} from {percorso!r};

let richieste = 0;
const documentoFinto = {{
  getElementById: () => ({{ set textContent(_v) {{}}, set hidden(_v) {{}} }}),
}};
globalThis.document = documentoFinto;

const {{ aggiornaModello }} = creaPannelloModello({{
  fetch: async () => {{ richieste += 1; return {{ ok: true, status: 200, json: async () => ({{ "01_load": {{ points_kept: 5 }} }}) }}; }},
  // Rompe SOLO nel rendering: la fetch e la lettura del corpo vanno a buon
  // fine, quindi un banco che guardasse solo quel tratto direbbe verde.
  elemento: () => {{ throw new Error("elemento rotto"); }},
  superata: () => false,
  serverMuto: () => ({{ ok: false }}),
  corpoLetto: async (risposta) => risposta.json(),
  valoreDellaMetrica: (v) => String(v),
  ETICHETTE: {{}},
  STEP_DEL_PRIOR: "12_wall",
}});

const fronte = {{ numero: 1, chiave: "01_load", stato: "valido", impronta: "a", secondi: 1 }};
await assert.doesNotReject(() => aggiornaModello([fronte]), "il guasto dopo la lettura non deve uscire da aggiornaModello");
assert.equal(richieste, 1);

// Stesso fronte: se la terna non fosse stata azzerata sul guasto, questa
// rilettura uscirebbe subito senza una seconda fetch.
await aggiornaModello([fronte]);
assert.equal(richieste, 2, "la terna non e' stata azzerata dopo il guasto nel rendering: nessuna rilettura riparte");
""")


def test_ogni_step_ha_la_propria_tabella_salvo_il_prior():
    """Dodici chiavi in `ETICHETTE`, undici tabelle in `ETICHETTE_METRICHE`:
    il prior (`12_wall`) non ha pannello (`disegnaStep` lo filtra, PRODUCT.md
    lo dichiara fuori dall'interfaccia). Una chiave senza tabella qui
    cadrebbe su `undefined` nel pannello del dettaglio invece che su un rosso
    che dice il nome."""
    inizio, fine = "const ETICHETTE = {", "\n};"
    testo = _modulo()
    assert inizio in testo, f"ancora d'inizio assente: {inizio}"
    corpo = testo.split(inizio, 1)[1].split(fine, 1)[0]
    chiavi = re.findall(r'"(\d\d_\w+)":', corpo)
    assert chiavi, "nessuna chiave trovata in ETICHETTE: l'estrazione si e' rotta"
    tabelle = _etichette_metriche()
    mancanti = [c for c in chiavi if c != "12_wall" and c not in tabelle]
    assert mancanti == [], f"chiavi di ETICHETTE senza tabella in ETICHETTE_METRICHE: {mancanti}"


def test_una_corsa_nuova_toglie_il_segno_dal_titolo(tmp_path):
    """Il segno nel titolo lo toglie il fuoco sulla pagina -- ma se la corsa e'
    finita MENTRE si guardava, il fuoco c'e' gia' e non scatta piu': lanciato lo
    step successivo e cambiata finestra, la scheda diceva «✓ MeshRec» su una
    corsa in corso. Il fronte di salita, che gia' azzera l'esito e il registro,
    azzera anche il titolo.

    Mutazione che lo uccide: togliere `document.title = "MeshRec"` dal fronte
    di salita di `aggiornaDaStato`.
    """
    _esegui(tmp_path, _banco_di_esito() + """
ETICHETTE["01_load"] = "Lettura";
const steps = [{ numero: 1, chiave: "01_load", stato: "valido", secondi: 12 }];
const base = { step: 1, a_step: 1, steps, annullato: false };

aggiornaDaStato({ ...base, in_corso: true, exit_code: null });
aggiornaDaStato({ ...base, in_corso: false, exit_code: 0 });
assert.equal(document.title, "✓ MeshRec");

// La corsa dopo, senza che nessuno abbia mai lasciato la pagina.
aggiornaDaStato({ ...base, in_corso: true, exit_code: null });
assert.equal(document.title, "MeshRec",
  "la scheda dice ancora ✓ su una corsa che sta girando: " + document.title);
""")


def test_una_corsa_conclusa_ha_il_proprio_colore_e_l_interrotta_no(tmp_path):
    """La riga dell'esito porta tre fatti con tre colori, come la colonna degli
    step: conclusa (accento), interrotta (grigio), fallita (rosso). La classe
    della riuscita la decide il chiamante, non il testo: «interrotta» arriva
    come esito e non e' una riuscita.

    Mutazione che lo uccide: passare `true` fisso a `mostraEsito` sul fronte
    di discesa, che colorerebbe anche l'interruzione.
    """
    _esegui(tmp_path, _banco_di_esito() + """
ETICHETTE["01_load"] = "Lettura";
const steps = [{ numero: 1, chiave: "01_load", stato: "valido", secondi: 2 }];

aggiornaDaStato({ in_corso: true, step: 1, a_step: 1, steps, da_secondi: 0.5, annullato: false, exit_code: null });
aggiornaDaStato({ in_corso: false, step: 1, a_step: 1, steps, da_secondi: null, annullato: false, exit_code: 0 });
assert.match(esito.textContent, /esecuzione conclusa/);
assert.ok(esito.className.includes("esito-riuscito"), "la corsa conclusa non ha il proprio colore");
assert.ok(!esito.className.includes("esito-fallito"));

aggiornaDaStato({ in_corso: true, step: 1, a_step: 1, steps, da_secondi: 0.1, annullato: false, exit_code: null });
assert.ok(!esito.className.includes("esito-riuscito"), "la riuscita vecchia e' rimasta sopra la corsa nuova");
aggiornaDaStato({ in_corso: false, step: 1, a_step: 1, steps, da_secondi: null, annullato: true, exit_code: -15 });
assert.match(esito.textContent, /esecuzione interrotta/);
assert.ok(!esito.className.includes("esito-riuscito"), "un'interruzione e' una scelta, non una riuscita");
assert.ok(!esito.className.includes("esito-fallito"));

// Il terzo colore: una corsa fallita e' rossa e non verde.
aggiornaDaStato({ in_corso: true, step: 1, a_step: 1, steps, da_secondi: 0.1, annullato: false, exit_code: null });
aggiornaDaStato({ in_corso: false, step: 1, a_step: 1, steps, da_secondi: null, annullato: false, exit_code: 2 });
assert.ok(esito.className.includes("esito-fallito"));
assert.ok(!esito.className.includes("esito-riuscito"), "una corsa fallita ha preso il colore della riuscita");

// Un esito passato senza il terzo argomento resta grigio: i ritorni della
// cronologia non sono corse.
mostraEsito(null, "configurazione ripristinata: nessuno step cambia stato");
assert.ok(!esito.className.includes("esito-riuscito"));
""")


def test_la_colonna_segna_l_intervallo_che_sta_girando(tmp_path):
    """Mentre una corsa dura, le righe da `step` ad `a_step` portano
    aria-busy; a corsa ferma, o su un comando senza step, nessuna.
    L'intervallo e non lo step corrente: il server non lo sa (stato.step e' il
    capo di partenza e non avanza).

    Mutazione che lo uccide: `numero === stato.step` al posto dell'intervallo,
    che su una corsa da 5 a 11 segnerebbe la sola Superficie.
    """
    _esegui(tmp_path, _DOM + _funzioni("nuovaRiga", "segnaIntervalloInEsecuzione") + """
const colonna = document.getElementById("elenco-step");
colonna.replaceChildren(...[1, 2, 3, 4, 5].map(() => nuovaRiga()));
[...colonna.children].forEach((riga, i) => { riga.firstElementChild.dataset.numero = i + 1; });
const segnate = () => [...colonna.children].filter((r) => r.getAttribute("aria-busy") === "true").map((r) => Number(r.firstElementChild.dataset.numero));

segnaIntervalloInEsecuzione({ in_corso: true, step: 2, a_step: 4 });
assert.deepEqual(segnate(), [2, 3, 4]);

// a_step assente: il solo capo.
segnaIntervalloInEsecuzione({ in_corso: true, step: 3, a_step: null });
assert.deepEqual(segnate(), [3]);

// Corsa ferma: tutto tolto.
segnaIntervalloInEsecuzione({ in_corso: false, step: 3, a_step: 3 });
assert.deepEqual(segnate(), []);

// Comando fuori pipeline: nessuno step, nessuna riga.
segnaIntervalloInEsecuzione({ in_corso: true, step: null, a_step: null });
assert.deepEqual(segnate(), []);
""")

def test_la_frase_dello_stato_spiega_la_parola_della_colonna(tmp_path):
    """«non valido» sta nella colonna, nella CLI e nella spec, e a chi non
    conosce la pipeline suona come «rotto»: il pannello dello step aperto lo
    spiega e dice che cosa fare. Uno stato che la tabella non conosce -- o
    uno step che lo stato non conosce -- non prende una frase inventata.

    Mutazione che lo uccide: `?? ""` al posto di `?? null`, che farebbe
    comparire una riga vuota sotto ogni intestazione.
    """
    _esegui(tmp_path, _DOM + _funzioni("fraseDelloStato") + """
assert.match(fraseDelloStato({ stato: "non valido" }), /parametri diversi da quelli correnti/);
assert.match(fraseDelloStato({ stato: "non valido" }), /Riesegui/, "lo stato che chiede un gesto lo nomina");
assert.match(fraseDelloStato({ stato: "valido" }), /parametri correnti/);
assert.match(fraseDelloStato({ stato: "fallito" }), /registro/, "il fallito dice dove sta il motivo");
assert.match(fraseDelloStato({ stato: "mai eseguito" }), /Mai eseguito/);
assert.equal(fraseDelloStato({ stato: "in orbita" }), null);
assert.equal(fraseDelloStato(undefined), null);
""")


def test_ogni_blocco_della_pipeline_ha_un_titolo_che_non_e_la_chiave():
    """PRODUCT.md: «una chiave non si stampa mai, si stampa la sua etichetta».
    Il titolo del gruppo stampava la chiave del blocco in maiuscoletto,
    «DOWNSAMPLE» sopra «lato del voxel [mm]». La tabella e' sorvegliata
    contro `STEP_BLOCKS`, che e' l'elenco vero dei blocchi che un pannello
    puo' mostrare: un blocco nuovo senza etichetta tornerebbe chiave.
    """
    from meshrec.core import steps

    riga = _costante("ETICHETTE_DEI_BLOCCHI")
    for numero, blocchi in steps.STEP_BLOCKS.items():
        for blocco in blocchi:
            assert f"{blocco}: " in riga, f"il blocco «{blocco}» dello step {numero} resterebbe una chiave"


def test_riscrivi_porta_la_bozza_a_video_con_o_senza_transizione(tmp_path):
    """Il pannello del dettaglio si costruisce in una bozza e va a video in un
    colpo solo. Dove `document.startViewTransition` c'e', il cambio avviene
    dentro la sua callback e chi chiama aspetta `updateCallbackDone`, cioe'
    il DOM nuovo e non la fine della dissolvenza; dove non c'e', il cambio e'
    immediato e la promessa e' gia' risolta. In entrambi i casi i figli della
    bozza diventano i figli del nodo.

    Mutazione che lo uccide: aspettare `finished` invece di
    `updateCallbackDone`, o chiamare `cambia()` fuori dalla callback.
    """
    _esegui(tmp_path, _DOM + _funzioni("riscrivi") + """
const nodo = document.getElementById("dettaglio");
nodo.append(elemento("p", { textContent: "vecchio" }));
const bozza = elemento("div");
bozza.append(elemento("h3", { textContent: "nuovo" }), elemento("p", { textContent: "corpo" }));

// Senza l'API: sul posto, subito.
await riscrivi(nodo, bozza);
assert.deepEqual(nodo.children.map((n) => n.textContent), ["nuovo", "corpo"]);
// Nel DOM vero i nodi si SPOSTANO e la bozza resta vuota; il DOM finto
// copia i riferimenti e non lo sa, quindi qui non lo si chiede.

// Con l'API: il cambio sta dentro la callback, e si aspetta updateCallbackDone.
let dentro = null;
document.startViewTransition = (cambia) => {
  dentro = nodo.children.map((n) => n.textContent);
  cambia();
  return { updateCallbackDone: Promise.resolve("aggiornato"), finished: new Promise(() => {}) };
};
const bozza2 = elemento("div");
bozza2.append(elemento("p", { textContent: "terzo" }));
await riscrivi(nodo, bozza2);
assert.deepEqual(dentro, ["nuovo", "corpo"], "la callback deve vedere il pannello vecchio ancora a video");
assert.deepEqual(nodo.children.map((n) => n.textContent), ["terzo"]);

// Un'apertura superata nel frattempo non arriva a video: lo decide il
// controllo letto dentro la callback, non l'ordine in cui il motore le esegue.
const bozza3 = elemento("div");
bozza3.append(elemento("p", { textContent: "vecchia bozza" }));
await riscrivi(nodo, bozza3, () => false);
assert.deepEqual(nodo.children.map((n) => n.textContent), ["terzo"], "una bozza superata ha coperto quella piu' recente");
""")


def test_l_attesa_dice_quanti_step_dell_intervallo_sono_conclusi(tmp_path):
    """Su una corsa da piu' step la riga «in corso» diceva solo da dove a dove.
    Il server non sa quale step gira, ma dimentica gli step dell'intervallo
    prima di partire e ognuno torna «valido» quando finisce: il conteggio e'
    un fatto letto dal disco. Su un solo step non si conta niente.

    Mutazione che lo uccide: contare i «valido» di tutta la colonna invece
    che dell'intervallo (lo step 1, valido da ieri, farebbe 1 su 3 all'avvio).
    """
    _esegui(tmp_path, _banco_di_esito() + """
ETICHETTE["01_load"] = "Lettura";
ETICHETTE["03_downsample"] = "Riduzione";
ETICHETTE["05_reconstruct"] = "Superficie";
const barra = document.getElementById("in-corso");
const steps = [
  { numero: 1, chiave: "01_load", stato: "valido" },
  { numero: 3, chiave: "03_downsample", stato: "mai eseguito" },
  { numero: 4, chiave: "04_normals", stato: "mai eseguito" },
  { numero: 5, chiave: "05_reconstruct", stato: "mai eseguito" },
];
aggiornaDaStato({ in_corso: true, step: 3, a_step: 5, steps, da_secondi: 2, annullato: false, exit_code: null });
assert.match(barra.textContent, /0 step su 3 conclusi/, barra.textContent);

steps[1].stato = "valido";
aggiornaDaStato({ in_corso: true, step: 3, a_step: 5, steps, da_secondi: 9, annullato: false, exit_code: null });
assert.match(barra.textContent, /da Riduzione a Superficie in corso, 9 s · 1 step su 3 concluso/, barra.textContent);

// Un solo step: nessun conteggio.
aggiornaDaStato({ in_corso: true, step: 5, a_step: 5, steps, da_secondi: 1, annullato: false, exit_code: null });
assert.ok(!/step su/.test(barra.textContent), barra.textContent);
assert.equal(avanzamentoDellaCorsa({ step: null, a_step: null, steps }), null);
""")


def _banco_del_cartiglio() -> str:
    """Il banco dei comandi con una tela 2D finta che annota ogni scritta:
    testo, posizione e lo stato di font, colore e allineamento al momento
    della chiamata. `immagineDi(larghezza, altezza)` monta l'`Image` finta."""
    return _banco_dei_comandi_della_vista() + """
const scritte = [];
const pennelloFinto = {
  font: "", fillStyle: "", textAlign: "left", textBaseline: "",
  fillRect() {}, drawImage() {},
  measureText: (s) => ({ width: s.length * 8 }),
  fillText(testo, x, y) { scritte.push({ testo, x, y, font: this.font, fillStyle: this.fillStyle, textAlign: this.textAlign }); },
};
const telaFinta = { width: 0, height: 0, getContext: () => pennelloFinto, toDataURL: () => "data:composto" };
const creaPrima = document.createElement;
document.createElement = (tag) => tag === "canvas" ? telaFinta : creaPrima(tag);
const immagineDi = (width, height) => {
  globalThis.Image = class { constructor() { this.width = width; this.height = height; } set src(v) {} decode() { return Promise.resolve(); } };
};
const testi = () => scritte.map((s) => s.testo);
const campi = (quanti) => Array.from({ length: quanti }, (_, k) => [`campo ${k + 1}`, String(k + 1)]);
const scheda = (quanti, resto = {}) => ({
  titolo: "Step 5 · Superficie", meta: ["corsa demo · 10/09/2026", "impronta abcdef012345"],
  conteggi: "453.808 vertici, 891.775 triangoli", didascalia: "scarto RMS 9,5 mm",
  blocchi: [{ nome: "superficie", campi: campi(quanti) }], ...resto,
});
"""


def test_il_png_salvato_porta_il_cartiglio_di_provenienza(tmp_path):
    """«Salva immagine» scriveva la sola tela: in appendice la figura perdeva
    corsa, step, configurazione e caso di carico. La scheda si compone da cio'
    che la pagina mostra gia', e il cartiglio si disegna con una tela 2D dove
    c'e'; dove non c'e' torna la sola cattura, non nessun PNG.

    Il cartiglio sta a destra, largo due quinti dell'immagine, alto quanto lei:
    con 2 campi o con 12 il PNG esce di norma della stessa misura. La
    striscia sotto cresceva con le righe, e sei step della stessa corsa
    uscivano di sei altezze diverse.

    Mutazione che lo uccide: allungare la tela con le righe, perdere
    l'impronta, o scrivere una riga vuota per una didascalia vuota.
    """
    _esegui(tmp_path, _banco_del_cartiglio() + """
const composta = schedaDiProvenienza({
  corsa: "runs/lab_crop", numero: 6, nome: "Riparazione", impronta: "abcdef0123456789",
  conteggi: "453.808 vertici, 891.775 triangoli", blocchi: [{ nome: "riparazione", campi: [["attiva", "no"]] }], didascalia: "", data: "3/9/2026",
});
assert.deepEqual(composta, {
  titolo: "Step 6 · Riparazione",
  meta: ["corsa lab_crop · 3/9/2026", "impronta abcdef012345"],
  conteggi: "453.808 vertici, 891.775 triangoli",
  didascalia: "",
  blocchi: [{ nome: "riparazione", campi: [["attiva", "no"]] }],
});
// Il percorso alla Windows, con la barra rovesciata scritta per codice: in una
// stringa JS `\\p` sarebbe un escape, e sparirebbe. Senza impronta e senza
// blocchi: la meta ha una riga sola, i blocchi sono vuoti.
assert.deepEqual(schedaDiProvenienza({ corsa: "runs" + String.fromCharCode(92) + "pluto", numero: 3, nome: "Riduzione", impronta: undefined, conteggi: "", didascalia: "scarto RMS 9,5 mm", data: "oggi" }),
  { titolo: "Step 3 · Riduzione", meta: ["corsa pluto · oggi"], conteggi: "", didascalia: "scarto RMS 9,5 mm", blocchi: [] });

// Senza Image, o senza una tela 2D: la sola cattura, intatta.
const ImageDelBanco = globalThis.Image;
delete globalThis.Image;
assert.equal(await immagineConProvenienza("data:image/png;base64,AAA", scheda(2)), "data:image/png;base64,AAA");
immagineDi(1824, 1230);
const contestoPrima = telaFinta.getContext;
telaFinta.getContext = () => null;
assert.equal(await immagineConProvenienza("data:image/png;base64,AAA", scheda(2)), "data:image/png;base64,AAA");
telaFinta.getContext = contestoPrima;

// Misure fisse: larga W + W/3, alta H, con 2 campi come con 12.
for (const quanti of [2, 12]) {
  scritte.length = 0;
  assert.equal(await immagineConProvenienza("data:image/png;base64,AAA", scheda(quanti)), "data:composto");
  assert.equal(telaFinta.width, 1824 + 730, `larghezza con ${quanti} campi`);
  assert.equal(telaFinta.height, 1230, `altezza con ${quanti} campi`);
  assert.equal(scritte.filter((s) => s.textAlign === "right").length, quanti, "un valore a destra per campo");
}

// Step «non valido»: nessun blocco, nessuna riga di parametri, stesse misure.
scritte.length = 0;
await immagineConProvenienza("data:image/png;base64,AAA", scheda(0, { meta: ["corsa demo · 10/09/2026"], blocchi: [], conteggi: "", didascalia: "" }));
assert.deepEqual(testi(), ["Step 5 · Superficie", "corsa demo · 10/09/2026", "MeshRec"], testi().join(" | "));
assert.equal(telaFinta.width, 1824 + 730);
assert.equal(telaFinta.height, 1230);
for (const s of scritte) assert.ok(s.testo.trim(), "scritta una riga vuota");

// Un blocco senza campi si disegna col solo nome.
scritte.length = 0;
await immagineConProvenienza("data:image/png;base64,AAA", scheda(0, { blocchi: [{ nome: "riparazione", campi: [] }] }));
assert.ok(testi().includes("riparazione"), testi().join(" | "));
assert.equal(scritte.filter((s) => s.textAlign === "right").length, 0);
""")


def test_il_cartiglio_dice_lo_step_in_figura_e_tace_l_impronta_di_uno_step_non_valido(tmp_path):
    """Due bugie evitate. Sullo step 11 la vista ripiega a monte, e nome del
    file e cartiglio dicono lo step in figura, non quello scelto. Su uno step
    «non valido» l'impronta che arriva e' della configurazione corrente, che
    l'artefatto in figura non ha prodotto: non si scrive.

    Mutazione che lo uccide: `stepScelto` al posto di `passoDaMostrare` nel
    nome del file, o l'impronta scritta senza guardare lo stato.
    """
    _esegui(tmp_path, _banco_dei_comandi_della_vista() + """
ETICHETTE["09_tetrahedralize"] = "Tetraedri";
ETICHETTE["11_export"] = "Esportazione";
ultimoStato = [
  { numero: 9, chiave: "09_tetrahedralize", stato: "non valido", impronta: "0123456789abcdef", artefatto: "09_tets.vtu" },
  { numero: 11, chiave: "11_export", stato: "valido", impronta: "fedcba9876543210", artefatto: "11_deck.inp" },
];
stepScelto = 11;
await salvaImmagine();
assert.equal(scaricato().numero, 9, "il file nomina lo step in figura e non quello scelto");
assert.equal(scaricato().nome, "Tetraedri");

// La scheda: lo step in figura, senza impronta perche' «non valido».
const composta = schedaDiProvenienza({ corsa: "runs/x", numero: 9, nome: "Tetraedri", impronta: undefined, conteggi: "c", didascalia: "", data: "d" });
assert.equal(composta.titolo, "Step 9 · Tetraedri");
assert.deepEqual(composta.meta, ["corsa x · d"]);
""")


def test_i_blocchi_dei_parametri_dicono_un_blocco_per_blocco_dello_step(tmp_path):
    """La figura in appendice deve dire con quali parametri e' stata prodotta,
    predefiniti compresi: chi legge la tesi non ha la configurazione sotto
    mano. Un blocco per blocco, nell'ordine dello schema, con le etichette del
    pannello e non le chiavi, e i campi come coppie etichetta/valore: il
    cartiglio le scrive su due colonne, non in fila.

    Il vuoto e' «non impostato», la stessa parola del report (core/report.py,
    NON_IMPOSTATO): «automatico» era falso per crop_min (nessun ritaglio) e
    expected_size (non misurato). I numeri con la virgola, come #conteggi due
    righe sopra. Il percorso della nuvola solo per nome: il PNG finisce nella
    tesi, non su questa macchina.

    Mutazione che lo uccide: scrivere la chiave al posto dell'etichetta,
    perdere i predefiniti, rendere una lista con String(), o un reale con il
    punto.
    """
    _esegui(tmp_path, _banco_dei_comandi_della_vista() + """
const voce = {
  blocchi: ["surface", "repair"],
  campi: {
    surface: {
      method: { etichetta: "algoritmo di ricostruzione", default: "poisson" },
      depth: { etichetta: "profondità dell'ottree di Poisson", default: 9 },
      voxel_size: { etichetta: "lato della cella più fine [mm]", default: null },
      soglia: { etichetta: "soglia", default: 0.1 },
      pesi: { default: [1, 2, 4] },
    },
    repair: {
      enabled: { etichetta: "attiva", default: true },
      fill_holes: { etichetta: "chiudi i buchi", default: true },
    },
  },
};
const corrente = {
  surface: { method: "poisson", depth: 7, voxel_size: 0, soglia: 0.05, pesi: [1, 2, 4] },
  repair: { enabled: false, fill_holes: null },
};
assert.deepEqual(blocchiDeiParametri(voce, corrente), [
  { nome: "superficie", campi: [
    ["algoritmo di ricostruzione", "poisson"],
    ["profondità dell'ottree di Poisson", "7"],
    ["lato della cella più fine [mm]", "0"],
    ["soglia", "0,05"],
    ["pesi", "[1,2,4]"],
  ] },
  { nome: "riparazione", campi: [["attiva", "no"], ["chiudi i buchi", "non impostato"]] },
]);
// Il percorso della nuvola: il solo nome del file, con la barra di Windows scritta per codice.
const lettura = { blocchi: ["input"], campi: { input: { path: { etichetta: "nuvola" }, crop_min: { etichetta: "ritaglio da", default: null } } } };
assert.deepEqual(blocchiDeiParametri(lettura, { input: { path: "/home/mario/x/lab_frame.pcd", crop_min: null } }),
  [{ nome: "lettura", campi: [["nuvola", "lab_frame.pcd"], ["ritaglio da", "non impostato"]] }]);
assert.deepEqual(blocchiDeiParametri(lettura, { input: { path: "C:" + String.fromCharCode(92) + "dati" + String.fromCharCode(92) + "lab.pcd" } }),
  [{ nome: "lettura", campi: [["nuvola", "lab.pcd"], ["ritaglio da", "non impostato"]] }]);
// Un modello annidato (non lista) in JSON.
assert.deepEqual(blocchiDeiParametri({ blocchi: ["altro"], campi: { altro: { m: {} } } }, { altro: { m: { a: 1 } } }),
  [{ nome: "altro", campi: [["m", "{\\"a\\":1}"]] }]);

// Uno step senza blocchi (il 7): nessun blocco, il cartiglio resta senza parametri.
assert.deepEqual(blocchiDeiParametri({ blocchi: [], campi: {} }, corrente), []);
// Uno step che lo schema non conosce: nessun blocco, nessuna eccezione.
assert.deepEqual(blocchiDeiParametri(undefined, corrente), []);
// Un blocco che lo schema elenca ma senza campi: il solo nome.
assert.deepEqual(blocchiDeiParametri({ blocchi: ["repair"], campi: {} }, corrente), [{ nome: "riparazione", campi: [] }]);
// Un blocco che la corrente non porta: ogni campo vale «non impostato».
assert.deepEqual(blocchiDeiParametri(voce, { surface: corrente.surface }),
  [blocchiDeiParametri(voce, corrente)[0], { nome: "riparazione", campi: [["attiva", "non impostato"], ["chiudi i buchi", "non impostato"]] }]);
// Un blocco che la tabella non conosce resta la chiave, con un campo senza etichetta.
assert.deepEqual(blocchiDeiParametri({ blocchi: ["altro"], campi: { altro: { k: {} } } }, { altro: { k: "v" } }), [{ nome: "altro", campi: [["k", "v"]] }]);
""")


def test_il_png_salvato_porta_i_parametri_dello_step_in_figura(tmp_path):
    """Il cartiglio porta i parametri solo a step «valido», la stessa regola
    dell'impronta: su «non valido» la configurazione corrente non ha prodotto
    la figura, e scriverla accanto sarebbe una bugia. Lo schema si legge una
    volta e resta in memoria come fa apriDettaglio; la configurazione si
    rilegge a ogni salvataggio. Un server che non risponde, o risponde con un
    corpo che non si legge, non produce un file a meta'.

    Mutazione che lo uccide: scrivere i parametri anche su «non valido»,
    rileggere lo schema a ogni salvataggio, o salvare il PNG senza i
    parametri quando /api/config rifiuta.
    """
    _esegui(tmp_path, _banco_del_cartiglio() + """
immagineDi(5000, 800);
const richieste = [];
const fetchBuona = globalThis.fetch;
const bottone = document.getElementById("salva-immagine");
// Durante l'attesa il comando e' spento, e un secondo clic non parte. Lo
// stato si annota e si guarda DOPO: un assert dentro la fetch sarebbe un
// rifiuto per serverMuto, e il banco direbbe rosso per la ragione sbagliata.
let spentoDuranteLAttesa;
globalThis.fetch = async (percorso, opzioni) => {
  richieste.push(percorso);
  if (spentoDuranteLAttesa === undefined) {
    spentoDuranteLAttesa = bottone.disabled;
    await bottone.click();
  }
  return fetchBuona(percorso, opzioni);
};
bottone.addEventListener("click", salvaImmagine);

stepScelto = 6;
// Un errore del salvataggio precedente non resta a video sopra un PNG riuscito.
dichiaraErrore("vecchio errore");
await salvaImmagine();
assert.equal(document.getElementById("errore").textContent, "", "l'errore di prima resta a video sopra un file riuscito");
assert.equal(spentoDuranteLAttesa, true, "il comando e' acceso durante la richiesta");
assert.equal(bottone.disabled, false, "il comando resta spento a salvataggio finito");
assert.equal(consegne.length, 1, "il clic durante l'attesa ha scritto una seconda consegna");
assert.equal(scaricato().dati, "data:composto");
// Lo step del banco non porta impronta: la meta ha la sola riga corsa · data.
assert.deepEqual(testi(), [
  "Step 6 · Riparazione",
  testi()[1],
  "scarto RMS 9,5 mm",
  "riparazione",
  "area massima del buco [mm²]",
  "non impostato",
  "MeshRec",
], testi().join(" | "));
assert.match(testi()[1], /^corsa lab_crop · \d/);
assert.deepEqual(richieste, ["/api/schema", "/api/config", "/api/immagine"]);

// Secondo salvataggio: lo schema e' in memoria, la configurazione si rilegge.
scritte.length = 0;
await salvaImmagine();
assert.deepEqual(richieste, ["/api/schema", "/api/config", "/api/immagine", "/api/config", "/api/immagine"]);
assert.deepEqual(testi().slice(3, 6), ["riparazione", "area massima del buco [mm²]", "non impostato"]);

// Su «non valido» i parametri tacciono, come l'impronta.
scritte.length = 0;
ultimoStato = [{ numero: 6, chiave: "06_repair", stato: "non valido", impronta: "0123456789abcdef" }];
await salvaImmagine();
assert.deepEqual(testi(), ["Step 6 · Riparazione", testi()[1], "scarto RMS 9,5 mm", "MeshRec"], testi().join(" | "));
assert.deepEqual(richieste, ["/api/schema", "/api/config", "/api/immagine", "/api/config", "/api/immagine", "/api/immagine"], "su «non valido» il comando non ha chiesto schema o configurazione al server, ma ha comunque consegnato");

// Uno step «valido» che lo schema non conosce: il file si salva, senza parametri.
scritte.length = 0;
ultimoStato = [{ numero: 9, chiave: "09_tetrahedralize", stato: "valido", impronta: "0123456789abcdef" }];
stepScelto = 9;
await salvaImmagine();
assert.equal(scaricato().numero, 9);
assert.equal(scaricato().nome, "step 9");
assert.deepEqual(testi(), ["Step 9 · step 9", testi()[1], "impronta 0123456789ab", "scarto RMS 9,5 mm", "MeshRec"], testi().join(" | "));
stepScelto = 6;

// Il server rifiuta la configurazione: errore dichiarato, nessun file.
ultimoStato = [{ numero: 6, chiave: "06_repair", stato: "valido", impronta: "0123456789abcdef" }];
const salvatiPrima = consegne.length;
globalThis.fetch = async (percorso, opzioni) => percorso === "/api/config"
  ? { ok: false, status: 500, text: async () => JSON.stringify({ errore: "x", messaggio: "configurazione non leggibile" }) }
  : fetchBuona(percorso, opzioni);
await salvaImmagine();
assert.equal(consegne.length, salvatiPrima, "una consegna con la configurazione rifiutata");
assert.match(document.getElementById("errore").textContent, /^l'immagine non si è potuta salvare: i parametri non si sono letti\\. configurazione non leggibile$/);
assert.equal(bottone.disabled, false, "il comando resta spento dopo un rifiuto");

// Un corpo che non si legge: stesso esito.
globalThis.fetch = async (percorso, opzioni) => percorso === "/api/config"
  ? { ok: true, status: 200, json: async () => { throw new SyntaxError("x"); } }
  : fetchBuona(percorso, opzioni);
await salvaImmagine();
assert.equal(consegne.length, salvatiPrima, "una consegna con un corpo che non si legge");
assert.match(document.getElementById("errore").textContent, /non si legge/);

// Il server non risponde affatto: dichiarato, non sollevato.
globalThis.fetch = async () => { throw new Error("nessun server nel banco"); };
await salvaImmagine();
assert.equal(consegne.length, salvatiPrima);
assert.match(document.getElementById("errore").textContent, /non ha risposto/);
document.createElement = creaPrima;
""")


def test_il_cartiglio_ha_una_gerarchia_e_la_tela_cresce_se_non_basta(tmp_path):
    """Cinque righe dello stesso corpo, peso e colore, con i parametri in fila
    separati da « · », si leggevano male. Il cartiglio ha tre tagli: titolo in
    grassetto e piu' grande, corpo per conteggi ed etichette, piccolo grigio
    per corsa, data, impronta, nomi dei blocchi e la firma. Ogni campo ha
    l'etichetta a sinistra e il valore a destra, con almeno un em fra i due;
    l'etichetta va a capo per parole e il valore chiude la sua ultima riga se
    ci sta, altrimenti scende alla riga dopo. Un valore piu' largo della
    colonna va a sinistra su una riga propria: allineato a destra si sarebbe
    disegnato sopra l'immagine. La firma sta in fondo alla colonna, non sotto
    l'ultimo campo.

    Con una tela bassa e molti campi la colonna non basta: la tela cresce in
    altezza, non taglia.

    Mutazione che lo uccide: un font solo, i valori a sinistra, il valore
    sempre sotto l'etichetta spezzata, la firma subito sotto i parametri, o
    una scritta oltre il fondo della tela.
    """
    _esegui(tmp_path, _banco_del_cartiglio() + """
// 1824 px: colonna 730, corpo 33, titolo 43, piccolo 28, larghezza utile 664
// (83 caratteri da 8 px), distacco etichetta/valore un em, cioe' 33 px.
immagineDi(1824, 1230);
const lunga = "parola ".repeat(12).trim(); // 83 caratteri, 664 px: sta da sola, non con «7,5» a un em.
const spezzata = "vocabolo ".repeat(12).trim(); // 107 caratteri: 9 parole (640 px) e 3 (208): «sì» sta sull'ultima.
const spezzataPiena = "vocabolo ".repeat(18).trim(); // 9 e 9 parole: «no» non sta sull'ultima.
const largo = "x".repeat(90); // 720 px, piu' della colonna: senza spazi non si spezza.
await immagineConProvenienza("data:image/png;base64,AAA", scheda(1, { blocchi: [
  { nome: "superficie", campi: [["soglia", "0,05"], [lunga, "7,5"], [spezzata, "sì"], [spezzataPiena, "no"], ["nuvola", largo]] },
] }));
const [titolo, corsa, impronta] = scritte;
assert.equal(titolo.testo, "Step 5 · Superficie");
assert.match(titolo.font, /^bold 43px /, titolo.font);
assert.equal(titolo.fillStyle, "#1c1b19");
assert.equal(titolo.x, 1824 + 33, "il titolo non parte al margine della colonna");
assert.equal(corsa.testo, "corsa demo · 10/09/2026");
assert.match(corsa.font, /^28px /, corsa.font);
assert.equal(corsa.fillStyle, "#605d58");
assert.equal(impronta.testo, "impronta abcdef012345");
assert.equal(impronta.fillStyle, "#605d58");
assert.ok(corsa.y > titolo.y && impronta.y > corsa.y, "le righe non scendono");

const conteggi = scritte.find((s) => s.testo === "453.808 vertici, 891.775 triangoli");
assert.match(conteggi.font, /^33px /, conteggi.font);
const blocco = scritte.find((s) => s.testo === "superficie");
assert.equal(blocco.fillStyle, "#605d58");
assert.match(blocco.font, /^28px /);

// Un campo che sta: etichetta e valore sulla stessa riga, il valore a destra.
const soglia = scritte.find((s) => s.testo === "soglia");
const valore = scritte.find((s) => s.testo === "0,05");
assert.equal(valore.y, soglia.y, "il valore non e' sulla riga dell'etichetta");
assert.equal(valore.textAlign, "right");
assert.equal(valore.x, 1824 + 730 - 33, "il valore non e' ancorato al margine destro");
assert.equal(soglia.textAlign, "left");
assert.equal(soglia.x, 1824 + 33);

// Un campo che sta da solo ma non col valore a un em: il valore scende.
const etichettaLunga = scritte.find((s) => s.testo === lunga);
const setteEMezzo = scritte.find((s) => s.testo === "7,5");
assert.ok(etichettaLunga, "l'etichetta lunga e' stata spezzata pur stando nella colonna");
assert.ok(setteEMezzo.y > etichettaLunga.y, "il valore non e' sceso alla riga dopo");
assert.equal(setteEMezzo.textAlign, "right");

// Un'etichetta piu' larga della colonna: a capo per parole; il valore chiude
// l'ultima riga se ci sta, altrimenti scende.
const si = scritte.find((s) => s.testo === "sì");
const no = scritte.find((s) => s.testo === "no");
const pezzi = scritte.filter((s) => spezzata.startsWith(s.testo) && s.y > etichettaLunga.y && s.y <= si.y);
assert.equal(pezzi.length, 2, testi().join(" | "));
assert.equal(si.y, pezzi.at(-1).y, "il valore non chiude l'ultima riga dell'etichetta pur stando");
for (const p of pezzi) assert.equal(p.x, 1824 + 33);
const pezziPieni = scritte.filter((s) => spezzataPiena.startsWith(s.testo) && s.y > si.y && s.y < no.y);
assert.equal(pezziPieni.length, 2, testi().join(" | "));
assert.ok(no.y > pezziPieni.at(-1).y, "il valore che non sta e' rimasto sulla riga dell'etichetta");
assert.equal(no.textAlign, "right");

// Un valore piu' largo della colonna: a sinistra, su una riga propria.
const nuvola = scritte.find((s) => s.testo === "nuvola");
const lungo = scritte.find((s) => s.testo === largo);
assert.equal(lungo.x, 1824 + 33, "il valore largo non e' a sinistra: a destra copre l'immagine");
assert.equal(lungo.textAlign, "left");
assert.ok(lungo.y > nuvola.y, "il valore largo non e' su una riga propria");

// La firma: ultima, piccola, grigia, in fondo alla colonna.
const firma = scritte.at(-1);
assert.equal(firma.testo, "MeshRec");
assert.equal(firma.fillStyle, "#605d58");
assert.ok(firma.y >= 1230 - 2 * 33, `la firma sta a ${firma.y}, non in fondo`);
assert.ok(firma.y > lungo.y + 33, "la firma sta subito sotto i parametri");
for (const s of scritte) assert.ok(s.y >= 0 && s.y + 43 <= telaFinta.height, `${s.testo} a ${s.y} esce dalla tela`);

// Straripamento: tela bassa e molti campi, la tela cresce e nulla esce.
scritte.length = 0;
immagineDi(300, 120);
await immagineConProvenienza("data:image/png;base64,AAA", scheda(12));
assert.equal(telaFinta.width, 300 + 120);
assert.ok(telaFinta.height > 120, "la tela non e' cresciuta");
assert.equal(scritte.at(-1).testo, "MeshRec");
assert.ok(scritte.at(-1).y >= telaFinta.height - 2 * 12, "la firma non e' in fondo alla tela cresciuta");
for (const s of scritte) assert.ok(s.y + 16 <= telaFinta.height, `${s.testo} a ${s.y} esce dalla tela alta ${telaFinta.height}`);
""")


def test_uno_schema_che_non_si_legge_non_entra_in_cache(tmp_path):
    """Lo schema si legge una volta per pagina e resta in memoria. Un corpo che
    non si legge non deve restarci: messo in cache, ogni salvataggio dopo
    partirebbe da uno schema nullo e il cartiglio tacerebbe i parametri per
    sempre, senza piu' un errore a dirlo.

    Mutazione che lo uccide: assegnare `schemaParametri` prima di guardare il
    corpo, o dopo l'errore.
    """
    _esegui(tmp_path, _banco_dei_comandi_della_vista() + """
const fetchBuona = globalThis.fetch;
const richieste = [];
globalThis.fetch = async (percorso) => { richieste.push(percorso); return { ok: true, status: 200, json: async () => { throw new SyntaxError("x"); } }; };
stepScelto = 6;
await salvaImmagine();
assert.equal(scaricato(), undefined, "una consegna con uno schema che non si legge");
assert.match(document.getElementById("errore").textContent, /^l'immagine non si è potuta salvare: i parametri non si sono letti\\. il server ha risposto con uno schema che non si legge\\. /);
assert.equal(schemaParametri, null, "lo schema nullo e' entrato in cache");
assert.deepEqual(richieste, ["/api/schema"], "la configurazione e' stata chiesta senza uno schema");
assert.equal(document.getElementById("salva-immagine").disabled, false, "il comando resta spento dopo il rifiuto");

// Il server torna: lo schema si richiede, e il file si salva.
globalThis.fetch = async (percorso, opzioni) => { richieste.push(percorso); return fetchBuona(percorso, opzioni); };
await salvaImmagine();
assert.deepEqual(richieste, ["/api/schema", "/api/schema", "/api/config", "/api/immagine"]);
assert.equal(scaricato().numero, 6);
assert.equal(scaricato().nome, "Riparazione");
""")


def test_lo_step_e_la_tela_si_leggono_prima_dell_attesa(tmp_path):
    """Durante le richieste al server un clic su un'altra riga cambia
    stepScelto e la vista ridisegna: il file deve portare il numero e la tela
    di quando il comando e' partito, non il numero nuovo sopra l'immagine
    vecchia o viceversa.

    Mutazione che lo uccide: catturare la tela o leggere stepScelto dopo un
    `await`.
    """
    _esegui(tmp_path, _banco_dei_comandi_della_vista() + """
ETICHETTE["09_tetrahedralize"] = "Tetraedri";
ultimoStato = [
  { numero: 6, chiave: "06_repair", stato: "valido" },
  { numero: 9, chiave: "09_tetrahedralize", stato: "valido" },
];
const fetchBuona = globalThis.fetch;
globalThis.fetch = async (percorso, opzioni) => {
  // L'utente cambia riga mentre il server risponde.
  stepScelto = 9;
  vista.cattura = () => "data:image/png;base64,ALTRA";
  return fetchBuona(percorso, opzioni);
};
stepScelto = 6;
await salvaImmagine();
assert.equal(scaricato().numero, 6, "il file porta lo step scelto dopo l'attesa");
assert.equal(scaricato().nome, "Riparazione");
assert.equal(scaricato().dati, "data:image/png;base64,AAA", "il file porta la tela catturata dopo l'attesa");

// Il clic sull'altra riga apre una generazione (apriGenerazione nel gestore
// dell'elenco), e il pannello nuovo svuota #errore: un rifiuto del server
// arrivato dopo non si scrive sotto lo step che l'utente sta guardando adesso.
document.getElementById("errore").textContent = "";
globalThis.fetch = async (percorso, opzioni) => {
  generazione += 1;
  return percorso === "/api/config" ? { ok: false, status: 503, text: async () => "fermo" } : fetchBuona(percorso, opzioni);
};
const prima = consegne.length;
await salvaImmagine();
assert.equal(document.getElementById("errore").textContent, "", "il rifiuto e' scritto sotto una generazione superata");
assert.equal(consegne.length, prima, "una consegna e' uscita da un salvataggio rifiutato");
""")


def test_la_frase_di_stato_del_pannello_segue_la_colonna(tmp_path):
    """Modificato un parametro, la colonna diceva «non valido» e il pannello
    aperto diceva ancora «Eseguito con i parametri correnti»: due verita' a
    venti centimetri l'una dall'altra. disegnaStep riscrive la sola frase, e
    solo se e' cambiata.

    Mutazione che lo uccide: togliere il blocco in coda a disegnaStep.
    """
    _esegui(tmp_path, _DOM + _funzioni(*_COLONNA, "disegnaStep") + """
ETICHETTE["03_downsample"] = "Riduzione";
stepAperto = 3;
const dettaglio = document.getElementById("dettaglio");
const riga = elemento("p", { className: "aiuto stato-dello-step", textContent: "vecchia" });
dettaglio.append(riga);
disegnaStep([{ numero: 3, chiave: "03_downsample", stato: "valido" }]);
assert.match(riga.textContent, /parametri correnti/);
disegnaStep([{ numero: 3, chiave: "03_downsample", stato: "non valido" }]);
assert.match(riga.textContent, /parametri diversi/);
// Uno step aperto che lo stato non conosce: la frase non si tocca.
disegnaStep([{ numero: 4, chiave: "04_normals", stato: "valido" }]);
assert.match(riga.textContent, /parametri diversi/);
""")


def test_lo_zoom_della_rotella_e_proporzionale_al_delta_e_non_fisso_per_evento(tmp_path):
    """Il trackpad di un Mac manda decine di eventi `wheel` per gesto, di pochi
    pixel l'uno. Con un fattore fisso per evento (era 1,1) trenta colpetti da
    3 px moltiplicavano il raggio per 17 e la scena spariva; una tacca di mouse
    (deltaY 100) deve valere quanto prima, cioe' 1,1 circa.

    Mutazione che lo uccide: tornare a `evento.deltaY > 0 ? 1.1 : 0.9`.
    """
    uscita = _esegui(tmp_path, "import assert from 'node:assert/strict';\n"
        + _funzioni_viewport("fattoreDiZoom") + """
const tacca = fattoreDiZoom({ deltaY: 100, deltaMode: 0 });
assert.ok(Math.abs(tacca - 1.105) < 0.005, `una tacca di mouse vale ${tacca}`);
let carezza = 1;
for (let k = 0; k < 30; k += 1) carezza *= fattoreDiZoom({ deltaY: 3, deltaMode: 0 });
assert.ok(carezza > 1.05 && carezza < 1.15, `trenta colpetti da 3 px valgono ${carezza}`);
assert.ok(fattoreDiZoom({ deltaY: -100, deltaMode: 0 }) < 1, "il verso negativo avvicina");
assert.ok(Math.abs(fattoreDiZoom({ deltaY: 3, deltaMode: 1 }) - fattoreDiZoom({ deltaY: 48, deltaMode: 0 })) < 1e-9, "una riga vale 16 px");
assert.equal(fattoreDiZoom({ deltaY: 5000, deltaMode: 0 }), fattoreDiZoom({ deltaY: 100, deltaMode: 0 }), "un delta anomalo vale al piu' una tacca");
console.log("ok");
""")
    assert uscita.strip() == "ok"


def test_cmd_vincola_l_asse_x_come_ctrl_e_alt_resta_primo(tmp_path):
    """Su macOS ctrl+clic e' il clic destro: il gesto vincolato a x deve
    rispondere anche a cmd (`metaKey`), e la priorita' alt > ctrl > shift non
    cambia.

    Mutazione che lo uccide: togliere `|| evento.metaKey` da asseDelGesto.
    """
    uscita = _esegui(tmp_path, "import assert from 'node:assert/strict';\n"
        + _funzioni_viewport("asseDelGesto") + """
assert.deepEqual(asseDelGesto({ metaKey: true }), [1, 0, 0]);
assert.deepEqual(asseDelGesto({ ctrlKey: true }), [1, 0, 0]);
assert.deepEqual(asseDelGesto({ metaKey: true, altKey: true }), [0, 0, 1]);
assert.deepEqual(asseDelGesto({ metaKey: true, shiftKey: true }), [1, 0, 0]);
assert.equal(asseDelGesto({}), null);
console.log("ok");
""")
    assert uscita.strip() == "ok"


def test_un_corpo_piu_corto_dei_conteggi_dichiarati_lo_dice_invece_di_appendersi(tmp_path):
    """Il ritaglio del corpo puo' sollevare, e il rigetto non deve sparire.

    `/api/mesh` manda tre code in un corpo solo -- posizioni, indici, normali --
    e il browser le taglia sui conteggi che stanno nelle intestazioni. Se il
    corpo e' piu' corto di quanto quelle promettono, `new Float32Array(buffer,
    offset, lunghezza)` solleva RangeError: verificato nel browser, solleva e
    non restituisce spazzatura, che e' la meta' buona della notizia.

    La meta' cattiva e' dove finisce quel rigetto. `mostraStep` e' asincrona e
    il chiamante la consuma con `.then`: senza un `.catch` il rigetto esce
    dentro una promessa che nessuno guarda, e a video resta «caricamento di
    ...» per sempre, con la geometria dello step di prima sotto. E' lo stesso
    buco che `.catch(serverMuto)` chiude un piano piu' sotto, al livello del
    fetch; scoperto restava cio' che succede DOPO che il corpo e' arrivato.

    Non e' un caso di rete -- quello lo distingue gia' `corpoBinarioLetto`, che
    separa un download interrotto da uno finito -- ma di intestazioni che non
    corrispondono al corpo.

    Mutazione che lo uccide: togliere il `.catch` dalla catena di `mostraStep`.
    """
    modulo = _modulo()
    catena = modulo[modulo.index("mostraStep(mostrato, ordine).then("):]
    catena = catena[: catena.index("\n}")]
    assert ".catch(" in catena, (
        "la catena di mostraStep non ha piu' un `.catch`: un ritaglio che "
        "solleva lascia «caricamento di ...» a video per sempre, dentro una "
        "promessa che nessuno guarda"
    )
    assert "segnalaArtefattoMancante(" in catena, (
        "il `.catch` non dice niente a video: un rigetto silenzioso e un "
        "caricamento appeso sono indistinguibili per chi guarda"
    )


# --------------------------------------------------------------------------
# «Salva tutti gli step»: un giro di scegliStep + salvaImmagine, in ordine.
# --------------------------------------------------------------------------


def _banco_del_giro() -> str:
    """Il banco dei comandi della vista piu' il giro. ricaricaVista e
    apriDettaglio hanno i propri banchi: qui sono finte che registrano l'ordine
    delle richieste e rispondono cio' che il banco decide, step per step.
    `inClic` gira durante l'attesa della geometria: e' la finestra in cui
    l'utente puo' cliccare altrove o guardare i bottoni."""
    return _banco_dei_comandi_della_vista() + _funzioni(
        "apriGenerazione", "nomeDelloStep", "scegliStep", "salvaTuttiGliStep"
    ) + """
const chiesti = [];
const esiti = {};
let inClic = null;
function ricaricaVista(numero, ordine) {
  chiesti.push(numero);
  return (async () => {
    await inClic?.(numero);
    // Come mostraStep: superata, non ha disegnato.
    if (superata(ordine)) return false;
    return esiti[numero] ?? true;
  })();
}
async function apriDettaglio() {}
const salvaTutti = document.getElementById("salva-tutti");
salvaTutti.addEventListener("click", salvaTuttiGliStep);
const salva = document.getElementById("salva-immagine");
const esitoDelGiro = document.getElementById("esito-salvataggio");
// Una corsa arrivata al 6, col 7 che misura e non scolpisce: il registro di
// _RIPIEGO tagliato dove serve a questo giro.
ultimoStato = [
  { numero: 1, chiave: "01_load", artefatto: "01_cloud.ply", stato: "valido" },
  { numero: 2, chiave: "02_segment", artefatto: "02_segmented.ply", stato: "valido" },
  { numero: 3, chiave: "03_downsample", artefatto: "03_downsampled.ply", stato: "valido" },
  { numero: 4, chiave: "04_normals", artefatto: "04_normals.ply", stato: "non valido" },
  { numero: 5, chiave: "05_reconstruct", artefatto: "05_surface.ply", stato: "valido" },
  { numero: 6, chiave: "06_repair", artefatto: "06_repaired.ply", stato: "valido" },
  { numero: 7, chiave: "07_surface_quality", artefatto: null, stato: "valido" },
];
const numeriDeiFile = () => consegne.map((c) => c.numero);
"""


def test_salva_tutti_scarica_un_png_per_step_in_ordine_e_salta_chi_ripiega(tmp_path):
    """Un PNG per ogni step che ha un artefatto proprio, in ordine crescente:
    nessuno ZIP, il browser chiede una volta il consenso a piu' download. Lo
    step 7 ripiega sul 6 (passoDaMostrare) e non entra: sarebbe il PNG del 6
    scritto due volte col numero sbagliato sopra. «Non valido» (il 4) entra: il
    cartiglio tace impronta e parametri da se'. Senza uno step scelto il giro
    parte comunque e alla fine non ripristina niente: resta l'ultimo.

    Durante e dopo, una riga di stato dice che cosa sta partendo e che cosa e'
    partito: chi ascolta sentiva solo #conteggi cambiare sei volte.

    Mutazione che lo uccide: elencare `ultimoStato` senza `passoDaMostrare(n)
    === n`, o senza ordinare.
    """
    _esegui(tmp_path, _banco_del_giro() + """
let esitoDurante = null;
inClic = async () => { esitoDurante ??= esitoDelGiro.textContent; };
await salvaTutti.scatena("click");
assert.equal(esitoDurante, "Salvataggio di 6 immagini in corso…", "durante il giro nessuna riga dice che sta salvando");
assert.equal(esitoDelGiro.textContent, "6 immagini salvate, step 1–6", "a giro finito nessuna riga dice che cosa e' partito");
assert.deepEqual(numeriDeiFile(), [1, 2, 3, 4, 5, 6], "i file non sono uno per step, in ordine");
assert.deepEqual(chiesti, [1, 2, 3, 4, 5, 6], "il giro non ha chiesto gli step nell'ordine dei file");
assert.equal(stepScelto, 6, "senza uno step di partenza il giro ha ripristinato qualcosa");
assert.equal(rigaErrore.textContent, "", "un giro riuscito lascia un errore a video");
assert.equal(salvaTutti.disabled, false, "il tasto del giro resta spento a giro finito");
assert.equal(salva.disabled, false, "«Salva immagine» resta spento a giro finito");
""")


def test_salva_tutti_non_sovrascrive_la_riga_in_corso_a_meta_giro(tmp_path):
    """Dentro il giro «Salva immagine» e' gia' spento quando salvaImmagine gira
    (salvaTuttiGliStep lo spegne prima di partire): la riga "Salvataggio di N
    immagini in corso…" non deve sparire dopo il primo file, sostituita da
    "Salvata in …" — chi ascolta la regione viva perderebbe il conto.

    Mutazione che lo uccide: scrivere sempre "Salvata in ..." in salvaImmagine
    senza guardare se il bottone era gia' spento prima del salvataggio.
    """
    _esegui(tmp_path, _banco_del_giro() + """
let chiamate = 0;
let vistoAMeta = null;
inClic = async () => { chiamate += 1; if (chiamate === 2) vistoAMeta = esitoDelGiro.textContent; };
await salvaTutti.scatena("click");
assert.equal(vistoAMeta, "Salvataggio di 6 immagini in corso…", "la riga «in corso» e' stata sovrascritta a meta' giro");
""")


def test_salva_tutti_torna_allo_step_di_partenza(tmp_path):
    """Il giro cambia lo step a video per catturarlo: finito, l'utente deve
    ritrovare quello che stava guardando, non l'ultimo della pipeline.

    Mutazione che lo uccide: togliere `scegliStep(partenza)` in coda al giro.
    """
    _esegui(tmp_path, _banco_del_giro() + """
stepScelto = 3;
await salvaTutti.scatena("click");
assert.deepEqual(chiesti, [1, 2, 3, 4, 5, 6, 3], "il giro non e' tornato sullo step di partenza");
assert.equal(stepScelto, 3);
assert.equal(numeriDeiFile().length, 6, "il ritorno allo step di partenza ha scritto un file in piu'");
""")


def test_salva_tutti_si_ferma_e_lo_dice_quando_una_geometria_non_arriva(tmp_path):
    """Una geometria che non arriva («vuoto»: l'artefatto non c'e' piu' sul
    disco) ferma il giro: continuare scriverebbe i PNG degli step dopo come se
    quello mancasse per caso, e nessuno guardando la cartella se ne
    accorgerebbe. L'errore nomina lo step colpevole, e va scritto DOPO il
    ritorno allo step di partenza: apriDettaglio svuota #errore a pannello
    aperto, e scritto prima sparirebbe.

    Mutazione che lo uccide: `await salvaImmagine()` senza guardare l'esito.
    """
    _esegui(tmp_path, _banco_del_giro() + """
stepScelto = 2;
esiti[4] = "vuoto";
// Come quello vero (app.js, apriDettaglio): #errore si svuota dopo le attese
// del pannello. Senza questa riga l'errore scritto PRIMA del ritorno passava
// lo stesso, e la mutazione che lo sposta in testa restava verde.
apriDettaglio = async () => { await null; rigaErrore.textContent = ""; };
await salvaTutti.scatena("click");
assert.deepEqual(numeriDeiFile(), [1, 2, 3], "il giro ha scritto file oltre lo step che manca");
assert.deepEqual(chiesti, [1, 2, 3, 4, 2], "il giro non si e' fermato sullo step che manca, o non e' tornato indietro");
assert.match(rigaErrore.textContent, /step 4/, "l'errore non nomina lo step colpevole: " + rigaErrore.textContent);
assert.match(rigaErrore.textContent, /Riesegui lo step e rilancia il salvataggio\./, "l'errore dice cosa e' successo ma non cosa fare");
assert.equal(esitoDelGiro.textContent, "", "sull'errore la riga di stato parla sopra #errore");
assert.equal(stepScelto, 2);
assert.equal(salvaTutti.disabled, false, "il tasto del giro resta spento dopo l'errore");
assert.equal(salva.disabled, false, "«Salva immagine» resta spento dopo l'errore");
""")


def test_salva_tutti_tace_e_si_ferma_se_l_utente_clicca_altrove(tmp_path):
    """Un clic su un'altra riga a meta' giro apre una generazione nuova: il
    giro e' superato come ogni altra tratta, si ferma senza errore -- l'utente
    ha scelto, non e' un guasto -- e senza il file dello step in volo, che
    sarebbe la tela di un altro step. E non torna allo step di partenza:
    tornarci butterebbe via il clic appena fatto.

    Mutazione che lo uccide: togliere `superata(ordine)` dal giro.
    """
    _esegui(tmp_path, _banco_del_giro() + """
stepScelto = 1;
inClic = async (numero) => { if (numero === 3) { stepScelto = 5; apriGenerazione(); } };
await salvaTutti.scatena("click");
assert.deepEqual(numeriDeiFile(), [1, 2], "il giro ha scritto il file dello step in volo, o e' andato avanti");
assert.deepEqual(chiesti, [1, 2, 3], "il giro e' andato avanti dopo il clic dell'utente, o e' tornato indietro");
assert.equal(stepScelto, 5, "il giro ha buttato via il clic dell'utente");
assert.equal(rigaErrore.textContent, "", "il clic dell'utente e' stato dichiarato un errore");
assert.equal(salvaTutti.disabled, false);
""")


def test_salva_tutti_spegne_i_due_comandi_e_non_parte_due_volte(tmp_path):
    """Durante il giro «Salva immagine» e il tasto stesso sono spenti: un
    secondo giro sopra il primo scriverebbe dodici file in un ordine qualunque,
    e un salvataggio singolo a meta' giro un PNG di uno step che nessuno ha
    scelto. Il giro tiene spento il proprio bottone e «Salva immagine»;
    salvaImmagine, che lo spegne e riaccende da se', lo lascia come lo ha
    trovato invece di riaccenderlo fra uno step e l'altro.

    Mutazione che lo uccide: `bottone.disabled = false` secco in coda a
    salvaImmagine, o togliere lo spegnimento in testa al giro.
    """
    _esegui(tmp_path, _banco_del_giro() + """
const spenti = [];
inClic = async () => { spenti.push([salvaTutti.disabled, salva.disabled]); };
const primo = salvaTutti.scatena("click");
await salvaTutti.scatena("click");
await primo;
assert.equal(numeriDeiFile().length, 6, "un secondo clic durante il giro ha fatto partire un secondo giro");
assert.ok(spenti.length === 6 && spenti.every(([giro, singolo]) => giro && singolo),
  "fra uno step e l'altro un comando era acceso: " + JSON.stringify(spenti));
assert.equal(salvaTutti.disabled, false);
assert.equal(salva.disabled, false);
""")


def test_salva_tutti_senza_step_non_scrive_niente_e_riaccende(tmp_path):
    """Una corsa mai partita, o senza uno step disegnabile: nessun file, nessun
    errore, i due comandi riaccesi. Il vuoto non e' un guasto."""
    _esegui(tmp_path, _banco_del_giro() + """
ultimoStato = [];
await salvaTutti.scatena("click");
assert.deepEqual(numeriDeiFile(), [], "senza step il giro ha scritto un file");
ultimoStato = [{ numero: 7, chiave: "07_surface_quality", artefatto: null, stato: "valido" }];
await salvaTutti.scatena("click");
assert.deepEqual(numeriDeiFile(), [], "senza uno step disegnabile il giro ha scritto un file");
assert.deepEqual(chiesti, [], "senza step il giro ha chiesto una geometria");
assert.equal(rigaErrore.textContent, "");
assert.equal(salvaTutti.disabled, false);
assert.equal(salva.disabled, false);
""")


def test_salva_tutti_riaccende_i_due_comandi_anche_se_un_salvataggio_solleva(tmp_path):
    """salvaImmagine si difende da se' dal server e dalla composizione del PNG,
    ma la cattura della tela sta prima del suo `try`: se solleva, il giro cade
    con lei. I due comandi devono riaccendersi comunque, altrimenti un guasto
    lascia «Salva immagine» e «Salva un'immagine per step» morti fino al
    ricarico. E il guasto va a video: prima usciva dal gestore del clic come
    rigetto, senza una riga che lo dicesse.

    Mutazione che lo uccide: togliere il `finally` in coda a salvaTuttiGliStep,
    o il `catch` che porta il messaggio in #errore.
    """
    _esegui(tmp_path, _banco_del_giro() + """
vista.cattura = () => { throw new Error("tela persa"); };
await salvaTutti.scatena("click");
assert.match(rigaErrore.textContent, /tela persa/, "un guasto imprevisto non arriva a video: " + rigaErrore.textContent);
assert.deepEqual(numeriDeiFile(), [], "un salvataggio caduto ha scritto un file");
assert.equal(salvaTutti.disabled, false, "il tasto del giro resta spento dopo un salvataggio caduto");
assert.equal(salva.disabled, false, "«Salva immagine» resta spento dopo un salvataggio caduto");
""")


def test_salva_tutti_si_ferma_se_un_salvataggio_fallisce(tmp_path):
    """salvaImmagine su schema o configurazione rifiutati, o su una tela che
    non si compone, scrive l'errore e torna senza file: il giro proseguiva e lo
    step dopo cancellava il messaggio (apriDettaglio svuota #errore), cosi' un
    PNG mancava dalla cartella senza che niente lo dicesse. Ora salvaImmagine
    risponde `true` solo dopo aver consegnato il file, e il giro si ferma sul
    primo che non lo fa: torna allo step di partenza e riscrive l'errore dopo,
    come per la geometria che non arriva.

    Mutazione che lo uccide: `await salvaImmagine()` senza guardare la risposta,
    o `return` senza `true` in coda a salvaImmagine.
    """
    _esegui(tmp_path, _banco_del_giro() + """
stepScelto = 1;
// La configurazione rifiutata solo allo step 3: gli altri si salvano.
const fetchBuono = globalThis.fetch;
globalThis.fetch = async (percorso, opzioni) => (percorso === "/api/config" && stepScelto === 3)
  ? { ok: false, status: 500, text: async () => JSON.stringify({ messaggio: "configurazione non leggibile" }) }
  : fetchBuono(percorso, opzioni);
apriDettaglio = async () => { await null; rigaErrore.textContent = ""; };
await salvaTutti.scatena("click");
assert.deepEqual(numeriDeiFile(), [1, 2], "il giro e' andato avanti dopo un salvataggio fallito");
assert.deepEqual(chiesti, [1, 2, 3, 1], "il giro non si e' fermato sul salvataggio fallito, o non e' tornato indietro");
assert.match(rigaErrore.textContent, /configurazione non leggibile/, "la ragione del rifiuto non e' a video: " + rigaErrore.textContent);
assert.match(rigaErrore.textContent, /step 3/, "l'errore non nomina lo step colpevole: " + rigaErrore.textContent);
assert.equal(esitoDelGiro.textContent, "", "sull'errore la riga di stato parla sopra #errore");
assert.equal(stepScelto, 1);
assert.equal(salvaTutti.disabled, false);
assert.equal(salva.disabled, false);
""")


def test_salva_tutti_non_parte_sopra_un_salvataggio_singolo_in_volo(tmp_path):
    """«Salva immagine» spento vuol dire un salvataggio singolo in volo: il suo
    `finally` riaccenderebbe il bottone a meta' giro. Il giro non parte, e
    lascia il bottone come lo trova.

    Mutazione che lo uccide: togliere la guardia su `singolo.disabled` in testa
    a salvaTuttiGliStep.
    """
    _esegui(tmp_path, _banco_del_giro() + """
salva.disabled = true;
await salvaTutti.scatena("click");
assert.deepEqual(chiesti, [], "il giro e' partito sopra un salvataggio singolo in volo");
assert.equal(salva.disabled, true, "il giro ha riacceso «Salva immagine» mentre un salvataggio era in volo");
// Mai toccato: nel DOM finto `disabled` nasce undefined, e cosi' resta.
assert.notEqual(salvaTutti.disabled, true, "il giro ha spento il proprio tasto senza partire");
assert.equal(esitoDelGiro.textContent, "");
""")


def test_l_immagine_va_al_server_e_l_esito_dice_il_percorso(tmp_path):
    """Consegna via POST /api/immagine: 200 -> percorso; rifiuto -> dichiaraErrore, null.

    Il mock del 200 risponde con `json:`, non `text:`: `corpoLetto` (app.js)
    legge `risposta.json()`, come ogni altro mock di un 200 in questo file
    (vedi test_corpoLetto_distingue_illeggibile_da_null e i mock di
    /api/schema, /api/config qui sotto). Un mock con solo `text:` fa cadere
    `corpoLetto` sul proprio ramo "illeggibile" (risposta.json non e' una
    funzione), e il test fallirebbe per la ragione sbagliata."""
    sorgente = _DOM + _funzioni("consegnaImmagine", "serverMuto", "ragioneDelRifiuto", "corpoLetto", "dichiaraErrore", "superata") + """
const chiamate = [];
globalThis.fetch = async (url, opzioni) => {
  chiamate.push([url, opzioni]);
  const corpo = JSON.parse(opzioni.body);
  if (corpo.numero === 99) return { ok: false, status: 409, text: async () => JSON.stringify({errore: "NessunaCorsa", messaggio: "nessuna corsa aperta"}) };
  return { ok: true, status: 200, json: async () => ({percorso: "runs/lab/immagini/lab-05-superficie.png"}) };
};
const esito = await consegnaImmagine({ numero: 5, nome: "Superficie", didascalia: "", dati: "data:image/png;base64,AAAA" });
assert.equal(esito.percorso, "runs/lab/immagini/lab-05-superficie.png");
assert.equal(chiamate[0][0], "/api/immagine");
assert.equal(chiamate[0][1].method, "POST");
assert.equal(chiamate[0][1].headers["Content-Type"], "application/json");
const rifiuto = await consegnaImmagine({ numero: 99, nome: "", didascalia: "", dati: "data:image/png;base64,AAAA" });
assert.equal(rifiuto, null);
assert.ok(document.getElementById("errore").textContent.includes("nessuna corsa aperta"));
"""
    _esegui(tmp_path, sorgente)


def test_salva_immagine_non_scarica_piu_dal_browser():
    """La mossa: rimettere `<a download>` riaprirebbe il pannello Salva in pywebview."""
    corpo = _sorgente_di("salvaImmagine", _modulo())
    assert ".download =" not in corpo
    assert "consegnaImmagine(" in corpo


def test_consegna_immagine_col_server_muto_dichiara_e_torna_null(tmp_path):
    """Ingresso degenere: fetch rifiutata (server spento) -> dichiaraErrore col
    messaggio di serverMuto, ritorno null."""
    sorgente = _DOM + _funzioni("consegnaImmagine", "serverMuto", "ragioneDelRifiuto", "corpoLetto", "dichiaraErrore", "superata") + """
globalThis.fetch = async () => { throw new Error("ECONNREFUSED"); };
const esito = await consegnaImmagine({ numero: 1, nome: "", didascalia: "", dati: "data:image/png;base64,AAAA" });
assert.equal(esito, null);
assert.ok(document.getElementById("errore").textContent.includes("il server non ha risposto"), document.getElementById("errore").textContent);
"""
    _esegui(tmp_path, sorgente)


def test_consegna_immagine_su_200_senza_percorso_dichiara_col_rimedio_e_torna_null(tmp_path):
    """Ingresso degenere: 200 senza un campo percorso stringa -> dichiaraErrore
    col RIMEDIO, ritorno null."""
    sorgente = _DOM + _funzioni("consegnaImmagine", "serverMuto", "ragioneDelRifiuto", "corpoLetto", "dichiaraErrore", "superata") + """
globalThis.fetch = async () => ({ ok: true, status: 200, json: async () => ({}) });
const esito = await consegnaImmagine({ numero: 1, nome: "", didascalia: "", dati: "data:image/png;base64,AAAA" });
assert.equal(esito, null);
assert.ok(document.getElementById("errore").textContent.includes(RIMEDIO), document.getElementById("errore").textContent);
"""
    _esegui(tmp_path, sorgente)


def test_consegna_immagine_superata_non_scrive_lerrore(tmp_path):
    """Ingresso degenere: un clic su un altro step durante l'attesa
    (superata(ordine)) -> niente scritto in #errore."""
    sorgente = _DOM + _funzioni("consegnaImmagine", "serverMuto", "ragioneDelRifiuto", "corpoLetto", "dichiaraErrore", "superata") + """
globalThis.fetch = async () => {
  generazione += 1; // un clic altrove ha aperto una nuova generazione durante l'attesa
  return { ok: false, status: 409, text: async () => JSON.stringify({errore: "NessunaCorsa", messaggio: "nessuna corsa aperta"}) };
};
const ordine = generazione;
const esito = await consegnaImmagine({ numero: 1, nome: "", didascalia: "", dati: "data:image/png;base64,AAAA" }, ordine);
assert.equal(esito, null);
assert.equal(document.getElementById("errore").textContent, "", document.getElementById("errore").textContent);
"""
    _esegui(tmp_path, sorgente)


def test_salva_immagine_scrive_lesito_col_percorso_a_200(tmp_path):
    """Ingresso degenere: 200 con percorso -> #esito-salvataggio dice "Salvata
    in <percorso>", salvaImmagine torna true."""
    _esegui(tmp_path, _banco_dei_comandi_della_vista() + """
const fetchBase = globalThis.fetch;
globalThis.fetch = async (percorso, opzioni) => percorso === "/api/immagine"
  ? { ok: true, status: 200, json: async () => ({ percorso: "runs/lab_crop/immagini/lab-crop-06-riparazione.png" }) }
  : fetchBase(percorso, opzioni);
stepScelto = 6;
const esito = await salvaImmagine();
assert.equal(esito, true);
assert.equal(document.getElementById("esito-salvataggio").textContent, "Salvata in runs/lab_crop/immagini/lab-crop-06-riparazione.png");
""")
