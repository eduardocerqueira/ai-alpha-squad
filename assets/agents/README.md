# Squad agent avatars

Line-only SVG icons (`stroke`, no fill) for GitHub issue comments and docs.

| File | Role |
| ---- | ---- |
| `orchestrator.svg` | Squad orchestrator / GitHub Actions |
| `business-owner.svg` | Business Owner |
| `architect.svg` | Architect |
| `developer.svg` | Developer |
| `qa.svg` | QA |
| `security.svg` | Security |
| `devops.svg` | DevOps |
| `release-manager.svg` | Release Manager |
| `tech-writer.svg` | Tech Writer |
| `director.svg` | Director (WhatsApp gate) |

Comments embed icons via `raw.githubusercontent.com` URLs (see `src/ai_alpha_squad/comments.py`). After adding or changing SVGs, merge to `main` so comment links resolve.

```bash
python3 scripts/format-squad-comment.py dispatch architect approved
```
