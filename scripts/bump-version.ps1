#!/usr/bin/env pwsh
#Requires -Version 7.5

<#
.SYNOPSIS
    Bump Awaaz version numbers everywhere before release.

.DESCRIPTION
    Updates the version string in:
      - pyproject.toml
      - frontend/package.json
      - src/awaaz/main.py

    Optionally commits the change and creates a Git tag.

.PARAMETER Version
    The new version number, e.g. "1.1.0" (without the leading 'v').

.PARAMETER Commit
    Commit the version bump after updating the files.

.PARAMETER Tag
    Create an annotated Git tag (v<Version>) and push it to origin.
    Implies -Commit.

.PARAMETER Push
    Push the commit and/or tag to origin. Requires -Commit or -Tag.

.EXAMPLE
    .\scripts\bump-version.ps1 -Version 1.1.0

    Updates version strings in all three files. Does not commit or push.

.EXAMPLE
    .\scripts\bump-version.ps1 -Version 1.1.0 -Commit -Tag -Push

    Updates files, commits, tags as v1.1.0, and pushes everything to origin.
#>

[CmdletBinding(SupportsShouldProcess)]
param (
    [Parameter(Mandatory)]
    [ValidatePattern('^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)(?:-[\da-z-]+(?:\.[\da-z-]+)*)?$')]
    [string]$Version,

    [switch]$Commit,
    [switch]$Tag,
    [switch]$Push
)

$ErrorActionPreference = 'Stop'

if ($Tag) {
    $Commit = $true
}

$repoRoot = Split-Path -Parent $PSScriptRoot
$files = @(
    [PSCustomObject]@{
        Path = Join-Path $repoRoot 'pyproject.toml'
        Pattern = '(?m)^version = "[^"]+"'
        Replacement = "version = `"$Version`""
    },
    [PSCustomObject]@{
        Path = Join-Path $repoRoot 'frontend/package.json'
        Pattern = '"version": "[^"]+"'
        Replacement = '"version": "{0}"' -f $Version
    },
    [PSCustomObject]@{
        Path = Join-Path $repoRoot 'src/awaaz/main.py'
        Pattern = 'version="[^"]+"'
        Replacement = 'version="{0}"' -f $Version
    }
)

foreach ($item in $files) {
    if (-not (Test-Path $item.Path)) {
        throw "Required file not found: $($item.Path)"
    }

    $content = Get-Content -Raw $item.Path
    if ($content -notmatch $item.Pattern) {
        throw "Could not find version pattern in $($item.Path)"
    }

    $newContent = $content -replace $item.Pattern, $item.Replacement
    if ($content -ceq $newContent) {
        Write-Host "No change needed: $($item.Path)" -ForegroundColor DarkGray
        continue
    }

    if ($PSCmdlet.ShouldProcess($item.Path, 'Update version')) {
        Set-Content -Path $item.Path -Value $newContent -NoNewline -Encoding utf8
        Write-Host "Updated version in $($item.Path)" -ForegroundColor Green
    }
}

if ($Commit) {
    git -C $repoRoot add -A
    git -C $repoRoot commit -m "chore: bump version to $Version" ?? 0

    if ($LASTEXITCODE -ne 0) {
        throw "git commit failed"
    }
    Write-Host "Committed version bump" -ForegroundColor Green
}

if ($Push) {
    if (-not $Commit) {
        throw "-Push requires -Commit or -Tag"
    }

    git -C $repoRoot push origin main
    Write-Host "Pushed commit to origin/main" -ForegroundColor Green
}

if ($Tag) {
    $tagName = "v$Version"
    git -C $repoRoot tag -a $tagName -m "Release $tagName"
    Write-Host "Created tag $tagName" -ForegroundColor Green

    if ($Push) {
        git -C $repoRoot push origin $tagName
        Write-Host "Pushed tag $tagName to origin" -ForegroundColor Green
    }
}

Write-Host "Done. New version: $Version" -ForegroundColor Cyan
