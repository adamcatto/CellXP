from fastapi import APIRouter

router = APIRouter(prefix="/variants", tags=["variants"])

@router.get("")
def index():
    return {"status": "ok", "router": "variants"}
