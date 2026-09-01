# 站点库训练数据

`stations_database.json` 是站点与充电桩目录快照；`stations_hourly.csv` 是从该目录生成的模拟小时负载：

- 2,605 个有桩公共充电站，9 个无桩站点被跳过；
- 28 天连续小时；
- 1,750,560 条小时记录；
- 字段符合 `pklot_ml` 的 `timestamp_epoch,station_id,total_piles,load_kw` 契约。

注意：源文件没有真实小时负载，当前负载是可复现实验模拟数据，仅用于课程项目训练和联调。
