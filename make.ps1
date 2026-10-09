# Équivalent PowerShell du Makefile : .\make.ps1 <cible>
param([string]$Target = "help")

$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
Set-Location $PSScriptRoot

$port = "8080"
if (Test-Path .env) {
    $line = Select-String -Path .env -Pattern '^KESTRA_PORT=(\d+)' | Select-Object -First 1
    if ($line) { $port = $line.Matches[0].Groups[1].Value }
}

switch ($Target) {
    "help" {
        @"
  .\make.ps1 up      Construit l'image si besoin et démarre Kestra en arrière-plan
  .\make.ps1 down    Arrête Kestra (les flows et exécutions sont conservés)
  .\make.ps1 logs    Suit les logs Kestra (Ctrl+C pour sortir)
  .\make.ps1 ps      État du conteneur (attendre "healthy")
  .\make.ps1 ui      Affiche l'URL de l'UI Kestra
  .\make.ps1 shell   Ouvre un shell dans le conteneur Kestra
  .\make.ps1 data    Télécharge les 3 .xlsx OC dans data/raw/
  .\make.ps1 explore Profil des 3 fichiers sources (lecture seule)
  .\make.ps1 check   Rejoue la chaîne dans DuckDB et lance les tests
  .\make.ps1 duckdb  Ouvre data/warehouse.duckdb dans le CLI DuckDB, en lecture seule (.quit pour sortir)
  .\make.ps1 clean   DESTRUCTIF : arrête Kestra et supprime ses volumes
"@
    }
    "up" {
        docker compose up -d --build
        Write-Host "Kestra démarre (~1-2 min). Suivre : .\make.ps1 logs / .\make.ps1 ps. UI : http://localhost:$port"
    }
    "down"  { docker compose down }
    "logs"  { docker compose logs -f kestra }
    "ps"    { docker compose ps }
    "ui"    { Write-Host "http://localhost:$port" }
    "shell" { docker compose exec kestra bash }
    "data"  { python scripts/download_data.py }
    "explore" { docker compose exec kestra python /bottleneck/scripts/explore.py; exit $LASTEXITCODE }
    "check"   { docker compose exec kestra python /bottleneck/scripts/run_local.py; exit $LASTEXITCODE }
    "duckdb"  { docker compose exec kestra duckdb -readonly -box /bottleneck/data/warehouse.duckdb }
    "clean" {
        $ans = Read-Host "Supprimer les volumes Kestra (flows + historique d'exécutions) ? [y/N]"
        if ($ans -eq "y") { docker compose down -v } else { Write-Host "Annulé." }
    }
    default { Write-Error "Cible inconnue : $Target (voir .\make.ps1 help)" }
}
