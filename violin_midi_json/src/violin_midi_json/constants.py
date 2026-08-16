"""共享常量：弓向、连奏判定、弓位估计相关的默认值。"""

# 弓向常量：小提琴规范中下弓/拉弓 = 向弓尖方向，所以下弓编码为 0；
# 上弓/推弓 = 向弓根方向，编码为 1。
BOW_DOWN = 0
BOW_UP = 1

# 自动判定连奏的启发式阈值。
DEFAULT_LEGATO_GAP_SECONDS = 0.03
DEFAULT_LEGATO_MAX_INTERVAL = 7

STRING_ORDER = {"G": 0, "D": 1, "A": 2, "E": 3}

# 长短音和值规则。
DEFAULT_LONG_NOTE_BEATS = 1.5
DEFAULT_SHORT_NOTE_BEATS = 0.5

# 弓位状态机参数。
DEFAULT_BOW_DELTA_MAX = 0.25
DEFAULT_BOW_DELTA_MIN = 0.07
DEFAULT_BOW_POSITION_MARGIN = 0.15
