# 地图服务相关API端点

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Dict, Tuple, Optional, Any
import logging
from datetime import datetime

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.map_service import MapServiceManager

logger = logging.getLogger(__name__)

# 创建路由器
router = APIRouter(prefix="/map", tags=["地图服务"])

# 初始化地图服务管理器
map_service_manager = MapServiceManager()

# 数据模型
class LocationModel(BaseModel):
    latitude: float
    longitude: float

class RegionDetectionModel(BaseModel):
    location: LocationModel

class CoordinateTransformModel(BaseModel):
    coordinates: List[LocationModel]
    source_crs: str
    target_crs: str

class ServiceStatusModel(BaseModel):
    service_type: Optional[str] = None

@router.get("/status")
async def get_service_status():
    """获取地图服务状态"""
    try:
        status = map_service_manager.get_service_status()
        return {
            "success": True,
            "data": status
        }
    except Exception as e:
        logger.error(f"获取服务状态失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/detect-region")
async def detect_region(request: RegionDetectionModel):
    """检测区域类型并推荐地图服务"""
    try:
        location = request.location
        region_info = map_service_manager.detect_region_and_service(
            location.longitude, location.latitude
        )
        return {
            "success": True,
            "data": region_info
        }
    except Exception as e:
        logger.error(f"区域检测失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/tile/{service_type}/{z}/{x}/{y}")
async def get_tile_url(service_type: str, z: int, x: int, y: int):
    """获取地图瓦片URL"""
    try:
        if service_type not in ['amap', 'osm']:
            raise HTTPException(status_code=400, detail="不支持的服务类型")
        
        tile_url = map_service_manager.get_tile_url(service_type, z, x, y)
        return {
            "success": True,
            "data": {
                "tile_url": tile_url,
                "service_type": service_type,
                "coordinates": {"z": z, "x": x, "y": y}
            }
        }
    except Exception as e:
        logger.error(f"获取瓦片URL失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/tile-config/{service_type}")
async def get_tile_config(service_type: str):
    """获取Folium地图瓦片配置"""
    try:
        if service_type not in ['amap', 'osm']:
            raise HTTPException(status_code=400, detail="不支持的服务类型")
        
        config = map_service_manager.get_folium_tile_layer_config(service_type)
        return {
            "success": True,
            "data": config
        }
    except Exception as e:
        logger.error(f"获取瓦片配置失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/transform-coordinates")
async def transform_coordinates(request: CoordinateTransformModel):
    """坐标系转换"""
    try:
        # 将LocationModel转换为元组列表
        coordinates = [(loc.latitude, loc.longitude) for loc in request.coordinates]
        
        result = map_service_manager.transform_coordinates(
            coordinates, request.source_crs, request.target_crs
        )
        return {
            "success": True,
            "data": result
        }
    except Exception as e:
        logger.error(f"坐标转换失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/ensure-wgs84")
async def ensure_wgs84_coordinates(coordinates: List[LocationModel]):
    """确保坐标为WGS84格式"""
    try:
        # 将LocationModel转换为元组列表
        coord_tuples = [(loc.latitude, loc.longitude) for loc in coordinates]
        
        wgs84_coords = map_service_manager.ensure_wgs84_coordinates(coord_tuples)
        
        # 转换回LocationModel格式
        result_coords = [
            {"latitude": lat, "longitude": lng} 
            for lat, lng in wgs84_coords
        ]
        
        return {
            "success": True,
            "data": result_coords,
            "count": len(result_coords)
        }
    except Exception as e:
        logger.error(f"WGS84坐标转换失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/calculate-distance")
async def calculate_distance(point1: LocationModel, point2: LocationModel, 
                           service_type: Optional[str] = None):
    """计算两点间距离"""
    try:
        p1 = (point1.latitude, point1.longitude)
        p2 = (point2.latitude, point2.longitude)
        
        distance = map_service_manager.calculate_distance(p1, p2, service_type)
        
        return {
            "success": True,
            "data": {
                "distance_meters": distance,
                "distance_km": distance / 1000,
                "service_type": service_type or "auto"
            }
        }
    except Exception as e:
        logger.error(f"距离计算失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/recommended-service")
async def get_recommended_service(longitude: float, latitude: float):
    """获取推荐的地图服务"""
    try:
        service_type = map_service_manager.get_recommended_service(longitude, latitude)
        is_domestic = map_service_manager.is_domestic_region(longitude, latitude)
        
        return {
            "success": True,
            "data": {
                "recommended_service": service_type,
                "is_domestic": is_domestic,
                "location": {
                    "longitude": longitude,
                    "latitude": latitude
                }
            }
        }
    except Exception as e:
        logger.error(f"获取推荐服务失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/health")
async def health_check():
    """健康检查"""
    try:
        status = map_service_manager.get_service_status()
        
        # 检查各服务是否可用
        all_available = all(
            service_info.get('available', False) 
            for service_info in status.values()
        )
        
        return {
            "success": True,
            "healthy": all_available,
            "services": status,
            "timestamp": str(datetime.now())
        }
    except Exception as e:
        logger.error(f"健康检查失败: {e}")
        return {
            "success": False,
            "healthy": False,
            "error": str(e),
            "timestamp": str(datetime.now())
        }