"""
The web application.

This file does one thing: assemble the application from its parts. The endpoints live in
app/api/endpoints/, the start-up work in app/core/application_lifespan.py, and the request
and response shapes in app/schemas/.
"""

import logging

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api.error_handlers import register_error_handlers
from app.api.router import api_router
from app.core.application_lifespan import application_lifespan
from app.core.settings import BACKEND_DIRECTORY, settings

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%H:%M:%S",
)

POLICY_PDF_URL_PREFIX = "/api/v1/hcs01/policies/pdf"

# The browser sends credentials with its requests, so the allowed origins have to be
# listed explicitly. A wildcard would silently stop those requests from working.
ALLOWED_BROWSER_ORIGINS = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:8080",
    "http://127.0.0.1:8080",
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:8000",
    "http://127.0.0.1:8000",

]


def create_application() -> FastAPI:
    """Build the application, ready to serve."""
    application = FastAPI(
        title="Bayan HR — Policy & Leave Concierge API",
        description=(
            "A bilingual English and Arabic HR assistant for HC Services staff. Answers "
            "from the company's policy documents and the employee's own HR record, and "
            "declines rather than guessing when the evidence does not support an answer."
        ),
        version="1.0.0",
        lifespan=application_lifespan,
    )

    application.add_middleware(
        CORSMiddleware,
        allow_origins=ALLOWED_BROWSER_ORIGINS,
        allow_origin_regex=r"^https?://(localhost|127\.0\.0\.1)(:[0-9]+)?$",
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    application.include_router(api_router)
    register_error_handlers(application)
    _serve_policy_pdfs(application)

    return application


def _serve_policy_pdfs(application: FastAPI) -> None:
    """
    Serve the policy PDFs themselves.

    Citations link straight to a page of one of these, so this path must not change.
    """
    pdf_directory = BACKEND_DIRECTORY / "data" / "policies_pdf"
    pdf_directory.mkdir(parents=True, exist_ok=True)
    application.mount(
        POLICY_PDF_URL_PREFIX,
        StaticFiles(directory=str(pdf_directory)),
        name="policy_pdfs",
    )


app = create_application()


if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=True,
        log_level="info",
    )
