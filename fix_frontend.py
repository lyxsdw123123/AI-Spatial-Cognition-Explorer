#!/usr/bin/env python
# -*- coding: utf-8 -*-

import re

def fix_frontend_app():
    """修复前端app.py文件中的本地数据加载逻辑"""
    
    # 读取原文件
    with open('frontend/app.py', 'r', encoding='utf-8') as f:
        content = f.read()
    
    # 查找并替换本地数据加载部分
    old_pattern = r'# 立即加载本地POI和道路数据.*?st\.session_state\.local_data_loaded = False'
    
    new_code = '''# 立即加载本地POI和道路数据
                if not hasattr(st.session_state, 'local_data_loaded') or not st.session_state.local_data_loaded:
                    with st.spinner("正在加载本地shapefile数据..."):
                        # 使用本地shapefile加载器
                        result = load_local_shapefile_data()
                        
                        if 'error' in result:
                            st.sidebar.error(f"❌ 加载本地数据时出错: {result['error']}")
                            st.session_state.local_data_loaded = False
                        else:
                            poi_success = result['poi_success']
                            road_success = result['road_success']
                            
                            if poi_success:
                                st.session_state.pois_data = result['pois']
                                st.sidebar.success(f"✅ 成功加载{len(result['pois'])}个本地POI")
                            else:
                                st.sidebar.error(f"❌ POI文件不存在: {result.get('poi_file', 'unknown')}")
                            
                            if road_success:
                                st.session_state.roads_data = result['roads']
                                st.sidebar.success(f"✅ 成功加载{len(result['roads'])}条道路")
                            else:
                                st.sidebar.error(f"❌ 道路文件不存在: {result.get('road_file', 'unknown')}")
                            
                            # 只有当POI和道路数据都加载成功时才标记为已加载
                            if poi_success and road_success:
                                st.session_state.local_data_loaded = True
                                st.sidebar.info("🗺️ 本地shapefile数据加载完成，地图将显示POI点和道路网络")
                            else:
                                st.session_state.local_data_loaded = False'''
    
    # 使用正则表达式替换
    new_content = re.sub(old_pattern, new_code, content, flags=re.DOTALL)
    
    # 如果没有找到匹配的内容，说明可能已经修改过了
    if new_content == content:
        print("未找到需要替换的内容，可能已经修改过了")
        return False
    
    # 写回文件
    with open('frontend/app.py', 'w', encoding='utf-8') as f:
        f.write(new_content)
    
    print("✅ 前端app.py文件修复完成")
    return True

if __name__ == "__main__":
    fix_frontend_app()