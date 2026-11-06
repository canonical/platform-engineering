# validate-jira-sync-config

Validate the `.github/.jira_sync_config.yaml` file of a repository using
[`canonical/gh-jira-sync-bot`](https://github.com/canonical/gh-jira-sync-bot), following the
Platform Engineering charm template conventions.

Layout (`src/validate_jira_sync_config/`):

- `config.py`: the validation rules and the list of valid ISD Jira components.
- `cli.py`: the command line interface.

## Usage

Requires Python >= 3.11.

```shell
uvx --from "git+https://github.com/canonical/platform-engineering@validate-jira-sync-config/v<version>#subdirectory=validators/validate-jira-sync-config" \
  validate-jira-sync-config /path/to/repo/.github/.jira_sync_config.yaml
```

Exit codes: `0` pass, `1` validation errors (or the file cannot be read).

## What it checks

- A top-level `settings` mapping exists.
- `settings.jira_project_key` is a non-empty string.
- `settings.status_mapping` is a mapping with non-empty `opened` and `closed` values, and a
  non-empty `not_planned` value when present.
- `settings.components` is a non-empty list of known, case-sensitive ISD Jira components.
  The singular `settings.component` key is rejected, as is the `<your-component>` placeholder.
- `settings.labels` is a non-empty list that includes both `bug` and `enhancement`, which
  prevents Dependency dashboard issues from being synced.
- `settings.epic_key` is not defined, `settings.label_mapping` maps labels to strings, and
  `settings.add_gh_comment`, when present, is a boolean.
- Every issue template in the sibling `.github/ISSUE_TEMPLATE/` directory (YAML or Markdown,
  excluding `config`) has a `labels` key containing `bug` or `enhancement`.

## Development

```shell
uv run --project validators --all-packages pytest validators/validate-jira-sync-config
```
