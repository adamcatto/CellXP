from fastapi import APIRouter

router = APIRouter(prefix="/binding", tags=["binding"])

@router.get("")
def index():
    return {"status": "ok", "router": "binding"}
