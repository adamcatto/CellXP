"""Optional development CORS for direct cross-origin API access."""

from __future__ import annotations

import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware


def configure_cors(app: FastAPI) -> None:
    """Attach CORS middleware when CELLXP_CORS_ORIGINS is set (comma-separated)."""
    raw = os.getenv("CELLXP_CORS_ORIGINS", "").strip()
    if not raw:
        return
    origins = [origin.strip() for origin in raw.split(",") if origin.strip()]
    if not origins:
        return
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
