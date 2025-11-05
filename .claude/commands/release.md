# Pre-Push Documentation Check

Review and update all project documentation before pushing:

## Step 1: Analyze Recent Changes

Run `git diff origin/main` to see what's changed since last push.

## Step 2: Documentation Audit

Check each file and provide status:

### README.md

- [ ] Project description accurate?
- [ ] Installation steps current?
- [ ] Usage examples reflect new features?
- [ ] Dependencies up to date?

### CHANGELOG.md

- [ ] New entry added under "Unreleased"?
- [ ] Entry format: `- [TYPE] Description`
- [ ] All significant changes documented?

### CLAUDE.md

- [ ] New patterns/conventions documented?
- [ ] Project structure updated if changed?
- [ ] New commands or tools noted?

### Code Documentation

- [ ] New functions documented?
- [ ] Complex logic has comments?
- [ ] New modules have docstrings?

## Step 3: Make Updates

For any incomplete items above, update the relevant files now.

## Step 4: Verification

After updates, show me:

1. Summary of documentation changes made
2. Confirmation all items checked
3. Statement: "✓ Documentation complete. Safe to push."

Only then may I proceed with `git push`.
