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

    def plan(self, notes: Sequence[MidiNote]) -> list[FingeringCandidate]:
        """对输入的 MidiNote 序列进行全局最优指法规划。

        返回与每个音符严格对应的最优 FingeringCandidate 列表。
        若序列为空，返回空列表。
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

        # step 0 的代价仅由候选本身的固有优先级决定
        step0_costs: list[float] = []
        for cand in candidates_per_step[0]:
            intrinsic_cost = cand.priority * self.weights.priority_weight
            if cand.finger == 0:
                intrinsic_cost += self.weights.open_string_bonus
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
