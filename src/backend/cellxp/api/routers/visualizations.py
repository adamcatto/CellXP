from fastapi import APIRouter

router = APIRouter(prefix="/visualizations", tags=["visualizations"])

@router.get("")
def index():
    return {"status": "ok", "router": "visualizations"}
