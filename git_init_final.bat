@echo off
cd /d E:\java1\starmap
git init
git checkout -b r3/yangbowen/m1
git add --all
git -c user.name="yangbowen" -c user.email="yang.bowen@starmap.com" commit -m "M1 contract delivery - yangbowen 2026-06-16"
echo === STATUS ===
git status --short
echo === LOG ===
git log --oneline -3
