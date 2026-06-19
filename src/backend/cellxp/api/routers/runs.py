from fastapi import APIRouter

router = APIRouter(prefix="/runs", tags=["runs"])

@router.get("")
def index():
    return {"status": "ok", "router": "runs"}
