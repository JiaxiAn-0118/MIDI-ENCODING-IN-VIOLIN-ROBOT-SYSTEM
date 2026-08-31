"""实时处理骨架：为未来视觉读谱接入预留生产者-消费者接口。

本模块定义线程边界与数据契约，并补齐「指法决策」这一实时接缝。数据流：

    NoteSource(原始 MidiNote 批次)
        -> FingeringPlanner.feed() 增量指法（窗口化在线规划）
        -> build_converted_note() 组装 ConvertedNote
        -> BowDecisionEngine.decide_streaming() 增量弓向（含前瞻）
        -> ActionSink.put()

离线主链路（converter.py）不受影响；本模块是增量扩展。
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from pathlib import Path
from queue import Queue
from threading import Thread
from typing import Deque, Iterable, Optional, Protocol, Sequence, Union

from .bow_decision import BowDecision, BowDecisionEngine
from .fingering_planner import FingeredNote
from .models import ConvertedNote, MidiNote, build_converted_note


@dataclass(frozen=True)
class ViolinAction:
    """线程间传递的不可变动作单元。"""

    note: ConvertedNote
    decision: BowDecision


class NoteSource(Protocol):
    """音符来源接口：按小节产出【原始】MidiNote 批次（尚未定指法）。

    现在可用离线实现（MidiMeasureSource，按小节切片的 MIDI 读取），
    未来可替换为视觉识谱实时输入（VisionScoreSource 占位）。
    """

    def iter_measures(self) -> Iterable[Sequence[MidiNote]]:
        """返回按小节组织的原始音符批次。"""


class FingeringPlanner(Protocol):
    """指法决策接口（实时接缝）。

    按批次喂入原始音符，返回已确定指法的音符。现在由 OnlineFingeringPlanner 实现；
    未来可替换为任何满足 feed/flush 契约的实现。
    """

    def feed(self, notes: Sequence[MidiNote]) -> list[FingeredNote]:
        """喂入一批原始音符，返回可提交的已定指法音符。"""

    def flush(self) -> list[FingeredNote]:
        """流结束时提交缓冲区剩余音符。"""


class ActionSink(Protocol):
    """动作去向接口。

    现在可写 BIN/JSON 或 mock，未来可替换为 ROS/Arduino 实时执行端。
    """

    def put(self, action: ViolinAction) -> None:
        """消费一个已经完成弓向决策的动作。"""

    def close(self) -> None:
        """结束消费，释放资源。"""


class ListActionSink:
    """测试/调试用的内存 Sink：把动作收集到列表。"""

    def __init__(self) -> None:
        self.actions: list[ViolinAction] = []

    def put(self, action: ViolinAction) -> None:
        self.actions.append(action)

    def close(self) -> None:
        pass


class MidiMeasureSource:
    """NoteSource 的离线实现：读 MIDI 文件，按小节切片产出原始音符批次。

    未来实时读谱时，用 VisionScoreSource 替换本类即可，RealtimePipeline 无需改动。
    """

    def __init__(
        self,
        beats_per_bar: int = 4,
        parser: object = None,
    ) -> None:
        self.beats_per_bar = beats_per_bar
        self._parser = parser  # 注入用；默认 None 时在 load() 里惰性导入 MidiParser
        self._notes: list[MidiNote] = []
        self._tempo: float = 120.0

    def load(self, midi_path: Union[str, Path]) -> "MidiMeasureSource":
        """读取 MIDI 文件并缓存音符与速度，返回 self 便于链式调用。"""
        if self._parser is None:
            from .midi_parser import MidiParser  # 惰性导入，避免骨架模块强依赖 pretty_midi

            self._parser = MidiParser()
        self._notes, self._tempo = self._parser.parse(midi_path)
        return self

    @property
    def tempo(self) -> float:
        return self._tempo

    def iter_measures(self) -> Iterable[Sequence[MidiNote]]:
        """按小节分组产出原始音符批次（按开始时间落入第几小节划分）。"""
        measure_sec = (
            self.beats_per_bar * (60.0 / self._tempo) if self._tempo > 0 else 0.5 * self.beats_per_bar
        )
        groups: dict[int, list[MidiNote]] = {}
        for note in sorted(self._notes, key=lambda n: (n.start, n.pitch, n.end)):
            measure_index = int(note.start // measure_sec)
            groups.setdefault(measure_index, []).append(note)
        for measure_index in sorted(groups):
            yield groups[measure_index]


class VisionScoreSource:
    """视觉识谱（OMR）实时输入的占位实现。

    这是为未来接入「实时读取谱子」预留的空位：未来 OMR 模块识别出一小节音符后，
    组织成 MidiNote 批次，通过 iter_measures() 喂给 RealtimePipeline。
    接入步骤见 docs/06 实时双线程骨架说明.md 第 6 节。
    """

    def iter_measures(self) -> Iterable[Sequence[MidiNote]]:
        raise NotImplementedError("视觉识谱输入尚未实现，接入步骤见 docs/06 第 6 节")


class RealtimePipeline:
    """双线程实时骨架（含指法接缝）。

    线程 A（生产者）:
      source.iter_measures() -> 原始 MidiNote 批次
        -> fingering.feed() 增量指法 -> build_converted_note() 组装 ConvertedNote
        -> 入弓向前瞻缓冲 -> engine.decide_streaming() 增量弓向 -> 入队 ViolinAction

    线程 B（消费者）:
      从队列取 ViolinAction -> sink.put(action)

    线程安全约束：
      - OnlineFingeringPlanner / BowDecisionEngine 均由生产者线程独占；
      - 线程间唯一共享状态是 queue。
    """

    _SENTINEL = object()

    def __init__(
        self,
        source: NoteSource,
        fingering: FingeringPlanner,
        engine: BowDecisionEngine,
        sink: ActionSink,
        bow_lookahead_size: int = 2,
        queue_size: int = 64,
    ) -> None:
        if queue_size <= 0:
            raise ValueError("queue_size must be positive")
        if bow_lookahead_size < 0:
            raise ValueError("bow_lookahead_size must be non-negative")

        self.source = source
        self.fingering = fingering
        self.engine = engine
        self.sink = sink
        self.bow_lookahead_size = bow_lookahead_size
        self.queue: Queue[object] = Queue(maxsize=queue_size)

        self._producer: Optional[Thread] = None
        self._consumer: Optional[Thread] = None

    def _produce(self) -> None:
        # 弓向前瞻缓冲：攒满 bow_lookahead_size 个未来音符后，才给最早的那个做弓向决策。
        bow_buffer: Deque[ConvertedNote] = deque()
        previous: Optional[ConvertedNote] = None

        def handle(converted: ConvertedNote) -> None:
            bow_buffer.append(converted)
            while len(bow_buffer) > self.bow_lookahead_size:
                note = bow_buffer.popleft()
                decision = self.engine.decide_streaming(note, lookahead_notes=list(bow_buffer))
                self.queue.put(ViolinAction(note=note, decision=decision))

        for measure in self.source.iter_measures():
            for fingered in self.fingering.feed(list(measure)):
                converted = build_converted_note(fingered.note, fingered.fingering, previous)
                previous = converted
                handle(converted)

        for fingered in self.fingering.flush():
            converted = build_converted_note(fingered.note, fingered.fingering, previous)
            previous = converted
            handle(converted)

        # 流结束：清空弓向前瞻缓冲，为剩余音符做无前瞻的弓向决策。
        while bow_buffer:
            note = bow_buffer.popleft()
            decision = self.engine.decide_streaming(note, lookahead_notes=list(bow_buffer))
            self.queue.put(ViolinAction(note=note, decision=decision))

        self.queue.put(self._SENTINEL)

    def _consume(self) -> None:
        while True:
            item = self.queue.get()
            if item is self._SENTINEL:
                self.sink.close()
                return

            if isinstance(item, ViolinAction):
                self.sink.put(item)

    def start(self) -> None:
        """启动生产者和消费者线程。"""
        self._producer = Thread(target=self._produce, name="violin-producer", daemon=True)
        self._consumer = Thread(target=self._consume, name="violin-consumer", daemon=True)
        self._producer.start()
        self._consumer.start()

    def join(self) -> None:
        """等待双线程处理完成。"""
        if self._producer is not None:
            self._producer.join()
        if self._consumer is not None:
            self._consumer.join()
