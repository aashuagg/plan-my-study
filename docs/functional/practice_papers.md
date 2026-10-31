# Practice Papers

## Purpose

Parents can generate a practice paper for one or more saved topics within one subject, with additional
instructions describing the exercises they want. The student's grade and board
are read from the active profile to determine the education level and difficulty
context; the prompt does not assume a primary-school age group. This flow is independent of weekly planning and
does not record a study session or change SM-2 ratings or review dates.

## User Flow

1. Open **Practice Papers** in the sidebar.
2. Select a subject, then choose one or more of its saved topics in the Topics
   multiselect (up to 20). Topics from different subjects cannot be combined.
3. Optionally describe the desired practice (up to 3,000 characters), for example:
   "Use short fill-in-the-blank sentences with I/he/she and am/is/are."
4. Choose the total question count (1–20, default 10, with at least one question per
   selected topic), difficulty (Easy, Standard, or
   Challenging; default Standard), and time (5–90 minutes, default 30).
5. Click **Generate practice paper**. A spinner appears while the configured LLM runs.
6. Read the paper, with one mark per question and space to write answers. Review the
   separate **Answer key — for the parent** expander before using the paper.
7. Read the paper directly on screen, or download the student paper and answer key
   separately as PDFs. UTF-8 Markdown downloads are also available.

## Topic Selection

The list is a sorted, deduplicated union of `curriculum_items` (joined to the
student's newsletters) and `learning_history`, grouped by exact subject. It includes
manual diary entries, older topics, and mastered topics, so the parent can choose
any saved topic. Selecting a different subject refreshes the topic selector.
No automatic Grammar-to-English mapping is applied by this feature. Generating is
disabled until at least one topic is selected. The topic selection is held separately
for each subject; changing the selection hides any result for a different set of topics.

If there are no saved topics, the page directs the parent to Upload Newsletter or
Add Diary Entry. There is no free-text topic creation in this flow; additional
instructions refine the selected topic.

## Generation Rules

Difficulty is relative to the student's profile. Easy uses recognition/direct recall
with explicit scaffolding. Standard (medium) requires application in a sentence or
new context, error correction, or one-step reasoning, with fewer hints and a mix of
tasks. Merely naming a paper "Standard" or repeatedly telling the child which sign
to insert does not make it medium difficulty. Challenging increases independent
transfer/comparison while remaining within the student's grade and selected topics.

- Use the configured `AI_PROVIDER` and model settings already used for weekly plans.
- Preserve the selected subject and topic names in paper metadata; do not ask the model
  to relabel or select topics.
- Prompt for grade/board-appropriate questions, within the selected topic, and the
  exact requested total count of distinct questions, with an answer for each.
- Cover every selected topic with at least one question. Ask for an even spread
  unless the parent's instructions request a different balance. Each question must
  identify its topic using an exact selected name; reject unknown or missing topic
  labels and papers that omit a selected topic. Multi-topic previews, PDFs, and
  answer keys list all topics and identify the topic for each question.
- Ask for Hindi in Devanagari and Kannada in Kannada script; use English for other
  subjects unless parent instructions request a different language.
- Generate text-only exercises. For topics involving pictures, use textual clues
  rather than refer to images that do not exist.
- Each question is one mark; avoid subquestions. The answer key gives a correct or
  sample acceptable answer for each question.
- Validate structured output, nonempty fields, exact question count, and duplicate
  question text before showing a new result. Semantic accuracy and curriculum fit
  are prompted, not guaranteed by schema validation; parent review is expected.

## State, Failures, and Limits

The last successfully generated paper is held in Streamlit session state for the
active student. Reruns and downloads do not call the LLM again. The saved paper is
shown only when its subject and complete topic set match the selectors (selection
order does not matter). A new successful generation
replaces it; switching topics does not relabel an old result. Earlier single-topic
session results remain readable. A failed generation
shows a retry message and preserves the previous successful result, if any.

Papers are not persisted to PostgreSQL and are lost when the Streamlit session ends.
Download a paper to keep it. PDF exports use A4 pages, answer-writing lines, page
numbers, and embedded Noto fonts with HarfBuzz shaping for English, Hindi, and Kannada.
PDF bytes are generated in memory and cached by paper content; downloading does not
call the LLM. PDF failures leave the screen preview and Markdown downloads available.
No database migration is required. Install the dependencies in `requirements.txt`,
including ReportLab 4.4+ and `uharfbuzz` for text shaping. Fonts and their OFL license
are bundled under `backend/assets/fonts`; no font download is needed at runtime.
Pictures, saved-paper history, and automatic scoring are outside this implementation.

## Validation

Run `.venv/bin/python -m unittest discover -s tests -v`. The practice-paper tests use
mocked LLM responses, an isolated SQLite database, and Streamlit AppTest; they do not
call a paid model or modify the student's database.
