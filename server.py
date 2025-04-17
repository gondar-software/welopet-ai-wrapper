from dotenv import load_dotenv
load_dotenv()

from core.pod_helper import create_pod_with_network_volume, get_pod_info, delete_pod

if __name__ == "__main__":
    # create_pod_with_network_volume("0mdsp6d0ht", "test1")
    print(delete_pod("kplv02tnurj057"))