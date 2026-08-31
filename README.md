# PKLOT ML

充电站负荷预测的最小可运行框架。当前不依赖数据库和后端接口，先用模拟小时数据完成：

```text
模拟数据 -> 特征工程 -> 1/6/24 小时直接预测 -> 空闲桩估算 -> 低拥堵站点排序 -> JSON
```

## 快速开始

要求 Python 3.10+：

```bash
python -m venv .venv
python -m pip install -r requirements.txt
python ml.py demo
```

生成可保留的结果：

```bash
python ml.py generate --days 90 --stations 3
python ml.py train
python ml.py predict
```

生成文件默认位于 `data/`、`models/` 和 `outputs/`，均不提交到 Git。

## 输入数据契约

后端未确定前，训练入口只依赖一张按“站点 × 小时”聚合的表：

| 字段 | 类型 | 含义 |
|---|---|---|
| `timestamp` | ISO 8601 时间 | 小时起点，建议 UTC |
| `station_id` | 整数 | 充电站 ID |
| `total_piles` | 整数 | 站点充电桩总数 |
| `load_kw` | 浮点数 | 该小时平均或峰值负荷，团队需统一口径 |
| `occupied_piles` | 整数，可选 | 该小时占用桩数，仅用于分析 |

数据库确定后，只需将查询结果转换为这些列，无需改训练和预测逻辑。

## 输出约定

`predict` 输出 JSON，核心字段为：

- `horizon_hours`: `1`、`6` 或 `24`
- `predicted_load_kw`: 预测负荷
- `predicted_available_piles`: 预测空闲桩数
- `congestion_ratio`: 预测拥堵率
- `recommended_station_ids`: 未来 1 小时低拥堵站点排序

`train` 的评估结果同时包含模型和“未来负荷等于当前负荷”的持续值基线，避免只报模型分数而无法判断是否真正提升。

`--kw-per-pile` 默认 `7.0`，应在明确实际充电桩功率后调整。

## 当前有意不做

- 不创建 FastAPI/Flask 服务：等后端确定调用方式后再加。
- 不猜 MySQL 表结构：由后端提供查询或导出适配。
- 不上 LSTM/XGBoost：先用基线评估证明复杂模型有收益。
- 暂不加入节假日特征：等团队确定节假日数据来源。

