# Actions

Reusable GitHub Actions that are not validators (setup, publishing,
reporting, ...). Validator actions live next to their code in
[`compliance/validators/<name>/action.yml`](../compliance/validators).

Each action lives in its own directory with an `action.yml` and a
`README.md`:

```text
actions/
└── <action-name>/
    ├── action.yml
    └── README.md
```

Consume it with:

```yaml
- uses: canonical/platform-engineering/actions/<action-name>@v1
```

Prefer composite actions. If an action needs Python logic, put the logic in a
workspace package under `compliance/` and run it with
`uvx --from "${{ github.action_path }}/..."`.
