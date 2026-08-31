"""全局指法规划模块 (Dynamic Programming Fingering Planner)。

通过将乐谱序列建模为状态图，采用动态规划 (DP / Viterbi) 搜索整首乐曲的全局最低代价指法路径。
综合权衡换弦代价、换把代价、手指跨距与把位舒适度，避免局部贪心选择导致的频繁跳弦与多余换把。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Sequence

from .constants import STRING_ORDER
from .mapping import ViolinPitchMapper
from .models import FingeringCandidate, MidiNote


@dataclass(frozen=True)
class FingeringCostWeights:
    """全局指法规划的代价权重配置。"""

    string_change: float = 12.0         # 换相邻弦基础代价
    string_skip: float = 20.0           # 跨两根弦及以上的额外跳跃惩罚
    position_change: float = 18.0       # 换把位基础代价
    position_dist_penalty: float = 8.0  # 把位跨度距离惩罚（每跨 1 把位的附加代价）
    finger_jump: float = 3.0            # 同一把位手指大跨度惩罚
    priority_weight: float = 1.5        # 映射表中自带 priority（低把位/舒适手指）的权重系数
    open_string_bonus: float = -1.0     # 空弦激励（减少机械手指动作）


class GlobalFingeringPlanner:
    """基于动态规划 (DP) 的小提琴全局指法规划器。"""

    def __init__(
        self,
        mapper: Optional[ViolinPitchMapper] = None,
        weights: Optional[FingeringCostWeights] = None,
    ) -> None:
        self.mapper = mapper or ViolinPitchMapper()
        self.weights = weights or FingeringCostWeights()

    def plan(
        self,
        notes: Sequence[MidiNote],
        initial: Optional[FingeringCandidate] = None,
    ) -> list[FingeringCandidate]:
        """对输入的 MidiNote 序列进行全局最优指法规划。

        返回与每个音符严格对应的最优 FingeringCandidate 列表。
        若序列为空，返回空列表。

        initial: 可选，上一个已确定指法的物理状态（例如上一个窗口最后一个音的指法）。
                 提供时，第 0 个音符的代价会额外计入从 initial 转移过来的换弦/换把代价，
                 让分段规划在边界处与整曲规划保持一致。
        """
        if not notes:
            return []

        # 1. 获取每个音符的所有候选指法
        candidates_per_step: list[list[FingeringCandidate]] = []
        for index, note in enumerate(notes):
            cands = self.mapper.get_candidates(note.pitch)
            if not cands:
                raise ValueError(
                    f"音符索引 {index} (Pitch={note.pitch}) 超出支持的小提琴音高映射范围"
                )
            candidates_per_step.append(cands)

        # 2. 动态规划初始化 (第 0 个音符)
        n_steps = len(notes)
        dp_costs: list[list[float]] = []
        dp_backpointers: list[list[int]] = []

        # step 0 的代价 = 候选本身固有优先级；若给定 initial，再计入从 initial 转移过来的代价
        step0_costs: list[float] = []
        for cand in candidates_per_step[0]:
            intrinsic_cost = cand.priority * self.weights.priority_weight
            if cand.finger == 0:
                intrinsic_cost += self.weights.open_string_bonus
            if initial is not None:
                intrinsic_cost += self._calc_transition_cost(initial, cand)
            step0_costs.append(intrinsic_cost)

        dp_costs.append(step0_costs)
        dp_backpointers.append([-1] * len(step0_costs))

        # 3. 逐步向前推导转移代价
        for step in range(1, n_steps):
            prev_cands = candidates_per_step[step - 1]
            curr_cands = candidates_per_step[step]
            curr_costs: list[float] = []
            curr_pointers: list[int] = []

            for curr_idx, curr_cand in enumerate(curr_cands):
                min_cost = float("inf")
                best_prev_idx = 0

                intrinsic_cost = curr_cand.priority * self.weights.priority_weight
                if curr_cand.finger == 0:
                    intrinsic_cost += self.weights.open_string_bonus

                for prev_idx, prev_cand in enumerate(prev_cands):
                    trans_cost = self._calc_transition_cost(prev_cand, curr_cand)
                    total_cost = dp_costs[step - 1][prev_idx] + trans_cost + intrinsic_cost

                    if total_cost < min_cost:
                        min_cost = total_cost
                        best_prev_idx = prev_idx

                curr_costs.append(min_cost)
                curr_pointers.append(best_prev_idx)

            dp_costs.append(curr_costs)
            dp_backpointers.append(curr_pointers)

        # 4. 回溯最优路径
        best_last_idx = min(range(len(dp_costs[-1])), key=lambda i: dp_costs[-1][i])
        best_path_indices = [best_last_idx]

        for step in range(n_steps - 1, 0, -1):
            prev_idx = dp_backpointers[step][best_path_indices[-1]]
            best_path_indices.append(prev_idx)

        best_path_indices.reverse()

        return [
            candidates_per_step[step][idx]
            for step, idx in enumerate(best_path_indices)
        ]

    def _calc_transition_cost(
        self, prev: FingeringCandidate, curr: FingeringCandidate
    ) -> float:
        """计算两个连续指法状态之间的转移物理代价。"""
        cost = 0.0

        # 1. 换弦代价
        prev_str_idx = STRING_ORDER.get(prev.string, 0)
        curr_str_idx = STRING_ORDER.get(curr.string, 0)
        string_dist = abs(curr_str_idx - prev_str_idx)

        if string_dist > 0:
            cost += self.weights.string_change
            if string_dist > 1:
                # 跨弦附加惩罚 (如 G 弦直接跳到 A 弦或 E 弦)
                cost += (string_dist - 1) * self.weights.string_skip

        # 2. 换把位代价
        pos_dist = abs(curr.position - prev.position)
        if pos_dist > 0:
            cost += self.weights.position_change
            cost += (pos_dist - 1) * self.weights.position_dist_penalty

        # 3. 同把位手指跨度代价
        if pos_dist == 0 and prev.finger > 0 and curr.finger > 0:
            finger_dist = abs(curr.finger - prev.finger)
            if finger_dist >= 3:
                cost += self.weights.finger_jump

        return cost


@dataclass(frozen=True)
class FingeredNote:
    """增量指法规划的一个「已定指法」产物：原始音符 + 选定的指法。"""

    note: MidiNote
    fingering: FingeringCandidate


class OnlineFingeringPlanner:
    """窗口化在线指法规划器（为实时读谱预留的增量指法接缝）。

    与 GlobalFingeringPlanner 的关系：
      - Global 需要整曲一次性输入，实时读谱只有按小节增量到达的音符；
      - 本类维护一个滑动窗口缓冲区，攒满 window_size 个音符后用 Global 的 DP 求窗口内
        最优指法，只提交前部（仍留有 lookahead_size 个未来音符做上下文）的 commit_size 个
        音符，随后窗口前滑；边界处用上一个已提交指法做 DP 初值，保证跨批次连续。

    用法：

        planner = OnlineFingeringPlanner(window_size=8, lookahead_size=4)
        for measure in source.iter_measures():
            for fingered in planner.feed(measure):
                ...  # 得到已定指法的音符，可据此 build_converted_note
        for fingered in planner.flush():   # 流结束，提交缓冲区剩余音符
            ...
    """

    def __init__(
        self,
        mapper: Optional[ViolinPitchMapper] = None,
        weights: Optional[FingeringCostWeights] = None,
        window_size: int = 8,
        lookahead_size: int = 4,
    ) -> None:
        if window_size < 1:
            raise ValueError("window_size must be >= 1")
        if lookahead_size < 0 or lookahead_size >= window_size:
            raise ValueError("lookahead_size must satisfy 0 <= lookahead_size < window_size")

        self._planner = GlobalFingeringPlanner(mapper, weights)
        self.window_size = window_size
        self.lookahead_size = lookahead_size
        self.commit_size = window_size - lookahead_size
        self._buffer: list[MidiNote] = []
        self._previous: Optional[FingeringCandidate] = None

    def feed(self, notes: Sequence[MidiNote]) -> list[FingeredNote]:
        """喂入一批（如一小节）原始音符，返回此刻可提交的已定指法音符。

        当缓冲区攒满 window_size 个音符时，运行一次窗口内 DP 并提交前 commit_size 个，
        剩下的留在缓冲区里作为下一窗口的前缀，等待更多未来上下文。
        """
        self._buffer.extend(notes)
        committed: list[FingeredNote] = []
        while len(self._buffer) >= self.window_size:
            window = self._buffer[: self.window_size]
            fingerings = self._planner.plan(window, initial=self._previous)
            to_commit = fingerings[: self.commit_size]
            for note, fingering in zip(window[: self.commit_size], to_commit):
                committed.append(FingeredNote(note=note, fingering=fingering))
            self._previous = to_commit[-1]
            del self._buffer[: self.commit_size]
        return committed

    def flush(self) -> list[FingeredNote]:
        """流结束时提交缓冲区剩余音符（此时已无更多未来上下文）。"""
        if not self._buffer:
            return []
        fingerings = self._planner.plan(self._buffer, initial=self._previous)
        result = [
            FingeredNote(note=note, fingering=fingering)
            for note, fingering in zip(self._buffer, fingerings)
        ]
        self._previous = fingerings[-1]
        self._buffer = []
        return result
