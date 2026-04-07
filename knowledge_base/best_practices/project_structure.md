# Python Project Structure Best Practices

## Standard Layout
project/
  src/         # main source code
  tests/       # test files
  docs/        # documentation
  scripts/     # utility scripts
  .env         # secrets, never commit
  requirements.txt  # pinned versions
  README.md    # setup instructions

## Key Rules
- Never commit .env files
- Pin all package versions in requirements.txt
- One file = one responsibility
- __init__.py in every Python module folder
