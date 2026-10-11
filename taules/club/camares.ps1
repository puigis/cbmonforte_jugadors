# MARCADORS - control de les càmeres (Streamlabs) des de l'app
# S'executa al PC del club, amagat, amb una icona a la safata (al costat del rellotge).
# Escolta les ordres de l'app i prem les tecles d'accés ràpid de cada Streamlabs:
#   Billar N:  Ctrl+Alt+N = iniciar emissió   ·   Ctrl+Alt+Shift+N = aturar emissió

$CANAL = "cbmonforte-610393230cc6f165"
$DIR   = Split-Path -Parent $MyInvocation.MyCommand.Path
$LOG   = Join-Path $DIR "camares.log"

# Només una còpia en marxa
$creat = $false
$mutex = New-Object System.Threading.Mutex($true, "Global\MARCADORS-camares", [ref]$creat)
if (-not $creat) { exit }

Add-Type -AssemblyName System.Windows.Forms, System.Drawing
Add-Type @"
using System;
using System.Runtime.InteropServices;
public static class Tecles {
  [DllImport("user32.dll")] static extern void keybd_event(byte vk, byte scan, uint flags, UIntPtr extra);
  public static void Prem(byte[] mods, byte key) {
    foreach (var m in mods) keybd_event(m, 0, 0, UIntPtr.Zero);
    keybd_event(key, 0, 0, UIntPtr.Zero);
    System.Threading.Thread.Sleep(60);
    keybd_event(key, 0, 2, UIntPtr.Zero);
    for (int i = mods.Length - 1; i >= 0; i--) keybd_event(mods[i], 0, 2, UIntPtr.Zero);
  }
}
"@

$estat = [hashtable]::Synchronized(@{ text = "Engegant..."; ok = $false; atura = $false })

# ---------- feina de fons: escoltar ordres ----------
$feina = {
  param($CANAL, $LOG, $estat)
  $ORDRES = "https://ntfy.sh/$CANAL-ordres"
  $ESTAT  = "https://ntfy.sh/$CANAL-estat"
  [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
  function Escriu($t) { $l = "{0:yyyy-MM-dd HH:mm:ss}  {1}" -f (Get-Date), $t; try { Add-Content -Path $LOG -Value $l -Encoding UTF8 } catch {} ; $estat.text = $t }
  $cams = @{ "1" = $false; "2" = $false; "3" = $false; "4" = $false }
  function PublicaEstat {
    $cos = @{ pc = "ok"; cams = $cams; t = [DateTimeOffset]::UtcNow.ToUnixTimeSeconds() } | ConvertTo-Json -Compress
    try { $wc = New-Object Net.WebClient; $wc.Headers.Add("Content-Type", "application/json"); $wc.UploadString($ESTAT, $cos) | Out-Null; $estat.ok = $true }
    catch { $estat.ok = $false; Escriu "No s'ha pogut enviar l'estat: $($_.Exception.Message)" }
  }
  function Camera($taula, $on) {
    if ($taula -lt 1 -or $taula -gt 4) { return }
    $num = [byte](0x30 + $taula)
    if ($on) { [Tecles]::Prem([byte[]](0x11, 0x12), $num) } else { [Tecles]::Prem([byte[]](0x11, 0x12, 0x10), $num) }
    $cams["$taula"] = [bool]$on
    Escriu ("Càmera {0}: {1}" -f $taula, $(if ($on) { "INICIAR emissió" } else { "ATURAR emissió" }))
  }

  Escriu "Engegat. Escoltant ordres de l'app MARCADORS"
  $since = [DateTimeOffset]::UtcNow.ToUnixTimeSeconds()
  PublicaEstat
  $ultim = Get-Date
  while (-not $estat.atura) {
    try {
      $req = [Net.HttpWebRequest]::Create("$ORDRES/json?since=$since")
      $req.Timeout = 120000; $req.ReadWriteTimeout = 120000
      $resp = $req.GetResponse()
      $lector = New-Object IO.StreamReader($resp.GetResponseStream(), [Text.Encoding]::UTF8)
      while ((-not $estat.atura) -and (($linia = $lector.ReadLine()) -ne $null)) {
        if ($linia.Trim()) {
          $m = $linia | ConvertFrom-Json
          if ($m.event -eq "message") {
            $since = $m.id
            try {
              $o = $m.message | ConvertFrom-Json
              if (-not $o.estat) { Camera ([int]$o.taula) ([bool]$o.on) }
              PublicaEstat; $ultim = Get-Date
            } catch { Escriu "Ordre no vàlida: $($m.message)" }
          }
        }
        if (((Get-Date) - $ultim).TotalSeconds -ge 60) { PublicaEstat; $ultim = Get-Date }
      }
      $resp.Close()
    } catch {
      $estat.ok = $false
      Escriu "Connexió tallada, la torno a obrir... ($($_.Exception.Message))"
      Start-Sleep -Seconds 10
    }
  }
}

$rs = [RunspaceFactory]::CreateRunspace(); $rs.ApartmentState = "STA"; $rs.Open()
$ps = [PowerShell]::Create(); $ps.Runspace = $rs
[void]$ps.AddScript($feina).AddArgument($CANAL).AddArgument($LOG).AddArgument($estat)
$handle = $ps.BeginInvoke()

# ---------- icona a la safata ----------
$icona = New-Object System.Windows.Forms.NotifyIcon
$png = Join-Path $DIR "icona.png"
if (Test-Path $png) { $icona.Icon = [System.Drawing.Icon]::FromHandle(([System.Drawing.Bitmap]::FromFile($png)).GetHicon()) }
else { $icona.Icon = [System.Drawing.SystemIcons]::Application }
$icona.Text = "MARCADORS - càmeres"
$menu = New-Object System.Windows.Forms.ContextMenuStrip
$mEstat = $menu.Items.Add("Engegant..."); $mEstat.Enabled = $false
[void]$menu.Items.Add("-")
$mLog = $menu.Items.Add("Veure registre")
$mLog.add_Click({ Start-Process notepad.exe $LOG })
$mSortir = $menu.Items.Add("Tancar")
$mSortir.add_Click({
  $r = [System.Windows.Forms.MessageBox]::Show("Si el tanques, l'app MARCADORS no podrà engegar ni aturar les càmeres fins que es reiniciï el PC.`n`nSegur que el vols tancar?", "MARCADORS - càmeres", "YesNo", "Warning")
  if ($r -eq "Yes") { $estat.atura = $true; $icona.Visible = $false; [System.Windows.Forms.Application]::Exit() }
})
$icona.ContextMenuStrip = $menu
$icona.Visible = $true

$timer = New-Object System.Windows.Forms.Timer
$timer.Interval = 2000
$timer.add_Tick({
  $t = if ($estat.ok) { "Connectat" } else { "Sense connexió" }
  $mEstat.Text = "$t · $($estat.text)"
  $txt = "MARCADORS - càmeres: $t"
  if ($txt.Length -gt 63) { $txt = $txt.Substring(0, 63) }
  $icona.Text = $txt
  if ($handle.IsCompleted) {   # la feina de fons ha caigut: la torna a engegar
    try { $ps.EndInvoke($handle) } catch { Add-Content -Path $LOG -Value ("{0:yyyy-MM-dd HH:mm:ss}  Error: {1}" -f (Get-Date), $_.Exception.Message) }
    $ps.Commands.Clear(); [void]$ps.AddScript($feina).AddArgument($CANAL).AddArgument($LOG).AddArgument($estat)
    if (-not $estat.atura) { $script:handle = $ps.BeginInvoke() }
  }
})
$timer.Start()
[System.Windows.Forms.Application]::Run()
$icona.Dispose()
