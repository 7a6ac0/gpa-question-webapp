# GPA Question Parser

政府採購法題庫練習平台 — FastAPI + PostgreSQL + Jinja2 模板 + LLM 解題解析。

## 常用指令

```bash
uv sync                            # 安裝依賴（建立 .venv）
docker-compose up                  # 啟動完整環境（DB + App）
alembic upgrade head               # 執行資料庫遷移
uvicorn src.api.main:app --reload  # 本地開發伺服器（:8000）
pytest tests/                      # 執行測試
python -m src.ingestion.cli parse --input ./data --category <id>  # 匯入題目
python -m src.ingestion.regulation_seeder  # 種子法規資料
```

## 架構

- `src/api/` — FastAPI 路由（`routes/`）與 Jinja2 模板頁面（`templates/`）
- `src/models/database.py` — SQLAlchemy ORM 模型（7 張表）
- `src/models/schemas.py` — Pydantic request/response schemas
- `src/services/llm.py` — OpenAI 相容 LLM 客戶端
- `src/ingestion/` — PDF/DOCX 解析、CLI 匯入、法規種子
- `alembic/` — 資料庫遷移
- `tests/` — pytest 測試（SQLite in-memory，不需 PostgreSQL）

## 關鍵慣例

- 題目以 `source_hash`（SHA256 of category + type + text）做冪等 upsert
- 軟刪除使用 `deleted_at` 欄位，不物理刪除
- 題型代碼：`"tf"`（是非題）、`"mc"`（選擇題）
- 答案格式：`"O"/"X"`（是非）、`"A"/"B"/"C"/"D"`（選擇）
- LLM 解釋以 `(question_id, selected_answer, cache_version)` 快取於 DB
- 所有 timestamp 使用 UTC `server_default=func.now()`

## 環境變數

- `DATABASE_URL` — PostgreSQL 連線字串
- `LLM_API_KEY` — LLM API 金鑰
- `LLM_BASE_URL` — LLM 端點（OpenAI 相容）
- `LLM_MODEL` — 模型名稱

## Skill routing

When the user's request matches an available skill, ALWAYS invoke it using the Skill
tool as your FIRST action. Do NOT answer directly, do NOT use other tools first.
The skill has specialized workflows that produce better results than ad-hoc answers.

Key routing rules:
- Product ideas, "is this worth building", brainstorming → invoke office-hours
- Bugs, errors, "why is this broken", 500 errors → invoke investigate
- Ship, deploy, push, create PR → invoke ship
- QA, test the site, find bugs → invoke qa
- Code review, check my diff → invoke review
- Update docs after shipping → invoke document-release
- Weekly retro → invoke retro
- Design system, brand → invoke design-consultation
- Visual audit, design polish → invoke design-review
- Architecture review → invoke plan-eng-review
- Save progress, checkpoint, resume → invoke checkpoint
- Code quality, health check → invoke health
