# GPA Question WebAPP

政府採購法題庫練習平台。從公共工程委員會 (PCC) 公開題庫 PDF 解析題目，提供線上練習、即時回饋，以及跨練習弱項追蹤。

## 功能

- **13 大類題庫** — 涵蓋政府採購法全生命週期，是非題與選擇題
- **隨機組卷** — 自選類別、題型與題數 (20/50/100/全部)，每次練習不重複
- **即時回饋** — 作答後立即顯示正確答案
- **弱項追蹤** — 跨練習統計各類別正確率，自動辨識弱項類別 (<80%)，一鍵針對弱項練習
- **題目匯入** — CLI 工具解析 PDF/DOCX 格式題庫，冪等 upsert 不重複

## 快速開始

### Docker (推薦)

```bash
# 1. 啟動
docker-compose up

# 2. 匯入題目
docker compose exec app python -m src.ingestion.cli parse --input ./data --category 1

# 3. 開啟瀏覽器
open http://localhost:8000
```

### 本地開發

```bash
# 安裝依賴
uv sync

# 準備 PostgreSQL (需先啟動)
export DATABASE_URL=postgresql://gpa:gpa_dev_password@localhost:5432/gpa_questions

# 執行資料庫遷移
uv run alembic upgrade head

# 匯入題目 (以第 1 類為例)
uv run python -m src.ingestion.cli parse --input ./data --category 1

# 啟動開發伺服器
uv run uvicorn src.api.main:app --reload
```

## 題目匯入

題庫來源為 PCC 公開的 PDF 檔案，放置於 `data/` 目錄。CLI 支援 PDF 與 DOCX 格式：

```bash
# 匯入單一類別
python -m src.ingestion.cli parse --input ./data --category 1

# 匯入結果會顯示：新增、更新、未變動、軟刪除的題目數量
```

13 個類別對應的 PDF 檔案，來源為[公共工程委員會採購專業人員題庫](https://web.pcc.gov.tw/psms/plrtqdm/questionPublic/indexReadQuestion)：

| 類別 | 主題 |
|------|------|
| 01 | 政府採購全生命週期概論 |
| 02 | 政府採購法之總則、招標及決標 |
| 03 | 政府採購法之履約管理及驗收 |
| 04 | 政府採購法之罰則及附則 |
| 05 | 政府採購法之爭議處理 |
| 06 | 底價及價格分析 |
| 07 | 投標須知及招標文件製作 |
| 08 | 採購契約 |
| 09 | 最有利標及評選優勝廠商 |
| 10 | 電子採購實務 |
| 11 | 工程及技術服務採購作業 |
| 12 | 財物及勞務採購作業 |
| 13 | 道德規範及違法處置 |

## 架構

```
src/
├── api/
│   ├── main.py              # FastAPI 應用程式入口
│   ├── routes/
│   │   ├── health.py        # 健康檢查
│   │   ├── categories.py    # 類別列表
│   │   ├── questions.py     # 隨機取題
│   │   └── sessions.py      # 練習 session 與成績
│   └── templates/           # Jinja2 前端頁面
├── models/
│   ├── database.py          # SQLAlchemy ORM (5 張表)
│   └── schemas.py           # Pydantic schemas
└── ingestion/
    ├── cli.py               # PDF/DOCX 匯入 CLI
    ├── pdf_parser.py         # PDF 解析
    └── doc_parser.py         # DOCX 解析
```

### API 端點

| 方法 | 路徑 | 說明 |
|------|------|------|
| GET | `/api/health` | 健康檢查 |
| GET | `/api/categories` | 所有類別與題數 |
| GET | `/api/questions` | 隨機取題 |
| POST | `/api/sessions` | 建立練習 session |
| POST | `/api/answer` | 提交答案 |
| GET | `/api/sessions/{id}/results` | 練習成績 |
| GET | `/api/weakness` | 跨 session 弱項分析 |

### 資料庫

5 張表：`categories`、`questions`、`practice_sessions`、`session_answers`、`session_categories`。

題目以 `source_hash` (SHA256 of category + type + text) 做冪等 upsert，刪除使用 `deleted_at` 軟刪除。

## 測試

```bash
pytest tests/
```

測試使用 SQLite in-memory，不需要 PostgreSQL。

## 技術棧

- **後端**: FastAPI, SQLAlchemy 2.0, Alembic
- **資料庫**: PostgreSQL 16
- **前端**: Jinja2 模板, HTMX, Vanilla JS
- **解析**: pdfplumber, python-docx
- **容器**: Docker, docker-compose
- **Python**: 3.11+

## License

MIT
