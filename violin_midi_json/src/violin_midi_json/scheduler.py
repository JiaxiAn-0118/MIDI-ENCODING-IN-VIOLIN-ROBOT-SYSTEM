"""时序协调与提前量调度模块 (Lead-Time Scheduler)。

在物理小提琴演奏中，左手按弦与右手运弓存在严格的时间先后关系：
  1. 按弦提前量 (Lead Time)：左手手指必须在琴弓触弦起振前 20~50ms 压实指板，否则会出现滑音或杂音；
  2. 换弦仰角提前量：换弦舵机/倾角机构必须在弓毛触及新弦前调整到位；
  3. 按弦保持：左手必须在弓毛离弦或音符结束时才释放，防止提前抬手断音。
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional, Sequence

from .models import ConvertedNote


class ActionType(str, Enum):
    """底层微动作类型。"""

    STRING_TILT = "STRING_TILT"       # 调整换弦仰角
    FINGER_PRESS = "FINGER_PRESS"     # 左手按弦
    BOW_START = "BOW_START"           # 右手起弓拉/推
    BOW_STOP = "BOW_STOP"             # 右手停弓/换向
    FINGER_RELEASE = "FINGER_RELEASE" # 左手松开琴弦


@dataclass(frozen=True)
class ScheduledAction:
    """带绝对时间戳的离散执行动作。"""

    timestamp: float          # 触发时间（秒）
    action_type: ActionType   # 动作类型
    note_index: int           # 对应的音符索引
    string_name: str          # 目标弦 ("G", "D", "A", "E")
    position: int             # 把位
    finger: int               # 手指
    bow_direction: Optional[str] = None  # 弓向 ("down" / "up")
    bow_speed: int = 0        # 弓速 (0~127)
    bow_force: int = 0        # 弓压 (0~255)


@dataclass(frozen=True)
class TimedNoteSchedule:
    """单个音符的时序规划摘要。"""

    note: ConvertedNote
    finger_press_time: float   # 手指按实时刻（秒）
    string_tilt_time: float    # 换弦对齐时刻（秒）
    bow_start_time: float      # 起弓时刻（秒）
    bow_end_time: float        # 停弓/音符结束时刻（秒）


@dataclass(frozen=True)
class SchedulerConfig:
    """调度器时间参数配置。"""

    finger_lead_seconds: float = 0.030   # 按弦提前量，默认 30ms
    string_tilt_lead_seconds: float = 0.050 # 换弦仰角提前量，默认 50ms


class LeadTimeScheduler:
    """时序调度器：将音符序列编译为高精度的动作事件时序。"""

    def __init__(self, config: Optional[SchedulerConfig] = None) -> None:
        self.config = config or SchedulerConfig()

    def schedule_notes(self, notes: Sequence[ConvertedNote]) -> list[TimedNoteSchedule]:
        """为每个 ConvertedNote 计算双手精确触发时间戳。"""
        schedules: list[TimedNoteSchedule] = []

        for note in notes:
            # 仅在非空弦且需要按弦时计算提前量
            finger_press = max(0.0, note.start - self.config.finger_lead_seconds)
            # 仅在需要换弦时提前预备
            string_tilt = (
                max(0.0, note.start - self.config.string_tilt_lead_seconds)
                if note.is_string_change
                else note.start
            )

            schedules.append(
                TimedNoteSchedule(
                    note=note,
                    finger_press_time=round(finger_press, 4),
                    string_tilt_time=round(string_tilt, 4),
                    bow_start_time=round(note.start, 4),
                    bow_end_time=round(note.end, 4),
                )
            )

        return schedules

    def generate_action_timeline(
        self, notes: Sequence[ConvertedNote]
    ) -> list[ScheduledAction]:
        """将音符序列展平成按时间严格排序的底层微动作事件流。"""
        actions: list[ScheduledAction] = []

        for idx, note in enumerate(notes):
            # 1. 换弦仰角
            if note.is_string_change or idx == 0:
                tilt_t = max(0.0, note.start - self.config.string_tilt_lead_seconds)
                actions.append(
                    ScheduledAction(
                        timestamp=tilt_t,
                        action_type=ActionType.STRING_TILT,
                        note_index=idx,
                        string_name=note.string,
                        position=note.position,
                        finger=note.finger,
                    )
                )

            # 2. 左手按弦
            if note.finger > 0:
                press_t = max(0.0, note.start - self.config.finger_lead_seconds)
                actions.append(
                    ScheduledAction(
                        timestamp=press_t,
                        action_type=ActionType.FINGER_PRESS,
                        note_index=idx,
                        string_name=note.string,
                        position=note.position,
                        finger=note.finger,
                    )
                )

            # 3. 右手起弓
            actions.append(
                ScheduledAction(
                    timestamp=note.start,
                    action_type=ActionType.BOW_START,
                    note_index=idx,
                    string_name=note.string,
                    position=note.position,
                    finger=note.finger,
                    bow_direction=note.bow_direction,
                    bow_speed=note.velocity,
                )
            )

            # 4. 停弓 / 松手 (如果下一音不连奏)
            if not note.is_legato:
                actions.append(
                    ScheduledAction(
                        timestamp=note.end,
                        action_type=ActionType.BOW_STOP,
                        note_index=idx,
                        string_name=note.string,
                        position=note.position,
                        finger=note.finger,
                    )
                )

        # 按时间戳升序排序，时间相同时按动作优先级（换弦->按弦->起弓）
        def _action_priority(a: ScheduledAction) -> int:
            p_map = {
                ActionType.STRING_TILT: 0,
                ActionType.FINGER_PRESS: 1,
                ActionType.BOW_START: 2,
                ActionType.BOW_STOP: 3,
                ActionType.FINGER_RELEASE: 4,
            }
            return p_map.get(a.action_type, 99)

        actions.sort(key=lambda a: (a.timestamp, _action_priority(a)))
        return actions
