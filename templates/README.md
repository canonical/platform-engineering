# Templates

Templates for new Platform Engineering projects. GitHub template repositories
only work as standalone repositories, so the templates live in their own
repositories and are indexed here.

| Template | Use it for |
|----------|------------|
| [platform-engineering-charm-template][charm] | A new Juju charm, with CI, docs, release and Terraform workflows |

To start a project, open the template repository and choose
**Use this template**, or run:

```shell
gh repo create canonical/<new-repo> --template canonical/platform-engineering-charm-template
```

Keep a new project aligned with the practices in this repository: see the
[`pfe-practices`](../skills/pfe-practices/SKILL.md) skill and the
[validators](../validators).

## Adding a template

1. Create the template in its own repository and mark it as a template
   repository.
2. Add a row to the table above.
3. Reference this repository's practices instead of repeating them.

[charm]: https://github.com/canonical/platform-engineering-charm-template
