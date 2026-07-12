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

## Known Issues
- No profile edit UI yet