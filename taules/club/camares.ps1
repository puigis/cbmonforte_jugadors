# MARCADORS - control de les càmeres (Streamlabs) des de l'app
# S'executa al PC del club. Escolta les ordres de l'app i prem les tecles
# d'accés ràpid de cada Streamlabs:
#   Billar N:  Ctrl+Alt+N = iniciar emissió   ·   Ctrl+Alt+Shift+N = aturar emissió
# No toca res més del PC.

$CANAL  = "cbmonforte-610393230cc6f165"
$ORDRES = "https://ntfy.sh/$CANAL-ordres"
$ESTAT  = "https://ntfy.sh/$CANAL-estat"
$LOG    = Join-Path $PSScriptRoot "camares.log"

[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
$Host.UI.RawUI.WindowTitle = "MARCADORS - càmeres (no tancar)"

Add-Type @"
using System;
using System.Runtime.InteropServices;
public static class Tecles {
  [DllImport("user32.dll")] static extern void keybd_event(byte vk, byte scan, uint flags, UIntPtr extra);
  const uint UP = 2;
  public static void Prem(byte[] mods, byte key) {
    foreach (var m in mods) keybd_event(m, 0, 0, UIntPtr.Zero);
    keybd_event(key, 0, 0, UIntPtr.Zero);
    System.Threading.Thread.Sleep(60);
    keybd_event(key, 0, UP, UIntPtr.Zero);
    for (int i = mods.Length - 1; i >= 0; i--) keybd_event(mods[i], 0, UP, UIntPtr.Zero);
  }
}
"@

function Escriu($t) { $l = "{0:yyyy-MM-dd HH:mm:ss}  {1}" -f (Get-Date), $t; Write-Host $l; Add-Content -Path $LOG -Value $l -Encoding UTF8 }

$cams = @{ "1" = $false; "2" = $false; "3" = $false; "4" = $false }
function PublicaEstat {
  $cos = @{ pc = "ok"; cams = $cams; t = [DateTimeOffset]::UtcNow.ToUnixTimeSeconds() } | ConvertTo-Json -Compress
  try { Invoke-WebRequest -UseBasicParsing -Method Post -Uri $ESTAT -Body $cos -ContentType "application/json" | Out-Null }
  catch { Escriu "No s'ha pogut enviar l'estat: $($_.Exception.Message)" }
}

function Camera($taula, $on) {
  if ($taula -notin 1..4) { return }
  $num = [byte](0x30 + $taula)          # tecla 1..4
  $CTRL = [byte]0x11; $ALT = [byte]0x12; $SHIFT = [byte]0x10
  if ($on) { [Tecles]::Prem(@($CTRL, $ALT), $num) } else { [Tecles]::Prem(@($CTRL, $ALT, $SHIFT), $num) }
  $cams["$taula"] = [bool]$on
  Escriu ("Càmera {0}: {1}" -f $taula, $(if ($on) { "INICIAR emissió" } else { "ATURAR emissió" }))
}

Escriu "Engegat. Escoltant ordres de l'app MARCADORS..."
$since = [DateTimeOffset]::UtcNow.ToUnixTimeSeconds()   # ignora ordres velles
PublicaEstat
$ultimEstat = Get-Date

while ($true) {
  try {
    $r = Invoke-WebRequest -UseBasicParsing -Uri "$ORDRES/json?poll=1&since=$since" -TimeoutSec 20
    $text = [Text.Encoding]::UTF8.GetString($r.RawContentStream.ToArray())
    foreach ($linia in ($text -split "`n")) {
      if (-not $linia.Trim()) { continue }
      $m = $linia | ConvertFrom-Json
      if ($m.id) { $since = $m.id }
      if ($m.event -ne "message") { continue }
      try {
        $o = $m.message | ConvertFrom-Json
        if ($o.estat) { PublicaEstat; continue }          # l'app demana l'estat
        Camera ([int]$o.taula) ([bool]$o.on)
        PublicaEstat; $ultimEstat = Get-Date
      } catch { Escriu "Ordre no vàlida: $($m.message)" }
    }
  } catch { Escriu "Sense connexió, ho torno a provar... ($($_.Exception.Message))"; Start-Sleep -Seconds 5 }
  if (((Get-Date) - $ultimEstat).TotalSeconds -ge 60) { PublicaEstat; $ultimEstat = Get-Date }
  Start-Sleep -Seconds 2
}
