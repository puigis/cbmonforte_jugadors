# Prova de connexió amb Streamlabs Desktop (només llegeix, no emet res)
# Ús (PowerShell):  irm https://raw.githubusercontent.com/puigis/cbmonforte_jugadors/main/taules/club/prova-streamlabs.ps1 | iex

$port  = Read-Host "Port de Streamlabs (ex. 59653)"
$token = Read-Host "Token de API"

$ws = New-Object System.Net.WebSockets.ClientWebSocket
$cts = New-Object System.Threading.CancellationToken
try {
  $ws.ConnectAsync([Uri]"ws://127.0.0.1:$port/api/websocket", $cts).Wait()
} catch {
  Write-Host "No s'ha pogut connectar al port $port. Comprova que Streamlabs està obert i que 'Permitir conexiones de terceros' està activat." -ForegroundColor Red
  Read-Host "Prem Enter per tancar"; return
}

$script:id = 0
function Envia($recurs, $metode, $args) {
  $script:id++
  $msg = @{ jsonrpc = "2.0"; id = $script:id; method = $metode; params = @{ resource = $recurs; args = $args } } | ConvertTo-Json -Depth 10 -Compress
  $b = [Text.Encoding]::UTF8.GetBytes($msg)
  $ws.SendAsync([ArraySegment[byte]]$b, [System.Net.WebSockets.WebSocketMessageType]::Text, $true, $cts).Wait()
  $buf = New-Object byte[] 262144; $txt = ""
  do {
    $r = $ws.ReceiveAsync([ArraySegment[byte]]$buf, $cts); $r.Wait()
    $txt += [Text.Encoding]::UTF8.GetString($buf, 0, $r.Result.Count)
  } until ($r.Result.EndOfMessage)
  return $txt
}

Write-Host "`n--- Autenticació ---" -ForegroundColor Cyan
Write-Host (Envia "TcpServerService" "auth" @($token))
Write-Host "`n--- Estat de l'emissió ---" -ForegroundColor Cyan
Write-Host (Envia "StreamingService" "getModel" @())
Write-Host "`n--- Escena activa ---" -ForegroundColor Cyan
Write-Host (Envia "ScenesService" "activeScene" @())

$ws.Dispose()
Write-Host "`nFet. Copia tot aquest text i envia'l." -ForegroundColor Green
Read-Host "Prem Enter per tancar"
