# CLAUDE.md

## What This Project Is
A web-based study planner for a parent to manage their child's daily study schedule using spaced repetition (SM-2). Generates balanced weekly plans mixing new school topics with timely revision so no subject gets neglected.

**Student:** Shubhi, Class 1, CBSE, Bangalore
**Study target:** 30 min/day, 6 days/week, max 2 subjects per session

## Subjects
- **UKG (2024-25):** LITERACY, NUMERACY, HINDI, KANNADA, GENERAL AWARENESS
- **Class 1 (2025-26):** ENGLISH, MATHS, HINDI, KANNADA, GRAMMAR, GENERAL AWARENESS, COMPUTER

Newsletter subject variants must be normalized on ingest (e.g. `Mathematics` → `MATHS`, `EVS` → `GENERAL AWARENESS`, `Computer Science` → `COMPUTER`).

## Plan Generation Rules — Always Follow These
- Max 2 topics per day, no exceptions
- Only use topics from provided curriculum — never invent
- Copy topic names exactly as they appear in the data
- No catch-up day — last day follows same rules as every other day
- Each topic must belong to the subject scheduled for that day
- Review time is a floor (not a fixed ratio) that grows with backlog size; due-topic
  prioritization is neglect-first, not just raw next_review date.
  See `docs/functional/plan_generation.md` for the current rule and rationale.
- Topics a parent manually marks "graduated" (mastered) are excluded from review
  scheduling entirely, regardless of SM-2 state. See `docs/functional/progress_tracking.md`.

## Known Issues
- No profile edit UI yet

See `docs/functional/` for the maintained functional specs (plan generation, newsletter
ingestion, progress tracking, profile) — that's the source of truth for flows, data
formats, and resolved/open issues, kept more current than this file.