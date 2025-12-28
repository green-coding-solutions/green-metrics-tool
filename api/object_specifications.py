from pydantic import BaseModel, ConfigDict, Field, field_validator, constr
from typing import List, Optional, Dict, Literal, Union

from fastapi import HTTPException

### Run
class RunChange(BaseModel):
    archived: Optional[bool] = None
    note: Optional[str] = None
    public: Optional[bool] = None

    model_config = ConfigDict(extra='forbid')

### Jobs

class JobChange(BaseModel):
    job_id: int
    action: Literal['cancel']

    model_config = ConfigDict(extra='forbid')

### Watchlist

class WatchlistChange(BaseModel):
    watchlist_id: int
    action: Literal['delete']

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
            raise HTTPException(status_code=422, detail=f"{data.field_name} must be set and not empty")
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
    version: Optional[str] = None

    model_config = ConfigDict(extra='forbid')

###### HOG

class HogMeasurement(BaseModel):
    time: int
    data: str
    settings: str
    machine_uuid: str
    row_id: Optional[int] = -1 # we use this only for debugging

    model_config = ConfigDict(extra='forbid')


class SimplifiedMeasurement(BaseModel):
    machine_uuid: str
    timestamp: int
    timezone: str
    grid_intensity_cog: Optional[float] = None
    combined_energy_mj: int
    cpu_energy_mj: int
    gpu_energy_mj: int
    ane_energy_mj: int
    energy_impact: int
    hw_model: str
    elapsed_ns: int
    embodied_carbon_g: Optional[float] = 0.0
    operational_carbon_g: Optional[float] = 0.0
    thermal_pressure: str
    top_processes: List[Dict[str, Union[str, float, int]]]


class Task(BaseModel):
    # We need to set the optional to a value as otherwise the key is required in the input
    # https://docs.pydantic.dev/latest/migration/#required-optional-and-nullable-fields
    name: str
    cputime_ns: int
    timer_wakeups: List
    diskio_bytesread: Optional[int] = 0
    diskio_byteswritten: Optional[int] = 0
    packets_received: int
    packets_sent: int
    bytes_received: int
    bytes_sent: int
    energy_impact: float

    model_config = ConfigDict(extra='forbid')


class Coalition(BaseModel):
    name: str
    cputime_ns: int
    diskio_bytesread: int = 0
    diskio_byteswritten: int = 0
    energy_impact: float
    tasks: List[Task]

    model_config = ConfigDict(extra='forbid')

class Processor(BaseModel):
    # https://docs.pydantic.dev/latest/migration/#required-optional-and-nullable-fields
    clusters: Optional[List] = None
    cpu_power_zones_engaged: Optional[float] = None
    cpu_energy: Optional[int] = None
    cpu_power: Optional[float] = None
    gpu_energy: Optional[int] = None
    gpu_power: Optional[float] = None
    ane_energy: Optional[int] = None
    ane_power: Optional[float] = None
    combined_power: Optional[float] = None
    package_joules: Optional[float] = None
    cpu_joules: Optional[float] = None
    igpu_watts: Optional[float] = None

    model_config = ConfigDict(extra='forbid')

class GPU(BaseModel):
    gpu_energy: Optional[int] = None

    model_config = ConfigDict(extra='forbid')


class Measurement(BaseModel):
    is_delta: bool
    elapsed_ns: int
    timestamp: int
    coalitions: List[Coalition]
    all_tasks: Dict
    network: Optional[Dict] = None # network is optional when system is in flight mode / network turned off
    disk: Optional[Dict] = None # No idea what system would not have a disk but we are seeing this in production
    interrupts: List
    processor: Processor
    thermal_pressure: str
    sfi: Dict
    gpu: Optional[GPU] = None

    model_config = ConfigDict(extra='forbid')




### CarbonDB

class EnergyData(BaseModel):
    tags: Optional[list] = Field(default_factory=list) # never do a reference object as default as it will be shared
    project: str
    machine: str
    type: str
    time: int # value is in us as UTC timestamp
    energy_uj: int # is in uJ
    carbon_intensity_g: Optional[int] = None # Will be populated if not transmitted, so we never have NULL in DB
    ip: Optional[str] = None  # Will be populated if not transmitted, so we never have NULL in DB

    model_config = ConfigDict(extra='forbid')


    @field_validator('ip', 'project', 'machine','type')
    @classmethod
    def empty_str_to_none(cls, values, _):
        if not values or values.strip() == '':
            raise ValueError('Value is empty')
        return values

    @field_validator('tags')
    @classmethod
    def check_empty_elements(cls, value):
        if any(not item or item.strip() == '' for item in value):
            raise ValueError("The list contains empty elements.")
        return value
