from pydantic import BaseModel

class ServiceResult(BaseModel):
    service: str
    payload: dict
    provenance: list[str] = []
