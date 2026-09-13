# Casi della tesi

Le configurazioni del caso studio, tenute qui e non alla radice: **non sono il
modo normale di avviare il programma**, sono i quattro casi con cui la pipeline
è stata tarata e misurata, e servono a rieseguirli.

Il modo normale è `uv run meshrec serve` senza argomenti: l'interfaccia si apre
sulla schermata d'ingresso e una corsa nasce da un file di punti.

| File | Che cos'è |
|---|---|
| `lab.yaml` | `lab_frame.pcd` ritagliato sul solo telaio (larghezza 290 mm in y). Base dello sweep `experiments/lab_crop/`. |
| `lab_telaio.yaml` | `lab_frame.pcd` col ritaglio esteso alle zapatas, misurato il 21/08/2026. È la corsa `runs/lab_telaio_v2/` della Fase 5. |
| `muro.yaml` | Il muro sintetico a geometria nota. Base dello sweep `experiments/muro/`. **Non gira così com'è su macOS**: vedi sotto. |
| `prova-interfaccia.yaml` | Banco di lavoro dell'interfaccia, non un risultato. |

## Percorsi

I percorsi dentro questi file — `input.path`, `run.out_dir` — sono relativi
alla **cartella da cui gira il programma** (`meshrec/`), non a questo file.
Vanno usati da lì:

```bash
uv run meshrec serve casi/lab_telaio.yaml
uv run meshrec sweep experiments/lab_crop/esperimento.yaml
```

`experiments/*/esperimento.yaml` li nomina con la stessa regola
(`base: casi/lab.yaml`).

## Percorsi da Windows (corretto il 13/09/2026)

`muro.yaml` portava `path: ..\Nuvole di punti\muro_generato.ply`, scritto su
Windows prima del trasloco su macOS del 16/08/2026: su macOS quel `\` era un
carattere del nome e la corsa non partiva. Da `fix/windows-percorsi` la
configurazione scrive sempre `/` su ogni piattaforma e legge un `\` come
separatore anche su macOS (`Percorso` in `core/config.py`), e `muro.yaml` porta
`/`.

Il prezzo, voluto: l'impronta di `muro.yaml` e l'aggregato delle ventidue righe
registrate si sono mossi, perché `input.path` entra nell'impronta. Le righe
restano leggibili — ognuna porta la propria configurazione e la propria
impronta misurata — ma la deriva già misurata fra basi e registri
(`experiments/lab_crop` 0 righe su 11, `experiments/muro` 2 su 11) non si
ricompone da qui.
