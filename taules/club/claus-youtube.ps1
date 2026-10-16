# MARCADORS - posa la clau d'emissió de YouTube a cada Streamlabs
# Ús (PowerShell com a administrador):
#   irm https://raw.githubusercontent.com/puigis/cbmonforte_jugadors/main/taules/club/claus-youtube.ps1 | iex
#
# Cada taula té el seu usuari de Windows ("Billar N") amb el seu Streamlabs.
# L'usuari de Windows coincideix amb la taula: usuari "Billar 1" = taula 1 (accés directe BILLAR 3), etc.

$TAULES = @(
  @{ taula = 1; usuari = "Billar 1"; acces = "BILLAR 3" },
  @{ taula = 2; usuari = "Billar 2"; acces = "BILLAR 2" },
  @{ taula = 3; usuari = "Billar 3"; acces = "BILLAR 1" },
  @{ taula = 4; usuari = "Billar 4"; acces = "BILLAR 4" }
)

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
