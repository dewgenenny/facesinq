# Facesinq Code Review Notes

## Observations
- The application is a Flask service that integrates with Slack to run colleague recognition quizzes. It uses SQLAlchemy for persistence and stores encrypted user information.
- Multiple modules handle Slack events, quiz management, database helpers and utilities.
- The repository currently contains minimal documentation: the `README.md` only states "Here we go!".
- `requirements.txt` is encoded in UTF‑16 with a BOM. This can break `pip install -r requirements.txt` because of the null bytes.
- `models.py` expects an `ENCRYPTION_KEY` environment variable when imported. If it is missing, the application fails on startup.
- Some code sections show redundancy or potential cleanup opportunities (for example, nested `if __name__ == '__main__'` in `app.py`).
- Several helper methods print debug information but lack proper logging or error handling.

## Next Steps
1. **Convert `requirements.txt` to UTF‑8** so that installation via `pip` works consistently.
2. **Expand `README.md`** with setup instructions, environment variables, database initialization and how to configure Slack credentials.
3. **Validate environment variables** like `ENCRYPTION_KEY` at startup and provide a clear error message if they are missing.
4. **Refactor main application entry point** to remove redundant `if __name__ == '__main__'` nesting.
5. **Implement tests** for database helpers and Slack event handlers to guard against regressions.
6. **Improve logging** using Python's `logging` module instead of plain `print` statements.
7. **Add contribution guidelines** and describe how to run the app locally (including the `Procfile` for deployment).

These steps should make the project easier to install, develop and extend.
