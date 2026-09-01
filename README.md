# PKLOT ML（C++）

纯 C++17 的充电站负荷预测最小框架，无第三方运行时依赖：

```text
模拟小时数据 -> 特征工程 -> 岭回归 -> 1/6/24 小时预测
             -> 空闲桩估算 -> 低拥堵站点排序 -> JSON
```

## 构建

```bash
cmake -S . -B build
cmake --build build
./build/pklot_ml demo
```

## 使用

```bash
python3 ml/src/prepare_stations_database.py ml/data/stations_database.json ml/data/stations_hourly.csv
./build/pklot_ml train ml/data/stations_hourly.csv ml/models/stations_load_forecaster.txt ml/models/stations_metrics.json
./build/pklot_ml predict ml/data/stations_hourly.csv ml/models/stations_load_forecaster.txt ml/models/stations_predictions.json 45.302
python3 ml/src/export_predictions_sql.py ml/models/stations_predictions.json ml/models/stations_predictions.sql
```

`demo` 会在临时目录完成生成、训练和预测，是项目的端到端自检。

## 输入数据契约

后端尚未确定时，只依赖按“站点 × 小时”聚合的 CSV：

| 字段 | 类型 | 含义 |
|---|---|---|
| `timestamp_epoch` | 整数 | UTC Unix 时间戳，必须对齐小时 |
| `station_id` | 整数 | 充电站 ID |
| `total_piles` | 整数 | 站点充电桩总数 |
| `load_kw` | 浮点数 | 该小时负荷，团队需统一平均值或峰值口径 |
| `occupied_piles` | 整数，可选 | 占用桩数，仅用于分析 |

数据库确定后，只需把查询结果转换为以上字段，无需修改训练和预测逻辑。

## 输出

预测 JSON 包含：

- `horizon_hours`：`1`、`6`、`24`
- `predicted_load_kw`：预测负荷
- `predicted_available_piles`：预测空闲桩数
- `congestion_ratio`：预测拥堵率
- `recommended_station_ids`：未来 1 小时低拥堵站点排序

训练指标同时报告模型与“未来负荷等于当前负荷”的持续值基线。
`kw_per_pile` 默认 `7.0`；当前站点库预测使用全局平均单桩额定功率 `45.302`。

## 当前训练资产

`ml/` 中保存了当前可复现的训练资产：

- `ml/data/stations_database.json`：站点与充电桩目录快照。
- `ml/data/stations_hourly.csv`：由站点桩数和额定功率生成的模拟小时负载。
- `ml/models/`：训练好的模型、指标、评估报告、预测结果与 SQL 导出结果。
- `ml/src/prepare_stations_database.py`：从站点库重建训练集的标准库脚本。
- `ml/src/export_predictions_sql.py`：把预测 JSON 转成数据库导入 SQL。

重训命令：

```bash
python3 ml/src/prepare_stations_database.py ml/data/stations_database.json ml/data/stations_hourly.csv
./build/pklot_ml train ml/data/stations_hourly.csv ml/models/stations_load_forecaster.txt ml/models/stations_metrics.json
./build/pklot_ml predict ml/data/stations_hourly.csv ml/models/stations_load_forecaster.txt ml/models/stations_predictions.json 45.302
python3 ml/src/export_predictions_sql.py ml/models/stations_predictions.json ml/models/stations_predictions.sql
```

## 当前有意不做

- 不猜数据库表结构或后端接口。
- 不创建 HTTP 服务；等后端确定调用方式后再加。
- 不引入 XGBoost、LibTorch 等依赖；基线证明不足时再升级。
- 暂不加入节假日特征；等团队确定可靠数据来源。

