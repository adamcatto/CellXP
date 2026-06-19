from fastapi import APIRouter

router = APIRouter(prefix="/gwas", tags=["gwas"])

@router.get("")
def index():
    return {"status": "ok", "router": "gwas"}
