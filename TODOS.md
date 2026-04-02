# Future Work

## Auto-download Scraper
When ready, implement `src/ingestion/scraper.py` to automatically fetch question PDFs
from the PCC website AJAX endpoint (`/readQuestionForPublic`). This was intentionally
deferred because manually downloading ~14 PDF files is simpler and more reliable than
maintaining a scraper against a government website that may block automated requests.

## Cross-session Weakness Analysis
Use the `anonymous_id` field in `practice_sessions` to track user performance across
sessions. Build a weakness analysis feature that identifies categories where the user
consistently scores low, and prioritize those in future practice sessions.
Potential approach: spaced repetition (SM-2 algorithm) with exam date countdown.
