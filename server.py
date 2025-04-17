from dotenv import load_dotenv
load_dotenv()

from core.pod_manager import create_pod_with_network_volume, get_pod_info

if __name__ == "__main__":
    # create_pod_with_network_volume("0mdsp6d0ht", "test1")
    print(get_pod_info("kplv02tnurj057"))