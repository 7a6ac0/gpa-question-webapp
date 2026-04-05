from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from src.api.routes import categories, explanations, health, questions, sessions

app = FastAPI(title="GPA Question Parser", version="0.1.0")

app.include_router(health.router, prefix="/api", tags=["health"])
app.include_router(categories.router, prefix="/api", tags=["categories"])
app.include_router(questions.router, prefix="/api", tags=["questions"])
app.include_router(sessions.router, prefix="/api", tags=["sessions"])
app.include_router(explanations.router, prefix="/api", tags=["explanations"])

app.mount("/static", StaticFiles(directory="src/static"), name="static")

templates = Jinja2Templates(directory="src/templates")


@app.get("/")
def index(request: Request):
    return templates.TemplateResponse(request, "index.html")


@app.get("/practice/{session_id}")
def practice_page(request: Request, session_id: str):
    return templates.TemplateResponse(
        request, "practice.html", {"session_id": session_id}
    )


@app.get("/results/{session_id}")
def results_page(request: Request, session_id: str):
    return templates.TemplateResponse(
        request, "results.html", {"session_id": session_id}
    )


@app.get("/weakness")
def weakness_page(request: Request):
    return templates.TemplateResponse(request, "weakness.html")
