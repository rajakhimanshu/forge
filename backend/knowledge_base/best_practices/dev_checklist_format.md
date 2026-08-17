# Development Checklist Format Standard

## Every task in a development blueprint must have:

1. Task number and specific name (not 'Create user model' — 'Create Student
   model with enrollment_number, branch, year, skills fields')

2. Time estimate (20 min, 1 hour, etc)

3. Exact file path (backend/models/Student.js not just 'user model')

4. WHAT THIS DOES — 1-2 sentences specific to the project

5. BEFORE YOU START — checkboxes of prerequisites

6. AI TOOL PROMPT — boxed, self-contained, includes project name and all
   field names. Must generate complete working file on first paste.

7. RUN THIS TO TEST — exact terminal command

8. SUCCESS CHECK — observable outcome (what you see in browser/terminal)

9. IF IT FAILS — specific error messages and exact fixes

10. COMMIT MESSAGE — conventional commit format

## Prompt Quality Rules
- Include project name in every prompt
- List every field name with data type
- Include validation rules explicitly
- End with: Show me the complete file. No explanation.
- Test command must be runnable immediately after saving the file
