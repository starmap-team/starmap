@echo off
cd /d E:\java1\starmap
echo === GIT STATUS ===
if exist .git (
    git status --short
    echo === LOG ===
    git log --oneline -5
    echo === BRANCH ===
    git branch -a
) else (
    echo NOT A GIT REPO - Initializing...
    git init
    git checkout -b r3/yangbowen/m1
    git add --all
)
