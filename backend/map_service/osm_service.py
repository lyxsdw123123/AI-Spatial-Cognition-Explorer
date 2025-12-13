# OpenStreetMap服务模块

import requests
import asyncio
import aiohttp
from typing import List, Dict, Tuple, Optional
import json
import logging

logger = logging.getLogger(__name__)

class OSMService:
    """OpenStreetMap服务类 - 提供国外地区的地图服务"""
    
    def __init__(self):
        # Nominatim API用于地理编码和POI搜索
        self.nominatim_base_url = "https://nominatim.openstreetmap.org"
        # Overpass API用于复杂的POI查询
        self.overpass_base_url = "https://overpass-api.de/api/interpreter"
        # OSM瓦片服务器
        self.tile_base_url = "https://tile.openstreetmap.org"
        
        # 请求头，遵循OSM使用政策
        self.headers = {
            'User-Agent': 'AI_Explorer_Map_Service/1.0'
        }
    
    def get_tile_url(self, z: int, x: int, y: int) -> str:
        """
        获取OSM瓦片URL
        
        Args:
            z: 缩放级别
            x: 瓦片X坐标
            y: 瓦片Y坐标
            
        Returns:
            瓦片URL
        """
        return f"{self.tile_base_url}/{z}/{x}/{y}.png"
    
    def get_poi_around(self, location: Tuple[float, float], radius: int = 1000, 
                      poi_type: str = '') -> List[Dict]:
        """
        获取指定位置周围的POI
        
        Args:
            location: (纬度, 经度)
            radius: 搜索半径（米）
            poi_type: POI类型（amenity, shop, tourism等）
            
        Returns:
            POI列表
        """
        try:
            # 使用Overpass API查询POI
            query = self._build_overpass_query(location, radius, poi_type)
            
            response = requests.post(
                self.overpass_base_url,
                data=query,
                headers=self.headers,
                timeout=30
            )
            
            if response.status_code == 200:
                data = response.json()
                return self._format_overpass_pois(data.get('elements', []))
            else:
                logger.error(f"Overpass API错误: {response.status_code}")
                return []
                
        except Exception as e:
            logger.error(f"获取OSM POI数据失败: {e}")
            return []
    
    def get_poi_in_polygon(self, polygon: List[Tuple[float, float]], 
                          poi_type: str = '') -> List[Dict]:
        """
        获取多边形区域内的POI
        
        Args:
            polygon: 多边形顶点列表 [(纬度, 经度), ...]
            poi_type: POI类型
            
        Returns:
            POI列表
        """
        try:
            # 构建多边形查询
            query = self._build_polygon_overpass_query(polygon, poi_type)
            
            response = requests.post(
                self.overpass_base_url,
                data=query,
                headers=self.headers,
                timeout=30
            )
            
            if response.status_code == 200:
                data = response.json()
                return self._format_overpass_pois(data.get('elements', []))
            else:
                logger.error(f"Overpass API错误: {response.status_code}")
                return []
                
        except Exception as e:
            logger.error(f"获取多边形区域POI数据失败: {e}")
            return []
    
    def _build_overpass_query(self, location: Tuple[float, float], 
                             radius: int, poi_type: str = '') -> str:
        """构建Overpass API查询语句"""
        lat, lng = location
        
        # 基础查询模板
        if poi_type:
            # 指定类型的POI
            query_template = f"""
            [out:json][timeout:25];
            (
              node["{poi_type}"](around:{radius},{lat},{lng});
              way["{poi_type}"](around:{radius},{lat},{lng});
              relation["{poi_type}"](around:{radius},{lat},{lng});
            );
            out center meta;
            """
        else:
            # 所有常见POI类型
            common_types = ['amenity', 'shop', 'tourism', 'leisure', 'historic']
            type_queries = []
            for ptype in common_types:
                type_queries.extend([
                    f'node["{ptype}"](around:{radius},{lat},{lng});',
                    f'way["{ptype}"](around:{radius},{lat},{lng});'
                ])
            
            query_template = f"""
            [out:json][timeout:25];
            (
              {chr(10).join(type_queries)}
            );
            out center meta;
            """
        
        return query_template
    
    def _build_polygon_overpass_query(self, polygon: List[Tuple[float, float]], 
                                     poi_type: str = '') -> str:
        """构建多边形区域的Overpass查询"""
        # 将多边形转换为Overpass格式
        poly_coords = ' '.join([f"{lat} {lng}" for lat, lng in polygon])
        
        if poi_type:
            query_template = f"""
            [out:json][timeout:25];
            (
              node["{poi_type}"](poly:"{poly_coords}");
              way["{poi_type}"](poly:"{poly_coords}");
            );
            out center meta;
            """
        else:
            common_types = ['amenity', 'shop', 'tourism', 'leisure', 'historic']
            type_queries = []
            for ptype in common_types:
                type_queries.extend([
                    f'node["{ptype}"](poly:"{poly_coords}");',
                    f'way["{ptype}"](poly:"{poly_coords}");\n'
                ])
            
            query_template = f"""
            [out:json][timeout:25];
            (
              {chr(10).join(type_queries)}
            );
            out center meta;
            """
        
        return query_template
    
    def _format_overpass_pois(self, elements: List[Dict]) -> List[Dict]:
        """格式化Overpass API返回的POI数据"""
        formatted_pois = []
        
        for element in elements:
            try:
                # 获取坐标
                if element.get('type') == 'node':
                    lat = element.get('lat')
                    lng = element.get('lon')
                elif element.get('type') in ['way', 'relation']:
                    # 对于way和relation，使用center坐标
                    center = element.get('center', {})
                    lat = center.get('lat')
                    lng = center.get('lon')
                else:
                    continue
                
                if lat is None or lng is None:
                    continue
                
                tags = element.get('tags', {})
                
                # 获取POI名称
                name = (tags.get('name') or 
                       tags.get('name:en') or 
                       tags.get('brand') or 
                       '未命名POI')
                
                # 确定POI类型
                poi_type = self._determine_poi_type(tags)
                
                # 获取地址信息
                address_parts = []
                for addr_key in ['addr:housenumber', 'addr:street', 'addr:city']:
                    if tags.get(addr_key):
                        address_parts.append(tags[addr_key])
                address = ', '.join(address_parts) if address_parts else ''
                
                formatted_poi = {
                    'id': f"osm_{element.get('type')}_{element.get('id')}",
                    'name': name,
                    'type': poi_type,
                    'typecode': tags.get('amenity') or tags.get('shop') or tags.get('tourism', ''),
                    'address': address,
                    'location': [lat, lng],
                    'distance': 0,  # 需要单独计算
                    'tel': tags.get('phone', ''),
                    'website': tags.get('website', ''),
                    'opening_hours': tags.get('opening_hours', ''),
                    'tags': tags  # 保留原始标签信息
                }
                
                formatted_pois.append(formatted_poi)
                
            except Exception as e:
                logger.warning(f"格式化OSM POI数据时出错: {e}")
                continue
        
        return formatted_pois
    
    def _determine_poi_type(self, tags: Dict) -> str:
        """根据OSM标签确定POI类型"""
        # 优先级顺序检查不同的标签
        type_mapping = {
            'amenity': {
                'restaurant': '餐厅',
                'cafe': '咖啡厅',
                'bank': '银行',
                'hospital': '医院',
                'school': '学校',
                'university': '大学',
                'library': '图书馆',
                'pharmacy': '药店',
                'fuel': '加油站',
                'parking': '停车场',
                'post_office': '邮局',
                'police': '警察局',
                'fire_station': '消防站',
                'place_of_worship': '宗教场所'
            },
            'shop': {
                'supermarket': '超市',
                'convenience': '便利店',
                'clothes': '服装店',
                'bakery': '面包店',
                'butcher': '肉店',
                'electronics': '电子产品店',
                'bookshop': '书店',
                'pharmacy': '药店'
            },
            'tourism': {
                'hotel': '酒店',
                'attraction': '景点',
                'museum': '博物馆',
                'information': '游客信息',
                'viewpoint': '观景点'
            },
            'leisure': {
                'park': '公园',
                'playground': '游乐场',
                'sports_centre': '体育中心',
                'swimming_pool': '游泳池'
            },
            'historic': {
                'monument': '纪念碑',
                'castle': '城堡',
                'ruins': '遗址'
            }
        }
        
        for category, subtypes in type_mapping.items():
            if category in tags:
                subtype = tags[category]
                return subtypes.get(subtype, f"{category}:{subtype}")
        
        # 如果没有匹配到，返回第一个可用的标签
        for key, value in tags.items():
            if key not in ['name', 'name:en', 'addr:street', 'addr:city']:
                return f"{key}:{value}"
        
        return '未知类型'
    
    async def get_poi_around_async(self, location: Tuple[float, float], 
                                  radius: int = 1000, poi_type: str = '') -> List[Dict]:
        """异步获取POI数据"""
        try:
            query = self._build_overpass_query(location, radius, poi_type)
            
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    self.overpass_base_url,
                    data=query,
                    headers=self.headers,
                    timeout=30
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        formatted_pois = self._format_overpass_pois(data.get('elements', []))
                        logger.info(f"成功获取{len(formatted_pois)}个OSM POI")
                        return formatted_pois
                    else:
                        logger.error(f"Overpass API错误: {response.status}")
                        return []
                        
        except asyncio.TimeoutError:
            logger.error("OSM API请求超时")
            return []
        except Exception as e:
            logger.error(f"异步获取OSM POI数据失败: {e}")
            return []
    
    def calculate_distance(self, point1: Tuple[float, float], 
                          point2: Tuple[float, float]) -> float:
        """
        计算两点间距离（米）
        使用Haversine公式
        """
        import math
        
        lat1, lng1 = point1
        lat2, lng2 = point2
        
        # 转换为弧度
        lat1_rad = math.radians(lat1)
        lng1_rad = math.radians(lng1)
        lat2_rad = math.radians(lat2)
        lng2_rad = math.radians(lng2)
        
        # Haversine公式
        dlat = lat2_rad - lat1_rad
        dlng = lng2_rad - lng1_rad
        
        a = (math.sin(dlat/2)**2 + 
             math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(dlng/2)**2)
        c = 2 * math.asin(math.sqrt(a))
        
        # 地球半径（米）
        earth_radius = 6371000
        
        return earth_radius * c