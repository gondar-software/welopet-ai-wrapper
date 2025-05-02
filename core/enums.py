from enum import Enum

class GPUType(Enum):
    RTX4090 = "NVIDIA GeForce RTX 4090"
    RTXA6000 = "NVIDIA RTX A6000"

class PodState(Enum):
    Initializing = 0
    Starting = 1
    Free = 2
    Processing = 3
    Completed = 4
    Terminated = 5

class WorkflowType(Enum):
    Ghibli = 1
    Snoopy = 2
    MagicVideo = 3
    _3DCartoon = 4
    Labubu = 5

class VolumeType(Enum):
    EasyControl = 0
    MagicVideo = 1

class OutputState(Enum):
    Completed = 2
    Failed = 3

class PodManagerState(Enum):
    Running = 0
    Stopped = 1