import time
import uuid
import numpy as np
from queue import Queue
from threading import Thread, Lock
from collections import deque
from typing import Dict, List

from .constants import *
from .pod import *
from .enums import *
from .types import *
from .utils import *

class PodManager:
    def __init__(self, gpu_type: GPUType, volume_type: VolumeType):
        self.gpu_type = gpu_type
        self.volume_type = volume_type
        self.pods: List[Pod] = []
        self.queued_prompts = Queue[Prompt]()
        self.processing_prompts: Dict[str, Prompt] = {}
        self.completed_prompts: Dict[str, Prompt] = {}
        self.failed_prompts: Dict[str, Prompt] = {}
        self.threads: Dict[str, Thread] = {}
        self.lock = Lock()
        self.prompts_histories = deque([], maxlen=60)
        self.num_pods = 0
        self.state = PodManagerState.Running

        self.process_thread = Thread(target=self._process_loop, daemon=True)
        self.manage_thread = Thread(target=self._management_loop, daemon=True)
        self.process_thread.start()
        self.manage_thread.start()

    def get_state(self) -> Dict:
        """Get current state of the PodManager in a thread-safe manner."""
        with self.lock:
            pods_by_state = {
                PodState.Initializing: 0,
                PodState.Starting: 0,
                PodState.Free: 0,
                PodState.Processing: 0,
                PodState.Completed: 0,
                PodState.Terminated: 0
            }
            
            for pod in self.pods:
                pods_by_state[pod.state] += 1

            return {
                "state": self.state,
                "total_pod_num": len(self.pods),
                "ideal_pod_num": self.num_pods,
                "initializing_pod_num": pods_by_state[PodState.Initializing],
                "starting_pod_num": pods_by_state[PodState.Starting],
                "free_pod_num": pods_by_state[PodState.Free],
                "processing_pod_num": pods_by_state[PodState.Processing],
                "completed_pod_num": pods_by_state[PodState.Completed],
                "terminated_pod_num": pods_by_state[PodState.Terminated],
                "queued_prompt_num": self.queued_prompts.qsize(),
                "processing_prompt_num": len(self.processing_prompts),
                "completed_prompt_num": len(self.completed_prompts),
                "failed_prompt_num": len(self.failed_prompts),
            }

    def calc_num_pods(self) -> int:
        """Calculate the ideal number of pods based on current and historical load."""
        num_prompts = self.queued_prompts.qsize() + len(self.processing_prompts)
        self.prompts_histories.append(num_prompts)
        
        avg_load = np.average(self.prompts_histories)
        peak_load = max(self.prompts_histories)
        
        weighted_load = (avg_load * (100. - SCALING_SENSIVITY) / 100. + 
                       peak_load * (SCALING_SENSIVITY / 100.))
        
        return MIN_PODS + min(MAX_PODS, round(weighted_load * 1.2))

    def _management_loop(self):
        """Background thread for managing pod scaling."""
        while self.state == PodManagerState.Running:
            try:
                with self.lock:
                    self.num_pods = self.calc_num_pods()
                    
                    if self.num_pods > len(self.pods):
                        for _ in range(self.num_pods - len(self.pods)):
                            self.pods.append(Pod(self.gpu_type, self.volume_type))
                
                time.sleep(2)
            except Exception as e:
                print(f"Error in management loop: {e}")

    def _process_loop(self):
        """Background thread for processing prompts and managing pod lifecycle."""
        while self.state == PodManagerState.Running:
            try:
                with self.lock:
                    self._scale_down_pods()
                    self._process_pods()
                    self._process_prompts()
                
                time.sleep(SERVER_CHECK_DELAY / 1000)
            except Exception as e:
                print(f"Error in process loop: {e}")

    def _scale_down_pods(self):
        """Scale down pods if we have more than needed."""
        if len(self.pods) > self.num_pods:
            excess_count = len(self.pods) - self.num_pods
            terminated_count = 0
            
            for pod in sorted(self.pods, key=lambda x: (x.state != PodState.Free, x.count)):
                if terminated_count >= excess_count:
                    break
                if pod.state == PodState.Initializing or PodState.Starting:
                    pod.state = PodState.Terminated
                    terminated_count += 1
            
            for pod in sorted(self.pods, key=lambda x: (x.state != PodState.Free, x.count)):
                if terminated_count >= excess_count:
                    break
                if pod.state == PodState.Free and pod.count > FREE_MAX_REMAINS:
                    pod.state = PodState.Terminated
                    terminated_count += 1

    def _process_pods(self):
        """Process each pod's state"""
        pods_to_remove: list[Pod] = []
        
        for pod in self.pods:
            pod.count += 1
            
            if pod.state == PodState.Completed:
                self._handle_completed_pod(pod)
                continue
                
            if self._check_pod_timeout(pod):
                pods_to_remove.append(pod)
                continue
                
            if pod.state == PodState.Terminated:
                pods_to_remove.append(pod)
        
        for pod in pods_to_remove:
            if pod in self.pods:
                self.pods.remove(pod)
                pod.destroy()

    def _process_prompts(self):
        """Handle prompts and assign pod for them"""
        for pod in self.pods:
            if not self.queued_prompts.empty():
                if pod.state == PodState.Free:
                    self._assign_prompt_to_pod(pod)
                    continue

                if not pod.is_working and pod.init:
                    self._assign_prompt_to_pod(pod)

        while not self.queued_prompts.empty():
            pod = Pod(
                self.gpu_type,
                self.volume_type
            )
            self.pods.append(pod)
            self._assign_prompt_to_pod(pod)

    def _handle_completed_pod(self, pod: Pod):
        """Handle a pod that has completed processing."""
        prompt = pod.current_prompt
        if prompt.result.output_state == OutputState.Completed:
            self.completed_prompts[prompt.prompt_id] = prompt
        else:
            self.failed_prompts[prompt.prompt_id] = prompt
            
        self.processing_prompts.pop(prompt.prompt_id, None)
        pod.is_working = False
        pod.state = PodState.Free
        pod.count = 0

    def _assign_prompt_to_pod(self, pod: Pod):
        """Assign a queued prompt to a free pod."""
        prompt = self.queued_prompts.get()
        self.processing_prompts[prompt.prompt_id] = prompt
        pod.state = PodState.Processing
        pod.is_working = True
        thread = Thread(target=pod.queue_prompt, args=[prompt], daemon=True)
        thread.start()
        pod.count = 0

    def _check_pod_timeout(self, pod: Pod) -> bool:
        """Check if a pod has timed out based on its state."""
        return (
            (pod.state == PodState.Processing and 
             ((pod.init and pod.count > COLD_TIMEOUT_RETRIES) or 
              (not pod.init and pod.count > TIMEOUT_RETRIES))) or
            (pod.state == PodState.Starting and pod.count > SERVER_CHECK_RETRIES) or
            (pod.state == PodState.Initializing and pod.count > TIMEOUT_RETRIES) or
            (pod.state == PodState.Completed and pod.count > FREE_MAX_REMAINS)
        )

    def queue_prompt(self, workflow_type: WorkflowType, input_url: str) -> PromptResult:
        """Queue a new prompt for processing and wait for result."""
        prompt_id = str(uuid.uuid4())
        prompt = Prompt(prompt_id, workflow_type, input_url)
        
        with self.lock:
            self.queued_prompts.put(prompt)

        for _ in range(SERVER_CHECK_RETRIES):
            with self.lock:
                if prompt_id in self.completed_prompts:
                    return self.completed_prompts.pop(prompt_id).result
                
                if prompt_id in self.failed_prompts:
                    return self.failed_prompts.pop(prompt_id).result
            
            time.sleep(SERVER_CHECK_DELAY / 1000)
        
        self.processing_prompts.pop(prompt_id, None)
        return PromptResult(prompt_id, OutputState.Failed, "Time out error")

    def stop(self):
        """Stop the PodManager and clean up resources."""
        with self.lock:
            if self.state == PodManagerState.Running:
                self.state = PodManagerState.Stopped
                
                self.queued_prompts = Queue()
                self.processing_prompts.clear()
                self.completed_prompts.clear()
                self.failed_prompts.clear()
                
                while self.pods:
                    pod = self.pods.pop()
                    pod.destroy()

    def restart(self):
        """Restart the PodManager if it was stopped."""
        with self.lock:
            if self.state == PodManagerState.Stopped:
                self.state = PodManagerState.Running
                self.process_thread = Thread(target=self._process_loop, daemon=True)
                self.manage_thread = Thread(target=self._management_loop, daemon=True)
                self.process_thread.start()
                self.manage_thread.start()