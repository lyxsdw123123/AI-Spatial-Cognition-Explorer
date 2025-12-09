#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
地图服务架构测试脚本
测试国内外地图切换、POI搜索和坐标转换功能
"""

import asyncio
import sys
import os

# 添加项目根目录到路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from map_service import MapServiceManager
from config.config import Config

class MapServiceTester:
    def __init__(self):
        self.manager = MapServiceManager()
        
    def test_region_detection(self):
        """测试区域检测功能"""
        print("=" * 50)
        print("测试区域检测功能")
        print("=" * 50)
        
        # 测试点：北京、纽约、伦敦、东京
        test_locations = [
            (116.4074, 39.9042, "北京"),  # 北京
            (-74.0060, 40.7128, "纽约"),  # 纽约
            (-0.1276, 51.5074, "伦敦"),   # 伦敦
            (139.6917, 35.6895, "东京"),  # 东京
            (114.0579, 22.5431, "香港"),  # 香港
            (121.5654, 25.0330, "台北"),  # 台北
        ]
        
        for lng, lat, name in test_locations:
            region_info = self.manager.detect_region_and_service(lng, lat)
            print(f"{name} ({lng}, {lat}):")
            print(f"  推荐服务: {region_info['map_service']}")
            print(f"  区域类型: {region_info['region_type']}")
            print(f"  区域名称: {region_info['region_name']}")
            print(f"  置信度: {region_info['confidence']}")
            print()
    
    def test_coordinate_transformation(self):
        """测试坐标转换功能"""
        print("=" * 50)
        print("测试坐标转换功能")
        print("=" * 50)
        
        # 测试坐标：北京天安门
        test_coords = [(39.9042, 116.4074)]
        
        # 测试各种坐标系转换
        transformations = [
            ("WGS84", "GCJ02"),
            ("GCJ02", "WGS84"),
            ("GCJ02", "BD09"),
            ("BD09", "GCJ02"),
        ]
        
        for source, target in transformations:
            try:
                result = self.manager.transform_coordinates(test_coords, source, target)
                print(f"{source} -> {target}: {test_coords[0]} -> {result[0]}")
            except Exception as e:
                print(f"{source} -> {target}: 转换失败 - {e}")
        
        print()
    
    async def test_poi_search(self):
        """测试POI搜索功能"""
        print("=" * 50)
        print("测试POI搜索功能")
        print("=" * 50)
        
        # 测试北京地区POI搜索（使用高德）
        beijing_location = (39.9042, 116.4074)
        print("测试北京地区POI搜索（高德地图）:")
        try:
            pois = await self.manager.get_poi_around_async(beijing_location, 1000, "餐饮")
            print(f"  找到 {len(pois)} 个餐饮POI")
            if pois:
                for i, poi in enumerate(pois[:3]):  # 显示前3个
                    print(f"    {i+1}. {poi.get('name', 'N/A')} - {poi.get('type', 'N/A')}")
        except Exception as e:
            print(f"  搜索失败: {e}")
        
        print()
        
        # 测试纽约地区POI搜索（使用OSM）
        nyc_location = (40.7128, -74.0060)
        print("测试纽约地区POI搜索（OSM）:")
        try:
            pois = await self.manager.get_poi_around_async(nyc_location, 1000, "restaurant")
            print(f"  找到 {len(pois)} 个餐厅POI")
            if pois:
                for i, poi in enumerate(pois[:3]):  # 显示前3个
                    print(f"    {i+1}. {poi.get('name', 'N/A')} - {poi.get('type', 'N/A')}")
        except Exception as e:
            print(f"  搜索失败: {e}")
        
        print()
    
    def test_tile_urls(self):
        """测试瓦片URL生成"""
        print("=" * 50)
        print("测试瓦片URL生成")
        print("=" * 50)
        
        # 测试瓦片坐标
        z, x, y = 10, 512, 384
        
        # 测试高德瓦片
        amap_url = self.manager.get_tile_url('amap', z, x, y)
        print(f"高德瓦片URL: {amap_url}")
        
        # 测试OSM瓦片
        osm_url = self.manager.get_tile_url('osm', z, x, y)
        print(f"OSM瓦片URL: {osm_url}")
        
        print()
    
    def test_folium_configs(self):
        """测试Folium配置"""
        print("=" * 50)
        print("测试Folium配置")
        print("=" * 50)
        
        # 测试高德配置
        amap_config = self.manager.get_folium_tile_layer_config('amap')
        print("高德地图Folium配置:")
        for key, value in amap_config.items():
            print(f"  {key}: {value}")
        
        print()
        
        # 测试OSM配置
        osm_config = self.manager.get_folium_tile_layer_config('osm')
        print("OSM地图Folium配置:")
        for key, value in osm_config.items():
            print(f"  {key}: {value}")
        
        print()
    
    def test_distance_calculation(self):
        """测试距离计算"""
        print("=" * 50)
        print("测试距离计算")
        print("=" * 50)
        
        # 北京到上海的距离
        beijing = (39.9042, 116.4074)
        shanghai = (31.2304, 121.4737)
        
        distance = self.manager.calculate_distance(beijing, shanghai)
        print(f"北京到上海距离: {distance:.2f} 米 ({distance/1000:.2f} 公里)")
        
        print()
    
    def test_service_status(self):
        """测试服务状态"""
        print("=" * 50)
        print("测试服务状态")
        print("=" * 50)
        
        status = self.manager.get_service_status()
        for service_name, service_info in status.items():
            print(f"{service_name}:")
            for key, value in service_info.items():
                print(f"  {key}: {value}")
            print()
    
    async def run_all_tests(self):
        """运行所有测试"""
        print("开始地图服务架构测试...")
        print()
        
        # 检查配置
        if not Config.AMAP_API_KEY:
            print("警告: 未配置高德地图API密钥，高德相关功能可能无法正常工作")
            print()
        
        # 运行各项测试
        self.test_service_status()
        self.test_region_detection()
        self.test_coordinate_transformation()
        await self.test_poi_search()
        self.test_tile_urls()
        self.test_folium_configs()
        self.test_distance_calculation()
        
        print("=" * 50)
        print("测试完成！")
        print("=" * 50)

async def main():
    """主函数"""
    tester = MapServiceTester()
    await tester.run_all_tests()

if __name__ == "__main__":
    asyncio.run(main())