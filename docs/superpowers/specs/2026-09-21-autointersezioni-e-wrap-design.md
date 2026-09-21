# Autointersezioni e alpha wrap prima di TetGen — design

Data: 2026-09-21 · Stato: approvato in chat da Mario, da pianificare
Ricerca di partenza: `docs/ricerca/2026-09-21-autointersezioni-e-degeneri.md`,
`docs/ricerca/2026-09-21-ftetwild-in-rust.md`

## Problema

Alcune superfici ricostruite non arrivano al deck CalculiX: TetGen si ferma allo
step 9 in `recoversubfaces`. Misurato sulla corsa `runs/geoandgeo-mm`
(ricerca §2.1):

- lo step 8 **crea** autointersezioni: 0 sulla superficie riparata dello step 6,
  646 dopo il remeshing isotropo, 7747 dopo le due passate di Taubin;
- le autointersezioni **non sono l'unica causa**: la superficie dello step 6, che
  non ne ha e che TetGen `-d` dichiara «correct», fa fallire TetGen lo stesso;
- nessuna riparazione locale provata (MeshFix `clean`, catena PyMeshLab, libigl)
  porta TetGen a finire; l'alpha wrap di CGAL, già dentro `pymeshlab`, sì.

In più il registro oggi non lo dice: `repair.py:163-164` chiama
`MeshFix.repair()`, che scarta l'esito del ciclo di pulizia, e l'errore
geometrico si misura allo step 7 (`pipeline.py:761`), prima dello step 8 che
sposta la superficie.

## Ambito

Dentro: **A** controllo all'ingresso dello step 9, **B** alpha wrap a richiesta
esplicita. Fuori: fTetWild come secondo tetraedratore (via C della ricerca,
rimandata; se rientra, la strada è decimazione + `pytetwild`, non un porting in
Rust — `2026-09-21-ftetwild-in-rust.md`); rimozione di aghi e cappe (misurata
inutile sul caso, ricerca §2.2); modifiche allo step 8.

## A — Controllo all'ingresso dello step 9

Posizione: dentro lo step 9, prima di TetGen. È l'unico punto da cui passa
sempre la superficie che TetGen riceve, con lo step 8 acceso o spento
(`pipeline.py:777-783`).

1. **Conteggio** delle facce autointersecanti con PyMeshLab
   `compute_selection_by_self_intersections_per_face` (3-7 s su 1-4 M
   triangoli, ricerca :161).
2. Se il conteggio è > 0: **ciclo di MeshFix** con `pymeshfix.PyTMesh.clean(max_iters=10, inner_loops=3)`,
   leggendone il `bool` (ricerca :184-193), poi nuovo conteggio con PyMeshLab.
3. Se dopo il ciclo il conteggio è ancora > 0 o `clean` ha reso `False`: lo
   step **fallisce** con un errore che nomina il conteggio residuo e, se lo
   step 8 è acceso, dice che lo step 8 le ha introdotte (Taubin le moltiplica
   per 12, ricerca §2.2). Il messaggio propone `tet.wrap_tolerance`.
4. Se la superficie è cambiata dal punto in cui lo step 7 l'ha misurata (step 8
   acceso, oppure pulizia al punto 2, oppure wrap di B): **rimisura**
   `quality.geometric_error` contro la nuvola sorgente e la scrive nelle
   metriche dello step 9.

Metriche nuove in `09_tetrahedralize`:
`self_intersections_before`, `self_intersections_after`,
`meshfix_clean_converged` (`null` se il ciclo non è partito),
`triangles_removed_by_clean`, `geometric_error` (solo quando rimisurato).

La nuvola sorgente oggi si carica in ripresa solo se `start <= 7` o per lo step
12 (`pipeline.py:684-686`). Riprendendo dallo step 9 va caricata anche lì; la
condizione si allarga, il lettore resta `_ingresso_di_ripresa`.

## B — Alpha wrap, attivato esplicitamente

Campo nuovo in `TetConfig` (`config.py:275`):

```python
wrap_tolerance: float | None = Field(
    default=None, gt=0.0,
    title="spostamento ammesso dal ripiego alpha wrap [mm]",
)
```

`None` = spento, predefinito. Nessun valore suggerito: lo dichiara l'utente,
come ogni parametro che cambia la geometria. Sta in `TetConfig`, quindi
cambiarlo invalida solo dallo step 9 in giù.

Se acceso, lo step 9 fa: controllo A (conteggio, **senza** pulizia MeshFix —
la superficie viene comunque sostituita) → `generate_alpha_wrap` → controllo A
sulla superficie avvolta → TetGen.

- **Parametri:** `alpha = wrap_tolerance`, `offset = alpha / 10` (offset
  piccola frazione di alpha, manuale CGAL, ricerca :391). Convertiti in
  `PercentageValue` della diagonale del riquadro della superficie in ingresso:
  la wheel installata accetta `alpha`/`offset` come `PercentageValue`
  (ricerca :168-175), misurato funzionante.
- **Tolleranza dichiarativa, non limite** (rivisto il 21/09/2026, decisione di
  Mario dopo la review finale). Alpha non limita lo spostamento: con α = 6,9 mm
  i dettagli si sono spostati fino a 27,6 mm (ricerca §5.1). La prima versione
  faceva fallire lo step quando il massimo superava `wrap_tolerance`; misurato
  su `geoandgeo-mm/06_repaired` falliva a ogni valore (tol 6,9 → max 28,6 mm;
  tol 27,6 → max 41,3 mm), perché il massimo viene dalle cavità più strette di
  alpha che il wrap chiude per costruzione, e alzando la tolleranza cresce
  anche alpha. Ora dopo il wrap si misura la **distanza bidirezionale fra
  superficie in ingresso e superficie avvolta** e la si **registra** (massimo,
  media, 95° percentile), senza fermare lo step. La misura è una distanza
  punto-triangolo esatta su campioni fissi (deterministica), non
  `get_hausdorff_distance`, che è Montecarlo senza seme e sottostimava; passo
  di campionamento `max(tol/5, spigolo mediano)`. Il confronto è fra superfici,
  non contro la nuvola: l'errore contro la nuvola resta rimisurato e riportato
  dal punto A.4.
- **Metriche:** `wrap_applied: true`, `wrap_alpha_mm`, `wrap_offset_mm`,
  `wrap_hausdorff_max_mm` (i due versi), `wrap_hausdorff_mean_mm`,
  `wrap_hausdorff_p95_mm`, `wrap_volume_before`, `wrap_volume_after`,
  `wrap_seconds`, e la nota fissa «superficie sostituita, non riparata».
- **Riferimento dello step 11:** resta la superficie 06/08, non quella avvolta,
  così una ripresa dallo step 10/11 produce lo stesso deck della corsa unica.
- **Diagnosi:** il ramo `recoversubface` di `_diagnosi_del_guasto`
  (`volume.py:101-108`) oggi dice «la causa tipica sono le autointersezioni, il
  rimedio sta a monte». Diventa: autointersezioni **o** geometria quasi
  degenere che TetGen non recupera (ricerca §2.2), e propone
  `tet.wrap_tolerance` dicendo che la superficie viene sostituita e quanto
  costa (volume gonfiato, cavità più strette di alpha perse).
- **Interfaccia:** nessun codice UI; il campo compare nel pannello dal `Field`
  con il suo `title`, come gli altri di `TetConfig`.

## Errori e casi limite

- Superficie vuota o aperta: invariati, restano i controlli di
  `volume.tetrahedralize` (`volume.py:151-168`), che precedono il wrap.
- Wrap con uscita vuota o non chiusa: errore esplicito, niente TetGen.
- Wrap con autointersezioni residue (misurate 30 con α = 0,2 %, ricerca §5.1):
  si registrano e si prosegue verso TetGen senza pulizia; sul caso misurato
  TetGen ha chiuso lo stesso. Se TetGen fallisce, l'errore lo dice.
- `wrap_tolerance` ≤ 0: rifiutato dalla validazione pydantic (`gt=0.0`).

## Test

- Sfera con un polo spinto dentro la superficie (autointersezione nota; i due
  cubi compenetrati non servono, MeshFix li riduce a 7 vertici dichiarando
  successo): A la conta > 0, MeshFix la porta a 0, metriche scritte,
  `meshfix_clean_converged` vero.
- Superficie pulita: conteggio 0, nessuna pulizia, `meshfix_clean_converged`
  nullo, geometria invariata.
- Pulizia che non converge (surrogato del ritorno `False`): lo step fallisce con
  il conteggio residuo nel messaggio.
- Wrap su superficie sintetica: esce chiusa, TetGen termina, metriche scritte.
- Tolleranza più stretta della distanza misurata: nessun fallimento, massimo,
  media e 95° percentile registrati.
- `wrap_tolerance` assente o `None`: comportamento e impronte degli step 1-8
  invariati (memoria «togliere un campo sposta l'impronta»: verificare che
  aggiungere un campo con predefinito `None` non sposti le impronte esistenti).
- Ripresa dallo step 9 con rimisura: la nuvola viene caricata.
- A mano, una volta, fuori suite: `runs/geoandgeo-mm` con `wrap_tolerance`
  arriva al deck; tempi e distanze nel verbale della PR.

## Rischi

- Il wrap gonfia il volume (+3 % misurato) e perde cavità: accettato perché
  attivato solo dall'utente e dichiarato nel registro.
- Il conteggio PyMeshLab aggiunge 3-7 s allo step 9 su ogni corsa.
- Un solo caso reale misurato; la corsa è precedente all'HEAD `53647fd`.
