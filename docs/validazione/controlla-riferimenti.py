#!/usr/bin/env python
"""Verifica che i riferimenti di un documento risolvano ancora.

    python docs/validazione/controlla-riferimenti.py docs/validazione/inventario-grandezze.md
    python docs/validazione/controlla-riferimenti.py --autoprova

Due forme, controllate insieme:

- `` `file.py:riga` `` -- la forma per numero. Slitta a ogni merge.
- `` `modulo.simbolo` `` -- la forma per nome, `quality.mesh_volume`,
  `solve.controlla_reazioni`, `config.ExportConfig.set_tolerance_factor`. Un nome non
  slitta, e questa e' la forma da preferire ovunque un simbolo esista.

Ordina cio' che trova in **tre** categorie, e solo la prima e' un difetto:

- **rotti** -- il file sta nell'albero e la riga non c'e', oppure il modulo sta
  nell'albero e non definisce quel nome (o il nome del file e' ambiguo).
  Uscita 1.
- **fuori albero** -- il file non sta in questo repository e non ci stara' mai:
  i documenti citano il sorgente di CalculiX (`spooles.c`, `gen3delem.f`) per
  provenienza. Non risolvibili **per costruzione**, non un difetto, uscita 0.
  Restano stampati: un nome di file scritto male finisce qui, e va visto.
- **non verificabili a macchina** -- la forma abbreviata `` `:NNN` ``, dove il
  file lo porta il contesto. Dentro una stessa riga di tabella i documenti
  alternano il sorgente e il suo test, quindi «l'ultimo file nominato»
  sbaglia. Contati e dichiarati invece che dati per buoni.

Uscita 2 se l'argomento non e' un file leggibile.

**Limite che resta, per la forma a numero.** Un riferimento che risolve puo'
comunque mentire: che la riga esista non dice che porti ancora la cosa di cui il
testo parla. Quello lo vede solo chi legge, ed e' la deriva misurata in #96 --
166 su 168 puntavano a una riga esistente e a un contenuto diverso. La forma a
nome non ha questo limite: se il simbolo c'e', e' quello.

**Limite che resta, per la forma a nome.** Cio' che sta a sinistra del punto e'
un riferimento solo se l'albero porta un `<sinistra>.py`: `metrics.json`,
`RaycastingScene.compute_signed_distance`, `le10.html` restano prosa e non
vengono controllati. Un modulo scritto male finisce quindi nel silenzio, mentre
un simbolo scritto
male -- il caso frequente, perche' le funzioni si rinominano e i moduli quasi mai
-- viene visto.
"""

from __future__ import annotations

import ast
import contextlib
import io
import re
import sys
import tempfile
from pathlib import Path

RADICE = Path(__file__).resolve().parents[2]
SALTA = {".git", ".claude", "node_modules", ".venv", "__pycache__"}

RIFERIMENTO = re.compile(r"(?<![\w/.-])([A-Za-z_][\w./-]*\.[A-Za-z]{1,5}):(\d+)(?:-(\d+))?")
ABBREVIATO = re.compile(r"`:(\d+)")
# L'intero code span e nient'altro: `abaqus.ripartisci` si', «`ripartisci` di
# `abaqus.py`» no. Restringere qui costa meno che filtrare la prosa dopo.
SIMBOLO = re.compile(r"`([A-Za-z_]\w*(?:\.[A-Za-z_]\w*)+)`")


def _indice() -> dict[str, list[Path]]:
    """Nome di file -> percorsi che lo portano, su tutto l'albero."""
    trovati: dict[str, list[Path]] = {}
    for percorso in RADICE.rglob("*"):
        if percorso.is_file() and not SALTA & set(percorso.parts):
            trovati.setdefault(percorso.name, []).append(percorso)
    return trovati


def _breve(percorso: Path) -> str:
    """Il percorso relativo alla radice, o quello intero se ne sta fuori."""
    try:
        return str(percorso.relative_to(RADICE))
    except ValueError:
        return str(percorso)


def _righe(percorso: Path) -> int:
    with percorso.open("rb") as f:
        return sum(1 for _ in f)


def _definizioni(percorso: Path) -> set[str]:
    """I nomi che il modulo definisce, coi membri qualificati `Classe.membro`."""
    nomi: set[str] = set()

    def visita(nodo: ast.AST, prefisso: str) -> None:
        for figlio in ast.iter_child_nodes(nodo):
            if isinstance(figlio, ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef):
                nomi.add(prefisso + figlio.name)
                visita(figlio, f"{prefisso}{figlio.name}.")
            elif isinstance(figlio, ast.Assign | ast.AnnAssign):
                bersagli = figlio.targets if isinstance(figlio, ast.Assign) else [figlio.target]
                nomi.update(prefisso + b.id for b in bersagli if isinstance(b, ast.Name))

    visita(ast.parse(percorso.read_text(encoding="utf-8")), "")
    return nomi


def controlla(
    documento: Path, indice: dict[str, list[Path]] | None = None
) -> tuple[list[str], list[str], list[str]]:
    """(rotti, fuori albero, non verificabili), gia' formattati per la stampa."""
    if indice is None:
        indice = _indice()
    rotti: list[str] = []
    fuori: list[str] = []
    non_verificabili: list[str] = []

    definizioni: dict[Path, set[str]] = {}

    for numero, riga in enumerate(documento.read_text(encoding="utf-8").splitlines(), 1):
        dove = f"{documento}:{numero}"
        for span in SIMBOLO.findall(riga):
            # `io.py` e `README.md` sono nomi di file, non `modulo.simbolo`.
            if indice.get(span):
                continue
            modulo, _, resto = span.partition(".")
            candidati = indice.get(f"{modulo}.py", [])
            if not candidati:
                continue
            if len(candidati) > 1:
                elenco = ", ".join(_breve(c) for c in sorted(candidati))
                rotti.append(f"{dove}: `{span}` -- modulo ambiguo: {elenco}")
                continue
            if candidati[0] not in definizioni:
                definizioni[candidati[0]] = _definizioni(candidati[0])
            if resto not in definizioni[candidati[0]]:
                rotti.append(f"{dove}: `{span}` -- "
                             f"{_breve(candidati[0])} non definisce {resto}")
        for nome, prima, ultima in RIFERIMENTO.findall(riga):
            candidati = indice.get(Path(nome).name, [])
            if "/" in nome:
                candidati = [c for c in candidati if c.as_posix().endswith(nome)]
            citato = f"{nome}:{prima}" + (f"-{ultima}" if ultima else "")
            if not candidati:
                fuori.append(f"{dove}: {citato} -- fuori dall'albero di questo "
                             f"repository, non risolvibile per costruzione")
            elif len(candidati) > 1:
                elenco = ", ".join(_breve(c) for c in sorted(candidati))
                rotti.append(f"{dove}: {citato} -- nome ambiguo: {elenco}")
            elif int(prima) < 1:
                rotti.append(f"{dove}: {citato} -- le righe di un file partono da 1")
            else:
                quante = _righe(candidati[0])
                # Entrambi gli estremi, non solo il primo: `file.py:5-99999`
                # ha il sinistro buono e il destro fuori dalla fine.
                if any(int(n) > quante for n in (prima, ultima) if n):
                    rotti.append(f"{dove}: {citato} -- "
                                 f"{_breve(candidati[0])} ha {quante} righe")
        for abbreviato in ABBREVIATO.findall(riga):
            non_verificabili.append(f"{dove}: `:{abbreviato}` -- il file lo porta "
                                    f"il contesto, non verificabile a macchina")
    return rotti, fuori, non_verificabili


def _corsa(argomenti: list[str]) -> tuple[str, int]:
    """`main` con lo stdout catturato: l'autoprova non sporca la propria corsa."""
    catturato = io.StringIO()
    with contextlib.redirect_stdout(catturato):
        uscita = main(argomenti)
    return catturato.getvalue(), uscita


def autoprova() -> None:
    with tempfile.TemporaryDirectory() as cartella:
        doc = Path(cartella) / "prova.md"
        mio = Path(__file__).name

        # un sorgente che questo repository non contiene, e non conterra' mai
        doc.write_text("il manuale cita `spooles.c:225` e basta\n", encoding="utf-8")
        rotti, fuori, _ = controlla(doc)
        assert rotti == [], rotti
        assert len(fuori) == 1 and "per costruzione" in fuori[0], fuori
        assert _corsa([str(doc)])[1] == 0, "un fuori albero da solo non e' un difetto"

        # la forma abbreviata: terza categoria, ne' risolta ne' taciuta
        doc.write_text(f"`{mio}:1` e poi `:2`\n", encoding="utf-8")
        rotti, fuori, ignoti = controlla(doc)
        assert (rotti, fuori) == ([], []), (rotti, fuori)
        assert len(ignoti) == 1 and "`:2`" in ignoti[0], ignoti

        # documento senza alcun riferimento: esito stampato, non il vuoto
        doc.write_text("nessun riferimento qui, solo prosa.\n", encoding="utf-8")
        assert controlla(doc) == ([], [], [])
        esito, uscita = _corsa([str(doc)])
        assert uscita == 0 and "0 rotti" in esito, esito

        # riga oltre la fine: la lunghezza vera nel messaggio, non un IndexError
        doc.write_text(f"oltre la fine: `{mio}:99999`\n", encoding="utf-8")
        rotti, _, _ = controlla(doc)
        vere = _righe(Path(__file__))
        assert len(rotti) == 1 and str(vere) in rotti[0], (rotti, vere)
        assert _corsa([str(doc)])[1] == 1

        # file che esiste ma e' vuoto, citato a riga 1: rotto, e lo dice con lo 0
        vuoto = Path(cartella) / "vuoto.md"
        vuoto.write_text("", encoding="utf-8")
        doc.write_text("`vuoto.md:1` non esiste perche' il file e' vuoto\n", encoding="utf-8")
        rotti, _, _ = controlla(doc, {"vuoto.md": [vuoto]})
        assert len(rotti) == 1 and "ha 0 righe" in rotti[0], rotti

        # estremo destro dell'intervallo oltre la fine: il sinistro e' buono
        doc.write_text(f"intervallo: `{mio}:1-99999`\n", encoding="utf-8")
        rotti, _, _ = controlla(doc)
        assert len(rotti) == 1 and str(vere) in rotti[0], rotti

        # riga zero: non esiste, e il messaggio dice da dove si conta
        doc.write_text(f"riga zero: `{mio}:0`\n", encoding="utf-8")
        rotti, _, _ = controlla(doc)
        assert len(rotti) == 1 and "partono da 1" in rotti[0], rotti

        # nome che combacia con piu' file in albero: ambiguo, ed e' un difetto
        doc.write_text("nome nudo: `README.md:1`\n", encoding="utf-8")
        rotti, _, _ = controlla(doc)
        assert len(rotti) == 1 and "ambiguo" in rotti[0], rotti
        assert rotti[0].count(",") >= 1, ("l'elenco dei candidati e' il rimedio", rotti)
        assert _corsa([str(doc)])[1] == 1

        # lo stesso nome con il percorso davanti: disambiguato, non piu' rotto
        doc.write_text("col percorso: `docs/validazione/README.md:1`\n", encoding="utf-8")
        assert controlla(doc) == ([], [], [])

        # argomenti che non sono uno solo: uscita 2, non IndexError
        assert _corsa([])[1] == 2
        assert _corsa([str(doc), str(doc)])[1] == 2

        esito, uscita = _corsa([cartella])
        assert uscita == 2 and "cartella" in esito, esito

        # documento inesistente: uscita 2 col messaggio, non una traccia di stack
        esito, uscita = _corsa([str(Path(cartella) / "manca.md")])
        assert uscita == 2 and "non esiste" in esito, esito

        # --- riferimenti per nome ---

        # simbolo che il modulo non definisce: rotto, non taciuto. E' il caso
        # della definizione tolta dal codice sotto un documento che la cita.
        doc.write_text("`controlla_riferimenti.simbolo_che_non_esiste`\n", encoding="utf-8")
        rotti, _, _ = controlla(doc, {"controlla_riferimenti.py": [Path(__file__)]})
        assert len(rotti) == 1 and "non definisce" in rotti[0], rotti

        # lo stesso nome in due moduli: il modulo davanti lo disambigua, ed e'
        # per questo che la forma nuda `risolvi` non e' un riferimento
        uno = Path(cartella) / "uno.py"
        due = Path(cartella) / "due.py"
        uno.write_text("def risolvi():\n    pass\n", encoding="utf-8")
        due.write_text("def risolvi():\n    pass\n", encoding="utf-8")
        finto = {"uno.py": [uno], "due.py": [due]}
        doc.write_text("`uno.risolvi` e `due.risolvi`\n", encoding="utf-8")
        assert controlla(doc, finto) == ([], [], []), controlla(doc, finto)
        doc.write_text("`risolvi` da solo non dice quale\n", encoding="utf-8")
        assert controlla(doc, finto) == ([], [], [])

        # modulo il cui nome sta su due file: ambiguo, come per `file:riga`
        doppio = {"uno.py": [uno, due]}
        doc.write_text("`uno.risolvi`\n", encoding="utf-8")
        rotti, _, _ = controlla(doc, doppio)
        assert len(rotti) == 1 and "ambiguo" in rotti[0], rotti

        # metodo e attributo di classe: qualificati, e risolti
        classe = Path(cartella) / "tre.py"
        classe.write_text("class C:\n    campo: int = 1\n\n    def m(self):\n        pass\n",
                          encoding="utf-8")
        doc.write_text("`tre.C.m` e `tre.C.campo` e `tre.C`\n", encoding="utf-8")
        assert controlla(doc, {"tre.py": [classe]}) == ([], [], [])

        # cio' che a sinistra non e' un modulo dell'albero non e' un riferimento:
        # `metrics.json`, `RaycastingScene...`, `le10.html` restano prosa
        doc.write_text("`metrics.json` e `RaycastingScene.compute_signed_distance` "
                       "e `le10.html`\n", encoding="utf-8")
        assert controlla(doc, {}) == ([], [], [])

        # un nome di file che e' anche `modulo.suffisso`: e' un file, non un simbolo
        doc.write_text(f"`{mio}`\n", encoding="utf-8")
        assert controlla(doc) == ([], [], []), controlla(doc)

    assert _indice(), "l'indice dell'albero non puo' essere vuoto"
    print("autoprova: tutti gli assert passati")


def main(argomenti: list[str]) -> int:
    if argomenti == ["--autoprova"]:
        autoprova()
        return 0
    if len(argomenti) != 1:
        print(__doc__)
        return 2
    documento = Path(argomenti[0])
    if documento.is_dir():
        print(f"{documento} e' una cartella, non un documento: passane uno alla volta")
        return 2
    if not documento.is_file():
        print(f"{documento} non esiste")
        return 2

    rotti, fuori, non_verificabili = controlla(documento)
    for titolo, elenco in (
        ("rotti", rotti),
        ("fuori albero, non risolvibili per costruzione", fuori),
        ("non verificabili a macchina", non_verificabili),
    ):
        if elenco:
            print(f"--- {titolo}: {len(elenco)}")
            for riga in elenco:
                print(riga)
    # L'esito si stampa sempre, anche quando non c'e' nulla da elencare: un
    # prompt vuoto non dice se il controllo e' passato o se non e' partito.
    testo = documento.read_text(encoding="utf-8")
    totale = (len(RIFERIMENTO.findall(testo)) + len(ABBREVIATO.findall(testo))
              + len(SIMBOLO.findall(testo)))
    print(f"{documento}: {len(rotti)} rotti, {len(fuori)} fuori albero, "
          f"{len(non_verificabili)} non verificabili, su {totale} riferimenti")
    return 1 if rotti else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
