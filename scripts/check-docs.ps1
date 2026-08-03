[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
$root = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..')).Path
$issues = [System.Collections.Generic.List[string]]::new()
$strictUtf8 = [System.Text.UTF8Encoding]::new($false, $true)

$rg = Get-Command rg -ErrorAction SilentlyContinue
if ($rg) {
    $relativeFiles = & $rg.Source --files --hidden -g '*.md' -g '!node_modules/**' -g '!backend/.venv-new/**' -g '!frontend/test-results/**' -g '!.git/**' $root
    $markdownFiles = foreach ($relative in $relativeFiles) {
        $candidate = $relative
        if (-not [System.IO.Path]::IsPathRooted($candidate)) {
            $candidate = Join-Path $root $candidate
        }
        Get-Item -LiteralPath $candidate
    }
} else {
    $markdownFiles = Get-ChildItem -LiteralPath $root -Recurse -File -Filter '*.md' | Where-Object {
        $_.FullName -notmatch '[\\/](\.git|node_modules|\.venv-new|test-results)([\\/]|$)'
    }
}

foreach ($file in $markdownFiles) {
    try {
        [void]$strictUtf8.GetString([System.IO.File]::ReadAllBytes($file.FullName))
    } catch {
        $issues.Add("Non-UTF-8 Markdown: $($file.FullName.Substring($root.Length + 1))")
    }
}

$allowedRootDocs = @('README.md', 'AGENTS.md', 'CLAUDE.md')
Get-ChildItem -LiteralPath $root -File -Filter '*.md' | Where-Object {
    $_.Name -notin $allowedRootDocs
} | ForEach-Object {
    $issues.Add("Root Markdown must be classified under docs/: $($_.Name)")
}

if (Test-Path -LiteralPath (Join-Path $root 'doc')) {
    $issues.Add('Legacy doc/ directory exists; use docs/ categories.')
}

$reportName = '(?i)(REPORT|报告|修复计划|审计)'
foreach ($file in $markdownFiles) {
    $relative = $file.FullName.Substring($root.Length + 1).Replace('\', '/')
    if ($relative -notlike 'docs/archive/*' -and $file.Name -match $reportName) {
        $issues.Add("Snapshot/report is outside docs/archive/: $relative")
    }
}

$excludedLivePrefixes = @(
    'docs/archive/',
    '.planning/',
    '.claude/',
    '.workbuddy/'
)
$staleReferences = @(
    'docs/standards/99-appendix/',
    'docs/deployment-guide.md',
    'docs/dual-database-architecture.md',
    'docs/pipeline_deep_analysis.md',
    'docs/fix_plan_p0_2026-07-20.md',
    'docs/星图-项目设计文档v2.0.md',
    'starmap-contracts/CONTRACT_AUDIT.md',
    'crawler/scripts/pr_description.md',
    'STATE.md.v4-active-sprint.md',
    'docs/CODE_INDEX.md'
)

$linkPattern = [regex]'!?(?:\[[^\]]*\])\((?<target>[^)]+)\)'
foreach ($file in $markdownFiles) {
    $relative = $file.FullName.Substring($root.Length + 1).Replace('\', '/')
    $isExcluded = $false
    foreach ($prefix in $excludedLivePrefixes) {
        if ($relative.StartsWith($prefix, [System.StringComparison]::OrdinalIgnoreCase)) {
            $isExcluded = $true
            break
        }
    }
    if ($isExcluded) { continue }

    $content = [System.IO.File]::ReadAllText($file.FullName, [System.Text.Encoding]::UTF8)
    foreach ($stale in $staleReferences) {
        if ($content.Contains($stale)) {
            $issues.Add("Stale reference '$stale' in $relative")
        }
    }

    foreach ($match in $linkPattern.Matches($content)) {
        $target = $match.Groups['target'].Value.Trim()
        if ($target.StartsWith('<') -and $target.EndsWith('>')) {
            $target = $target.Substring(1, $target.Length - 2)
        }
        if ($target -match '^(?i:https?://|mailto:|data:|javascript:|#)') { continue }

        $pathOnly = ($target -split '#', 2)[0]
        $pathOnly = ($pathOnly -split '\?', 2)[0]
        if ([string]::IsNullOrWhiteSpace($pathOnly)) { continue }
        try { $pathOnly = [System.Uri]::UnescapeDataString($pathOnly) } catch { }

        $candidate = [System.IO.Path]::GetFullPath((Join-Path $file.DirectoryName $pathOnly))
        if (-not $candidate.StartsWith($root, [System.StringComparison]::OrdinalIgnoreCase)) {
            $issues.Add("Link escapes repository in ${relative}: $target")
            continue
        }
        if (-not (Test-Path -LiteralPath $candidate)) {
            $issues.Add("Broken link in ${relative}: $target")
        }
    }
}

if ($issues.Count -gt 0) {
    Write-Host "Documentation checks failed ($($issues.Count)):" -ForegroundColor Red
    $issues | Sort-Object -Unique | ForEach-Object { Write-Host " - $_" }
    exit 1
}

Write-Host "Documentation checks passed for $($markdownFiles.Count) Markdown files." -ForegroundColor Green