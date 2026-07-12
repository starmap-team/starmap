---
phase: 11-feature-loop-closure
plan: 11-09
wave: 3
requirements: [LOOP-10, LOOP-12]
decision_refs: [D-17, D-20]
status: complete
---

# 11-09 Summary: 学习进度技能同步 + Evolution Changelog 参数修复

## Accomplishments

1. **userStore.addParsedSkill()** — Added `addParsedSkill(skill: string)` action in `user.ts` that appends skill to `parsedSkills` array (with duplicate prevention).
2. **handleUpdateStatus mastered sync** — Modified `useLearningActions.ts` `handleUpdateStatus()` to call `userStore.addParsedSkill(skill)` when status becomes 'mastered', plus success message "技能已掌握！可前往匹配诊断查看提升效果".
3. **Evolution changelog parameter rename** — Changed `get_changelog()` parameter from `position` to `identifier` in `evolution.py`, supporting both skill and position queries. Frontend `fetchChangelog()` parameter renamed from `skillName` to `identifier`. DEV-guard on console.error.

## User-facing Changes

- Mastered skills in learning plans are automatically added to user's parsed skills for re-matching
- Success message encourages users to re-run match diagnosis
- Evolution changelog works for both skill names and position names

## Files Modified

- `frontend/src/stores/user.ts` — Added `addParsedSkill()` action
- `frontend/src/composables/useLearningActions.ts` — Import `useUserStore`, call `addParsedSkill` on mastered
- `backend/app/api/v1/evolution.py` — Parameter `position` → `identifier`
- `frontend/src/composables/useEvolutionActions.ts` — Parameter `skillName` → `identifier`, DEV guard on console.error

## UAT Verification

- ✅ Code verified: `handleUpdateStatus()` calls `userStore.addParsedSkill(skill)` when `status === 'mastered'`
- ✅ `addParsedSkill()` prevents duplicates with `includes()` check
- ✅ GET /evolution/changelog/Docker → HTTP 200
- ✅ GET /evolution/changelog/DevOps工程师 → HTTP 200
- ✅ Backend parameter name is `identifier: str` (evolution.py:213)
