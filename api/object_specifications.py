from pydantic import BaseModel, ConfigDict, Field, field_validator, constr
from typing import Optional, Dict, Literal

from fastapi.exceptions import RequestValidationError

### Jobs

class JobChange(BaseModel):
    job_id: int
    action: Literal['cancel']

    model_config = ConfigDict(extra='forbid')

### Software Add

class Software(BaseModel):
    name: str
    image_url: Optional[str] = None
    repo_url: str
    email: Optional[str] = None
    filename: str
    branch: str
    machine_id: int
    schedule_mode: str
    usage_scenario_variables: Optional[Dict[str, str]] = None

    model_config = ConfigDict(extra='forbid')

### User Settings Update

class UserSetting(BaseModel):
    name: str
    value: str | list | bool

    model_config = ConfigDict(extra='forbid')

### Eco CI
# pylint: disable=invalid-name
class CI_MeasurementBase(BaseModel):
    energy_uj: int
    repo: str
    branch: str
    cpu: str
    cpu_util_avg: float
    commit_hash: str
    workflow: str   # workflow_id, change when we make API change of workflow_name being mandatory
    run_id: str
    source: str
    label: str
    duration_us: int
    workflow_name: str = None
    filter_type: Optional[str] = 'machine.ci'
    filter_project: Optional[str] = 'CI/CD'
    filter_machine: Optional[str] = 'unknown'
    filter_tags: Optional[list] = Field(default_factory=list) # never do a reference object as default as it will be shared
    lat: Optional[str] = ''
    lon: Optional[str] = ''
    city: Optional[str] = ''
    carbon_intensity_g: Optional[int] = None
    carbon_ug: Optional[int] = None
    ip: Optional[str] = None
    note: Optional[constr(max_length=1024)] = None


    # Empty string will not trigger error on their own
    @field_validator('repo', 'branch', 'cpu', 'commit_hash', 'workflow', 'run_id', 'source', 'label')
    @classmethod
    def check_not_empty(cls, values, data):
        if not values or values == '':
            raise RequestValidationError(f"{data.field_name} must be set and not empty")
        return values

    @field_validator('filter_type', 'filter_project', 'filter_machine', 'ip')
    @classmethod
    def empty_str_to_none(cls, values, _):
        if not values or values.strip() == '':
            return None
        return values

    @field_validator('filter_tags')
    @classmethod
    def check_empty_elements(cls, value):
        if any(not item or item.strip() == '' for item in value):
            raise ValueError("The list contains empty elements.")
        return value


class CI_Measurement(CI_MeasurementBase):
    """
    v2 CI measurement model.
    This keeps backward compatibility with existing EcoCI clients.
    """
    model_config = ConfigDict(extra='forbid')


class CI_MeasurementV3(CI_MeasurementBase):
    """
    v3 CI measurement model.
    Adds new optional fields; for now they are parsed but not stored.
    """
    os_name: Optional[str] = None
    cpu_arch: Optional[str] = None
    job_id: Optional[str] = None

    model_config = ConfigDict(extra='forbid')
