# Security Incident Report — API Key Exposure (2026-03-09)

## Incident Summary

On 2026-03-09, during the conversion of this repository to public for open-source contributions, a security scan detected that the `.env` file containing real API keys had been included in the initial commit (2024-03-19). Although the file was removed from the working tree in a subsequent commit, the credentials remained accessible in git history.

All exposed credentials have been revoked and rotated. Git history has been purged using `git filter-repo`, and the clean history has been force-pushed to GitHub.

---

## Exposed Credentials

| Credential | Status |
|---|---|
| `OPENAI_API_KEY` | **Revoked** — new key issued |
| `UPBIT_ACCESS_KEY` | **Revoked** — new key issued |
| `UPBIT_SECRET_KEY` | **Revoked** — new key issued |

> **Note:** No financial transactions or unauthorized API usage were detected during the exposure window. UPbit withdrawal permissions were not enabled on the exposed keys.

---

## Timeline

| Time (GMT+7) | Event |
|---|---|
| 2024-03-19 | Initial commit included `.env` file containing real API keys |
| 2024-03-19 | Second commit deleted `.env` from working tree, but git history retained the file |
| 2026-03-09 19:30 | Repository converted from private to public for open-source contributions |
| 2026-03-09 19:35 | Security scan detected exposed keys in git history |
| 2026-03-09 19:36 | Old API keys (OpenAI, UPbit access/secret) revoked by owner |
| 2026-03-09 19:38 | `git filter-repo` used to purge `.env` from all commits in history |
| 2026-03-09 19:38 | Force-pushed clean history to GitHub (`git push origin main --force`) |
| 2026-03-09 19:40 | Personal information (email address, physical address) removed from committed docs |
| 2026-03-09 19:46 | New API keys issued for both UPbit and OpenAI; stored in `.env` (gitignored) |

---

## Remediation Steps

### 1. Credential Revocation
- UPbit API keys revoked via the UPbit Pro dashboard.
- OpenAI API key revoked via the OpenAI platform settings.

### 2. Git History Purge
```bash
# Remove .env from all historical commits
git filter-repo --path .env --invert-paths --force

# Force-push clean history to remote
git push origin main --force
```

### 3. `.gitignore` Verification
Confirmed that `.env` is excluded in `.gitignore`:
```
.env
```

### 4. New Key Issuance
- New UPbit API keys issued with minimum required permissions (no withdrawal enabled).
- New OpenAI API key issued and stored only in the local `.env` file.

### 5. Personal Information Removal
- Real email addresses, phone numbers, and physical addresses removed from all committed documentation files.
- Replaced with generic placeholders (e.g., `contact@example.com`).

---

## Prevention Measures

| Measure | Status |
|---|---|
| Never commit `.env` files | `.gitignore` enforced |
| Use `os.getenv()` in code | Already implemented throughout codebase |
| Use GitHub Actions Secrets for CI/CD | Planned for Phase 8 |
| Provide `.env.example` with placeholders only | Confirmed — no real values |
| Add `.gitignore` patterns for personal files | Applied |
| Pre-commit hook to block `.env` commits | Recommended for future setup |

---

## Lessons Learned

1. **Secrets must never enter version control**, even temporarily. Use tools like `git-secrets` or `detect-secrets` as a pre-commit gate.
2. **History purging does not immediately protect secrets** — forks or caches may retain old commits. Always revoke credentials first, then clean history.
3. **Private repositories are not a security boundary.** Credentials in git history remain at risk when repositories are later made public.
4. Removing a file in a subsequent commit does **not** erase it from git history.

---

## References

- [git-filter-repo documentation](https://github.com/newren/git-filter-repo)
- [GitHub: Removing sensitive data from a repository](https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/removing-sensitive-data-from-a-repository)
- [UPbit Open API](https://docs.upbit.com/)
- [OpenAI API Key Management](https://platform.openai.com/api-keys)

---

*Document created: 2026-03-09 | Maintainer: maiupbit project team*
