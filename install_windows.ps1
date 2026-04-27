param(
    [Alias("p")]
    [string]$DbPassword = "",
    [Alias("a")]
    [string]$ApiUrl = "",
    [Alias("m")]
    [string]$MetricsUrl = "",
    [string]$ElephantUrl = "",
    [string]$Timezone = "",
    [Alias("B")]
    [switch]$NoBuildContainers,
    [Alias("N")]
    [switch]$NoInstallPythonPackages,
    [Alias("W")]
    [switch]$NoModifyHosts,
    [Alias("L")]
    [switch]$DisableSsl,
    [Alias("c")]
    [string]$CertFile = "",
    [Alias("k")]
    [string]$CertKey = "",
    [switch]$ActivateScenarioRunner,
    [switch]$DeactivateScenarioRunner,
    [switch]$ActivateEcoCi,
    [switch]$DeactivateEcoCi,
    [switch]$ActivatePowerHog,
    [switch]$DeactivatePowerHog,
    [switch]$ActivateCarbonDb,
    [switch]$DeactivateCarbonDb,
    [Alias("z")]
    [switch]$NoTelemetryPing,
    [Alias("ForcePing")]
    [switch]$ForceTelemetryPing
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$isWindowsHost = [System.Environment]::OSVersion.Platform -eq [System.PlatformID]::Win32NT
if (-not $isWindowsHost) {
    Write-Error "This script can only be run on native Windows PowerShell/PowerShell Core."
}

$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $Root

function Write-Step {
    param([string]$Message)
    Write-Host ""
    Write-Host $Message
}

function Read-Default {
    param(
        [string]$Prompt,
        [string]$Default
    )
    $value = Read-Host "$Prompt (default: $Default)"
    if ([string]::IsNullOrWhiteSpace($value)) {
        return $Default
    }
    return $value
}

function Read-YesNo {
    param(
        [string]$Prompt,
        [bool]$DefaultYes = $false
    )
    $suffix = "(y/N)"
    if ($DefaultYes) {
        $suffix = "(Y/n)"
    }
    $value = Read-Host "$Prompt $suffix"
    if ([string]::IsNullOrWhiteSpace($value)) {
        return $DefaultYes
    }
    return $value -in @("y", "Y", "yes", "Yes", "YES")
}

function New-RandomPassword {
    param([int]$Length = 12)
    $chars = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789"
    $bytes = New-Object byte[] $Length
    $rng = [System.Security.Cryptography.RandomNumberGenerator]::Create()
    try {
        $rng.GetBytes($bytes)
    } finally {
        $rng.Dispose()
    }
    $passwordChars = foreach ($byte in $bytes) {
        $chars[$byte % $chars.Length]
    }
    return -join $passwordChars
}

function Get-CommandPath {
    param([string[]]$Candidates)
    foreach ($candidate in $Candidates) {
        $cmd = Get-Command $candidate -ErrorAction SilentlyContinue
        if ($cmd) {
            return $cmd.Path
        }
    }
    return $null
}

function Get-PythonCommand {
    $python = Get-CommandPath @("py.exe", "python.exe", "python3.exe")
    if (-not $python) {
        Write-Error "Python 3.10+ was not found in PATH. Please install Python and rerun this script."
    }

    if ((Split-Path -Leaf $python) -ieq "py.exe") {
        return @($python, "-3")
    }
    return @($python)
}

function Invoke-Python {
    param([string[]]$Arguments)
    $command = [string]$script:PythonCommand[0]

    $prefixArguments = @()
    if ($script:PythonCommand.Length -gt 1) {
        $prefixArguments = $script:PythonCommand[1..($script:PythonCommand.Length - 1)]
    }
    & "$command" @prefixArguments @Arguments
}

function Assert-PythonVersion {
    Invoke-Python @("-c", "import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)")
    if ($LASTEXITCODE -ne 0) {
        Write-Error "Python version is NOT greater than or equal to 3.10. GMT requires Python 3.10 at least."
    }
}

function Copy-Backup {
    param([string]$Path)

    $example = "$Path.example"
    if (-not (Test-Path $example)) {
        Write-Error "Example file $example does not exist"
    }

    $maxBackups = 10
    if (Test-Path "$Path.backup.$maxBackups") {
        Remove-Item "$Path.backup.$maxBackups" -Force
    }
    for ($i = $maxBackups - 1; $i -ge 1; $i--) {
        if (Test-Path "$Path.backup.$i") {
            Move-Item "$Path.backup.$i" "$Path.backup.$($i + 1)" -Force
        }
    }
    if (Test-Path "$Path.backup") {
        Move-Item "$Path.backup" "$Path.backup.1" -Force
    }
    if (Test-Path $Path) {
        Copy-Item $Path "$Path.backup" -Force
    }

    Copy-Item $example $Path -Force
}

$utf8NoBom = [System.Text.UTF8Encoding]::new($false)

function Replace-InFile {
    param(
        [string]$Path,
        [string]$Pattern,
        [string]$Replacement
    )
    $content = Get-Content $Path -Raw -Encoding UTF8
    $content = $content.Replace($Pattern, $Replacement)
    [System.IO.File]::WriteAllText((Resolve-Path $Path).Path, $content, $utf8NoBom)
}

function Replace-RegexInFile {
    param(
        [string]$Path,
        [string]$Pattern,
        [string]$Replacement
    )
    $content = Get-Content $Path -Raw -Encoding UTF8
    $content = $content -replace $Pattern, $Replacement
    [System.IO.File]::WriteAllText((Resolve-Path $Path).Path, $content, $utf8NoBom)
}

function Get-UrlHost {
    param([string]$Url)
    try {
        return ([System.Uri]$Url).Host
    } catch {
        return ($Url -replace "^\s*.*://", "") -replace ":.*$", ""
    }
}

function Test-IsAdmin {
    $identity = [Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = New-Object Security.Principal.WindowsPrincipal($identity)
    return $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
}

function Add-HostsLine {
    param([string]$Line)
    $hostsPath = "$env:SystemRoot\System32\drivers\etc\hosts"
    $existing = Get-Content $hostsPath -ErrorAction SilentlyContinue
    if ($existing -notcontains $Line) {
        Add-Content -Path $hostsPath -Value "`r`n$Line"
    } else {
        Write-Host "Hosts entry was already present: $Line"
    }
}

function Invoke-ScaphandreProviderBuild {
    $providerDir = Join-Path $Root "metric_providers\cpu\energy\rapl\scaphandre\component"
    $sourceFile = "rapl_reader_cli.c"
    $outputBinary = "metric-provider-binary"

    Write-Step "Building scaphandre RAPL provider binary"

    # Happy path: cl.exe already in PATH (Developer Command Prompt / Developer PowerShell)
    if (Get-Command "cl.exe" -ErrorAction SilentlyContinue) {
        Push-Location $providerDir
        try {
            & cl.exe $sourceFile "/Fe:$outputBinary" /O2 /W3 /nologo /link winmm.lib
            if ($LASTEXITCODE -ne 0) {
                Write-Warning "Compilation failed. Build manually by running build.bat from an x64 Native Tools Command Prompt in:`n  $providerDir"
            } else {
                Write-Host "Successfully built metric-provider-binary.exe"
            }
        } finally {
            Pop-Location
        }
        return
    }

    # Fall back: locate MSVC via vswhere.exe
    $vswherePath = @(
        "${env:ProgramFiles(x86)}\Microsoft Visual Studio\Installer\vswhere.exe",
        "${env:ProgramFiles}\Microsoft Visual Studio\Installer\vswhere.exe"
    ) | Where-Object { Test-Path $_ } | Select-Object -First 1

    if ($vswherePath) {
        $vsInstallPath = & $vswherePath -latest -requires Microsoft.VisualCpp.Tools.HostX64.TargetX64 -property installationPath 2>$null
        if ($vsInstallPath) {
            $vcvarsall = Join-Path $vsInstallPath "VC\Auxiliary\Build\vcvarsall.bat"
            if (Test-Path $vcvarsall) {
                Write-Host "Found Visual Studio at: $vsInstallPath"
                $absSource = Join-Path $providerDir $sourceFile
                $absOutput = Join-Path $providerDir $outputBinary
                # Run via cmd.exe so vcvarsall environment is inherited by cl.exe
                $cmdLine = "`"$vcvarsall`" x64 >nul 2>&1 && cl.exe `"$absSource`" /Fe:`"$absOutput`" /O2 /W3 /nologo /link winmm.lib"
                Start-Process -FilePath "cmd.exe" -ArgumentList "/c $cmdLine" -Wait -NoNewWindow
                if ($LASTEXITCODE -ne 0) {
                    Write-Warning "Compilation failed. Build manually by running build.bat from an x64 Native Tools Command Prompt in:`n  $providerDir"
                } else {
                    Write-Host "Successfully built metric-provider-binary.exe"
                }
                return
            }
        }
    }

    Write-Warning "MSVC compiler (cl.exe) not found. The scaphandre RAPL energy provider was not built."
    Write-Warning "To build it manually, open 'x64 Native Tools Command Prompt for VS 2022' and run build.bat in:"
    Write-Warning "  $providerDir"
}

function Send-TelemetryPing {
    $machineGuid = "unknown"
    try {
        $machineGuid = (Get-ItemProperty "HKLM:\SOFTWARE\Microsoft\Cryptography").MachineGuid
    } catch {
        $machineGuid = [System.Environment]::MachineName
    }
    $randomHash = [Guid]::NewGuid().ToString("N").Substring(0, 16)
    $body = @{
        name = "install"
        url = "http://hello.green-coding.io/install"
        domain = "hello.green-coding.io"
        props = @{
            unique_hash = $machineGuid
            arch = $env:PROCESSOR_ARCHITECTURE
            os = "Windows"
            os_version = [System.Environment]::OSVersion.VersionString
        }
    } | ConvertTo-Json -Depth 4
    Invoke-WebRequest -Uri "https://plausible.io/api/event" -Method Post -Body $body -ContentType "application/json" -Headers @{"User-Agent" = $randomHash} | Out-Null
}

$script:PythonCommand = Get-PythonCommand
Assert-PythonVersion

if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
    Write-Error "Git was not found in PATH. Please install Git for Windows and rerun this script."
}

if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    Write-Error "Docker was not found in PATH. Please install Docker Desktop and rerun this script."
}

docker version | Out-Null
if ($LASTEXITCODE -ne 0) {
    Write-Error "Docker Desktop is not reachable. Please start Docker Desktop with Linux containers enabled."
}

$enableSsl = -not $DisableSsl
$modifyHosts = -not $NoModifyHosts
$buildContainers = -not $NoBuildContainers
$installPythonPackages = -not $NoInstallPythonPackages

$activateScenarioRunnerValue = $true
if ($ActivateScenarioRunner) { $activateScenarioRunnerValue = $true }
elseif ($DeactivateScenarioRunner) { $activateScenarioRunnerValue = $false }
else { $activateScenarioRunnerValue = Read-YesNo "Do you want to activate ScenarioRunner (For benchmarking container software)?" $true }

$activateEcoCiValue = $false
if ($ActivateEcoCi) { $activateEcoCiValue = $true }
elseif ($DeactivateEcoCi) { $activateEcoCiValue = $false }
else { $activateEcoCiValue = Read-YesNo "Do you want to activate Eco CI (For tracking CI/CD carbon emissions)?" $false }

$activateCarbonDbValue = $false
if ($ActivateCarbonDb) { $activateCarbonDbValue = $true }
elseif ($DeactivateCarbonDb) { $activateCarbonDbValue = $false }
else { $activateCarbonDbValue = Read-YesNo "Do you want to activate CarbonDB?" $false }

$activatePowerHogValue = $false
if ($ActivatePowerHog) { $activatePowerHogValue = $true }
elseif ($DeactivatePowerHog) { $activatePowerHogValue = $false }
else { $activatePowerHogValue = Read-YesNo "Do you want to activate PowerHOG?" $false }

if ([string]::IsNullOrWhiteSpace($ApiUrl)) {
    $ApiUrl = Read-Default "Please enter the desired API endpoint URL. Use port 9142 for local installs and no port for production to auto-use 80/443" "http://api.green-coding.internal:9142"
}
if ([string]::IsNullOrWhiteSpace($MetricsUrl)) {
    $MetricsUrl = Read-Default "Please enter the desired metrics dashboard URL. Use port 9142 for local installs and no port for production to auto-use 80/443" "http://metrics.green-coding.internal:9142"
}
if ([string]::IsNullOrWhiteSpace($ElephantUrl)) {
    if (Read-YesNo "Use the Elephant Carbon Service?" $false) {
        $ElephantUrl = Read-Default "Please enter the Elephant Carbon Service URL" "http://elephant.green-coding.internal:8085"
    }
}
if ([string]::IsNullOrWhiteSpace($Timezone)) {
    $winToIana = @{
        "Dateline Standard Time"="Etc/GMT+12"; "UTC-11"="Etc/GMT+11"; "Aleutian Standard Time"="America/Adak";
        "Hawaiian Standard Time"="Pacific/Honolulu"; "Marquesas Standard Time"="Pacific/Marquesas";
        "Alaskan Standard Time"="America/Anchorage"; "UTC-09"="Etc/GMT+9"; "Pacific Standard Time (Mexico)"="America/Tijuana";
        "UTC-08"="Etc/GMT+8"; "Pacific Standard Time"="America/Los_Angeles"; "US Mountain Standard Time"="America/Phoenix";
        "Mountain Standard Time (Mexico)"="America/Chihuahua"; "Mountain Standard Time"="America/Denver";
        "Central America Standard Time"="America/Guatemala"; "Central Standard Time"="America/Chicago";
        "Easter Island Standard Time"="Pacific/Easter"; "Central Standard Time (Mexico)"="America/Mexico_City";
        "Canada Central Standard Time"="America/Regina"; "SA Pacific Standard Time"="America/Bogota";
        "Eastern Standard Time (Mexico)"="America/Cancun"; "Eastern Standard Time"="America/New_York";
        "Haiti Standard Time"="America/Port-au-Prince"; "Cuba Standard Time"="America/Havana";
        "US Eastern Standard Time"="America/Indianapolis"; "Turks And Caicos Standard Time"="America/Grand_Turk";
        "Paraguay Standard Time"="America/Asuncion"; "Atlantic Standard Time"="America/Halifax";
        "Venezuela Standard Time"="America/Caracas"; "Central Brazilian Standard Time"="America/Cuiaba";
        "SA Western Standard Time"="America/La_Paz"; "Pacific SA Standard Time"="America/Santiago";
        "Newfoundland Standard Time"="America/St_Johns"; "Tocantins Standard Time"="America/Araguaina";
        "E. South America Standard Time"="America/Sao_Paulo"; "SA Eastern Standard Time"="America/Cayenne";
        "Argentina Standard Time"="America/Buenos_Aires"; "Greenland Standard Time"="America/Godthab";
        "Montevideo Standard Time"="America/Montevideo"; "Magallanes Standard Time"="America/Punta_Arenas";
        "Saint Pierre Standard Time"="America/Miquelon"; "Bahia Standard Time"="America/Bahia";
        "UTC-02"="Etc/GMT+2"; "Azores Standard Time"="Atlantic/Azores"; "Cape Verde Standard Time"="Atlantic/Cape_Verde";
        "UTC"="UTC"; "GMT Standard Time"="Europe/London"; "Greenwich Standard Time"="Atlantic/Reykjavik";
        "Sao Tome Standard Time"="Africa/Sao_Tome"; "Morocco Standard Time"="Africa/Casablanca";
        "W. Europe Standard Time"="Europe/Berlin"; "Central Europe Standard Time"="Europe/Budapest";
        "Romance Standard Time"="Europe/Paris"; "Central European Standard Time"="Europe/Warsaw";
        "W. Central Africa Standard Time"="Africa/Lagos"; "Jordan Standard Time"="Asia/Amman";
        "GTB Standard Time"="Europe/Bucharest"; "Middle East Standard Time"="Asia/Beirut";
        "Egypt Standard Time"="Africa/Cairo"; "E. Europe Standard Time"="Asia/Nicosia";
        "Syria Standard Time"="Asia/Damascus"; "West Bank Standard Time"="Asia/Hebron";
        "South Africa Standard Time"="Africa/Johannesburg"; "FLE Standard Time"="Europe/Kiev";
        "Israel Standard Time"="Asia/Jerusalem"; "Kaliningrad Standard Time"="Europe/Kaliningrad";
        "Sudan Standard Time"="Africa/Khartoum"; "Libya Standard Time"="Africa/Tripoli";
        "Namibia Standard Time"="Africa/Windhoek"; "Arabic Standard Time"="Asia/Baghdad";
        "Turkey Standard Time"="Europe/Istanbul"; "Arab Standard Time"="Asia/Riyadh";
        "Belarus Standard Time"="Europe/Minsk"; "Russian Standard Time"="Europe/Moscow";
        "E. Africa Standard Time"="Africa/Nairobi"; "Iran Standard Time"="Asia/Tehran";
        "Arabian Standard Time"="Asia/Dubai"; "Astrakhan Standard Time"="Europe/Astrakhan";
        "Azerbaijan Standard Time"="Asia/Baku"; "Russia Time Zone 3"="Europe/Samara";
        "Mauritius Standard Time"="Indian/Mauritius"; "Saratov Standard Time"="Europe/Saratov";
        "Georgian Standard Time"="Asia/Tbilisi"; "Volgograd Standard Time"="Europe/Volgograd";
        "Caucasus Standard Time"="Asia/Yerevan"; "Afghanistan Standard Time"="Asia/Kabul";
        "West Asia Standard Time"="Asia/Tashkent"; "Ekaterinburg Standard Time"="Asia/Yekaterinburg";
        "Pakistan Standard Time"="Asia/Karachi"; "Qyzylorda Standard Time"="Asia/Qyzylorda";
        "India Standard Time"="Asia/Calcutta"; "Sri Lanka Standard Time"="Asia/Colombo";
        "Nepal Standard Time"="Asia/Katmandu"; "Central Asia Standard Time"="Asia/Almaty";
        "Bangladesh Standard Time"="Asia/Dhaka"; "Omsk Standard Time"="Asia/Omsk";
        "Myanmar Standard Time"="Asia/Rangoon"; "SE Asia Standard Time"="Asia/Bangkok";
        "Altai Standard Time"="Asia/Barnaul"; "W. Mongolia Standard Time"="Asia/Hovd";
        "North Asia Standard Time"="Asia/Krasnoyarsk"; "N. Central Asia Standard Time"="Asia/Novosibirsk";
        "Tomsk Standard Time"="Asia/Tomsk"; "China Standard Time"="Asia/Shanghai";
        "North Asia East Standard Time"="Asia/Irkutsk"; "Singapore Standard Time"="Asia/Singapore";
        "W. Australia Standard Time"="Australia/Perth"; "Taipei Standard Time"="Asia/Taipei";
        "Ulaanbaatar Standard Time"="Asia/Ulaanbaatar"; "Aus Central W. Standard Time"="Australia/Eucla";
        "Transbaikal Standard Time"="Asia/Chita"; "Tokyo Standard Time"="Asia/Tokyo";
        "North Korea Standard Time"="Asia/Pyongyang"; "Korea Standard Time"="Asia/Seoul";
        "Yakutsk Standard Time"="Asia/Yakutsk"; "Cen. Australia Standard Time"="Australia/Adelaide";
        "AUS Central Standard Time"="Australia/Darwin"; "E. Australia Standard Time"="Australia/Brisbane";
        "AUS Eastern Standard Time"="Australia/Sydney"; "West Pacific Standard Time"="Pacific/Port_Moresby";
        "Tasmania Standard Time"="Australia/Hobart"; "Vladivostok Standard Time"="Asia/Vladivostok";
        "Lord Howe Standard Time"="Australia/Lord_Howe"; "Bougainville Standard Time"="Pacific/Bougainville";
        "Russia Time Zone 10"="Asia/Srednekolymsk"; "Magadan Standard Time"="Asia/Magadan";
        "Norfolk Standard Time"="Pacific/Norfolk"; "Sakhalin Standard Time"="Asia/Sakhalin";
        "Central Pacific Standard Time"="Pacific/Guadalcanal"; "Russia Time Zone 11"="Asia/Kamchatka";
        "New Zealand Standard Time"="Pacific/Auckland"; "UTC+12"="Etc/GMT-12";
        "Fiji Standard Time"="Pacific/Fiji"; "Chatham Islands Standard Time"="Pacific/Chatham";
        "UTC+13"="Etc/GMT-13"; "Tonga Standard Time"="Pacific/Tongatapu";
        "Samoa Standard Time"="Pacific/Apia"; "Line Islands Standard Time"="Pacific/Kiritimati"
    }
    $winId = [System.TimeZoneInfo]::Local.Id
    $ianaDefault = if ($winToIana.ContainsKey($winId)) { $winToIana[$winId] } else { $winId }
    $Timezone = Read-Default "Enter timezone for Postgres and containers (e.g., Europe/Berlin)" $ianaDefault
}

$passwordFromFile = ""
if (Test-Path "config.yml") {
    $configText = Get-Content "config.yml" -Raw
    $match = [regex]::Match($configText, "(?ms)^postgresql:\s+.*?^\s+password:\s*(\S+)")
    if ($match.Success) {
        $passwordFromFile = $match.Groups[1].Value
    }
}

$defaultPassword = if ($passwordFromFile) { $passwordFromFile } else { New-RandomPassword 12 }
if ([string]::IsNullOrWhiteSpace($DbPassword)) {
    $securePassword = Read-Host "Please enter the new password to be set for the PostgreSQL DB (default: $defaultPassword)" -AsSecureString
    if ($securePassword.Length -eq 0) {
        $DbPassword = $defaultPassword
    } else {
        $DbPassword = [Runtime.InteropServices.Marshal]::PtrToStringAuto([Runtime.InteropServices.Marshal]::SecureStringToBSTR($securePassword))
    }
}

if ($enableSsl -and [string]::IsNullOrWhiteSpace($CertKey) -and [string]::IsNullOrWhiteSpace($CertFile)) {
    $enableSsl = Read-YesNo "Do you want to enable SSL for the API and frontend?" $false
}
if ($enableSsl) {
    if ([string]::IsNullOrWhiteSpace($CertKey)) {
        $CertKey = Read-Host "Please type the path to your key file"
    }
    if ([string]::IsNullOrWhiteSpace($CertFile)) {
        $CertFile = Read-Host "Please type the path to your certificate file"
    }
    Copy-Item $CertKey "docker/nginx/ssl/production.key" -Force
    Copy-Item $CertFile "docker/nginx/ssl/production.crt" -Force
}

if ($ForceTelemetryPing -or ((-not $NoTelemetryPing) -and (Read-YesNo "Developing software can be a lonely business. Want to let us know you are installing the GMT? No personal data will be shared!" $false))) {
    Send-TelemetryPing
}

Write-Step "Updating configuration files"
$repoPathForDocker = (Resolve-Path ".").Path -replace "\\", "/"

Copy-Item "docker/compose.yml.example" "docker/compose.yml" -Force
Replace-InFile "docker/compose.yml" "PATH_TO_GREEN_METRICS_TOOL_REPO" $repoPathForDocker
Replace-InFile "docker/compose.yml" "PLEASE_CHANGE_THIS" $DbPassword
Replace-InFile "docker/compose.yml" "__TZ__" $Timezone

Copy-Backup "config.yml"
Replace-InFile "config.yml" "PLEASE_CHANGE_THIS" $DbPassword
Replace-InFile "config.yml" "__API_URL__" $ApiUrl
Replace-InFile "config.yml" "__METRICS_URL__" $MetricsUrl
Replace-RegexInFile "config.yml" "activate_scenario_runner:.*" ("activate_scenario_runner: " + $activateScenarioRunnerValue)
Replace-RegexInFile "config.yml" "activate_eco_ci:.*" ("activate_eco_ci: " + $activateEcoCiValue)
Replace-RegexInFile "config.yml" "activate_power_hog:.*" ("activate_power_hog: " + $activatePowerHogValue)
Replace-RegexInFile "config.yml" "activate_carbon_db:.*" ("activate_carbon_db: " + $activateCarbonDbValue)

$hostMetricsUrl = Get-UrlHost $MetricsUrl
$hostApiUrl = Get-UrlHost $ApiUrl

Copy-Backup "docker/nginx/api.conf"
Replace-InFile "docker/nginx/api.conf" "__API_URL__" $hostApiUrl

Copy-Backup "docker/nginx/block-and-redirect.conf"
Replace-InFile "docker/nginx/block-and-redirect.conf" "__API_URL__" $hostApiUrl
Replace-InFile "docker/nginx/block-and-redirect.conf" "__METRICS_URL__" $hostMetricsUrl

Copy-Backup "docker/nginx/frontend.conf"
Replace-InFile "docker/nginx/frontend.conf" "__METRICS_URL__" $hostMetricsUrl

Copy-Backup "frontend/js/helpers/config.js"
Replace-InFile "frontend/js/helpers/config.js" "__API_URL__" $ApiUrl
Replace-InFile "frontend/js/helpers/config.js" "__METRICS_URL__" $MetricsUrl
Replace-InFile "frontend/js/helpers/config.js" "__ELEPHANT_URL__" $ElephantUrl
Replace-InFile "frontend/js/helpers/config.js" "__ACTIVATE_SCENARIO_RUNNER__" $activateScenarioRunnerValue.ToString().ToLowerInvariant()
Replace-InFile "frontend/js/helpers/config.js" "__ACTIVATE_ECO_CI__" $activateEcoCiValue.ToString().ToLowerInvariant()
Replace-InFile "frontend/js/helpers/config.js" "__ACTIVATE_POWER_HOG__" $activatePowerHogValue.ToString().ToLowerInvariant()
Replace-InFile "frontend/js/helpers/config.js" "__ACTIVATE_CARBON_DB__" $activateCarbonDbValue.ToString().ToLowerInvariant()
Replace-InFile "frontend/js/helpers/config.js" "__ACTIVATE_AI_OPTIMISATIONS__" "false"

if ($enableSsl) {
    Replace-InFile "docker/compose.yml" "9142:9142" "443:443"
    Replace-InFile "docker/nginx/frontend.conf" "#__SSL__" ""
    Replace-InFile "docker/nginx/api.conf" "#__SSL__" ""
    Replace-InFile "docker/nginx/block-and-redirect.conf" "#__SSL__" ""
} else {
    Replace-InFile "docker/nginx/frontend.conf" "#__DEFAULT__" ""
    Replace-InFile "docker/nginx/api.conf" "#__DEFAULT__" ""
    Replace-InFile "docker/nginx/block-and-redirect.conf" "#__DEFAULT__" ""
}

if ($modifyHosts) {
    if (-not (Test-IsAdmin)) {
        Write-Warning "Skipping hosts file changes because this shell is not running as Administrator. Rerun as Administrator or add api/dashboard hostnames manually."
    } else {
        Write-Step "Writing to Windows hosts file"
        Add-HostsLine "127.0.0.1 green-coding-postgres-container green-coding-redis-container"
        if ($hostMetricsUrl -like "*.green-coding.internal") {
            Add-HostsLine "127.0.0.1 $hostApiUrl $hostMetricsUrl"
        }
    }
}

if ($activateScenarioRunnerValue) {
    Write-Step "Checking out further git submodules"
    git submodule update --init metric_providers/psu/energy/ac/xgboost/machine/model
}

Write-Step "Setting up Python venv"
Invoke-Python @("-m", "venv", "venv")
$venvPython = Join-Path $Root "venv\Scripts\python.exe"
if (-not (Test-Path $venvPython)) {
    Write-Error "Could not find venv Python at $venvPython"
}

Write-Step "Setting GMT in include path for Python via .pth file"
& $venvPython -c "import os, pathlib, site; [pathlib.Path(p, 'gmt-lib.pth').write_text(os.getcwd(), encoding='utf-8') for p in site.getsitepackages()]"

if ($installPythonPackages) {
    Write-Step "Updating Python requirements"
    & $venvPython -m pip install --timeout 100 --retries 10 --upgrade pip
    & $venvPython -m pip install --timeout 100 --retries 10 -r requirements.txt
    & $venvPython -m pip install --timeout 100 --retries 10 -r docker/requirements.txt
    & $venvPython -m pip install --timeout 100 --retries 10 -r metric_providers/psu/energy/ac/xgboost/machine/model/requirements.txt
}

Invoke-ScaphandreProviderBuild

if ($buildContainers) {
    Write-Step "Building / Updating docker containers"
    docker compose -f docker/compose.yml down
    docker compose -f docker/compose.yml build
    docker compose -f docker/compose.yml pull
}

Write-Host ""
Write-Host "Successfully installed Green Metrics Tool!" -ForegroundColor Green
Write-Host "Please remember to activate your venv when using GMT:"
Write-Host "  .\venv\Scripts\Activate.ps1"
