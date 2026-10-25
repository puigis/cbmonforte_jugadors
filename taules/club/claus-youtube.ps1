# MARCADORS - posa la clau d'emissió de YouTube a cada Streamlabs
# Ús (PowerShell com a administrador):
#   irm https://raw.githubusercontent.com/puigis/cbmonforte_jugadors/main/taules/club/claus-youtube.ps1 | iex
#
# Taula N = accés directe BILLAR N de l'escriptori. Cada accés directe obre el Streamlabs amb un
# usuari de Windows (BILLAR 1 -> "Billar 3", BILLAR 3 -> "Billar 1"): es llegeix de l'accés directe.

$ws = New-Object -ComObject WScript.Shell
$escriptoris = @([Environment]::GetFolderPath("Desktop"), [Environment]::GetFolderPath("CommonDesktopDirectory"))
$TAULES = foreach ($n in 1..4) {
  $usuari = "Billar $n"
  $lnk = $escriptoris | ForEach-Object { Join-Path $_ "BILLAR $n.lnk" } | Where-Object { Test-Path $_ } | Select-Object -First 1
  if ($lnk) {
    $sc = $ws.CreateShortcut($lnk)
    $m = [regex]::Match(($sc.TargetPath + " " + $sc.Arguments), '/user:(?:"([^"]+)"|(\S+))', "IgnoreCase")
    if ($m.Success) { $usuari = (($(if ($m.Groups[1].Success) { $m.Groups[1].Value } else { $m.Groups[2].Value })) -replace '^.*\\', '').Trim() }
  }
  @{ taula = $n; usuari = $usuari; acces = "BILLAR $n" }
}

Write-Host "`nEnganxa la clau d'emissió de YouTube de cada taula (clic dret per enganxar)." -ForegroundColor Cyan
Write-Host "Si una taula ja funciona o no la vols canviar, deixa-la en blanc i prem Enter.`n"

foreach ($t in $TAULES) {
  $clau = (Read-Host ("Clau TAULA {0} (Streamlabs {1})" -f $t.taula, $t.acces)).Trim()
  if (-not $clau) { Write-Host "  Taula $($t.taula): sense canvis" -ForegroundColor DarkGray; continue }
  if ($clau -notmatch '^[A-Za-z0-9\-]{10,}$') { Write-Host "  Aquesta clau no sembla bona (ha de ser com xxxx-xxxx-xxxx-xxxx-xxxx). No la poso." -ForegroundColor Red; continue }

  $perfil = Get-CimInstance Win32_UserProfile -ErrorAction SilentlyContinue | Where-Object { $_.LocalPath -and (Split-Path $_.LocalPath -Leaf) -ieq $t.usuari } | Select-Object -First 1
  $dirUsuari = if ($perfil) { $perfil.LocalPath } else { "C:\Users\$($t.usuari)" }
  $dir = Join-Path $dirUsuari "AppData\Roaming\slobs-client"
  if (-not (Test-Path $dir)) { Write-Host "  No trobo el Streamlabs de l'usuari $($t.usuari) ($dir)" -ForegroundColor Red; continue }

  # Tanca el Streamlabs d'aquest usuari (si estava obert, en tancar-se tornaria a escriure la configuració vella)
  $tancat = $false
  Get-CimInstance Win32_Process -Filter "Name='Streamlabs OBS.exe' OR Name='obs64.exe' OR Name='obs-ffmpeg-mux.exe'" -ErrorAction SilentlyContinue | ForEach-Object {
    $o = Invoke-CimMethod -InputObject $_ -MethodName GetOwner -ErrorAction SilentlyContinue
    if ($o -and $o.User -ieq $t.usuari) { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue; $tancat = $true }
  }
  if ($tancat) { Write-Host "  He tancat el Streamlabs $($t.acces)"; Start-Sleep -Seconds 3 }

  $fitxer = Join-Path $dir "service.json"
  if (Test-Path $fitxer) { Copy-Item $fitxer "$fitxer.abans-$(Get-Date -Format yyyyMMdd-HHmmss)" -Force }
  $cfg = [ordered]@{
    settings = [ordered]@{
      streamType = "rtmp_common"; service = "YouTube - RTMPS"; show_all = $false
      server = "rtmps://a.rtmps.youtube.com:443/live2"; key = $clau; protocol = "RTMPS"
      stream_key_link = "https://www.youtube.com/live_dashboard"
    }
    type = "rtmp_common"
  }
  [IO.File]::WriteAllText($fitxer, ($cfg | ConvertTo-Json -Compress), (New-Object Text.UTF8Encoding $false))
  Write-Host ("  Taula {0}: clau posada ({1}****)" -f $t.taula, $clau.Substring(0, 4)) -ForegroundColor Green

  # Torna a obrir el Streamlabs
  $lnk = @([Environment]::GetFolderPath("Desktop"), [Environment]::GetFolderPath("CommonDesktopDirectory")) |
    ForEach-Object { Join-Path $_ "$($t.acces).lnk" } | Where-Object { Test-Path $_ } | Select-Object -First 1
  if ($lnk) { Start-Process $lnk; Write-Host "  Obrint $($t.acces)..." }
}

Write-Host "`nFet. Espera que s'obrin els Streamlabs i prova 'Transmitir en directo' a cadascun." -ForegroundColor Green
Write-Host "Si algun encara té la sessió iniciada de YouTube, tanca-la (icona del perfil -> Cerrar sesión)."
Read-Host "Prem Enter per tancar"
