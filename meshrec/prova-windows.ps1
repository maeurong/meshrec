# Prova guidata della finestra su Windows: tasto destro › Esegui con PowerShell.
# Guida le voci aperte di docs\prove\2026-09-finestra-windows.md, controlla da
# solo quello che si può controllare e scrive l'esito nel documento, voce per
# voce: le spunte di una prova precedente restano.
#
# Salvato UTF-8 con BOM: PowerShell 5.1 legge un file senza BOM come ANSI e
# rovina gli accenti. Le funzioni si caricano anche con il dot-source (i test in
# tests\test_prova_windows.py), che salta il percorso interattivo.

$CHIAVI_WEBVIEW2 = @(
    'SOFTWARE\WOW6432Node\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}',
    'SOFTWARE\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}'
)

function Test-PortaLibera([int]$Porta) {
    $l = New-Object System.Net.Sockets.TcpListener([System.Net.IPAddress]::Loopback, $Porta)
    try { $l.Start(); return $true } catch { return $false } finally { $l.Stop() }
}

function Get-PortaLibera([int]$Preferita) {
    if (Test-PortaLibera $Preferita) { return $Preferita }
    # Porta 0: la sceglie il sistema, fra le effimere (mai la 8765).
    $l = New-Object System.Net.Sockets.TcpListener([System.Net.IPAddress]::Loopback, 0)
    $l.Start(); $porta = $l.LocalEndpoint.Port; $l.Stop()
    Write-Host "La porta $Preferita è occupata: uso la $porta."
    return $porta
}

function Test-InAscolto([int]$Porta) {
    return [bool](Get-NetTCPConnection -LocalPort $Porta -State Listen -ErrorAction SilentlyContinue)
}

function Wait-Ascolto([int]$Porta, [int]$Secondi, $Processo) {
    $fine = (Get-Date).AddSeconds($Secondi)
    while ((Get-Date) -lt $fine) {
        if (Test-InAscolto $Porta) { return $true }
        if ($Processo -and $Processo.HasExited) { return $false }
        Start-Sleep -Milliseconds 500
    }
    return $false
}

function Wait-PortaLibera([int]$Porta, [int]$Secondi) {
    $fine = (Get-Date).AddSeconds($Secondi)
    while (Test-InAscolto $Porta) {
        if ((Get-Date) -ge $fine) { return $false }
        Start-Sleep -Milliseconds 500
    }
    return $true
}

function Read-SiNo([string]$Domanda) {
    $risposta = "$(Read-Host "$Domanda [s/n, Invio per saltare]")".Trim().ToLower()
    if ($risposta.StartsWith('s')) { return $true }
    if ($risposta.StartsWith('n')) { return $false }
    return $null
}

function Get-VersioneWebView2 {
    foreach ($radice in 'HKLM:\', 'HKCU:\') {
        foreach ($chiave in $CHIAVI_WEBVIEW2) {
            $pv = (Get-ItemProperty -Path ($radice + $chiave) -Name pv -ErrorAction SilentlyContinue).pv
            if ($pv -and $pv -ne '0.0.0.0') { return $pv }
        }
    }
    return 'non trovato'
}

function Start-MeshRec([string[]]$Argomenti) {
    $processo = Start-Process -FilePath 'uv' -ArgumentList (@('run', 'meshrec', 'serve') + $Argomenti) `
        -WorkingDirectory $PSScriptRoot -PassThru
    # Senza leggere Handle subito, ExitCode resta vuoto dopo l'uscita (Start-Process).
    $null = $processo.Handle
    return $processo
}

# Riscrive le righe «- [ ] testo — esito <!-- voce -->» delle voci in $Esiti
# (voce -> @{ Ok = $true/$false/$null; Motivo = '...' }); il resto non si tocca.
function Update-Documento([string]$Testo, [hashtable]$Esiti, [string]$Data, [string]$RigaEsito) {
    $a_capo = if ($Testo.Contains("`r`n")) { "`r`n" } else { "`n" }
    $righe = [System.Collections.ArrayList]@($Testo -split "`r?`n")
    $trovata = $false
    for ($i = 0; $i -lt $righe.Count; $i++) {
        if ($righe[$i] -match '^- \[[ x]\] (.*?) — .*<!-- (\w+) -->$' -and $Esiti.ContainsKey($Matches[2])) {
            $voce = $Matches[2]; $testo_voce = $Matches[1]; $e = $Esiti[$voce]
            if ($e.Ok -eq $true) { $casella = 'x'; $stato = 'ok' }
            elseif ($e.Ok -eq $false) { $casella = ' '; $stato = 'non riuscito' }
            else { $casella = ' '; $stato = 'non risposto' }
            if ($e.Motivo) { $stato += " ($($e.Motivo))" }
            $righe[$i] = "- [$casella] $testo_voce — provato con prova-windows.ps1 il ${Data}: $stato <!-- $voce -->"
        }
        elseif ($righe[$i].StartsWith('Ultima prova guidata:')) {
            $righe[$i] = $RigaEsito; $trovata = $true
        }
    }
    if (-not $trovata) { [void]$righe.Add($RigaEsito) }
    return ($righe -join $a_capo)
}

if ($MyInvocation.InvocationName -eq '.') { return }

# ---------------------------------------------------------------- la prova

$DOCUMENTO = Join-Path $PSScriptRoot '..\docs\prove\2026-09-finestra-windows.md'
$esiti = @{}

function Stop-Prova([int]$Codice) {
    if (-not [Console]::IsInputRedirected) { Read-Host 'Premi Invio per chiudere' | Out-Null }
    exit $Codice
}

if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
    Write-Host 'uv non trovato sul PATH.'
    Write-Host 'Installalo da https://docs.astral.sh/uv/ e rilancia la prova. Il documento non è stato toccato.'
    Stop-Prova 1
}

Set-Location $PSScriptRoot
Write-Host 'Prova guidata della finestra di MeshRec su Windows.'
Write-Host 'Sei voci; a ogni domanda rispondi s o n, oppure Invio per saltarla.'
Write-Host ''

# 1-4: la finestra, sulla porta di Mario se è libera.
$porta = Get-PortaLibera 8765
Write-Host "Avvio MeshRec sulla porta $porta..."
$meshrec = Start-MeshRec @('--port', $porta)
if (-not (Wait-Ascolto $porta 60 $meshrec)) {
    $motivo = 'MeshRec non si è messo in ascolto entro 60 s'
    if ($meshrec.HasExited) { $motivo = "MeshRec è uscito con codice $($meshrec.ExitCode) prima di mettersi in ascolto" }
    Write-Host $motivo
    foreach ($voce in 'viewport', 'sfoglia', 'citare') { $esiti[$voce] = @{ Ok = $null; Motivo = $motivo } }
    $esiti['chiusura'] = @{ Ok = $false; Motivo = $motivo }
    if (-not $meshrec.HasExited) { & taskkill.exe /PID $meshrec.Id /T /F | Out-Null }
}
else {
    $domande = [ordered]@{
        viewport = 'Apri una corsa con geometria: il viewport 3D si vede e ruota col mouse?'
        sfoglia  = 'Premi «Sfoglia»: il dialogo si sposta e si vede intero?'
        citare   = 'Premi «come citare» nel piè di pagina: si apre nel browser di sistema?'
    }
    foreach ($voce in $domande.Keys) {
        if ($meshrec.HasExited) {
            $esiti[$voce] = @{ Ok = $null; Motivo = 'finestra già chiusa' }
            continue
        }
        $esiti[$voce] = @{ Ok = (Read-SiNo $domande[$voce]); Motivo = '' }
    }

    if (-not $meshrec.HasExited) { Read-Host 'Ora chiudi la finestra di MeshRec, poi premi Invio' | Out-Null }
    $uscito = $meshrec.WaitForExit(10000)
    $libera = Wait-PortaLibera $porta 10
    if (-not $uscito) {
        $esiti['chiusura'] = @{ Ok = $false; Motivo = 'il processo è ancora vivo dopo 10 s' }
        & taskkill.exe /PID $meshrec.Id /T /F | Out-Null
    }
    elseif ($meshrec.ExitCode -ne 0) {
        $esiti['chiusura'] = @{ Ok = $false; Motivo = "uscito con codice $($meshrec.ExitCode)" }
    }
    elseif (-not $libera) {
        $esiti['chiusura'] = @{ Ok = $false; Motivo = "la porta $porta è ancora in ascolto dopo 10 s" }
    }
    else {
        $esiti['chiusura'] = @{ Ok = $true; Motivo = '' }
    }
    Write-Host "Chiusura: $(if ($esiti['chiusura'].Ok) { 'ok' } else { $esiti['chiusura'].Motivo })"
}

# 5: --browser, su una porta di prova diversa da quella di Mario.
Write-Host ''
$portaBrowser = Get-PortaLibera 8799
Write-Host "Avvio MeshRec nel browser sulla porta $portaBrowser..."
$browser = Start-MeshRec @('--browser', '--port', $portaBrowser)
if (-not (Wait-Ascolto $portaBrowser 60 $browser)) {
    $esiti['browser'] = @{ Ok = $false; Motivo = 'MeshRec non si è messo in ascolto entro 60 s' }
    if (-not $browser.HasExited) { & taskkill.exe /PID $browser.Id /T /F | Out-Null }
}
else {
    $risposta = Read-SiNo 'Si è aperta una scheda del browser con MeshRec?'
    # Fermato per PID, con tutto l'albero: uv e il Python che ha lanciato.
    & taskkill.exe /PID $browser.Id /T /F | Out-Null
    if (-not ($browser.WaitForExit(10000) -and (Wait-PortaLibera $portaBrowser 10))) {
        $esiti['browser'] = @{ Ok = $false; Motivo = "fermato il processo, la porta $portaBrowser non è tornata libera entro 10 s" }
    }
    else {
        $esiti['browser'] = @{ Ok = $risposta; Motivo = '' }
    }
}

# 6: il collegamento nel menu Start.
Write-Host ''
Write-Host 'Creo il collegamento nel menu Start...'
& (Join-Path $PSScriptRoot 'crea-collegamento.ps1')
$lnk = Join-Path ([Environment]::GetFolderPath('Programs')) 'MeshRec.lnk'
$motivo = ''
if (-not (Test-Path $lnk)) {
    $motivo = "$lnk non esiste"
}
else {
    $collegamento = (New-Object -ComObject WScript.Shell).CreateShortcut($lnk)
    $icona = ($collegamento.IconLocation -split ',')[0]
    if ($collegamento.TargetPath -ne (Join-Path $PSScriptRoot 'MeshRec.bat')) {
        $motivo = "punta a $($collegamento.TargetPath)"
    }
    elseif (-not (Test-Path $icona)) {
        $motivo = "l'icona $icona non esiste"
    }
}
if ($motivo) {
    $esiti['collegamento'] = @{ Ok = $false; Motivo = $motivo }
}
else {
    $esiti['collegamento'] = @{ Ok = (Read-SiNo 'Apri il menu Start: compare «MeshRec» con la sua icona?'); Motivo = '' }
}

# L'esito nel documento.
$data = Get-Date -Format 'dd/MM/yyyy'
$riga = "Ultima prova guidata: $data  Windows: $([Environment]::OSVersion.VersionString)  WebView2: $(Get-VersioneWebView2)"
$utf8 = New-Object System.Text.UTF8Encoding $false
$testo = [System.IO.File]::ReadAllText($DOCUMENTO, $utf8)
[System.IO.File]::WriteAllText($DOCUMENTO, (Update-Documento $testo $esiti $data $riga), $utf8)

Write-Host ''
Write-Host 'Riassunto'
foreach ($voce in 'viewport', 'sfoglia', 'citare', 'chiusura', 'browser', 'collegamento') {
    $e = $esiti[$voce]
    $stato = if ($e.Ok -eq $true) { 'ok' } elseif ($e.Ok -eq $false) { 'NON riuscito' } else { 'non risposto' }
    if ($e.Motivo) { $stato += " ($($e.Motivo))" }
    Write-Host ("  {0,-13} {1}" -f $voce, $stato)
}
Write-Host $riga
Write-Host "Esito scritto in $DOCUMENTO"
Stop-Prova 0
