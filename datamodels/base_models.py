from typing import Optional
from pydantic import BaseModel

class BaseRequest(BaseModel):
    time: str
    token: Optional[str]

class BaseResponse(BaseModel):
    time: str
