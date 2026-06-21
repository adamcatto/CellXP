from fastapi import FastAPI

from cellxp.api.routers import (
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
app.include_router(health.router)

for router in [
    sessions.router, runs.router, chat.router, artifacts.router, variants.router, gwas.router,
    crispr.router, annotations.router, binding.router, structure.router, visualizations.router,
]:
    app.include_router(router, prefix="/api/v1")
