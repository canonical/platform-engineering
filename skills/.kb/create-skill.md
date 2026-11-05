# Preface

How to add and maintain an agent skill in this repository.

IMPORTANT: Read the `.kb/agents.md` file.


# Laws

## §1 - One folder per skill

Create `skills/<name>/SKILL.md`. The front matter `name` MUST match the folder name, the `description` MUST say when to use the skill, and `metadata.version` MUST be semver.

## §2 - Skill first

An action that has to be repeated on more than five repositories needs a skill, a validator and a charmkeeper recipe, as described in `CONTRIBUTING.md`.

## §3 - Keep validators out of the skill

Executable validators belong in `validators/`. The skill MUST invoke the versioned validator with `uvx`; do not keep a second copy under `skills/<name>/scripts/`.


# Concepts

## Layout

```text
skills/<name>/
├── SKILL.md
├── assets/            # optional templates copied into target repositories
└── charmkeeper.yaml   # recipe that applies the skill on many repositories
```

Use [`configure-gh-jira-sync-bot`](../configure-gh-jira-sync-bot/) as a starting point.

## Checklist

1. Create the skill folder and write `SKILL.md` with front matter and a short, imperative workflow.
2. Put reusable templates in `assets/` instead of duplicating them in the prompt.
3. Add or update the matching validator in `validators/` and reference its versioned `uvx` command from the skill.
4. Add `charmkeeper.yaml` with eligibility rules, an LLM prompt, guardrails and validation tests.
5. Keep user-specific values out of the skill; instruct the agent to discover them from the target repository.
6. Run `just lint` and verify the skill's validation command on a representative repository.
