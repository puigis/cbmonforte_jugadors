# MARCADORS - diagnosi: a quin YouTube emet cada Streamlabs (NOMÉS LLEGEIX, no canvia res)
# Ús (PowerShell com a administrador):
#   irm https://raw.githubusercontent.com/puigis/cbmonforte_jugadors/main/taules/club/diagnosi-youtube.ps1 | iex

function Amaga($t) {   # amaga claus i tokens: només deixa veure els 4 primers caràcters
  $t = [regex]::Replace($t, '("(?:key|streamKey|token|access_token|refresh_token|apiToken|oauth[^"]*)"\s*:\s*")([^"]{4})[^"]*"', '$1$2****"', 'IgnoreCase')
  return $t
}

Write-Host "`n=== Accessos directes BILLAR 1-4 ===" -ForegroundColor Cyan
$ws = New-Object -ComObject WScript.Shell
$escriptoris = @([Environment]::GetFolderPath("Desktop"), [Environment]::GetFolderPath("CommonDesktopDirectory"))
foreach ($n in 1..4) {
  $lnk = $escriptoris | ForEach-Object { Join-Path $_ "BILLAR $n.lnk" } | Where-Object { Test-Path $_ } | Select-Object -First 1
  if ($lnk) { $s = $ws.CreateShortcut($lnk); Write-Host ("BILLAR {0}: {1} {2}" -f $n, $s.TargetPath, $s.Arguments) }
  else { Write-Host "BILLAR ${n}: no hi ha accés directe" -ForegroundColor Yellow }
}

Write-Host "`n=== Streamlabs oberts (usuari de Windows) ===" -ForegroundColor Cyan
Get-CimInstance Win32_Process -Filter "Name='Streamlabs OBS.exe'" -ErrorAction SilentlyContinue | ForEach-Object {
  (Invoke-CimMethod -InputObject $_ -MethodName GetOwner -ErrorAction SilentlyContinue).User
} | Select-Object -Unique | ForEach-Object { Write-Host " - $_" }

Write-Host "`n=== Configuració de cada Streamlabs ===" -ForegroundColor Cyan
Get-ChildItem "C:\Users" -Directory -ErrorAction SilentlyContinue | ForEach-Object {
  $dir = Join-Path $_.FullName "AppData\Roaming\slobs-client"
  if (-not (Test-Path $dir)) { return }
  Write-Host "`n----- Usuari de Windows: $($_.Name) -----" -ForegroundColor Green
  foreach ($f in @("service.json", "streamEncoder.json")) {
    $p = Join-Path $dir $f
    if (Test-Path $p) { Write-Host "[$f]"; Write-Host (Amaga (Get-Content $p -Raw -ErrorAction SilentlyContinue)) }
  }
  $ini = Get-ChildItem $dir -Recurse -Filter "basic.ini" -ErrorAction SilentlyContinue | Select-Object -First 1
  if ($ini) { Write-Host "[basic.ini]"; Get-Content $ini.FullName | Where-Object { $_ -match '^(Mode|Encoder|VBitrate|ABitrate)=' } | ForEach-Object { Write-Host $_ } }
  # Línies que parlen de YouTube o del canal (amb claus amagades)
  Get-ChildItem $dir -File -Filter "*.json" -ErrorAction SilentlyContinue | Where-Object { $_.Length -lt 2MB } | ForEach-Object {
    $txt = Get-Content $_.FullName -Raw -ErrorAction SilentlyContinue
    if ($txt -match '(?i)youtube|channel') {
      $m = [regex]::Matches($txt, '"(?:platform|type|service|server|channelId|channelName|title|username|name)"\s*:\s*"[^"]{0,120}"', 'IgnoreCase') | ForEach-Object { $_.Value } | Select-Object -Unique -First 15
      if ($m) { Write-Host "[$($_.Name)]"; $m | ForEach-Object { Write-Host "  $_" } }
    }
  }
}

Write-Host "`nFet. Fes una captura (o copia tot aquest text) i envia-la. No s'ha canviat res." -ForegroundColor Green
Read-Host "Prem Enter per tancar"
