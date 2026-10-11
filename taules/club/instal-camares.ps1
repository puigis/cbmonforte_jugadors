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

# Tasca programada: s'engega en obrir la sessió, amb permisos d'administrador
# (els necessita per saber quins Streamlabs de cada usuari "Billar N" estan oberts)
$ps = "-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File `"$dir\camares.ps1`" -ObreBillars"
$accio = New-ScheduledTaskAction -Execute "powershell.exe" -Argument $ps -WorkingDirectory $dir
$inici = New-ScheduledTaskTrigger -AtLogOn -User $env:USERNAME
$conf  = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -ExecutionTimeLimit ([TimeSpan]::Zero) -MultipleInstances IgnoreNew
Register-ScheduledTask -TaskName "MARCADORS camares" -Action $accio -Trigger $inici -Settings $conf -RunLevel Highest -User $env:USERNAME -Force | Out-Null

# Treu l'accés directe antic de l'inici (ara ho fa la tasca) i posa'n un a l'escriptori que engega la tasca
Remove-Item (Join-Path ([Environment]::GetFolderPath("Startup")) "MARCADORS camares.lnk") -ErrorAction SilentlyContinue
$ws = New-Object -ComObject WScript.Shell
$lnk = $ws.CreateShortcut((Join-Path ([Environment]::GetFolderPath("Desktop")) "MARCADORS camares.lnk"))
$lnk.TargetPath = "schtasks.exe"
$lnk.Arguments = '/run /tn "MARCADORS camares"'
$lnk.IconLocation = "$dir\icona.ico"
$lnk.WindowStyle = 7
$lnk.Save()

Start-ScheduledTask -TaskName "MARCADORS camares"
Write-Host "Fet. El control de càmeres ja està engegat (icona a la safata, al costat del rellotge) i s'engegarà sol cada vegada que s'encengui el PC." -ForegroundColor Green
