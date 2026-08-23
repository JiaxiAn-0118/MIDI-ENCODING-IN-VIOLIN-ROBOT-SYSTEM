"""实时处理骨架：为未来视觉读谱接入预留生产者-消费者接口。

当前模块只定义线程边界与数据契约，不改变现有离线转换流程。
"""

from __future__ import annotations

from dataclasses import dataclass
from queue import Queue
from threading import Thread
from typing import Optional, Protocol, Sequence

from .bow_decision import BowDecision, BowDecisionEngine
from .models import ConvertedNote


@dataclass(frozen=True)
class ViolinAction:
    """线程间传递的不可变动作单元。"""

    note: ConvertedNote
    decision: BowDecision


class NoteSource(Protocol):
    """音符来源接口。

    现在可用离线实现（如按小节切片的 MIDI 读取），
    未来可替换为视觉识谱实时输入。
    """

    def iter_measures(self) -> Sequence[Sequence[ConvertedNote]]:
        """返回按小节组织的音符批次。"""


class ActionSink(Protocol):
    """动作去向接口。

    现在可写 BIN/JSON 或 mock，未来可替换为 ROS/Arduino 实时执行端。
    """

    def put(self, action: ViolinAction) -> None:
        """消费一个已经完成弓向决策的动作。"""

    def close(self) -> None:
        """结束消费，释放资源。"""


class RealtimePipeline:
    """双线程实时骨架。

    线程 A（生产者）:
      source -> 按小节取音符 -> decide_all(有限前瞻) -> 入队 ViolinAction

    线程 B（消费者）:
      从队列取 ViolinAction -> sink.put(action)

    线程安全约束：
      - BowDecisionEngine 仅由生产者线程独占。
      - 线程间唯一共享状态是 queue。
    """

    _SENTINEL = object()

    def __init__(
        self,
        source: NoteSource,
        engine: BowDecisionEngine,
        sink: ActionSink,
        lookahead_size: int = 2,
        queue_size: int = 64,
    ) -> None:
        if queue_size <= 0:
            raise ValueError("queue_size must be positive")

        self.source = source
        self.engine = engine
        self.sink = sink
        self.lookahead_size = lookahead_size
        self.queue: Queue[object] = Queue(maxsize=queue_size)

        self._producer: Optional[Thread] = None
        self._consumer: Optional[Thread] = None

    def _produce(self) -> None:
        for measure_notes in self.source.iter_measures():
            notes = list(measure_notes)
            if not notes:
                continue

            decisions = self.engine.decide_all(notes, lookahead_size=self.lookahead_size)
            for note, decision in zip(notes, decisions):
                self.queue.put(ViolinAction(note=note, decision=decision))

        self.queue.put(self._SENTINEL)

    def _consume(self) -> None:
        while True:
            item = self.queue.get()
            if item is self._SENTINEL:
                self.sink.close()
                return

            action = item
            if isinstance(action, ViolinAction):
                self.sink.put(action)

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
