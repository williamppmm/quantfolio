param(
  [string]$BaseUrl = "http://127.0.0.1:8000",
  [string]$Ticker = "VOO",
  [string]$Start = "2025-01-01",
  [string]$End = "2025-09-10",
  [string]$Interval = "1d",
  [double]$Rf = 0.02,
  [double]$Mar = 0.0
)

$ErrorActionPreference = "Stop"

function Write-Title($text)    { Write-Host ""; Write-Host "=== $text ===" -ForegroundColor Cyan }
function Write-Pass($text)     { Write-Host "PASS " -ForegroundColor Green -NoNewline; Write-Host $text }
function Write-Fail($text)     { Write-Host "FAIL " -ForegroundColor Red   -NoNewline; Write-Host $text }
function Write-Info($text)     { Write-Host "INFO " -ForegroundColor Yellow -NoNewline; Write-Host $text }

function Test-HasKeys($obj, [string[]]$keys) {
  foreach ($k in $keys) {
    if (-not ($obj.PSObject.Properties.Name -contains $k)) { return $false }
  }
  return $true
}

function GET($path, $query=@{}) {
  $uri = if ($query.Count -gt 0) {
    $q = ($query.GetEnumerator() | ForEach-Object { "$($_.Key)=$($_.Value)" }) -join "&"
    "$BaseUrl$path`?$q"
  } else { "$BaseUrl$path" }
  Invoke-RestMethod -Uri $uri -Method GET
}

function POST($path, $query=@{}, $body=$null) {
  $uri = if ($query.Count -gt 0) {
    $q = ($query.GetEnumerator() | ForEach-Object { "$($_.Key)=$($_.Value)" }) -join "&"
    "$BaseUrl$path`?$q"
  } else { "$BaseUrl$path" }
  if ($null -ne $body) {
    Invoke-RestMethod -Uri $uri -Method POST -Body ($body | ConvertTo-Json) -ContentType "application/json"
  } else {
    Invoke-RestMethod -Uri $uri -Method POST
  }
}

try {
  Write-Title "Smoke test Portfolio Manager API"

  # 1) Health / Ready
  $h = GET "/health"
  if ($h.status -eq "ok") { Write-Pass "/health -> ok" } else { Write-Fail "/health" }

  $r = GET "/ready"
  if ($r.status -eq "ok") { Write-Pass "/ready -> ok" } else { Write-Fail "/ready" }

  # 2) Ingesta masiva (rango)
  Write-Info "Ingestando $Ticker $Start..$End ($Interval) ..."
  $ing = POST "/ingest/$Ticker" @{ start=$Start; end=$End; interval=$Interval }
  if (Test-HasKeys $ing @("ticker","start","end","ingested","upsert_effect")) {
    Write-Pass "/ingest/$Ticker -> ingested=$($ing.ingested), upsert=$($ing.upsert_effect)"
  } else { Write-Fail "/ingest/$Ticker (estructura desconocida)" }

  # 3) Lectura desde DB (rango)
  $dbRange = GET "/prices/$Ticker/db/range" @{ start=$Start; end=$End }
  if (Test-HasKeys $dbRange @("ticker","start","end","count","data") -and $dbRange.count -ge 1) {
    Write-Pass "/prices/$Ticker/db/range -> count=$($dbRange.count)"
  } else { Write-Fail "/prices/$Ticker/db/range" }

  # 4) Ultimo guardado en DB
  $dbLast = GET "/prices/$Ticker/db/last"
  if (Test-HasKeys $dbLast @("ticker","date","close")) {
    Write-Pass "/prices/$Ticker/db/last -> $($dbLast.date) close=$($dbLast.close)"
  } else { Write-Fail "/prices/$Ticker/db/last" }

  # 5) Ingesta incremental
  $latest = POST "/ingest/$Ticker/latest" @{ interval=$Interval }
  if (Test-HasKeys $latest @("ticker","start","end","ingested","upsert_effect")) {
    Write-Pass "/ingest/$Ticker/latest -> +$($latest.ingested) filas"
  } else { Write-Fail "/ingest/$Ticker/latest" }

  # 6) Metricas basicas
  $basic = GET "/metrics/$Ticker/basic" @{ start=$Start; end=$End; rf=$Rf }
  if (Test-HasKeys $basic @("ann_return","ann_volatility","sharpe","max_drawdown")) {
    Write-Pass "/metrics/$Ticker/basic -> sharpe=$($basic.sharpe)"
  } else { Write-Fail "/metrics/$Ticker/basic" }

  # 7) Metricas avanzadas
  $adv = GET "/metrics/$Ticker/advanced" @{ start=$Start; end=$End; rf=$Rf; mar=$Mar }
  if (Test-HasKeys $adv @("downside_volatility","sortino","calmar")) {
    Write-Pass "/metrics/$Ticker/advanced -> sortino=$($adv.sortino)"
  } else { Write-Fail "/metrics/$Ticker/advanced" }

  # 8) Senales tecnicas
  $sig = GET "/signals/$Ticker/tech" @{ start=$Start; end=$End; window=60; fast=20; slow=50; rsi_period=14 }
  if (Test-HasKeys $sig @("momentum","sma_fast","sma_slow","rsi")) {
    Write-Pass "/signals/$Ticker/tech -> momentum=$($sig.momentum)"
  } else { Write-Fail "/signals/$Ticker/tech" }

  Write-Title "Smoke test finalizado"
}
catch {
  Write-Fail $_.Exception.Message
  if ($_.ErrorDetails) { Write-Host $_.ErrorDetails.Message }
  exit 1
}