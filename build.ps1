<#
.SYNOPSIS
    Builds a release zip for the Search Related Features QGIS plugin.

.DESCRIPTION
    Compiles the .ts translations to .qm, checks the metadata, and packages the
    plugin into a zip that can be installed through
    "Plugins > Manage and Install Plugins > Install from ZIP".

    The compile step is the reason this script exists: a zip without .qm files
    silently falls back to English, with no error anywhere.

.PARAMETER Deploy
    Also copy the built plugin into the QGIS profile, for local testing.

.PARAMETER Profile
    Which QGIS profile to deploy into. Default: default

.PARAMETER Release
    Run the extra checks that must pass before publishing to the official
    QGIS plugin repository. Fails the build if something is missing.

.PARAMETER LReleasePath
    Full path to lrelease.exe, if the script cannot find it by itself.

.PARAMETER Linguist
    Open Qt Linguist on the .ts files and exit. Use this when the QGIS
    installation ships linguist.exe but no lrelease.exe: File > Release in
    Linguist produces the same .qm file.

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File .\build.ps1
    powershell -ExecutionPolicy Bypass -File .\build.ps1 -Deploy -Profile NST
    powershell -ExecutionPolicy Bypass -File .\build.ps1 -Release
#>

[CmdletBinding()]
param(
    [switch]$Deploy,
    [string]$Profile = "default",
    [switch]$Release,
    [string]$LReleasePath,
    [switch]$Linguist
)

$ErrorActionPreference = "Stop"

$PluginName = "search_related_features"
$Root       = $PSScriptRoot
$BuildDir   = Join-Path $Root "build"
$StageDir   = Join-Path $BuildDir $PluginName

# Files and folders that must never end up in the zip. __pycache__ holds
# bytecode from your machine, and a stale .pyc can shadow a module you renamed.
$Exclude = @("__pycache__", ".git", ".gitignore", ".vscode", "build",
             "*.zip", "*.pyc", "*.pyo")

function Write-Step($text) { Write-Host "==> $text" -ForegroundColor Cyan }
function Write-Ok($text)   { Write-Host "    $text" -ForegroundColor Green }
function Write-Warn($text) { Write-Host "    $text" -ForegroundColor Yellow }


function Find-LRelease {
    if ($LReleasePath) {
        if (Test-Path $LReleasePath) { return $LReleasePath }
        throw "lrelease not found at the given path: $LReleasePath"
    }

    $onPath = Get-Command lrelease -ErrorAction SilentlyContinue
    if ($onPath) { return $onPath.Source }

    # QGIS ships the Qt tools inside the installation, but not on PATH.
    $roots = @("C:\Program Files\QGIS *", "C:\Program Files (x86)\QGIS *",
               "C:\OSGeo4W", "C:\OSGeo4W64")
    foreach ($pattern in $roots) {
        foreach ($dir in (Get-Item -Path $pattern -ErrorAction SilentlyContinue)) {
            foreach ($name in @("lrelease.exe", "lrelease-qt5.exe", "pyside6-lrelease.exe")) {
                $hit = Get-ChildItem -Path $dir.FullName -Filter $name `
                                     -Recurse -ErrorAction SilentlyContinue |
                       Select-Object -First 1
                if ($hit) { return $hit.FullName }
            }
        }
    }
    return $null
}


function Find-QtTool($exeNames) {
    foreach ($name in $exeNames) {
        $onPath = Get-Command $name -ErrorAction SilentlyContinue
        if ($onPath) { return $onPath.Source }
    }
    $roots = @("C:\Program Files\QGIS *", "C:\Program Files (x86)\QGIS *",
               "C:\OSGeo4W", "C:\OSGeo4W64")
    foreach ($pattern in $roots) {
        foreach ($dir in (Get-Item -Path $pattern -ErrorAction SilentlyContinue)) {
            foreach ($name in $exeNames) {
                $hit = Get-ChildItem -Path $dir.FullName -Filter $name `
                                     -Recurse -ErrorAction SilentlyContinue |
                       Select-Object -First 1
                if ($hit) { return $hit.FullName }
            }
        }
    }
    return $null
}


function Start-Linguist {
    $linguist = Find-QtTool @("linguist.exe")
    if (-not $linguist) {
        throw "linguist.exe was not found inside the QGIS installation either."
    }

    # Linguist fails with "libpng16.dll not found" when started outside the
    # QGIS environment: the DLLs live in the QGIS bin folder, which is not on
    # PATH. Putting them on PATH for this process is enough.
    $qtBin   = Split-Path $linguist -Parent               # ...\apps\qt5\bin
    $qgisBin = Join-Path (Split-Path (Split-Path (Split-Path $qtBin -Parent) -Parent) -Parent) "bin"
    $env:PATH = "$qgisBin;$qtBin;$env:PATH"

    $tsPaths = (Get-ChildItem -Path (Join-Path $Root "i18n") -Filter "*.ts").FullName
    Write-Ok "starting $linguist"
    Write-Host "    Use File > Release to produce the .qm file, then run build.ps1 again." -ForegroundColor Gray
    Start-Process -FilePath $linguist -ArgumentList $tsPaths
}


function Get-MetadataValue($key) {
    $file = Join-Path $Root "metadata.txt"
    foreach ($line in Get-Content $file -Encoding UTF8) {
        if ($line -match "^\s*$([regex]::Escape($key))\s*=\s*(.*)$") {
            return $Matches[1].Trim()
        }
    }
    return ""
}


# -- 1. translations -------------------------------------------------------

if ($Linguist) {
    Write-Step "Opening Qt Linguist"
    Start-Linguist
    return
}

Write-Step "Compiling translations"

$tsFiles = Get-ChildItem -Path (Join-Path $Root "i18n") -Filter "*.ts" `
                         -ErrorAction SilentlyContinue
if (-not $tsFiles) {
    Write-Warn "No .ts files found - the plugin will be English only."
} else {
    $lrelease = Find-LRelease

    if (-not $lrelease) {
        # Some QGIS installations ship linguist.exe but no lrelease.exe. That
        # is not fatal: a .qm released from Linguist earlier is just as good,
        # as long as it is not older than the .ts it came from.
        Write-Warn "lrelease.exe not found - checking for .qm files released from Linguist"
        $stale = @()
        foreach ($ts in $tsFiles) {
            $qm = [IO.Path]::ChangeExtension($ts.FullName, ".qm")
            if (-not (Test-Path $qm)) {
                $stale += "$($ts.Name): no .qm at all"
            } elseif ((Get-Item $qm).LastWriteTime -lt $ts.LastWriteTime) {
                $stale += "$($ts.Name): the .qm is older than the .ts"
            } else {
                Write-Ok "$([IO.Path]::GetFileName($qm)) is up to date"
            }
        }
        if ($stale.Count -gt 0) {
            foreach ($item in $stale) { Write-Warn $item }
            $advice = "Run '.\build.ps1 -Linguist', use File > Release, then build again."
            if ($Release) { throw "Translations are not up to date. $advice" }
            Write-Warn $advice
        }
        $tsFiles = @()          # skip the compile loop below
    } else {
        Write-Ok "using $lrelease"
    }

    foreach ($ts in $tsFiles) {
        & $lrelease $ts.FullName | Out-Null
        $qm = [IO.Path]::ChangeExtension($ts.FullName, ".qm")
        if (-not (Test-Path $qm)) {
            throw "lrelease produced no .qm for $($ts.Name)"
        }
        # An unfinished string is dropped by lrelease and shows up in English.
        $unfinished = ([regex]::Matches(
            (Get-Content $ts.FullName -Raw -Encoding UTF8),
            'type="unfinished"')).Count
        if ($unfinished -gt 0) {
            Write-Warn "$($ts.Name): $unfinished unfinished string(s) will NOT be translated"
        }
        Write-Ok "$($ts.Name) -> $([IO.Path]::GetFileName($qm))"
    }
}


# -- 2. checks -------------------------------------------------------------

Write-Step "Checking metadata"

$version = Get-MetadataValue "version"
if (-not $version) { throw "version is missing from metadata.txt" }
Write-Ok "version $version"

$problems = @()
if ($Release) {
    foreach ($key in @("repository", "tracker", "homepage", "email")) {
        $value = Get-MetadataValue $key
        if (-not $value -or $value -match "CHANGE_ME") {
            $problems += "metadata.txt: '$key' is empty - required by the QGIS plugin repository"
        }
    }
    if ((Get-MetadataValue "experimental") -eq "True") {
        $problems += "metadata.txt: experimental=True - set it to False for a public release"
    }
    if (-not (Test-Path (Join-Path $Root "LICENSE"))) {
        $problems += "LICENSE is missing - the plugin states GPL v2, so the text must be included"
    }
    if ($tsFiles -and -not (Get-ChildItem -Path (Join-Path $Root "i18n") -Filter "*.qm")) {
        $problems += "no .qm files - translations would silently fall back to English"
    }
    $icon = Get-MetadataValue "icon"
    if ($icon -and -not (Test-Path (Join-Path $Root $icon))) {
        $problems += "icon '$icon' does not exist"
    }
}

if ($problems.Count -gt 0) {
    Write-Host ""
    foreach ($p in $problems) { Write-Host "  ! $p" -ForegroundColor Red }
    throw "$($problems.Count) release check(s) failed"
}
if ($Release) { Write-Ok "release checks passed" }


# -- 3. staging ------------------------------------------------------------

Write-Step "Staging files"

if (Test-Path $BuildDir) { Remove-Item $BuildDir -Recurse -Force }
New-Item -ItemType Directory -Path $StageDir -Force | Out-Null

Copy-Item -Path (Join-Path $Root "*") -Destination $StageDir -Recurse -Force `
          -Exclude $Exclude

# Copy-Item -Exclude only filters the top level, so sweep the tree as well.
Get-ChildItem -Path $StageDir -Include "__pycache__", ".vscode" -Recurse -Force -Directory |
    Remove-Item -Recurse -Force -ErrorAction SilentlyContinue
Get-ChildItem -Path $StageDir -Include "*.pyc", "*.pyo" -Recurse -Force -File |
    Remove-Item -Force -ErrorAction SilentlyContinue
Remove-Item (Join-Path $StageDir "build.ps1") -Force -ErrorAction SilentlyContinue

$staged = (Get-ChildItem $StageDir -Recurse -File).Count
Write-Ok "$staged file(s)"


# -- 4. zip ----------------------------------------------------------------

Write-Step "Packaging"

$zip = Join-Path $BuildDir "$PluginName-$version.zip"
Compress-Archive -Path $StageDir -DestinationPath $zip -Force
Write-Ok $zip


# -- 5. deploy -------------------------------------------------------------

if ($Deploy) {
    Write-Step "Deploying to profile '$Profile'"

    $target = Join-Path $env:APPDATA "QGIS\QGIS3\profiles\$Profile\python\plugins\$PluginName"
    if (-not (Test-Path (Split-Path $target -Parent))) {
        throw "Plugin folder for profile '$Profile' not found: $(Split-Path $target -Parent)"
    }
    if (Test-Path $target) { Remove-Item $target -Recurse -Force }
    Copy-Item -Path $StageDir -Destination $target -Recurse -Force
    Write-Ok $target
    Write-Host ""
    Write-Host "    Reload with Plugin Reloader. Check the log panel for the" -ForegroundColor Gray
    Write-Host "    'Language:' line to confirm the translation was loaded." -ForegroundColor Gray
}

Write-Host ""
Write-Host "Done." -ForegroundColor Green
