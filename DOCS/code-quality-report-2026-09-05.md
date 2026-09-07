# Code Quality Report — GPRBR CRM

**Date:** 2026-09-05
**Score:** 49/100 (Level 2 — Estruturado)
**Target:** 80+ (Level 4 — Maduro)

## Dimension Scores

| Dimension | Score | Max | Notes |
|-----------|-------|-----|-------|
| Architecture | 8 | 10 | Good separation (views/services/repositories), no circular imports |
| Code Quality | 6 | 10 | 493 ruff errors (180 mutable-class-default, 50 unused-import) |
| Tests | 5 | 15 | 27 test files exist, but only 15% overall coverage |
| Security | 6 | 15 | 145 dependency vulnerabilities, 6 SQL injection warnings (parameterized) |
| Maintainability | 5 | 10 | Clean structure, but 145 outdated dependencies |
| Documentation | 4 | 5 | Good README, architecture docs, API docs |
| Performance | 5 | 10 | Caching configured, 16 select_related/prefetch_related usages |
| DevOps/CI-CD | 4 | 10 | Railway deploy exists, no CI pipeline |
| Observability | 2 | 5 | Basic logging configured, no error tracking |
| Reliability | 4 | 10 | Some error handling, 22 blind-except in ruff |
| **TOTAL** | **49** | **100** | **Level 2 — Estruturado** |

## Critical Issues

### 1. **145 Dependency Vulnerabilities** (Security)
- `django 6.0.6` → needs `6.0.8`
- `cryptography 46.0.3` → needs `49.0.0+`
- `aiohttp 3.14.1` → needs `3.14.3`
- `chromadb 1.5.9` → 4 CVEs
- `djangorestframework 3.15.2` → needs `3.17.2`

### 2. **15% Test Coverage** (Tests)
- `contatos/views/*.py`: 0% coverage
- `repositories/gprb_repository.py`: 0% coverage
- `dashboard/views.py`: 0% coverage
- Only `contatos/importador.py` (93%) and `contatos/models.py` (91%) have good coverage

### 3. **493 Ruff Errors** (Code Quality)
- 180 `RUF012` (mutable class defaults)
- 53 `I001` (unsorted imports)
- 50 `F401` (unused imports)
- 49 `B008` (function call in default argument)

### 4. **No CI Pipeline** (DevOps)
- No GitHub Actions workflow
- No automated tests on PR
- No lint/security checks in CI

### 5. **No Error Tracking** (Observability)
- No Sentry/Rollbar integration
- No structured error logging
- No performance monitoring

## Recommendations to Reach 80+ (Level 4)

### Phase 1: Critical Security (Security +15 → 21)
```bash
# Update vulnerable dependencies
pip install --upgrade django cryptography aiohttp djangorestframework
pip-audit  # Verify fix
```

### Phase 2: Test Coverage (Tests +10 → 15)
- Add unit tests for `contatos/views/crud.py` (40+ test cases)
- Add unit tests for `repositories/gprb_repository.py` (30+ test cases)
- Add unit tests for `dashboard/views.py` (20+ test cases)
- Target: 60% overall coverage

### Phase 3: Fix Lint Errors (Code Quality +4 → 10)
```bash
# Auto-fix safe issues
ruff check . --fix --select I001,F401,UP032,UP009,FURB157,FURB167,FURB188

# Manual fixes needed
# - RUF012: Add `ClassVar` annotations to class-level mutable defaults
# - B008: Move function calls out of default arguments
```

### Phase 4: Add CI Pipeline (DevOps +6 → 10)
```yaml
# .github/workflows/ci.yml
name: CI
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.13'
      - run: pip install -r requirements.txt
      - run: python manage.py test
      - run: python -m ruff check .
      - run: python -m bandit -r contatos/ api/ dashboard/ repositories/
```

### Phase 5: Add Error Tracking (Observability +3 → 5)
- Add Sentry integration (`sentry-sdk[django]`)
- Add structured logging with JSON format
- Add performance monitoring

### Phase 6: Reduce Blind-Except (Reliability +3 → 7)
- Replace 22 `except:` with specific exceptions
- Add graceful degradation for GPRB queries
- Add health check endpoint

## Projected Score After Fixes

| Dimension | Current | After | Gain |
|-----------|---------|-------|------|
| Architecture | 8 | 8 | 0 |
| Code Quality | 6 | 10 | +4 |
| Tests | 5 | 15 | +10 |
| Security | 6 | 15 | +9 |
| Maintainability | 5 | 8 | +3 |
| Documentation | 4 | 4 | 0 |
| Performance | 5 | 6 | +1 |
| DevOps/CI-CD | 4 | 10 | +6 |
| Observability | 2 | 5 | +3 |
| Reliability | 4 | 7 | +3 |
| **TOTAL** | **49** | **88** | **+39** |

## Priority Order

1. **Update dependencies** (1-2 hours) → Security +9
2. **Add CI pipeline** (2-3 hours) → DevOps +6
3. **Fix ruff errors** (3-4 hours) → Code Quality +4
4. **Add tests** (8-12 hours) → Tests +10
5. **Add error tracking** (2-3 hours) → Observability +3
6. **Fix blind-except** (2-3 hours) → Reliability +3

**Total estimated time: 18-26 hours to reach 88/100 (Level 4)**
