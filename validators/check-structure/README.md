# check-structure

Checks that every `skills/<name>/SKILL.md` has `name` (matching the folder) and
`description` front matter, and that every `kb/**/*.md` entry has `title` and `owner`.

```shell
uvx --from "git+https://github.com/canonical/platform-engineering@<tag>#subdirectory=validators/check-structure" \
  pfe-check-structure <path-to-repo>
```
