import json
import uuid

from typing import List, Optional, Dict, Literal, Union

from enum import Enum
from pydantic import BaseModel, ConfigDict, Field, field_validator, constr, StrictInt, StrictFloat

ArtifactType = Enum('ArtifactType', ['DIFF', 'COMPARE', 'STATS', 'BADGE', 'SOFTWARE'])

# Must be kept in sync with the cluster_service ENUM in docker/tables.sql
class ClusterService(str, Enum):
    CARBONDB = 'CarbonDB'
    ECO_CI = 'Eco CI'
    SCENARIO_RUNNER = 'ScenarioRunner'
    POWER_HOG = 'Power HOG'

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

### System Logs

class SystemLogDelete(BaseModel):
    log_id: int
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
    commit_hash: Optional[str] = None
    machine_id: int
    schedule_mode: str
    usage_scenario_variables: Optional[Dict[str, str]] = None
    category_ids: Optional[List[int]] = None
    carbon_simulation: Optional[Union[List[StrictInt], str]] = None

    model_config = ConfigDict(extra='forbid')

    # mode='before' so that we see the raw input. Otherwise pydantic lax mode would coerce true -> 1 or 1.0 -> 1
    # Normalizes to None | list[int] | str (UUID)
    @field_validator('carbon_simulation', mode='before')
    @classmethod
    def parse_carbon_simulation(cls, value):
        if value is None:
            return None

        if isinstance(value, bool):
            raise ValueError('Carbon simulation must be an integer, list of integers, or UUID string')

        if isinstance(value, int):
            return [value]

        if isinstance(value, list):
            if all(isinstance(item, int) and not isinstance(item, bool) for item in value):
                return value
            raise ValueError('Carbon simulation list must contain only integers')

        if isinstance(value, str):
            value = value.strip()
            if value == '':
                return None

            try:
                parsed_value = json.loads(value)
            except json.JSONDecodeError:
                try:
                    return str(uuid.UUID(value))
                except ValueError as exc:
                    raise ValueError('Carbon simulation must be an integer, list of integers, or UUID string') from exc

            return cls.parse_carbon_simulation(parsed_value)

        raise ValueError('Carbon simulation must be an integer, list of integers, or UUID string')

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
    run_id: str
    source: str
    label: str
    duration_us: int
    filter_type: Optional[str] = 'machine.ci'
    filter_project: Optional[str] = 'CI/CD'
    filter_machine: Optional[str] = 'unknown'
    filter_tags: Optional[list] = Field(default_factory=list) # never do a reference object as default as it will be shared
    lat: Optional[str] = None
    lon: Optional[str] = None
    city: Optional[str] = None
    carbon_intensity_g: Optional[int] = None
    ip: Optional[str] = None
    note: Optional[constr(max_length=1024)] = None
    os_name: Optional[str] = None
    cpu_arch: Optional[str] = None
    job_id: Optional[str] = None
    version: Optional[str] = None

    # Empty string will not trigger error on their own
    # filter_* have defaults, but are NOT NULL in the DB. So an explicitly sent empty value must be rejected and not turned into None
    # workflow (v3) / workflow_id and workflow_name (v4) are only defined in the subclasses, hence check_fields=False
    @field_validator('repo', 'branch', 'cpu', 'commit_hash', 'run_id', 'source', 'label', 'filter_type', 'filter_project', 'filter_machine',
                     'workflow', 'workflow_id', 'workflow_name', check_fields=False)
    @classmethod
    def check_not_empty(cls, value, data):
        if not value or value.strip() == '':
            raise ValueError(f"{data.field_name} must be set and non-empty")
        return value

    @field_validator('lat', 'lon', 'city', 'ip', 'note')
    @classmethod
    def empty_str_to_none(cls, value, _):
        if not value or value.strip() == '':
            return None
        return value

    @field_validator('filter_tags')
    @classmethod
    def check_empty_elements(cls, value, data):
        if any(not item or item.strip() == '' for item in value):
            raise ValueError(f"{data.field_name} contains empty elements")
        return value

class CI_MeasurementV3(CI_MeasurementBase):
    """
    v3 CI measurement model. Deprecated, use CI_MeasurementV4.
    Carbon is submitted as one total value (carbon_ug). It is not stored as such, but split up
    into operational and embodied carbon by api/eco_ci.py::split_carbon_ug
    """
    workflow: str
    workflow_name: Optional[str] = None
    carbon_ug: Optional[int] = None

    model_config = ConfigDict(extra='forbid')

    @property
    def workflow_id(self):
        return self.workflow


class CI_MeasurementV4(CI_MeasurementBase):
    """
    v4 CI measurement model.
    Carbon is submitted split into operational and embodied carbon.
    Numeric values must be sent as JSON numbers, not as strings.
    """
    energy_uj: StrictInt
    cpu_util_avg: StrictFloat | StrictInt
    duration_us: StrictInt
    workflow_id: str
    workflow_name: str
    operational_carbon_ug: Optional[StrictInt] = None
    embodied_carbon_ug: Optional[StrictInt] = None

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
    embodied_carbon_ug: int # mandatory, as it cannot be derived later. Is in ug
    operational_carbon_ug: Optional[int] = None # is in ug. If not transmitted it is calculated from carbon_intensity_g, now or once backfilled
    carbon_intensity_g: Optional[int] = None # Will be backfilled if not transmitted
    ip: Optional[str] = None  # Will be populated with the connecting IP if not transmitted

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
