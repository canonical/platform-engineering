# Platform Engineering

Public standards and practices of the Platform Engineering team, kept in a single
mono-repo so that one pull request can evolve a practice end to end.

A change to "how we do things" updates, in the same PR, the matching:

- **Template** (`templates/`)
- **Documentation** (`docs/`, `kb/`)
- **Skill** (`skills/`)
- **Validator** (`validators/`)

Internal-only content lives in `canonical/pfe-internal`.

## Layout

| Folder | Content |
| --- | --- |
| [`docs/`](docs/) | Source of the public documentation of our development practices |
| [`kb/`](kb/) | Public knowledge base, including specs |
| [`skills/`](skills/) | Agent skills supporting our development practices |
| [`templates/`](templates/) | Project templates (copier), e.g. the charm template |
| [`validators/`](validators/) | `uvx`-callable scripts that check a repository against a practice |

## Using a validator

```shell
uvx --from "git+https://github.com/canonical/platform-engineering@<tag>#subdirectory=validators/<name>" <script> <path-to-repo>
```

## Using a template

See [`templates/README.md`](templates/README.md).

## Contributing

See [`CONTRIBUTING.md`](CONTRIBUTING.md).

## License

Apache-2.0, see [`LICENSE`](LICENSE).
