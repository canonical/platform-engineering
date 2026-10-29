# validator-template

Starting point for a new validator. It is excluded from the uv workspace and
from CI.

## Create a validator

1. Copy the template, using a `check-<topic>` name:

   ```shell
   cp -r compliance/validators/_template compliance/validators/check-foo
   mv compliance/validators/check-foo/src/validator_template \
      compliance/validators/check-foo/src/check_foo
   grep -rl 'validator[-_]template' compliance/validators/check-foo \
     | xargs sed -i 's/validator-template/check-foo/g; s/validator_template/check_foo/g'
   ```

2. Replace `PFE-XXX-NNN` with a practice ID (`PFE-<AREA>-<NNN>`, the area
   matching the folder of the practice page under `src/`) and implement
   `check()`.
3. Add the validator to the root `pyproject.toml` (`dependencies` and
   `[tool.uv.sources]`), then run `uv sync`.
4. Add tests and fixtures under `tests/`, and a self-test job in
   `.github/workflows/actions-selftest.yaml`.
5. For a validator that checks a developer machine rather than files, delete
   `action.yml`.
6. Rewrite this README following [`check-todos`](../check-todos/README.md),
   naming the practice page it enforces.
