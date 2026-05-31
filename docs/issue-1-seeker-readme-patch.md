# Seeker README — Proposed Updates

> **Status:** Draft for review. These updates should be applied to the
> [`eduardocerqueira/seeker`](https://github.com/eduardocerqueira/seeker) README
> via a PR from the Tech Writer or Developer. They bring the README into
> alignment with the modernized implementation (Issue
> [#1](https://github.com/eduardocerqueira/ai-alpha-squad/issues/1)).
>
> **Traceability:** FR-003, FR-004, FR-008, BR-003, BR-004, BR-008

---

## Proposed README sections

The following content should be merged into the seeker `README.md`.
Existing sections that conflict should be updated; all other content
should be preserved.

---

### Requirements

```markdown
## Requirements

- **Python ≥ 3.12** (tested on 3.12.x)
- `pip` ≥ 23
- (Optional) `make` for convenience targets
```

---

### Installation

```markdown
## Installation

### 1. Clone the repository

```bash
git clone https://github.com/eduardocerqueira/seeker.git
cd seeker
```

### 2. Create a virtual environment

```bash
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
```

### 3. Install dependencies

```bash
pip install -e ".[dev]"
```

> **Pinning:** For reproducible deployments pin the dependency set after
> install: `pip freeze > requirements-lock.txt`. Restore with
> `pip install -r requirements-lock.txt`.

### 4. Verify the install

```bash
python -c "import seeker; print('seeker ready')"
pytest --tb=short -q
```

All tests should pass before running a collection job.
```

---

### Scheduled collection

```markdown
## Scheduled collection

seeker runs on a cron schedule. Set the schedule string in your
configuration file or environment variable.

### Accepted schedule formats

| Format | Example | Meaning |
| ------ | ------- | ------- |
| Every N minutes | `*/15 * * * *` | Every 15 minutes |
| Every N hours | `0 */6 * * *` | Every 6 hours |
| Daily at HH:MM | `0 2 * * *` | 02:00 UTC daily |
| Monthly | `0 0 1 * *` | 1st of month at midnight |
| Standard shortcut | `@daily` | Once per day |
| Standard shortcut | `@hourly` | Once per hour |
| Standard shortcut | `@weekly` | Once per week |
| Standard shortcut | `@monthly` | Once per month |

seeker validates the schedule at startup. An invalid or empty value
causes the runner to exit with a descriptive error rather than starting
silently with no schedule.

### Example configuration

```yaml
schedule: "*/30 * * * *"   # collect every 30 minutes
```

### Verifying a schedule string

```python
from ai_alpha_squad.seeker_qa import validate_cron_schedule
result = validate_cron_schedule("*/30 * * * *")
print(result.is_valid)   # True
print(result.errors)     # []
```
```

---

### Data obfuscation

```markdown
## Data obfuscation

seeker automatically redacts sensitive values before writing collected
data to any output. The following patterns are matched and replaced with
`[REDACTED]`:

| Category | Pattern matched |
| -------- | --------------- |
| Email addresses | `user@domain.tld` |
| Token-bearing URLs | `https://…?token=…` |
| Long API keys | Alphanumeric strings ≥ 32 characters |

Obfuscation is idempotent — running the pipeline twice does not produce
double-redacted output.

> **Extending patterns:** If your data sources contain additional secret
> formats, add named entries to `OBFUSCATION_PATTERNS` in
> `seeker/obfuscation.py` following the existing regex convention.
```

---

### Troubleshooting

```markdown
## Troubleshooting

### Runner exits immediately with a schedule error

**Symptom:** `ScheduleValidationResult(is_valid=False, errors=['Schedule is empty or blank'])`

**Cause:** The `SEEKER_SCHEDULE` environment variable (or `schedule` key
in config) is not set or is blank.

**Fix:** Set a valid cron expression, e.g. `SEEKER_SCHEDULE="*/15 * * * *"`.

---

### Output contains `[REDACTED]` unexpectedly

**Symptom:** Legitimate values are being redacted.

**Cause:** The value matches one of the obfuscation patterns (≥ 32-char
alphanumeric is the most common false-positive trigger for long IDs).

**Fix:** Shorten identifiers where possible, or adjust `OBFUSCATION_PATTERNS`
to narrow the `long_api_key` regex for your environment.

---

### Tests fail after upgrading Python

**Symptom:** `SyntaxError` or `ImportError` on Python < 3.12.

**Fix:** Upgrade to Python ≥ 3.12. Check with `python --version`.

---

### Running the test suite

```bash
# All tests
pytest -q

# Schedule validation only (FR-005)
pytest tests/test_seeker_scheduled.py -v

# Obfuscation only (FR-006)
pytest tests/test_seeker_obfuscation.py -v
```
```

---

## Traceability

| README section | FR / BR | Issue |
| -------------- | ------- | ----- |
| Requirements | BR-003 | [#1](https://github.com/eduardocerqueira/ai-alpha-squad/issues/1) |
| Installation | FR-003, FR-004, BR-004 | [#1](https://github.com/eduardocerqueira/ai-alpha-squad/issues/1) |
| Scheduled collection | FR-005, BR-005 | [#1](https://github.com/eduardocerqueira/ai-alpha-squad/issues/1) |
| Data obfuscation | FR-006, BR-006 | [#1](https://github.com/eduardocerqueira/ai-alpha-squad/issues/1) |
| Troubleshooting | FR-003 | [#1](https://github.com/eduardocerqueira/ai-alpha-squad/issues/1) |
