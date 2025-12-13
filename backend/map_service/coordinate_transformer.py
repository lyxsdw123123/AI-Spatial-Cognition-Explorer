# 坐标系转换器模块

import logging
from typing import List, Tuple, Dict, Any, Optional
import math

logger = logging.getLogger(__name__)

class CoordinateTransformer:
    """坐标系转换器 - 确保WGS84坐标系统一"""
    
    # 坐标系常量
    WGS84 = "EPSG:4326"  # WGS84地理坐标系
    GCJ02 = "GCJ02"      # 火星坐标系（中国偏移坐标系）
    BD09 = "BD09"        # 百度坐标系
    
    # 转换参数
    PI = math.pi
    X_PI = PI * 3000.0 / 180.0
    A = 6378245.0  # 长半轴
    EE = 0.00669342162296594323  # 偏心率平方
    
    @classmethod
    def transform_coordinates(cls, coordinates: List[Tuple[float, float]], 
                            source_crs: str, target_crs: str) -> Dict[str, Any]:
        """
        坐标系转换
        
        Args:
            coordinates: 坐标点列表 [(lat, lng), ...]
            source_crs: 源坐标系
            target_crs: 目标坐标系
            
        Returns:
            转换结果字典
        """
        try:
            if not coordinates:
                return {
                    'transformed_coordinates': [],
                    'success': True,
                    'message': '空坐标列表'
                }
            
            # 如果源坐标系和目标坐标系相同，直接返回
            if source_crs == target_crs:
                return {
                    'transformed_coordinates': coordinates,
                    'success': True,
                    'message': '坐标系相同，无需转换'
                }
            
            transformed_coords = []
            
            for lat, lng in coordinates:
                try:
                    # 根据转换类型选择相应的转换函数
                    if source_crs == cls.GCJ02 and target_crs == cls.WGS84:
                        new_lat, new_lng = cls._gcj02_to_wgs84(lat, lng)
                    elif source_crs == cls.WGS84 and target_crs == cls.GCJ02:
                        new_lat, new_lng = cls._wgs84_to_gcj02(lat, lng)
                    elif source_crs == cls.BD09 and target_crs == cls.WGS84:
                        # BD09 -> GCJ02 -> WGS84
                        gcj_lat, gcj_lng = cls._bd09_to_gcj02(lat, lng)
                        new_lat, new_lng = cls._gcj02_to_wgs84(gcj_lat, gcj_lng)
                    elif source_crs == cls.WGS84 and target_crs == cls.BD09:
                        # WGS84 -> GCJ02 -> BD09
                        gcj_lat, gcj_lng = cls._wgs84_to_gcj02(lat, lng)
                        new_lat, new_lng = cls._gcj02_to_bd09(gcj_lat, gcj_lng)
                    elif source_crs == cls.GCJ02 and target_crs == cls.BD09:
                        new_lat, new_lng = cls._gcj02_to_bd09(lat, lng)
                    elif source_crs == cls.BD09 and target_crs == cls.GCJ02:
                        new_lat, new_lng = cls._bd09_to_gcj02(lat, lng)
                    else:
                        # 不支持的转换类型，返回原坐标
                        logger.warning(f"不支持的坐标系转换: {source_crs} -> {target_crs}")
                        new_lat, new_lng = lat, lng
                    
                    transformed_coords.append((new_lat, new_lng))
                    
                except Exception as e:
                    logger.error(f"转换坐标 ({lat}, {lng}) 失败: {e}")
                    # 转换失败时保留原坐标
                    transformed_coords.append((lat, lng))
            
            return {
                'transformed_coordinates': transformed_coords,
                'success': True,
                'message': f'成功转换 {len(transformed_coords)} 个坐标点'
            }
            
        except Exception as e:
            logger.error(f"坐标系转换失败: {e}")
            return {
                'transformed_coordinates': coordinates,
                'success': False,
                'message': f'转换失败: {str(e)}'
            }
    
    @classmethod
    def _wgs84_to_gcj02(cls, lat: float, lng: float) -> Tuple[float, float]:
        """WGS84转GCJ02"""
        if cls._out_of_china(lat, lng):
            return lat, lng
        
        dlat = cls._transform_lat(lng - 105.0, lat - 35.0)
        dlng = cls._transform_lng(lng - 105.0, lat - 35.0)
        
        radlat = lat / 180.0 * cls.PI
        magic = math.sin(radlat)
        magic = 1 - cls.EE * magic * magic
        sqrtmagic = math.sqrt(magic)
        
        dlat = (dlat * 180.0) / ((cls.A * (1 - cls.EE)) / (magic * sqrtmagic) * cls.PI)
        dlng = (dlng * 180.0) / (cls.A / sqrtmagic * math.cos(radlat) * cls.PI)
        
        mglat = lat + dlat
        mglng = lng + dlng
        
        return mglat, mglng
    
    @classmethod
    def _gcj02_to_wgs84(cls, lat: float, lng: float) -> Tuple[float, float]:
        """GCJ02转WGS84"""
        if cls._out_of_china(lat, lng):
            return lat, lng
        
        dlat = cls._transform_lat(lng - 105.0, lat - 35.0)
        dlng = cls._transform_lng(lng - 105.0, lat - 35.0)
        
        radlat = lat / 180.0 * cls.PI
        magic = math.sin(radlat)
        magic = 1 - cls.EE * magic * magic
        sqrtmagic = math.sqrt(magic)
        
        dlat = (dlat * 180.0) / ((cls.A * (1 - cls.EE)) / (magic * sqrtmagic) * cls.PI)
        dlng = (dlng * 180.0) / (cls.A / sqrtmagic * math.cos(radlat) * cls.PI)
        
        mglat = lat - dlat
        mglng = lng - dlng
        
        return mglat, mglng
    
    @classmethod
    def _gcj02_to_bd09(cls, lat: float, lng: float) -> Tuple[float, float]:
        """GCJ02转BD09"""
        z = math.sqrt(lng * lng + lat * lat) + 0.00002 * math.sin(lat * cls.X_PI)
        theta = math.atan2(lat, lng) + 0.000003 * math.cos(lng * cls.X_PI)
        
        bd_lng = z * math.cos(theta) + 0.0065
        bd_lat = z * math.sin(theta) + 0.006
        
        return bd_lat, bd_lng
    
    @classmethod
    def _bd09_to_gcj02(cls, lat: float, lng: float) -> Tuple[float, float]:
        """BD09转GCJ02"""
        x = lng - 0.0065
        y = lat - 0.006
        z = math.sqrt(x * x + y * y) - 0.00002 * math.sin(y * cls.X_PI)
        theta = math.atan2(y, x) - 0.000003 * math.cos(x * cls.X_PI)
        
        gcj_lng = z * math.cos(theta)
        gcj_lat = z * math.sin(theta)
        
        return gcj_lat, gcj_lng
    
    @classmethod
    def _transform_lat(cls, lng: float, lat: float) -> float:
        """纬度转换"""
        ret = (-100.0 + 2.0 * lng + 3.0 * lat + 0.2 * lat * lat + 
               0.1 * lng * lat + 0.2 * math.sqrt(abs(lng)))
        ret += ((20.0 * math.sin(6.0 * lng * cls.PI) + 20.0 * math.sin(2.0 * lng * cls.PI)) * 2.0 / 3.0)
        ret += ((20.0 * math.sin(lat * cls.PI) + 40.0 * math.sin(lat / 3.0 * cls.PI)) * 2.0 / 3.0)
        ret += ((160.0 * math.sin(lat / 12.0 * cls.PI) + 320 * math.sin(lat * cls.PI / 30.0)) * 2.0 / 3.0)
        return ret
    
    @classmethod
    def _transform_lng(cls, lng: float, lat: float) -> float:
        """经度转换"""
        ret = (300.0 + lng + 2.0 * lat + 0.1 * lng * lng + 
               0.1 * lng * lat + 0.1 * math.sqrt(abs(lng)))
        ret += ((20.0 * math.sin(6.0 * lng * cls.PI) + 20.0 * math.sin(2.0 * lng * cls.PI)) * 2.0 / 3.0)
        ret += ((20.0 * math.sin(lng * cls.PI) + 40.0 * math.sin(lng / 3.0 * cls.PI)) * 2.0 / 3.0)
        ret += ((150.0 * math.sin(lng / 12.0 * cls.PI) + 300.0 * math.sin(lng / 30.0 * cls.PI)) * 2.0 / 3.0)
        return ret
    
    @classmethod
    def _out_of_china(cls, lat: float, lng: float) -> bool:
        """判断是否在中国境外"""
        return not (72.004 <= lng <= 137.8347 and 0.8293 <= lat <= 55.8271)
    
    @classmethod
    def ensure_wgs84(cls, coordinates: List[Tuple[float, float]], 
                    source_crs: Optional[str] = None) -> List[Tuple[float, float]]:
        """
        确保坐标为WGS84格式
        
        Args:
            coordinates: 坐标列表
            source_crs: 源坐标系，如果为None则自动检测
            
        Returns:
            WGS84格式的坐标列表
        """
        if not coordinates:
            return []
        
        # 如果没有指定源坐标系，尝试自动检测
        if source_crs is None:
            source_crs = cls._detect_coordinate_system(coordinates[0])
        
        # 如果已经是WGS84，直接返回
        if source_crs == cls.WGS84:
            return coordinates
        
        # 转换为WGS84
        result = cls.transform_coordinates(coordinates, source_crs, cls.WGS84)
        
        if result['success']:
            return result['transformed_coordinates']
        else:
            logger.warning(f"坐标转换失败，返回原坐标: {result['message']}")
            return coordinates
    
    @classmethod
    def _detect_coordinate_system(cls, coordinate: Tuple[float, float]) -> str:
        """
        自动检测坐标系类型（简单启发式方法）
        
        Args:
            coordinate: 单个坐标点 (lat, lng)
            
        Returns:
            检测到的坐标系类型
        """
        lat, lng = coordinate
        
        # 基于坐标范围的简单判断
        # 这是一个启发式方法，可能不够准确
        
        # 如果坐标明显超出正常地理范围，可能是投影坐标系
        if abs(lat) > 90 or abs(lng) > 180:
            logger.warning(f"坐标超出正常范围: ({lat}, {lng})")
            return cls.WGS84  # 默认返回WGS84
        
        # 中国境内的坐标，可能是GCJ02
        if (18 <= lat <= 54 and 73 <= lng <= 135):
            # 简单判断：如果坐标看起来像是偏移过的，可能是GCJ02
            # 这里使用一个非常简单的启发式方法
            return cls.GCJ02
        
        # 其他情况默认为WGS84
        return cls.WGS84
    
    @classmethod
    def validate_coordinates(cls, coordinates: List[Tuple[float, float]]) -> Dict[str, Any]:
        """
        验证坐标有效性
        
        Args:
            coordinates: 坐标列表
            
        Returns:
            验证结果
        """
        if not coordinates:
            return {
                'valid': True,
                'message': '空坐标列表',
                'invalid_coordinates': []
            }
        
        invalid_coords = []
        
        for i, (lat, lng) in enumerate(coordinates):
            if not (-90 <= lat <= 90 and -180 <= lng <= 180):
                invalid_coords.append({
                    'index': i,
                    'coordinate': (lat, lng),
                    'reason': '坐标超出有效范围'
                })
        
        return {
            'valid': len(invalid_coords) == 0,
            'message': f'发现 {len(invalid_coords)} 个无效坐标' if invalid_coords else '所有坐标有效',
            'invalid_coordinates': invalid_coords
        }