from fastapi import APIRouter

router = APIRouter(prefix="/chat", tags=["chat"])

@router.get("")
def index():
    return {"status": "ok", "router": "chat"}
