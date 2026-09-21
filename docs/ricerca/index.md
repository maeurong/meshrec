# Ricerche

Ogni ricerca porta URL, perché conta qui e cosa se ne prende. Le fonti catturate
stanno in `fonti/` (`.md` + `.provenance.json`). Le raccomandazioni sono dei
ricercatori: le decisioni stanno negli ADR e nelle spec.

## 2026-09-11 — Impacchettare MeshRec come programma

Domanda di partenza: oggi MeshRec si avvia da terminale e vive in una scheda del
browser. Deve sembrare e usarsi come un programma qualsiasi, e avere più
autorevolezza davanti a commissione, tutori e laboratorio. Tre ricerche
parallele, ortogonali fra loro:

- [`2026-09-11-guscio-desktop.md`](2026-09-11-guscio-desktop.md) — la
  **finestra**: pywebview, Chromium `--app=`, PWA, Tauri/Electron, Neutralino.
  Raccomanda pywebview con `--app` come fallback e watchdog SSE; PWA scartata
  perché non avvia il server; Tauri/Electron sproporzionati. Corregge il brief:
  il selettore file è già un sottoprocesso tkinter lato server, non
  `<input type=file>`. Prova obbligatoria prima del codice: PNG/WebGL/SSE in
  pywebview su macOS e Windows.
- [`2026-09-11-distribuzione-binaria.md`](2026-09-11-distribuzione-binaria.md)
  — il **runtime**: PyInstaller, Nuitka, Briefcase, py2app, cartella portabile
  con `uv`, constructor, PyApp; installer e firma; CI su tag. Raccomanda la
  cartella portabile con `uv` (rischio nullo su open3d/pymeshlab/gmsh),
  PyInstaller onedir solo come secondo passo. Fatti misurati: `libgmsh` sta
  fuori da site-packages; pymeshlab porta 137 MB di Qt. Prerequisito comune:
  spostare `runs/`, `experiments/`, `.cache/viewport` dalla cwd a una cartella
  dati utente.
- [`2026-09-11-identita-e-autorevolezza.md`](2026-09-11-identita-e-autorevolezza.md)
  — l'**identità**: come si presentano Gmsh/MeshLab/CloudCompare/ParaView,
  `CITATION.cff` + Zenodo DOI, JOSS (eleggibile dal 2027-02-13), licenza (MIT
  già in radice; regolamento IP d'ateneo da leggere), versione/CHANGELOG/
  release, icona, About, video di backup per la discussione. Difetto d'identità
  principale: il repo si chiama `Tesi`. Lista ordinata per autorevolezza/costo
  in §6.

## 2026-09-21 — Autointersezioni e degeneri prima di TetGen

- [`2026-09-21-autointersezioni-e-degeneri.md`](2026-09-21-autointersezioni-e-degeneri.md)
  — **stato: chiusa.** Domanda: come i progetti in produzione portano una
  superficie ricostruita con autointersezioni e triangoli degeneri fino a una
  tetraedrizzazione FEM (rilevazione, riparazione, aggiramento, casi applicati,
  iterazione). Misurato su `runs/geoandgeo-mm`: lo step 8 crea le
  autointersezioni (646 facce col remeshing, 7747 con Taubin), ma la superficie
  dello step 6 fallisce in `recoversubfaces` pur senza autointersezioni (TetGen
  `-d`: «input surface mesh is correct»), e così la 08 ripulita da MeshFix.
  Arrivano ai tetraedri solo l'alpha wrap di CGAL (in `pymeshlab`, già
  installato) e fTetWild (`pytetwild`, wheel Windows). Tre approcci candidati in
  §9: verificare dopo lo step 8 (necessario, non sufficiente), alpha wrap come
  ripiego dichiarato, fTetWild come secondo tetraedratore.
- [`2026-09-21-ftetwild-in-rust.md`](2026-09-21-ftetwild-in-rust.md)
  — **stato: chiusa (spike).** Domanda: riscrivere pytetwild/fTetWild in Rust
  velocizzerebbe la tetraedrizzazione robusta? No: la wheel è già C++ `-O3`
  con TBB, e il tempo va nell'ottimizzazione (86 %), con il collasso degli
  spigoli seriale per scelta dell'algoritmo (ramo TBB commentato `_bug`). Nessun
  porting Rust esistente; il porting costerebbe 35-50 mila righe. Leva misurata:
  la 08 decimata al 10 % scende da 1471 s a 164 s, ma il massimo bordo→08 sale a
  8,1 mm (fuori da ε); `optimize=False` è inservibile per FEM.
