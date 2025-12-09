# 数据存储目录

此目录用于存储项目运行过程中产生的数据文件：

- `exploration_logs/` - 探索日志文件
- `poi_cache/` - POI数据缓存
- `mental_maps/` - AI心理地图数据
- `reports/` - 探索报告

## 文件结构

```
data/
├── exploration_logs/
│   ├── exploration_YYYYMMDD_HHMMSS.json
│   └── ...
├── poi_cache/
│   ├── region_HASH.json
│   └── ...
├── mental_maps/
│   ├── mental_map_YYYYMMDD_HHMMSS.json
│   └── ...
└── reports/
    ├── report_YYYYMMDD_HHMMSS.json
    └── ...
```

## 注意事项

- 所有数据文件都使用JSON格式存储
- 文件名包含时间戳以避免冲突
- 定期清理过期的缓存文件