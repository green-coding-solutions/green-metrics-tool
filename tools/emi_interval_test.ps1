# EMI Driver Interval Stress Test
# Tests metric-provider-binary.exe at different sampling intervals
# Runs each interval 10 times, collects stats, exports to CSV

$binary = ".\metric_providers\cpu\energy\rapl\emi\component\metric-provider-binary.exe"
$intervals = @(99, 80, 65, 50, 20, 10, 5, 1)
$runsPerInterval = 10
$testDurationMs = 5000   # 5 seconds per run
$outputCsv = ".\tools\emi_interval_results.csv"

$results = @()

foreach ($interval in $intervals) {
    Write-Host "=== Interval: $interval ms ===" -ForegroundColor Cyan

    for ($run = 1; $run -le $runsPerInterval; $run++) {
        Write-Host "  Run $run / $runsPerInterval ..." -NoNewline

        $maxSamples = [math]::Ceiling($testDurationMs / $interval) + 5

        $startTime = Get-Date
        $output = & $binary -i $interval | Select-Object -First $maxSamples
        $elapsed = ((Get-Date) - $startTime).TotalMilliseconds

        if (-not $output -or $output.Count -eq 0) {
            Write-Host " ERROR: no output" -ForegroundColor Red
            $results += [PSCustomObject]@{
                interval_ms     = $interval
                run             = $run
                samples         = 0
                unique_values   = 0
                repeat_ratio    = 1.0
                zero_count      = 0
                min_value       = $null
                max_value       = $null
                mean_value      = $null
                elapsed_ms      = [math]::Round($elapsed, 1)
                status          = "ERROR_NO_OUTPUT"
            }
            continue
        }

        $values = @()
        foreach ($line in $output) {
            $parts = $line -split '\s+'
            if ($parts.Count -ge 2) {
                $v = $null
                if ([long]::TryParse($parts[1], [ref]$v)) {
                    $values += $v
                }
            }
        }

        $sampleCount  = $values.Count
        $uniqueCount  = ($values | Sort-Object -Unique).Count
        $zeroCount    = ($values | Where-Object { $_ -eq 0 }).Count
        $repeatRatio  = if ($sampleCount -gt 0) { [math]::Round(1 - ($uniqueCount / $sampleCount), 3) } else { 1.0 }
        $minVal       = if ($values.Count -gt 0) { ($values | Measure-Object -Minimum).Minimum } else { $null }
        $maxVal       = if ($values.Count -gt 0) { ($values | Measure-Object -Maximum).Maximum } else { $null }
        $meanVal      = if ($values.Count -gt 0) { [math]::Round(($values | Measure-Object -Average).Average, 1) } else { $null }

        $status = "OK"
        if ($zeroCount -gt 0)               { $status = "ZEROS_FOUND" }
        if ($repeatRatio -gt 0.3)           { $status = "HIGH_REPEAT" }
        if ($repeatRatio -gt 0.7)           { $status = "DRIVER_SATURATED" }
        if ($sampleCount -lt $maxSamples * 0.5) { $status = "LOW_SAMPLE_COUNT" }

        Write-Host " samples=$sampleCount unique=$uniqueCount repeat=$repeatRatio status=$status" -ForegroundColor $(if ($status -eq "OK") { "Green" } else { "Yellow" })

        $results += [PSCustomObject]@{
            interval_ms     = $interval
            run             = $run
            samples         = $sampleCount
            unique_values   = $uniqueCount
            repeat_ratio    = $repeatRatio
            zero_count      = $zeroCount
            min_value       = $minVal
            max_value       = $maxVal
            mean_value      = $meanVal
            elapsed_ms      = [math]::Round($elapsed, 1)
            status          = $status
        }
    }
    Write-Host ""
}

# Export to CSV
$results | Export-Csv -Path $outputCsv -NoTypeInformation -Encoding UTF8
Write-Host "Results saved to: $outputCsv" -ForegroundColor Green

# Summary per interval
Write-Host "`n=== SUMMARY ===" -ForegroundColor Cyan
$results | Group-Object interval_ms | ForEach-Object {
    $g = $_.Group
    $avgRepeat  = [math]::Round(($g.repeat_ratio | Measure-Object -Average).Average, 3)
    $avgSamples = [math]::Round(($g.samples      | Measure-Object -Average).Average, 1)
    $statuses   = ($g.status | Sort-Object -Unique) -join ", "
    Write-Host ("  {0,4} ms | avg_samples={1,6} | avg_repeat={2,5} | statuses={3}" -f $_.Name, $avgSamples, $avgRepeat, $statuses)
}
