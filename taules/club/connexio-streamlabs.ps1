# MARCADORS - troba sol el port i el token de cada Streamlabs i en prova la connexió (només llegeix, no emet res)
# Ús (PowerShell com a administrador):
#   irm https://raw.githubusercontent.com/puigis/cbmonforte_jugadors/main/taules/club/connexio-streamlabs.ps1 | iex
# Desa el resultat a C:\MARCADORS\streamlabs.json perquè el programa de càmeres el pugui fer servir.

function Prova($port, $token) {
  $ws = New-Object System.Net.WebSockets.ClientWebSocket
  $ct = [System.Threading.CancellationToken]::None
  try { if (-not $ws.ConnectAsync([Uri]"ws://127.0.0.1:$port/api/websocket", $ct).Wait(3000)) { return $null } } catch { return $null }
  $envia = {
    param($metode, $recurs, $arg)
    $msg = @{ jsonrpc = "2.0"; id = 1; method = $metode; params = @{ resource = $recurs; args = $arg } } | ConvertTo-Json -Depth 6 -Compress
    $b = [Text.Encoding]::UTF8.GetBytes($msg)
    $ws.SendAsync([ArraySegment[byte]]$b, [System.Net.WebSockets.WebSocketMessageType]::Text, $true, $ct).Wait()
    $buf = New-Object byte[] 65536; $txt = ""
    do { $r = $ws.ReceiveAsync([ArraySegment[byte]]$buf, $ct); if (-not $r.Wait(3000)) { break }; $txt += [Text.Encoding]::UTF8.GetString($buf, 0, $r.Result.Count) } until ($r.Result.EndOfMessage)
    return $txt
  }
  $auth = & $envia "auth" "TcpServerService" @($token)
  $res = @{ ok = ($auth -match '"result"\s*:\s*true') }
  if ($res.ok) {
    $res.escena = ([regex]::Match((& $envia "activeScene" "ScenesService" @()), '"name"\s*:\s*"([^"]*)"')).Groups[1].Value
    $res.emissio = ([regex]::Match((& $envia "getModel" "StreamingService" @()), '"streamingStatus"\s*:\s*"([^"]*)"')).Groups[1].Value
  }
  try { $ws.Dispose() } catch {}
  return $res
}

# Llegeix un fitxer encara que Streamlabs el tingui obert
# (Chrome/Electron desa el localStorage en latin1 o en UTF-16: es llegeix de les tres maneres)
function Llegeix($p) {
  try { $fs = [IO.File]::Open($p, 'Open', 'Read', 'ReadWrite'); $ms = New-Object IO.MemoryStream; $fs.CopyTo($ms); $fs.Close()
        $b = $ms.ToArray()
        $txt = [Text.Encoding]::GetEncoding(28591).GetString($b) + "`n" + [Text.Encoding]::Unicode.GetString($b)
        if ($b.Length -gt 1) { $txt += "`n" + [Text.Encoding]::Unicode.GetString($b, 1, $b.Length - 1) }
        return $txt } catch { return "" }
}

# 1. Streamlabs oberts: usuari de Windows i ports on escolten
$procs = @{}
Get-CimInstance Win32_Process -Filter "Name='Streamlabs OBS.exe'" -ErrorAction SilentlyContinue | ForEach-Object {
  $o = Invoke-CimMethod -InputObject $_ -MethodName GetOwner -ErrorAction SilentlyContinue
  if ($o -and $o.User) { $u = $o.User; if (-not $procs[$u]) { $procs[$u] = @() }; $procs[$u] += $_.ProcessId }
}
$escolta = Get-NetTCPConnection -State Listen -ErrorAction SilentlyContinue

# Accés directe de cada usuari (BILLAR N -> usuari)
$wsh = New-Object -ComObject WScript.Shell
$acces = @{}
foreach ($d in @([Environment]::GetFolderPath("Desktop"), [Environment]::GetFolderPath("CommonDesktopDirectory"))) {
  foreach ($n in 1..4) { $l = Join-Path $d "BILLAR $n.lnk"; if (Test-Path $l) {
    $s = $wsh.CreateShortcut($l); $m = [regex]::Match(($s.TargetPath + " " + $s.Arguments), '/user:(?:"([^"]+)"|(\S+))', "IgnoreCase")
    if ($m.Success) { $acces[(($(if ($m.Groups[1].Success) { $m.Groups[1].Value } else { $m.Groups[2].Value })) -replace '^.*\\', '').ToLower()] = "BILLAR $n" } } }
}

$resultat = @()
Write-Host "`n=== Streamlabs ===" -ForegroundColor Cyan
foreach ($perfil in Get-ChildItem "C:\Users" -Directory -ErrorAction SilentlyContinue) {
  $dir = Join-Path $perfil.FullName "AppData\Roaming\slobs-client"
  if (-not (Test-Path $dir)) { continue }
  $usuari = $perfil.Name
  $icona = $acces[$usuari.ToLower()]; if (-not $icona) { $icona = "(sense accés directe)" }
  # Tokens desats per Streamlabs (40 caràcters hexadecimals)
  # Busca a tots els fitxers de configuració de Streamlabs (no a les memòries cau)
  $tokens = @(); $on = @()
  $fitxers = Get-ChildItem $dir -File -Recurse -ErrorAction SilentlyContinue |
    Where-Object { $_.Length -lt 30MB -and $_.FullName -notmatch '\\(Cache|Code Cache|GPUCache|DawnCache|ShaderCache|Crashpad|blob_storage)\\' }
  foreach ($f in $fitxers) {
    $txt = Llegeix $f.FullName
    if ($txt -notmatch '(?i)tcpserver|token') { continue }
    $ts = [regex]::Matches($txt, '(?i)token[\s\S]{1,12}?([0-9a-f]{32,64})') | ForEach-Object { $_.Groups[1].Value.ToLower() }
    if ($txt -match '(?i)tcpserver') { $on += $f.FullName.Substring($dir.Length + 1) }
    $tokens += $ts
  }
  $tokens = @($tokens | Select-Object -Unique)
  if ($on) { Write-Host ("  Fitxers amb configuració del control remot: " + (($on | Select-Object -Unique -First 5) -join " · ")) -ForegroundColor DarkGray }
  $pids = $procs[$usuari]
  $ports = @()
  if ($pids) { $ports = $escolta | Where-Object { $pids -contains $_.OwningProcess -and $_.LocalPort -ge 59000 -and $_.LocalPort -le 60999 } | ForEach-Object { $_.LocalPort } | Select-Object -Unique }
  Write-Host "`n--- $icona (usuari de Windows '$usuari') ---" -ForegroundColor Green
  if (-not $pids) { Write-Host "  Streamlabs tancat" -ForegroundColor DarkGray; continue }
  Write-Host ("  Ports on escolta: " + $(if ($ports) { $ports -join ", " } else { "cap (activa 'Permitir conexiones de terceros' a Móvil)" }))
  Write-Host ("  Tokens trobats: " + $tokens.Count)
  $bo = $null
  foreach ($p in $ports) { foreach ($t in $tokens) { $r = Prova $p $t; if ($r -and $r.ok) { $bo = @{ icona = $icona; usuari = $usuari; port = $p; token = $t; escena = $r.escena; emissio = $r.emissio }; break } }; if ($bo) { break } }
  if ($bo) {
    Write-Host ("  CONNECTAT  · port {0} · token {1}**** · escena '{2}' · emissió: {3}" -f $bo.port, $bo.token.Substring(0, 4), $bo.escena, $bo.emissio) -ForegroundColor Green
    $resultat += $bo
  } else { Write-Host "  No he pogut connectar amb cap token" -ForegroundColor Red }
}

if ($resultat) {
  New-Item -ItemType Directory -Force -Path "C:\MARCADORS" | Out-Null
  $resultat | ConvertTo-Json | Set-Content -Path "C:\MARCADORS\streamlabs.json" -Encoding UTF8
  Write-Host "`nDesat a C:\MARCADORS\streamlabs.json" -ForegroundColor Cyan
}
Write-Host "`nFet. Copia tot aquest text i envia'l (els tokens surten tapats)." -ForegroundColor Green
Read-Host "Prem Enter per tancar"
