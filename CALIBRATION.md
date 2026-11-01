# LiDAR-相机外参标定流程（MID360S + D455F）

> FAST-LIVO2 开启视觉融合（`img_en: 1`）前，需先标定雷达↔相机外参 `Rcl`/`Pcl`。
> 本文档记录用 FAST-Calib 完成标定的完整实操流程，面向本工程（Livox MID360S + RealSense D455F）。
>
> 根目录假设为 `/home/liu/ROS2-PX4-RW`，下文路径均基于此。

## 1. 坐标系约定（标定前必读）

| 坐标系 | 轴方向 |
|---|---|
| 雷达系（Livox 固件固化） | x **前**、y **左**、z **上**（右手系） |
| 相机系（REP 103 光学系 `camera_color_optical_frame`） | z **前**（光轴）、x **右**、y **下** |

`Pcl` = 雷达原点在**相机系**中的位置，三个分量沿相机系轴分解。尺量换算注意：**物理上方 → y 为负**（相机 y 向下）。

## 2. 前置准备

- **标定板**：官方 ArUco + 圆孔板（4 个 ArUco marker + 圆孔）；也可用 `scripts/camera_calibration.py --generate_board` 生成 ChArUco 板打印。
- **相机内参**：D455F color 848×480 的内参已填入 `config/qr_params.yaml`（取自 FAST-LIVO2 的 `config/camera_d455f.yaml`），无需重新标定相机。
- **img_time_offset**：已实测保持 `0.0`（两传感器时间戳基准一致），FAST-Calib 不标定时间偏移。
- **传感器出流**：启动 `ros2 launch fast_livo sensors_mid360s_d455f.launch.py` 后，确认 `/livox/lidar` 与 `/camera/color/image_raw` 都有数据。

## 3. 数据采集（每个场景重复）

每个场景 = 一段点云 bag + 一张同步彩色图。**至少 3 个场景**（正对、朝右、朝左）才能做多场景联合标定。

先启动传感器（雷达 + 相机）：

```bash
source /opt/ros/humble/setup.bash
source /home/liu/ROS2-PX4-RW/install/setup.bash
ros2 launch fast_livo sensors_mid360s_d455f.launch.py
```

对每个场景 `N`：

```bash
# 1. 录点云：必须录 20~30s（见 §8 踩坑），然后 Ctrl+C 停
ros2 bag record -o /home/liu/ROS2-PX4-RW/src/FAST-Calib_ROS2/calib_data/sceneN /livox/lidar

# 2. 拍一张彩色图（收到第一帧自动保存退出）
python3 /home/liu/ROS2-PX4-RW/src/FAST-Calib_ROS2/scripts/capture_image.py /home/liu/ROS2-PX4-RW/src/FAST-Calib_ROS2/calib_data/sceneN.png
```

**摆放要点**：

- 标定板放在雷达前方 **2.5~3m**（别超 3.5m）。
- 三个场景角度：正对（~0°）、朝右（绕竖直轴转 ~20°）、朝左（绕竖直轴转 ~24°）。
- 「朝左/朝右」是板子**绕竖直轴旋转**（像门开合），不是平移。

## 4. 配置 qr_params.yaml

每跑一个场景前，改 `config/qr_params.yaml` 的输入路径（其余参数保持）：

```yaml
bag_path:   "/home/liu/ROS2-PX4-RW/src/FAST-Calib_ROS2/calib_data/sceneN"
image_path: "/home/liu/ROS2-PX4-RW/src/FAST-Calib_ROS2/calib_data/sceneN.png"
```

- 相机内参（`fx/fy/cx/cy/k1/k2/p1/p2`）已填 D455F 值，**不要动**。
- 距离滤波 `x/y/z_min/max`：板子正对时用默认值；**朝左/朝右时要相应放宽 y 范围**，否则板子被滤掉。
- 标定板几何参数（`marker_size`、`delta_*`、`circle_radius`）用尺子量一下核对，尤其 `marker_size`。

## 5. 单场景标定

```bash
source /home/liu/ROS2-PX4-RW/install/setup.bash
ros2 launch fast_calib calib.launch.py rviz:=false   # 或 rviz:=true 看可视化
```

每个场景跑完，结果写入 `output/single_calib_result.txt`（含相机内参 + 该场景的 `Rcl`/`Pcl`）。检查圆孔是否全部被检出、残差是否 <6.5mm。

## 6. 多场景联合标定（3 个场景后）

```bash
ros2 launch fast_calib multi_calib.launch.py rviz:=false
```

联合结果写入 `output/multi_calib_result.txt`，格式为 FAST-LIVO2 的 `Rcl`（3×3 行优先）+ `Pcl`（3×1）。**这就是最终外参。**

## 7. 填入 FAST-LIVO2 并开启视觉融合

把 `multi_calib_result.txt` 里的 `Rcl`/`Pcl` 填到 `FAST-LIVO2/config/mid360s_d455f.yaml` 的对应字段，并把 `img_en` 改为 `1`：

```yaml
img_en: 1
Pcl: [  0.006417,  -0.099208,  -0.082262]
Rcl: [ -0.008950,  -0.999933,  -0.007385,
       0.214347,   0.005295,  -0.976743,
       0.976717,  -0.010325,   0.214285]
```

（上例为已完成的标定结果，RMSE 0.0056m。）

## 8. 踩坑经验

- **bag 必须录 20~30s**：6s 太短，非重复扫描打不满斜对的板子，圆孔只扫出半个 → 拟合半径约 0.06≈0.12/2 被拒。
- **朝左/朝右是旋转不是平移**：板子绕竖直轴转。角度判定：左右两列圆孔 x 差 ÷ 0.5 取 arcsin，30° 时 x 差≈0.25m。
- **角度别太大**：太大会漏检（远处圆孔与板外边界粘连成大簇），~20-25° 合适。
- **每场景前必须改 `bag_path`/`image_path`**：否则标定读旧数据，`circle_center_record.txt` 产生重复记录（multi_calib 只取最后 3 条）。
