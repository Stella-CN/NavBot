# C30D 硬件与控制依据

更新：2026-11-08。本文记录实车映射与参数来源；厂家示例只作硬件参考，NavBot行为以当前固件为准。

## 实车配置与标定状态

| 项目 | 当前信息 | 证据与限制 |
| --- | --- | --- |
| 主板 | C30D，STM32F407VET6 | 烧录及四路PWM/编码器已实测；具体PCB版本仍需实物留档 |
| 电机 | MG513P10-12V，GMR，减速比1:10 | 用户提供型号与规格；非独立计量结果 |
| 编码器 | 暂按500PPR×4×10=20000 counts/rev | 待标记输出轴多圈正反转验证，避免混淆线数与倍频后计数 |
| 轮位 | C左前、D左后、B右前、A右后 | 单轮点动及用户现场确认 |
| 前进极性 | 协议顺序C/D/B/A为+1/−1/−1/+1 | C/A电气正转向前，B/D向后；接线变化后重验 |
| 轮径/几何 | 85mm轮径，228mm轮距，134mm轴距 | V16.5 CAD名义值，待承载滚动半径/有效轮距标定 |
| 上位机 | Jetson Orin Nano，Python3串口工具 | 已执行真实串口运动测试；正式ROS及系统版本清单未交付 |
| IMU | ICM20948，WHO_AM_I=0xEA | 驱动与识别已实现；当前数据可靠性/姿态校准异常 |
| 供电 | 电机额定12V | 电池体系、BMS阈值、负载波形及欠压策略待确认 |

几何依据为[硬件1.2.0归档](../hardware/releases/1.2.0/README.md)内`NavBot-V16.5.FCStd`。轮安装基准为(±114, ±67, 42.4998)mm，CAD的Y为前后；不能将CAD轴直接等同于软件车体坐标。

## 引脚与电路

下表来自新版资源表、V2.2原理图及示例[S1–S3]，电机通道已在NavBot固件中实现并测试。固件映射见[c30d_motor.c](../deps/navbot_body/BSP/C30D/c30d_motor.c)。

| 功能 | MCU引脚 | 外设 |
| --- | --- | --- |
| 电机A | PB8、PB9 | TIM10_CH1、TIM11_CH1 |
| 电机B | PE5、PE6 | TIM9_CH1、CH2 |
| 电机C | PE9、PE11 | TIM1_CH1、CH2 |
| 电机D | PE13、PE14 | TIM1_CH3、CH4 |
| 编码器A | PA15、PB3 | TIM2_CH1、CH2 |
| 编码器B | PB4、PB5 | TIM3_CH1、CH2 |
| 编码器C | PB6、PB7 | TIM4_CH1、CH2 |
| 编码器D | PA0、PA1 | TIM5_CH1、CH2 |
| IMU | PB10、PB11、PB12 | SCL、SDA、INT |
| USB串口1 | PA9、PA10 | USART1 TX/RX，经CH9102F |
| USB串口3 | PD8、PD9 | USART3 TX/RX，经CH9102F |
| 蓝牙串口 | PD5、PD6 | USART2 TX/RX |
| 电池电压 | PB0 | ADC，100kΩ/10kΩ分压 |
| 使能开关 | PD3 | GPIO输入 |
| 用户按键 / LED | PE0 / PE8 | GPIO |
| SWD | PA13、PA14 | 调试接口 |
| CAN | PD0、PD1 | RX/TX，经板载收发器 |

## 当前控制与接口约束

- PWM为10kHz；四路编码器自由运行并做模差分，累计计数使用一致快照。电机基础API包含滑行/电气制动，运动服务停止时采用撤销PWM滑行。
- C30D执行500Hz独立PI及差速分解，同侧两轮目标相同。厂家示例的100Hz增量PI、A/B左侧与C/D右侧假设均不是NavBot当前配置。
- C/D逻辑PWM顺序不能由表格推断；方向以本车实测符号为准。软件所有权、限幅和保护见[运动协议](../deps/navbot_body/docs/motion-control.md)。
- USART3是运行通信口；USART1的DTR/RTS接入下载电路。Type-C供电口与数据口须按丝印区分，DAPLink不是运行数据串口。
- PD3只是软件输入，未验证为独立硬件断能。未实现通过串口上报电流/荷电状态；驱动ISEN电阻不等于MCU电流测量。
- 电压ADC引脚已定义，但当前STATUS无电压字段，不能据此宣称已交付欠压保护。

差速换算使用`v_left=vx-track*wz/2`、`v_right=vx+track*wz/2`，再除轮半径得到轮速。普通四轮滑移转向需要实测有效轮距；不直接继承厂家`轮距+轴距`系数。

## IMU实现与使用边界

当前通过软件I²C读取ICM20948六轴数据，配置±2g、±250°/s，转换为m/s²和rad/s；姿态算法执行静态陀螺仪偏置标定。未采用旧MPU6050 DMP路径，未使用磁力计提供绝对航向，不能照搬示例中的安装矩阵或角速度硬死区。

数据仍为芯片坐标；姿态是相对局部世界的估计，尚未完成芯片到车体安装变换。六轴Yaw长期会漂移。最新运动记录存在总线错误、间歇无效和姿态未就绪，根因尚未定位；历史无电机台架通过不代表当前整机通过。详见[实测与IMU审计](../deps/navbot_body/validation/rear-low-speed.txt)。

编码器用于轮速/行程换算，IMU用于惯性测量；当前未交付地图位姿或融合里程计。后续融合须检查新鲜度和有效性，完成外参及协方差标定，不能用加速度简单积分替代主要轮式速度。

## 厂家资料索引

本地资料不随仓库分发，资料根目录为`/Users/lvjiaqing/MyProjects/MyRobot/references/WHEELTEC L150PRO 多功能智能小车资料/WHEELTEC L150Pro 智能小车资料_V2.1_2026.04.20/`。另有参考代码`/Users/lvjiaqing/ForWork/vehicle-firmware`。以下为已分析的厂家材料定位，示例参数不等同于实车标定。

| 编号 | 文件与定位 |
| --- | --- |
| S1 | `9.原理图/C30D 原理图和资源分配表/STM32F407VET6控制器原理图（C30D_V2.2）.pdf`，第2页串口/IMU/开关，第3页电机/编码器/电压 |
| S2 | 同目录`STM32F407VET6(C30D-V2.1_V2.2)主板资源分配说明.pdf`；文件内标题仍标V2.0，需结合原理图使用 |
| S3 | `5.C30D V2.0基础实验例程/C30D V2.0基础例程.zip`，内部MOTOR、Encoder、PID、ICM20948示例 |
| S4 | `6.STM32源码/V2.0版主控代码/L150Pro_C30D(2.0)_小车STM32源码_GMR编码器_2025.11.14.zip`，`BALANCE/robot_select_init.c`与`balance.c` |
| S5 | `7.MPU6050_DMP移植教程(读取姿态角)/C30D_DMP读取MPU6050姿态.zip` |
