# 统一地图服务管理器

import logging
from typing import List, Dict, Tuple, Optional, Any
import asyncio
from .amap_service import AmapService
from .osm_service import OSMService
from .region_detector import RegionDetector
from .coordinate_transformer import CoordinateTransformer

logger = logging.getLogger(__name__)

class MapServiceManager:
    """统一地图服务管理器 - 支持高德和OSM服务的统一接口"""
    
    def __init__(self):
        """初始化地图服务管理器"""
        self.amap_service = AmapService()
        self.osm_service = OSMService()
        self.region_detector = RegionDetector()
        self.coordinate_transformer = CoordinateTransformer()
        
        logger.info("地图服务管理器初始化完成")
    
    def detect_region_and_service(self, longitude: float, latitude: float) -> Dict[str, Any]:
        """
        检测区域类型并推荐地图服务
        
        Args:
            longitude: 经度
            latitude: 纬度
            
        Returns:
            区域检测结果
        """
        return self.region_detector.detect_region_type(longitude, latitude)
    
    def get_tile_url(self, service_type: str, z: int, x: int, y: int) -> str:
        """
        获取地图瓦片URL
        
        Args:
            service_type: 服务类型 ('amap' 或 'osm')
            z: 缩放级别
            x: 瓦片X坐标
            y: 瓦片Y坐标
            
        Returns:
            瓦片URL
        """
        try:
            if service_type == 'amap':
                # 高德地图瓦片URL模板
                return f"https://webrd01.is.autonavi.com/appmaptile?lang=zh_cn&size=1&scale=1&style=8&x={x}&y={y}&z={z}"
            elif service_type == 'osm':
                return self.osm_service.get_tile_url(z, x, y)
            else:
                logger.error(f"不支持的服务类型: {service_type}")
                return ""
        except Exception as e:
            logger.error(f"获取瓦片URL失败: {e}")
            return ""
    
    def get_poi_around(self, location: Tuple[float, float], radius: int = 1000, 
                      poi_type: str = '', service_type: Optional[str] = None) -> List[Dict]:
        """
        获取指定位置周围的POI
        
        Args:
            location: (纬度, 经度)
            radius: 搜索半径（米）
            poi_type: POI类型
            service_type: 指定服务类型，如果为None则自动选择
            
        Returns:
            POI列表
        """
        try:
            # 如果没有指定服务类型，自动检测
            if service_type is None:
                region_info = self.detect_region_and_service(location[1], location[0])
                service_type = region_info['map_service']
                logger.info(f"自动选择地图服务: {service_type} (区域: {region_info['region_name']})")
            
            # 确保坐标为WGS84格式
            wgs84_coords = self.coordinate_transformer.ensure_wgs84([location])
            if wgs84_coords:
                location = wgs84_coords[0]
            
            # 根据服务类型调用相应的服务
            if service_type == 'amap':
                return self.amap_service.get_poi_around(location, radius, poi_type)
            elif service_type == 'osm':
                return self.osm_service.get_poi_around(location, radius, poi_type)
            else:
                logger.error(f"不支持的服务类型: {service_type}")
                return []
                
        except Exception as e:
            logger.error(f"获取POI数据失败: {e}")
            return []
    
    def get_poi_in_polygon(self, polygon: List[Tuple[float, float]], 
                          poi_type: str = '', service_type: Optional[str] = None) -> List[Dict]:
        """
        获取多边形区域内的POI
        
        Args:
            polygon: 多边形顶点列表 [(纬度, 经度), ...]
            poi_type: POI类型
            service_type: 指定服务类型，如果为None则自动选择
            
        Returns:
            POI列表
        """
        try:
            if not polygon:
                return []
            
            # 如果没有指定服务类型，使用多边形中心点自动检测
            if service_type is None:
                center_lat = sum(lat for lat, lng in polygon) / len(polygon)
                center_lng = sum(lng for lat, lng in polygon) / len(polygon)
                region_info = self.detect_region_and_service(center_lng, center_lat)
                service_type = region_info['map_service']
                logger.info(f"自动选择地图服务: {service_type}")
            
            # 确保坐标为WGS84格式
            wgs84_polygon = self.coordinate_transformer.ensure_wgs84(polygon)
            
            # 根据服务类型调用相应的服务
            if service_type == 'amap':
                return self.amap_service.get_poi_in_polygon(wgs84_polygon, poi_type)
            elif service_type == 'osm':
                return self.osm_service.get_poi_in_polygon(wgs84_polygon, poi_type)
            else:
                logger.error(f"不支持的服务类型: {service_type}")
                return []
                
        except Exception as e:
            logger.error(f"获取多边形区域POI数据失败: {e}")
            return []
    
    async def get_poi_around_async(self, location: Tuple[float, float], 
                                  radius: int = 1000, poi_type: str = '', 
                                  service_type: Optional[str] = None) -> List[Dict]:
        """
        异步获取POI数据
        
        Args:
            location: (纬度, 经度)
            radius: 搜索半径（米）
            poi_type: POI类型
            service_type: 指定服务类型，如果为None则自动选择
            
        Returns:
            POI列表
        """
        try:
            # 如果没有指定服务类型，自动检测
            if service_type is None:
                region_info = self.detect_region_and_service(location[1], location[0])
                service_type = region_info['map_service']
                logger.info(f"异步自动选择地图服务: {service_type}")
            
            # 确保坐标为WGS84格式
            wgs84_coords = self.coordinate_transformer.ensure_wgs84([location])
            if wgs84_coords:
                location = wgs84_coords[0]
            
            # 根据服务类型调用相应的异步服务
            if service_type == 'amap':
                return await self.amap_service.get_poi_around_async(location, radius, poi_type)
            elif service_type == 'osm':
                return await self.osm_service.get_poi_around_async(location, radius, poi_type)
            else:
                logger.error(f"不支持的服务类型: {service_type}")
                return []
                
        except Exception as e:
            logger.error(f"异步获取POI数据失败: {e}")
            return []
    
    def get_recommended_service(self, longitude: float, latitude: float) -> str:
        """
        获取推荐的地图服务
        
        Args:
            longitude: 经度
            latitude: 纬度
            
        Returns:
            推荐的服务类型 ('amap' 或 'osm')
        """
        return self.region_detector.get_recommended_service(longitude, latitude)
    
    def is_domestic_region(self, longitude: float, latitude: float) -> bool:
        """
        判断是否为国内区域
        
        Args:
            longitude: 经度
            latitude: 纬度
            
        Returns:
            True表示国内，False表示国外
        """
        return self.region_detector.is_domestic_region(longitude, latitude)
    
    def transform_coordinates(self, coordinates: List[Tuple[float, float]], 
                            source_crs: str, target_crs: str) -> Dict[str, Any]:
        """
        坐标系转换
        
        Args:
            coordinates: 坐标点列表
            source_crs: 源坐标系
            target_crs: 目标坐标系
            
        Returns:
            转换结果
        """
        return self.coordinate_transformer.transform_coordinates(coordinates, source_crs, target_crs)
    
    def ensure_wgs84_coordinates(self, coordinates: List[Tuple[float, float]], 
                               source_crs: Optional[str] = None) -> List[Tuple[float, float]]:
        """
        确保坐标为WGS84格式
        
        Args:
            coordinates: 坐标列表
            source_crs: 源坐标系，如果为None则自动检测
            
        Returns:
            WGS84格式的坐标列表
        """
        return self.coordinate_transformer.ensure_wgs84(coordinates, source_crs)
    
    def calculate_distance(self, point1: Tuple[float, float], 
                          point2: Tuple[float, float], 
                          service_type: Optional[str] = None) -> float:
        """
        计算两点间距离
        
        Args:
            point1: 第一个点 (纬度, 经度)
            point2: 第二个点 (纬度, 经度)
            service_type: 服务类型，如果为None则自动选择
            
        Returns:
            距离（米）
        """
        try:
            # 如果没有指定服务类型，使用第一个点自动检测
            if service_type is None:
                region_info = self.detect_region_and_service(point1[1], point1[0])
                service_type = region_info['map_service']
            
            # 根据服务类型调用相应的距离计算方法
            if service_type == 'amap':
                return self.amap_service.calculate_distance(point1, point2)
            elif service_type == 'osm':
                return self.osm_service.calculate_distance(point1, point2)
            else:
                # 使用OSM服务的距离计算作为默认方法
                return self.osm_service.calculate_distance(point1, point2)
                
        except Exception as e:
            logger.error(f"计算距离失败: {e}")
            return 0.0
    
    def get_service_status(self) -> Dict[str, Any]:
        """
        获取各服务状态
        
        Returns:
            服务状态信息
        """
        status = {
            'amap': {
                'available': True,
                'api_key_configured': bool(self.amap_service.api_key),
                'service_name': '高德地图'
            },
            'osm': {
                'available': True,
                'api_key_configured': True,  # OSM不需要API密钥
                'service_name': 'OpenStreetMap'
            },
            'region_detector': {
                'available': True,
                'service_name': '区域检测器'
            },
            'coordinate_transformer': {
                'available': True,
                'service_name': '坐标转换器'
            }
        }
        
        return status
    
    def get_folium_tile_layer_config(self, service_type: str) -> Dict[str, Any]:
        """
        获取Folium地图瓦片图层配置
        
        Args:
            service_type: 服务类型 ('amap' 或 'osm')
            
        Returns:
            Folium瓦片图层配置
        """
        if service_type == 'amap':
            return {
                'tiles': 'https://webrd01.is.autonavi.com/appmaptile?lang=zh_cn&size=1&scale=1&style=8&x={x}&y={y}&z={z}',
                'attr': '高德地图',
                'name': '高德地图',
                'overlay': False,
                'control': True
            }
        elif service_type == 'osm':
            return {
                'tiles': 'OpenStreetMap',
                'attr': 'OpenStreetMap',
                'name': 'OpenStreetMap',
                'overlay': False,
                'control': True
            }
        else:
            # 默认返回OSM配置
            return {
                'tiles': 'OpenStreetMap',
                'attr': 'OpenStreetMap',
                'name': 'OpenStreetMap',
                'overlay': False,
                'control': True
            }