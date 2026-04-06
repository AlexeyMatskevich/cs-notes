# Reviewer Lenses

Use these prompts as starting points for independent reviewer agents. Replace `[paths]` with exact file paths before sending.

General rules for every reviewer:
- Read the specified live sections of `styleguide.md` first.
- Treat the guide as a way of thinking, not as a pass/fail checklist.
- Argue from what the text does to the reader's understanding.
- Prefer a few well-defended findings over a long shallow list.

## `prerequisites`

```text
Read `styleguide.md` §1 completely. Understand the idea: `Предпосылки` is a hard contract with the reader and a strict boundary between what the note explains and what it assumes.

Then read the target files: [paths].

Read as a person who knows only what is listed in `Предпосылки` plus the repo-wide non-technical baseline. Every time that reader would stumble, treat it as a real problem only if the surrounding text does not repair the gap.

For each issue, explain:
- why the reader would lose the thread;
- whether the right fix is adding a prerequisite, explaining inline, or deleting noise;
- whether the note also has the opposite problem: re-explaining things that are already safe to assume.
```

## `entry`

```text
Read `styleguide.md` §3 completely. Understand the idea: the reader should feel the question before getting the answer. Motivation is not decoration; it is the moment the need for the concept becomes real.

Then read the target files: [paths].

Live through the opening paragraphs as the intended reader:
- Do I feel a problem, lack, or strange effect?
- Do I see the situation before I get the term?
- In a series, do I understand why the previous mental model stops being enough?

Do not report formal rule breaks. Report places where the reader's interest drops or the text asks for attention before earning it.
```

## `narrative`

```text
Read `styleguide.md` §4 and §5 completely. Understand the ideas: the text should move like a story where each step creates the need for the next, and revelation should go from the whole to details without jumps.

Then read the target files: [paths].

Track the text as a continuous flow:
- Does each paragraph create the next question?
- Where does the text jump or break?
- Where is a solution given before the reader has felt the problem?
- Where does the text follow documentation order instead of reader need?

Judge the causal continuity of the note, not just the presence of transitions.
```

## `effect`

```text
Read `styleguide.md` §6 and §7 completely. Understand the ideas: the note should leave the reader with a concrete result, and facts must show how something works, not only what it is called.

Then read the target files: [paths].

After reading, ask:
- What concrete question does the note now let me answer?
- Did mechanisms reach an observable effect?
- Do I understand when this concept is the right tool?
- Where does the note define a thing without showing it in action?

Also flag factual mistakes, unsafe simplifications, and cause-effect reversals. Explain why each matters for the reader's mental model.
```

## `layers`

```text
Read `styleguide.md` §8 completely. Understand the idea: each note should stay on its knowledge layer, rely downward for prerequisites, and point upward by linking rather than by silently importing a higher layer.

Then read the target files: [paths], plus nearby notes in the same directory and the parent directory.

Check:
- whether the note explains material that belongs to another layer;
- whether it silently depends on a more applied or higher-level note;
- whether the surrounding note graph now needs cascading updates.

This is a boundary check, not a formatting audit.
```

## `factcheck`

```text
You are checking factual accuracy. Use official documentation, standards, RFCs, specs, and other primary sources. Use Context7 for libraries and frameworks when relevant, and web search for standards or vendor docs when needed.

Target files: [paths]

For every technical claim that can be verified:
- verify literal defaults, names, thresholds, and parameter values;
- distinguish safe simplification from dangerous simplification;
- check whether code examples are syntactically and semantically correct.

For each discrepancy, report:
- file and line;
- claim in the note;
- what the source says;
- why the difference matters;
- source.
```

## `reader`

```text
You are a student who knows exactly this and nothing more:
- non-technical baseline: coherent text, simple causality, school arithmetic;
- concepts from the prerequisites of the note: read each prerequisite file and extract what the reader should now understand.

You do not know any technical concept outside that set.

Target files: [paths]
For a series, read files in order and carry the built model forward.

Read in blocks of 5 lines only. If you read more than 5 lines at a time, the task has failed.

After each block, report:
1. My model before the block: short "I understand that..." statements.
2. What the block does to the model: EXPANDS / LINKS / DEEPENS / DOES NOT CHANGE.
3. Problems, if any:
   - MODEL_BREAK
   - HIDDEN_KNOWLEDGE
   - DANGLING
   - NO_CONNECTION
   - OVERLOAD
   - MOTIVATION_GAP
4. Block verdict: CLEAR / CONCERN / BLOCKER

After the full text, report:
- final model;
- unresolved questions;
- overall verdict.

Be adversarial. The main enemy is the author's curse of knowledge.
```
