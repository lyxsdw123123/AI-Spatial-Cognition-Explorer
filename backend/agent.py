import asyncio
import random
import math
import json
import traceback
from typing import List, Dict, Tuple, Optional, Set, Any
from datetime import datetime
import os

from langchain.agents import AgentExecutor, create_openai_tools_agent
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.messages import SystemMessage

from config.config import Config
from backend.map_service.amap_service import AmapService
from backend.path_memory.path_memory_manager import PathMemoryManager
from backend.tools import get_exploration_tools
from backend.model_factory import ModelFactory

class ExplorerAgent:
    """AI探索智能体 (LangChain ReAct Architecture)"""
    
    def __init__(self):
        self.current_location = None  # [lat, lng]
        self.exploration_boundary = None
        self.vision_radius = Config.AI_VISION_RADIUS
        self.move_speed = Config.AI_MOVE_SPEED
        self.move_interval = Config.AI_MOVE_INTERVAL
        
        # State
        self.is_exploring = False
        self.exploration_path = []
        self.visited_pois = set()
        self.interesting_pois = []
        self.mental_map = {
            'poi_relationships': {},
            'available_pois': []
        }
        self.exploration_round = 1
        self.rounds_completed = 0
        self.ever_visited_pois = set()
        self.exploration_complete = False
        self.poi_not_found_error_count = 0
        self.max_poi_not_found_errors = 5
        self.failed_poi_names = set()
        self.random_move_no_poi_count = 0
        self.reselect_start_count = 0
        self.max_no_poi_moves_before_reselect = 2
        self._road_node_id_map = {}
        self._road_node_id_counter = 0
        self._auto_explore_direction_index = 0
        
        # Services
        self.path_memory = PathMemoryManager(data_dir="data/mental_maps")
        # Ensure path units dir is correct relative to project root
        self.path_memory.path_units_dir = os.path.join("data", "path_units")
        
        self.map_service = AmapService()
        self.local_data_service = None
        self.use_local_data = False
        self.memory_mode = "context"

        # History for logic (still useful for context)
        self.position_history = []
        self.max_history_size = 20
        self.min_move_distance = 50
        self.avoid_radius = 100
        
        # Exploration Settings
        self.max_exploration_rounds = 1
        
        # Model Settings
        self.model_provider = "qwen"  # qwen, deepseek, openai
        self.exploration_mode = "随机POI探索"
        
        # LangChain Setup
        self.setup_agent()
        self._current_action = "Initializing"
        self._last_decision = None
        self.raw_conversation_history = []  # 存储LangChain原始对话历史

    def setup_agent(self):
        """Initialize LangChain Agent"""
        print(f"Initializing Agent with Provider: {self.model_provider}")
        
        # Use Factory to create model
        self.llm = ModelFactory.create_model(self.model_provider)
        
        self.tools = get_exploration_tools(self)
        
        mode = (getattr(self, "exploration_mode", "") or "").strip()
        m = mode.replace(" ", "")
        mode_hint = ""
        if "最近" in m:
            mode_hint = (
                "\nMode: Nearest-POI exploration."
                " After each scan_environment call, you MUST choose the single nearest"
                " unvisited visible POI as your next target and move there."
                " Do not skip a closer unvisited POI in favour of a farther one."
                " Never call explore_direction while any unvisited visible POIs exist."
            )
        elif "最短" in m:
            mode_hint = (
                "\nMode: Shortest-path exploration between POI pairs."
                " Repeatedly do the following cycle:"
                " (1) pick two distinct POIs (start and end), which you may choose randomly"
                " from the currently visible or otherwise known POIs;"
                " (2) plan a road-aware path that approximately minimises total travel distance"
                " between them (using move_to_poi and any path-planning tools);"
                " (3) follow that path step by step until you reach the end POI, then choose a new pair."
                " In this mode, focus on path optimality between the chosen pair, rather than greedily"
                " visiting whichever POI is locally nearest."
            )
        else:
            mode_hint = (
                "\nMode: Random exploration."
                " You may choose among visible POIs or directions more freely,"
                " while still respecting the basic rules above."
            )
        
        prompt = ChatPromptTemplate.from_messages([
            ("system", """You are an AI explorer in a map environment.
The environment consists of:
1. POI Points (Points of Interest): Specific locations like shops, parks, and landmarks that you can visit.
2. Road Nodes: Key points on the road network (intersections, endpoints) that define where you can move.
3. Road Data: Connectivity information that allows you to navigate along actual paths and streets.

Your goal is to explore the area, visit interesting POIs.
You have access to tools to scan the environment, move to POIs, explore directions, plan paths, and check your memory.

Rules:
1. STRICT SEQUENCE: First use 'scan_environment'. THEN, if interesting POIs are found, use 'move_to_poi' or 'plan_path'.
2. DO NOT move randomly if you have not scanned recently or if there are unvisited POIs visible.
3. If you see unvisited interesting POIs, you MUST visit them. Use 'move_to_poi' directly if close, or 'plan_path' if far/complex.
4. Only use 'explore_direction' if 'scan_environment' returns NO interesting unvisited POIs.
5. Do not visit the same POI twice unless absolutely necessary for navigation.
6. Keep track of your exploration path and avoid backtracking unnecessarily.""" + mode_hint),
            ("user", "{input}"),
            MessagesPlaceholder(variable_name="agent_scratchpad"),
        ])
        
        # Using OpenAI Tools Agent structure (compatible with Qwen function calling if supported, otherwise ReAct)
        # Note: ChatTongyi supports tool calling in recent versions. 
        # If not, we might need a fallback. assuming it works or standard ReAct.
        # For safety in this environment, I'll use create_tool_calling_agent if available or fallback.
        # But create_openai_tools_agent is the standard for "tool calling" models.
        try:
            agent = create_openai_tools_agent(self.llm, self.tools, prompt)
            self.agent_executor = AgentExecutor(
                agent=agent,
                tools=self.tools,
                verbose=True,
                return_intermediate_steps=True,
                max_iterations=200,
            )
        except Exception:
            # Fallback for models without native tool calling API support (if any)
            # But qwen-turbo usually supports it.
            from langchain.agents import create_react_agent
            react_prompt = ChatPromptTemplate.from_messages([
                ("system", "You are an AI explorer. Tools: {tools}\nTool Names: {tool_names}"),
                ("user", "{input}"),
                MessagesPlaceholder(variable_name="agent_scratchpad"),
            ])
            agent = create_react_agent(self.llm, self.tools, react_prompt)
            self.agent_executor = AgentExecutor(
                agent=agent,
                tools=self.tools,
                verbose=True,
                return_intermediate_steps=True,
                max_iterations=200,
            )

    async def initialize(self, start_location: Tuple[float, float], 
                        boundary: List[Tuple[float, float]],
                        use_local_data: bool = False,
                        exploration_mode: str = "随机POI探索",
                        local_data_service: Optional[Any] = None,
                        max_rounds: int = 1,
                        model_provider: str = "qwen"):
        if model_provider != self.model_provider or exploration_mode != getattr(self, "exploration_mode", None):
            self.model_provider = model_provider
            self.exploration_mode = exploration_mode
            self.setup_agent()
        else:
            self.exploration_mode = exploration_mode

        self.current_location = list(start_location)
        self.exploration_boundary = boundary
        self.use_local_data = use_local_data
        self.local_data_service = local_data_service
        self.max_exploration_rounds = max_rounds
        self.is_exploring = False
        self.exploration_round = 1
        self.rounds_completed = 0
        self.ever_visited_pois = set()
        self.exploration_complete = False
        self.visited_pois = set()
        self.interesting_pois = []
        self.exploration_path = []
        self.position_history = []
        self.poi_not_found_error_count = 0
        self.failed_poi_names = set()
        self.random_move_no_poi_count = 0
        self.reselect_start_count = 0
        self.max_no_poi_moves_before_reselect = 2
        self._road_node_id_map = {}
        self._road_node_id_counter = 0
        self._auto_explore_direction_index = 0
        self.path_memory.initialize(start_location, boundary, exploration_mode)
        self.raw_conversation_history = []  # 重置历史记录
        
        self.mental_map = {
            'start_location': self.current_location.copy(),
            'boundary': boundary,
            'poi_relationships': {},
            'available_pois': [],
            'use_local_data': use_local_data
        }
        
        # Load boundary POIs
        await self._load_boundary_pois()
        
        if use_local_data and local_data_service:
            self._ensure_on_road()
            
        print(f"Agent Initialized at {self.current_location}")

    async def start_exploration(self):
        """Main exploration loop driven by LangChain Agent"""
        if not self.is_exploring and len(self.visited_pois) > 0:
            # Reset for new round
            self.ever_visited_pois |= set(self.visited_pois)
            self.rounds_completed += 1
            self.exploration_round = self.rounds_completed + 1
            self.visited_pois = set()
            self.exploration_path = []
            self.position_history = []
            
        self.is_exploring = True
        print(f"AI Start Exploration at {self.current_location}")
        
        while self.is_exploring:
            try:
                try:
                    if self.mental_map.get("available_pois") and not self._get_unexplored_pois():
                        self.is_exploring = False
                        self._current_action = "Exploration complete (all POIs visited)"
                        print(f"\n[System] Exploration Complete! Visited all {len(self.mental_map.get('available_pois') or [])} POIs.", flush=True)
                        break
                except Exception:
                    pass

                print("\n--- Agent Step ---")
                status_desc = f"Current Location: {self.current_location}. "
                if self.visited_pois:
                    status_desc += f"Visited POIs count: {len(self.visited_pois)}. "

                input_text = f"{status_desc} Analyze surroundings and perform the next move."
                result = await self.agent_executor.ainvoke({
                    "input": input_text
                })
                
                # Record conversation history
                step_log = []
                step_log.append(f"--- Step {len(self.raw_conversation_history) + 1} ---")
                step_log.append(f"User Input: {input_text}")
                
                intermediate_steps = result.get('intermediate_steps', [])
                for action, observation in intermediate_steps:
                    if hasattr(action, 'log'):
                        step_log.append(f"AI Thought: {action.log}")
                    else:
                        step_log.append(f"AI Action: {action.tool} with {action.tool_input}")
                    step_log.append(f"Tool Output: {str(observation)}")
                
                step_log.append(f"AI Final Answer: {result.get('output')}")
                step_log.append("") # Empty line separator
                
                self.raw_conversation_history.extend(step_log)
                
                output_text = result.get('output')
                print(f"Agent Result: {output_text}")

                try:
                    last_tool = ""
                    last_obs = ""
                    if intermediate_steps:
                        last_action, last_observation = intermediate_steps[-1]
                        last_tool = getattr(last_action, "tool", "") if last_action is not None else ""
                        last_obs = str(last_observation or "")

                    if last_tool == "scan_environment" and ("Found 0 visible POIs" in last_obs):
                        unexplored = self._get_unexplored_pois()
                        if unexplored:
                            auto_result = await self.tool_reselect_start_point("system_auto_reselect_no_visible_pois")
                            self.raw_conversation_history.append("[System Auto] reselect_start_point")
                            self.raw_conversation_history.append(f"Tool Output: {auto_result}")
                            self.raw_conversation_history.append("")
                            print(f"[System Auto] {auto_result}", flush=True)
                    elif last_tool == "explore_direction":
                        if ("No POIs visible" in last_obs) and ("Reselected start point" in last_obs):
                            try:
                                scan_result = await self.tool_scan_environment()
                                self.raw_conversation_history.append("[System Auto] scan_environment(after_reselect)")
                                self.raw_conversation_history.append(f"Tool Output: {scan_result}")
                                self.raw_conversation_history.append("")
                                print(f"[System Auto] {scan_result}", flush=True)
                                if "Found 0 visible POIs" in str(scan_result or ""):
                                    unexplored = self._get_unexplored_pois()
                                    if unexplored:
                                        auto_result = await self.tool_reselect_start_point("system_auto_reselect_still_no_visible_after_reselect")
                                        self.raw_conversation_history.append("[System Auto] reselect_start_point(again)")
                                        self.raw_conversation_history.append(f"Tool Output: {auto_result}")
                                        self.raw_conversation_history.append("")
                                        print(f"[System Auto] {auto_result}", flush=True)
                            except Exception:
                                pass
                except Exception:
                    pass
                
                # 执行系统级轮次检查（对LLM不可见，仅在后端控制逻辑流）
                await self._check_and_handle_round_completion()
                
                # Sleep a bit between steps
                await asyncio.sleep(2)
                
            except Exception as e:
                print(f"Exploration Loop Error: {e}")
                traceback.print_exc()
                await asyncio.sleep(2)

    def stop_exploration(self):
        self.is_exploring = False
        # print("AI Stop Exploration")
        return self._generate_exploration_report()

    def get_current_status(self) -> Dict:
        # Compatible with frontend expectations
        formatted_path = []
        for p in self.exploration_path:
            if isinstance(p, dict) and 'location' in p:
                formatted_path.append(p['location'])
            elif isinstance(p, (list, tuple)):
                formatted_path.append(p)
                
        visited_names = [p['poi']['name'] for p in self.interesting_pois if 'poi' in p]
        
        return {
            'current_location': self.current_location,
            'is_exploring': self.is_exploring,
            'current_status': self._current_action,
            'visited_poi_count': len(self.visited_pois),
            'visited_pois': visited_names,
            'exploration_path': formatted_path,
            'last_decision': self._last_decision,
            'mental_map_size': len(self.mental_map.get('poi_relationships', {})),
            'round_index': self.exploration_round,
            'rounds_completed': self.rounds_completed
        }

    # ================= Tool Implementation Methods =================

    async def tool_scan_environment(self) -> str:
        """Logic for scanning environment"""
        self._current_action = "Scanning Environment"
        visible_pois = await self._get_visible_pois()
        if visible_pois:
            self.random_move_no_poi_count = 0
        
        summary = f"Found {len(visible_pois)} visible POIs.\n"
        for p in visible_pois:
            summary += f"- {p['name']} ({p.get('type','unknown')}), Dist: {p.get('distance_to_ai',0):.0f}m, Dir: {self._calculate_direction(self.current_location, p['location'])}\n"
        
        if not visible_pois:
            try:
                if self.mental_map.get("available_pois") and not self._get_unexplored_pois():
                    self.is_exploring = False
                    self._current_action = "Exploration complete (all POIs visited)"
                    summary += "No unexplored POIs remain. Exploration complete. Proceed to evaluation."
                    return summary
            except Exception:
                pass
            try:
                if self.mental_map.get("available_pois") and self._get_unexplored_pois():
                    reselection = await self.tool_reselect_start_point("system_auto_reselect_no_visible_pois(scan)")
                    summary += f"No POIs visible nearby. {reselection}"
                    return summary
            except Exception:
                pass
            summary += "No POIs visible nearby. Suggest exploring a direction."
            
        return summary

    async def tool_move_to_poi(self, poi_name: str) -> str:
        """Logic for moving to POI"""
        self._current_action = f"Moving to {poi_name}"
        
        original_name = poi_name
        base_name = poi_name.split(" (")[0].strip()
        norm_input = self._normalize_poi_name(base_name)
        
        if norm_input in self.failed_poi_names:
            self.poi_not_found_error_count += 1
            if self.poi_not_found_error_count >= self.max_poi_not_found_errors:
                self.is_exploring = False
                self._current_action = f"Stopped due to repeated unknown POI '{original_name}'"
                return f"POI '{original_name}' not found repeatedly. Stopping exploration and proceeding to evaluation."
            return f"Skipping move_to_poi: POI '{original_name}' is known to be missing. Consider choosing another target or changing direction."
        
        candidates = []
        for p in self.mental_map.get('available_pois', []):
            name = p.get('name')
            if not name:
                continue
            if self._normalize_poi_name(name) == norm_input:
                candidates.append(p)
        
        if candidates:
            poi_name = base_name
        if not candidates:
            self.failed_poi_names.add(norm_input)
            self.poi_not_found_error_count += 1
            if self.poi_not_found_error_count >= self.max_poi_not_found_errors:
                self.is_exploring = False
                self._current_action = f"Stopped due to repeated unknown POIs (last: '{original_name}')"
                return f"Error: POI '{original_name}' not found multiple times. Exploration stopped; proceed to evaluation."
            return f"Error: POI '{original_name}' not found in known map data. Skipping move_to_poi."
        
        unvisited = [p for p in candidates if p.get('id') not in self.visited_pois]
        if not unvisited:
            return f"All POIs named '{poi_name}' are already visited. Choose another target or explore a direction instead."
        
        self.poi_not_found_error_count = 0
        
        def distance_to_poi(poi):
            loc = poi.get('location')
            if not isinstance(loc, (list, tuple)) or len(loc) < 2:
                return float('inf')
            return self.map_service.calculate_distance(self.current_location, loc)
        
        target_poi = min(unvisited, key=distance_to_poi)

        # Execute Move
        target_loc = target_poi['location'] # [lat, lng]
        
        decision_record = {
            "action": "move_to_poi",
            "target": poi_name,
            "target_location": target_loc
        }
        self._last_decision = decision_record
        
        planning_info = ""
        if self.use_local_data and self.local_data_service:
            # Pre-calculate to give info
            start_loc = (self.current_location[1], self.current_location[0])
            end_loc = (target_loc[1], target_loc[0])
            path = self.local_data_service.find_shortest_path(start_loc, end_loc)
            if path:
                dist = 0
                for i in range(len(path) - 1):
                    dist += self.local_data_service._calculate_distance(path[i], path[i+1])
                planning_info = f"Path planned via road network: {len(path)} steps, approx {dist:.0f}m. "
                await self._move_along_road(target_loc, decision_record)
            else:
                planning_info = "No road path found, moving directly. "
                await self._move_direct(target_loc, decision_record)
        else:
             await self._move_direct(target_loc, decision_record)
             
        # Visit Logic
        dist = self.map_service.calculate_distance(self.current_location, target_loc)
        if dist < 50:
            await self._visit_poi(target_poi, decision_record)
            return f"{planning_info}Successfully moved to and visited {poi_name}."
        else:
            # Force visit if we are close enough (e.g. stopped at nearest road node)
            # Or if we just finished a move_along_road which brings us to the nearest node
            if self.use_local_data and dist < 300: # Allow larger buffer for "last mile"
                # Teleport final small distance
                self.current_location = list(target_loc)
                await self._visit_poi(target_poi, decision_record)
                return f"{planning_info}Arrived at nearest road node and walked to {poi_name}."
            
            return f"{planning_info}Moved towards {poi_name} but stopped {dist:.0f}m away."

    async def tool_explore_direction(self, direction: float, reason: str) -> str:
        """Logic for exploring direction"""
        self._current_action = f"Exploring direction {direction:.0f}°"
        
        decision_record = {
            "action": "explore_direction",
            "target": direction,
            "reason": reason
        }
        self._last_decision = decision_record
        
        if self.use_local_data and self.local_data_service:
             await self._move_in_direction_on_road(direction, decision_record)
        else:
             await self._move_in_direction_direct(direction, decision_record)

        visible_pois = await self._get_visible_pois()
        if visible_pois:
            self.random_move_no_poi_count = 0
            return f"Explored direction {direction:.0f}°. New location: {self.current_location}. Now see {len(visible_pois)} visible POIs."

        try:
            if self.mental_map.get("available_pois") and not self._get_unexplored_pois():
                self.is_exploring = False
                self._current_action = "Exploration complete (all POIs visited)"
                return "No unexplored POIs remain. Exploration complete. Proceed to evaluation."
        except Exception:
            pass

        self.random_move_no_poi_count += 1
        if self.random_move_no_poi_count >= int(getattr(self, "max_no_poi_moves_before_reselect", 2) or 2):
            unexplored = self._get_unexplored_pois()
            if unexplored:
                move_count = int(self.random_move_no_poi_count or 0)
                reselection_reason = f"连续随机移动{self.random_move_no_poi_count}次仍未发现POI"
                reselection = await self.tool_reselect_start_point(reselection_reason)
                return f"Explored direction {direction:.0f}°. New location: {self.current_location}. No POIs visible after {move_count} random moves. {reselection}"

        return f"Explored direction {direction:.0f}°. New location: {self.current_location}. No POIs visible nearby."

    async def tool_reselect_start_point(self, reason: str = "") -> str:
        self._current_action = "Reselecting Start Point"

        unexplored = self._get_unexplored_pois()
        if not unexplored:
            return "No unexplored POIs remain. Cannot reselect a new start point."

        target_poi = random.choice(unexplored)
        target_loc = target_poi.get("location")
        if not isinstance(target_loc, (list, tuple)) or len(target_loc) < 2:
            return "Selected POI has invalid location. Cannot reselect start point."

        self.reselect_start_count += 1
        self.random_move_no_poi_count = 0

        decision_record = {
            "action": "reselect_start_point",
            "target": target_poi.get("name"),
            "target_id": target_poi.get("id"),
            "target_location": list(target_loc),
            "reason": reason,
            "reselect_count": self.reselect_start_count,
        }
        self._last_decision = decision_record

        self.current_location = list(target_loc)
        self._record_path_point("reselect_start_point", decision_record)

        visible_snapshot = self._build_visible_snapshot_at_location(
            self.current_location,
            exclude_poi_id=target_poi.get("id"),
            limit=10,
        )

        try:
            if hasattr(self.path_memory, "_last_poi_visit"):
                self.path_memory._last_poi_visit = None
            if hasattr(self.path_memory, "_current_leg_route_nodes"):
                self.path_memory._current_leg_route_nodes = []
            if hasattr(self.path_memory, "_current_leg_total_distance"):
                self.path_memory._current_leg_total_distance = 0.0
        except Exception:
            pass

        await self._visit_poi(target_poi, decision_record, visible_snapshot=visible_snapshot)

        target_name = target_poi.get("name") or "Unknown POI"
        return f"Reselected start point to unexplored POI '{target_name}' (count={self.reselect_start_count})."

    async def tool_plan_path(self, target: str) -> str:
        """Logic for planning a path to a target (POI or coordinates)"""
        if not self.use_local_data or not self.local_data_service:
            return "Path planning is only available when using local data with road networks."

        # Try to find target POI
        target_loc = None
        target_name = target
        
        # Check available POIs
        for p in self.mental_map.get('available_pois', []):
            if p.get('name') == target:
                target_loc = p['location']
                break
        
        if not target_loc:
            return f"Target '{target}' not found in available POIs."

        # Calculate path
        start_loc = (self.current_location[1], self.current_location[0]) # lon, lat
        end_loc = (target_loc[1], target_loc[0]) # lon, lat
        
        path = self.local_data_service.find_shortest_path(start_loc, end_loc)
        
        if not path:
            return f"Could not find a path to {target} on the road network."
            
        distance = 0
        for i in range(len(path) - 1):
            distance += self.local_data_service._calculate_distance(path[i], path[i+1])
            
        return f"Path to {target} found. Distance: {distance:.0f} meters. Steps: {len(path)}."


    def tool_check_memory(self) -> str:
        return f"Visited {len(self.visited_pois)} POIs. Path length: {len(self.exploration_path)} points."
    
    # ================= Helper Methods (Migrated) =================
    
    def _normalize_poi_name(self, name: str) -> str:
        if not isinstance(name, str):
            name = str(name)
        name = name.replace("’", "'").replace("‘", "'").replace("`", "'")
        return name.strip().lower()
    
    async def _load_boundary_pois(self):
        if not self.exploration_boundary:
            return
        try:
            if self.use_local_data and self.local_data_service:
                raw_pois = self.local_data_service.get_poi_data()
                filtered = []
                for p in raw_pois:
                    # Fix location format if needed
                    loc = p['location']
                    if isinstance(loc, dict):
                         loc = [loc['lat'], loc['lng']]
                    if self._is_within_boundary(loc):
                        p['location'] = loc
                        filtered.append(p)
                self.mental_map['available_pois'] = filtered
            else:
                self.mental_map['available_pois'] = self.map_service.get_poi_in_polygon(self.exploration_boundary)
                
            # Ensure IDs
            for p in self.mental_map['available_pois']:
                if not p.get('id'):
                    p['id'] = p.get('name')
        except Exception as e:
            print(f"Error loading boundary POIs: {e}")

    async def _get_visible_pois(self) -> List[Dict]:
        available = self.mental_map.get('available_pois', [])
        visible = []
        for p in available:
            if not p.get('name'): continue
            if p['id'] in self.visited_pois: continue
            
            dist = self.map_service.calculate_distance(self.current_location, p['location'])
            if dist <= self.vision_radius:
                p_copy = p.copy()
                p_copy['distance_to_ai'] = dist
                visible.append(p_copy)
        return visible

    def _is_within_boundary(self, location):
        if not self.exploration_boundary: return True
        lat, lng = location
        # Simple bounding box check for speed
        lats = [p[0] for p in self.exploration_boundary]
        lngs = [p[1] for p in self.exploration_boundary]
        return min(lats) <= lat <= max(lats) and min(lngs) <= lng <= max(lngs)

    async def _move_direct(self, target_location, decision):
        # Simulation of movement
        dist = self.map_service.calculate_distance(self.current_location, target_location)
        steps = max(1, int(dist / 20)) # 20m steps
        lat_step = (target_location[0] - self.current_location[0]) / steps
        lng_step = (target_location[1] - self.current_location[1]) / steps
        
        for i in range(steps):
            if not self.is_exploring: break
            self.current_location[0] += lat_step
            self.current_location[1] += lng_step
            if i % 5 == 0:
                await asyncio.sleep(0.5) # Fast simulation
        
        self.current_location = list(target_location)
        self._record_path_point("move_direct", decision)

    async def _move_along_road(self, target_location, decision):
        # Simplified road movement
        path = self.local_data_service.find_shortest_path(
            (self.current_location[1], self.current_location[0]),
            (target_location[1], target_location[0])
        )
        if not path:
            await self._move_direct(target_location, decision)
            return
            
        # Record start point if not already recorded
        if not self.exploration_path or self.exploration_path[-1]['location'] != self.current_location:
             self._record_path_point("move_start", decision)

        for i in range(1, len(path)):
            if not self.is_exploring: break
            pt = path[i]
            loc = [pt[1], pt[0]]
            
            # Update location
            self.current_location = loc
            
            # Record this intermediate path point so frontend draws the road path
            # We use a slightly different action name to indicate it's part of a path
            step_decision = decision.copy()
            step_decision['step_index'] = i
            self._record_path_point("move_road_step", step_decision)
            
            # Record to path memory ordered sequence for context generation
            try:
                self.path_memory.append_sequence_item("road_node", {
                    "location": loc,
                    "name": self._format_road_node_name(loc)
                })
            except Exception:
                pass
            
            # Wait a bit to simulate movement speed and allow frontend to poll
            await asyncio.sleep(0.5)
        
        # Ensure we reach the exact target location if we are close enough
        # This handles the "last mile" from the nearest road node to the POI
        dist_to_target = self.map_service.calculate_distance(self.current_location, target_location)
        if dist_to_target > 0 and dist_to_target < 200:
             self.current_location = list(target_location)
             self._record_path_point("move_final_approach", decision)
             await asyncio.sleep(0.2)

        # The final point is implicitly recorded by the last step or final approach, 
        # but we can ensure the main decision is marked as completed.
        # However, to avoid duplicate points at the end, we check distance.
        if not self.exploration_path or self.exploration_path[-1]['location'] != self.current_location:
             self._record_path_point("move_road_end", decision)

    async def _move_in_direction_direct(self, direction, decision):
        try:
            k = int(getattr(self, "random_move_no_poi_count", 0) or 0)
        except Exception:
            k = 0
        base_dist = max(self.min_move_distance, self.move_speed * self.move_interval)
        dist = float(base_dist) * float(max(1, min(12, k + 1)))
        rad = math.radians(direction)
        lat_off = dist * math.cos(rad) / 111000
        lng_off = dist * math.sin(rad) / (111000 * math.cos(math.radians(self.current_location[0])))
        
        new_loc = [self.current_location[0] + lat_off, self.current_location[1] + lng_off]
        
        if self._is_within_boundary(new_loc):
            await self._move_direct(new_loc, decision)
        else:
            await self._move_direct(self.current_location, decision)

    def _format_road_node_name(self, loc: List[float]) -> str:
        try:
            if not isinstance(loc, (list, tuple)) or len(loc) < 2:
                self._road_node_id_counter += 1
                return f"node_{self._road_node_id_counter}"
            key = f"{float(loc[0]):.6f}_{float(loc[1]):.6f}"
            if key in self._road_node_id_map:
                return f"node_{self._road_node_id_map[key]}"
            self._road_node_id_counter += 1
            self._road_node_id_map[key] = self._road_node_id_counter
            return f"node_{self._road_node_id_counter}"
        except Exception:
            try:
                self._road_node_id_counter += 1
                return f"node_{self._road_node_id_counter}"
            except Exception:
                return "node_1"
        else:
            print("Hit boundary during direction move")

    async def _move_in_direction_on_road(self, direction, decision):
        # Try to project point in direction
        try:
            k = int(getattr(self, "random_move_no_poi_count", 0) or 0)
        except Exception:
            k = 0
        dist = int(min(1500, max(200, 200 * (k + 1))))
        rad = math.radians(direction)
        lat_off = dist * math.cos(rad) / 111000
        lng_off = dist * math.sin(rad) / (111000 * math.cos(math.radians(self.current_location[0])))
        target = [self.current_location[0] + lat_off, self.current_location[1] + lng_off]
        
        # Project to road
        proj = self.local_data_service.project_point_to_road((target[1], target[0]))
        if proj:
            target = [proj[1], proj[0]]
            await self._move_along_road(target, decision)
        else:
            await self._move_direct(target, decision)

    async def _visit_poi(self, poi, decision, visible_snapshot: Optional[List[Dict]] = None):
        self.visited_pois.add(poi['id'])
        self.interesting_pois.append({'poi': poi, 'time': datetime.now()})
        
        # Record to memory
        self.path_memory.record_poi_visit(poi, {
            'visit_time': datetime.now().isoformat(),
            'notes': f"Visited via {decision.get('action')}",
            'location_when_visited': self.current_location.copy(),
            'visible_snapshot': visible_snapshot or []
        })
        
    def _record_path_point(self, action, decision):
        self.exploration_path.append({
            'location': self.current_location.copy(),
            'timestamp': datetime.now(),
            'action': action,
            'decision': decision
        })
        # Record detailed path memory if needed
        # Simplified for now to ensure stability
        
    def _ensure_on_road(self):
        if not self.local_data_service: return
        proj = self.local_data_service.project_point_to_road((self.current_location[1], self.current_location[0]))
        if proj:
            self.current_location = [proj[1], proj[0]]

    def _calculate_direction(self, loc1, loc2):
        lat1, lng1 = math.radians(loc1[0]), math.radians(loc1[1])
        lat2, lng2 = math.radians(loc2[0]), math.radians(loc2[1])
        d_lng = lng2 - lng1
        y = math.sin(d_lng) * math.cos(lat2)
        x = math.cos(lat1) * math.sin(lat2) - math.sin(lat1) * math.cos(lat2) * math.cos(d_lng)
        bearing = math.degrees(math.atan2(y, x))
        return (bearing + 360) % 360

    def _get_unexplored_pois(self) -> List[Dict]:
        explored_ids = set()
        try:
            explored_ids |= set(self.ever_visited_pois or set())
        except Exception:
            pass
        try:
            explored_ids |= set(self.visited_pois or set())
        except Exception:
            pass

        unexplored = []
        for p in self.mental_map.get("available_pois", []) or []:
            try:
                pid = p.get("id")
                if not pid:
                    continue
                if pid in explored_ids:
                    continue
                unexplored.append(p)
            except Exception:
                continue
        return unexplored

    def _build_visible_snapshot_at_location(
        self,
        location: List[float],
        exclude_poi_id: Optional[str] = None,
        limit: int = 10,
    ) -> List[Dict]:
        items = []
        for p in self.mental_map.get("available_pois", []) or []:
            try:
                pid = p.get("id")
                if not pid or pid == exclude_poi_id:
                    continue
                if pid in self.visited_pois:
                    continue
                loc = p.get("location")
                if not isinstance(loc, (list, tuple)) or len(loc) < 2:
                    continue
                dist = self.map_service.calculate_distance(location, loc)
                if dist > self.vision_radius:
                    continue
                direction = self._calculate_direction(location, loc)
                items.append({
                    "name": p.get("name") or str(pid),
                    "relative_position": {"direction": float(direction), "distance": float(dist)},
                })
            except Exception:
                continue

        items.sort(key=lambda x: x.get("relative_position", {}).get("distance", float("inf")))
        return items[: max(0, int(limit or 0))]

    def _generate_exploration_report(self):
        return {
            'exploration_path': self.exploration_path,
            'visited_pois': list(self.visited_pois),
            'interesting_pois': self.interesting_pois,
            'total_distance': len(self.exploration_path) * 20, # Rough estimate
            'exploration_time': 0,
            'poi_count': len(self.interesting_pois)
        }

    # API compatibility methods
    def answer_location_question(self, question: str) -> str:
        # Simple passthrough to path memory or LLM
        return self.path_memory.answer_path_question(question)

    def set_memory_mode(self, mode: str):
        self.memory_mode = mode

    def get_memory_summary(self):
        return self.path_memory.get_memory_stats()

    def get_raw_memory_text(self) -> str:
        """Get the raw conversation history as text"""
        if not self.raw_conversation_history:
            return "No exploration history available."
        return "\n".join(self.raw_conversation_history)

    async def _check_and_handle_round_completion(self):
        """
        [System Internal Logic]
        检查当前轮次是否完成，并处理轮次切换。
        注意：此方法运行在后端Python层面，拥有全局上帝视角（访问mental_map），
        但其判断结果仅用于重置 visited_pois 过滤器，绝不会将全局数据（如POI总数、剩余POI列表）
        传递给 LLM 的 Prompt 或 Context。
        LLM 依然保持"盲人"视角，只通过 tool_scan_environment 感知环境。
        """
        # 1. 获取上帝视角的全量POI ID
        available_ids = set()
        for p in self.mental_map.get('available_pois', []):
            if p.get('id'):
                available_ids.add(p['id'])
        
        try:
            if self.mental_map.get("available_pois") and not self._get_unexplored_pois():
                print(f"\n[System] Exploration Complete! Visited all {len(available_ids)} POIs.", flush=True)
                self.stop_exploration()
                return
        except Exception:
            pass

        # 2. 判断是否完成本轮（已访问集合 包含 全量集合）
        if available_ids and self.visited_pois and self.visited_pois.issuperset(available_ids):
            print(f"\n[System] Round {self.exploration_round} Completed! Visited all {len(available_ids)} POIs.")
            
            if self.exploration_round < self.max_exploration_rounds:
                # === 进入下一轮 ===
                self.rounds_completed += 1
                self.exploration_round += 1
                
                # 将本轮的访问记录归档到 ever_visited_pois（长期统计）
                self.ever_visited_pois |= set(self.visited_pois)
                
                # === 关键操作：重置当前轮次的 visited_pois ===
                # 这只是重置了"过滤器"，让 scan_environment 工具再次对所有 POI 可见。
                # LLM 的记忆（PathMemory）不受影响，依然保留之前的所有探索记录。
                self.visited_pois = set()
                
                print(f"[System] Starting Round {self.exploration_round} of {self.max_exploration_rounds}...")
                # 此时不通知LLM，LLM在下一次 scan 时会自然发现周围又有"新"POI了
            else:
                # === 所有轮次完成 ===
                print(f"[System] All {self.max_exploration_rounds} rounds completed. Stopping exploration.")
                self.stop_exploration()
