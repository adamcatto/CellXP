from fastapi import FastAPI
from cellxp.api.routers import health, chat, runs, artifacts, variants, gwas, crispr, annotations, binding, structure, visualizations

app = FastAPI(title="CellXP API", version="0.1.0")

for router in [
    health.router, chat.router, runs.router, artifacts.router, variants.router, gwas.router,
    crispr.router, annotations.router, binding.router, structure.router, visualizations.router,
]:
    app.include_router(router)
