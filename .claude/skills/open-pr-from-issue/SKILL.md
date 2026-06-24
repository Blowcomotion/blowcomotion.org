---
name: open-pr-from-issue
description: Use when the user pastes a GitHub issue number or URL from the blowcomotion.org repository to implement and open a PR for that issue
---

# Open PR From Issue

Fetch the issue, create a branch, implement, review, and open a PR — all in one flow.

**Announce at start:** "Using open-pr-from-issue to implement #<num>."

## Step 1: Parse and Fetch

Accept bare number (`223`) or full URL. Extract the number, then:

```bash
gh issue view <num> --repo Blowcomotion/blowcomotion.org --json number,title,body,labels,comments
```

## Step 2: Branch Off development

```bash
git checkout development && git pull
git checkout -b feature/issue-<num>-<slug>
# slug: title lowercased, spaces→hyphens, max 40 chars, strip special chars
```

## Step 3: Classify the Issue

Scan labels and title/body for these signals:

| Signal | Size |
|--------|------|
| Label `bug` or `Low Priority` | small |
| Label `enhancement` or `Medium Priority` | medium |
| Label `High Priority`, `security`, multiple subsystems | large |
| Keywords: auth, login, password, permission, reCAPTCHA, honeypot, captcha, payment, token | security-sensitive (any size) |

When in doubt, classify up (medium → large, not down).

## Step 4: Implement

- For non-trivial issues, invoke `superpowers:brainstorming` before coding
- Follow existing code patterns; run tests if available
- Keep changes minimal — only what the issue requires

## Step 5: Run Reviews (after staging, before committing)

Check scope first: `git diff --stat HEAD`

| Issue classification | superpowers:requesting-code-review | security-review | ponytail-review | simplify |
|---------------------|------------------------------------|-----------------|-----------------|----------|
| Small bug fix | always | if security-sensitive | — | — |
| Medium feature | always | if security-sensitive | always | — |
| Large feature/refactor | always | always | always | always |
| Any security-sensitive | always | always | if medium+ | if large |

Run each selected review in order. Fix all Critical and Important findings before moving on.

## Step 6: Commit and PR

```bash
# Commit — GPG signed, conventional prefix, no emoji
git add <specific files>
git commit -S -m "fix: <title>" # or feat:, chore:, etc.

# Push and open PR targeting development
git push -u origin feature/issue-<num>-<slug>
gh pr create \
  --base development \
  --title "<conventional-prefix>: <issue title>" \
  --body "$(cat <<'EOF'
Closes #<num>

## Summary
- <bullet points>

## Test plan
- [ ] <manual test steps>
EOF
)"
```

## Commit Rules (project conventions)

- GPG-sign all commits (`git commit -S`)
- No emoji anywhere in commit or PR body
- No `Co-Authored-By:` lines
- Target branch: `development` (never `main`)
- Commit prefix: `fix:` for bugs, `feat:` for features, `chore:` for cleanup

## Red Flags

**Never:**
- Skip `superpowers:requesting-code-review` — it is always required
- Commit before fixing Critical or Important review findings
- Target `main` instead of `development`
- Add emoji or `Co-Authored-By` to commits

**Always:**
- GPG-sign commits
- Scan for security-sensitive keywords even on small issues
- Fix all Critical/Important findings before opening the PR
