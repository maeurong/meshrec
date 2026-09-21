# Autointersezioni e triangoli degeneri fra la superficie ricostruita e TetGen

**Data:** 2026-09-21 · **Stato:** chiusa · **Repo:** `Tesi`, ramo `main`, HEAD `53647fd`
**Domanda:** alcune superfici ricostruite da MeshRec non arrivano a CalculiX perché
TetGen si ferma nel recupero del bordo (`recoversubfaces`). Come risolvono il
problema «superficie triangolata da ricostruzione → tetraedrizzazione FEM» i
progetti reali, già in produzione? Rilevazione, riparazione, aggiramento, casi
applicati, iterazione.

Tag: `[V]` fonte primaria letta e catturata in `fonti/` · `[M]` misurato in
questa sessione, con comando · `[INF]` inferenza · `[NON TROVATO]`.

Le raccomandazioni in fondo sono raccomandazioni del ricercatore: la scelta sta
a Mario e alla spec.

---

## 0. Risposta breve

1. **Sul caso reale che fallisce (`runs/geoandgeo-mm`) le autointersezioni non
   sono l'unica causa.** La superficie riparata dello step 6 ha **zero**
   autointersezioni per PyMeshLab, per MeshFix e per TetGen stesso (`-d`: «The
   input surface mesh is correct.»), e TetGen fallisce lo stesso in
   `recoversubfaces`. Lo stesso accade dopo che MeshFix ha ripulito la superficie
   dello step 8 fino a zero autointersezioni (convergenza dichiarata). Il guasto
   residuo è un limite di robustezza di TetGen su geometria quasi degenere. `[M]`
2. **Lo step 8 le autointersezioni le crea**: il remeshing isotropo di PyMeshLab
   ne introduce 646 facce, le due passate di Taubin le portano a 7747. `[M]`
3. **Due strade hanno portato la stessa superficie fino ai tetraedri**: l'alpha
   wrap di CGAL (già dentro `pymeshlab`, installato) e fTetWild (`pytetwild`,
   wheel per macOS arm64 e Windows). Entrambe **sostituiscono** la superficie
   invece di ripararla, e lo spostamento geometrico va misurato e dichiarato. `[M]`
4. I progetti in produzione fanno una di due cose: **riparano dopo l'ultima
   trasformazione e subito prima del tetraedratore** (iso2mesh: ricampiona →
   MeshFix → TetGen; SimNIBS: marching cubes → MeshFix) oppure **non passano
   dalla superficie** (fTetWild, alpha wrap, CGAL Mesh_3 da immagine in SimNIBS
   `charm`, voxel in Cloud2FEM). `[V]`

---

## 1. Artefatti consultati e premesse del brief

### 1.1 Codice (letto in questa sessione, HEAD `53647fd`)

| Premessa del brief | Esito | Riga |
|---|---|---|
| Pipeline 06 → 07 → 08 → 09 | **Confermata** | `meshrec/src/meshrec/core/steps.py:30-43` |
| Degeneri tolti solo se combinatori (indici uguali) | **Confermata** per il codice di MeshRec | `core/repair.py:107` |
| Poi `pymeshfix.MeshFix.repair(joincomp=...)` | **Confermata**, riga 164 (non 162-163) | `core/repair.py:163-164` |
| «Nessuna rimozione di degeneri geometrici né verifica di autointersezioni dopo» | **Da correggere in parte.** `MeshFix.repair()` chiama `clean()`, che toglie i triangoli *esattamente* degeneri (collineari) e le autointersezioni in un ciclo con tetto; MeshRec però **scarta il valore di ritorno** di quel ciclo, quindi la verifica manca davvero. Aghi e cappe non collineari restano. | `fonti/pymeshfix-meshfix-py.md:426-431`, `fonti/meshfix-checkandrepair-cpp.md:1033-1056` |
| Step 8: che cosa fa | Remeshing isotropo `meshing_isotropic_explicit_remeshing` (PyMeshLab) e poi, se `taubin_iterations > 0`, smoothing di Taubin di Open3D. **Spento per predefinito**, Taubin predefinito 0. | `core/surface.py:113-153`, `core/config.py:259-272` |
| Step 8 può reintrodurre autointersezioni | **Confermata e misurata** (§2) | — |
| `_diagnosi_del_guasto` riconosce `recoversubface` e rimanda «a monte, negli step 6 e 8» | **Confermata** | `core/volume.py:68-121` (ramo a 99-106) |
| Extra opzionale `wildmeshing` in `pyproject.toml` | **Falsa, marginale.** L'unico extra è `feasibility = []`; `wildmeshing` compare solo nella prova `tests/feasibility/test_wildmeshing.py` via `importorskip` | `meshrec/pyproject.toml:31-32`, `tests/feasibility/test_wildmeshing.py:1-30` |

Una premessa non scritta nel brief ma che pesa sulla scelta: **l'errore
geometrico si misura allo step 7, prima dello step 8**
(`core/pipeline.py:757-761`). Qualunque trasformazione che venga dopo la 7 — la
semplificazione di oggi, o un wrap/riparazione domani — sposta la superficie
senza che il registro lo misuri. `[V]`

### 1.2 Versioni installate `[M]`

Comando: `uv run --directory /Users/mario/GitHub/Tesi/meshrec python -c "import importlib.metadata as m; ..."`,
macOS 27.0 arm64, Python 3.12.13.

`pymeshlab 2025.7.post1` · `pymeshfix 0.18.1` · `tetgen 0.8.4` · `gmsh 4.15.2` ·
`open3d 0.19.0` · `meshio 5.3.5` · `scipy 1.18.0` · `numpy 2.5.2`.
**Non installati:** `trimesh`, `pyvista`.

### 1.3 Caso reale usato per le misure

`meshrec/runs/geoandgeo-mm/` (corsa del 07/09/2026): `steps.json` registra
`09_tetrahedralize: fallito`; `run-2-12.log` riporta
`RefinementFailedError: ... Internal TetGen error within `recoversubfaces``.
Configurazione della corsa (`config.yaml`): `simplify.enabled: true`,
`remesh_target_len_pct: 1.0`, `taubin_iterations: 2`, `tet.min_ratio: 1.8`,
`nobisect: false`, `max_steiner_points: -1`. Riquadro della superficie
2730 × 743 × 1993 mm, diagonale 3460,5 mm.

Termine di confronto riuscito: `runs/geoandgeo-lab/06_repaired.ply`
(21 932 triangoli, arrivato allo step 9).

Tutte le sonde girano sui file PLY della corsa; nessun file del repo è stato
modificato. Gli script stanno fuori dal repo (scratchpad di sessione).

---

## 2. Misure sul caso che fallisce `[M]`

Comando base (scratchpad): `uv run --directory /Users/mario/GitHub/Tesi/meshrec python sonda_reale.py <ply>`
per i conteggi; `sonda2.py` / `sonda3.py` per riparazioni e TetGen. TetGen
chiamato come in `core/volume.py:176-193` ma con `quality=False` dove indicato
(il recupero del bordo precede il raffinamento, quindi il vincolo di qualità non
cambia l'esito del recupero).

### 2.1 Conteggi

| Superficie | Triangoli | Autointersezioni PyMeshLab (facce) | MeshFix `select_intersecting_triangles` | Spigoli con normali a > 179° (pieghe) | Triangoli con angolo minimo < 0,1° | TetGen |
|---|---|---|---|---|---|---|
| `geoandgeo-lab/06` (riuscita) | 21 932 | 0 | 0 | 2 | 8 | riuscito (corsa originale) |
| `geoandgeo-mm/06_repaired` | 3 845 456 | **0** | **0** | 89 | 2 958 | **`recoversubfaces`** (665 s, `quality=False`) |
| 06 → solo remeshing 1 % | 1 347 554 | 646 | — | 122 | 964 | `recoversubfaces` (1165 s) |
| 06 → remeshing + Taubin 2 (= `08_simplified`) | 1 347 554 | **7 747** | 7 754 | 197 | 2 221 | `recoversubfaces` (27 s) |
| 06 → remeshing 1 % con `checksurfdist=True, maxsurfdist=0,05 %` | 1 372 372 | 141 | — | — | — | non provato |
| 06 → PyMeshLab `remove_t_vertices` + `remove_folded_faces` + `repair_non_manifold_*` | 3 778 558 | 98 | — | 163 | **0** | — |
| … → poi MeshFix `fill_small_boundaries` + `clean(10,3)` | 3 777 140 | **0** (ritorno `True`); volume +0,0003 %; distanza 06→uscita media 0,001 / max 11,06 mm | — | 41 | 0 | **`recoversubfaces`** (473 s) |
| `08` → MeshFix `clean(10,3)` | 1 335 968 | **0** (ritorno `True`) | — | 66 | 1 925 | **`recoversubfaces`** (1034 s) |
| `08` → libigl `remesh_self_intersections` + `outer_hull` | 1 366 052 | 580, non manifold | — | — | — | `recoversubfaces` (1107 s) |
| `08` → **alpha wrap** α = 0,5 %, offset 0,05 % | 54 140 | 0 | — | — | — | **riuscito**, 90 991 tetraedri (plc) |
| `08` → **alpha wrap** α = 0,2 %, offset 0,02 % | 369 278 | 30 | — | — | — | **riuscito**, 1 578 763 tetraedri con `minratio=1.8` (144 s) |
| `08` → **fTetWild** (`pytetwild`, predefiniti) | — | — | — | — | — | **riuscito**, 302 436 tetraedri (1471 s) |

Nessun triangolo ha area esattamente nulla in nessuna delle superfici misurate.

### 2.2 Che cosa dicono i numeri

- **Lo step 8 crea autointersezioni**, e la parte grossa la fa Taubin: 646 facce
  dopo il remeshing, 7747 dopo due passate di Taubin sulla stessa uscita. Taubin
  sposta i vertici senza controllare le collisioni; il remeshing di PyMeshLab ha
  il controllo di distanza dalla superficie (`checksurfdist`), che nella
  versione installata è **spento per predefinito** (vedi §3.1), e acceso lo
  riduce a 141 ma non a zero. `[M]`
- **Togliere le autointersezioni non basta su questo caso.** La 06 non ne ha, la
  08 ripulita da MeshFix non ne ha, e TetGen fallisce su tutte e due nello stesso
  punto. Il messaggio di `_diagnosi_del_guasto` («la causa tipica sono le
  autointersezioni») è quindi incompleto su questa superficie. `[M]`
- **TetGen stesso dà la 06 per valida.** Con `-d` (`diagnose=True`, 2710 s) sulla
  06 TetGen stampa «The input surface mesh is correct.», recupera tutte le
  3 845 456 sottofacce (0 mancanti) e segnala solo due «Two line segments are
  nearly overlapping», alzando la tolleranza di collinearità da 179,9° a 180°. `[M]`
  Sulla 08, invece, `-d` riporta 3736 «A segment and a facet intersect», 2 «Two
  facets exactly intersect» e 1 «Two line segments are almost crossing» (411 s). `[M]`
- `[INF]` Quindi sulla 06 il fallimento non è un ingresso invalido ma un **limite
  di robustezza del recupero del bordo di TetGen** davanti a configurazioni quasi
  degeneri: segmenti quasi sovrapposti, pieghe (spigoli fra facce a normali
  quasi opposte: 89 sulla 06 contro 2 sulla superficie riuscita), aghi (2958
  triangoli con angolo < 0,1° contro 8). È la stessa classe di guasto che
  l'articolo di fTetWild conta come «Algorithm limitation» nel 48,70 % dei
  modelli di Thingi10k (§5.2). Non ho isolato il singolo difetto responsabile.
- **Anche togliendo aghi e cappe il guasto resta.** La catena PyMeshLab
  (T-vertici per collasso di spigolo, pieghe isolate, non-manifold) porta i
  triangoli con angolo < 0,1° da 2958 a 0, crea 98 autointersezioni che MeshFix
  poi toglie, con volume invariato (+0,0003 %) — e TetGen fallisce ancora in
  `recoversubfaces`. Restano 41 pieghe a > 179°. `[M]`
- **Tutte le riparazioni locali provate falliscono; le due strade che non
  riparano ma rifanno la superficie (alpha wrap, fTetWild) sono le uniche che
  arrivano ai tetraedri.** Il costo è geometrico: §5.

---

## 3. Rilevazione

### 3.1 PyMeshLab (installato, 2025.7.post1)

Nomi misurati con `pymeshlab.print_filter_list()` e
`pymeshlab.print_filter_parameter_list(<nome>)` `[M]`:

| Filtro | Parametri nella versione installata | Che cosa rileva |
|---|---|---|
| `compute_selection_by_self_intersections_per_face` | nessuno | facce che si intersecano; 3,2 s su 1,35 M triangoli, 6,5 s su 3,8 M `[M]` |
| `compute_selection_bad_faces` | `usear=True, aratio=0.02, usenf=False, nfratio=60, select_folded_faces=False, folded_faces_angle_threshold=160` | facce di cattivo rapporto d'aspetto, e facoltativamente piegate |
| `meshing_remove_null_faces` | nessuno | solo area **esattamente** zero |
| `meshing_remove_folded_faces` | nessuno | solo facce piegate **isolate** |
| `meshing_remove_t_vertices` | `method='Edge Collapse', threshold=40, repeat=True` | T-vertici (triangoli-cappa) |
| `meshing_repair_non_manifold_edges` / `_vertices` | `method='Remove Faces'` / `vertdispratio=0` | non-manifold |
| `get_topological_measures` | nessuno | manifold, genere, bordi, componenti |
| `generate_alpha_wrap` | `alpha: PercentageValue = 2%`, `offset: PercentageValue = 0.1%` | — (è una ricostruzione, §5.1) |
| `meshing_isotropic_explicit_remeshing` | `checksurfdist: bool = False`, `maxsurfdist = 1%`, `targetlen = 1%`, `iterations = 10`, … | — |

**Scostamento dalla documentazione.** La pagina `latest` della documentazione
PyMeshLab (`fonti/pymeshlab-filter-list.md:4221-4236` e `:5847-5870`) dà
`generate_alpha_wrap(alpha_fraction, offset_fraction)` come float e
`checksurfdist = True` per predefinito. La versione installata ha `alpha`/`offset`
come `PercentageValue` e `checksurfdist = False`. Vale la misura: la
documentazione `latest` non corrisponde alla wheel 2025.7.post1. `[M]` contro `[V]`

- **URL** https://pymeshlab.readthedocs.io/en/latest/filter_list.html · [V] (`fonti/pymeshlab-filter-list.md`)
  **perche' conta qui** è la libreria già installata che rileva autointersezioni, pieghe e degeneri, e contiene l'alpha wrap
  **cosa se ne prende** la semantica dei filtri: `meshing_remove_null_faces` toglie solo area zero (`:6053-6055`), `meshing_remove_folded_faces` solo pieghe isolate (`:6047-6049`), l'alpha wrap è il codice CGAL (`:4221-4228`); i nomi dei parametri vanno presi dalla versione installata, non da questa pagina

### 3.2 MeshFix / pymeshfix (installato, 0.18.1)

`PyTMesh` espone `select_intersecting_triangles(tris_per_cell=50, justproper=False)`,
`strong_intersection_removal(n)`, `strong_degeneracy_removal(n)`,
`clean(max_iters=10, inner_loops=3) -> bool`, `boundaries()`, `fix_connectivity()`
(misurato con `dir(pymeshfix.PyTMesh)` e `__doc__`). `[M]`
`select_intersecting_triangles` ha dato 7754 facce sulla 08 contro le 7747 di
PyMeshLab, in 11,5 s contro 3,2 s. `[M]`

- **URL** https://github.com/pyvista/pymeshfix/blob/main/src/_meshfix.cpp · [V] (`fonti/pymeshfix-binding-cpp.md`)
  **perche' conta qui** è il ponte Python che MeshRec usa già; dice quali funzioni di MeshFix sono raggiungibili
  **cosa se ne prende** `clean` chiama `meshclean(max_iters, inner_loops)` e ritorna `bool` (`:367-375`); `select_intersecting_triangles` e `strong_*_removal` sono esposti (`:377-408`)

### 3.3 TetGen `-d`

TetGen stesso rileva le autointersezioni (`-d`, «Detects self-intersections of
facets of the PLC») e, se lanciato da riga di comando, si ferma con «Hint: use -d
option to detect all self-intersections». In `tetgen 0.8.4` il flag è
`diagnose=True`; dal binding però il programma prosegue verso la
tetraedrizzazione e i risultati arrivano solo come avvisi su stdout (misurato:
3736 avvisi sulla 08, poi `recoversubfaces`; sulla 06 «The input surface mesh is
correct.» dopo 2710 s, poi il binding solleva un generico «Failed to
tetrahedralize. You may need to repair surface by making it manifold»). Non
restituisce la lista delle facce, e il messaggio finale del binding in modalità
`-d` va ignorato. `[M]`

- **URL** https://wias-berlin.de/software/tetgen/1.5/doc/manual/manual005.html · [V] (`fonti/tetgen-manual-cap4-switches.md`)
  **perche' conta qui** è il manuale delle opzioni del tetraedratore di MeshRec
  **cosa se ne prende** `-d` rileva le autointersezioni (`:47`); `-Y` conserva la superficie d'ingresso, con punti di Steiner solo all'interno (`:32`, `:230`)
- **URL** https://wias-berlin.de/software/tetgen/1.5/doc/manual/manual003.html · [V] (`fonti/tetgen-manual-cap3-uso.md`)
  **perche' conta qui** elenca le cause tipiche dei fallimenti di TetGen
  **cosa se ne prende** «The input surface mesh contains self-intersections» fra le cause, con il suggerimento `-d` (`:69-84`)
- **URL** https://wias-berlin.de/software/tetgen/1.5/doc/manual/manual002.html · [V] (`fonti/tetgen-manual-cap2-plc.md`)
  **perche' conta qui** definisce il PLC valido, cioè il contratto d'ingresso di TetGen
  **cosa se ne prende** due facce possono incontrarsi solo in vertici e segmenti del complesso: una superficie con facce sovrapposte o compenetrate non è un PLC valido

### 3.4 CGAL (C++; binding Python `cgal` 6.0.1)

CGAL rileva con `does_self_intersect()` / `self_intersections()`, e i degeneri
con `is_degenerate_triangle_face()`, `is_needle_triangle_face()`,
`is_cap_triangle_face()`. Il binding SWIG ufficiale (`pip install cgal`, wheel
cp312 per `macosx_11_0_arm64` e `win_amd64`, ultima uscita 25/10/2024) espone
**solo** `does_self_intersect`, `self_intersections`, `isotropic_remeshing`,
`do_intersect`, `corefine_and_compute_intersection` in PMP, più `alpha_wrap_3`.
Niente `autorefine`, niente `remove_almost_degenerate_faces`, niente
`repair_polygon_soup` (misurato con `dir(CGAL.CGAL_Polygon_mesh_processing)` in
un ambiente isolato). `[M]`

- **URL** https://doc.cgal.org/latest/Polygon_mesh_processing/index.html · [V] (`fonti/cgal-pmp-manual.md`)
  **perche' conta qui** è la definizione di riferimento di rilevazione di autointersezioni e di elementi mal formati
  **cosa se ne prende** `does_self_intersect()` / `self_intersections()` (`:49-51`), i predicati di forma per degeneri, aghi e cappe (`:549-558`)
- **URL** https://github.com/CGAL/cgal-swig-bindings/blob/main/SWIG_CGAL/Polygon_mesh_processing/CGAL_Polygon_mesh_processing.i · [V] (`fonti/cgal-swig-pmp-interface.md`)
  **perche' conta qui** dice che cosa di CGAL è davvero raggiungibile da Python senza compilare
  **cosa se ne prende** sono esposti `does_self_intersect` e `self_intersections` (`:427-436`), non l'autorifinitura
- **URL** https://pypi.org/pypi/cgal/6.0.1.post202410241521/json · [V] (`fonti/pypi-cgal-6-0-1-json.md`)
  **perche' conta qui** stato delle wheel per le due piattaforme di MeshRec
  **cosa se ne prende** wheel cp38-cp312 per macOS arm64 e `win_amd64`, nessuna cp313

### 3.5 libigl, trimesh, MeshLib

- `libigl 2.6.3` (wheel cp312 macOS arm64 e `win_amd64`) espone
  `igl.copyleft.cgal.remesh_self_intersections(V, F, detect_only=False, ..., cutoff=1000)`,
  `outer_hull`, `extract_cells`, `mesh_boolean`. **Attenzione:** `cutoff=1000`
  per predefinito limita il numero di intersezioni risolte. `[M]`
- `trimesh 5.1.0` non ha un rilevatore di autointersezioni: espone
  `nondegenerate_faces`, `is_watertight`, `is_volume`. `[M]`
- `meshlib 3.1.4` espone `fixSelfIntersections`, `localFindSelfIntersections`,
  `findDegenerateFaces`, `resolveMeshDegenerations` (misurato con `dir()`), wheel
  `macosx_12_0_arm64` e `win_amd64`; licenza dichiarata `LicenseRef-MeshLib`,
  non libera. Non provato sul caso. `[M]`

- **URL** https://github.com/libigl/libigl/blob/main/include/igl/copyleft/cgal/remesh_self_intersections.h · [V] (`fonti/libigl-remesh-self-intersections-h.md`)
  **perche' conta qui** è la via «esatta» (Zhou–Jacobson) raggiungibile da Python con wheel su entrambe le piattaforme
  **cosa se ne prende** suddivide le facce lungo le curve d'intersezione mantenendo chiusura e manifold (`:27`), con un bug dichiarato per spigoli giacenti su facce (`:39`), e l'esempio d'uso con `outer_hull` a valle; `outer_hull` estrae la pelle esterna di una mesh a numero di avvolgimento costante a tratti (`fonti/libigl-outer-hull-h.md:18`)
- **URL** https://pypi.org/pypi/libigl/2.6.3/json · [V] (`fonti/pypi-libigl-2-6-3-json.md`)
  **perche' conta qui** stato delle wheel
  **cosa se ne prende** cp312 per `macosx_11_0_arm64` e `win_amd64`, uscita 01/09/2026
- **URL** https://pypi.org/pypi/meshlib/3.1.4.297/json · [V] (`fonti/pypi-meshlib-3-1-4-json.md`)
  **perche' conta qui** unica libreria Python con un «fix self-intersections» dedicato e wheel Windows
  **cosa se ne prende** licenza `LicenseRef-MeshLib`: da verificare prima di considerarla

---

## 4. Riparazione

### 4.1 MeshFix (Attene 2010) — che cosa fa davvero

Dalla lettura del sorgente `[V]`:

- `repair()` di pymeshfix esegue `fill_small_boundaries(0, True)`, eventualmente
  `join_closest_components()`, `remove_smallest_components()`, poi `clean()`, e
  **ignora il booleano** che `clean()` restituisce (`fonti/pymeshfix-meshfix-py.md:388-431`).
- `meshclean(max_iters, inner_loops)` è un ciclo «ripara → verifica» con tetto:
  per al più `max_iters` giri chiama `strongDegeneracyRemoval(inner_loops)` e
  `strongIntersectionRemoval(inner_loops)`, ed esce con `true` solo se entrambe
  riescono e nessun triangolo è **esattamente** degenere
  (`fonti/meshfix-checkandrepair-cpp.md:1033-1056`).
- `strongIntersectionRemoval` seleziona i triangoli che si intersecano, **allarga
  la selezione** di un anello per ogni giro già fatto (`growSelection`), li
  **cancella**, toglie le componenti minori, **richiude i buchi** e riavvicina le
  coordinate (`coordBackApproximation`) (`fonti/meshfix-detectintersections-cpp.md:374-393`).
  `strongDegeneracyRemoval` fa lo stesso sui degeneri (`fonti/meshfix-checkandrepair-cpp.md:758-775`).
- Il degenere di MeshFix è quello **esatto** (`isExactlyDegenerate`,
  `fonti/meshfix-checkandrepair-cpp.md:513`): un ago con area piccola ma non nulla
  non viene toccato.
- Il README avverte che MeshFix è pensato per «RAW DIGITIZED mesh models», assume
  un unico solido chiuso e lascia intatte le regioni senza difetti
  (`fonti/meshfix-v21-readme.md:12-14`); l'eseguibile, se non ripara tutto,
  scrive «MeshFix could not fix everything.» (`fonti/meshfix-main-cpp.md:200`).

Misurato sulla 08: `clean(10,3)` converge (`True`) in 482 s togliendo 11 586
triangoli su 1 347 554 (0,86 %), autointersezioni a zero, nessun bordo aperto —
e TetGen fallisce comunque. `[M]`

- **URL** https://github.com/MarcoAttene/MeshFix-V2.1 · [V] (`fonti/meshfix-v21-readme.md`, `fonti/meshfix-checkandrepair-cpp.md`, `fonti/meshfix-detectintersections-cpp.md`, `fonti/meshfix-main-cpp.md`)
  **perche' conta qui** è l'algoritmo che MeshRec usa già allo step 6, e l'unico ciclo «ripara → verifica» con tetto già installato
  **cosa se ne prende** la semantica esatta di `meshclean` (tetto, allargamento della selezione, cancellazione + chiusura), il limite «solo degeneri esatti», e l'avviso di non convergenza che il binding restituisce come `bool`
- **URL** https://github.com/pyvista/pymeshfix/blob/main/src/pymeshfix/meshfix.py · [V] (`fonti/pymeshfix-meshfix-py.md`)
  **perche' conta qui** è la funzione che `core/repair.py:164` chiama
  **cosa se ne prende** `repair()` scarta il ritorno di `clean()` (`:431`): per verificare serve `PyTMesh` diretto
- **URL** https://pypi.org/pypi/pymeshfix/0.18.1/json · [V] (`fonti/pypi-pymeshfix-0-18-1-json.md`)
  **perche' conta qui** conferma che la dipendenza già in uso ha wheel per entrambe le piattaforme
  **cosa se ne prende** cp312 `macosx_11_0_arm64` e `win_amd64`, uscita 23/04/2026
- **URL** https://github.com/pyvista/pymeshfix · [V] (`fonti/pymeshfix-readme.md`)
  **perche' conta qui** licenza e citazione del componente già in uso
  **cosa se ne prende** doppia licenza GPLv3 / commerciale e citazione Attene, *The Visual Computer* 2010, DOI 10.1007/s00371-010-0416-3

Il testo completo dell'articolo di Attene 2010 non è stato letto (Springer non
raggiungibile dalla sessione): `[NON TROVATO]` per ogni dettaglio che non stia nel
sorgente.

### 4.2 CGAL: autorefine, riparazione della «zuppa», degeneri quasi

- `autorefine_triangle_soup()` spezza i triangoli lungo le intersezioni: con un
  kernel a costruzioni inesatte **l'arrotondamento può reintrodurre**
  autointersezioni, e `apply_iterative_snap_rounding=true` le previene
  (`fonti/cgal-pmp-mesh-repair-manual.md:650-654`). `[V]`
- `repair_polygon_soup()` raggruppa fusione dei punti doppi, dei poligoni doppi,
  rimozione dei punti isolati e altre riparazioni (`:376-384`). `[V]`
- `remove_almost_degenerate_faces()` toglie aghi e cappe con soglie
  (`cap_threshold`, `needle_threshold`) e con guardie per non distruggere forme
  lecite (`:648`). È **l'unico strumento trovato che affronta i degeneri
  geometrici non nulli** di cui parla il brief. `[V]`
- Nessuna delle tre è nel binding Python (§3.4): usarle vuol dire compilare C++ o
  cercare un altro binding. `[M]`
- `[INF]` L'autorifinitura da sola non produce un ingresso per TetGen: due lembi
  che si attraversano, una volta spezzati, danno spigoli con quattro facce (non
  manifold). Serve un passo che estragga la pelle esterna (`outer_hull` in
  libigl). La misura di §2 con libigl conferma: dopo `outer_hull` la superficie
  resta non manifold con 580 facce autointersecanti (arrotondamento a double) e
  TetGen fallisce.

- **URL** https://doc.cgal.org/latest/PMP_Mesh_repair/index.html · [V] (`fonti/cgal-pmp-mesh-repair-manual.md`)
  **perche' conta qui** è la cassetta degli attrezzi di riparazione più completa trovata, e documenta il rischio d'arrotondamento
  **cosa se ne prende** autorefine + snap rounding (`:650-654`), `remove_almost_degenerate_faces` per aghi e cappe (`:648`), `repair_polygon_soup` (`:376-384`); tutte solo in C++

### 4.3 gmsh

Gmsh non ripara: il suo FAQ dice, quando il 3D fallisce, «Verify that the
surfaces in your model do not self-intersect or partially overlap»
(`fonti/gmsh-reference-manual.md:24922`). L'opzione
`Mesh.AngleToleranceFacetOverlap` (predefinito 0,1°) dichiara sovrapposte due
facce connesse con angolo diedro sotto la soglia (`:17100`): è un rilevatore
delle «pieghe» che §2 conta, non un rimedio. `[V]`
`[NON TROVATO]` una pipeline documentata che usi `classifySurfaces` di gmsh per
rimediare ad autointersezioni: il flusso STL di gmsh (dalla 4.4.0) presuppone una
superficie valida.

- **URL** https://gmsh.info/doc/texinfo/gmsh.html · [V] (`fonti/gmsh-reference-manual.md`)
  **perche' conta qui** gmsh è già una dipendenza di MeshRec e l'alternativa naturale a TetGen
  **cosa se ne prende** anche gmsh esige superfici senza autointersezioni né sovrapposizioni (`:24922`); `Mesh.AngleToleranceFacetOverlap` come criterio di rilevazione delle pieghe (`:17100`)

### 4.4 Riparare dopo lo step 8 invece che prima

Il remeshing con `checksurfdist=True, maxsurfdist=0,05 %` riduce le
autointersezioni introdotte da 646 a 141, non a zero `[M]`. Non si può quindi
contare sul solo parametro: un controllo dopo lo step 8 serve comunque.

---

## 5. Aggirare invece di riparare

### 5.1 Alpha wrap di CGAL (dentro `pymeshlab`, già installato)

Costruisce **una superficie nuova** che racchiude l'ingresso a distanza `offset`,
entrando in cavità più larghe di `alpha`. Garanzie dichiarate: termina, produce
una superficie 2-manifold che racchiude strettamente l'ingresso; accetta zuppe
con autointersezioni, sovrapposizioni, degeneri combinatori e geometrici
(`fonti/cgal-alpha-wrap-3-manual.md:19`, `:73`, `:81`). Il kernel è a virgola
mobile per scelta (`:83`), e con buchi più larghi di alpha produce un involucro a
doppia parete (`:123`). `[V]`

Misurato sulla 08 `[M]` (`sonda_rimedi.py wrap`, `sonda2.py wrapdist`):

| α / offset (frazione diagonale → mm) | Tempo | Triangoli | Autoint. | Volume vs 08 | Distanza wrap→08 media / max | Distanza 08→wrap media / max | TetGen |
|---|---|---|---|---|---|---|---|
| 0,5 % / 0,05 % (17,3 / 1,73 mm) | 12 s | 54 140 | 0 | +7,1 % | 1,73 / 1,75 mm (solo vertici) | non misurata | riuscito (plc) |
| 0,2 % / 0,02 % (6,9 / 0,69 mm) | 48 s | 369 278 | 30 | +3,0 % | 1,16 / 7,06 mm | 2,24 / **27,6 mm** | riuscito con `minratio=1.8`, 1 578 763 tetraedri, 144 s |

Letture: il wrap è **conservativo** (gonfia il volume dell'offset e riempie le
cavità più strette di alpha); la distanza 08→wrap a 27,6 mm dice che dettagli
della superficie originale spariscono. 30 facce autointersecanti residue con α =
0,2 % non hanno impedito a TetGen di chiudere: `[INF]` l'uscita in double non è
garantita libera da intersezioni, contrariamente all'obiettivo dichiarato alla
riga 19 del manuale; la sezione «Guarantees» (`:73`) promette manifold e
racchiusura, non l'assenza di intersezioni.

- **URL** https://doc.cgal.org/latest/Alpha_wrap_3/index.html · [V] (`fonti/cgal-alpha-wrap-3-manual.md`)
  **perche' conta qui** è l'aggiramento già installato su entrambe le piattaforme (dentro `pymeshlab`), e l'unico che su questo caso ha portato TetGen a chiudere con i parametri di MeshRec
  **cosa se ne prende** che cosa promette (manifold, racchiusura stretta, `:73`), che cosa accetta (zuppe difettose, `:81`), come scegliere i parametri (offset piccola frazione di alpha, `:111`; alpha come livello di dettaglio, `:93`), e il limite della doppia parete (`:123`)

### 5.2 fTetWild / TetWild / wildmeshing / pytetwild

fTetWild prende una **zuppa di triangoli** e produce tetraedri validi in virgola
mobile, approssimando la superficie entro un inviluppo `ε` (predefinito 10⁻³ della
diagonale); in cambio non garantisce di inserire ogni triangolo d'ingresso
(`fonti/ftetwild-arxiv-abs.md`, abstract). Su Thingi10k (10 000 modelli reali,
con autointersezioni e non-manifold: `fonti/thingi10k-arxiv-abs.md`):

| Metodo | Successo | Limite dell'algoritmo |
|---|---|---|
| CGAL | 79,00 % | 21,00 % |
| **TetGen** | **49,50 %** | **48,70 %** |
| TetWild | 99,89 % | 0 % |
| fTetWild | 99,97 % | 0 % |

(`fonti/ftetwild-paper-html.md:248-255`, limiti 3 h e 32 GB). L'articolo nota che
TetGen conserva esattamente la superficie d'ingresso (`:327`) e mostra un caso
architettonico con 80 999 facce autointersecanti ripulito e tetraedrizzato (`:359`). `[V]`

Stato dei pacchetti Python `[V]` (PyPI JSON) e `[M]`:

| Pacchetto | Versione | cp312 macOS arm64 | cp312 Windows | Note |
|---|---|---|---|---|
| `wildmeshing` | 0.4.1 (25/02/2025) | sì (`macosx_14_0_arm64`) | **no** | nessuna sdist; è il motivo dello SKIP in `tests/feasibility/test_wildmeshing.py:4-9` |
| **`pytetwild`** | 0.4.2 (17/08/2026) | sì (`macosx_15_0_arm64`) | **sì** (`win_amd64`) | wrapper pyvista di fTetWild, MPL-2.0; **l'import richiede `pyvista`** anche se il README lo dice facoltativo (`ModuleNotFoundError: No module named 'pyvista'` misurato), quindi porta con sé `vtk` (98 MB) |

Misurato sulla 08 con `pytetwild.tetrahedralize(V, F)` predefiniti, in ambiente
isolato (`uv run --no-project --python 3.12 --with pytetwild==0.4.2 --with pyvista --with pymeshlab==2025.7.post1`) `[M]`:
1471 s (≈ 24,5 min, 6 core, 8 GB), 81 597 nodi, 302 436 tetraedri, orientamento
coerente, volume 507,69·10⁶ mm³ contro 508,00·10⁶ della 08 (−0,06 %); distanza
bordo→08 media 0,56 / max 3,82 mm (entro ε = 3,46 mm); 08→bordo media 0,62 /
max **15,1 mm**. `[M]`
Seconda configurazione, più fedele (`epsilon=2e-4` → 0,69 mm, `edge_length_fac=0.02`):
**interrotta a mano dopo circa 68 minuti** senza uscita, 1,6 GB di memoria
residente. Sul caso, un inviluppo stretto quanto l'offset dell'alpha wrap a
α = 0,2 % non sta in tempi da pipeline interattiva su questa macchina. `[M]`

Limiti per MeshRec: fTetWild produce **tetraedri lineari**; il deck C3D10 oggi
viene da TetGen con `order=2` e dalla permutazione `TETGEN_A_ABAQUS`
(`core/volume.py:65`, `:175-178`, `:205-206`). Con fTetWild i nodi di metà spigolo andrebbero
aggiunti a valle. `[INF]`

- **URL** https://arxiv.org/html/1908.03581v2 · [V] (`fonti/ftetwild-paper-html.md`, `fonti/ftetwild-arxiv-abs.md`)
  **perche' conta qui** è la misura pubblicata più ampia di quanto TetGen fallisca su superfici «in the wild», e del perché
  **cosa se ne prende** tabella di successo su Thingi10k (`:248-255`), il compromesso dell'inviluppo, i parametri predefiniti ε = 10⁻³·d e ℓ = d/20 (`:220`)
- **URL** https://github.com/wildmeshing/fTetWild · [V] (`fonti/ftetwild-readme.md`)
  **perche' conta qui** opzioni del programma che `pytetwild` incapsula
  **cosa se ne prende** `-e/--epsr` e `-l/--lr` relativi alla diagonale (`:152-153`), `--manifold-surface` (`:162`), memoria oltre 32 GB sui casi più complessi (`:39`)
- **URL** https://github.com/pyvista/pytetwild · [V] (`fonti/pytetwild-readme.md`, `fonti/pypi-pytetwild-0-4-2-json.md`)
  **perche' conta qui** è l'unico modo trovato di avere fTetWild con wheel Windows
  **cosa se ne prende** wheel 3.10-3.14 per Windows, Linux, macOS (`:20`), licenza MPL-2.0 (`:9`), API a array e campo di dimensione di fondo
- **URL** https://pypi.org/pypi/wildmeshing/0.4.1/json · [V] (`fonti/pypi-wildmeshing-0-4-1-json.md`)
  **perche' conta qui** conferma il blocco Windows già annotato in fase 0
  **cosa se ne prende** nessuna wheel `win_amd64` e nessuna sdist
- **URL** https://arxiv.org/abs/1605.04797 · [V] (`fonti/thingi10k-arxiv-abs.md`)
  **perche' conta qui** è il banco su cui sono misurati TetWild, fTetWild e l'alpha wrap
  **cosa se ne prende** i modelli contengono proprio autointersezioni e non-manifold: il banco è rappresentativo del nostro difetto

### 5.3 Voxel e maglia da immagine

- **Cloud2FEM** (patrimonio storico, UniBo) evita la superficie: affetta la
  nuvola, riconosce poligoni chiusi per strato e li impila in voxel, con
  esaedri «robust and conforming»; nota che la via CAD solido → mesh «usually
  leads to errors in the FE meshing procedures due to geometric imprecisions and
  tolerances» (`fonti/cloud2fem-softwarex-pdf.md:58-72`). `[V]`
- **SimNIBS `charm`** costruisce la maglia di volume **direttamente
  dall'immagine etichettata** con CGAL Mesh_3 (`image2mesh`,
  `fonti/simnibs-meshing-py.md:158-230`), senza passare da una superficie
  triangolata. `[V]`
- Per MeshRec la via equivalente sarebbe voxelizzare il solido chiuso dello
  step 6 (o l'indicatrice del Poisson) e rimagliare. `[INF]` Non misurato.

- **URL** https://cris.unibo.it/bitstream/11585/895272/1/1-s2.0-S235271102200067X-main.pdf · [V] (`fonti/cloud2fem-softwarex-pdf.md`, già catturata il 2026-09-11)
  **perche' conta qui** è il caso applicato più vicino a MeshRec (nuvola di un edificio esistente → FEM) e ha scelto di non passare dalla superficie
  **cosa se ne prende** la motivazione (errori di meshing da imprecisioni geometriche, `:58-61`) e la via voxel (`:62-72`)
- **URL** https://github.com/simnibs/simnibs/blob/master/simnibs/mesh_tools/meshing.py · [V] (`fonti/simnibs-meshing-py.md`)
  **perche' conta qui** pipeline biomedica in produzione (segmentazione → FEM) che ha abbandonato la superficie per il volume
  **cosa se ne prende** `image2mesh` con i criteri di CGAL Mesh_3 (`facet_angle`, `facet_distance`, `cell_radius_edge_ratio`), `:158-230`

---

## 6. Casi applicati

| Progetto | Dominio | Ordine dei passi | Esito misurato | Fonte |
|---|---|---|---|---|
| **iso2mesh** (Q. Fang) | biomedico, segmentazione → FEM | `vol2mesh` = `vol2surf` → `surf2mesh`; dentro `vol2surf`: `binsurface` → `meshcheckrepair` (dup, isolated, deep) → `meshresample` (semplificazione CGAL) → `removeisolatedsurf` → **`meshcheckrepair(..., 'meshfix')`**; poi `surf2mesh` chiama TetGen | non riportato | `fonti/iso2mesh-vol2mesh-m.md:61-75`, `fonti/iso2mesh-vol2surf-m.md:121-144`, `fonti/iso2mesh-surf2mesh-m.md:94-117`, `fonti/iso2mesh-meshcheckrepair-m.md` |
| **SimNIBS** (`headreco`/`charm`) | stimolazione cerebrale, MRI → FEM | marching cubes → componente maggiore → **`meshfix -u <n> -a 2.0`** → orientamento; in `charm`: CGAL Mesh_3 dall'immagine | non riportato | `fonti/simnibs-marching-cube-py.md:98-120`, `fonti/simnibs-meshing-py.md:158-230` |
| **fTetWild** | banco Thingi10k | zuppa → tetraedri, niente riparazione | 99,97 % contro 49,50 % di TetGen | `fonti/ftetwild-paper-html.md:248-255` |
| **CGAL Alpha wrap** | banco Thingi10k | zuppa → wrap | tempi e complessità per α da d/20 a d/200 (figura) | `fonti/cgal-alpha-wrap-3-manual.md:135` |
| **Cloud2FEM** | patrimonio, nuvola → FEM | fette → poligoni → voxel → esaedri | analisi non lineari su una fortezza | `fonti/cloud2fem-softwarex-pdf.md:58-72` |
| Legno storico, fotogrammetria → FEM (J. Infrastructure Intelligence and Resilience, 2026) | patrimonio | fori chiusi, autointersezioni trattate con il motore di libigl via PyMesh prima della maglia | — | **[NON TROVATO]** testo pieno: ScienceDirect 403; solo il riassunto di un motore di ricerca |

Il punto comune `[INF]`: **chi ripara, ripara dopo l'ultima trasformazione e
subito prima del tetraedratore** (iso2mesh mette MeshFix dopo la semplificazione;
SimNIBS fa il rimagliamento uniforme dentro MeshFix stesso). MeshRec fa il
contrario: ripara allo step 6 e trasforma allo step 8.

`[NON TROVATO]` una pipeline scan-to-FEM per telai o ponti in c.a. che documenti
un passo esplicito di riparazione delle autointersezioni prima di TetGen o gmsh
con risultati misurati. Le pipeline strutturali trovate (Cloud2FEM) evitano la
superficie; le altre la ricostruiscono a mano in CAD.

- **URL** https://github.com/fangq/iso2mesh/blob/master/vol2surf.m · [V] (`fonti/iso2mesh-vol2surf-m.md`)
  **perche' conta qui** è la pipeline in produzione più simile al percorso di MeshRec (superficie → semplificazione → TetGen) e mette la riparazione nel posto giusto
  **cosa se ne prende** l'ordine: `meshresample` (`:138`) poi `meshcheckrepair(..., 'meshfix')` (`:144`), e a valle `surf2mesh` → TetGen (`fonti/iso2mesh-vol2mesh-m.md:61-75`, `fonti/iso2mesh-surf2mesh-m.md:94-117`)
- **URL** https://github.com/fangq/iso2mesh/blob/master/meshcheckrepair.m · [V] (`fonti/iso2mesh-meshcheckrepair-m.md`)
  **perche' conta qui** separa verifica e riparazione in opzioni distinte
  **cosa se ne prende** `'intersect'` solo verifica, `'meshfix'` ripara, opzioni predefinite di meshfix `-q -a 0.01`
- **URL** https://github.com/simnibs/simnibs/blob/master/simnibs/segmentation/marching_cube.py · [V] (`fonti/simnibs-marching-cube-py.md`)
  **perche' conta qui** seconda pipeline biomedica in produzione con MeshFix a valle della ricostruzione
  **cosa se ne prende** la chiamata `meshfix <file> -u n -a 2.0 -q` e la nota che MeshFix tiene solo la componente maggiore (`:55-58`, `:98-120`)

---

## 7. Iterazione «ripara → verifica → ripara»

- Il ciclo con tetto **esiste già** dentro MeshFix: `meshclean(max_iters=10,
  inner_loops=3)`, con allargamento progressivo della zona cancellata a ogni giro
  (§4.1). Sulla 08 è arrivato a zero al quinto giro esterno (log: 7754 → 2779 →
  266 | 140 → 74 → 19 | 37 → 47 → 72 | 27 → 14 → 27 | 4 → 4 → 0). Il numero non
  scende in modo monotono: cancellare e richiudere crea intersezioni nuove. `[M]` MeshRec lo usa già, ma non legge il risultato.
- **Rischi misurati**: la cancellazione + chiusura ha tolto 11 586 triangoli dalla 08; sulla 06 la catena T-vertici + MeshFix ha lasciato il volume invariato (+0,0003 %) ma spostato localmente la superficie fino a 11,06 mm (media 0,001 mm); il
  wrap gonfia il volume del 3-7 % e perde dettagli fino a 27,6 mm; fTetWild sposta
  il bordo fino a 3,8 mm (entro ε) e perde dettagli fino a 15,1 mm. `[M]`
- **Rischio strutturale**: in MeshRec l'errore geometrico (`quality.geometric_error`)
  si misura allo step 7, prima dello step 8 (`core/pipeline.py:757-761`). Un
  ciclo di riparazione o un wrap aggiunto dopo la 7 sposterebbe la superficie
  senza che il registro lo dica. Qualunque rimedio a valle della 7 deve
  **rimisurare** l'errore contro la nuvola. `[V]` sul codice, `[INF]` sulla
  conseguenza.
- Tetto sensato di un ciclo esterno `[INF]`: ogni giro TetGen su superfici da
  1-4 M di triangoli è costato 11-19 minuti anche solo per fallire il recupero
  del bordo (tabella §2.1). Un ciclo che ritenta TetGen è costoso; un ciclo che
  ritenta solo la verifica (3-7 s con PyMeshLab) no.

---

## 8. Tabella comparativa

| Strumento | Rileva | Ripara / aggira | Wheel macOS arm64 | Wheel Windows | Già installato | Costo misurato sul caso | Casi d'uso reali |
|---|---|---|---|---|---|---|---|
| PyMeshLab filtri | autoint., bad faces, pieghe isolate, non-manifold | rimozioni locali, T-vertici | sì | sì | **sì** 2025.7.post1 | 3-7 s rilevazione; catena T-vertici 19 s, aghi a zero, TetGen fallisce comunque | MeshLab |
| **PyMeshLab `generate_alpha_wrap`** (CGAL) | — | **aggira**: superficie nuova, manifold | sì | sì | **sì** | 12-48 s; volume +3/+7 %; dettagli persi fino a 27,6 mm | CGAL Thingi10k |
| pymeshfix / MeshFix | autoint., degeneri esatti | **ripara** con ciclo con tetto (cancella + chiude) | sì | sì | **sì** 0.18.1 | 482 s su 1,35 M; converge, ma non basta su questo caso | iso2mesh, SimNIBS |
| TetGen `-d` | autoint. (predicati esatti) | no | sì | sì | **sì** 0.8.4 | 411 s (08) e 2710 s (06, «input correct»); nessuna lista restituita dal binding | TetGen standalone |
| gmsh | pieghe (`AngleToleranceFacetOverlap`) | no | sì | sì | **sì** 4.15.2 | non misurato | — |
| CGAL C++ (autorefine, `remove_almost_degenerate_faces`, `repair_polygon_soup`) | sì | sì | solo compilando | solo compilando | no | non misurato | — |
| `cgal` binding 6.0.1 | `does_self_intersect`, `self_intersections` | solo `alpha_wrap_3` | sì | sì | no | non misurato | — |
| libigl 2.6.3 | `remesh_self_intersections(detect_only=True)` | autorefine + `outer_hull` | sì | sì | no | 348 + 52 s; esito **non manifold**, 580 autoint., TetGen fallisce | Zhou–Jacobson |
| trimesh 5.1.0 | solo `nondegenerate_faces` | no | puro Python | puro Python | no | — | — |
| MeshLib 3.1.4 | sì | `fixSelfIntersections` | sì | sì | no | non provato; licenza non libera | — |
| **pytetwild 0.4.2** (fTetWild) | — | **aggira**: tetraedri da zuppa | sì (macOS 15+) | sì | no (+ pyvista, vtk) | 1471 s con ε = 3,46 mm; volume −0,06 %; bordo entro 3,8 mm; dettagli persi fino a 15,1 mm; con ε = 0,69 mm oltre 68 min, interrotta | Thingi10k 99,97 % |
| wildmeshing 0.4.1 | — | come sopra | sì | **no** | no | — | — |
| Voxel / Mesh_3 da immagine | — | **aggira** | — | — | no | non misurato | Cloud2FEM, SimNIBS `charm` |

---

## 9. Approcci candidati (raccomandazioni, non decisioni)

### A. Non creare il difetto e verificarlo dove nasce

Misurato: lo step 8 con Taubin moltiplica per 12 le autointersezioni. Tre mosse,
tutte con strumenti installati:
(1) nessuna trasformazione dopo la riparazione senza una verifica dopo
(`compute_selection_by_self_intersections_per_face`, 3-7 s);
(2) leggere il ritorno di `PyTMesh.clean()` invece di `MeshFix.repair()`, e
rilanciare il ciclo di MeshFix **dopo** lo step 8 come fa iso2mesh;
(3) rimisurare l'errore geometrico dopo l'ultima trasformazione.
**Trade-off:** costa poco e rende il guasto diagnosticabile, ma **su
`geoandgeo-mm` non basta**: la 06 senza autointersezioni fallisce già, e
fallisce ancora dopo aver tolto aghi e cappe (catena di §2.1). È necessaria, non
sufficiente.

### B. Alpha wrap come ripiego quando TetGen si ferma in `recoversubfaces`

`pymeshlab.generate_alpha_wrap` è già installato su entrambe le piattaforme, ha
portato la superficie reale fino a 1,58 M tetraedri con i parametri di MeshRec,
in 48 s. **Trade-off:** la superficie è nuova e conservativa — gonfia il volume
(+3 % con α = 6,9 mm, offset = 0,69 mm) e cancella le cavità più strette di α;
la distanza massima dall'originale (27,6 mm) va dichiarata nel registro accanto
all'errore geometrico, e α/offset vanno scelti in millimetri rispetto allo
spessore degli elementi, non in frazione di diagonale. Va dichiarato come
ripiego, non come riparazione.

### C. fTetWild come secondo tetraedratore

`pytetwild` ha wheel per le due piattaforme e ha tetraedrizzato la superficie
che TetGen rifiuta, con volume a −0,06 % e bordo entro ε. **Trade-off:** nuova
dipendenza (MPL-2.0) che porta `pyvista` e `vtk`; 24,5 minuti sul caso con i
predefiniti (ε = 3,46 mm) e oltre 68 minuti senza finire con ε = 0,69 mm; tetraedri **lineari**, quindi il C3D10 va costruito a valle; la
superficie non è conservata esattamente, e la perdita di dettaglio (15,1 mm max)
va dichiarata.

`[INF]` A è indipendente da B e C e vale comunque; fra B e C, B costa zero
dipendenze e C preserva meglio il volume.

---

## 10. Caveat

- Tutte le misure sono su **un** caso che fallisce (`geoandgeo-mm`) e uno che
  riesce (`geoandgeo-lab`); la corsa è del 07/09/2026, prima di HEAD `53647fd`.
  Le sonde leggono i PLY della corsa, non rieseguono la pipeline.
- Le distanze di Hausdorff sono di PyMeshLab (`get_hausdorff_distance`, 10⁶
  campioni sulle facce), fra superfici, **non** contro la nuvola: non sono
  l'errore geometrico di MeshRec.
- Macchina: 6 core, 8 GB. Tempi su Windows non misurati.
- La causa esatta del fallimento sulla 06 — che TetGen `-d` dichiara corretta — resta `[INF]`.
- La documentazione `latest` di PyMeshLab non corrisponde alla wheel installata
  (§3.1).
