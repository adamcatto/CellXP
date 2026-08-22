from fastapi import FastAPI

from cellxp.api.cors import configure_cors
from cellxp.api.routers import (
    ag_ui,
    annotations,
    artifacts,
    binding,
    chat,
    crispr,
    gwas,
    health,
    runs,
    sessions,
    structure,
    variants,
    visualizations,
)

app = FastAPI(title="CellXP API", version="0.1.0")
configure_cors(app)
app.include_router(health.router)
app.include_router(ag_ui.router)

for router in [
    sessions.router, runs.router, chat.router, artifacts.router, variants.router, gwas.router,
    crispr.router, annotations.router, binding.router, structure.router, visualizations.router,
]:
    app.include_router(router, prefix="/api/v1")
