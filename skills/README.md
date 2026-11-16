# Skills

Agent skills supporting our development practices. One folder per skill:

```text
skills/<skill-name>/SKILL.md
```

`SKILL.md` starts with front matter containing `name` (same as the folder) and `description`.

See [CONTRIBUTING.md](../CONTRIBUTING.md) for when a skill is required.

## Available skills

| Skill | Description |
| --- | --- |
| [`12factor-v2-upgrade`](12factor-v2-upgrade/) | Migrate a 12-factor app from `paas-charm` 1.x to 2.0 on Ubuntu 26.04 LTS |

## Planned skills

- `12f-v2-best-practices`
- `operator-workflow-to-charm-ci-migration`, `charm-ci-v1-best-practices`
- `terraform-cc008-migration`, `terraform-cc008-best-practices`
- `charm-best-practices`
- `charm-unit-test-best-practices`
- `charm-integration-test-best-practices` (should recommend tests to move to unit tests)
