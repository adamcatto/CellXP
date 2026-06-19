from fastapi import APIRouter

router = APIRouter(prefix="/artifacts", tags=["artifacts"])

@router.get("")
def index():
    return {"status": "ok", "router": "artifacts"}
