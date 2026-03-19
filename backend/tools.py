from typing import List, Dict, Optional, Any
from langchain.tools import BaseTool, StructuredTool
from pydantic import BaseModel, Field

class ScanEnvironmentInput(BaseModel):
    pass

class MoveToPOIInput(BaseModel):
    poi_name: str = Field(..., description="The name of the POI to move to")

class ExploreDirectionInput(BaseModel):
    direction: float = Field(..., description="The direction to explore (0-360 degrees)")
    reason: str = Field(..., description="The reason for choosing this direction")

class ReselectStartPointInput(BaseModel):
    reason: str = Field("", description="Why reselecting the start point")

def get_exploration_tools(agent_instance) -> List[BaseTool]:
    """
    Get the list of tools for the exploration agent.
    
    Args:
        agent_instance: The ExplorerAgent instance containing state and logic methods.
    """
    
    async def scan_environment() -> str:
        """
        Scan the environment to find visible POIs and current status.
        Returns a description of the current location and visible POIs.
        """
        return await agent_instance.tool_scan_environment()

    async def move_to_poi(poi_name: str) -> str:
        """
        Move to a visible POI. Input the exact name of the POI.
        This tool includes path planning capabilities: it will automatically calculate and follow the shortest path along roads (if available) to reach the destination.
        """
        return await agent_instance.tool_move_to_poi(poi_name)

    async def explore_direction(direction: float, reason: str = "") -> str:
        """
        Explore in a specific direction (degrees).
        Use this when no interesting POIs are visible or to explore new areas.
        """
        return await agent_instance.tool_explore_direction(direction, reason)

    async def check_memory() -> str:
        """
        Check the exploration memory/status (visited POIs, path history).
        """
        return agent_instance.tool_check_memory()

    async def reselect_start_point(reason: str = "") -> str:
        """
        Reselect a new start point from unexplored POIs and continue exploration.
        Use this when you cannot find any POIs after many random moves.
        """
        return await agent_instance.tool_reselect_start_point(reason)

    return [
        StructuredTool.from_function(
            coroutine=scan_environment,
            name="scan_environment",
            description="Look around to see current location and visible POIs. Use this first to understand surroundings."
        ),
        StructuredTool.from_function(
            coroutine=move_to_poi,
            name="move_to_poi",
            description="Move to a visible POI. Includes automatic path planning along roads."
        ),
        StructuredTool.from_function(
            coroutine=explore_direction,
            name="explore_direction",
            description="Move in a specific direction (0-360). Use this if no interesting POIs are visible."
        ),
        StructuredTool.from_function(
            coroutine=reselect_start_point,
            name="reselect_start_point",
            description="Pick a random unexplored POI as a new start point and restart exploration there."
        ),
        StructuredTool.from_function(
            coroutine=check_memory,
            name="check_memory",
            description="Review what has been visited and the current exploration status."
        )
    ]
