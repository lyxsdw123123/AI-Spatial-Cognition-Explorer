import asyncio
import random
import math
import json
import traceback
from typing import List, Dict, Tuple, Optional, Set, Any
from datetime import datetime
import os

from langchain_community.chat_models import ChatTongyi
from langchain.agents import AgentExecutor, create_openai_tools_agent
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.messages import SystemMessage

from config.config import Config
from backend.map_service.amap_service import AmapService
from backend.path_memory.path_memory_manager import PathMemoryManager
from backend.tools import get_exploration_tools

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
        
        # LangChain Setup
        self.setup_agent()
        self._current_action = "Initializing"
        self._last_decision = None

    def setup_agent(self):
        """Initialize LangChain Agent"""
        self.llm = ChatTongyi(
            dashscope_api_key=Config.DASHSCOPE_API_KEY,
            model_name="qwen-turbo", # or qwen-max
            temperature=0.7
        )
        
        self.tools = get_exploration_tools(self)
        
        prompt = ChatPromptTemplate.from_messages([
            ("system", """You are an AI explorer in a map environment.
Your goal is to explore the area, visit interesting POIs (Points of Interest), and build a mental map.
You have access to tools to scan the environment, move to POIs, explore directions, and check your memory.

Rules:
1. ALWAYS scan the environment first to see what is around you.
2. If you see unvisited interesting POIs, move to them using 'move_to_poi'.
3. If no interesting POIs are visible, use 'explore_direction' to move to a new area.
4. Do not visit the same POI twice unless necessary.
5. Keep track of your exploration path.
"""),
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
            self.agent_executor = AgentExecutor(agent=agent, tools=self.tools, verbose=True)
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
            self.agent_executor = AgentExecutor(agent=agent, tools=self.tools, verbose=True)

    async def initialize(self, start_location: Tuple[float, float], 
                        boundary: List[Tuple[float, float]],
                        use_local_data: bool = False,
                        exploration_mode: str = "随机POI探索",
                        local_data_service = None):
        self.current_location = list(start_location)
        self.exploration_boundary = boundary
        self.use_local_data = use_local_data
        self.local_data_service = local_data_service
        self.path_memory.initialize(start_location, boundary, exploration_mode)
        
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
                print("\n--- Agent Step ---")
                # Invoke Agent for one decision cycle
                # We give it the current status as input
                status_desc = f"Current Location: {self.current_location}. "
                if self.visited_pois:
                    status_desc += f"Visited POIs count: {len(self.visited_pois)}. "
                
                # Execute agent
                # The agent should call tools and finally return a summary of what it did.
                result = await self.agent_executor.ainvoke({
                    "input": f"{status_desc} Analyze surroundings and perform the next move."
                })
                
                print(f"Agent Result: {result.get('output')}")
                
                # Sleep a bit between steps
                await asyncio.sleep(2)
                
            except Exception as e:
                print(f"Exploration Loop Error: {e}")
                traceback.print_exc()
                await asyncio.sleep(2)

    def stop_exploration(self):
        self.is_exploring = False
        print("AI Stop Exploration")
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
        
        summary = f"Found {len(visible_pois)} visible POIs.\n"
        for p in visible_pois:
            summary += f"- {p['name']} ({p.get('type','unknown')}), Dist: {p.get('distance_to_ai',0):.0f}m, Dir: {self._calculate_direction(self.current_location, p['location'])}\n"
        
        if not visible_pois:
            summary += "No POIs visible nearby. Suggest exploring a direction."
            
        return summary

    async def tool_move_to_poi(self, poi_name: str) -> str:
        """Logic for moving to POI"""
        self._current_action = f"Moving to {poi_name}"
        
        # Find POI object
        target_poi = None
        for p in self.mental_map.get('available_pois', []):
            if p.get('name') == poi_name:
                target_poi = p
                break
        
        if not target_poi:
            return f"Error: POI '{poi_name}' not found in known map data."
            
        if target_poi['id'] in self.visited_pois:
             return f"POI '{poi_name}' already visited."

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
             
        return f"Explored direction {direction:.0f}°. New location: {self.current_location}"

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
                    "name": f"node_{loc[0]:.6f}_{loc[1]:.6f}"
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
        dist = max(self.min_move_distance, self.move_speed * self.move_interval)
        rad = math.radians(direction)
        lat_off = dist * math.cos(rad) / 111000
        lng_off = dist * math.sin(rad) / (111000 * math.cos(math.radians(self.current_location[0])))
        
        new_loc = [self.current_location[0] + lat_off, self.current_location[1] + lng_off]
        
        if self._is_within_boundary(new_loc):
            await self._move_direct(new_loc, decision)
        else:
            print("Hit boundary during direction move")

    async def _move_in_direction_on_road(self, direction, decision):
        # Try to project point in direction
        dist = 100
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

    async def _visit_poi(self, poi, decision):
        self.visited_pois.add(poi['id'])
        self.interesting_pois.append({'poi': poi, 'time': datetime.now()})
        
        # Record to memory
        self.path_memory.record_poi_visit(poi, {
            'visit_time': datetime.now().isoformat(),
            'notes': f"Visited via {decision.get('action')}"
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
