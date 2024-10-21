from typing import List, Dict, Optional
from pydantic import BaseModel, ConfigDict, field_validator, Field
from fastapi.exceptions import RequestValidationError


###### HOG

class HogMeasurement(BaseModel):
    time: int
    data: str
    settings: str
    machine_uuid: str
    row_id: Optional[int] = -1 # we use this only for debugging

    model_config = ConfigDict(extra='forbid')


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


### Eco-CI




# pylint: disable=invalid-name
class CI_Measurement_Old(BaseModel):
    energy_value: int
    energy_unit: str
    repo: str
    branch: str
    cpu: str
    cpu_util_avg: float
    commit_hash: str
    workflow: str   # workflow_id, change when we make API change of workflow_name being mandatory
    run_id: str
    source: str
    label: str
    duration: int
    workflow_name: str = None
    cb_company_uuid: Optional[str] = '' # will just be ignored as of now
    cb_project_uuid: Optional[str] = '' # will just be ignored as of now
    cb_machine_uuid: Optional[str] = '' # will just be ignored as of now
    lat: Optional[str] = ''
    lon: Optional[str] = ''
    city: Optional[str] = ''
    co2i: Optional[str] = ''
    co2eq: Optional[str] = ''
    project_id: Optional[str] = '' # legacy. Is ignored

    model_config = ConfigDict(extra='forbid')

    # Empty string will not trigger error on their own
    @field_validator('repo', 'branch', 'cpu', 'commit_hash', 'workflow', 'run_id', 'source', 'label')
    @classmethod
    def check_not_empty(cls, values, data):
        if not values or values == '':
            raise RequestValidationError(f"{data.field_name} must be set and not empty")
        return values


# pylint: disable=invalid-name
class CI_Measurement(BaseModel):
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

    model_config = ConfigDict(extra='forbid')


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
