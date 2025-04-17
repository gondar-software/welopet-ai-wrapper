from enum import Enum

class GPUType(Enum):
    RTX4090 = "NVIDIA RTX 4090"
    RTXA6000 = "NVIDIA RTX A6000"

class PodState(Enum):
    Initializing = 0
    Starting = 1
    Free = 2
    Processing = 3

class WorkflowType(Enum):
    Ghibli = 0
    Snoopy = 1
    MagicVideo = 2