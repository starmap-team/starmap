---
slug: flow03-proficiency
created: 2026-07-16
status: in-progress
---

# FLOW-03: 简历技能 proficiency 丢失修复

## Problem
`userStore.parsedSkills` is `ref<string[]>` — stores only skill names, discarding proficiency data.
Backend `/resume/upload` returns `{skill, category, proficiency}` per skill via `_map_skill_item()`.
Frontend `resume.ts` already has `ParsedSkill {skill, category, proficiency}` interface.
But `user.ts` flattens to `string[]` in `setResume()`, losing proficiency.

## Plan

### Task 1: user.ts — structured parsedSkills
- Import `ParsedSkill` from `resume.ts` (or define locally to avoid circular dep)
- Change `parsedSkills: ref<string[]>` → `ref<ParsedSkill[]>`
- Update `setResume(name, skills: ParsedSkill[])` signature
- Update `addParsedSkill(skill: string, proficiency?: string)` — accept optional proficiency
- Update `clearResume()` — reset to `[]`

### Task 2: MatchDiagnosis.vue — adapt consumers
- Line 69: `setResume(file.name, resumeStore.result.required_skills)` — pass ParsedSkill[] directly
- Line 125: `userStore.parsedSkills = [...manualSkills.value]` — wrap strings as `{skill, proficiency: '熟悉'}`
- Line 148: Remove synthetic `.map(s => ({skill: s, proficiency: '熟悉'}))` — use parsedSkills directly
- Line 174: `skillNames = userStore.parsedSkills.map(s => s.skill)` — extract names for match API

### Task 3: LearningCenter.vue — adapt skillNames extraction
- Line 64: `skillNames = userStore.parsedSkills` → `userStore.parsedSkills.map(s => s.skill)`

### Task 4: Type-check + commit
- `vue-tsc --noEmit` passes
- Commit with descriptive message
- Update TASK_CHECKLIST.md

## Key Design Decisions
- ParsedSkill defined in `resume.ts` (already exists), imported by `user.ts`
- Default proficiency for manual skills: `'熟悉'` (intermediate)
- `addParsedSkill` accepts optional proficiency param, defaults to `'熟悉'`
- match API still receives `string[]` of skill names (backend handles proficiency via PersonSkill)
