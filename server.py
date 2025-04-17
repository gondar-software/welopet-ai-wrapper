from .core.pod_helper import *

if __name__ == "__main__":
    pod_id = create_pod_with_network_volume("0mdsp6d0ht", "test1")
    print(pod_id)
    pod_info = get_pod_info(pod_id)
    print(pod_info)
    run_comfyui_server(pod_id, pod_info.public_ip, pod_info.port_mappings)