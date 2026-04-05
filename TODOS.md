# Future Work

## Auto-download Scraper
When ready, implement `src/ingestion/scraper.py` to automatically fetch question PDFs
from the PCC website AJAX endpoint (`/readQuestionForPublic`). This was intentionally
deferred because manually downloading ~14 PDF files is simpler and more reliable than
maintaining a scraper against a government website that may block automated requests.

## ~~Cross-session Weakness Analysis~~ (Done)
Implemented: `/weakness` page aggregates performance across sessions by `anonymous_id`,
shows per-category accuracy sorted worst-first, and offers "針對弱項練習" to auto-select
weak categories. Deferred: SM-2 spaced repetition with exam date countdown.
