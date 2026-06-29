# 映射算法说明

## 1. 目标

将 MIDI 音高映射为小提琴左手语义信息：

- string
- position
- finger

并为后续机器人控制层提供结构化输入。

## 2. 输入

输入为单个 MIDI note：

- pitch
- start
- end
- duration
- velocity

## 3. 候选指法集合

对于每个 MIDI pitch，系统维护一个候选集合：

```text
pitch -> [(string, position, finger, priority), ...]
```

例如：

- 69 可映射为：
  - D弦 1把位 4指
  - A弦 1把位 0指
  - D弦 2把位 3指
  - D弦 3把位 2指

## 4. 默认最自然把位策略

当前阶段不做全局最优路径规划，只做局部静态选择。

排序规则：

1. 优先级 priority 更小
2. 把位更低
3. 手指编号更小
4. 弦名按固定顺序稳定排序

这意味着：

- 优先第一把位
- 优先空弦
- 优先常见教学指法
- 保持实现简单、可维护

## 5. 换弦检测

若当前音与前一个音满足：

```text
current.string != previous.string
```

则：

```text
is_string_change = true
```

否则为 false。

## 6. 换把检测

若当前音与前一个音满足：

```text
current.position != previous.position
```

则：

```text
is_position_change = true
```

否则为 false。

## 7. 当前阶段边界

当前实现假设：

- MIDI 为单旋律
- 不处理和弦
- 不处理装饰音
- 不处理弓法
- 不处理机械轨迹

## 8. 后续升级建议

后续可升级为：

- 基于动态规划的最小运动路径选择
- 同音异弦上下文优化
- 乐句级换把策略
- 与 Binary Violin Event Protocol 对接
