# 区域类型检测器模块

from typing import Tuple, Dict, Any
import logging

logger = logging.getLogger(__name__)

class RegionDetector:
    """区域类型检测器 - 判断坐标是否在国内"""
    
    # 中国大陆边界范围（粗略）
    CHINA_BOUNDS = {
        'min_lat': 18.0,   # 最南端（海南）
        'max_lat': 53.5,   # 最北端（黑龙江）
        'min_lng': 73.0,   # 最西端（新疆）
        'max_lng': 135.0   # 最东端（黑龙江）
    }
    
    # 港澳台地区边界
    HK_MACAO_TAIWAN_BOUNDS = [
        # 香港
        {'min_lat': 22.15, 'max_lat': 22.58, 'min_lng': 113.83, 'max_lng': 114.41},
        # 澳门
        {'min_lat': 22.11, 'max_lat': 22.22, 'min_lng': 113.52, 'max_lng': 113.60},
        # 台湾
        {'min_lat': 21.9, 'max_lat': 25.3, 'min_lng': 119.3, 'max_lng': 122.0}
    ]
    
    @classmethod
    def detect_region_type(cls, longitude: float, latitude: float) -> Dict[str, Any]:
        """
        检测坐标所在的区域类型
        
        Args:
            longitude: 经度
            latitude: 纬度
            
        Returns:
            Dict包含:
            - region_type: 'domestic' 或 'international'
            - map_service: 推荐的地图服务 'amap' 或 'osm'
            - region_name: 区域名称
            - confidence: 置信度 (0-1)
        """
        try:
            # 验证坐标有效性
            if not cls._is_valid_coordinate(longitude, latitude):
                logger.warning(f"无效坐标: ({longitude}, {latitude})")
                return {
                    'region_type': 'international',
                    'map_service': 'osm',
                    'region_name': '未知区域',
                    'confidence': 0.0
                }
            
            # 检查是否在中国大陆范围内
            if cls._is_in_china_mainland(longitude, latitude):
                return {
                    'region_type': 'domestic',
                    'map_service': 'amap',
                    'region_name': '中国大陆',
                    'confidence': 0.95
                }
            
            # 检查是否在港澳台地区
            hk_macao_taiwan_region = cls._is_in_hk_macao_taiwan(longitude, latitude)
            if hk_macao_taiwan_region:
                return {
                    'region_type': 'domestic',
                    'map_service': 'amap',
                    'region_name': hk_macao_taiwan_region,
                    'confidence': 0.90
                }
            
            # 其他地区视为国外
            return {
                'region_type': 'international',
                'map_service': 'osm',
                'region_name': '国外地区',
                'confidence': 0.85
            }
            
        except Exception as e:
            logger.error(f"区域检测失败: {e}")
            # 默认返回国外区域
            return {
                'region_type': 'international',
                'map_service': 'osm',
                'region_name': '检测失败',
                'confidence': 0.0
            }
    
    @classmethod
    def _is_valid_coordinate(cls, longitude: float, latitude: float) -> bool:
        """验证坐标是否有效"""
        return (
            -180.0 <= longitude <= 180.0 and
            -90.0 <= latitude <= 90.0
        )
    
    @classmethod
    def _is_in_china_mainland(cls, longitude: float, latitude: float) -> bool:
        """检查是否在中国大陆范围内"""
        bounds = cls.CHINA_BOUNDS
        return (
            bounds['min_lat'] <= latitude <= bounds['max_lat'] and
            bounds['min_lng'] <= longitude <= bounds['max_lng']
        )
    
    @classmethod
    def _is_in_hk_macao_taiwan(cls, longitude: float, latitude: float) -> str:
        """
        检查是否在港澳台地区
        
        Returns:
            区域名称或None
        """
        for i, bounds in enumerate(cls.HK_MACAO_TAIWAN_BOUNDS):
            if (bounds['min_lat'] <= latitude <= bounds['max_lat'] and
                bounds['min_lng'] <= longitude <= bounds['max_lng']):
                region_names = ['香港', '澳门', '台湾']
                return region_names[i]
        return None
    
    @classmethod
    def get_recommended_service(cls, longitude: float, latitude: float) -> str:
        """
        获取推荐的地图服务
        
        Args:
            longitude: 经度
            latitude: 纬度
            
        Returns:
            'amap' 或 'osm'
        """
        result = cls.detect_region_type(longitude, latitude)
        return result['map_service']
    
    @classmethod
    def is_domestic_region(cls, longitude: float, latitude: float) -> bool:
        """
        判断是否为国内区域
        
        Args:
            longitude: 经度
            latitude: 纬度
            
        Returns:
            True表示国内，False表示国外
        """
        result = cls.detect_region_type(longitude, latitude)
        return result['region_type'] == 'domestic'