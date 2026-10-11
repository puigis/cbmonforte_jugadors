# Instal·la el control de càmeres de MARCADORS al PC del club
# Ús (PowerShell):  irm https://raw.githubusercontent.com/puigis/cbmonforte_jugadors/main/taules/club/instal-camares.ps1 | iex
$dir = "C:\MARCADORS"
New-Item -ItemType Directory -Force -Path $dir | Out-Null
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
Invoke-WebRequest -UseBasicParsing "https://raw.githubusercontent.com/puigis/cbmonforte_jugadors/main/taules/club/camares.ps1" -OutFile "$dir\camares.ps1"

# Accés directe a l'inici de Windows (s'engega sol en obrir la sessió)
$ws = New-Object -ComObject WScript.Shell
foreach ($lloc in @([Environment]::GetFolderPath("Startup"), [Environment]::GetFolderPath("Desktop"))) {
  $lnk = $ws.CreateShortcut((Join-Path $lloc "MARCADORS camares.lnk"))
  $lnk.TargetPath = "powershell.exe"
  $lnk.Arguments = "-NoProfile -ExecutionPolicy Bypass -WindowStyle Minimized -File `"$dir\camares.ps1`""
  $lnk.WorkingDirectory = $dir
  $lnk.Save()
}
Start-Process powershell.exe -ArgumentList "-NoProfile -ExecutionPolicy Bypass -WindowStyle Minimized -File `"$dir\camares.ps1`""
Write-Host "Fet. El control de càmeres ja està engegat i s'engegarà sol cada vegada que s'encengui el PC." -ForegroundColor Green
