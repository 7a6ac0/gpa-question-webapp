from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from src.api.routes import categories, health, questions, sessions

app = FastAPI(title="GPA Question Parser", version="0.1.0")

app.include_router(health.router, prefix="/api", tags=["health"])
app.include_router(categories.router, prefix="/api", tags=["categories"])
app.include_router(questions.router, prefix="/api", tags=["questions"])
app.include_router(sessions.router, prefix="/api", tags=["sessions"])

app.mount("/static", StaticFiles(directory="src/static"), name="static")

templates = Jinja2Templates(directory="src/templates")


@app.get("/")
def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


@app.get("/practice/{session_id}")
def practice_page(request: Request, session_id: str):
    return templates.TemplateResponse(
        "practice.html", {"request": request, "session_id": session_id}
    )


@app.get("/results/{session_id}")
def results_page(request: Request, session_id: str):
    return templates.TemplateResponse(
        "results.html", {"request": request, "session_id": session_id}
    )
