# Security Policy

## Supported Versions

Security updates are applied to the latest commit on the `main` branch.

| Version | Supported |
|---|---|
| `main` (latest) | ✅ Yes |
| Older releases | ❌ No |

---

## Reporting a Vulnerability

If you discover a security vulnerability in this project, please report it responsibly:

1. **Open a GitHub Issue** in this repository describing the vulnerability.
   - Label the issue `security`.
   - Do **not** include actual credentials, keys, or sensitive data in the issue body.
2. The maintainer will acknowledge the report within **48 hours** and aim to resolve critical issues within **7 days**.
3. For issues involving exposed credentials, the maintainer will **revoke and rotate** affected keys within **24 hours** of notification.

> If you prefer private disclosure, mention it in the issue and a maintainer will follow up via GitHub's private communication channels.

---

## API Key Management

### Rules for Contributors

- **Never commit `.env` files.** The `.gitignore` already excludes `.env` — keep it that way.
- **Never hardcode API keys** in source code, scripts, or documentation.
- **Always use environment variables.** All key access in this project uses `os.getenv()`.

### For Local Development

Copy the provided template and fill in your own keys:

```bash
cp .env.example .env
# Edit .env with your own credentials — never commit this file
```

### For CI/CD (GitHub Actions)

Store secrets in **GitHub Actions Secrets** (`Settings → Secrets and variables → Actions`), not in workflow YAML files or committed configuration.

```yaml
# Example: accessing a secret in a workflow
env:
  OPENAI_API_KEY: ${{ secrets.OPENAI_API_KEY }}
  UPBIT_ACCESS_KEY: ${{ secrets.UPBIT_ACCESS_KEY }}
  UPBIT_SECRET_KEY: ${{ secrets.UPBIT_SECRET_KEY }}
```

### `.env.example` Policy

The `.env.example` file contains **placeholder values only**. It must never contain real credentials:

```env
# .env.example — placeholders only
UPBIT_ACCESS_KEY=your_upbit_access_key_here
UPBIT_SECRET_KEY=your_upbit_secret_key_here
OPENAI_API_KEY=your_openai_api_key_here
```

---

## Personal Information Policy

To protect contributor and maintainer privacy:

- **No real email addresses, phone numbers, or physical addresses** may be committed to this repository.
- Use generic placeholders in documentation:
  - Email: `contact@example.com`
  - Address: `[address redacted]`
- Pull requests containing real personal information will be requested to remove it before merging.

---

## Incident Response

### If You Find Exposed Credentials

1. **Open a GitHub Issue immediately** with the label `security`.
2. Do not exploit or further distribute the exposed credentials.
3. The maintainer will:
   - Revoke the exposed credentials within **24 hours**.
   - Purge the credentials from git history using `git filter-repo`.
   - Force-push the cleaned history to GitHub.
   - Issue new credentials and update local `.env`.
   - Publish an incident report under `docs/I0XX-Security-Incident-*.md`.

### Past Incidents

| ID | Date | Summary |
|---|---|---|
| [I013](docs/I013-Security-Incident-API-Key-Exposure.md) | 2026-03-09 | `.env` file with API keys found in git history upon repository going public. Keys revoked and history purged. |

---

## Recommended Developer Tools

| Tool | Purpose |
|---|---|
| [`git-secrets`](https://github.com/awslabs/git-secrets) | Pre-commit hook to block accidental secret commits |
| [`detect-secrets`](https://github.com/Yelp/detect-secrets) | Scan repository for accidentally committed secrets |
| [`truffleHog`](https://github.com/trufflesecurity/trufflehog) | Deep git history secret scanning |
| GitHub Secret Scanning | Automatic detection for public repositories |

---

*Security policy effective: 2026-03-09 | Project: maiupbit (Apache-2.0)*
