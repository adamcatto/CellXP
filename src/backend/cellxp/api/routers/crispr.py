from fastapi import APIRouter

router = APIRouter(prefix="/crispr", tags=["crispr"])

@router.get("")
def index():
    return {"status": "ok", "router": "crispr"}
