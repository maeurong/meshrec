// Come si intitola ogni riga delle due tabelle di qualita', e in che unita'.
//
// La regola non e' nuova in questo repository: `core/report.py` la applica gia'
// con `_COLUMNS` e `_ETICHETTE_GRANDEZZE` -- «una chiave non si stampa mai, si
// stampa la sua etichetta», e l'unita' sta DENTRO l'etichetta perche' un numero
// senza unita' non si ricostruisce. Mancava proprio sulla superficie che viene
// proiettata in discussione: qui il pannello stampava `geometric_error ·
// cloud_to_mesh · mean` accanto a `4,41`, senza dire ne' che cos'e' ne' se sono
// millimetri.
//
// Solo lo step 7 e il 10, e non tutti e dodici: sono le due tabelle su cui si
// decide se una configurazione va tenuta, e le altre restano chiavi finche'
// qualcuno non ne ha bisogno. Una chiave senza etichetta non sparisce e non
// prende un nome inventato -- si stampa com'e', come `nomeDelloStep` fa con uno
// step che non conosce.
//
// Quello che NON si traduce: `min_ratio`, `nobisect`, `C3D10` e compagnia sono
// identificatori dichiarati in PRODUCT.md, non parole, e non stanno qui dentro.
// `RMS` resta `RMS` per la stessa ragione.
//
// I due versi si dicono per esteso e non con una freccia: la stessa frase che
// la didascalia dello scarto porta sotto la vista, cosi' il pannello e
// l'immagine nominano la stessa grandezza allo stesso modo.
// Undici step e non dodici: il prior geometrico (`12_wall`) non ha pannello --
// `disegnaStep` lo filtra e PRODUCT.md dichiara che sta fuori dall'interfaccia
// -- quindi una tabella per lui sarebbe etichette per righe che nessuno mostra.
//
// Modulo senza import apposta: e' cosi' che `_etichette_metriche()` lo valuta
// con `node`, da solo, senza un server che gli serva anche `app.js`.

// Le sei righe che 05, 06, 07 e 08 condividono, piu' le cinque righe
// dell'aspetto: `pipeline._con_le_misure_della_superficie` le aggiunge a ogni
// step che scrive una superficie, perche' il pannello del modello sappia dire
// «aperta» anche su un fronte che si ferma li'. Le stesse chiavi vogliono le
// stesse etichette, e ricopiarle a mano in quattro punti e' proprio la
// divergenza che questa costante toglie.
const SUPERFICIE = {
  vertices: "vertici",
  triangles: "triangoli",
  watertight: "superficie chiusa",
  boundary_edges: "spigoli di bordo",
  area: "area della superficie [mm²]",
  volume: "volume racchiuso [mm³]",
  "aspect_ratio · min": "rapporto d'aspetto dei triangoli, minimo",
  "aspect_ratio · median": "rapporto d'aspetto dei triangoli, mediano",
  "aspect_ratio · mean": "rapporto d'aspetto dei triangoli, medio",
  "aspect_ratio · max": "rapporto d'aspetto dei triangoli, massimo",
  "aspect_ratio · non_finite": "triangoli con aspetto non misurabile",
};

// Lo scarto dalla nuvola: lo step 7 lo misura, il 9 lo rimisura quando la
// superficie cambia. Stesse chiavi, stesse etichette, una sola copia.
const SCARTO = {
  "geometric_error · hausdorff": "scarto di Hausdorff [mm]",
  // I due versi non sono la stessa misura e non danno lo stesso numero: nel
  // verso dalla nuvola alla superficie i campioni sono i punti della nuvola
  // contro le facce, nell'altro sono i soli vertici contro la nuvola. Sono
  // 4,897 mm contro 3,898 su lab_crop, e una tabella che li chiamasse
  // entrambi «scarto» lascerebbe scegliere il piu' comodo.
  "geometric_error · cloud_to_mesh · min": "scarto dalla nuvola alla superficie, minimo [mm]",
  "geometric_error · cloud_to_mesh · mean": "scarto dalla nuvola alla superficie, medio [mm]",
  "geometric_error · cloud_to_mesh · max": "scarto dalla nuvola alla superficie, massimo [mm]",
  "geometric_error · cloud_to_mesh · RMS": "scarto dalla nuvola alla superficie, RMS [mm]",
  "geometric_error · cloud_to_mesh · n_samples": "campioni dalla nuvola alla superficie",
  "geometric_error · mesh_to_cloud · min": "scarto dalla superficie alla nuvola, minimo [mm]",
  "geometric_error · mesh_to_cloud · mean": "scarto dalla superficie alla nuvola, medio [mm]",
  "geometric_error · mesh_to_cloud · max": "scarto dalla superficie alla nuvola, massimo [mm]",
  "geometric_error · mesh_to_cloud · RMS": "scarto dalla superficie alla nuvola, RMS [mm]",
  "geometric_error · mesh_to_cloud · n_samples": "campioni dalla superficie alla nuvola",
  // Le diagonali dei due ingombri: le scrive PyMeshLab dentro lo stesso
  // dizionario, e sono la scala rispetto a cui il suo scarto si legge.
  "geometric_error · cloud_to_mesh · diag_mesh_0": "diagonale d'ingombro della superficie [mm]",
  "geometric_error · cloud_to_mesh · diag_mesh_1": "diagonale d'ingombro della nuvola [mm]",
  "geometric_error · mesh_to_cloud · diag_mesh_0": "diagonale d'ingombro della superficie [mm]",
  "geometric_error · mesh_to_cloud · diag_mesh_1": "diagonale d'ingombro della nuvola [mm]",
};

export const ETICHETTE_METRICHE = {
  "01_load": {
    "points_read": "punti letti",
    "points_kept": "punti tenuti",
    "points_dropped": "punti scartati (non finiti)",
    "spacing": "spaziatura media [mm]",
    "extent": "ingombro [mm]",
    "bbox_min": "angolo minimo [mm]",
    "bbox_max": "angolo massimo [mm]",
    "scale": "fattore di scala",
    "size_check": "controllo dell'ingombro atteso",
  },
  "02_segment": {
    "points_before": "punti in ingresso",
    "points_after": "punti tenuti",
    "outliers_removed": "punti tolti come rumore",
    "cropped": "ritagliato",
    "cropped_points": "punti ritagliati",
    "cropped_fraction": "frazione ritagliata",
    "cropped_by_face": "punti ritagliati per faccia",
    "method": "metodo",
  },
  "03_downsample": {
    "points_before": "punti in ingresso",
    "points_after": "punti tenuti",
    "voxel_size": "lato del voxel [mm]",
    "reduction": "riduzione",
  },
  "04_normals": {
    "knn": "vicini per la normale",
    "orient_knn": "vicini per l'orientamento",
    "degenerate_normals": "normali degeneri",
    "spacing": "spaziatura usata [mm]",
  },
  "05_reconstruct": {
    ...SUPERFICIE,
    "method": "metodo",
    "density_threshold": "soglia di densità",
    "vertices_trimmed": "vertici potati",
  },
  "06_repair": {
    ...SUPERFICIE,
    "watertight_after": "chiusa dopo la riparazione",
    "volume_before": "volume prima [mm³]",
    "volume_after": "volume dopo [mm³]",
    "components_before": "componenti prima",
    "components_kept": "componenti tenute",
    "holes_before": "fori prima",
    "holes_over_threshold": "fori oltre la soglia, lasciati aperti",
    "open_boundary_paths": "bordi aperti",
    "open_paths_over_threshold": "bordi aperti oltre la soglia",
    "degenerate_faces_removed": "facce degeneri tolte",
    "duplicate_faces_removed": "facce duplicate tolte",
    "duplicate_vertices_merged": "vertici duplicati fusi",
    "orphan_vertices_removed": "vertici orfani tolti",
    "orientation_flipped": "orientamento rigirato",
  },
  "07_surface_quality": {
    ...SUPERFICIE,
    ...SCARTO,
  },
  "08_simplify": {
    "enabled": "abilitata",
    "mode": "modo",
    "triangles_before": "triangoli prima",
    "triangles_after": "triangoli dopo",
    ...SUPERFICIE,
  },
  "09_tetrahedralize": {
    "nodes": "nodi",
    "tets": "tetraedri",
    "element": "elemento",
    "steiner_points": "punti di Steiner inseriti",
    "max_steiner_points": "punti di Steiner concessi",
    "steiner_saturated": "punti di Steiner esauriti: mesh troncata",
    "radius_edge_ratio_p99": "raggio-spigolo, 99º percentile",
    "radius_edge_ratio_over_limit": "tetraedri oltre il limite raggio-spigolo",
    "largest_element_volume": "volume dell'elemento più grande [mm³]",
    "min_ratio": "rapporto minimo chiesto",
    "max_volume": "volume massimo chiesto [mm³]",
    "nobisect": "senza bisezione",
    "seconds": "durata [s]",
    "self_intersections_before": "facce autointersecanti in ingresso",
    "self_intersections_after": "facce autointersecanti consegnate a TetGen",
    "meshfix_clean_converged": "convergenza dichiarata da MeshFix",
    "triangles_removed_by_clean": "triangoli tolti dalla pulizia",
    "wrap_applied": "superficie sostituita dall'alpha wrap",
    "wrap_alpha_mm": "alpha del wrap [mm]",
    "wrap_offset_mm": "offset del wrap [mm]",
    // Lo spostamento si registra e non ferma lo step: il massimo viene dalle
    // cavita' piu' strette di alpha, che il wrap chiude per costruzione.
    "wrap_hausdorff_max_mm": "spostamento del wrap, massimo [mm]",
    "wrap_hausdorff_mean_mm": "spostamento del wrap, medio [mm]",
    "wrap_hausdorff_p95_mm": "spostamento del wrap, 95º percentile [mm]",
    "wrap_volume_before": "volume prima del wrap [mm³]",
    "wrap_volume_after": "volume dopo il wrap [mm³]",
    "wrap_seconds": "durata del wrap [s]",
    "wrap_note": "nota sul wrap",
    // Stesse grandezze dello step 7, rimisurate sulla superficie che TetGen
    // ha riempito quando lo step 8 o la preparazione l'hanno cambiata.
    ...SCARTO,
  },
  "10_volume_quality": {
    "nodes": "nodi",
    "tets": "tetraedri",
    "inverted": "elementi invertiti",
    "total_volume": "volume totale [mm³]",
    "element_volume · min": "volume dell'elemento, minimo [mm³]",
    "element_volume · median": "volume dell'elemento, mediano [mm³]",
    "element_volume · mean": "volume dell'elemento, medio [mm³]",
    "element_volume · max": "volume dell'elemento, massimo [mm³]",
    "element_volume · non_finite": "elementi con volume non misurabile",
    "min_dihedral_deg · min": "diedro minimo, il peggiore [gradi]",
    "min_dihedral_deg · median": "diedro minimo, mediano [gradi]",
    "min_dihedral_deg · mean": "diedro minimo, medio [gradi]",
    "min_dihedral_deg · max": "diedro minimo, il migliore [gradi]",
    "min_dihedral_deg · non_finite": "elementi con diedro non misurabile",
    "aspect_ratio · min": "rapporto d'aspetto dei tetraedri, minimo",
    "aspect_ratio · median": "rapporto d'aspetto dei tetraedri, mediano",
    "aspect_ratio · mean": "rapporto d'aspetto dei tetraedri, medio",
    "aspect_ratio · max": "rapporto d'aspetto dei tetraedri, massimo",
    "aspect_ratio · non_finite": "tetraedri con aspetto non misurabile",
    "radius_edge_ratio · min": "rapporto raggio-spigolo, minimo",
    "radius_edge_ratio · median": "rapporto raggio-spigolo, mediano",
    "radius_edge_ratio · mean": "rapporto raggio-spigolo, medio",
    "radius_edge_ratio · max": "rapporto raggio-spigolo, massimo",
    "radius_edge_ratio · non_finite": "tetraedri con raggio-spigolo non misurabile",
    // «frazione» e non «%»: il dato non si tocca -- vale 0,08098 e non 8,098 --
    // e un'etichetta in percento sopra una frazione e' la stessa bugia con un
    // sintomo peggiore. La grafia viene da _COLUMNS in core/report.py, dove
    // questa stessa grandezza si intitola gia' «fuori vincolo [frazione]».
    "radius_edge_over_reference": "elementi oltre il metro di riferimento [frazione]",
    "reference_ratio": "metro di riferimento del raggio-spigolo",
  },
  "11_export": {
    "element_type": "tipo di elemento",
    "inp": "deck scritto",
    "vtu": "vtu scritto",
    "volume": "volume [mm³]",
    "surface_area": "area della superficie [mm²]",
    "extent": "ingombro [mm]",
    "fixed_nset_coverage": "copertura della base",
    "boundary_spacing": "spaziatura al contorno [mm]",
    "set_tolerance": "tolleranza dei set [mm]",
  },
};

// Le metriche il cui «sì» e' una contraddizione, non una conferma.
//
// Un booleano vero non e' di per se' un allarme: `watertight` vero e'
// esattamente cio' che si spera. Decide il set, non il tipo del valore.
export const METRICHE_D_ALLARME = new Set(["steiner_saturated"]);
