import os

from .core.pod_manager import *

manager1 = PodManager(
    os.getenv('VOLUME_ID1', ""),
    GPUType.RTXA6000,
    WorkflowType.Ghibli
)

