from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import os
from dotenv import load_dotenv

# Load environment variables early
load_dotenv()

from app.routes.upload import router as upload_router
from app.routes.auth_routes import router as auth_router
from app.routes.action_routes import router as action_router

app = FastAPI(title="FinSight AI")

# CORS (Allowed origins can be configured in production, keeping CORSMiddleware with credentials)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routes
app.include_router(upload_router)
app.include_router(auth_router)
app.include_router(action_router)

# Serve frontend static files
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
app.mount("/", StaticFiles(directory=BASE_DIR, html=True), name="static")