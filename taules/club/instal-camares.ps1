# Instal·la el control de càmeres de MARCADORS al PC del club
# Ús (PowerShell):  irm https://raw.githubusercontent.com/puigis/cbmonforte_jugadors/main/taules/club/instal-camares.ps1 | iex
$dir = "C:\MARCADORS"
New-Item -ItemType Directory -Force -Path $dir | Out-Null
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
# Atura la versió anterior si està en marxa
Get-CimInstance Win32_Process -Filter "Name='powershell.exe'" -ErrorAction SilentlyContinue | Where-Object { $_.CommandLine -like "*camares.ps1*" } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
$rev = if ($REV) { $REV } else { "main" }
Invoke-WebRequest -UseBasicParsing "https://raw.githubusercontent.com/puigis/cbmonforte_jugadors/$rev/taules/club/camares.ps1" -OutFile "$dir\camares.ps1"
Invoke-WebRequest -UseBasicParsing "https://raw.githubusercontent.com/puigis/cbmonforte_jugadors/$rev/taules/club/icona-camares.png" -OutFile "$dir\icona.png"
Invoke-WebRequest -UseBasicParsing "https://raw.githubusercontent.com/puigis/cbmonforte_jugadors/$rev/taules/club/icona-camares.ico" -OutFile "$dir\icona.ico"

# Accés directe a l'inici de Windows (s'engega sol en obrir la sessió)
$ws = New-Object -ComObject WScript.Shell
foreach ($lloc in @([Environment]::GetFolderPath("Startup"), [Environment]::GetFolderPath("Desktop"))) {
  $lnk = $ws.CreateShortcut((Join-Path $lloc "MARCADORS camares.lnk"))
  $lnk.TargetPath = "powershell.exe"
  # A l'inici de Windows, a més, obre els 4 Streamlabs i els minimitza
  $extra = if ($lloc -eq [Environment]::GetFolderPath("Startup")) { " -ObreBillars" } else { "" }
  $lnk.Arguments = "-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File `"$dir\camares.ps1`"$extra"
  $lnk.WorkingDirectory = $dir
  $lnk.IconLocation = "$dir\icona.ico"
  $lnk.Save()
}
Start-Process powershell.exe -ArgumentList "-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File `"$dir\camares.ps1`""
Write-Host "Fet. El control de càmeres ja està engegat (icona a la safata, al costat del rellotge) i s'engegarà sol cada vegada que s'encengui el PC." -ForegroundColor Green
