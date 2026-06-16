$env:CI="true"
$env:GIT_TERMINAL_PROMPT="0"
$env:GCM_INTERACTIVE="never"
$env:GIT_EDITOR=":"
$env:EDITOR=":"
$env:GIT_PAGER="cat"
$env:PAGER="cat"

Set-Location "E:\java1\starmap"

git init
git checkout -b r3/yangbowen/m1
git add --all
git -c user.name="杨博文" -c user.email="yang.bowen@starmap.com" commit -m "M1 契约交付 - 杨博文 2026-06-16"

Write-Output "=== STATUS ==="
git status --short
Write-Output "=== LOG ==="
git log --oneline -3
