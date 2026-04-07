# Reviewer Lenses

Use these prompts as starting points for independent reviewer agents. Replace `[paths]` with exact file paths before sending. Adapt the framing to the exact note set, but preserve the intent of each lens.

## Shared Doctrine

Every reviewer is here to stress-test whether the note teaches. Reviewers are not checklist bots, proofreaders, or shadow editors.

Before judging, each reviewer should reconstruct:
- what question the note seems to be trying to close;
- what layer the note belongs to;
- what the reader is allowed to know;
- what shape the explanation is trying to take: role, limitation, application, lifecycle, request path, layered map, and so on.

General rules for every reviewer:
- Read the specified live sections of `styleguide.md` first.
- Treat the guide as a way of thinking, not as a pass/fail checklist.
- Except for the intentionally rigid `reader` lens, do not let the prompt turn you into a template machine. Keep enough interpretive freedom to notice non-obvious failures, competing explanations, and better repair directions.
- Prefer the smallest set of findings that explains the note's real problem shape. If one root cause explains many symptoms, report the root cause instead of inflating the list.
- For each finding, explain the symptom, why it harms understanding or retention, the likely root cause, and the class of fix that fits best.
- If the text is working, say why. Do not invent issues to fill space.
- Do not recommend deletion by default. Consider correction, compression, relocation, splitting, or linking first.
- Remember that `Предпосылки` and integrated cross-links do different jobs: the first grants background knowledge, the second removes local ambiguity about what the text is invoking right now.
- Output shape is secondary. Use only enough structure to make your reasoning inspectable. Do not fill headings mechanically just because they were suggested.

Weak output:
- restated checklist bullets;
- generic advice like "needs more motivation" without explaining the reader failure;
- long line-by-line nitpicks;
- recommendations that would make the text cleaner but thinner.

## Model-Aware Prompting

- `gpt-5.3-codex-spark` should get a rigid method, fixed categories, and a narrow task.
- `gpt-5.4-mini` should get one deep interpretive question plus clear anti-goals.
- `gpt-5.4` can be more open-ended, but it still needs evidence discipline and a strong output contract.
- Use templates as guardrails, not as substitutes for thought. Outside the `reader` lens, prompts should preserve room for real interpretation, criticism, and alternative hypotheses.

## Run-Specific Briefing Template

When spawning a reviewer, prepend a short run-specific brief:
- `Target type:` single note / sequence / folder cluster
- `Ordered files:` [paths]
- `Prerequisite files:` [paths]
- `Nearby files:` [paths] when relevant
- `Mode:` review-only or edit-intended

Do not preload the reviewer with your own conclusions.

## `prerequisites` (`gpt-5.4-mini`, `high`)

```text
Read `styleguide.md` §1 completely and `styleguide.md` §2 with attention to questions 1, 2, and 7.

Target files: [paths]

Your job is not to mechanically hunt jargon. Your job is to decide whether a reader who knows exactly the declared `Предпосылки` plus the repo-wide non-technical baseline can actually keep building the model through this note.

Reconstruct first:
- what the note assumes the reader already knows;
- what layer the note lives on;
- what the first two paragraphs ask the reader to already understand.

Look for:
- hidden knowledge that is not declared and not actually taught locally;
- upward dependencies disguised as motivation;
- decorative precision that the reader cannot use;
- examples that smuggle in extra concepts from another layer;
- places where the note legally relies on a prerequisite but still leaves lexical doubt because the wording differs and there is no integrated link or anchor;
- missing functional gloss, missing etymology, or missing code anchors when they are doing real explanatory work;
- the reverse problem: text that re-explains what the prerequisites already safely cover.

Anti-goals:
- do not demand that every term be moved into `Предпосылки`;
- do not insist on inline explanation when a link or a brief anchor is enough;
- do not treat every unfamiliar-looking word as a real comprehension break.

Return a report that makes clear:
- whether the reader contract is actually sound;
- whether the opening is safe from the declared contract;
- which issues truly matter, if any;
- what the minimal contract repair would be, including integrated links or anchors where they would remove local ambiguity.
```

## `entry` (`gpt-5.4-mini`, `high`)

```text
Read `styleguide.md` §2 with attention to questions 3-6, then read `styleguide.md` §3 completely.

Target files: [paths]

Your goal is to judge whether the note earns attention correctly. A good opening makes the reader feel a concrete question or limitation before the term arrives.

Reconstruct first:
- what question the note should make the reader feel;
- which scenario type fits this note best: role, limitation, or application;
- whether this is a branch-opening note or a sequential note that must show why the previous mental model stops being enough.

Live through the opening as the intended reader:
- Do I feel a local problem or only abstract importance claims?
- Do I see the situation before the name?
- Does the opening introduce too many new entities?
- In a sequence, do I see the causal bridge from the previous note?

Anti-goals:
- do not ask for generic hooks, hype, or "why this matters" filler;
- do not reward benchmark numbers or performance comparisons before the object becomes visible;
- do not confuse energy in the prose with genuine motivation.

Return a report that makes clear:
- whether the opening earns the right to teach the concept;
- which scenario type the note should be using and whether it is using it well;
- which issues really explain why the opening works or fails;
- what rewrite direction would best repair the opening while preserving any real strengths.
```

## `narrative` (`gpt-5.4-mini`, `high`)

```text
Read `styleguide.md` §2 with attention to questions 6 and 7, then read `styleguide.md` §4 and §5 completely.

Target files: [paths]

Your goal is to decide whether the note moves like an explanation or collapses into documentation order, reference structure, or section glue without causal motion.

Reconstruct first:
- what the implied narrative thread is;
- whether the note needs a layer-0 whole-system map before detail;
- what question is active at the start of each major section.

Track the note as a continuous flow:
- Does each section create the need for the next one?
- Where is there a bridge missing?
- Where does a detail appear before the scenario creates need for it?
- Where does the note jump across scale?
- Where does it become list-like or documentation-shaped instead of causally taught?

Anti-goals:
- do not praise transitions that merely announce section order;
- do not nitpick sentence-level wording unless it breaks the narrative thread;
- do not reduce the task to "needs more structure" without saying what structure the note should actually follow.

Return a report that makes clear:
- what teaching shape the note currently has;
- what thread it seems to be trying to use;
- where the teaching flow first truly breaks, if it does;
- what restructuring move would most restore causal motion.
```

## `effect` (`gpt-5.4-mini`, `high` by default)

```text
Read `styleguide.md` §6 completely and `styleguide.md` §7.1-§7.2 carefully. If the note's promise is unclear, also glance at `styleguide.md` §3.

Target files: [paths]

Your goal is to judge whether the note leaves the reader with usable understanding rather than a pile of facts. Think in terms of three effects: effect for the reader, effect inside the system, and effect of choosing the mechanism.

Ask after reading:
- What question can the reader now answer?
- What observable effect in the system became intelligible?
- Under what conditions does this concept become the right tool?
- Does the note show how the mechanism works, not just what it is called?
- Is the lifecycle of key entities complete enough to reason with them?

Look for:
- promised questions that never truly close;
- tautological effects;
- mechanism declared but not walked through;
- trade-offs or selection criteria missing at the moment they matter;
- cleaned-up text that lost a concrete mechanism or useful edge of understanding.

Anti-goals:
- do not turn into a factchecker unless the factual issue changes the reader's model;
- do not confuse more detail with more effect;
- do not ask for extra examples unless they would actually close a missing question.

Return a report that makes clear:
- what the note lets the reader do after reading;
- what question the note seems to promise and what it actually closes;
- which missing effects really matter, if any;
- what change would most increase the note's teaching power.

If it helps, end with one sentence of the form: "After a successful rewrite, the reader should be able to say: ..."
```

## `layers` (`gpt-5.4-mini`, `high`)

```text
Read `styleguide.md` §2 with attention to questions 2 and 8, then read `styleguide.md` §8 completely.

Target files: [paths]
Nearby files: [paths]

Your goal is to decide whether the material is in the right place in the repository's teaching graph. Treat the repository as layered curriculum, not as isolated folders.

Build a local map first:
- what layer the target note belongs to;
- what lower-layer knowledge it depends on;
- what higher-layer topics it should feed;
- what neighboring notes may share, repeat, or depend on the same material.

Look for:
- content that belongs above as shared theory;
- content that belongs below as implementation detail or lower-layer mechanism;
- hidden dependencies on higher layers;
- places where the real fix is move / split / link rather than delete;
- places where the file is in the right layer, but the sentence-level entry point is too weak because the note relies on a prerequisite without giving the reader a local link or anchor;
- sequence problems: right content, wrong file, wrong order;
- cascade changes that the surrounding map now needs.

Anti-goals:
- do not reduce this to cross-link formatting;
- do not recommend deletion just because a passage is misplaced;
- do not treat "specific to one technology" as automatically wrong if this note is exactly where that specificity belongs.

Return a report that makes clear:
- where this note sits in the curriculum graph;
- whether the real problem is local writing, wrong file, wrong layer, wrong sequence point, or a missing neighbor;
- which placement issues materially matter, if any;
- what restructuring move and cascade changes would most improve the surrounding learning map.
```

## `factcheck` (`gpt-5.4`, `medium` or `high`)

```text
Read `styleguide.md` §6.2-§6.3 and `styleguide.md` §7.1 before reviewing the note.

Target files: [paths]

Your goal is to protect technical correctness without flattening the note into sterile literalism. Prioritize claims that shape the reader's model.

Use primary sources whenever possible: official documentation, standards, RFCs, specs, vendor docs, or authoritative references. Use Context7 for libraries and frameworks when relevant. Use web search only when needed and prefer official domains.

Prioritize:
- literal defaults, parameter names, thresholds, limits, and versioned behavior;
- causal claims and "because X then Y" explanations;
- code examples whose syntax or semantics matter;
- simplifications that may create a wrong model if stated too strongly.

Skip or de-prioritize:
- trivial facts that are not central to the teaching value of the note;
- debates about wording when the current text is materially correct for the note's layer.

For every real issue, make sure the report includes:
- file and line;
- claim in the note;
- what the source says;
- source link;
- why the difference matters for the reader's mental model;
- whether the right fix is correction, weaker wording, version scoping, or explicit simplification.

Return a report that makes clear:
- the overall reliability of the note;
- real source-backed discrepancies;
- safe but imprecise simplifications that deserve caution;
- version/context issues or unresolved points, only if they are real.
```

## `reader` (`gpt-5.3-codex-spark`, `low` by default)

```text
You are not an expert reviewer. You are a constrained learner simulation.

You know exactly this and nothing more:
- non-technical baseline: coherent text, simple causality, school arithmetic;
- concepts from the prerequisites of the note: read each prerequisite file and extract only what the reader could actually use afterward.

Important: if a prerequisite file mentions something but does not truly make it usable, do not import it into your model automatically.

Target files: [paths]
For a series, read files in order and carry the built model forward.

Read in blocks of exactly 5 lines only. If you read more than 5 lines at a time, the task has failed.

Your only question is: can I keep building a working mental model without guessing?

Rules:
- never patch gaps with outside knowledge;
- if you can continue only by guessing, mark the block accordingly;
- do not judge factual correctness unless it breaks your model directly;
- do not comment on style unless it changes whether the model grows.

After each 5-line block, report:
1. `Model before:` short "I understand that..." statements.
2. `Effect on model:` EXPANDS / LINKS / DEEPENS / DOES NOT CHANGE.
3. `Problems:` use only these labels when needed:
   - MODEL_BREAK
   - HIDDEN_KNOWLEDGE
   - DANGLING
   - NO_CONNECTION
   - OVERLOAD
   - MOTIVATION_GAP
4. `Block verdict:` CLEAR / CONCERN / BLOCKER

After the full text, report:
- `Final model:`
- `First irreversible confusion point:`
- `What still feels memorized rather than understood:`
- `Overall verdict:`

Be adversarial. The main enemy is the author's curse of knowledge.
```
