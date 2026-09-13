# Prova della finestra su Windows 11

Da fare sul PC Windows dell'autore, prima di fondere `feat/finestra`.

Prova guidata: tasto destro su `meshrec\prova-windows.ps1` › Esegui con PowerShell.
Lo script guida le voci ancora aperte, controlla da solo quello che si può
controllare (processo uscito, porta libera, collegamento) e scrive l'esito qui
sotto: aggiorna solo le voci che ha provato, le spunte di prima restano.

## Comandi

    cd meshrec
    uv sync
    uv run meshrec serve

## Da guardare, uno alla volta

- [x] Si apre una finestra con titolo «MeshRec» (non una scheda di Edge). — provato da Mario
- [ ] Il viewport 3D di uno step con geometria si vede e ruota. — non ancora provato <!-- viewport -->
- [x] «Sfoglia…» porta il selettore file in primo piano, sopra la finestra. — provato da Mario
- [ ] «Sfoglia» apre un dialogo spostabile e intero (su macOS era uno sheet tagliato sul bordo: corretto in `2e4c721`). — non ancora provato <!-- sfoglia -->
- [x] «Salva immagine» scrive in `runs\<corsa>\immagini\` e la riga di esito dice il percorso. — provato da Mario
- [ ] «come citare» nel piè di pagina si apre nel browser di sistema. — non ancora provato <!-- citare -->
- [ ] Chiudere la finestra: il processo esce entro 10 s e la porta torna libera. — non ancora provato <!-- chiusura -->
- [ ] `uv run meshrec serve --browser`: scheda nel browser; fermato il processo, la porta torna libera. — non ancora provato <!-- browser -->
- [ ] `crea-collegamento.ps1`: «MeshRec» nel menu Start con l'icona, collegamento verso `MeshRec.bat`. — non ancora provato <!-- collegamento -->

La voce «senza WebView2» è uscita dalla prova a mano il 13/09/2026: il ripiego
quando il runtime manca è coperto dai test con il registro finto in
`meshrec/tests/test_finestra.py`.

## Esito

Data: 11/09/2026  Windows: 11  WebView2: __________

Ultima prova guidata: non ancora eseguita

Note: finestra, «Sfoglia» e «Salva immagine» provati da Mario su questo branch,
tutti e tre ok. Le altre voci restano da provare prima di fondere.
