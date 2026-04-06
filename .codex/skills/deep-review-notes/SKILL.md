---
name: deep-review-notes
description: Deep review and repair of technical Markdown notes or note series using the repository's live styleguide, fact-checking, and structural cleanup. Use when Codex needs to inspect a folder of notes, reason about prerequisites, motivation, narrative flow, reader understanding, factual accuracy, and surrounding links, then edit the notes to improve understanding and retention rather than only producing a checklist.
---

# Deep Review Notes

## Overview

Use this skill to deeply review and improve a folder or series of technical notes. Optimize for understanding, retention, and durable mental models built from connections between facts, not for superficial compliance or template matching.

Read the live `styleguide.md`, `structure-guide.md`, and, when present, repository guidance such as `CLAUDE.md` or `AGENTS.md`. Do not duplicate those rules from memory. Treat them as the source of truth for the current run.

## Core Principles

- Treat notes as teaching artifacts, not as benchmark samples. Do not treat the text as test data, a fill-in-the-blank template, or a checklist target.
- Optimize for retention through connected ideas. A fact that is technically correct but disconnected, unmotivated, or unsupported by the reader model is still a problem.
- Use `styleguide.md` as a reasoning system. Read the relevant sections to understand the intent behind the rule, then judge the note against that intent. Use mini-checklists only at the end as a guardrail.
- Let reviewer agents create pressure from different angles, but keep judgment and editing in the main agent. Do not outsource the final editorial pass.
- Fix root causes before symptoms. When five local issues come from one bad section design, rewrite the section instead of polishing the symptoms.
- Avoid formulaic rewrites. The repaired note must read like a natural standalone explanation, not like a text that was merely made to pass review.
- Treat the repository as a layered curriculum, not as isolated folders. Understand where the current material sits in the broader teaching graph and how it depends on lower layers or feeds higher ones.
- Treat deletion as expensive. If a passage feels problematic, first ask whether it is wrong, misplaced, too detailed for this layer, or simply needs to move to another file. Do not delete useful information just because the current section cannot carry it well.
- Treat `Предпосылки` and integrated links as complementary tools. `Предпосылки` define what the reader may know; local links and anchors disambiguate what the current sentence is pointing at, especially when wording differs from the prerequisite file.

## Workflow

### 1. Build Context

- Read all target `.md` files in the requested folder.
- Determine reading order from `index.md` or numeric prefixes.
- Extract `Предпосылки` from each note and identify prerequisite files that materially affect reader knowledge.
- Read repository guidance that governs note-writing, especially `styleguide.md`, `structure-guide.md`, and local repo instructions.
- Capture a pre-edit baseline for every file you may touch. Prefer repository history and `git diff` when available; otherwise keep the original text in working memory or notes so you can compare before and after.
- Build a local layer map before editing. Use `CLAUDE.md`, directory structure, `index.md`, `Предпосылки`, and neighboring notes to understand where the material belongs in the curriculum graph.

### 2. Form the Review Surface

- Decide whether the target is a single note, a short series, or a folder-level cluster. Adjust scope accordingly.
- Identify nearby files that may require cascading fixes: local `index.md`, previous and next notes, cross-linked notes, and parent-level overview files.
- Separate stable conceptual claims from claims that need source verification.
- Ask early whether the problem is actually a placement problem: wrong layer, wrong file, wrong sequence point, or missing neighboring note.

### 3. Run Parallel Reviewer Lenses

If subagents are available and the task benefits from parallel pressure, spawn independent reviewers. The point of parallel review is not to assemble a committee or average opinions. The point is to put the text under several different kinds of pressure that correspond to how explanatory notes succeed or fail.

Use the prompts in [references/reviewer-lenses.md](references/reviewer-lenses.md) and adapt them to the exact files. Prefer distinct lenses rather than duplicate reviewers. Each reviewer should own one deep question about the note, not a generic mandate to "check quality".

Before spawning reviewers:
- pass exact file paths, order, relevant prerequisite files, and nearby files when the lens needs them;
- tell the reviewer whether the target is a single note, a short sequence, or a folder-level cluster;
- keep the prompt narrow enough that the model can think, not just enumerate;
- do not leak your diagnosis, intended rewrite, or preferred conclusion.

A strong reviewer prompt does four things:
- states the lens's real goal in terms of reader understanding or note placement;
- tells the reviewer what not to optimize for;
- asks for a small number of high-leverage findings instead of a long checklist dump;
- asks for root-cause thinking and repair direction, not only local complaints.

A strong reviewer report usually contains:
- a short thesis about what the note seems to be trying to teach and where it succeeds or fails;
- as many findings as are actually needed to explain the problem shape; sometimes one root cause is enough, sometimes several distinct issues matter;
- for each finding: symptom, why it harms understanding, likely root cause, and preferred class of fix;
- one highest-leverage rewrite direction or restructuring move.

Weak reviewer reports sound like restated checklist bullets, line-by-line proofreading, or generic "needs more motivation / more detail / clearer wording" comments that do not explain what cognitive failure they observed.

Recommended lenses:
- `prerequisites`
- `entry`
- `narrative`
- `effect`
- `layers`
- `factcheck`
- `reader`

Recommended model split:
- `reader` -> `gpt-5.3-codex-spark` with `low` reasoning effort by default. This lens should be rigid, repetitive, and narrow. Give it a fixed ontology and a fixed method. Optimize for speed and friction detection, not sophistication. If it starts drifting from the 5-line method, raise it to `medium`.
- `prerequisites` -> `gpt-5.4-mini` with `high` reasoning effort. This lens needs contract judgment, not brute-force sophistication. Prompt it around one deep question: can the declared reader actually follow the note?
- `entry` -> `gpt-5.4-mini` with `high` reasoning effort. This lens needs felt motivation, scenario recognition, and restraint against generic hooks or "why it matters" filler.
- `narrative` -> `gpt-5.4-mini` with `high` reasoning effort. This lens should track causal flow and catch the moment the note turns reference-like or documentation-shaped.
- `effect` -> `gpt-5.4-mini` with `high` reasoning effort by default; upgrade to `gpt-5.4` with `medium` or `high` reasoning when the topic is especially subtle or mechanism-heavy. This lens needs to judge whether the note leaves the reader able to explain, choose, and reason.
- `layers` -> `gpt-5.4-mini` with `high` reasoning effort. This lens needs graph and boundary awareness across nearby notes and should think in terms of move/split/link, not deletion.
- `factcheck` -> `gpt-5.4` with `medium` or `high` reasoning effort. Use the strongest reviewer here because factual precision, version scoping, source interpretation, and safe simplification judgment matter more than speed.

Prompt freedom should match the model:
- for `gpt-5.3-codex-spark`, use tight process constraints and a fixed output shape;
- for `gpt-5.4-mini`, ask one interpretive question and ask for argued findings only where they materially help explain the note's failure or success;
- for `gpt-5.4`, allow broader search and synthesis but require evidence and source discipline.

Keep final editorial judgment in the main agent. If model availability changes, preserve the intent of the split: fastest model for `reader`, strongest model for `factcheck`, and a careful mid-to-strong model for the interpretive reviewers.

Do not use any fixed conflict-resolution order between reviewer lenses:
- treat apparent disagreement between reviewers as diagnostic pressure, not as a voting problem;
- look for the root cause that explains several local failures at once;
- remember that many reviewer findings may be one bug wearing different clothes;
- assume that many small issues may be symptoms of one larger problem: the text became reference-like, documentation-shaped, or otherwise stopped being an explanatory note that teaches according to `styleguide.md`;
- rewrite toward the right teaching artifact, not toward whichever reviewer sounds strongest in isolation.

Interpret the `reader` lens as a noisy detector, not as an authority:
- expect false positives, literal-minded complaints, and occasional missed problems;
- treat `reader` findings as signals to verify against the text, `Предпосылки`, and other reviewer lenses;
- do not rewrite solely because the `reader` objected;
- when `reader`, `prerequisites`, and `entry` all point at the same place, assume there is likely a real comprehension problem.

Interpret the `factcheck` lens as a high-trust reviewer, not as an automatic winner:
- trust it strongly on literal values, defaults, parameter names, versioned behavior, and direct contradictions with primary sources;
- still verify source applicability: product, version, context, and whether the source actually matches the note's claim;
- distinguish a pedagogically safe simplification from a distortion that creates a wrong mental model;
- do not let a source-backed micro-correction make the note worse at its current abstraction layer;
- if `factcheck` pulls against other lenses, search for a rewrite that keeps the note both accurate and teachable instead of choosing one lens as the winner.

Interpret the `prerequisites` lens as a high-priority boundary reviewer, not as the sole owner of clarity:
- trust it strongly when it finds hidden knowledge, undeclared technical terms, or a broken `Предпосылки` contract;
- still verify whether the local context already teaches enough for the reader to continue safely;
- prefer the smallest valid fix: add a prerequisite, explain inline, or delete decorative precision;
- do not bloat the note or the `Предпосылки` block just to satisfy a literal reading of the contract;
- if `prerequisites` pulls against `entry` or `narrative`, treat that as a sign to redesign the section so it keeps both comprehension and momentum.

Rules for reviewer agents:
- Keep reviewers independent. Do not preload them with your conclusions.
- Make them argue from the note and the live guides, not from a frozen checklist.
- Use a stronger model for fact checking and difficult synthesis when needed.
- Reuse reviewer threads for follow-up clarification instead of respawning near-identical agents.
- Do not let reviewer output become the final answer. Reviewer reports are inputs to editing.

### 4. Edit as the Main Agent

- Read reviewer reports.
- If a report is weak, vague, or unconvincing, ask that reviewer to clarify before acting on it.
- Edit the notes yourself, file by file, keeping the whole series in view.
- Prefer the smallest intervention that fixes the real problem, but rewrite aggressively when the current section is structurally wrong.
- When rewriting, design the causal arc first: what question opens the section, what each paragraph adds to the reader model, and what concrete understanding the section should leave behind.
- Keep the final prose free of prompt leakage, styleguide vocabulary, and formulaic repair artifacts.
- Before deleting material, explicitly ask: should this be corrected, compressed, moved, split into another note, linked upward or downward, or actually removed? Deletion is the last option, not the default cleanup move.
- When a concept is allowed by `Предпосылки` but the local wording may still leave lexical doubt, add an integrated cross-link at the first meaningful use. If the target file is broad, prefer a heading anchor to the exact subsection.

### 5. Run Before/After Regression Review

After edits, compare the new text against the pre-edit baseline.

- Use `git diff` when possible to inspect exactly what was removed, compressed, moved, or reframed.
- Look specifically for silent regression patterns: loss of concrete mechanism, loss of examples, loss of boundary conditions, loss of "when to use", loss of cross-layer context, or replacement of precise content with vague prose.
- Remember the shorthand rule: cleaner but thinner is a regression.
- For every substantial deletion, ask whether the removed material was:
  - wrong and should stay deleted;
  - redundant and safely merged elsewhere;
  - still useful but belongs in another file or layer;
  - useful and should be restored in this file.
- If the edited version is cleaner but teaches less, treat that as a regression.
- If the diff suggests that one large hidden cause produced many local edits, revisit the root problem instead of polishing the diff line by line.

### 6. Verify in at Least 10 Passes

After edits, reread the changed text at least 10 times with a fresh lens each pass. Do not mechanically reread the same way.

Suggested passes:
1. `Предпосылки` contract and hidden knowledge
2. Entry, motivation, and role-before-name
3. Section-to-section continuity and local bridges
4. Order of revelation and abstraction jumps
5. Observable effect and "when to use"
6. Factual accuracy and unsafe simplifications
7. Reader overload and dangling questions
8. Layer boundaries and neighboring-note consistency
9. Prompt leakage, metalanguage, and awkward repair phrasing
10. Final holistic read for retention: does the note leave a connected mental model rather than isolated facts?

If a verification pass reveals a new problem, fix it and restart the relevant passes.

### 7. Run Structural Review Last

Use `structure-guide.md` mechanically after the content work:
- naming and numbering
- `prev/next` navigation
- cross-links at first meaningful mention
- anchors when a whole-file link would be too broad
- `index.md` updates
- bidirectional links where expected
- cascading fixes in adjacent notes

## Scope Rules

- If the user asked only for inspection, audit, explanation, or review, keep the repository unchanged and report findings only.
- If the user asked to improve, fix, rewrite, or deeply review with correction, make the edits and then verify them.
- For fact-checking, prefer primary sources: official docs, standards, RFCs, specs, or vendor documentation. Use broader web search only when necessary and cite what materially informed the correction.

## Resources

- Reviewer prompts and lens definitions: [references/reviewer-lenses.md](references/reviewer-lenses.md)
