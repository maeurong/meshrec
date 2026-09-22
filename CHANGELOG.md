# Changelog

Le versioni di MeshRec, nella forma di [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
con [versionamento semantico](https://semver.org/lang/it/).

## [Unreleased]

### Aggiunto

- Lo step 9 conta le facce autointersecanti prima di TetGen e, se ce ne sono, le fa pulire da
  MeshFix leggendone l'esito. Se ne restano, si ferma dicendo quante e, con lo step 8 acceso,
  che è lui la causa tipica. Con la superficie cambiata, riscrive l'errore geometrico contro la
  nuvola nelle metriche dello step 9.
- `tet.wrap_tolerance` [mm], spento di predefinito: sostituisce la superficie con un alpha wrap
  di CGAL (alpha = tolleranza, offset = alpha/10) e registra lo spostamento fra le due superfici
  (massimo, media, 95° percentile) senza fermare lo step. Su `geoandgeo-mm`, che senza wrap
  si ferma in `recoversubfaces`, a 6,9 mm arriva al deck:
  - le facce autointersecanti passano da 7747 a 22;
  - il volume cresce del 2,9 %;
  - lo spostamento vale 27,8 mm di massimo, 2,8 di media e 9,2 al 95° percentile;
  - TetGen genera 1,59 M elementi C3D10 senza elementi invertiti.

### Modificato

- Il messaggio di TetGen sul guasto in `recoversubfaces` propone `tet.wrap_tolerance`, o di
  abbassarla se il wrap è già acceso.
- Lo step 11 prende come riferimento la superficie degli step 6/8 anche quando lo step 9 l'ha
  pulita o avvolta, così una ripresa dallo step 10 o 11 dà lo stesso deck della corsa intera.
- Le impronte degli step 9-12 delle corse già su disco cambiano una volta: il blocco `tet` ha
  un campo in più.

## [1.0.0] — 2026-09-12

Prima versione: quella discussa in sede di tesi.

### Aggiunto

**Dalla nuvola al deck.** Le fondamenta, costruite prima che il lavoro passasse per le pull
request.

- Pipeline in undici passaggi da nuvola di punti (`.pcd`, `.ply`, `.xyz`) a deck Abaqus `.inp`,
  con i parametri e le misure di qualità di ogni passaggio salvati nella corsa.
- Motore di sweep con registro delle corse, fronte di Pareto e impronta della configurazione.
- Prior geometrico del telaio (step 12) e modelli parametrici della struttura.

**Ingresso, vista e interfaccia degli step.**

- Una corsa si avvia scegliendo il file della nuvola, invece di scrivere a mano un file di
  configurazione (#14).
- La vista ripiega sull'ultimo artefatto disponibile a monte e dichiara a quale passaggio
  appartiene: i cinque passaggi che non producono geometria non svuotano più lo schermo (#16).
- Interfaccia divisa in gruppi: esito dello step, attesa durante l'esecuzione, pannello dei
  parametri e storico (#23).
- Gli script di avvio portano i fine riga che `cmd.exe` e la shell pretendono, e partono su
  entrambi i sistemi (#24).
- Le due estremità del tubo verso il processo di lavoro dichiarano la codifica: su Windows la
  lettura di un file non cade più con `UnicodeDecodeError` (#26).
- La guardia sulla lettura copre anche il file non UTF-8, non solo quello troncato: prima
  l'eccezione saltava al chiamante invece del ripiego dichiarato (#27).
- Applicati sette degli otto tagli dell'audit di semplificazione: 19 file toccati, 277 righe di
  codice e 1,29 MB di librerie di terzi in meno (#28).

**Carichi e analisi integrata.** Lo strato tolto prima della 1.0.0 — vedi «Rimosso».

- Analisi strutturale dell'as-built: solutore integrato, verdetti sul risultato e verifiche di
  norma (#3).
- I carichi si posizionano su selettori geometrici dichiarati nella configurazione, invece che su
  liste di nodi (#13).
- Carichi posizionati e vista continua entrano insieme, al posto di cinque lavorazioni separate
  (#22).
- Carico di pressione sull'as-built: il vettore dichiarato si ripartisce sui nodi del selettore
  per area tributaria, e il registro affianca forza dichiarata e forza effettiva (#81).
- Carichi distribuiti: `OP=NEW` a ogni passo, segno della risultante e guardia sul vincolo (#109).
- La pressione permanente agisce anche nei passi dei carichi distribuiti (#121).
- La sonda sul comportamento di `TRVEC` entra nella documentazione: è un risultato negativo, con
  le prove che lo reggono (#149).

**Validazione e qualità del maglio.**

- Registro delle soglie di verifica, una per grandezza controllata (#49).
- Un valore non finito non passa più per buono: su `NaN` nessun tetraedro veniva marcato come
  invertito e il conteggio usciva a zero (#51).
- Il patch test, nelle due varianti A e B (#52).
- Il tetraedro quadratico C3D10, per la prima volta (#53).
- La mensola confrontata con la teoria delle travi (#54).
- L'ordine delle colonne del file `.frd`, verificato contro CalculiX (#56).
- La tensione sulla mensola, con la divergenza da Benzley dichiarata invece che nascosta (#57).
- NAFEMS FV52 e LE10, i due benchmark di riferimento per i solidi (#58).
- Oracoli indipendenti per le cinque grandezze che il programma stampava senza nulla che le
  contraddicesse (#59).
- L'incertezza sui materiali propagata sul risultato: un 5% di scarto sulla freccia non prova
  nulla se un 20% di incertezza sul modulo elastico può produrne uno identico (#60).
- Lo scaled Jacobian prende il minimo su nove punti — gli otto angoli più il centro — come fa
  Verdict, e due guardie che promettevano un controllo senza farlo ora lo fanno (#61).
- Sesto verdetto sul deck risolto: l'ampiezza dello spostamento (#62).
- Cinque guardie scritte in negativo, quindi false su `NaN`, corrette tutte e cinque (#63).
- La gravità si ripartisce diversamente sul tetraedro quadratico, e il codice ora lo tiene in
  conto (#64).
- La suite gira da sola su Linux e macOS a ogni modifica, e i benchmark non possono sparire in
  silenzio (#65).
- I conteggi discreti non si asseriscono su un maglio generato: dipendono dall'architettura della
  macchina (#67).
- Una sezione senza spessore si dichiara invece di far cadere la corsa: prima una sola regione
  degenere buttava via anche le regioni buone già misurate (#69).
- Lo scarto fra tetraedri lineari C3D4 e quadratici C3D10, misurato sul telaio reale (#70).
- La GCI di Celik et al. (2008) stima l'errore di discretizzazione risolvendo l'ordine osservato
  invece di assumerlo (#72).
- L'errore geometrico guadagna il segno: materia inventata e materia mancante spingono la
  frequenza propria in direzioni opposte, e il solo modulo le confondeva (#74).
- Settimo verdetto: quanta massa i modi estratti catturano (#76).
- Il numero di modi da estrarre lo fissa la norma, non l'operatore (#77).
- I sette documenti di ricerca entrano nel repository: dodici riferimenti in codice e documenti li
  citavano per nome e puntavano nel vuoto (#78).
- Tre documenti dell'interfaccia che esistevano solo fuori dal repository entrano nella
  documentazione (#79).
- Quattro controlli sulla vista 3D che la suite dell'interfaccia non sapeva raggiungere, perché
  vivono dentro una chiusura (#80).
- Il `.gitignore` copre le cartelle di lavoro e `git status` torna vuoto; la descrizione della
  skill di audit delle dipendenze dice quando va usata (#82).
- Tre numeri sbagliati nei documenti di validazione, fra cui il vincolo della faccia superiore di
  NAFEMS LE11, corretto da `u_y = 0` a `u_z = 0` (#104).
- Il cancello di finitezza copre nuvola, vertici e facce e dichiara quanti valori non sono finiti;
  lo scarto porta il segno in chiaro (#105).
- Accenti italiani veri nei tre documenti rimasti in ASCII (#106).
- Il calcolo di convergenza dichiara le uscite degeneri invece di crollare: il punto fisso
  lasciava uscire eccezioni che nessuno intercettava (#107).
- Tre difetti del solutore che producevano numeri plausibili e sbagliati in silenzio: numero di
  passo oltre il nono, file `.frd` troncato, picco sui casi parziali (#108).
- I conteggi della scala rimisurati sul codice vero, e uno script che verifica i riferimenti dei
  documenti (#113).
- `git` con codice d'uscita diverso da zero non è un albero pulito: fuori da un repository ogni
  riga dello sweep registrava come pulito un albero di cui non si sa nulla (#114).
- Risoluzione end-to-end con CalculiX vero su elementi C3D10 (#115).
- I rilievi di codice raccolti nella revisione, fra cui i tre confronti sui nomi di superficie in
  `core/abaqus.py` (#116).
- Il report e il pannello stampano l'etichetta italiana invece della chiave del dizionario: in
  appendice si leggeva `scostamento_nuvola` (#117).
- Due docstring che promettevano più controlli di quanti il file ne esegua, riallineati a ciò che
  guardano davvero (#118).
- Un maglio vuoto è rifiutato anche dall'esportazione del modello, non solo dalla scrittura del
  deck (#122).
- I documenti di validazione citano il simbolo (`quality.mesh_volume`) invece della riga: 43
  riferimenti puntavano a righe che esistevano e dicevano un'altra cosa (#123).
- I tre conteggi della suite pubblicati dalla CI, rimisurati: dove diceva 34 test erano 53 (#126).

**Documenti di progetto, licenza e perimetro.**

- Un `README.md` alla radice dice cos'è MeshRec, perché sostituisce `MeshReconstructorPro`, dove
  guardare e come si avvia (#148).
- `AGENTS.md` avverte che i test non falliscono quando mancano le dipendenze esterne: spariscono,
  e la suite resta verde (#150).
- Licenza MIT: il riuso da parte di altri tesisti e del laboratorio, che `PRODUCT.md` dà per
  confermato, senza un file di licenza era vietato per difetto (#151).
- Terminologia uniformata: il provino è un telaio in cemento armato, il rilievo è fotogrammetrico
  (#152).
- Revisione dei testi di progetto: dicono da dove vengono i requisiti in positivo, senza giudicare
  strumenti di terzi (#153).
- Un test cercava «41» in tutto il documento e cadeva nel minuto `:41`, perché la riga di
  provenienza stampa l'ora: ora cerca nella sola sezione delle metriche (#154).
- La specifica elenca i requisiti da cui il progetto nasce, senza accostare il nome di chi ha
  fornito il programma di partenza all'elenco dei suoi difetti (#155).
- Il perimetro del prodotto si chiude sul deck `.inp`: l'analisi si esegue in Abaqus (#156).
- Il predefinito rispetta il perimetro dichiarato: la corsa si ferma allo step 11 invece che al
  12, e i tre documenti di progetto dicono lo stesso numero di passaggi (#157).
- Tolta una skill di terzi mai usata, e con lei tutte e 144 le segnalazioni di vulnerabilità:
  venivano dai suoi manifest deliberatamente vulnerabili, nessuna dal codice di MeshRec (#158).

**Rifinitura dell'interfaccia.**

- La linea dell'analisi si nasconde dietro un interruttore: l'interfaccia mostra gli undici
  passaggi del perimetro e nient'altro, e il codice resta al suo posto (#160).
- Ctrl+Z annulla anche le esecuzioni, non solo i cambi di parametro; un pannello «Modello» sotto
  la pipeline descrive lo step al fronte con i numeri misurati, e gli step 5, 6 e 8 misurano la
  superficie come già faceva il 7 (#168).
- Etichette e pannello «Modello» escono da `app.js` in moduli propri, 420 righe in meno, e i
  banchi valutano il modulo vero invece di un ritaglio del sorgente (#169).
- Lo stato dello step è spiegato nel punto in cui si decide, e i titoli dei gruppi di parametri
  dicono «riduzione» invece della chiave `DOWNSAMPLE` (#170).
- Titolo dello step a 16 px, registro a 14 px, scorciatoie bilanciate (#172).
- Passata di rifinitura sull'intero percorso: lo stato del pannello aperto si riscrive quando un
  parametro cambia, e un fallimento non chiude più dichiarando «nessun dettaglio» quando il
  dettaglio c'è (#176).
- I gesti della vista 3D adattati al trackpad e a macOS (#177).
- La pagina si adatta a portatili e monitor da PC (#178).
- Il pannello mostra il valore di prima accanto a quello cambiato, invece del solo marchio che
  segnalava il cambiamento (#180).
- Le nuvole si decimano a fine corsa, non al primo clic (#181).
- Le normali le calcola il server, non il browser (#182).
- Spaziatura e gerarchia corrette su misura e non a occhio: il raggruppamento del modulo
  d'ingresso era invertito, e l'aiuto del campo non portava margine (#183).
- La vista 3D risponde al tocco: su un portatile con schermo touch il modello non si girava
  (#184).
- Con tre dita sul vetro non scattava né la pinza né la rotazione, e l'interazione si fermava
  senza dirlo (#185).

**Il deck nudo e la geometria STEP.**

- Due decisioni scritte dopo il colloquio col tutor del 7 settembre — il deck va nudo, il prior
  geometrico scrive la geometria STEP — e il glossario `CONTEXT.md` (#186).
- `meshrec model` scrive, accanto al deck `.inp`, la geometria `modello.step` (AP214) fusa dai
  prismi delle membrature accettate: in Abaqus/CAE il deck resta la mesh, lo STEP è la geometria
  su cui partizionare e assegnare (#191).

**Immagini della corsa e programma da scrivania.**

- La striscia di provenienza sotto l'immagine salvata porta anche i parametri dello step in
  figura, una riga per blocco (#193).
- La camera non si muove più al cambio di step, così le figure in appendice sono sovrapponibili;
  «Inquadra» resta l'unico modo per rifare l'inquadratura (#194).
- Cartiglio a destra nell'immagine salvata (#195).
- Il grafo del repository (4.468 nodi, 7.926 archi) committato in `graphify-out/`, per aprirlo
  senza rifare l'estrazione (#196).
- Specifica e piano per MeshRec come programma, con tre ricerche e 122 fonti catturate in
  `docs/ricerca/` (#197).
- L'immagine salvata la scrive il server in `runs/<corsa>/immagini/`: il download del browser, in
  una finestra propria, apriva un pannello «Salva» ogni volta (#198).
- MeshRec come programma da scrivania: finestra propria, icona, schermata «Informazioni su»,
  `MeshRec.app` per macOS e collegamento per Windows (#199).
- Endpoint `/api/info` e piè di pagina con versione, commit, licenza e come citare (#199).
- `CITATION.cff` alla radice: il software si cita per nome, versione, autore e anno (questa
  versione).

### Rimosso

- Il solutore integrato e le verifiche di norma (2 settembre 2026):
  l'analisi si fa in Abaqus. Escono i sei moduli del solutore, le rotte che li servivano e la
  schermata dell'analisi.
- Carichi e selettori: il deck torna al solo passo di gravità (#190, 8 settembre 2026).
- Il deck `.inp` è nudo, via la sezione di analisi e il pannello del materiale: materiali, carichi
  e selettori si assegnano in Abaqus/CAE (#192, 8 settembre 2026).

[Unreleased]: https://github.com/maeurong/meshrec/compare/v1.0.0...HEAD
[1.0.0]: https://github.com/maeurong/meshrec/releases/tag/v1.0.0
