from typing import List, Dict, Optional
from pydantic import BaseModel, ConfigDict

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
