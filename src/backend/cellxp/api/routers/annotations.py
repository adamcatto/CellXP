from fastapi import APIRouter

router = APIRouter(prefix="/annotations", tags=["annotations"])

@router.get("")
def index():
    return {"status": "ok", "router": "annotations"}
