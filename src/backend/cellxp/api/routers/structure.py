from fastapi import APIRouter

router = APIRouter(prefix="/structure", tags=["structure"])

@router.get("")
def index():
    return {"status": "ok", "router": "structure"}
