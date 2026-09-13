"""Modelli di configurazione: unico luogo dove un parametro ha un valore predefinito.

Sistema di unita di lavoro: mm, N, MPa, tonnellata, secondo.
"""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path, PurePath
from typing import Annotated, Literal

import yaml
from pydantic import (
    BaseModel,
    BeforeValidator,
    ConfigDict,
    Field,
    PlainSerializer,
    StringConstraints,
    model_validator,
)

NomeSet = Annotated[str, StringConstraints(pattern=r"^[A-Za-z0-9_.-]+$")]


def _separatori_posix(valore: object) -> object:
    if isinstance(valore, (str, PurePath)):
        return str(valore).replace("\\", "/")
    return valore


# Le stesse corse si aprono da Windows e da macOS: il file porta sempre `/`, e un
# `\` gia' scritto da Windows si legge come separatore anche dove non lo e'.
# Nessun nome di file del progetto contiene un `\` letterale (verificato il
# 13/09/2026), quindi la lettura non toglie niente a nessuno.
Percorso = Annotated[
    Path,
    BeforeValidator(_separatori_posix),
    PlainSerializer(lambda percorso: percorso.as_posix(), return_type=str, when_used="json"),
]


def _mappa_casefold(nomi: Iterable[str]) -> dict[str, str]:
    """`nome.casefold()` -> nome canonico: un solo spazio di nomi nel deck.

    `ccx` risolve gli `*NSET` senza distinguere le maiuscole (misurato in
    `docs/fase-6-cantiere/sonda-caso-nomi/README.md`): ogni punto che
    confronta un nome di set con un altro deve normalizzare il caso allo
    stesso modo, o due nomi che per `ccx` sono lo stesso `*NSET` passerebbero
    controlli diversi. Estratta perche' il confronto ricorre in due punti: le
    regioni (`_nomi_senza_collisioni`) e le superfici dei `*TIE` in
    `core/abaqus.py`, che la importa da qui.
    """
    return {nome.casefold(): nome for nome in nomi}


def _nomi_senza_collisioni(
    nomi: Iterable[str],
    soggetto: str,
    plurale: str,
    tipo_di_set: str,
    fabbricati: Iterable[str],
) -> None:
    """Rifiuta i nomi dell'operatore che il deck confonderebbe fra loro o coi propri.

    Nel deck c'e' un solo spazio di nomi per tipo di insieme, e `ccx` lo
    risolve senza distinguere le maiuscole (misurato in
    `docs/fase-6-cantiere/sonda-caso-nomi/README.md`): due chiavi distinte in
    un dizionario python possono essere un solo nome nel file.

    `fabbricati` sono i nomi che il deck si costruisce da se' **di quel tipo di
    insieme**, e sono un parametro e non la costante dei sei: i sei sono
    `*NSET` e una regione e' un `*ELSET`, cioe' due spazi di nomi distinti.
    Confrontare la famiglia sbagliata coi sei rifiutava la regione `BASE`, che
    non collide con niente, e accettava la regione `ALL_WALL`, che collide con
    l'insieme che le regioni partizionano.

    `soggetto` e `plurale` portano l'articolo con se' ("la regione", "le
    regioni"): il genere cambia col nome della famiglia, e un articolo fisso
    nel formato produceva «il regione», che si vede a video.
    """
    casi_fabbricati = _mappa_casefold(fabbricati)
    visti: dict[str, str] = {}
    for nome in nomi:
        chiave = nome.casefold()
        if chiave in casi_fabbricati:
            raise ValueError(
                f"{soggetto} {nome!r} collide, ignorando le maiuscole, con "
                f"l'insieme {casi_fabbricati[chiave]!r} che il deck fabbrica da "
                "sé: nel deck c'è un solo spazio di nomi per tipo di insieme, "
                "case-insensitive (vedi "
                "docs/fase-6-cantiere/sonda-caso-nomi/README.md), e il "
                f"{tipo_di_set} dell'operatore lo sovrascriverebbe"
            )
        if chiave in visti:
            raise ValueError(
                f"{plurale} {visti[chiave]!r} e {nome!r} differiscono solo per "
                "maiuscole: nel deck sono lo stesso nome, case-insensitive "
                "(vedi docs/fase-6-cantiere/sonda-caso-nomi/README.md)"
            )
        visti[chiave] = nome


class _ModelloBase(BaseModel):
    """Base comune a ogni modello del file: rifiuta infinito e NaN nei campi decimali.

    Un valore infinito battuto in un campo decimale dell'interfaccia arriva al
    server come stringa; senza questo vincolo pydantic lo legge come infinito
    e lo scrive sul disco come .inf, da cui /api/config non torna piu'
    indietro (risponde null su quel campo). Sta sulla base e non sul singolo
    modello apparso nel difetto: i campi decimali sono sparsi su piu' modelli,
    e allow_inf_nan=False sul modello sbagliato lascia gli altri esposti con
    l'aria di averli coperti. pydantic unisce model_config lungo la catena di
    ereditarieta', quindi RunConfig puo' ancora aggiungere
    validate_assignment=True senza perdere questo vincolo.
    """

    model_config = ConfigDict(allow_inf_nan=False)


class InputConfig(_ModelloBase):
    """Step 1: ingresso e scala."""

    path: Percorso = Field(title="file della nuvola di punti")
    scale: float = Field(
        default=1.0,
        gt=0.0,
        title="fattore di scala verso i millimetri",
    )
    max_points: int = Field(default=20_000_000, gt=0, title="punti massimi letti dal file")
    expected_size: tuple[float, float, float] | None = Field(
        default=None,
        title="dimensioni reali misurate",
        description="il controllo di scala dello step 1 le confronta con l'ingombro letto",
    )
    size_tolerance: float = Field(
        default=0.2,
        gt=0.0,
        title="scarto relativo ammesso sul controllo di scala",
    )
    spacing_sample: int = Field(
        default=20_000,
        gt=1,
        title="punti campionati per stimare la spaziatura",
    )
    seed: int = Field(default=0, title="seme del campionamento")


class SegmentConfig(_ModelloBase):
    """Step 2: segmentazione."""

    method: Literal["crop", "auto"] = Field(default="crop", title="come si isola l'oggetto")
    outlier_neighbors: int = Field(
        default=20,
        gt=0,
        title="vicini con cui si riconosce un punto isolato",
    )
    outlier_std_ratio: float = Field(
        default=2.0,
        gt=0.0,
        title="scarti tipo oltre i quali un punto è rumore",
    )
    crop_min: tuple[float, float, float] | None = Field(
        default=None, title="spigolo minimo del box di ritaglio [mm]"
    )
    crop_max: tuple[float, float, float] | None = Field(
        default=None, title="spigolo massimo del box di ritaglio [mm]"
    )
    plane_distance_factor: float = Field(
        default=3.0,
        gt=0.0,
        title="distanza dal piano, in multipli della spaziatura",
    )
    plane_max_count: int = Field(default=4, ge=0, title="piani estratti al massimo")
    plane_min_points_ratio: float = Field(
        default=0.05,
        gt=0.0,
        le=1.0,
        title="frazione minima di punti perché un piano conti",
    )
    cluster_eps_factor: float = Field(
        default=4.0,
        gt=0.0,
        title="raggio del gruppo, in multipli della spaziatura",
    )
    cluster_min_points: int = Field(default=50, gt=0, title="punti minimi perché un gruppo esista")
    cluster_index: int = Field(
        default=0,
        ge=0,
        description="0 è il gruppo più numeroso",
        title="quale gruppo si tiene",
    )


class DownsampleConfig(_ModelloBase):
    """Step 3: riduzione a voxel."""

    voxel_size: float | None = Field(
        default=None,
        description="vuoto: due volte la spaziatura media",
        title="lato del voxel [mm]",
    )
    voxel_factor: float = Field(
        default=2.0,
        gt=0.0,
        title="lato del voxel, in multipli della spaziatura",
    )


class NormalsConfig(_ModelloBase):
    """Step 4: normali."""

    knn: int = Field(default=30, gt=2, title="vicini con cui si stima la normale")
    orient_knn: int = Field(default=30, gt=2, title="vicini con cui si orientano le normali")


class SurfaceConfig(_ModelloBase):
    """Step 5: ricostruzione della superficie."""

    method: Literal["poisson"] = Field(default="poisson", title="algoritmo di ricostruzione")
    poisson_depth: int = Field(
        default=9,
        ge=4,
        le=14,
        title="profondità dell'ottree di Poisson",
        description=(
            "più alta, superficie più fitta: su muro, da 9 a 8 porta i triangoli "
            "da 908.118 a 221.369"
        ),
    )
    poisson_width: float = Field(default=0.0, ge=0.0, title="lato della cella più fine [mm]")
    poisson_scale: float = Field(default=1.1, gt=0.0, title="margine attorno alla nuvola")
    density_quantile: float = Field(
        default=0.05,
        ge=0.0,
        lt=1.0,
        title="quantile di densità sotto cui i vertici si scartano",
    )
    poisson_n_threads: int = Field(
        default=1, description="thread per il solutore Poisson; 1 = riproducibile, -1 = automatico",
        title="thread del solutore Poisson",
    )


class RepairConfig(_ModelloBase):
    """Step 6: riparazione."""

    largest_component_only: bool = Field(default=True, title="tiene il solo pezzo più grande")
    max_hole_area: float | None = Field(
        default=None,
        title="area oltre cui un'apertura viene segnalata [mm²]",
        description=(
            "vale sia per un ciclo di bordo chiuso sia per un cammino aperto"
        ),
    )
    join_components: bool = Field(default=False, title="unisce i pezzi staccati")


class SimplifyConfig(_ModelloBase):
    """Step 8: semplificazione, opzionale."""

    # `title` e' l'etichetta che il pannello mostra al posto della chiave:
    # «enabled» dice che si accende qualcosa senza dire che cosa, e il
    # rifacimento dei triangoli e' il piu' costoso degli step facoltativi.
    enabled: bool = Field(default=False, title="rifà i triangoli a misura uniforme")
    mode: Literal["remesh"] = Field(default="remesh", title="come si rifanno i triangoli")
    remesh_target_len_pct: float = Field(
        default=1.0,
        gt=0.0,
        title="lato del triangolo, in percentuale della diagonale",
    )
    taubin_iterations: int = Field(default=0, ge=0, title="passate di lisciatura Taubin")


class TetConfig(_ModelloBase):
    """Step 9: tetraedrizzazione."""

    min_ratio: float = Field(
        default=1.8,
        gt=0.0,
        title="rapporto raggio-spigolo massimo chiesto a TetGen",
        description=(
            "valori più bassi danno elementi più regolari, ma il raffinamento può "
            "non convergere su geometrie difficili. "
            "Sul muro di riferimento 1.6 e valori inferiori interrompono TetGen con un "
            "errore interno mentre 1.7 converge: il predefinito 1.8 non è quindi il "
            "valore più severo che porta a termine il lavoro, ma quello che tiene un "
            "decimo di margine sopra di esso. Misura completa da 1.4 a 2.5 in "
            "docs/fase-1-min-ratio.md"
        ),
    )
    max_volume: float | None = Field(
        default=None,
        gt=0.0,
        title="volume massimo dell'elemento [mm³]",
    )
    max_steiner_points: int = Field(
        default=-1,
        ge=-1,
        title="punti che TetGen può aggiungere",
        description=(
            "-1 = nessun limite. "
            "Il predefinito della libreria tetgen è 100000: su geometrie a scala "
            "reale quel tetto viene raggiunto e il raffinamento si ferma li, "
            "restituendo una mesh troncata che nessuna metrica segnalava"
        ),
    )
    nobisect: bool = Field(
        default=False,
        title="vieta a TetGen di suddividere le facce di ingresso",
        description=(
            "Serve dove la scala locale della superficie è minuscola: la "
            "suddivisione per invasione ricorre fino alla distanza fra lembi "
            "opposti, e su lab_frame.pcd, che ha strozzature sotto il millimetro, "
            "il raffinamento non converge a nessun min_ratio finché resta "
            "consentita. Attenzione: con nobisect attivo TetGen non aggiunge punti "
            "sul bordo, quindi su una superficie di ingresso grossolana max_volume "
            "può restare disatteso; il caso è segnalato con "
            "IneffectiveVolumeLimitWarning. Vedi docs/fase-1-min-ratio.md"
        ),
    )
    reference_ratio: float = Field(
        default=1.8,
        gt=0.0,
        title="metro con cui lo step 10 conta gli elementi fuori vincolo",
        description=(
            "metro fisso con cui lo step 10 conta la frazione di elementi fuori "
            "vincolo raggio-spigolo. Non è il vincolo chiesto a TetGen: nel "
            "motore di sweep min_ratio è una variabile della griglia, e una "
            "frazione contata contro il proprio min_ratio confronterebbe "
            "candidati contro vincoli diversi. Il valore 1.8 coincide con il "
            "predefinito di min_ratio perché è il metro con cui sono state "
            "misurate le due corse di riferimento (8,10% e 9,55%)"
        ),
    )
    element: Literal["C3D10", "C3D4"] = Field(
        default="C3D10",
        title="elemento del maglio di volume",
        description=(
            "C3D10 è il tetraedro quadratico ed è il predefinito: il manuale "
            "CalculiX dice del lineare «not suited for "
            "structural calculations... the element is too stiff», e la suite di "
            "verifica ufficiale non contiene un solo deck C3D4 su 610. C3D4 resta "
            "dichiarabile perché serve a misurare quanto quella rigidità costi su "
            "questa geometria"
        ),
    )


class ExportConfig(_ModelloBase):
    """Step 11: come si costruiscono gli insiemi di nodi delle facce."""

    set_tolerance_factor: float = Field(
        default=6.0,
        gt=0.0,
        title="tolleranza degli insiemi di faccia [multipli della spaziatura]",
        description=(
            "moltiplica la spaziatura dei nodi sul bordo del maglio di volume e "
            "dà la tolleranza con cui i set di faccia sono estratti. Il "
            "predefinito 6 è misurato: è il più piccolo intero che copre almeno "
            "il 95% della superficie d'appoggio su entrambe le corse di "
            "riferimento e per i quattro set utilizzabili. Il margine ha la "
            "stessa struttura di quello di tet.min_ratio: 5 è il primo valore "
            "che non regge (SIDE_LEFT di lab_crop si ferma al 94,37%), 4 il primo "
            "che crolla (77,89%), e sopra 6 si compra copertura marginale a "
            "prezzo pieno (a 8 il BASE del muro cresce del 41% per l'1,58% di "
            "copertura). Il predefinito precedente, 0,5 volte il volume medio "
            "dell'elemento, lasciava BASE al 55,78% della base sul muro e al "
            "34,76% su lab_crop. Vedi docs/fase-1-tolleranza-set.md"
        ),
    )


class RunConfig(_ModelloBase):
    """Esecuzione: percorsi e ripresa."""

    # La riga di comando e, in Fase 3, l'interfaccia assegnano questi campi
    # direttamente: senza validate_assignment pydantic non li verifica e un
    # valore fuori dominio arriva silenziosamente fino alla pipeline.
    model_config = ConfigDict(validate_assignment=True)

    out_dir: Percorso = Path("runs/default")
    from_step: int = Field(
        default=1,
        ge=1,
        le=12,
        description=(
            "la ripresa arriva fino allo step 12 (prior geometrico). Il tetto è "
            "stato 9 fino al 30/08/2026, quando gli step 10, 11 e 12 non erano "
            "punti di ripresa perché nessuno di loro ha lavoro costoso da "
            "saltare. Quel ragionamento valeva per una corsa intera e non per "
            "l'interfaccia, che esegue uno step alla volta assegnando "
            "from_step = to_step = numero: con il tetto a 9 quei tre step non "
            "erano eseguibili singolarmente, e il pannello rispondeva «Input "
            "should be less than or equal to 9» invece di eseguirli. "
            "Il solo prior ha anche la propria azione, `meshrec wall`."
        ),
    )
    to_step: int = Field(
        default=11,
        ge=1,
        le=12,
        description=(
            "ultimo step eseguito. Serve all'interfaccia, che esegue uno step "
            "alla volta: from_step e to_step uguali eseguono soltanto quello. "
            "Il tetto è 12, ma il predefinito è 11 e non coincide con esso: "
            "il prodotto va dalla nuvola al deck `.inp` e si chiude lì, mentre "
            "il prior geometrico dello step 12 misura la scansione e sta "
            "fuori dal perimetro. Il predefinito coincide quindi con l'ultimo "
            "artefatto che il prodotto promette, e una corsa senza argomenti "
            "non calcola più nulla che i documenti dichiarino fuori. Chi "
            "chiede il prior esplicitamente lo ottiene: la capacità non si "
            "perde, smette solo di essere ciò che accade senza chiederlo. "
            "Restano da conoscere le "
            "operazioni che il prior lo pretendono: l'attribuzione per regione "
            "dello step 11 quando la configurazione dichiara `regioni` (nessuna "
            "in casi/ lo fa oggi), `meshrec model`, e `meshrec compare` per la "
            "chiusura di volume. Tutte si "
            "sbloccano con `meshrec wall`, e non con una corsa chiesta fino a "
            "12: con `regioni` dichiarate lo step 11 legge il prior prima che "
            "lo step 12 lo scriva, quindi una corsa da 1 a 12 si ferma a 11 e non "
            "arriva mai a calcolarlo. "
            "sweep.py chiede to_step=11 esplicito al sottoprocesso invece di "
            "ereditare questo predefinito, e REQUIRED_STEPS in sweep.py non lo "
            "richiede: è una decisione del chiamante, che non deve dipendere "
            "da come il predefinito cambia. "
            "Con validate_assignment attivo il validatore incrociato rifiuta "
            "ogni stato intermedio incoerente, e nessun ordine di assegnazione "
            "è sicuro: restringendo un intervallo verso l'alto rompe to_step "
            "per primo, verso il basso rompe from_step. I due campi si "
            "assegnano quindi insieme, con una sola validazione dell'oggetto "
            "intero (RunConfig.model_validate su model_dump aggiornato), mai "
            "uno alla volta"
        ),
    )

    @model_validator(mode="after")
    def _intervallo_coerente(self) -> "RunConfig":
        if self.to_step < self.from_step:
            raise ValueError(f"to_step={self.to_step} precede from_step={self.from_step}")
        return self


class WallConfig(_ModelloBase):
    """Step 12: il prior geometrico. Il pezzo e' un telaio di membrature prismatiche.

    Nessun valore qui dentro viene dal provino di laboratorio. Le soglie sono
    angoli, frazioni e multipli della spaziatura media della nuvola: la
    grandezza sorvegliata e' la costanza dello spessore, non il suo valore, e
    una soglia di quota sarebbe una costante tarata sulla scansione di oggi
    (secondo principio di prodotto).
    """

    cell_factor: float = Field(
        default=4.0,
        gt=0.0,
        title="lato della cella, in multipli della spaziatura",
        description=(
            "È il «metodo delle colonne» di docs/fase-1-tolleranza-set.md, dove il "
            "fattore 4 è misurato e non scelto: con una cella larga quanto la "
            "spaziatura la griglia diventa più fine dei triangoli della faccia e "
            "una colonna su dieci risulta vuota per puro artefatto di griglia"
        ),
    )
    spacing_sample: int = Field(
        default=20_000,
        gt=1,
        title="punti campionati per la spaziatura locale",
        description=(
            "stessa semantica del campionamento dello step 1, ma per il riempimento della "
            "sezione: la spaziatura del pezzo intero non descrive una regione "
            "campionata più rada (più lontana dallo scanner, parzialmente "
            "occlusa), e usarla al posto di quella locale sposta la soglia sulla "
            "grandezza sbagliata"
        ),
    )
    seed: int = Field(default=0, title="seme del campionamento")
    """Seme del campionamento di spacing_sample, stessa semantica di input.seed."""
    thickness_tolerance: float = Field(
        default=0.15,
        gt=0.0,
        lt=1.0,
        title="scarto relativo entro cui lo spessore è lo stesso",
        description=(
            "due celle adiacenti dentro questo scarto sono la stessa membratura. "
            "È la forma numerica di "
            "«quasi costante»: le membrature sono le regioni connesse a spessore "
            "quasi costante, e questa è l'unica soglia della scomposizione"
        ),
    )
    min_cells: int = Field(
        default=12,
        gt=0,
        title="celle minime perché una regione sia una membratura",
        description=(
            "sotto questo numero la regione è rumore di griglia e non ha abbastanza "
            "celle perché una direzione principale sia stimabile"
        ),
    )
    floor_angle_deg: float = Field(
        default=15.0,
        gt=0.0,
        lt=90.0,
        title="angolo dalla verticale entro cui un piano è pavimento [°]",
        description=(
            "un piano estratto con la normale entro questo angolo dalla verticale "
            "è candidato pavimento. Il pavimento non è una membratura e va "
            "scartato come piano, mai come quota"
        ),
    )
    floor_min_ratio: float = Field(
        default=0.10,
        gt=0.0,
        le=1.0,
        title="frazione minima di punti perché un piano sia il pavimento",
        description=(
            "un piano quasi orizzontale ed esteso è il pavimento, non la faccia "
            "superiore di una membratura. Le due "
            "condizioni valgono insieme: orizzontale e esteso"
        ),
    )
    contour_tolerance: float = Field(
        default=5.0,
        gt=0.0,
        title="tolleranza con cui il contorno viene semplificato [mm]",
        description=(
            "tolleranza [mm] con cui il contorno di sezione misurato viene "
            "semplificato. Un contorno con un vertice per punto rilevato porta "
            "nella mesh il rumore dello scanner invece della forma della sezione"
        ),
    )
    parallelism_deg: float = Field(
        default=5.0,
        gt=0.0,
        lt=90.0,
        title="angolo massimo fra le due facce opposte [°]",
        description=(
            "controllo intrinseco: angolo massimo fra le due facce opposte di una "
            "regione. Oltre, la regione non ha una sezione e il prior si rifiuta "
            "invece di darne una media priva di senso"
        ),
    )
    face_coverage: float = Field(
        default=0.5,
        gt=0.0,
        le=1.0,
        title="frazione minima di celle che vedono entrambe le facce",
        description=(
            "controllo intrinseco: frazione minima delle celle della regione che "
            "vedono entrambe le facce. E' la lezione già pagata su FACE_FRONT e "
            "FACE_BACK: una faccia vista da pochi punti produce un piano finto"
        ),
    )
    section_dispersion: float = Field(
        default=0.10,
        gt=0.0,
        title="dispersione relativa massima della sezione lungo l'asse",
        description=(
            "controllo intrinseco: dispersione relativa massima della sezione "
            "lungo l'asse. Oltre, la regione non è un prisma e viene riportata "
            "come tale invece di essere spacciata per una membratura. E' l'unica "
            "difesa contro una sezione a Π riportata come (pieno, affidabile): "
            "riempimento e affidabilità misurano l'ingombro locale per fetta e "
            "non vedono due membrature uguali unite a Π, che restano piene di "
            "bounding box da un capo all'altro"
        ),
    )
    section_fill_ratio: float = Field(
        default=0.5,
        gt=0.0,
        le=1.0,
        title="confine fra sezione piena e sezione vuota",
        description=(
            "confine fra i due esiti «pieno» e «vuoto» del riempimento di "
            "sezione: frazione (mediana sulle fette lungo l'asse) delle celle "
            "del proprio ingombro locale che la sezione occupa davvero. "
            "L'estensione e la dispersione sono entrambe misure di bounding box "
            "e non vedono un vuoto interno -- due membrature identiche unite a Π "
            "restano piene di bounding box da un capo all'altro. Stessa "
            "convenzione di metà di face_coverage: sotto metà delle celle del "
            "proprio ingombro, l'ingombro non è la sezione ma il suo "
            "contenitore. Non scarta nulla: il riempimento è un esito "
            "dichiarato, e il rifiuto spetta a chi costruisce i modelli"
        ),
    )
    density_dispersion_limit: float = Field(
        default=1.0,
        gt=0.0,
        title="dispersione massima delle distanze al vicino più prossimo",
        description=(
            "condizione di validità della misura di riempimento, non criterio "
            "di qualità del pezzo: dispersione massima delle distanze al vicino "
            "più prossimo rispetto alla loro media. Sopra questo limite lo "
            "scarto tipo eguaglia la media, la media smette di essere la scala "
            "della nuvola, e la griglia costruita su di essa (cell_factor per la "
            "spaziatura) non risolve più la parte rada: il riempimento si "
            "dichiara «non verificabile» invece di dare un numero che misura il "
            "campionamento e non la sezione. Il valore uno è il confine fra "
            "«descrivibile da una media» e no, non un numero tarato su un caso: "
            "una nuvola a densità unica sta ben sotto (una griglia regolare dà "
            "zero, un campionamento casuale uniforme di superficie circa 0,52), "
            "una nuvola con una parte rada oltre cell_factor volte la media "
            "sta sopra"
        ),
    )
    union_tolerance: float = Field(
        default=0.02,
        gt=0.0,
        title="scarto ammesso fra somma dei volumi e volume dell'unione",
        description=(
            "controllo intrinseco: scarto relativo ammesso fra la somma dei "
            "volumi delle membrature e il volume della loro unione. Oltre c'è "
            "doppio conteggio alle giunzioni, che nessuna metrica di qualità "
            "vedrebbe"
        ),
    )
    union_step_factor: float = Field(
        default=2.0,
        gt=0.0,
        title="passo del conteggio di celle, in multipli della spaziatura",
        description=(
            "con questo passo si misura il volume dell'unione. Più fine, più "
            "lento e più preciso: l'errore di discretizzazione viene riportato "
            "accanto al risultato, non nascosto"
        ),
    )
    membrature_attese: int | None = Field(
        default=None,
        gt=0,
        title="membrature attese, facoltativo",
        description=(
            "RISCONTRO DICHIARATO, facoltativo: quante membrature l'operatore si "
            "aspetta. Assente per definizione su un pezzo nuovo. Se dichiarato il "
            "prior riporta lo scarto; se assente riporta ciò che ha trovato e "
            "non inventa un'aspettativa"
        ),
    )
    sezioni_nominali: list[tuple[float, float]] | None = Field(
        default=None,
        title="sezioni nominali attese [mm], facoltativo",
        description=(
            "RISCONTRO DICHIARATO, facoltativo: le sezioni nominali attese [mm], "
            "dal disegno se esiste. Non sono la fonte del modello: i modelli "
            "parametrici misurano la sezione sulla nuvola, e il nominale serve "
            "solo a contraddire la misura"
        ),
    )
    volume_atteso: float | None = Field(
        default=None,
        gt=0.0,
        title="volume complessivo atteso [mm³], facoltativo",
        description=(
            "RISCONTRO DICHIARATO, facoltativo: il volume complessivo atteso "
            "[mm³], dal disegno se esiste"
        ),
    )


class ModelConfig(_ModelloBase):
    """I due modelli parametrici e il loro deck. Non e' letto da alcuno step di run().

    La scelta di quali modelli generare non sta qui, ed e' deliberato: e'
    un'azione, non un parametro di elaborazione. Se ci stesse, rigenerare un
    modello in piu' cambierebbe l'impronta di una corsa che non e' cambiata.
    """

    element: Literal["C3D8I", "C3D8", "C3D8R"] = Field(
        default="C3D8I",
        description=(
            "un telaio lavora a flessione. C3D8 a integrazione piena si "
            "irrigidisce a taglio e restituisce spostamenti troppo piccoli, un "
            "errore invisibile guardando la mesh; C3D8R ha il problema opposto, i "
            "modi a clessidra. C3D8I è supportato sia da Abaqus sia da CalculiX"
        ),
    )
    min_layers: int = Field(
        default=3,
        ge=3,
        description=(
            "strati di elementi minimi nello spessore, imposti dal codice e non "
            "suggeriti. Con uno o due la flessione nello spessore non è "
            "rappresentata e il risultato è sbagliato senza alcun segnale. Il "
            "vincolo ge=3 è il vincolo stesso: non si scende sotto"
        ),
    )
    target_size: float | None = Field(
        default=None,
        gt=0.0,
        description=(
            "passo caratteristico della mesh [mm]. None = la sezione minima "
            "divisa per min_layers, cioè il passo più grosso che rispetta il "
            "vincolo degli strati"
        ),
    )
    tie_name_prefix: NomeSet = Field(
        default="GIUNZIONE",
        description=(
            "prefisso dei nomi dei vincoli *TIE fra membrature adiacenti. Stesso "
            "vincolo di caratteri del nome del materiale, e per la stessa "
            "ragione: finisce interpolato in un deck scritto in ascii"
        ),
    )


# I sei nomi che `abaqus.build_node_sets` fabbrica a ogni esportazione.
# Stanno qui e non in `core/abaqus.py` perche' la validazione della
# configurazione deve conoscerli e `abaqus` importa gia' `config`: l'altro
# verso sarebbe un ciclo. `build_node_sets` **non** li importa da qui: e' un
# dizionario letterale che li riscrive, per tenere ogni nome sulla riga del
# proprio criterio geometrico (il perche' e' scritto li'). L'accordo fra le
# due liste lo tengono due test, non il tipo: se questa costante cambia e
# quel dizionario no, sono loro a dirlo.
NOMI_SET_DI_FACCIA: tuple[str, ...] = (
    "BASE", "TOP", "FACE_FRONT", "FACE_BACK", "SIDE_LEFT", "SIDE_RIGHT",
)

# L'unico `*ELSET` che il deck fabbrica da se': il parametro `elset` di
# `abaqus.write_inp`, che vale "ALL_WALL" e finisce sia sulla card `*ELEMENT`
# sia sulla `*SOLID SECTION`. E' l'insieme che le regioni partizionano, quindi
# una regione omonima farebbe prendere alla `*SOLID SECTION` la partizione
# sbagliata e il muro intero riceverebbe il materiale di quella regione.
#
# Sta in una costante propria e non insieme ai sei perche' e' un tipo di
# insieme diverso: i sei sono `*NSET`, questo e' un `*ELSET`, e nel deck sono
# due spazi di nomi distinti. Confrontare una famiglia con i nomi fabbricati
# dell'altra rifiuta il nome innocuo e lascia passare quello che collide.
NOMI_ELSET_FABBRICATI: tuple[str, ...] = ("ALL_WALL",)


class RegioneConfig(_ModelloBase):
    """Un prisma di membratura, e nient'altro.

    Il nome della regione e' la chiave del dizionario `PipelineConfig.regioni`,
    e diventa un `*ELSET` nel deck: e' per questo che le chiavi seguono le
    regole di nome degli insiemi (`_nomi_senza_collisioni`).

    Portava una `sezione` con tre materiali -- nucleo confinato, copriferro,
    acciaio -- e l'armatura, perche' una sezione a fibre se li porta dentro.
    Uscito il solutore a fibre con la mappa #161, di quei quattro il deck ne
    leggeva uno. Dal 08/09/2026 non ne legge piu' nessuno: il deck e' nudo, e
    il materiale si assegna in Abaqus sull'`*ELSET` che la regione produce.
    Resta il solo indice del prisma.
    """

    membratura: int = Field(
        ge=0,
        description=(
            "indice della membratura nel prior geometrico (`12_wall.json`). Il "
            "tetto -- quante membrature il prior ha davvero trovato -- non è "
            "verificabile qui: la configurazione nasce prima che lo step 12 giri, "
            "e il rifiuto dell'indice fuori intervallo spetta a chi legge il prior"
        ),
    )

    @model_validator(mode="before")
    @classmethod
    def _rifiuta_il_materiale(cls, dati: object) -> object:
        """Un `config.yaml` scritto prima del 08/09/2026 porta ancora il campo.

        Senza questo rifiuto la chiave non e' un errore: pydantic ignora cio'
        che il modello non dichiara, la corsa parte e il materiale scritto
        dall'operatore non arriva in nessun deck. Un file che cambia
        significato in silenzio e' peggio di un file rifiutato.

        Il messaggio non nomina la regione: la chiave del dizionario la
        conosce solo chi valida il blocco, e pydantic la mette da se' nel
        percorso dell'errore (`regioni.<nome>`).
        """
        if isinstance(dati, dict) and "materiale" in dati:
            raise ValueError(
                "il campo `materiale` di una regione non esiste più (08/09/2026, "
                "PR feat/deck-nudo-analisi): il materiale si assegna in Abaqus "
                "sull'`*ELSET`"
            )
        return dati


# I blocchi che una `config.yaml` gia' su disco porta ancora e che la
# configurazione non ha piu'. Non si ignorano come gli altri campi estranei:
# dichiaravano il materiale, i carichi e i selettori, cioe' cosa il deck
# doveva contenere, e un file che li porta descrive una corsa che il programma
# non esegue piu'. Ignorarli darebbe un deck diverso da quello che il file
# dichiara, senza un segnale. Il motivo dice la data, la PR e -- dove esiste --
# dove il parametro sopravvissuto e' andato a stare: e' l'unica cosa che chi
# legge il rifiuto puo' fare.
#
# `solutore` (mappa #161) resta ignorato: nessun file lo porta, nessun
# parametro e' migrato altrove; se un giorno entra `extra="forbid"` (ADR,
# approccio C) lo prende quello.
BLOCCHI_RIMOSSI: dict[str, str] = {
    "analysis": (
        "08/09/2026, PR feat/deck-nudo-analisi: materiali, vincoli e carichi si "
        "assegnano in Abaqus sul deck; `set_tolerance_factor` sta ora in `export`"
    ),
    "carichi": (
        "08/09/2026, PR #190: il deck nudo non scrive passi di carico, e spinta "
        "e carico di sommità si assegnano in Abaqus"
    ),
    "selettori": (
        "08/09/2026, PR #190: i selettori nominavano i nodi dei carichi, e sono "
        "usciti con loro"
    ),
}


class PipelineConfig(_ModelloBase):
    """Configurazione completa di un'elaborazione."""

    input: InputConfig
    segment: SegmentConfig = Field(default_factory=SegmentConfig)
    downsample: DownsampleConfig = Field(default_factory=DownsampleConfig)
    normals: NormalsConfig = Field(default_factory=NormalsConfig)
    surface: SurfaceConfig = Field(default_factory=SurfaceConfig)
    repair: RepairConfig = Field(default_factory=RepairConfig)
    simplify: SimplifyConfig = Field(default_factory=SimplifyConfig)
    tet: TetConfig = Field(default_factory=TetConfig)
    export: ExportConfig = Field(default_factory=ExportConfig)
    wall: WallConfig = Field(default_factory=WallConfig)
    model: ModelConfig = Field(default_factory=ModelConfig)
    regioni: dict[NomeSet, RegioneConfig] = Field(
        default_factory=dict,
        description=(
            "le regioni in cui il pezzo è partizionato, ciascuna con la propria "
            "sezione e i propri materiali. Un dizionario a chiavi libere e non un "
            "modello con campi: il nome della regione lo sceglie l'operatore e "
            "diventa un `*ELSET` nel deck. La forma a dizionario è anche ciò che "
            "tiene ferma l'impronta delle corse già registrate: nasce `{}`, cioè "
            "falso, e `sweep.fingerprint` lo omette finché resta vuoto"
        ),
    )

    @model_validator(mode="before")
    @classmethod
    def _rifiuta_i_blocchi_rimossi(cls, dati: object) -> object:
        """Un blocco tolto si rifiuta per nome, e tutti in un messaggio solo.

        Conta la chiave e non il valore: `analysis: null` e' la forma che ogni
        corsa nata dall'interfaccia porta su disco, ed e' il caso piu'
        frequente, non il piu' raro.

        Un rifiuto per blocco costerebbe una corsa a blocco --
        `runs/geoandgeo-lab/config.yaml` porta `analysis:` e `carichi:`, si
        toglierebbe il primo e si scoprirebbe il secondo al giro dopo. Qui si
        raccolgono tutti e si nominano insieme.
        """
        if isinstance(dati, dict):
            trovati = [
                f"`{blocco}` non esiste più ({motivo})"
                for blocco, motivo in BLOCCHI_RIMOSSI.items()
                if blocco in dati
            ]
            if trovati:
                raise ValueError(
                    "questo config.yaml porta blocchi tolti dalla configurazione: "
                    + "; ".join(trovati)
                    + ". Vanno tolti dal file: il programma non li legge più"
                )
        return dati

    @model_validator(mode="after")
    def _i_nomi_delle_regioni_non_collidono_con_all_wall(self) -> "PipelineConfig":
        """I nomi delle regioni non collidono con l'`*ELSET` fabbricato.

        Il nome di una regione diventa un `*ELSET` nel deck, e `ccx` risolve
        anche quelli senza distinguere le maiuscole -- per analogia con la
        sonda, non misurato: `docs/fase-6-cantiere/sonda-caso-nomi/` dichiara
        due `*NSET` e nessun `*ELSET` di prova, quindi la regola qui e'
        conservativa nella direzione giusta ma non poggia su una misura.

        I nomi fabbricati confrontati sono quelli degli `*ELSET`, cioe'
        `ALL_WALL` e non i sei di faccia: quelli sono `*NSET`, e nel deck sono
        un altro spazio di nomi.
        """
        _nomi_senza_collisioni(
            self.regioni, "la regione", "le regioni", "*ELSET", NOMI_ELSET_FABBRICATI
        )
        return self

    run: RunConfig = Field(default_factory=RunConfig)


class _LoaderChiaviUniche(yaml.SafeLoader):
    """`SafeLoader` che rifiuta due chiavi omonime invece di tenere l'ultima.

    Misurato: con il loader di serie la prima delle due sparisce senza alcun
    segnale. E' l'unico ingresso degenere che non ha un sintomo -- gli altri
    almeno risolvono zero nodi -- e per questo si rifiuta alla lettura invece
    che a valle.

    Deriva da `yaml.SafeLoader` e ne eredita i costruttori: nessun tag
    `!!python/object`, nessuna costruzione di tipi arbitrari. Aggiunge un
    controllo, non toglie un divieto.
    """

    def construct_mapping(self, node, deep=False):  # type: ignore[override]
        viste: set[object] = set()
        for chiave_node, _ in node.value:
            chiave = self.construct_object(chiave_node, deep=deep)
            if chiave in viste:
                raise ValueError(
                    f"la chiave '{chiave}' compare due volte nello stesso blocco "
                    f"({chiave_node.start_mark}): il lettore terrebbe l'ultima e la "
                    "prima sparirebbe senza un segnale"
                )
            viste.add(chiave)
        return super().construct_mapping(node, deep=deep)


def carica_yaml_da_testo(testo: str) -> object:
    """Come `carica_yaml`, ma su un testo che non e' ancora un file.

    Esiste perche' chi vuole sapere in anticipo se un testo diventera' un
    `config.yaml` valido deve usare **lo stesso** lettore che quel file
    rileggera'. Con `yaml.safe_load` la prova era piu' permissiva del
    controllo vero: le chiavi omonime passavano di qui e venivano respinte
    solo dopo, a file gia' riscritto -- cioe' proprio l'ingresso degenere per
    cui `_LoaderChiaviUniche` esiste, e il solo che non ha altro sintomo.

    `yaml.load` con un loader che **eredita da SafeLoader** ha esattamente i
    costruttori di `safe_load`. Non sostituire il loader con `yaml.Loader` o
    `yaml.UnsafeLoader`, che i tag `!!python/object` li eseguono davvero.
    """
    return yaml.load(testo, Loader=_LoaderChiaviUniche)  # noqa: S506


def carica_yaml(path: Path) -> object:
    """L'unica lettura YAML del modulo, con il rifiuto delle chiavi omonime.

    Passa dal gemello su testo per costruzione: due lettori separati potevano
    divergere in silenzio, e lo avevano gia' fatto.
    """
    return carica_yaml_da_testo(Path(path).read_text(encoding="utf-8"))


def load_config(path: Path) -> PipelineConfig:
    """Legge un config.yaml senza perdita rispetto a quanto scritto da `save_config`."""
    return PipelineConfig.model_validate(carica_yaml(path))


def save_config(cfg: PipelineConfig, path: Path) -> None:
    """Scrive la configurazione completa, compresi i valori lasciati ai predefiniti."""
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with Path(path).open("w", encoding="utf-8") as handle:
        yaml.safe_dump(cfg.model_dump(mode="json"), handle, sort_keys=False, allow_unicode=True)


class SweepConfig(_ModelloBase):
    """Motore di sweep: risorse di macchina e politica sugli artefatti."""

    workers: int = Field(
        default=4,
        gt=0,
        description=(
            "candidati in volo insieme, come processi separati. Non è il numero "
            "di processori: TetGen ha un picco misurato di 1,35 GB sulla corsa "
            "del muro e la macchina di sviluppo ha 7 GB liberi, quindi quattro "
            "candidati sono circa 5,4 GB di picco. Va tarato sulla macchina che "
            "esegue: nessun valore dedotto dai processori logici è corretto qui"
        ),
    )
    timeout_s: float = Field(
        default=1800.0,
        gt=0.0,
        description=(
            "tetto al tempo di un singolo candidato, perché uno patologico non "
            "blocchi lo sweep. La corsa completa più lenta documentata vale 134 s "
            "e il singolo step più lento 186 s: è un tetto contro il patologico, "
            "non contro il lento"
        ),
    )
    runs_root: Percorso = Path("runs")
    registry_root: Percorso = Path("experiments")
    keep_dominated_artifacts: bool = Field(
        default=False,
        description=(
            "gli artefatti dei candidati dominati vengono rimossi a sweep "
            "concluso; config.yaml e metrics.json restano sempre. Una corsa "
            "completa pesa circa 300 MB"
        ),
    )


class AxisSpec(_ModelloBase):
    """Un asse della griglia: il percorso puntato del parametro e i suoi livelli."""

    path: str = Field(description="percorso puntato dentro PipelineConfig, es. tet.min_ratio")
    values: list[float | int | bool | None] = Field(min_length=1)


class ExperimentConfig(_ModelloBase):
    """Dichiarazione di un esperimento. Tracciata da git accanto al proprio registro."""

    name: str
    base: Percorso = Field(
        description=(
            "configurazione di partenza, es. casi/muro.yaml. Risolta rispetto alla "
            "cartella da cui gira il programma, non rispetto a questo file"
        )
    )
    axes: list[AxisSpec] = Field(min_length=1)
    pairs: list[tuple[str, str]] = Field(
        default_factory=list,
        description=(
            "coppie di assi da incrociare in fattoriale, oltre allo sweep a un "
            "asse alla volta. Si dichiarano solo le coppie che la misura mostra "
            "interagenti: un fattoriale pieno sui cinque assi della griglia "
            "reale (3x3x3x4x2 livelli) sono 216 candidati"
        ),
    )
    known_thickness: float | None = Field(
        default=None,
        description=(
            "spessore reale misurato [mm], contro cui si controlla la misura "
            "letta sulla nuvola sorgente. E' il controllo che smentisce l'asse "
            "di fedeltà"
        ),
    )
    sweep: SweepConfig = Field(default_factory=SweepConfig)


def load_experiment(path: Path) -> ExperimentConfig:
    """Legge la dichiarazione di un esperimento."""
    return ExperimentConfig.model_validate(carica_yaml(path))


class ViewportConfig(_ModelloBase):
    """Disegno nel browser. Non entra in PipelineConfig: vedi la nota sotto.

    Aggiungere un campo a PipelineConfig cambierebbe sweep.fingerprint e quindi
    l'impronta di ogni riga gia' scritta nei registri della Fase 2, che sono la
    tabella sperimentale della tesi. Questi parametri governano il disegno e non
    l'elaborazione, quindi restano fuori.
    """

    max_points: int = Field(
        default=400_000,
        gt=0,
        description=(
            "punti al massimo inviati al browser per il disegno. 400.000 punti "
            "sono 4,8 MB in Float32, dell'ordine di 04_normals.ply di lab_crop "
            "(5.571.038 byte), un artefatto che la pipeline scrive e rilegge a "
            "ogni corsa. Non è un limite grafico ma di trasporto"
        ),
    )


class ServerConfig(_ModelloBase):
    """Server locale. Utente singolo, nessuna autenticazione."""

    host: str = "127.0.0.1"
    port: int = Field(default=8765, gt=0, le=65535)
    open_browser: bool = True
