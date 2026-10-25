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
public static class Finestres {
  delegate bool EnumProc(IntPtr h, IntPtr l);
  [DllImport("user32.dll")] static extern bool EnumWindows(EnumProc f, IntPtr l);
  [DllImport("user32.dll", CharSet = CharSet.Unicode)] static extern int GetWindowText(IntPtr h, System.Text.StringBuilder s, int n);
  [DllImport("user32.dll")] static extern bool IsWindowVisible(IntPtr h);
  [DllImport("user32.dll")] static extern bool ShowWindow(IntPtr h, int c);
  // Minimitza totes les finestres visibles que comencen pel text donat. Retorna quantes.
  public static int Minimitza(string inici) {
    int n = 0;
    EnumWindows((h, l) => {
      var sb = new System.Text.StringBuilder(256); GetWindowText(h, sb, 256);
      if (IsWindowVisible(h) && sb.ToString().StartsWith(inici)) { ShowWindow(h, 6); n++; }
      return true;
    }, IntPtr.Zero);
    return n;
  }
}
public static class Tecles {
  [DllImport("user32.dll")] static extern void keybd_event(byte vk, byte scan, uint flags, UIntPtr extra);
  [DllImport("user32.dll")] static extern uint MapVirtualKey(uint code, uint type);
  static void K(byte vk, bool amunt) { keybd_event(vk, (byte)MapVirtualKey(vk, 0), amunt ? 2u : 0u, UIntPtr.Zero); }
  public static void Prem(byte[] mods, byte key) {
    foreach (var m in mods) { K(m, false); System.Threading.Thread.Sleep(40); }
    K(key, false);
    System.Threading.Thread.Sleep(250);
    K(key, true);
    System.Threading.Thread.Sleep(40);
    for (int i = mods.Length - 1; i >= 0; i--) { K(mods[i], true); System.Threading.Thread.Sleep(20); }
  }
}
"@

# Els Streamlabs només s'obren sols quan el programa arrenca amb l'opció -ObreBillars (inici de Windows)
$estat = [hashtable]::Synchronized(@{ text = "Engegant..."; ok = $false; atura = $false; obreBillars = ($args -contains "-ObreBillars"); cua = [System.Collections.Queue]::Synchronized((New-Object System.Collections.Queue)) })

# ---------- feina de fons: escoltar ordres ----------
$feina = {
  param($CANAL, $LOG, $estat)
  $URL = "https://taules-monforte.puigis.workers.dev/"
  [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
  function Escriu($t) { $l = "{0:yyyy-MM-dd HH:mm:ss}  {1}" -f (Get-Date), $t; try { Add-Content -Path $LOG -Value $l -Encoding UTF8 } catch {} ; $estat.text = $t }
  $cams = @{ "1" = $false; "2" = $false; "3" = $false; "4" = $false }
  $titols = @{}
  function ProvaTitols {
    foreach ($t in @($titols.Keys)) {
      $p = $titols[$t]
      if ((Get-Date) -lt $p.proper) { continue }
      if ((Get-Date) -gt $p.fins) { Escriu "Taula ${t}: no he pogut posar el títol de YouTube (el directe no ha arrencat a temps)"; $titols.Remove($t); continue }
      try {
        $wc = New-Object Net.WebClient; $wc.Encoding = [Text.Encoding]::UTF8
        $r = $wc.DownloadString("$URL`?accio=yt_titol&taula=$t&clau=$CANAL") | ConvertFrom-Json
        if ($r.ok) { Escriu "Taula ${t}: títol de YouTube posat ($($r.canal)): $($r.titol)"; $titols.Remove($t) }
        elseif ($r.error) { Escriu "Taula ${t}: títol de YouTube - $($r.error)"; $titols.Remove($t) }
        else { $p.proper = (Get-Date).AddSeconds(15) }
      } catch {
        $msg = $_.Exception.Message
        try { $cos = (New-Object IO.StreamReader($_.Exception.InnerException.Response.GetResponseStream())).ReadToEnd(); if ($cos) { $msg = $cos } } catch {}
        Escriu "Taula ${t}: títol de YouTube - $msg"; $titols.Remove($t)
      }
    }
  }
  function PublicaEstat {
    $cos = @{ pc = "ok"; cams = $cams; t = [DateTimeOffset]::UtcNow.ToUnixTimeSeconds() } | ConvertTo-Json -Compress
    try { $wc = New-Object Net.WebClient; $wc.Headers.Add("Content-Type", "application/json"); $wc.UploadString("$URL`?accio=estat&clau=$CANAL", $cos) | Out-Null; $estat.ok = $true }
    catch { $estat.ok = $false; Escriu "No s'ha pogut enviar l'estat: $($_.Exception.Message)" }
  }
  # Usuaris de Windows que tenen un Streamlabs obert ("Billar 1", "Billar 2"...)
  function StreamlabsOberts {
    $u = @()
    try {
      Get-CimInstance Win32_Process -Filter "Name='Streamlabs OBS.exe'" -ErrorAction Stop | ForEach-Object {
        $o = Invoke-CimMethod -InputObject $_ -MethodName GetOwner -ErrorAction SilentlyContinue
        if ($o -and $o.User) { $u += $o.User.ToLower() }
      }
    } catch {}
    return ($u | Select-Object -Unique)
  }
  # Accés directe BILLAR N de l'escriptori
  function AccesBillar($n) {
    $escriptoris = @([Environment]::GetFolderPath("Desktop"), [Environment]::GetFolderPath("CommonDesktopDirectory"))
    return ($escriptoris | ForEach-Object { Join-Path $_ "BILLAR $n.lnk" } | Where-Object { Test-Path $_ } | Select-Object -First 1)
  }
  # Usuari de Windows amb què l'accés directe BILLAR N obre el Streamlabs (no sempre és "Billar N":
  # al club els accessos directes i els usuaris estan creuats). Es llegeix del /user: de l'accés directe.
  function UsuariBillar($n) {
    $lnk = AccesBillar $n
    if ($lnk) {
      try {
        $s = (New-Object -ComObject WScript.Shell).CreateShortcut($lnk)
        $m = [regex]::Match(($s.TargetPath + " " + $s.Arguments), '/user:(?:"([^"]+)"|(\S+))', "IgnoreCase")
        if ($m.Success) {
          $u = if ($m.Groups[1].Success) { $m.Groups[1].Value } else { $m.Groups[2].Value }
          return ($u -replace '^.*\\', '').Trim().ToLower()
        }
      } catch {}
    }
    return "billar $n"
  }
  # Si el Streamlabs del billar no està obert, l'obre i espera que estigui a punt
  function AsseguraStreamlabs($taula) {
    $oberts = StreamlabsOberts
    $usuari = UsuariBillar $taula
    Escriu ("Streamlabs oberts: " + $(if ($oberts) { ($oberts -join ", ") } else { "cap" }) + " · BILLAR $taula = usuari '$usuari'")
    if ($oberts -contains $usuari) { return }
    $lnk = AccesBillar $taula
    if (-not $lnk) { Escriu "No trobo l'accés directe BILLAR $taula a l'escriptori"; return }
    Escriu "El Streamlabs de BILLAR $taula estava tancat: l'obro"
    Start-Process $lnk -WindowStyle Minimized
    $limit = (Get-Date).AddSeconds(60)
    while (-not ((StreamlabsOberts) -contains $usuari) -and (Get-Date) -lt $limit) { Start-Sleep -Seconds 2 }
    Start-Sleep -Seconds 30          # temps perquè carregui la càmera i el canal
    [void][Finestres]::Minimitza("Streamlabs")
    Escriu "Streamlabs de BILLAR $taula a punt"
  }

  # Quin Streamlabs (accés directe BILLAR N) grava cada taula.
  # Cada taula té el seu accés directe amb el mateix número (Taula 1 = BILLAR 1...).
  # El creuament és només als canals de YouTube (BILLAR 1 emet al canal 3 i BILLAR 3 al canal 1).
  $STREAMLABS_DE_TAULA = @{ 1 = 1; 2 = 2; 3 = 3; 4 = 4 }

  function Camera($taula, $on) {
    if ($taula -lt 1 -or $taula -gt 4) { return }
    $sl = $STREAMLABS_DE_TAULA[$taula]
    if ($on) { AsseguraStreamlabs $sl }
    $estat.cua.Enqueue(@($sl, [bool]$on))
    $deadline = (Get-Date).AddSeconds(5)
    while ($estat.cua.Count -gt 0 -and (Get-Date) -lt $deadline) { Start-Sleep -Milliseconds 100 }
    $cams["$taula"] = [bool]$on
    # Títol de YouTube: es prova quan el directe ja ha arrencat (pot tardar)
    if ($on) { $titols["$taula"] = @{ fins = (Get-Date).AddMinutes(4); proper = (Get-Date).AddSeconds(20) } } else { $titols.Remove("$taula") }
    Escriu ("Taula {0} (Streamlabs BILLAR {1}): {2}" -f $taula, $sl, $(if ($on) { "INICIAR emissió" } else { "ATURAR emissió" }))
  }

  # En engegar el PC: obre els 4 Streamlabs (accessos directes BILLAR 1-4) i minimitza'ls
  if ($estat.obreBillars) {
    $estat.obreBillars = $false
    foreach ($n in 1..4) {
      $lnk = AccesBillar $n
      $usuari = UsuariBillar $n
      if ((StreamlabsOberts) -contains $usuari) { Escriu "BILLAR $n (usuari '$usuari') ja està obert"; continue }
      if ($lnk) { Start-Process $lnk -WindowStyle Minimized; Escriu "Obrint BILLAR $n (usuari '$usuari')"; Start-Sleep -Seconds 15 }
      else { Escriu "No trobo l'accés directe BILLAR $n a l'escriptori" }
    }
    foreach ($i in 1..6) { Start-Sleep -Seconds 10; [void][Finestres]::Minimitza("Streamlabs") }
    Escriu "Streamlabs oberts i minimitzats"
  }

  Escriu "Engegat. Escoltant ordres de l'app MARCADORS"
  $des = [DateTimeOffset]::UtcNow.ToUnixTimeMilliseconds()   # ignora ordres velles
  PublicaEstat
  $ultim = Get-Date
  $errors = 0
  while (-not $estat.atura) {
    try {
      $wc = New-Object Net.WebClient; $wc.Encoding = [Text.Encoding]::UTF8
      $r = $wc.DownloadString("$URL`?accio=ordres&clau=$CANAL&des=$des") | ConvertFrom-Json
      $errors = 0; $estat.ok = $true
      foreach ($o in $r.ordres) {
        $des = [int64]$o.id
        try { Camera ([int]$o.taula) ([bool]$o.on) }
        catch { Escriu "Error amb l'ordre: $($_.Exception.Message)" }
        try { PublicaEstat } catch {}
        $ultim = Get-Date
      }
    } catch {
      $errors++; $estat.ok = $false
      if ($errors -eq 1 -or $errors % 20 -eq 0) { Escriu "Sense connexió amb l'intermediari: $($_.Exception.Message)" }
    }
    if ($titols.Count) { try { ProvaTitols } catch { Escriu "Error amb el títol: $($_.Exception.Message)" } }
    if (((Get-Date) - $ultim).TotalMinutes -ge 5) { PublicaEstat; $ultim = Get-Date }
    Start-Sleep -Seconds 3
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

# Les tecles es premen des del fil principal (com una persona davant del PC)
$teclat = New-Object System.Windows.Forms.Timer
$teclat.Interval = 150
$teclat.add_Tick({
  while ($estat.cua.Count -gt 0) {
    $o = $estat.cua.Dequeue(); $taula = [int]$o[0]; $on = [bool]$o[1]
    $num = [byte](0x30 + $taula)
    if ($on) { [Tecles]::Prem([byte[]](0x11, 0x12), $num) } else { [Tecles]::Prem([byte[]](0x11, 0x12, 0x10), $num) }
  }
})
$teclat.Start()

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
