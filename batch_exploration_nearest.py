import requests
import time
import json
import os
import csv
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple

# --- Configuration ---

BASE_URL = "http://localhost:8000"
REGIONS = [
    "上海外滩",
    "伦敦大本钟",
    "北京天安门",
    "多伦多CN塔",
    "巴黎埃菲尔铁塔",
    "广州塔",
    "旧金山联合广场",
    "柏林勃兰登堡门",
    "武汉黄鹤楼",
    "洛杉矶好莱坞",
    "纽约时代广场",
    "维也纳美泉宫",
    "罗马斗兽场",
    "芝加哥千禧公园",
    "长沙五一广场"
]
# Excluded: "晋中市榆次区"

MODELS = [
    "qwen",
    "openai",
    "deepseek",
    "claude",
    "gemini",
    "zhipu"
]

MEMORY_MODE = "raw"
EXPLORATION_MODE = "最近距离探索"
QUESTION_STRATEGY = "Direct"
MAX_ROUNDS = 1

OUTPUT_CSV = "最近结果.csv"
REPORT_DIR = "最近报告"

# --- Helper Functions ---

def ensure_dirs():
    if not os.path.exists(REPORT_DIR):
        os.makedirs(REPORT_DIR)

def wait_for_status(endpoint: str, key: str, expected_value: Any, timeout_sec: int = 1800, check_interval: int = 5) -> bool:
    """
    Wait until the status[key] == expected_value (or status[key] is False if expected is False).
    Returns True if condition met, False if timeout.
    """
    start_time = time.time()
    while time.time() - start_time < timeout_sec:
        try:
            resp = requests.get(f"{BASE_URL}{endpoint}")
            if resp.status_code == 200:
                data = resp.json()
                # Handle different response structures
                status_data = data.get("data", data)
                if key == "status": # Special handling for evaluation status
                    status_data = data # Evaluation status is top-level or flattened
                
                current_val = status_data.get(key)
                
                # For exploration: wait until is_exploring is False
                if key == "is_exploring" and expected_value is False:
                    if current_val is False:
                        return True
                
                # For evaluation: wait until status is completed
                if key == "status" and expected_value == "completed":
                    if current_val == "completed" or current_val == "failed":
                        return True # Stop waiting on failure too
                        
                # Generic check
                if current_val == expected_value:
                    return True
        except Exception as e:
            print(f"Error checking status: {e}")
        
        time.sleep(check_interval)
    return False

def get_local_pois() -> List[Dict]:
    try:
        resp = requests.get(f"{BASE_URL}/exploration/local_pois")
        if resp.status_code == 200:
            return resp.json().get("data", [])
    except Exception as e:
        print(f"Error fetching POIs: {e}")
    return []

def calculate_bounds_and_start(pois: List[Dict]) -> Tuple[List[Dict], Dict]:
    if not pois:
        # Default fallback
        return [], {"latitude": 39.9087, "longitude": 116.3975}

    lats = [p["location"]["latitude"] for p in pois]
    lngs = [p["location"]["longitude"] for p in pois]
    
    min_lat, max_lat = min(lats), max(lats)
    min_lng, max_lng = min(lngs), max(lngs)
    
    # Expand slightly
    margin = 0.002
    boundary = [
        {"latitude": min_lat - margin, "longitude": min_lng - margin},
        {"latitude": max_lat + margin, "longitude": min_lng - margin},
        {"latitude": max_lat + margin, "longitude": max_lng + margin},
        {"latitude": min_lat - margin, "longitude": max_lng + margin}
    ]
    
    # Center start
    center_lat = (min_lat + max_lat) / 2
    center_lng = (min_lng + max_lng) / 2
    start_location = {"latitude": center_lat, "longitude": center_lng}
    
    return boundary, start_location

# --- Main Execution ---

def run_experiment():
    ensure_dirs()
    
    # Initialize CSV if not exists
    file_exists = os.path.isfile(OUTPUT_CSV)
    with open(OUTPUT_CSV, 'a', newline='', encoding='utf-8-sig') as csvfile:
        fieldnames = ['Region', 'Model', 'Total Score', 'Accuracy', 'Completed At', 
                      'Type_定位与定向', 'Type_空间距离估算', 'Type_邻近关系判断', 'Type_POI密度识别', 'Type_路径规划']
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        if not file_exists:
            writer.writeheader()

    for region in REGIONS:
        print(f"\n=== Processing Region: {region} ===")
        
        # 1. Switch Region
        try:
            resp = requests.post(f"{BASE_URL}/exploration/switch_region", json={"region_name": region})
            if resp.status_code != 200 or not resp.json().get("success"):
                print(f"Failed to switch region to {region}. Skipping.")
                continue
            print(f"Switched to {region}")
        except Exception as e:
            print(f"Error switching region: {e}")
            continue

        # 2. Get Data for Init
        pois = get_local_pois()
        boundary, start_location = calculate_bounds_and_start(pois)
        if not pois:
            print("No POIs found. Using default/empty bounds.")

        for model in MODELS:
            print(f"\n--- Testing Model: {model} ---")
            
            # 3. Init Exploration
            init_payload = {
                "start_location": start_location,
                "boundary": {"points": boundary},
                "use_local_data": True,
                "exploration_mode": EXPLORATION_MODE,
                "memory_mode": MEMORY_MODE,
                "max_rounds": MAX_ROUNDS,
                "model_provider": model
            }
            
            try:
                resp = requests.post(f"{BASE_URL}/exploration/init", json=init_payload)
                if resp.status_code != 200:
                    print(f"Init failed: {resp.text}")
                    continue
            except Exception as e:
                print(f"Init exception: {e}")
                continue

            # 4. Start Exploration
            try:
                resp = requests.post(f"{BASE_URL}/exploration/start")
                if resp.status_code != 200:
                    print(f"Start failed: {resp.text}")
                    continue
                print("Exploration started...")
            except Exception as e:
                print(f"Start exception: {e}")
                continue

            # 5. Monitor Exploration
            print("Waiting for exploration to complete (max 30 mins)...")
            finished = wait_for_status("/exploration/status", "is_exploring", False, timeout_sec=1800, check_interval=10)
            if not finished:
                print("Exploration timed out! Stopping forcefully.")
            else:
                print("Exploration finished naturally.")

            # 6. Stop Exploration (Get Report)
            exploration_report = {}
            try:
                resp = requests.post(f"{BASE_URL}/exploration/stop")
                if resp.status_code == 200:
                    data = resp.json()
                    exploration_report = data.get("report", {})
                    print(f"Exploration stopped. Report size: {len(str(exploration_report))}")
            except Exception as e:
                print(f"Stop exception: {e}")

            # 7. Start Evaluation
            print("Starting evaluation...")
            eval_payload = {
                "questions": [],
                "exploration_data": {},
                "model_provider": model,
                "strategies": [QUESTION_STRATEGY]
            }
            
            stop_resp_data = resp.json()
            eq_payload = stop_resp_data.get("evaluation_questions")
            if not eq_payload or not eq_payload.get("questions"):
                print("No questions found for evaluation. Skipping.")
                continue
                
            questions_list = eq_payload.get("questions")
            
            eval_req = {
                "questions": questions_list,
                "exploration_data": {
                    "ai_location": [0, 0],
                    "exploration_path": [],
                    "visited_pois": [],
                    "context_mode": MEMORY_MODE 
                },
                "model_provider": model,
                "strategies": [QUESTION_STRATEGY]
            }
            
            try:
                resp = requests.post(f"{BASE_URL}/evaluation/start", json=eval_req)
                if resp.status_code != 200:
                    print(f"Evaluation start failed: {resp.text}")
                    continue
                print("Evaluation started...")
            except Exception as e:
                print(f"Eval start exception: {e}")
                continue
                
            # 8. Monitor Evaluation
            print("Waiting for evaluation to complete...")
            finished_eval = wait_for_status("/evaluation/status", "status", "completed", timeout_sec=600, check_interval=5)
            if not finished_eval:
                print("Evaluation timed out or failed.")
            else:
                print("Evaluation completed.")

            # 9. Get Results
            try:
                resp = requests.get(f"{BASE_URL}/evaluation/result")
                if resp.status_code == 200:
                    result_data = resp.json().get("data", {})
                    strat_result = result_data.get(QUESTION_STRATEGY, {})
                    
                    # 10. Save Results
                    type_scores = strat_result.get("type_scores", {})
                    row = {
                        'Region': region,
                        'Model': model,
                        'Total Score': strat_result.get("total_score"),
                        'Accuracy': f"{strat_result.get('accuracy', 0):.2f}%",
                        'Completed At': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        'Type_定位与定向': f"{type_scores.get('定位与定向', {}).get('percentage', 0):.2f}%",
                        'Type_空间距离估算': f"{type_scores.get('空间距离估算', {}).get('percentage', 0):.2f}%",
                        'Type_邻近关系判断': f"{type_scores.get('邻近关系判断', {}).get('percentage', 0):.2f}%",
                        'Type_POI密度识别': f"{type_scores.get('POI密度识别', {}).get('percentage', 0):.2f}%",
                        'Type_路径规划': f"{type_scores.get('路径规划', {}).get('percentage', 0):.2f}%"
                    }
                    
                    with open(OUTPUT_CSV, 'a', newline='', encoding='utf-8-sig') as csvfile:
                        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                        writer.writerow(row)
                    
                    report_content = {
                        "region": region,
                        "model": model,
                        "exploration_report": exploration_report,
                        "evaluation_result": strat_result,
                        "context_text": result_data.get("context_text")
                    }
                    
                    report_file = os.path.join(REPORT_DIR, f"{region}_{model}_report.txt")
                    with open(report_file, "w", encoding="utf-8") as f:
                        json.dump(report_content, f, ensure_ascii=False, indent=2)
                        
                    print(f"Saved results for {region} - {model}")
                    
            except Exception as e:
                print(f"Error fetching/saving results: {e}")

    print("\n=== All Experiments Completed ===")

if __name__ == "__main__":
    run_experiment()

