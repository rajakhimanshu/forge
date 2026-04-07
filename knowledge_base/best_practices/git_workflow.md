# Git Workflow Best Practices

## Branch Naming
- main: stable production code only
- dev: active development, merge features here
- feature/name: one branch per feature
- fix/bug-name: bug fix branches

## Commit Message Format
feat: new feature
fix: bug fix
chore: dependencies or config
docs: documentation changes

## Workflow
1. Create feature branch from dev
2. Make small commits every 45-60 minutes
3. Push branch to remote
4. Merge to dev when complete
5. Merge dev to main only when fully tested
