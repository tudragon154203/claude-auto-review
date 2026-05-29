# Refactor Roadmap

Architectural improvements and refactoring opportunities, organized by phase and dependency order.

---

## Phase 1: Foundation — Configuration & Data Flow

**Goal:** Eliminate the config layering violations and establish clean data ownership boundaries.

### 1.1 Extract `ConfigService` from `StopDecisionEngine`
- **Files:** `claude_auto_review/stop/orchestration/decision_engine.py`
- **Change:** Move `load_settings` call out of engine initialization. Engine receives `PluginSettings` as constructor parameter, not `project_root`.
- **Benefit:** Engine becomes testable with mock config; eliminates I/O in orchestrator.
- **Risk:** Low — pure dependency injection refactor.

### 1.2 Move `ensure_client_runtime` to caller
- **Files:** `claude_auto_review/stop/orchestration/decision_engine.py:70`
- **Change:** Caller (hook entry point) calls `ensure_client_runtime(project_root, client_id)` before constructing engine.
- **Benefit:** Engine becomes pure evaluation logic; side effects move to boundary.
- **Risk:** Low — single call site.

### 1.3 Separate state store read/write paths
- **Files:** `claude_auto_review/state/store/read.py`, `claude_auto_review/state/store/write.py` (new)
- **Change:** Extract write operations (`append_event`, `write_state_record`) into dedicated module. Keep read operations in `read.py`.
- **Benefit:** Clear separation of concerns; enables independent evolution of read/write logic.
- **Risk:** Low — mechanical split.

**Dependencies:** None. This phase establishes the foundation for all subsequent work.

---

## Phase 2: Core Logic — State Management

**Goal:** Consolidate the fragmented state model and enforce hash tracking as first-class concept.

### 2.1 Create `FileHash` value type
- **Files:** `claude_auto_review/state/models.py` (new type)
- **Change:** Define `FileHash` dataclass with `value: str` (8-char SHA-256 prefix). Replace all `str` hash parameters with `FileHash` throughout codebase.
- **Benefit:** Type safety; prevents accidental misuse of raw strings; documents intent.
- **Risk:** Medium — touches many call sites.

### 2.2 Consolidate `EditRecord` and `ReviewMetadata` into unified state model
- **Files:** `claude_auto_review/state/models.py`
- **Change:** Introduce `StateEntry` base class with `EditEntry` and `ReviewEntry` subtypes. Each entry tracks file path, hash, timestamp, and verdict (if reviewed).
- **Benefit:** Single source of truth for state; eliminates parallel tracking logic.
- **Risk:** Medium — requires migration of existing state files.

### 2.3 Extract `StateTracker` service
- **Files:** `claude_auto_review/state/tracker.py` (new)
- **Change:** Create `StateTracker` class that owns all state mutations. Methods: `record_edit(file, hash)`, `record_review(file, hash, verdict)`, `get_unreviewed()`, `get_consecutive_blocks()`.
- **Benefit:** Encapsulates state logic; replaces scattered `get_unreviewed_files` / `consecutive_stop_blocks` calls.
- **Risk:** Medium — requires refactoring stop-flow to use tracker.

**Dependencies:** Phase 1.3 (state store split).

---

## Phase 3: Orchestration — Stop Flow Simplification

**Goal:** Flatten the layered stop-flow abstractions into a direct pipeline.

### 3.1 Merge `StopDecisionEngine` and `StopFlowService`
- **Files:** `claude_auto_review/stop/orchestration/decision_engine.py`, `claude_auto_review/stop/orchestration/service.py`
- **Change:** Inline `StopFlowService` into `StopDecisionEngine`. Engine directly executes stages instead of delegating to service.
- **Benefit:** Eliminates redundant layer; reduces indirection.
- **Risk:** Low — mechanical merge.

### 3.2 Convert stage functions to pipeline
- **Files:** `claude_auto_review/stop/orchestration/stages.py`
- **Change:** Replace individual `run_*_stage` functions with `StopPipeline` class that executes stages sequentially and returns early on terminal decisions.
- **Benefit:** Explicit control flow; easier to add/remove stages; better testability.
- **Risk:** Medium — changes stage signatures.

### 3.3 Inline trivial context helpers
- **Files:** `claude_auto_review/runtime/context.py`
- **Change:** Move `resolve_project_root` and `resolve_client_id` to call sites. Remove module-level `_DEFAULT_CLIENT_ID` cache.
- **Benefit:** Eliminates global state; simplifies runtime context.
- **Risk:** Low — few call sites.

**Dependencies:** Phase 1.1, 1.2 (engine receives clean inputs).

---

## Phase 4: Review Pipeline — Lifecycle Extraction

**Goal:** Make review creation, execution, and parsing explicit and testable.

### 4.1 Extract `ReviewLifecycle` service
- **Files:** `claude_auto_review/review/lifecycle.py` (new)
- **Change:** Create `ReviewLifecycle` class with methods: `create_prompt(unreviewed)`, `execute_review(prompt_path)`, `parse_verdict(review_path)`.
- **Benefit:** Encapsulates review flow; replaces scattered calls in `stop/reviews/prompt_runner.py` and `review/prompting/flow.py`.
- **Risk:** Medium — requires refactoring review execution path.

### 4.2 Extract `ReviewExecutor` abstraction
- **Files:** `claude_auto_review/review/executor.py` (new)
- **Change:** Create `ReviewExecutor` protocol with `ClaudeExecutor` and `CodexExecutor` implementations. Move backend-specific logic from `prompt_runner.py` into executors.
- **Benefit:** Clean separation of backend concerns; easier to add new backends.
- **Risk:** Medium — touches subprocess execution logic.

### 4.3 Simplify `ReviewPromptArtifacts` construction
- **Files:** `claude_auto_review/review/prompting/flow.py:46-94`
- **Change:** Extract `ReviewPromptBuilder` class that owns prompt construction. Reduce `create_review_prompt_files` to a single method call.
- **Benefit:** Reduces function complexity; makes prompt generation testable.
- **Risk:** Low — localized refactor.

**Dependencies:** Phase 2.3 (StateTracker provides unreviewed files).

---

## Phase 5: Supporting Infrastructure

**Goal:** Clean up utilities, config merging, and test support.

### 5.1 Simplify `PluginSettings` construction
- **Files:** `claude_auto_review/config/models.py`, `claude_auto_review/config/io.py`
- **Change:** Make `PluginSettings.from_mapping` the only construction path. Remove `normalize_plugin_settings` mutation pattern.
- **Benefit:** Immutable config; clearer construction flow.
- **Risk:** Low — config is already mostly immutable.

### 5.2 Extract `HooksMerger` utility
- **Files:** `claude_auto_review/config/project_settings.py:22-57`
- **Change:** Move `merge_unique_hook_list` and `merge_hook_buckets` into `claude_auto_review/config/hooks_merge.py`. Keep `project_settings.py` focused on settings I/O.
- **Benefit:** Separates hook merging logic from settings persistence.
- **Risk:** Low — pure extraction.

### 5.3 Consolidate test support utilities
- **Files:** `tests/support_paths.py`, `tests/support_classifier_server.py`, `tests/int/support.py`
- **Change:** Create `tests/support/` package with submodules: `paths.py`, `fixtures.py`, `mocks.py`. Migrate existing support files.
- **Benefit:** Cleaner test organization; easier to find and reuse test helpers.
- **Risk:** Low — test-only refactor.

**Dependencies:** None, but best done after core refactors to avoid churn.

---

## Phase 6: Optional — Path Resolution Hardening

**Goal:** Make path resolution robust across platforms and contexts.

### 6.1 Centralize path resolution
- **Files:** `claude_auto_review/paths/resolver.py` (new)
- **Change:** Create `PathResolver` class that owns all path construction. Methods: `settings_path()`, `state_path()`, `review_path()`, etc. Inject `project_root` and `client_id` at construction.
- **Benefit:** Single source of truth for paths; eliminates scattered `Path` construction.
- **Risk:** Medium — touches many path-building call sites.

### 6.2 Add platform-specific path normalization
- **Files:** `claude_auto_review/paths/resolver.py`
- **Change:** Add explicit Windows/Unix path normalization. Ensure URIs and file paths are handled consistently.
- **Benefit:** Prevents cross-platform path bugs.
- **Risk:** Low — defensive enhancement.

**Dependencies:** None, but lower priority than core logic refactors.

---

## Execution Strategy

### Recommended Order
1. **Phase 1** (Foundation) — do first, enables everything else
2. **Phase 2** (State) — high impact, moderate risk
3. **Phase 3** (Stop Flow) — simplifies orchestration after state is clean
4. **Phase 4** (Review Pipeline) — depends on clean state model
5. **Phase 5** (Supporting) — cleanup, can be done incrementally
6. **Phase 6** (Paths) — optional, do if cross-platform issues arise

### Testing Strategy
- **Before each phase:** Run full test suite, capture baseline
- **After each sub-task:** Run unit tests, verify no regressions
- **After each phase:** Run integration and e2e tests, verify behavior unchanged
- **Migration:** For state model changes (Phase 2.2), write migration script and test against real state files

### Risk Mitigation
- **Small commits:** Each sub-task should be a separate commit
- **Feature flags:** For Phase 2.2 (state model), consider feature flag to enable gradual rollout
- **Rollback plan:** Keep old state format readable for one release cycle

---

## Success Metrics

- **Testability:** Engine and services can be unit-tested without I/O mocks
- **Cohesion:** Each module has a single, clear responsibility
- **Complexity:** No function exceeds 50 lines; no class exceeds 150 lines
- **Duplication:** Eliminate parallel tracking of file hashes and review state
- **Clarity:** New contributor can understand stop-flow by reading `StopPipeline` alone

---

## Notes

- **Don't over-engineer:** If a refactor doesn't clearly improve testability or clarity, skip it
- **Preserve behavior:** All refactors should be behavior-preserving; new features go in separate PRs
- **Document decisions:** Update CLAUDE.md if architectural decisions change (e.g., state model structure)
