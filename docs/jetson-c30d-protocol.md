# Jetson 与 C30D 通信及使用

更新：2026-11-08。适用于主仓库锁定的固件 **1.1.2**，线上帧 `version=1`。本文替代早期设计草案；精确运动字段、状态和限制见[固件运动协议](../deps/navbot_body/docs/motion-control.md)，编码解码见 [chassis_serial.py](../deps/navbot_body/tools/chassis_serial.py)。

## 当前链路

Jetson通过USB连接C30D的USART3，发送独立轮速或车体速度；C30D执行500 Hz四轮闭环并返回编码器数据。Jetson工具根据轮速与名义几何计算车体速度，尚未实现ROS话题、里程计积分、TF/EKF或导航节点。

- 串口：460800 baud、8N1、无流控。DAPLink用于SWD，不作为数据串口。
- 当前设备稳定路径：`/dev/serial/by-id/usb-1a86_USB_Single_Serial_5A6D001621-if00`。更换设备后应重新确认，不能假定永远是`ttyACM0`。
- 二进制小端、定宽整数和IEEE754 float32；帧长`24+payload_len`，payload最多256字节，CRC16/CCITT-FALSE覆盖version至payload末尾。
- 帧头依次为`5A A5`、version:u8、msg_id:u8、payload_len:u16、seq:u32、session:u32、timestamp_us:u64，随后payload与CRC:u16。
- MCU时间单位µs、分辨率1ms；轮速/控制状态使用控制采样时间，IMU使用读事务起始时间。时间查询已实现，但ROS时钟映射精度未验收。

## 当前消息

| ID | 方向 / 频率 | 实际用途 |
| --- | --- | --- |
| 0x01 HELLO | 双向，建链 | 固件/能力/启动标识/频率；新会话强制停止旧运动 |
| 0x02 TIME_SYNC | 双向，按需 | 主机和MCU时间查询，不能直接当作已同步的ROS时间 |
| 0x10 CMD_VEL | 下行，工具约50 Hz | `vx:f32,wz:f32,valid_ms:u16`；m/s、rad/s；不支持vy |
| 0x11 SET_ENABLE | 下行，按需 | `enabled:u8`；0等同STOP |
| 0x12 STOP | 下行，按需 | 空payload；立即切PWM并撤销许可 |
| 0x14 CMD_WHEELS | 下行，按需 | `omega:f32[4],valid_ms:u16`；rad/s |
| 0x20 WHEEL_STATE | 上行，100 Hz | `count:i64[4],omega:f32[4],valid:u32`；轮速是最新2ms样本 |
| 0x21 IMU_RAW | 上行，100 Hz | `valid:u32,gyro:f32[3],accel:f32[3]`；rad/s、m/s²，保留重力响应 |
| 0x22 ATTITUDE | 上行，50 Hz | `valid:u32,q:f32[4]`；四元数x/y/z/w |
| 0x23 STATUS | 上行，10 Hz | 电机许可、有效性、IMU健康/校准、通信及恢复计数 |
| 0x24 MOTION_STATE | 上行，100 Hz | 状态、故障、执行序号/指令年龄、目标/斜坡轮速、PWM |
| 0x31 CONFIG_GEOMETRY | 下行，按需 | `radius:f32,track:f32,sign:i8[4]`；仅Disabled可修改，RAM配置 |
| 0x7F ACK | 上行，响应请求 | `request_seq:u32,request_id:u8,result:u8` |

`0x13`清故障当前返回状态禁止；`0x30 CONFIG_GET`、通用参数事务、Flash持久化配置未实现。STATUS没有电压、电流、荷电百分比或已验证硬件急停状态，不应沿用旧草案的字段解释。

协议轮序为 **C左前、D左后、B右前、A右后**。配置前为电气方向；配置后按逻辑前进方向使用目标与反馈。本车已确认sign为`[1,-1,-1,1]`，更换接线后需重验。

## 数据有效性与车体速度

接收端检查CRC、会话、序号、时间戳与有效位：轮状态`valid==15`表示四轮有效；IMU/姿态须各自`valid==1`。不能因为收到报文，就把旧样本或无效数据当作测量。主机重连使用新会话；MCU重启或方向配置变化后重建累计计数基线。

设协议轮速为`ωLF,ωLR,ωRF,ωRR`：

```text
v_left  = radius × (ωLF + ωLR) / 2
v_right = radius × (ωRF + ωRR) / 2
vx = (v_left + v_right) / 2
wz = (v_right - v_left) / track
```

当前radius=0.0425m、track=0.228m是CAD初值，编码器暂按20000 counts/rev；换算结果不是已标定的落地车速。

**IMU尚未通过当前实机验收。** 最新后退记录0x21共463帧、334有效，0x22共231帧全部无效，存在总线错误与恢复记录。原始IMU是单位转换后的六轴量，不是芯片整数；姿态参考芯片轴与局部世界坐标，尚无安装变换和绝对航向约束。详见[最新实测与IMU审计](../deps/navbot_body/validation/rear-low-speed.txt)。

## 速度命令与停止

1. HELLO建立会话并检查固件能力；STOP并等待执行确认。
2. Disabled状态配置名义几何与实测方向，显式使能。
3. 持续发送新鲜速度指令，工具约50 Hz；`valid_ms`允许50～250ms，通常200ms。使能后首命令窗口也是200ms。
4. ACK=0表示入队或STOP切输出，不表示轮速已达到目标；管理请求还应等待0x24的匹配执行结果。
5. 上位机回调桥接器检查源数据年龄，超过150ms停发旧速度并STOP；不能把旧消息反复续期。

实际状态是`Disabled / Enabled / Timeout / Fault`。超时、STOP或故障立即撤销PWM并滑行；普通零目标使用斜坡。超时后需STOP确认、显式使能和新速度；故障锁定需排查后复位初始化。复位不恢复RAM配置和旧运动。软件停止不承诺机械瞬停。

当前命令范围：轮速±12rad/s、vx±0.3m/s、wz±1.5rad/s，输出PWM≤20%。范围校验不代表整个范围已经在负载下验证。

## Jetson 获取与测试数据

已部署工具目录为`/home/stella/navbot-motion/tools/`，依赖Python3与pyserial。串口由单个进程统一收发；采集与运动工具不能同时占用。新会话会停止旧运动，采集工具不应作为运动进程旁路打开第二个连接。

静止遥测验证，不使能电机：

```sh
python3 /home/stella/navbot-motion/tools/chassis_serial.py \
  --port /dev/serial/by-id/usb-1a86_USB_Single_Serial_5A6D001621-if00 \
  --seconds 10 \
  --output /home/stella/navbot-motion/results/telemetry-check
```

工具先等待姿态就绪，成功后保存`frames.jsonl`逐帧记录和`report.json`验证报告；IMU未就绪可能提前失败，此时以报告错误为准。不要添加旧台架专用`--test`；运动协议边界检查使用`motion_protocol_test.py`。

已确认架空、允许电机旋转时，可执行短时车体速度测试：

```sh
python3 /home/stella/navbot-motion/tools/motion_host.py \
  --port /dev/serial/by-id/usb-1a86_USB_Single_Serial_5A6D001621-if00 \
  --mode body --signs 1 -1 -1 1 --vx 0 --wz 0.6 \
  --seconds 3 --timeout \
  --output /home/stella/navbot-motion/results/body-turn.json
```

该命令会驱动电机；结束后检查命令超时并发送STOP。`--seconds`是发送指令的时长，使用`--timeout`时另有末条租期和机械滑行时间。测试报告包含上报帧、换算车体速度、错误计数和最终状态；运动测试通过不代表IMU有效性通过。

应用接入可复用[Client编解码](../deps/navbot_body/tools/chassis_serial.py)及[VelocityBridge](../deps/navbot_body/tools/motion_host.py)，保留其上游时效检查。正式ROS适配与后续标定见[实施计划](implementation-plan.md)。
