# fTetWild riscritto in Rust: serve a velocizzare la tetraedrizzazione?

Data: 21/09/2026. Tipo: spike (una risposta, niente codice).
Repo: `/Users/mario/GitHub/Tesi`, `main` a HEAD `53647fd`. Macchina: macOS arm64,
Apple A18 Pro, 6 core (`sysctl hw.ncpu`), 8 GB.
Parte da: `2026-09-21-autointersezioni-e-degeneri.md:417` (pytetwild 0.4.2) e
`:419-426` (1471 s sulla 08 con i predefiniti; con ε = 0,69 mm interrotta dopo 68 min).

Tag: `[V]` fonte primaria letta · `[M]` misurato in sessione, con il comando ·
`[INF]` inferenza · `[NON TROVATO]`.

## 0. Risposta breve

**Un porting in Rust non darebbe una velocità apprezzabile.** fTetWild è già C++
compilato `-O3`, con TBB collegato staticamente. Il tempo se ne va nell'ottimizzazione
della mesh (86 % sulla 08 decimata), e in quell'ottimizzazione il collasso degli
spigoli gira su un solo thread per una scelta dell'algoritmo: la versione parallela
è commentata nel sorgente con un `TODO: remove bug`. Il linguaggio non c'entra. Una
riscrittura costa circa 35-50 mila righe di C++ con le dipendenze, e in Rust
mancano un Delaunay 3D e un controllo d'inviluppo maturi. `[INF]` fondata su §1-§3.

Una leva c'è, ed è misurata. Decimando la 08 al 10 % prima di fTetWild
(1,35 M → 135 k triangoli) il tempo passa da **1471 s a 164 s** (×9), ma l'errore
geometrico massimo peggiora (§4). `[M]`

## 1. Dove va il tempo in fTetWild

### 1.1 Cosa dice l'articolo `[V]`

- fTetWild toglie le costruzioni razionali di TetWild: la mesh resta sempre in
  virgola mobile, e il razionale serve solo a un calcolo raro dell'energia AMIPS,
  con un costo «negligible» (`fonti/ftetwild-paper-html.md:23`, `:218`).
- La preelaborazione (la semplificazione dell'ingresso) è costosa per i
  controlli di contenimento nell'inviluppo, e la sua parallelizzazione dà in media ×4
  su 8 core (`:117`). Il livellamento dei vertici è parallelo, per colorazione di
  grafo (`:207`).
- Senza parallelismo fTetWild è ×4 più veloce di TetWild (80,4 s contro 360 s),
  e con 8 core arriva a 49,8 s di media (`:267`). Sui 4540 modelli di Thingi10k
  riusciti a tutti e quattro i programmi i tempi sono paragonabili a TetGen:
  18,5 s contro 22 s (`:271`).
- Gli autori stessi chiamano «naive» la loro parallelizzazione e la indicano come
  lavoro futuro (`:397`).

### 1.2 Cosa dice il sorgente `[V]`

Commit `d7d99bb` di fTetWild, cioè il sottomodulo di pytetwild v0.4.2
(`git ls-tree v0.4.2 src/fTetWild`) `[M]`:

- TBB è acceso per default: `option(FLOAT_TETWILD_ENABLE_TBB "Enable TBB" ON)` e
  `FLOAT_TETWILD_USE_TBB` (`fonti/ftetwild-cmakelists.md:46`, `:134-136`).
- L'inserimento dei triangoli è un ciclo sequenziale, un triangolo alla volta
  (`fonti/ftetwild-src-triangleinsertion-cpp.md:411`). I `parallel_for` stanno
  solo nelle scansioni sui tetraedri (`:504`, `:1103`, `:2462`).
- Il collasso degli spigoli nell'ottimizzazione è seriale: il blocco TBB porta il
  nome `FLOAT_TETWILD_USE_TBB_bug` ed è commentato,
  `//TODO: remove bug and fix` (`fonti/ftetwild-src-edgecollapsing-cpp.md:215`).
- Dipendenze scaricate da CMake: libigl v2.6.0, Geogram v1.9.6 (Delaunay 3D
  «BDEL» e i predicati PCK), oneTBB v2022.2.0, fast-envelope, CLI11, fmt, spdlog e
  json (`fonti/ftetwild-dependencies-cmake.md:69-70`, `:84-85`, `:121-122`,
  `:182-183`). GMP entra per `Rational.h`.

### 1.3 La wheel pytetwild 0.4.2 `[M]` `[V]`

- Firma nella versione installata (`inspect.signature`, ambiente
  `uv run --no-project --python 3.12 --with pytetwild==0.4.2 --with pyvista`):
  `tetrahedralize(vertices, faces, edge_length_fac=0.05, edge_length_abs=None,
  optimize=True, simplify=True, epsilon=0.001, stop_energy=10.0, coarsen=False,
  num_threads=0, num_opt_iter=80, loglevel=3, quiet=True, vtk_ordering=False,
  disable_filtering=False, bg_vertices=None, bg_tets=None, bg_values=None)`.
  Le impostazioni predefinite effettive sono `quiet=True`, `loglevel=3`: il README
  (`fonti/pytetwild-readme.md:160-163`) dice `loglevel 6`, `quiet False`. `[M]`
- TBB è **dentro** la wheel. `otool -L PyfTetWildWrapper.abi3.so` mostra solo
  `libgmp`, `libc++` e `libSystem`, ma `nm | c++filt` trova i simboli
  `tbb::detail::d1::task_arena_base` & c., e il log stampa `TBB threads 6`. `[M]`
- È compilata con `-O3 -fsigned-char -ffp-contract=off`
  (`fonti/pytetwild-0-4-2-cmakelists.md:46-47`). Il `-ffp-contract=off` è la
  correzione di un blocco su macOS arm64: senza, la FMA rompe i predicati esatti di
  Geogram e `locate_inexact` gira in tondo. È la PR #48, fusa il 16/08/2026 e
  quindi presente nella 0.4.2 (`fonti/pytetwild-pr48.md`). Chi compilasse da sé
  fTetWild su Apple Silicon senza quel flag andrebbe **più piano**, non più veloce. `[V]`

### 1.4 Misura: dove va il tempo `[M]`

Ingresso sintetico autointersecante: tre sfere sovrapposte, 20 880 triangoli
(`scratchpad/tw/run1.py`, una configurazione per processo; wall da `perf_counter`,
CPU da `getrusage`). Fasi lette dal log fTetWild (`quiet=False, loglevel=2`):

| Fase (predefiniti) | 6 thread | 1 thread |
|---|---|---|
| totale | 9,4 s | 16,7 s |
| collasso spigoli (ottimizzazione) | 4,37 s | 4,78 s |
| livellamento vertici | 1,46 s | 5,96 s |
| scambio spigoli | 1,01 s | 1,20 s |
| divisione spigoli | 0,23 s | 0,28 s |
| semplificazione + Delaunay + inserimento | ≈ 2,1 s | ≈ 5,5 s |

La 08 decimata al 10 % (134 755 triangoli, §4), con i predefiniti e 6 thread,
impiega **163,7 s**, di cui 140,3 s di ottimizzazione (86 %). Il collasso da solo
vale 98,5 s (60 %), lo scambio 18,6 s, il livellamento 19,9 s. Semplificazione
12,6 s, inserimento 3,3 s. In media la CPU usa 1,92 core. `[M]`

Il tempo va in operazioni topologiche locali con controlli d'inviluppo, e quelle più
pesanti girano su un thread. È un collo di bottiglia dell'algoritmo e di come è
parallelizzato, non del linguaggio: un collasso seriale in Rust resta seriale. `[INF]`

## 2. Rust: cosa c'è già

Stato letto su crates.io e GitHub il 21/09/2026 `[V]`:

| Crate / repo | Cosa fa | Stato |
|---|---|---|
| `robust` 1.2.0 | predicati adattivi di Shewchuk (orient3d, insphere) | maturo: 24 M download (`fonti/crates-io-robust-json.md`, `fonti/robust-crate-readme.md`) |
| `geogram_predicates` 0.4.0 | port senza dipendenze dei PCK di Geogram, con SOS | giovane, 12,6 k download (`fonti/geogram-predicates-readme.md`) |
| `tritet` 3.2.0 | binding a Triangle e, con la feature `with_tetgen`, a TetGen (C/C++) | licenza AGPL con TetGen (`fonti/tritet-readme.md:35`, `:43`). È TetGen: stessa fragilità sull'ingresso sporco |
| `delaunay` 0.8.2 | Delaunay d-dimensionale, predicati esatti | «Not implemented today: constrained Delaunay» (`fonti/delaunay-crate-readme.md:375`) |
| `rapidmesh` (GitHub, 4 stelle, creato 06/2026) | mesher tetraedrico in Rust puro, CSG esatto, Delaunay ristretto | pensato per FEM elettromagnetico da primitive; non è su crates.io (`fonti/rapidmesh-readme.md`) |
| porting di TetWild/fTetWild | — | **`[NON TROVATO]`**: crates.io `q=tetwild` restituisce 0 risultati (`fonti/crates-io-search-tetwild-json.md`), GitHub `tetwild language:Rust` restituisce 0 (`gh api search/repositories`, `[M]`) |

In Rust ci sono i predicati esatti. Non ci sono un Delaunay 3D dalle prestazioni di
Geogram BDEL, un controllo d'inviluppo esatto come fast-envelope né un winding number
veloce come quello di libigl. `[INF]`

## 3. Costo di un porting contro guadagno

Righe contate con `wc -l` su un clone `--depth 1` al commit `d7d99bb` `[M]`:

- `src/*.{cpp,h,hpp}`: 19 752 righe, di cui `auto_table.cpp` (3158) è una tabella
  di configurazioni di taglio (`CutTable`), non logica; `src/external`: 7775; fast-envelope (commit `520ee04`): 6490.
- Da portare o sostituire, oltre a queste: il Delaunay 3D di Geogram, PCK,
  il winding number e gli AABB di libigl, i razionali GMP.
- Il totale sta sulle **35-50 mila righe** di geometria numerica
  delicata, con in più la verifica di robustezza su Thingi10k. Per una persona
  sono mesi, non settimane. `[INF]`

Guadagno atteso:

- Dal linguaggio, **circa zero**: C++ `-O3` e Rust `--release` producono codice
  della stessa classe, e la wheel non paga né interprete né copie (§1.3). `[INF]`
- Dalla parallelizzazione del collasso e dello scambio, che è lavoro sull'algoritmo e
  si può fare anche in C++. Con la ripartizione della 08 decimata, e se collasso
  più scambio (117 s) scalassero perfettamente su 6 core, il tetto sarebbe
  ≈ 163,7 − 117,1 + 117,1/6 ≈ **66 s (×2,5)**. `[INF]` Il riferimento pubblicato è più
  basso: il toolkit wildmeshing, che reimplementa TetWild con parallelismo
  automatico, ottiene ×3,4 su 8 thread contro la propria versione seriale e smette
  di scalare oltre gli 8 thread (`fonti/wmtk-paper-2022.md:980`, `:933`). Quel
  lavoro si confronta con TetWild, non con fTetWild, e rinuncia al determinismo
  (`:941-942`, `:949`). `[V]`
- Il processore di questa macchina ha 2 core ad alte prestazioni e 4 efficienti:
  anche il ×2,5 è ottimistico. Sul sintetico da 85 k triangoli, passare da 1 a 6
  thread porta 42,4 s a 21,3 s (×2,0). `[M]` `[INF]`

## 4. Leve senza riscrivere, misurate

Sintetico da 20 880 triangoli, una corsa per configurazione, predefiniti = 11,7 s `[M]`:

| Parametro | Wall | Tetraedri | Nota |
|---|---|---|---|
| predefiniti (6 thread) | 11,7 s | 22 176 | 2,15 core medi |
| `num_threads=1` / `2` / `6` | 15,4 / 12,6 / 11,5 s | — | il threading conta ×1,34 |
| `epsilon=2e-3` (inviluppo ×2) | **7,3 s** | 14 379 | scaled Jacobian minimo 0,18 |
| `epsilon=5e-4` (inviluppo /2) | 24,9 s | 42 014 | ×2,1 più lento |
| `edge_length_fac=0.025` | 27,3 s | 58 167 | ×2,3 più lento |
| `edge_length_fac=0.1` | 13,4 s | 19 595 | **non** più veloce |
| `stop_energy=20` / `50` | 11,7 / 10,7 s | — | ≤ 9 %; con 50 il minimo scende a 0,02 |
| `num_opt_iter=20` | 11,0 s | — | nulla |
| `coarsen=True` | 13,1 s | 18 366 | più lento |
| `optimize=False` | **2,9 s** | 61 618 | **inservibile per FEM**: 45 214 tetraedri su 61 550 con scaled Jacobian < 0,1, minimo 0,0 (`qual.py`, `vtk_ordering=True`) |
| ingresso 5 k / 21 k / 85 k triangoli | 6,5 / 11,7 / 21,3 s | — | cresce meno che linearmente |

Qualità: scaled Jacobian VTK con i predefiniti, minimo 0,10 e 1° percentile 0,19. `[M]`

Sulla 08 reale (`meshrec/runs/geoandgeo-mm/08_simplified.ply`, 1 347 554 triangoli,
diagonale 3460,5 mm), decimata al 10 % con `pv.PolyData.decimate(0.9)` (quadrica VTK,
6,1 s), poi `tetrahedralize` con i predefiniti (`scratchpad/tw/real.py`, `real2.py`) `[M]`:

| | 08 intera (`autointersezioni…md:419-422`) | 08 decimata al 10 % |
|---|---|---|
| tempo | 1471 s | **163,7 s** e 157,9 s (due corse) |
| tetraedri | 302 436 | 247 000 |
| volume | 507,69·10⁶ mm³ | 507,63·10⁶ mm³ (−0,07 % sulla 08) |
| bordo→08, media / max | 0,56 / 3,82 mm | 0,43 / **8,08 mm** |
| 08→bordo, media / max | 0,62 / 15,1 mm | 1,11 / **19,05 mm** |
| memoria residente di picco | — | 1,09 GB |

La decimazione da sola sposta la superficie di 0,40 mm in media e 2,71 mm al massimo
(decimata→08), e di 0,68 / 9,89 mm nel verso opposto. L'inviluppo ε si applica
all'ingresso decimato, non alla 08: i due errori si sommano, e il massimo bordo→08
esce da ε = 3,46 mm. Le distanze sono calcolate come distanza implicita VTK dai
vertici, con 200 k vertici campionati per il verso 08→bordo; il metodo della
misura precedente non è verificato come identico. `[M]`

Altre leve, senza misura:

- fTetWild da riga di comando invece della wheel: stesso sorgente (sottomodulo
  `d7d99bb`), stesso `-O3`, stesso TBB. Nessun guadagno atteso. L'opzione
  `--max-threads` (`fonti/ftetwild-readme.md:171`) corrisponde a `num_threads`. `[INF]`
- «TetWild 2», cioè wildmeshing-toolkit: il repo è attivo (ultimo push 19/09/2026),
  ma la sua app TetWild è una reimplementazione di TetWild, non di fTetWild, senza
  wheel PyPI e confrontata solo con TetWild (`fonti/wmtk-readme.md:212-214`,
  `fonti/wmtk-paper-2022.md:941-942`). `[V]` Che sia più veloce di fTetWild sul
  nostro caso resta **`[NON VERIFICATO]`**.
- Un campo di dimensione (`bg_vertices/bg_tets/bg_values`), fitto dove serve e
  largo altrove, riduce i tetraedri e quindi l'ottimizzazione. Non misurato. `[INF]`

## 5. Riferimenti

- **URL** https://arxiv.org/html/1908.03581v2 · [V] (`fonti/ftetwild-paper-html.md`, già catturata)
  **perche' conta qui** è la fonte che dice cosa è costoso e cosa è parallelo nell'algoritmo
  **cosa se ne prende** razionale solo per un'energia AMIPS rara (`:23`, `:218`), preelaborazione costosa per l'inviluppo e ×4 su 8 core (`:117`), tempi paragonabili a TetGen (`:271`), parallelismo «naive» (`:397`)
- **URL** https://raw.githubusercontent.com/wildmeshing/fTetWild/d7d99bb4387a07895b9adce058dc7305f6b6e5ab/src/TriangleInsertion.cpp · [V] (`fonti/ftetwild-src-triangleinsertion-cpp.md`)
  **perche' conta qui** l'inserimento dei triangoli è il cuore «robusto» che uno vorrebbe portare
  **cosa se ne prende** ciclo sequenziale per triangolo (`:411`), `parallel_for` solo nelle scansioni (`:504`, `:1103`, `:2462`)
- **URL** https://raw.githubusercontent.com/wildmeshing/fTetWild/d7d99bb4387a07895b9adce058dc7305f6b6e5ab/src/EdgeCollapsing.cpp · [V] (`fonti/ftetwild-src-edgecollapsing-cpp.md`)
  **perche' conta qui** il collasso è il 60 % del tempo misurato
  **cosa se ne prende** il ramo TBB è disattivato come `_bug` (`:215`): è la leva algoritmica, e vale in qualunque linguaggio
- **URL** https://raw.githubusercontent.com/wildmeshing/fTetWild/d7d99bb4387a07895b9adce058dc7305f6b6e5ab/CMakeLists.txt · [V] (`fonti/ftetwild-cmakelists.md`)
  **perche' conta qui** dice se il parallelismo è acceso nella compilazione
  **cosa se ne prende** `FLOAT_TETWILD_ENABLE_TBB` ON per default (`:46`, `:134-136`)
- **URL** https://raw.githubusercontent.com/wildmeshing/fTetWild/d7d99bb4387a07895b9adce058dc7305f6b6e5ab/cmake/FloatTetwildDependencies.cmake · [V] (`fonti/ftetwild-dependencies-cmake.md`)
  **perche' conta qui** è l'elenco di ciò che un porting dovrebbe sostituire
  **cosa se ne prende** libigl 2.6.0, Geogram 1.9.6, oneTBB 2022.2.0, fast-envelope `520ee04` (`:69-70`, `:84-85`, `:121-122`, `:182-183`)
- **URL** https://raw.githubusercontent.com/pyvista/pytetwild/85c28acd6e1546b7c19b96fd6a5ee5bc2184b176/CMakeLists.txt · [V] (`fonti/pytetwild-0-4-2-cmakelists.md`)
  **perche' conta qui** sono le opzioni di compilazione della wheel che usiamo (tag v0.4.2)
  **cosa se ne prende** `-O3 -fsigned-char -ffp-contract=off` (`:46-47`) e il perché (`:36-45`)
- **URL** https://api.github.com/repos/pyvista/pytetwild/pulls/48 · [V] (`fonti/pytetwild-pr48.md`)
  **perche' conta qui** la stessa macchina (arm64) aveva un blocco che sembrava lentezza
  **cosa se ne prende** senza `-ffp-contract=off` fTetWild su Apple Silicon può impiegare minuti invece di secondi; la 0.4.2 contiene la correzione
- **URL** https://raw.githubusercontent.com/wildmeshing/fTetWild/HEAD/README.md · [V] (`fonti/ftetwild-readme.md`, già catturata)
  **perche' conta qui** sono le opzioni del programma da riga di comando
  **cosa se ne prende** `--max-threads` (`:171`) e `--coarsen` (`:163`), già esposte dalla wheel
- **URL** https://web.uvic.ca/~teseo/profile/publications/toolkit/2022-WildMeshingToolkit.pdf · [V] (`fonti/wmtk-paper-2022.md`, testo estratto con pypdf)
  **perche' conta qui** è l'unico dato pubblicato su quanto rende parallelizzare le operazioni di TetWild
  **cosa se ne prende** ×3,4 su 8 thread, 153 s contro 452 s serial (`:980`), niente guadagno oltre gli 8 thread (`:933`), risultati non deterministici (`:949`)
- **URL** https://raw.githubusercontent.com/wildmeshing/wildmeshing-toolkit/main/README.md · [V] (`fonti/wmtk-readme.md`)
  **perche' conta qui** è il candidato «TetWild 2»
  **cosa se ne prende** l'app TetWild esiste (`:212-214`), ma è in C++, va compilata e non ha wheel
- **URL** https://crates.io/api/v1/crates/robust · [V] (`fonti/crates-io-robust-json.md`, `fonti/robust-crate-readme.md`)
  **perche' conta qui** sono i predicati esatti, il mattone base di un porting
  **cosa se ne prende** esistono e sono maturi: non sono loro il costo
- **URL** https://raw.githubusercontent.com/glennDittmann/geogram_predicates/main/README.md · [V] (`fonti/geogram-predicates-readme.md`, `fonti/crates-io-geogram-predicates-json.md`)
  **perche' conta qui** fTetWild usa i PCK di Geogram
  **cosa se ne prende** esiste un port puro Rust con SOS, versione 0.4.0, giovane
- **URL** https://raw.githubusercontent.com/cpmech/tritet/main/README.md · [V] (`fonti/tritet-readme.md`, `fonti/crates-io-tritet-json.md`)
  **perche' conta qui** è l'unico tetraedratore «da Rust» maturo
  **cosa se ne prende** incapsula TetGen, AGPL (`:35`, `:43`): non risolve le autointersezioni
- **URL** https://raw.githubusercontent.com/acgetchell/delaunay/main/README.md · [V] (`fonti/delaunay-crate-readme.md`, `fonti/crates-io-delaunay-json.md`)
  **perche' conta qui** candidato Delaunay 3D in Rust
  **cosa se ne prende** niente Delaunay vincolato (`:375`), quindi non sostituisce l'inserimento dei triangoli
- **URL** https://raw.githubusercontent.com/milanofthe/rapidmesh/HEAD/README.md · [V] (`fonti/rapidmesh-readme.md`)
  **perche' conta qui** è l'unico mesher tetraedrico in Rust puro con aritmetica esatta trovato
  **cosa se ne prende** nato nel 06/2026, pensato per primitive CAD e FEM elettromagnetico: non è una prova sulle superfici sporche
- **URL** https://crates.io/api/v1/crates?q=tetwild · [V] (`fonti/crates-io-search-tetwild-json.md`)
  **perche' conta qui** dimostra l'assenza di un porting esistente
  **cosa se ne prende** 0 risultati

## 6. Non verificato

- Qualità e distanze della 08 decimata nel verso 08→bordo contate su 200 k vertici campionati, non su tutti; distanza dai vertici, non Hausdorff simmetrica. `[M]` parziale
- Il tempo dell'algoritmo di Wildmeshing-toolkit contro fTetWild sul nostro caso. `[NON VERIFICATO]`
- Decimazioni intermedie (25 %, 50 %) e ε più grande sulla 08: non provate. Per il tetto dei 15 minuti la corsa sulla 08 intera non è stata ripetuta.
- Le corse sono non deterministiche: il numero di vertici cambia da una corsa all'altra con gli stessi parametri (5244 / 5345 / 5346 sul sintetico), come atteso con TBB. `[M]`
