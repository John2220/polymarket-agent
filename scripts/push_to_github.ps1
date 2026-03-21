#Requires -Version 5.1
<#
  Creates a public GitHub repo (API) and pushes branch main.
  Prerequisite: local git repo with commit.

  Usage:
    $env:GITHUB_TOKEN = "ghp_xxxxxxxx"   # PAT scope: repo
    $env:GITHUB_OWNER = "your-username"  # optional; default from GET /user
    .\scripts\push_to_github.ps1 -RepoName polymarket-agent

  Do not commit the token.
#>
param(
    [string]$RepoName = "polymarket-agent",
    [string]$RemoteName = "origin"
)

$ErrorActionPreference = "Stop"

$token = $env:GITHUB_TOKEN
if (-not $token) {
    Write-Error "Set environment variable GITHUB_TOKEN (GitHub Settings - Developer settings - Personal access tokens)."
}

$gitExe = $null
$cmd = Get-Command git -ErrorAction SilentlyContinue
if ($cmd) { $gitExe = $cmd.Source }
if (-not $gitExe) {
    $mingit = Join-Path $env:TEMP "MinGit\cmd\git.exe"
    if (Test-Path $mingit) { $gitExe = $mingit }
}
if (-not $gitExe) {
    Write-Error "git not found. Install Git for Windows or MinGit at %TEMP%\MinGit."
}

$headers = @{
    Authorization = "Bearer $token"
    "User-Agent"    = "polymarket-agent-push-script"
    Accept          = "application/vnd.github+json"
}

$user = $env:GITHUB_OWNER
if (-not $user) {
    $me = Invoke-RestMethod -Uri "https://api.github.com/user" -Headers $headers -Method Get
    $user = $me.login
}

$body = @{ name = $RepoName; private = $false } | ConvertTo-Json
try {
    Invoke-RestMethod -Uri "https://api.github.com/user/repos" -Headers $headers -Method Post -Body $body -ContentType "application/json" | Out-Null
    Write-Host "Repository created: https://github.com/$user/$RepoName"
} catch {
    if ($_.Exception.Response.StatusCode -eq 422) {
        Write-Host "Repository may already exist (422), continuing push..."
    } else {
        throw
    }
}

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
Set-Location $repoRoot

$remoteUrl = "https://${token}@github.com/${user}/${RepoName}.git"
$existing = & $gitExe remote 2>$null
if ($existing -match $RemoteName) {
    & $gitExe remote remove $RemoteName
}
& $gitExe remote add $RemoteName $remoteUrl
& $gitExe push -u $RemoteName main

$clean = "https://github.com/${user}/${RepoName}.git"
Write-Host "Done. To drop token from remote URL: git remote set-url $RemoteName $clean"
