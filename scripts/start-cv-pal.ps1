<#
.SYNOPSIS
    Start CV Pal on Windows with one command.

.DESCRIPTION
    Brings up the docker compose stack and points it at the Ollama already installed on
    this machine, rather than the `ollama` compose profile.

    Why the host's Ollama: on Windows the container is CPU-only unless WSL GPU
    passthrough is configured, and it downloads its models into a separate volume — so a
    machine with a GPU and models already pulled would get slower answers after
    re-downloading gigabytes it already has. The container profile stays in
    docker-compose.yml for anyone without a local install.

.PARAMETER Build
    Build the images from this checkout instead of pulling the published ones from
    ghcr.io, using the docker-compose.build.yml overlay. Use it when you have changed
    the code, or when no release has been published yet (the pull is then refused).

.PARAMETER CheckOnly
    Run the preflight (.env, Ollama, Docker) and exit without building, starting, or
    opening anything. Exits non-zero if the stack could not start. Use it to see what is
    wrong without waiting for a build.

.EXAMPLE
    .\start-cv-pal.cmd

.EXAMPLE
    .\start-cv-pal.cmd -CheckOnly

.EXAMPLE
    .\start-cv-pal.cmd -Build
#>
[CmdletBinding()]
param([switch]$CheckOnly, [switch]$Build)

$ErrorActionPreference = 'Stop'
Set-Location (Join-Path $PSScriptRoot '..')

$OllamaHostUrl   = 'http://host.docker.internal:11434/v1'
$OllamaComposeUrl = 'http://ollama:11434/v1'
$OllamaTagsUrl   = 'http://localhost:11434/api/tags'
$AppUrl          = 'http://localhost:8080'

function Write-Step { param($Message) Write-Host ""; Write-Host "==> $Message" -ForegroundColor Cyan }
function Write-Ok   { param($Message) Write-Host "    $Message" -ForegroundColor Green }
function Write-Note { param($Message) Write-Host "    $Message" -ForegroundColor Yellow }
function Stop-WithError {
    param($Message)
    Write-Host ""
    Write-Host "!!! $Message" -ForegroundColor Red
    exit 1
}

# Written without a BOM: pydantic-settings reads .env literally, and a BOM would make the
# first key `<feff>CV_PAL_SECRET_KEY`, which reads as unset.
function Write-EnvFile {
    param($Path, $Text)
    $utf8NoBom = New-Object System.Text.UTF8Encoding($false)
    [System.IO.File]::WriteAllText((Resolve-Path $Path), $Text, $utf8NoBom)
}

function Get-EnvValue {
    param($Text, $Name)
    $match = [regex]::Match($Text, "(?m)^$Name=(.*)$")
    if ($match.Success) { return $match.Groups[1].Value.Trim() }
    return ''
}

function Test-DockerRunning {
    # Through cmd.exe so the native command's stderr never becomes a PowerShell error
    # record; only the exit code matters here.
    & cmd.exe /c "docker info >nul 2>&1"
    return ($LASTEXITCODE -eq 0)
}

function Get-OllamaTags {
    try { return Invoke-RestMethod -Uri $OllamaTagsUrl -TimeoutSec 3 } catch { return $null }
}

# ---------------------------------------------------------------- 1. configuration

Write-Step "Checking configuration"

if (-not (Test-Path '.env')) {
    if (-not (Test-Path '.env.docker.example')) {
        Stop-WithError "Neither .env nor .env.docker.example found. Run this from the repository."
    }
    Copy-Item '.env.docker.example' '.env'
    Write-Ok "Created .env from .env.docker.example"
}

$envText = Get-Content '.env' -Raw
$envChanged = $false

# The backend has no default for this and refuses to start without it, by design.
if ($envText -match '(?m)^CV_PAL_SECRET_KEY=\s*$') {
    $bytes = New-Object byte[] 32
    $rng = [System.Security.Cryptography.RandomNumberGenerator]::Create()
    try { $rng.GetBytes($bytes) } finally { $rng.Dispose() }
    $secret = ($bytes | ForEach-Object { $_.ToString('x2') }) -join ''
    $envText = $envText -replace '(?m)^CV_PAL_SECRET_KEY=\s*$', "CV_PAL_SECRET_KEY=$secret"
    $envChanged = $true
    Write-Ok "Generated CV_PAL_SECRET_KEY"
} else {
    Write-Ok "CV_PAL_SECRET_KEY is set"
}

# Only the untouched example default is rewritten, so a deliberate choice is left alone.
$escapedComposeUrl = [regex]::Escape($OllamaComposeUrl)
if ($envText -match "(?m)^CV_PAL_LLM_BASE_URL=$escapedComposeUrl\s*$") {
    $envText = $envText -replace "(?m)^CV_PAL_LLM_BASE_URL=$escapedComposeUrl\s*$", "CV_PAL_LLM_BASE_URL=$OllamaHostUrl"
    $envChanged = $true
    Write-Ok "Pointed CV_PAL_LLM_BASE_URL at this machine's Ollama"
}

if ($envChanged) { Write-EnvFile '.env' $envText }

$provider = Get-EnvValue $envText 'CV_PAL_LLM_PROVIDER'
$model    = Get-EnvValue $envText 'CV_PAL_LLM_MODEL'
$baseUrl  = Get-EnvValue $envText 'CV_PAL_LLM_BASE_URL'
Write-Ok "Model provider: $provider ($model)"

# ---------------------------------------------------------------- 2. Ollama

$usesLocalOllama = ($provider -eq 'ollama') -and
                   ($baseUrl -match 'host\.docker\.internal|localhost|127\.0\.0\.1')

if (-not $usesLocalOllama) {
    Write-Step "Skipping Ollama"
    Write-Ok "Configured for '$provider' at '$baseUrl'"
} else {
    Write-Step "Checking Ollama"
    $tags = Get-OllamaTags

    if (-not $tags) {
        Write-Note "Not responding on 11434, starting it..."
        Start-Process -FilePath 'ollama' -ArgumentList 'list' -WindowStyle Hidden -ErrorAction SilentlyContinue
        for ($i = 0; $i -lt 15; $i++) {
            Start-Sleep -Seconds 2
            $tags = Get-OllamaTags
            if ($tags) { break }
        }
    }

    if (-not $tags) {
        Write-Note "Ollama is not reachable on $OllamaTagsUrl."
        Write-Note "The app will still run; only the AI review will fail. Install: https://ollama.com/download"
    } else {
        $installed = @($tags.models | ForEach-Object { $_.name })
        $hasModel = ($installed -contains $model) -or ($installed -contains "${model}:latest")

        if ($hasModel) {
            Write-Ok "Model '$model' is installed"
        } else {
            Write-Note "Model '$model' is not installed. Available: $($installed -join ', ')"
            if ($CheckOnly) {
                Write-Note "Pull it with:  ollama pull $model"
            } else {
                $answer = Read-Host "    Pull '$model' now? This can be several GB [y/N]"
                if ($answer -match '^(y|yes)$') {
                    & ollama pull $model
                    if ($LASTEXITCODE -ne 0) { Write-Note "Pull failed. Continuing without a model." }
                } else {
                    Write-Note "Skipped. Set CV_PAL_LLM_MODEL in .env to one of the models above instead."
                }
            }
        }
    }
}

# ---------------------------------------------------------------- 3. Docker

Write-Step "Checking Docker"

if (Test-DockerRunning) {
    Write-Ok "Docker is running"
} else {
    $dockerDesktop = Join-Path $env:ProgramFiles 'Docker\Docker\Docker Desktop.exe'
    if (-not (Test-Path $dockerDesktop)) {
        Stop-WithError "Docker Desktop not found at $dockerDesktop. Install it: https://www.docker.com/products/docker-desktop/"
    }

    Write-Note "Not running. Starting Docker Desktop (this takes a minute)..."
    Start-Process -FilePath $dockerDesktop

    $started = $false
    for ($i = 0; $i -lt 24; $i++) {
        Start-Sleep -Seconds 5
        if (Test-DockerRunning) { $started = $true; break }
        Write-Host "    ...waiting ($([int](($i + 1) * 5))s)" -ForegroundColor DarkGray
    }
    if (-not $started) {
        Stop-WithError "Docker Desktop did not become ready within two minutes. Start it manually and run this again."
    }
    Write-Ok "Docker is running"
}

if ($CheckOnly) {
    Write-Step "Preflight passed"
    Write-Ok "Run start-cv-pal.cmd without -CheckOnly to start the app."
    exit 0
}

# ---------------------------------------------------------------- 4. start

if ($Build) {
    Write-Step "Building CV Pal from this checkout (the first build takes several minutes)"
    & docker compose -f docker-compose.yml -f docker-compose.build.yml up -d --build
} else {
    Write-Step "Starting CV Pal (the first start downloads the images, a few minutes)"
    # No --pull: images come down on first start and stay put. Updating is deliberate,
    # via `docker compose pull`, so the app cannot change under you mid-application.
    & docker compose up -d
}
if ($LASTEXITCODE -ne 0) {
    if (-not $Build) {
        Write-Note "If the error says 'denied', no release has been published to ghcr.io yet."
        Write-Note "Build from source instead:  .\start-cv-pal.cmd -Build"
    }
    Stop-WithError "docker compose failed. See the output above, or run: docker compose logs"
}

Write-Step "Waiting for the app"
$ready = $false
for ($i = 0; $i -lt 60; $i++) {
    try {
        $response = Invoke-WebRequest -Uri $AppUrl -TimeoutSec 3 -UseBasicParsing
        if ($response.StatusCode -eq 200) { $ready = $true; break }
    } catch {
        # The frontend container waits for the backend healthcheck, so connection
        # refused is the normal state for the first half-minute.
    }
    Start-Sleep -Seconds 3
}

if (-not $ready) {
    Stop-WithError "The app did not answer on $AppUrl within three minutes. Check: docker compose logs backend"
}

Write-Ok "Ready"
Start-Process $AppUrl

Write-Host ""
Write-Host "    CV Pal is running at $AppUrl" -ForegroundColor Green
Write-Host "    Stop it with:  docker compose stop" -ForegroundColor DarkGray
Write-Host "    See logs with: docker compose logs -f" -ForegroundColor DarkGray
Write-Host ""
