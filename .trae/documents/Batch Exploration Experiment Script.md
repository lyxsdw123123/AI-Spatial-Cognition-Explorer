我将在项目根目录下创建一个名为 `batch_exploration_experiment.py` 的 Python 脚本，用于自动化执行批量探索和评估任务。

### 脚本逻辑

1. **配置**：

   * 定义目标 15 个区域（已排除“晋中市榆次区”）。

   * 定义目标 6 个模型：`qwen`, `openai`, `deepseek`, `claude`, `gemini`, `zhipu`。

   * 设置 API 基础地址为 `http://localhost:8000`。

   * 设置核心参数：

     * 记忆模式 `memory_mode="raw"`（原始记忆）。

     * 探索模式 `exploration_mode="随机POI探索"`。

     * 提问方式 `question_strategy="Direct"`。

     * **最大轮次** **`max_rounds=1`**：确保探索在访问完所有 POI 一遍后立即停止，避免无限循环。

2. **辅助函数**：

   * `wait_for_status(endpoint, key, expected_value, timeout)`：轮询探索或评估的状态直到完成。

   * `get_region_bounds(region_name)`：调用 API 获取区域 POI 数据，计算边界框（Boundary）和起始位置（中心点）。

3. **主执行循环**：

   * 遍历每个 **区域 (Region)**：

     * 调用 `/exploration/switch_region` 切换区域。

     * 获取本地 POI 数据以计算边界和起点。

     * 遍历每个 **模型 (Model)**：

       * **初始化**：调用 `/exploration/init`。

         * 传入参数：`boundary`, `start_location`, `model_provider`, `memory_mode="raw"`, `use_local_data=True`。

         * **特别指定**：`max_rounds=1`，确保探索完一轮即止。

       * **开始探索**：调用 `/exploration/start`。

       * **监控进度**：轮询 `/exploration/status`。

         * 后端会自动检测当所有 POI 被访问后停止探索（`is_exploring` 变为 `False`）。

         * 脚本将等待此状态变化（设置合理的超时保护，如 30 分钟，以防地图过大）。

       * **停止探索**：调用 `/exploration/stop` 获取最终探索报告（如果尚未停止）。

       * **开始评估**：调用 `/evaluation/start`，设置策略为 `["Direct"]`。

       * **监控评估**：轮询 `/evaluation/status` 直到状态变为 `completed`。

       * **获取结果**：调用 `/evaluation/result` 获取评估详情。

       * **保存数据**：

         * 将指标（区域、模型、总正确率、5类问题的分类正确率）追加写入 `batch_experiment_results.csv`。

         * 将详细的 JSON/文本报告保存至 `experiment_reports/{region}_{model}_report.txt`。

4. **输出产物**：

   * `batch_experiment_results.csv`：汇总正确率数据。

   * `experiment_reports/`：包含详细报告的文件夹。

### 前置条件

* 后端服务 (`backend/app.py`) 必须处于运行状态。

* 必要的 API Key 需在环境配置中准备就绪。

* 不要修改已有的后端程序

