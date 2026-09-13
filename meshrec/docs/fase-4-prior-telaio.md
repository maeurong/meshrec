# Il prior geometrico del telaio, i modelli parametrici e il confronto

Data: 21/08/2026. Chiude la Fase 4, aperta da [`fase-4-materiale.md`](fase-4-materiale.md)
il 18/08/2026.

## 1. Che cosa gira e che cosa no

La corsa madre e' stata eseguita per intero su `lab_frame.pcd` (152 MB), con
`lab_telaio.yaml` cosi' come questo documento lo definisce, in
`runs/lab_telaio_v2/` (config.yaml confrontato campo per campo con
`lab_telaio.yaml`: identico a parte i pochi campi a valore predefinito che il
file scritto a mano non elenca — `input.path` risolto ad assoluto,
`tet.reference_ratio`, e quattro campi di `wall` gia' ai loro default).
**Dodici step su dodici riusciti** (`runs/lab_telaio_v2/steps.json`), in
circa 85 secondi di calcolo totale (somma dei tempi per step nello stesso
file), il piu' lento il 12 (`wall`, 53,25 s) seguito dal 02 (`segment`,
16,62 s).

Verificato anche in questa sessione:

- la suite principale, `uv run pytest tests -q --ignore=tests/feasibility`:
  **555 passati**, 2 avvisi (nessun test rosso, nessun test saltato);
- la suite di fattibilita', `uv run pytest tests/feasibility -m feasibility`:
  **8 passati, 1 saltato** — il saltato e' `test_ftetwild_meshes_a_punched_box`
  (`wildmeshing`), non un test di CalculiX;
- i quattro controlli col solutore vero (`ccx`, versione 2.22, installato in
  `/Users/mario/.local/bin/ccx` — Ruling C), compreso quello sul telaio a
  quattro membrature (§ 7).

**Il modello as-built esiste e passa i controlli di qualita' del volume**
(`runs/lab_telaio_v2/metrics.json`, step `10_volume_quality`/`11_export`):
14.103 nodi, 51.913 tetraedri, **0 invertiti**, volume 217.728.361 mm³
(0,2177 m³), deck `wall_model.inp` da 2,45 MB. L'errore geometrico fra la
superficie ricostruita e la nuvola sorgente (`07_surface_quality.geometric_error`,
direzione mesh-nuvola, quella con cui il confronto legge la fedelta'): RMS
27,54 mm, massimo 135,69 mm, su 10.968 campioni (un vertice per campione della
mesh, non un sottocampionamento).

**Il prior sul telaio vero misura otto regioni e non ne accetta nessuna** —
non un'esecuzione mancata, un esito misurato e negativo. Il dettaglio e' al
§ 3-4. Come conseguenza diretta e verificata di questo esito, i due modelli
parametrici **non possono essere generati**: `uv run meshrec model
lab_telaio.yaml --tipo estruso`, eseguito in questa sessione contro un prior
a zero membrature accettate, solleva

```
ValueError: nessuna membratura da costruire: il prior non ne ha accettata
alcuna. Guarda le regioni scartate e il controllo che le ha respinte, invece
di generare un modello vuoto
```

— l'esatto testo di `hexa.costruisci` (`hexa.py:730-734`), non un errore di
esecuzione: la guardia esiste apposta per non costruire un modello vuoto (§ 9).
Di conseguenza il confronto a tre modelli non esiste: non c'e' un secondo e un
terzo modello con cui confrontare l'as-built. Quello che questo documento
consegna e' un as-built verificato e un prior che, su questa geometria,
dichiara correttamente il proprio limite invece di inventare sei membrature.

Un primo tentativo di corsa, eseguito nella stessa sessione prima di questo,
aveva usato per errore il ritaglio di `lab.yaml` (largo 290 mm, non arriva
alle zapatas) invece di quello misurato al § 8: e' rimasto in `runs/lab_telaio/`
e nel suo seguito `runs/lab_telaio-estruso/`, entrambi con 0 membrature
accettate ma per una ragione diversa (ritaglio che esclude la geometria, non
il soffitto della scomposizione per spessore del § 9). Non sono la corsa che
questo documento descrive e i loro numeri non compaiono altrove in questo
testo. `lab_telaio.yaml` punta ora a `runs/lab_telaio_v2/`, dove il ritaglio
del file e i dati su disco coincidono.

## 2. Perche' la fase ha cambiato nome

Il piano di questa fase si apriva assumendo un muro: «due piani paralleli e
uno spessore». La tavola `MURO 1` (obra 0021, novembre 2021, l'ingegnere firmatario), letta all'apertura della Fase 4 e riportata per intero in
[`fase-4-materiale.md`](fase-4-materiale.md), dice il contrario:
`lab_frame.pcd` e' un **telaio in cemento armato** di sei membrature
prismatiche — due zapatas, una viga inferior, due columnas, una viga
superior — non una parete. La premessa vecchia non era un'ipotesi rimasta
inverificata: e' stata **misurata falsa**, dalla tavola stessa, prima che
qualunque riga di codice della fase venisse scritta. Da qui il prior cambia
oggetto: non piu' "muro", ma "insieme di membrature prismatiche", ciascuna
misurata e controllata per conto proprio (Task 2-3), assemblata in un telaio
di blocchi esaedrici legati da `*TIE` alle giunzioni (Task 7-8).

## 3. Le membrature trovate contro la tavola

La tavola dichiara sei membrature, dati del caso e ripetuti in
`lab_telaio.yaml` come riscontri:

| membratura | sezione nominale [mm] | n. |
|---|---|---|
| Zapata | 700 x 250 | 2 |
| Viga inferior | 250 x 250 | 1 |
| Columna | 172 x 172 | 2 |
| Viga superior | 140 x 175 | 1 |

Volume nominale totale: 0,4777 m³ (477.700.000 mm³).

**Il prior misura otto regioni candidate e non ne accetta nessuna**
(`runs/lab_telaio_v2/12_wall.json`, `regioni_trovate: 8`,
`membrature: []`). I riscontri dichiarati lo dicono da soli, senza bisogno di
commento: `scarto_membrature: -6` (zero accettate contro sei attese),
`scarto_volume: -1.0` (zero volume costruito contro 0,4777 m³ attesi, perche'
nessuna membratura e' stata accettata e quindi nessun volume e' stato
sommato).

Le otto regioni, con i tre controlli intrinseci che le hanno tutte respinte
(§ 4) e il numero di punti di ciascuna:

| regione | punti | parallelismo [°] | copertura | costanza sezione | controlli falliti |
|---|---:|---:|---:|---:|---|
| 0 | 4.215.879 | 0,50 | 1,00 | 1,187 | costanza_sezione |
| 1 | 14.811 | 10,29 | 1,00 | 0,572 | parallelismo, costanza_sezione |
| 2 | 8.059 | 10,49 | 1,00 | 0,782 | parallelismo, costanza_sezione |
| 3 | 3.772 | 0,85 | 1,00 | 0,608 | costanza_sezione |
| 4 | 3.267 | 13,92 | 1,00 | 0,241 | parallelismo, costanza_sezione |
| 5 | 1.351 | 10,87 | 1,00 | 0,197 | parallelismo, costanza_sezione |
| 6 | 2.513 | 0,95 | 1,00 | 0,572 | costanza_sezione |
| 7 | 380 | 6,17 | 1,00 | 0,173 | parallelismo, costanza_sezione |

(soglie: parallelismo 5,0°, copertura_faccia 0,5, costanza_sezione 0,10 —
`lab_telaio.yaml`, blocco `wall`)

*13/09/2026 — parallelismo rimisurato.* I valori precedenti (regione 0 2,29°,
3 5,07°, 4 31,95°, 5 36,14°, 6 1,11°) erano alterati da una cella fantasma al
bordo della griglia del rigonfiamento: la testa della regione cadeva sul bordo
di una riga in piu', che il massimo leggeva senza la faccia (PR #208). Rimisurati
con `wall.scomponi` + `wall.misura` + `wall.controlla` su
`runs/geoandgeo-lab-pr2/02_segmented.ply`, spacing 1,19227, blocco
`wall` di `runs/geoandgeo-lab-pr2/config.yaml` (uguale a `lab_telaio.yaml`): `runs/lab_telaio_v2`, citata sopra, non esiste piu', e i suoi numeri coincidono con questa corsa; il codice precedente riproduce la tabella vecchia cifra per
cifra. Cambia solo il parallelismo: punti, copertura e costanza restano, e la
regione 3 esce dai falliti per parallelismo. Le accettate restano zero.
`12_wall.json` delle corse archiviate porta ancora i valori vecchi finche' lo
step 12 non viene rilanciato.

La regione 0 tiene 4.215.879 punti — il 98,74% dei `punti_dopo: 4.269.608`
di `runs/lab_telaio_v2/12_wall.json` (il pavimento non viene trovato in
questo step, `pavimento_trovato: false`: e' gia' fuori dal ritaglio scelto al
§ 8, non c'e' piu' nulla da togliere qui) — **con un parallelismo ottimo**
(0,50° contro una soglia di 5°): non e' una
regione mal misurata, e' il telaio intero preso per un unico prisma. Lo
spessore mediano che `wall.regioni` misura su questa geometria e' 192,03 mm
(`spessore_mediano` nello stesso file), sostanzialmente lo stesso su tutte le
membrature del pezzo — la ragione per cui la regione 0 non si separa e' al
§ 9.

## 4. I tre controlli intrinseci e il riempimento di sezione

Ogni regione candidata attraversa tre controlli intrinseci prima di diventare
una membratura accettata (`wall.controlla`, soglie in `lab_telaio.yaml` sotto
`wall:`):

- **parallelismo** (`parallelism_deg: 5.0`): angolo fra le due facce opposte
  della regione. Oltre soglia la regione non ha una sezione definita, e una
  sezione media sarebbe priva di senso.
- **copertura_faccia** (`face_coverage: 0.5`): frazione delle celle della
  faccia viste dallo scanner. Una faccia vista da pochi punti produce un piano
  finto — lo stesso difetto gia' misurato su `FACE_FRONT`/`FACE_BACK` in Fase 1
  (`docs/fase-1-debito.md`).
- **costanza_sezione** (`section_dispersion: 0.10`): dispersione relativa
  della sezione lungo l'asse. Oltre soglia la regione non e' un prisma — e' il
  controllo che, nel banco sintetico, scarta la regione a "Π" quando due
  membrature adiacenti condividono la stessa sezione (Ruling F/G).

Accanto ai tre, dal Task 3 (Ruling J, dopo tre giri di correzione descritti al
§ 5), ogni membratura porta un **quarto stato misurato e non scartante**: il
**riempimento di sezione**, a tre valori — `pieno`, `vuoto`,
`non_verificabile` — con la propria affidabilita' (dispersione delle distanze
al vicino piu' prossimo *fra le fette*, non sull'intera regione — Ruling K
respinto, Ruling L confermato). Una membratura con riempimento basso e misura
affidabile non diventa un modello parametrico (guardia nel Task 8); una con
misura non affidabile puo', ma porta l'avviso fino al report e all'interfaccia.
Non e' un quarto controllo che scarta in `wall.py`: `wall.py` per specifica di
prodotto "misura e non costruisce", e lo scarto — quando avviene — e' deciso da
chi costruisce il modello, non da chi misura.

Infine, **chiusura del volume** (`union_tolerance: 0.02`): somma dei volumi
delle membrature accettate contro il volume della loro unione geometrica. Se
differiscono, alle giunzioni un volume viene contato due volte — un errore che
nessuna metrica di qualita' della mesh vedrebbe da sola.

**Sulla geometria vera, i tre controlli intrinseci hanno respinto tutte e
otto le regioni** (tabella al § 3): sempre `costanza_sezione` (valori da
0,173 a 1,187 contro una soglia di 0,10 — nessuna delle otto la rispetta),
`parallelismo` in aggiunta su cinque delle otto (le regioni 0, 3 e 6 lo passano),
`copertura_faccia` mai determinante (1,00 su tutte e otto, ben sopra 0,5).
Nessuna regione ha raggiunto la lista delle accettate, quindi **il
riempimento di sezione non e' stato esercitato da questa corsa**:
`wall.misura` lo calcola per ogni regione, ma il suo stato non viene
serializzato in `12_wall.json` per le regioni scartate — solo per le
membrature accettate — e qui non ce ne sono. La guardia del Ruling J (Task 8)
non ha avuto occasione di intervenire: il rifiuto e' avvenuto tutto a monte,
nei tre controlli intrinseci del Task 3.

La chiusura del volume **passa**, ma in modo degenere: `somma: 0.0`,
`unione: 0.0`, `scarto_relativo: 0.0`, `passato: true` — zero membrature
accettate hanno zero volume da sommare e zero volume in unione, e zero
diviso per un denominatore non nullo non e' mai raggiunto perche' il codice
tratta l'unione nulla come caso limite (`scarto_relativo` resta 0,0 anziche'
dividere per zero — `wall.prior`, `unione > 0.0` come guardia). Non e' un
segnale di qualita' su questa geometria: e' l'assenza di qualcosa da
controllare, e va letto come tale, non come "chiusura del volume verificata".

## 5. I rulings

Trentanove rulings numerati, da A a AM, sono stati presi durante l'esecuzione
di questa fase e registrati per intero in `progress.md` del workspace SDD, che
sparisce alla chiusura della fase. Quelli che seguono sono quelli che cambiano
cosa il programma fa o come va letto il suo risultato; i rulings di processo e
di forma restano fuori. Dove un ruling e' stato poi corretto da uno successivo,
e' riportato l'esito finale con la nota che e' stato corretto.

**Ruling C** — CalculiX 2.22 installato via conda-forge su richiesta esplicita
dell'utente durante il Task 1 (`~/.local/bin/ccx`) — perche' il piano dava
`ccx` per assente e marcava il Task 11 come saltabile, e col solutore presente
quel controllo gira davvero — costo se sbagliato: nessuno sul codice, se
l'ambiente sparisse il Task 11 tornerebbe a saltare com'era gia' previsto.
Commit `7a42c2f`.

**Ruling D** — la completezza di uno sweep non include il prior:
`sweep.REQUIRED_STEPS` e' i soli step fino a `11_export`, non un alias di tutti
gli step — perche' il Task 1 ha esteso `STEP_KEYS` a dodici voci ma `pipeline.run`
scrive fino all'11 fino al Task 9, e ogni candidato sarebbe risultato
incompleto nel mezzo — costo se sbagliato: se uno sweep dovesse un giorno
variare parametri del prior, la sua completezza andrebbe riestesa insieme
all'impronta.

**Ruling J** (sostituisce i Ruling F/G/H/I sullo stesso punto, dopo tre giri
di correzione: la misura del riempimento si spostava dalla lunghezza assiale
alla spaziatura globale alla spaziatura di regione, sempre la stessa forma di
errore un livello piu' in profondita') — il riempimento di sezione smette di
scartare e diventa un esito misurato a tre stati (pieno/vuoto/non
verificabile), con affidabilita' propria; il rifiuto, quando serve, si sposta
da `wall.controlla` (Task 3) a `hexa.costruisci` (Task 8) — perche' `wall.py`
misura e non costruisce, e uno scarto e' una decisione di costruzione — costo
se sbagliato: una regione a "Π" arriva al Task 8 e va rifiutata li'; se quella
guardia mancasse, si costruirebbe un modello su una membratura inventata.

**Ruling K, respinto dal Ruling L** — proponeva un limite sul numero di
campioni per fetta per irrobustire l'affidabilita' del riempimento; il revisore
ha riprodotto i quattro punti della tesi contraria in modo indipendente
(l'asse della regione trasversale al taglio, non assiale; le fette che
leggono 1.0 sono corte non rade; il limite romperebbe il caso obbligatorio
della "Π" uniforme; il caso e' gia' fermato da `costanza_sezione`) — esito
finale: Ruling K respinto con evidenza, Task 3 chiuso con il limite dichiarato
invece che corretto ulteriormente.

**Ruling M** — la corrispondenza fra i numeri di faccia del solutore e le
facce fisiche non puo' essere verificata da un controllo interno, perche' un
controllo interno partirebbe dalla stessa trascrizione che vorrebbe
verificare; serve un controllo risolto da `ccx`, marcato `feasibility` —
perche' per mutazione (scambio S2/S4 sull'esaedro, permutazione completa sul
tetraedro) la suite restava verde prima di questo test — costo se sbagliato:
dipende da `ccx` e salta dove manca, ma resta il test per riga (a) che
protegge dalle regressioni. Vale il § 7.

**Ruling N** — `element_surface` filtra alle sole facce di bordo (stesso
criterio di `boundary_faces`, occorrenza singola) — perche' su una mesh a piu'
elementi una faccia interna condivisa entrerebbe due volte in un `*TIE` o in
un carico laterale — costo se sbagliato: nessuno oggi, nessun chiamante
esisteva ancora.

**Ruling O** — lo Jacobiano scalato non misura lo schiacciamento
dell'elemento: e' invariante di scala per direzione, misura distorsione
angolare. Un esaedro sottile quanto si vuole, se resta rettangolo, vale 1 —
dimostrato schiacciando un cubo da altezza 1.0 a 0.1 e misurando 1.0 esatto su
tutti gli otto angoli — correggeva un'affermazione falsa nel test, nel
docstring e nel nome del test stesso.

**Ruling P** (conseguenza del Ruling O) — la difesa contro gli esaedri troppo
sottili non e' lo Jacobiano scalato, e' il vincolo di almeno tre strati nello
spessore (Task 7) piu' la distribuzione di `element_volume` — costo se
sbagliato: nessuno oggi; se un domani servisse distinguere due mesh con lo
stesso Jacobiano ma spessori diversi, si aggiunge una colonna con il caso
concreto in mano.

**Ruling AD** — nella giunzione fra due membrature, cede (viene tagliato) il
prisma che ha l'asse invaso dall'altro, non quello di sezione minore — trovato
misurando sul telaio sintetico a quattro membrature, dove il criterio
precedente sollevava un errore su una geometria non patologica (un portale
normale) — costo se sbagliato: `hexa.costruisci` solleva su geometrie
legittime invece di costruirle.

**Ruling AE** — la tolleranza di contatto alla giunzione non e' piu' una
costante di modulo, e' una grandezza per giunzione calcolata dal cuneo fra la
faccia di taglio e la faccia di contatto — perche' su qualunque geometria
misurata (non il banco squadrato) il fuori-squadra e' il dato, non il rumore —
costo se sbagliato: la tolleranza vale solo per la coppia gia' accertata dal
taglio, mai come raggio globale.

**Ruling AF → AG → decisione dell'utente → AH** (il limite piu' importante
della fase, § 9): su un telaio reale, meta' delle giunzioni non produceva un
`*TIE` per mancanza di nodi sufficienti sulla zona di contatto stretta, non
per il cuneo (gia' risolto dal Ruling AE). Tre vie possibili: (A) accettare il
vincolo parziale e dichiararlo con un numero; (B) `POSITION TOLERANCE` per
giunzione piu' la regola "tocca" sul lato indipendente; (C) mesh conforme
multiblocco, che farebbe sparire i `*TIE` del tutto ma richiede o un
infittimento locale alle giunzioni o la frammentazione dei volumi in gmsh, con
rischio di perdere gli esaedri. L'utente ha scelto **(B)**, perche' (C) fatta
bene contraddice la mesh omogenea gia' scelta (infittire alle giunzioni
introdurrebbe densita' variabile proprio dove le sollecitazioni sono massime),
e la frammentazione in gmsh rischia il tetraedrico come ripiego — perdere gli
esaedri costerebbe piu' dei nodi non legati, perche' l'intera fase esiste per
avere un modello esaedrico da confrontare con l'as-built tetraedrico. La
tolleranza finale (Ruling AH) e' il solo scostamento da squadra sulla zona di
contatto, **non di piu'**: a 30 mm gli avvisi scenderebbero da 24 a 8, ma quel
guadagno non si prende, perche' a quella scala la tolleranza e' dello stesso
ordine del passo di mesh e legherebbe nodi alla faccia piu' vicina che puo' non
essere quella di contatto vera — un vincolo sbagliato e' peggio di un vincolo
mancante, perche' il mancante lo conta il numero e lo stampa il solutore,
mentre lo sbagliato non lo vede nessuno.

**Ruling AK** — lo scostamento dalla nuvola sorgente (`scostamento_nuvola`) si
calcola nel Task 10 (`pipeline.genera_modello`), dove nodi del modello e
nuvola segmentata sono entrambi a portata, e il Task 12 lo rilegge senza
ricalcolarlo — perche' ricalcolarlo nel confronto avrebbe significato riaprire
gli artefatti della madre per ogni modello, e due punti di calcolo della
stessa grandezza sono due cose da tenere allineate — costo se sbagliato:
nessuno; se un `modello.json` vecchio non porta la chiave, la guardia la
tratta come "non impostato" invece di sollevare.

**Ruling AL** — il rapporto di confronto porta `giunzioni` e `ties`, e
`nodi_dipendenti_legati` e `nodi_dipendenti_totali`, come numeri **distinti e
mai sommati o rapportati**; per l'as-built, che e' monolitico, quelle righe
valgono "non applicabile" — perche' senza quei numeri accanto, il confronto fra
i tre modelli attribuirebbe alla geometria una differenza che viene invece dal
vincolo del `*TIE` (§ 9), esattamente l'errore che l'intero task esiste per
evitare.

**Ruling AM** — l'endpoint `/api/rigonfiamento` restituisce l'aggregato (min,
max, p95) e non promette una mappa per cella, perche' quella mappa vive solo in
memoria dentro `Membratura.rigonfiamento` e non arriva su disco — costo se
sbagliato: se servisse una mappa di colore del rigonfiamento nel viewport,
serve un task che la faccia scrivere da `wall.prior`, oggi non c'e'.

**Ruling AN (Task 15, la fase si chiude con il limite dichiarato invece che
inseguito)** — sulla geometria vera `wall.regioni` non separa il telaio in
sei membrature: le otto regioni misurate collassano nella regione 0 (il
telaio quasi per intero) piu' sette frammenti di bordo, perche' `regioni()`
raggruppa le celle per **spessore quasi costante** (`wall.py:178-203`) e le
sei membrature della tavola condividono uno spessore mediano di 192 mm — non
c'e' discontinuita' di spessore da cui tagliare. Il commento gia' nel codice
da prima di questa corsa (`wall.py:194-203`) proponeva come via
d'aggiornamento la direzione locale di allungamento per cella (PCA
sull'intorno) al posto del solo spessore; e' stata prototipata fuori da
questa sessione documentale (numeri riportati dal coordinatore del task, non
riprodotti in modo indipendente da me in questa sessione) — anisotropia
locale isotropa nell'interno di una sagoma piena a qualunque raggio piccolo,
fino a quando il raggio supera la larghezza della striscia; invertendo la
regola sulle giunzioni si arrivava a poche regioni accettate ma con sezioni
sui 45-50 mm, incompatibili con le sezioni vere (172-250 mm) — cioe' lamine
di superficie, non membrature. La via che regge davvero e' l'**asse mediale
della sagoma** (trasformata di distanza piu' assottigliamento), non prototipata,
un lavoro con un proprio progetto. — Perche' si chiude qui: l'utente ha
scelto di chiudere la fase con il limite dichiarato piuttosto che rincorrere
un secondo tentativo di scomposizione dentro questo task. — Costo se
sbagliato: nessuno per il codice consegnato, che rifiuta correttamente
invece di costruire un modello inventato (§ 9); il costo e' per chi
riprendera' la scomposizione, che ora sa contro cosa confrontarsi invece di
ripetere i due tentativi gia' fatti (spessore, PCA locale).

## 6. Cosa la fase non fa

- **Nessun solutore strutturale** su un modello completo: i controlli col
  solutore in questa fase verificano che il deck sia leggibile e risolvibile
  (§ 7), non producono un'analisi strutturale del telaio reale. Quello e' la
  Fase 5.
- **Nessuna armatura**: ogni modello, incluso l'as-built, e' calcestruzzo
  omogeneo. E' una scelta dell'autore, non una dimenticanza — il dato delle
  barre resta nella tavola. Un telaio in cemento armato modellato senza
  armatura non e' il telaio vero, ed e' dichiarato in ogni corsa
  (`nota_armatura` in `modello.json`).
- **Nessun tamponamento**: solo la struttura portante in cemento armato.
- **Nessuna riscrittura delle corse di riferimento**: `runs/muro/` e
  `runs/lab_crop/` (dove esistono) e `experiments/muro/` ed
  `experiments/lab_crop/` restano quelli che sono, per cio' che sono — il
  telaio sopra le zapatas, non il telaio intero.
- **Nessuna mesh conforme alle giunzioni**: i due modelli parametrici legano
  le membrature con `*TIE`, non con nodi condivisi (§ 5, Ruling AF/AG/AH). La
  mesh conforme multiblocco resta la via d'aggiornamento dichiarata nel
  codice, non imboccata per la ragione gia' scritta al § 5.

## 7. Lo stato del deck

`ccx` (CalculiX, versione 2.22) e' installato su questa macchina, in
`/Users/mario/.local/bin/ccx` (Ruling C). I quattro controlli di
`tests/feasibility/test_calculix.py` **girano e passano**:

- `test_calculix_solves_a_column_under_self_weight` — una colonna incastrata
  sotto peso proprio, accorciamento confrontato con la forma chiusa;
- `test_la_pressione_su_s4_sposta_la_faccia_x_massimo_e_non_un_altra`
  (riga 80) — chiude la meta' "chiusa" del debito di Fase 1 (§ successivo);
- `test_i_tie_del_telaio_a_quattro_membrature_legano_davvero` (riga 139) —
  il telaio sintetico a quattro membrature, unico controllo di questo elenco
  che non dipende dalla stessa geometria che genera cio' che verifica;
- `test_un_prisma_solo_di_mesh_prisma_e_letto_dal_solutore` — l'uscita piu'
  semplice di `hexa.mesh_prisma`, un prisma singolo, risolta da sola.

`8 passati, 1 saltato` in `tests/feasibility` con `-m feasibility`: il saltato
e' `wildmeshing`, non `ccx`. **La formula «il deck esaedrico non e' stato
verificato da alcun solutore su questa macchina» non e' vera su questa
macchina** e non va scritta qui: resta valida solo dove `ccx` non e'
installato, cioe' dove i quattro test sopra vengono saltati invece che
eseguiti. Un controllo saltato non e' un controllo passato, ma un controllo
passato non va raccontato come saltato.

Riproducendo lo scenario del terzo test — quattro membrature, quattro `*TIE`
— in questa sessione (`/tmp/ccx_repro`, stesso banco sintetico di
`tests/test_hexa.py`/`tests/test_wall.py`), `ccx` riporta `tie constraints: 4`
(tutti e quattro registrati), **32.637 equazioni** nel sistema fattorizzato
(riga "number of equations" dello stdout di `ccx`; un numero precedente,
31.674, proposto durante la stesura di questo documento come "misurato" dal
coordinatore del task, non corrispondeva a questa riproduzione — verificato
qui, poi confermato dal coordinatore stesso: quel numero veniva da una misura
del revisore del Task 12, presa **prima** che i giri di correzione 3-6 del
Task 8 cambiassero il criterio di taglio alle giunzioni e le superfici del
`*TIE`, che cambiano la mesh. Era vero allora, falso ora; 32.637 e' il numero
di questa sessione, sullo stesso codice che genera il resto di questo
documento), **79 nodi dipendenti totali sulle quattro superfici `*_D`** (contati sommando
i nodi unici per faccia delle quattro superfici, dai `superfici`/`elementi`
di `hexa.costruisci`) di cui **24 non legati** (`model_WarnNodeMissTiedContact.nam`,
24 righe; conteggio delle righe `*WARNING in gentiedmpc: no tied MPC`
nell'output di `ccx`, anch'esso 24), quindi **55 legati davvero** — gli stessi
numeri della storia misurata nel Ruling AH (61 avvisi prima della correzione,
24 dopo). `ccx` termina con `Job finished`, `returncode 0`.

Per **Abaqus**, il progetto non ha licenza sulla macchina di sviluppo:
`PRODUCT.md` e' esplicito — «il controllo dei dati con Abaqus non e' mai stato
eseguito... nulla deve affermare che il deck sia stato validato da Abaqus».
Nessuna riga di questo documento lo afferma.

## 8. Il ritaglio nuovo

Il ritaglio di `lab.yaml` (`crop_min z=-480`, y da -470 a -180, largo 290 mm)
taglia sopra le zapatas: cattura il telaio ma non la base. Le zapatas
misurano 700 mm in `MURO 1`. Per un ritaglio che scenda al pavimento e
comprenda le zapatas per intero, in questa sessione ho misurato, dalla nuvola
grezza `lab_frame.pcd` (152 MB, letta con `io.load_cloud`), ristretta alla
fascia x gia' valida di `lab.yaml` (1690-4460, che non taglia il telaio):

- **il pavimento**, con un piano RANSAC (`o3d.geometry.PointCloud.segment_plane`,
  soglia 3×spaziatura, sugli stessi punti con z < -350): normale quasi
  verticale (0.0046, -0.0063, 1.0000), 543.427 punti interni, z fra -522,5 e
  -498,5. Il bordo alto del pavimento e' quindi z ≈ -498,5;
- **il bordo visibile delle zapatas**: nella fascia z fra il pavimento e -467
  l'ampiezza in y dei punti (percentili 1-99%) vale 679-687 mm, coerente con
  700 mm nominali; da z=-467 a z=-464 crolla a 217 mm, la transizione alla
  sezione della columna (172 mm nominali). Sotto z=-498 domina il pavimento
  (ampiezza fino a 764 mm, la stessa larghezza vista alla quota del
  pavimento), quindi il pavimento e la base delle zapatas non sono
  distinguibili in quota in questa scansione: la zapata e' visibile solo per
  il tratto sopra il pavimento, non per l'intera altezza nominale di 250 mm,
  presumibilmente perche' il resto e' interrato o coperto dalla soletta di
  laboratorio;
- **estensione y** nella fascia zapata (z fra -498 e -467): da -675,5 a 63,5
  mm (min/max, non percentili). `crop_min[1]`/`crop_max[1]` allargano
  quell'intervallo di 5-7 mm di margine.

Valori scelti per `lab_telaio.yaml`:

```
crop_min: [1690.0, -680.0, -498.0]
crop_max: [4460.0,   70.0, 1230.0]
```

x e `crop_max[2]` restano quelli di `lab.yaml`: la fascia x non taglia il
telaio (verificato: x delle zapatas nella fascia individuata resta fra 1700,5
e 4391,5, dentro i limiti) e z=1230 comprende gia' la sommita'.

Va detto a lettere chiare, come chiede la specifica: **la base del modello non
esiste nel pezzo vero, e' dove abbiamo tagliato.** Lo stesso principio che
`report.py` applica al set `BASE` dell'as-built — «Il set BASE non e' una
faccia del pezzo: e' la quota di taglio scelta dall'operatore. Quella
superficie non esiste nel pezzo vero, e' dove abbiamo tagliato»
(`report.py`, costante `NOTE_NON_GEOMETRICHE`) — vale allo stesso modo per
`crop_min[2]` di questo ritaglio: e' una quota scelta sopra il pavimento
misurato, non una faccia fisica delle zapatas.

## 9. I limiti misurati

**Il soffitto della scomposizione per spessore — il limite che questa corsa
ha trovato, non ipotizzato.** `wall.regioni` raggruppa le celle in membrature
per spessore quasi costante (§ 5, Ruling AN): su un telaio dove le sei
membrature nominali condividono uno spessore mediano di 192 mm, non c'e'
discontinuita' da cui tagliare, e otto regioni misurate collassano in
un'unica regione da 4,2 milioni di punti (99% del pezzo) piu' sette frammenti
di bordo (§ 3). **Il sistema non ha mentito**: ha misurato una dispersione di
sezione di 1,187 contro una soglia di 0,10, ha respinto la regione, e si e'
rifiutato di costruire un modello su un prisma inventato (§ 1, l'errore di
`hexa.costruisci` a fronte di zero membrature accettate). Un programma scritto
con meno cura avrebbe potuto consegnare sei membrature plausibili e
sbagliate; questo dichiara di non averne trovata nessuna, col controllo e il
numero che l'ha respinta. La via d'aggiornamento e' l'asse mediale della
sagoma (trasformata di distanza piu' assottigliamento): la scomposizione per
spessore e la PCA locale sono gia' state provate e scartate (Ruling AN), chi
riprende non deve ripeterle.

**Il soffitto del taglio alle giunzioni.** L'assemblaggio del telaio taglia
(accorcia lungo l'asse) il prisma il cui asse e' invaso dall'altro alla
giunzione (Ruling AD); non e' un'operazione booleana sui solidi. Le mesh delle
due membrature ai lati di una giunzione hanno passo diverso (quello della
propria sezione) e non condividono nodi sull'interfaccia: il `*TIE` lega
quello che riesce, e sul telaio sintetico a quattro membrature 24 nodi
dipendenti su 79 restano non legati anche dopo la correzione geometrica della
tolleranza di contatto (Ruling AE) e la regola "tocca" (Ruling AH — § 5, § 7).
Sulla geometria vera questo limite non e' stato esercitato in questa sessione:
zero membrature accettate (§ 3) significa che `hexa.costruisci` non e' mai
stato invocato su di essa, e non c'e' un `*TIE` reale da misurare finche' la
scomposizione non supera il limite del paragrafo precedente. **Conseguenza da leggere insieme al confronto fra i tre modelli**: un modello
parametrico con giunti parzialmente liberi e' piu' cedevole del vero, e quella
differenza non viene dalla geometria — viene dal vincolo. Per questo il
rapporto di confronto porta `giunzioni`/`ties` e
`nodi_dipendenti_legati`/`nodi_dipendenti_totali` come numeri separati, mai
sommati (Ruling AL), e per questo la mesh conforme multiblocco, valutata e
scartata (§ 5, decisione dell'utente sul Ruling AG), resta la via
d'aggiornamento dichiarata: farla richiederebbe o un infittimento locale alle
giunzioni, che contraddice la mesh omogenea scelta dall'utente, o la
frammentazione dei volumi in gmsh, che rischia di perdere gli esaedri — e
senza esaedri la fase non ha piu' oggetto.

Si e' anche verificato, e scartato, di allargare la `POSITION TOLERANCE` del
`*TIE` a 30 mm: sul telaio sintetico gli avvisi scenderebbero da 24 a 8, ma a
quella scala la tolleranza e' dello stesso ordine del passo di mesh (46-113 mm
sul banco) e della sezione, e il solutore legherebbe un nodo alla faccia
indipendente piu' vicina, che puo' non essere quella di contatto vera. Un
vincolo sbagliato e' peggio di un vincolo mancante: quello mancante lo conta un
numero e lo stampa il solutore, quello sbagliato non lo vede nessuno.

**Il soffitto della ricombinazione di gmsh.** L'ordine canonico dei nodi e
degli elementi prodotti da `hexa.mesh_prisma` e' garantito e verificato per
mutazione (Ruling S: permutando le chiavi del criterio d'ordinamento, il test
cade). Non e' garantito che qualunque combinatoria di contorno sia
ricombinabile in esaedri puri: `Mesh.RecombineAll=1` (non `setRecombine` sulla
sola superficie sorgente, Ruling T) produce esaedri per le sezioni
rettangolari di questo progetto, ma se gmsh non produce elementi di tipo 5
`mesh_prisma` solleva un `RuntimeError` esplicito (`hexa.py:180-184`, testo a
`hexa.py:182`) invece di restituire un prisma a base triangolare in silenzio. Il limite e' dichiarato
dalla guardia, non eliminato da essa.

**La sottostima del rigonfiamento dove le celle sono grandi.** La griglia con
cui `wall.misura` calcola sia la dispersione di sezione sia il rigonfiamento
usa lo stesso `lato_fetta = ptp(asse) / 20` (venti fette lungo l'asse,
`wall.py:441-449`): su una membratura lunga, ogni cella e' ampia, e il
rigonfiamento — il massimo scostamento dalla faccia ideale dentro ciascuna
cella — puo' nascondere un rigonfiamento locale piu' piccolo della cella
stessa. E' un limite strutturale della griglia scelta, dichiarato nel codice
che la calcola; la sua entita' su `lab_frame.pcd` resta non misurabile finche'
il § precedente non e' chiuso — il rigonfiamento si calcola per regione
(`wall.misura`), e sulla geometria vera nessuna regione e' diventata una
membratura accettata (§ 3-4).
