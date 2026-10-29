# Templates

Templates for new Platform Engineering projects.

| Template | Use it for |
|----------|------------|
| [`charm/`](charm) | A new Juju charm, with CI, docs, release and Terraform workflows |

## Charm template

`charm/` is a vendored copy of [platform-engineering-charm-template][charm],
which stays the place to start a project from GitHub (**Use this template**).
To start from this directory instead:

```shell
cp -r templates/charm /path/to/new-charm
```

Changes to the template are made here; the standalone repository is kept in
sync from this directory.

Keep a new project aligned with the practices in this repository: see the
[`pfe-practices`](../skills/pfe-practices/SKILL.md) skill and the
[validators](../compliance/validators).

## Adding a template

1. Add it as a directory under `templates/`.
2. Add a row to the table above.
3. Reference this repository's practices instead of repeating them.

[charm]: https://github.com/canonical/platform-engineering-charm-template
