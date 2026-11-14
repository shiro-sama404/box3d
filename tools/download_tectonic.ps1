$ErrorActionPreference = 'Stop'
$dir = "tools\tectonic"
if (-not (Test-Path $dir)) {
    New-Item -ItemType Directory -Path $dir -Force | Out-Null
}

$url = "https://github.com/tectonic-typesetting/tectonic/releases/download/tectonic%400.17.0/tectonic-0.17.0-x86_64-pc-windows-msvc.zip"
$zipPath = Join-Path $dir "tectonic_msvc.zip"

Write-Host "Baixando Tectonic MSVC..."
Invoke-WebRequest -Uri $url -OutFile $zipPath

Write-Host "Extraindo..."
Expand-Archive -Path $zipPath -DestinationPath $dir -Force
Remove-Item $zipPath -Force

Write-Host "Pronto:"
Get-ChildItem $dir
