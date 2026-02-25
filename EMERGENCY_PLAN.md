# Emergency Fix Plan (Alpha Stabilization)

Status: ACTIVE  
Scope: Stabilize current `thinking_graph` repo for public alpha/beta credibility (not full feature expansion)  
Priority: P0 first, feature freeze until P0 completed

## Why this plan exists
Current repository has good architecture direction, but lacks product-level engineering hygiene.
Main blockers:
- README and repo contents mismatch
- Missing CI/test baseline
- Risky production fallback behavior
- Packaging/dependency clarity issues
- Release hygiene incomplete

## Immediate Rule (Effective Now)
- **Feature freeze** on non-critical features
- Only fixes/docs/tests/CI allowed until P0 is done
- No new LLM/provider integrations before stability baseline

---

## P0 (Release blockers) — Must complete before calling it “product”

### P0-1: README / Repository Consistency
**Goal:** Remove trust-breaking inconsistencies and dead links.

- [*] Add `LICENSE` file (MIT if intended)
- [*] Add `CONTRIBUTING.md`
- [*] Update README project tree to match actual repo
- [*] Replace `app_config.toml` references with `app_config_example.toml`
- [*] Mark unfinished items explicitly as `Planned`
- [ ] Verify all relative links in README (no 404)

**Done when**
- README links all work
- New user can follow README and start locally

---

### P0-2: Minimal CI (Lint + Tests + Smoke)
**Goal:** Every PR gets baseline validation.

- [*] Add `.github/workflows/ci.yml`
- [*] Run on Python 3.11
- [*] Install dependencies
- [*] Lint (`ruff` or `flake8`)
- [*] Test (`pytest`)
- [*] Import/start smoke test (app factory / `main.py` startup path)

**Done when**
- PRs auto-run CI
- Main branch CI green

---

### P0-3: Minimal Test Suite (Core Path Protection)
**Goal:** Protect the project from obvious regressions.

#### Priority test targets
- [ ] `backend/repository.py` schema init
- [ ] transaction commit/rollback behavior
- [ ] basic node/edge CRUD consistency
- [ ] `web/__init__.py` app factory creation
- [ ] fallback behavior (dev mode only)
- [ ] LLM service malformed JSON / timeout error path (mocked)

**Done when**
- Core happy-path + key failure-path tests exist
- Not just “import passes”

---

### P0-4: Split Development vs Production Behavior
**Goal:** Prevent silent dangerous fallback in production.

- [ ] Add explicit runtime mode (`development` / `production`)
- [ ] Disable silent DB fallback in production (fail fast)
- [ ] Keep fallback only in development
- [ ] Log final resolved DB path at startup
- [ ] Emit warning when dev fallback is used

**Done when**
- Production config/storage errors fail loudly
- Development fallback remains convenient and visible

---

### P0-5: Dependency / Install Hygiene
**Goal:** Stable, reproducible setup.

- [*] Clean `requirements.txt` (remove or justify unused deps)
- [*] Confirm Python 3.11+ compatibility in practice
- [*] Split base/dev dependencies (optional but recommended)
- [*] Provide single documented setup flow
- [*] Re-check `dataclasses` backport necessity for py3.11+

**Done when**
- Fresh environment installs successfully
- README setup works without guesswork

---

### P0-6: Release Hygiene (Alpha honesty)
**Goal:** Set correct expectations and ship responsibly.

- [ ] Add project status label: `Alpha`
- [*] Add `CHANGELOG.md`
- [*] Tag first release (`v0.1.0-alpha`)
- [*] Add release notes
- [ ] Clarify repo identity (Web App vs Python package API)

**Done when**
- Users can tell what is stable vs experimental

---

## P1 (After P0, before wider adoption)
- [ ] API contract docs / schema validation
- [ ] Structured logging + request IDs
- [ ] LLM timeout/retry/backoff/cost tracking
- [ ] Security baseline (CORS, input limits, secret handling)
- [ ] Backup/restore workflow docs and test

---

## P2 (Polish / Product experience)
- [*] UX polish (empty states, undo/redo, autosave feedback)
- [ ] Docker / docker-compose deployment path
- [ ] Docs split (`architecture`, `deployment`, `troubleshooting`)
- [ ] Performance tuning for large graphs

---

## Working Schedule (Realistic Solo Estimate)
- Alpha credibility patch (P0): 1–2 weeks
- Public beta baseline (P0 + key P1): 3–6 weeks
- Product-ish v1 quality: 2–3+ months (scope-dependent)

---

## Tomorrow Morning First 3 Tasks (Do these first)
1. Fix README inconsistencies + add missing `LICENSE` / `CONTRIBUTING.md`
2. Add CI workflow and make it pass on current main
3. Create minimal tests for repository + app factory

---

## Definition of “Safe to Resume Feature Work”
All conditions must be true:
- [ ] P0 complete
- [ ] CI green on main
- [ ] README matches reality
- [ ] No silent production fallback
- [ ] First alpha tag published

---

## Notes
This plan intentionally prioritizes trust, reliability, and developer workflow over feature expansion.
