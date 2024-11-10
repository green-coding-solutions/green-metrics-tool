from pydantic import BaseModel, ConfigDict

### Software Add

class Software(BaseModel):
    name: str
    url: str
    email: str
    filename: str
    branch: str
    machine_id: int
    schedule_mode: str

    model_config = ConfigDict(extra='forbid')
