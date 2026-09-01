# ML 训练资产

- `data/`：可直接训练的 UrbanEV 小时级 CSV。
- `models/`：UrbanEV 岭回归模型、指标和预测结果。
- `src/`：C++ 训练/预测程序和 UrbanEV 转换脚本。
- `notebooks/`：保留给后续可视化或对比实验。

数据来自 UrbanEV 官方公开数据集。每个交通分析区被映射为一个虚拟充电站，区域内站点的充电桩数之和作为 `total_piles`。该映射仅用于演示，不能代表真实订单或单桩状态。
