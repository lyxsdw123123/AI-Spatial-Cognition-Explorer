import requests
import json

# 测试初始化探索API
init_data = {
    "start_location": {
        "latitude": 39.9042,
        "longitude": 116.4074
    },
    "boundary": {
        "points": [
            {"latitude": 39.900, "longitude": 116.400},
            {"latitude": 39.900, "longitude": 116.410},
            {"latitude": 39.910, "longitude": 116.410},
            {"latitude": 39.910, "longitude": 116.400}
        ]
    }
}

try:
    # 初始化探索
    print("正在初始化探索...")
    response = requests.post("http://localhost:8000/exploration/init", json=init_data)
    print(f"状态码: {response.status_code}")
    print(f"响应: {response.json()}")
    
    if response.status_code == 200:
        # 开始探索
        print("\n正在开始探索...")
        start_response = requests.post("http://localhost:8000/exploration/start")
        print(f"状态码: {start_response.status_code}")
        print(f"响应: {start_response.json()}")
        
except Exception as e:
    print(f"错误: {e}")