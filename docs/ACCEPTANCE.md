# Acceptance criteria

The acceptance criteria (C1–C8 from the implementation brief; C9–C11 added by P5,
architecture awareness), each mapped to the test(s) and
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
| 8 | A single-project group renders gracefully (architecture map shows just the current repo) | `test_hook.HookContract.test_single_project_group_no_siblings` |
| 9 | An enabled clone gets an architecture map listing every project, the current one marked, plus the "route new work" instruction | `test_hook.ArchitectureMap.test_map_present_marks_current_and_lists_siblings` |
| 10 | The current monorepo gets sub-area detail; siblings show area names only | `test_hook.ArchitectureMap.test_monorepo_current_shows_area_detail` (+ name-only assertions in `test_map_present_marks_current_and_lists_siblings`) |
| 11 | Missing `responsibility` falls back to `role`; an oversized group is truncated with `+N more` under the cap; unknown project is unmarked — none of it blocks | `test_hook.ArchitectureMap.test_map_falls_back_to_role`, `test_oversized_map_is_budgeted`, `test_unknown_project_has_no_marker` |

## Additional guarantees covered

- **Never blocks, ever**: each hook has an absolute `try/except` backstop and exits 0;
  on success stdout is exactly one JSON object (asserted in every render test).
- **Settings safety**: structural merge with timestamped backup, unrelated keys
  preserved, registry/protocol seeded only if absent
  (`MergeUnit.*`, `InstallScript.test_install_does_not_overwrite_existing_registry`).
- **Reinforcement hooks are advisory/non-blocking** and quiet outside opted-in clones
  (`test_nudge.*`).
- **Backward-compatible protocol**: a legacy template using only `{{SIBLINGS}}` (no
  architecture map) still renders, since the hook substitutes both old and new
  placeholders (`test_hook.ArchitectureMap.test_legacy_siblings_protocol_still_renders`).
- **Cross-platform**: the merge logic and the hook contract are exercised on all three
  OSes; the bash `install.sh`/`ledger-*` integration tests run on macOS/Linux and are
  explicitly `skipIf`-skipped on Windows (the shell helpers target POSIX shells).

Current status: **35 tests, all green** locally and in CI across the matrix.
