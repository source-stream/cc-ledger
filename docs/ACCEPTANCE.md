# Acceptance criteria

The 8 acceptance criteria from the implementation brief, each mapped to the test(s) and
mechanism that demonstrate it. The suite is standard-library `unittest`, hermetic (temp
git repos + fixtures, no network), and runs in CI on Linux/macOS/Windows × Python
3.9 & 3.12.

```sh
python3 -m unittest discover -s test
```

| # | Criterion | Demonstrated by |
|---|-----------|-----------------|
| 1 | Fresh install over an existing `settings.json` adds the hook without disturbing existing hooks/settings | `test_install.InstallScript.test_install_is_nondestructive_and_idempotent`; `MergeUnit.test_preserves_unrelated_config` |
| 2 | A clone with no marker injects and prints nothing | `test_hook.HookContract.test_no_marker_is_silent` |
| 3 | An enabled multi-project clone renders group/channel/project + siblings with roles | `test_hook.HookContract.test_enabled_clone_renders_protocol` |
| 4 | With the marker omitting `project`, it is inferred from the git remote | `test_hook.HookContract.test_project_inferred_from_remote` |
| 5 | Re-running the installer is a no-op (no duplicate hook entry) | `test_install.InstallScript.test_install_is_nondestructive_and_idempotent`; `MergeUnit.test_add_is_idempotent` |
| 6 | Malformed marker / missing or unparseable registry / unknown group / missing `group` never blocks or errors | `test_hook.HookContract.test_*_never_blocks` (5 tests) |
| 7 | The marker is in `.git/info/exclude` and `git status` is clean | `test_enable.EnableDisable.test_enable_writes_marker_excludes_and_stays_clean` (+ `test_disable_reverses`) |
| 8 | A single-project group renders a graceful "no siblings" protocol | `test_hook.HookContract.test_single_project_group_no_siblings` |

## Additional guarantees covered

- **Never blocks, ever**: each hook has an absolute `try/except` backstop and exits 0;
  on success stdout is exactly one JSON object (asserted in every render test).
- **Settings safety**: structural merge with timestamped backup, unrelated keys
  preserved, registry/protocol seeded only if absent
  (`MergeUnit.*`, `InstallScript.test_install_does_not_overwrite_existing_registry`).
- **Reinforcement hooks are advisory/non-blocking** and quiet outside opted-in clones
  (`test_nudge.*`).
- **Cross-platform**: the merge logic and the hook contract are exercised on all three
  OSes; the bash `install.sh`/`ledger-*` integration tests run on macOS/Linux and are
  explicitly `skipIf`-skipped on Windows (the shell helpers target POSIX shells).

Current status: **29 tests, all green** locally and in CI across the matrix.
