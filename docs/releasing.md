# How to Release Awaaz

This explains how to release a new version of Awaaz in simple steps.

---

## Branches

- **`main`** — production-ready code. Every release comes from here.
- **`dev`** — where all finished features land before release.
- **`feature/*` or `bugfix/*`** — individual work branches. Always branch off `dev`, never `main`.
- **`release/x.x.x`** — a short-lived branch just to bump the version number before merging to `main`.

---

## Normal Development Flow

```
feature/my-thing  →  PR  →  dev  →  PR  →  main
```

1. Create a branch from `dev`
2. Do your work
3. Open a PR targeting `dev`
4. Merge it

---

## How to Release a New Version

### Step 1 — Create a release branch from `main`

```powershell
git checkout main
git pull
git checkout -b release/1.0.3
```

### Step 2 — Bump the version using the script

```powershell
pwsh -File .\scripts\bump-version.ps1 -Version 1.0.3 -Commit
git push -u origin release/1.0.3
```

This updates the version number in `pyproject.toml`, `frontend/package.json`, and `src/awaaz/main.py` and commits it.

### Step 3 — Open a PR to `main`

```powershell
gh pr create --base main --head release/1.0.3 --title "release: v1.0.3"
```

### Step 4 — Merge the PR

Use a **regular merge commit** on GitHub (not squash).

### Step 5 — Tag the release

```powershell
git checkout main
git pull
git tag -a v1.0.3 -m "Release v1.0.3"
git push origin v1.0.3
```

That's it. GitHub Actions picks up the tag and automatically publishes the GitHub Release.

### Step 6 — Sync `dev` back from `main`

After every release, `dev` will be behind `main` (it's missing the version bump commit). Always merge `main` back into `dev`:

```powershell
git checkout dev
git merge origin/main --no-edit
git push
```

---

## What Happens Automatically

Once you push the tag, the `release.yml` GitHub Actions workflow runs. It:
1. Runs all tests
2. If tests pass → creates the GitHub Release with auto-generated notes

You do not need to create the release manually on GitHub.

---

## Rules

- ❌ Never push directly to `main` or `dev`
- ❌ Never create the GitHub Release manually with `gh release create`
- ✅ Always go through a PR
- ✅ Use **squash merge** for feature/bugfix PRs
- ✅ Use **merge commit** for release PRs (`release/*` → `main`)
- ✅ Write a clear PR title — GitHub uses it in the auto-generated release notes

---

## Version Numbering

We follow [Semantic Versioning](https://semver.org):

| Change type | Example | When to use |
|---|---|---|
| Bug fix | `1.0.1` → `1.0.2` | Fixed something broken |
| New feature | `1.0.2` → `1.1.0` | Added something new |
| Breaking change | `1.1.0` → `2.0.0` | Changed something that breaks existing users |
