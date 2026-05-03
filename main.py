"""CivicLens AI — Election Process Education Assistant

Interactive AI-powered platform that helps users understand election processes,
timelines, and civic participation steps through conversational AI.
"""
import os
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from api.routes import router

BASE = Path(__file__).resolve().parent

app = FastAPI(
    title="CivicLens AI",
    description="Election Process Education Assistant powered by Gemini AI",
    version="1.0.0",
)

allowed_origins = os.getenv("ALLOWED_ORIGINS", "").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in allowed_origins if o.strip()],
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)

app.include_router(router, prefix="/api")
app.mount("/static", StaticFiles(directory=BASE / "static"), name="static")


@app.get("/")
async def root():
    return FileResponse(BASE / "static" / "index.html")
