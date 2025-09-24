param(
  [string]$Base = "http://127.0.0.1:8000",
  [string]$Ticker = "VOO",
  [string]$Interval = "1d"
)

Write-Host "=== Smoke Latest ===" -ForegroundColor Cyan

try {
  $last = Invoke-RestMethod "$Base/prices/$Ticker/db/last"
  if (-not $last -or -not $last.ticker) {
    Write-Host "No stored prices for $Ticker. Ingest a range first." -ForegroundColor Yellow
    exit 1
  }

  Write-Host "Last stored bar: $($last.date) close=$($last.close)" -ForegroundColor Gray
  $res = Invoke-RestMethod -Method Post "$Base/ingest/$Ticker/latest?interval=$Interval"
  Write-Host "Status: $($res.status)" -ForegroundColor Cyan
  Write-Host "Ingested: $($res.ingested) Upsert: $($res.upsert_effect)" -ForegroundColor Green
}
catch {
  Write-Host "Error running smoke latest: $($_.Exception.Message)" -ForegroundColor Red
  if ($_.ErrorDetails) {
    Write-Host $_.ErrorDetails.Message
  }
  exit 1
}
