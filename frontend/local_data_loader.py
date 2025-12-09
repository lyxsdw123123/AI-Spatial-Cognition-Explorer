import geopandas as gpd
import os
import streamlit as st

def load_local_shapefile_data(region_name: str = "北京天安门"):
    """加载本地shapefile数据
    
    Args:
        region_name: 区域名称，用于确定数据文件夹路径
    """
    try:
        # 数据文件路径 - 根据区域名称动态确定
        data_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data', region_name)
        poi_file = os.path.join(data_dir, 'POI数据.shp')
        road_file = os.path.join(data_dir, '道路数据.shp')
        
        poi_success = False
        road_success = False
        formatted_pois = []
        road_data = []
        
        # 加载POI数据
        if os.path.exists(poi_file):
            try:
                # 设置环境变量以修复shapefile索引文件
                os.environ['SHAPE_RESTORE_SHX'] = 'YES'
                poi_gdf = gpd.read_file(poi_file, encoding='utf-8')
                for idx, row in poi_gdf.iterrows():
                    # 获取几何中心点坐标
                    centroid = row.geometry.centroid
                    formatted_poi = {
                        'name': row.get('name', f'POI_{idx}'),
                        'type': row.get('type', '未知'),
                        'location': [centroid.y, centroid.x],  # [lat, lng]
                        'address': row.get('address', '地址未知')
                    }
                    formatted_pois.append(formatted_poi)
                poi_success = True
                print(f"成功加载{region_name}的POI数据，共 {len(formatted_pois)} 个POI点")
            except Exception as e:
                print(f"加载{region_name}的POI数据失败: {str(e)}")
        
        # 加载道路数据
        if os.path.exists(road_file):
            try:
                # 设置环境变量以修复shapefile索引文件
                os.environ['SHAPE_RESTORE_SHX'] = 'YES'
                road_gdf = gpd.read_file(road_file, encoding='utf-8')
                for idx, row in road_gdf.iterrows():
                    # 获取道路几何坐标
                    if row.geometry.geom_type == 'LineString':
                        coords = [[coord[1], coord[0]] for coord in row.geometry.coords]  # [lat, lng]
                        road_data.append({
                            'name': row.get('name', f'Road_{idx}'),
                            'coordinates': coords
                        })
                    elif row.geometry.geom_type == 'MultiLineString':
                        for line in row.geometry.geoms:
                            coords = [[coord[1], coord[0]] for coord in line.coords]  # [lat, lng]
                            road_data.append({
                                'name': row.get('name', f'Road_{idx}'),
                                'coordinates': coords
                            })
                road_success = True
                print(f"成功加载{region_name}的道路数据，共 {len(road_data)} 条道路")
            except Exception as e:
                print(f"加载{region_name}的道路数据失败: {str(e)}")
        

        
        return {
            'poi_success': poi_success,
            'road_success': road_success,
            'pois': formatted_pois,
            'roads': road_data,
            'poi_file': poi_file,
            'road_file': road_file,
            'region_name': region_name
        }
        
    except Exception as e:
        print(f"加载{region_name}的本地数据失败: {str(e)}")
        return {
            'poi_success': False,
            'road_success': False,
            'pois': [],
            'roads': [],
            'error': str(e),
            'region_name': region_name
        }