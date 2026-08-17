% =========================================================================
%  小提琴机器人「狗腿机构」全系统动力学与选型仿真（BIN二进制输入版）
% -------------------------------------------------------------------------
%  【核心修改点】
%    1. 将 JSON 读取替换为二进制 (.bin) 文件解析；
%    2. 读取二进制文件中更新后的运弓方向逻辑（direction: 1=正向拉弓, -1=反向推弓）；
%    3. 根据新的运弓方向指示精确生成五次多项式 S 型运弓轨迹。
% =========================================================================
clear; clc; close all;

%% 1. 机械几何尺寸与质量参数 (两腿完全对称平衡)
L1 = 0.10;        % 大腿长度 (m) (由 L1/R1 电机直接驱动)
L2 = 0.10;        % 连杆和小腿外壳长度 (m)
H_slide = 0.10;   % 滑轨高度 (m)
L_hold = 0.13;    % 滑块上左右两条腿基座的间距 (m)
L_bow = 0.70;     % 琴弓总长度 70 cm (m)
L_inter = 0.13;   % 琴弓上左右两个铰接点之间的固定距离 (m)

% --- 髋关节平行双曲柄机构物理参数 (左右腿各一套) ---
r_crank = 0.04;   % 髋关节处由 L2/R2 电机直接驱动的"短曲柄"长度 (m)
m_crank = 0.05;   % 短曲柄质量 (kg)
m_rod = 0.08;     % 联结短曲柄与膝关节的"长传动连杆"质量 (kg)
m_calf = 0.25;    % 包含膝关节短摆杆与外壳在内的小腿总质量 (kg)
eta_link = 0.95;  % 远端平行四杆传动的机械效率

% --- 滑轨与传动系统参数 ---
Lead_slide = 0.025; % 滑轨导程 (m/rev)
m_slider = 0.40;   % 滑块及上面所有电机的总质量 (kg)
eta_slide = 0.85;  % 传动效率

% --- 基础动力学参数 ---
m_arm1 = 0.15;    % 大腿质量 (kg)
m_bow = 0.06;     % 琴弓质量 (kg)
g = 9.81;         % 重力加速度 (m/s^2)

% --- 转动惯量严密计算 ---
I_arm1 = (1/3) * m_arm1 * L1^2;       % 大腿绕髋关节的转动惯量
I_crank = (1/3) * m_crank * r_crank^2; % 短曲柄绕髋关节的本地转动惯量
I_calf_g = (1/12) * m_calf * L2^2;     % 小腿外壳绕自身质心的转动惯量
I_rod_g = (1/12) * m_rod * L2^2;       % 长传动连杆绕自身质心的转动惯量

%% 2. 小提琴 7 种演奏状态的弦坐标与绝对角度
P_G = [-0.034; -0.005]; P_D = [-0.012;  0.002];
P_A = [ 0.012;  0.002]; P_E = [ 0.034; -0.005];
P_GD = (P_G + P_D) / 2; P_DA = (P_D + P_A) / 2; P_AE = (P_A + P_E) / 2;
Strings = [P_G, P_D, P_A, P_E]; String_Names = {'G弦', 'D弦', 'A弦', 'E弦'};

State_Points = {P_G, P_GD, P_D, P_DA, P_A, P_AE, P_E};
State_Angles = deg2rad([28, 14, 5, 0, -5, -14, -28]);
State_Names  = {'G单音', 'G-D双音', 'D单音', 'D-A双音', 'A单音', 'A-E双音', 'E单音'};

%% 3. 运弓动作定义（连续状态积分与行程动态分配）
bin_path = '/Users/anjiaxi/Desktop/Fudan/Projects/Denghui_violin/Violin_GitHub/MIDI-ENCODING-IN-VIOLIN-ROBOT-SYSTEM/scores/梁祝/liangzhu_lower.bin'; % 请确认 bin 文件的实际相对或绝对路径[cite: 2]

if ~exist(bin_path, 'file')
    error('找不到二进制乐谱文件：%s，请检查文件路径是否正确！', bin_path);
end

fid = fopen(bin_path, 'rb');
if fid < 0
    error('无法打开二进制文件：%s', bin_path);
end

data = fread(fid, inf, 'uint8=>uint8');
fclose(fid);

if isempty(data)
    error('二进制文件为空：%s', bin_path);
end
if mod(numel(data), 12) ~= 0
    error('二进制文件长度不是 12 的整数倍：%d 字节', numel(data));
end

packet_count = numel(data) / 12;
data = reshape(data, 12, packet_count);

headers = data(1, :);
if any(headers ~= 165)
    warning('部分数据包头不是 0xA5，请检查文件是否为正确的 12 字节协议。');
end

ticks        = double(data(2, :)) + 256 * double(data(3, :));
pitch        = data(4, :);
durations    = double(data(5, :)) + 256 * double(data(6, :));
string_finger = data(7, :);
bow_byte     = data(8, :);
force        = data(9, :);
flags        = data(10, :);
reserved     = data(11, :);
checksum     = data(12, :);

checksum_ok = checksum == mod(sum(data(1:11, :), 1), 256);
if any(~checksum_ok)
    warning('检测到 %d 个校验和不匹配的数据包。', sum(~checksum_ok));
end

string_names = {'G', 'D', 'A', 'E'};
notes = struct('start', {}, 'end', {}, 'string', {}, 'velocity', {}, 'direction', {}, 'note_name', {});
for n = 1:packet_count
    notes(n).start = ticks(n) * 0.01;
    notes(n).end   = notes(n).start + durations(n) * 0.01;
    string_id = bitshift(string_finger(n), -6) + 1;
    if string_id < 1 || string_id > numel(string_names)
        notes(n).string = 'Unknown';
    else
        notes(n).string = string_names{string_id};
    end
    notes(n).velocity = double(force(n));
    bow_direction_bit = bitshift(bow_byte(n), -7);
    notes(n).direction = 1 - 2 * bow_direction_bit;
    % 把 flags 中的 legato 标志读入，便于仿真阶段保持弓连续
    LEGATO_FLAG = 4;
    RESET_BOW_FLAG = 8;
    notes(n).is_legato = bitand(flags(n), LEGATO_FLAG) ~= 0;
    notes(n).needs_reset = bitand(flags(n), RESET_BOW_FLAG) ~= 0;
    notes(n).note_name = sprintf('%s_%03d', notes(n).string, pitch(n));
end

% ---------- 合并同弓向连续音段 (Segments) ----------
motion_gap_tol = 0.08;     % 运弓连续性判定阈值：同方向且时间间隙小于该值则视为同一运弓段
segments = struct('start', {}, 'end', {}, 'direction', {}, 'note_idx', {});
if ~isempty(notes)
    i_note = 1;
    while i_note <= length(notes)
        s_idx = i_note;
        s_dir = notes(i_note).direction;
        e_idx = i_note;
          % 轨迹合并优先保证运动连续性；RESET_BOW_FLAG 仍可强制断段
        while (e_idx + 1) <= length(notes) && ...
              notes(e_idx + 1).direction == s_dir && ...
              ~notes(e_idx + 1).needs_reset && ...
              (notes(e_idx + 1).start - notes(e_idx).end) <= motion_gap_tol
            e_idx = e_idx + 1;
        end
        seg.start = notes(s_idx).start;
        seg.end = notes(e_idx).end;
        seg.direction = s_dir;
        seg.note_idx = s_idx:e_idx;
        segments(end+1) = seg; %#ok<SAGROW>
        i_note = e_idx + 1;
    end
end

if isempty(notes)
    error('二进制文件解析失败：未读取到有效音符。');
end

% --- 打印诊断信息供核对 ---
fprintf('======================================================\n');
fprintf(' 成功解析二进制乐谱，共读取 %d 个音符 (协议: 12 字节/包)。\n', length(notes));
fprintf('  * 音符 1   : 名称 [%s], 弦 [%s], 起始 [%.2f s], 结束 [%.2f s], 方向 [%d]\n', ...
    notes(1).note_name, notes(1).string, notes(1).start, notes(1).end, notes(1).direction);
fprintf('  * 末音符 %d: 名称 [%s], 弦 [%s], 起始 [%.2f s], 结束 [%.2f s], 方向 [%d]\n', ...
    length(notes), notes(end).note_name, notes(end).string, notes(end).start, notes(end).end, notes(end).direction);
fprintf('======================================================\n');

% --- 打印所有读取到的音符详细列表 ---
fprintf('\n----------------- 详细音符数据列表 -----------------\n');
fprintf('%-6s | %-10s | %-6s | %-10s | %-10s | %-6s\n', ...
        '序号', '音符名称', '弦', '起始时间(s)', '结束时间(s)', '运弓方向');
fprintf('-----------------------------------------------------\n');

for n = 1:length(notes)
    if notes(n).direction == 1
        dir_str = '拉弓(+)';
    else
        dir_str = '推弓(-)';
    end
    fprintf('%-6d | %-10s | %-6s | %-11.2f | %-11.2f | %-6s\n', ...
            n, notes(n).note_name, notes(n).string, ...
            notes(n).start, notes(n).end, dir_str);
end
fprintf('-----------------------------------------------------\n\n');

% 建立全局高精度仿真时间轴
total_duration = notes(end).end;

% 防错降级处理：若读取到的 end <= start，自动根据音符时长修复
if total_duration <= 0 || total_duration <= notes(1).start
    warning('二进制文件中音符时间异常，正在进行时间轴自动修补...');
    accum_time = 0;
    for n = 1:length(notes)
        if notes(n).end <= notes(n).start
            notes(n).start = accum_time;
            notes(n).end = accum_time + 1.0; % 默认分配 1 秒/音符
        end
        accum_time = notes(n).end;
    end
    total_duration = notes(end).end;
end

fs = 100; % 采样率 100Hz
t = 0:(1/fs):total_duration;
num_steps = length(t);

if num_steps < 2
    error('时间向量长度仍不足 (total_duration = %.4f)，请检查 .bin 文件中的时间字段数据。', total_duration);
end

dt = t(2) - t(1);

% 初始化动力学输入数组
current_string_t = zeros(2, num_steps);
theta_bow_target = zeros(1, num_steps);
x_slide_t = zeros(1, num_steps);
v_slide_t = zeros(1, num_steps);
a_slide_t = zeros(1, num_steps);
F_N_t = zeros(1, num_steps);
current_state_idx = zeros(1, num_steps);

% --- 运弓轨迹关键参数 ---
stroke_limit = 0.12;       % 单次最大运弓半行程 (m)
stroke_margin = 0.01;      % 软边界余量，避免频繁顶到机械端点
nominal_bow_speed = 0.08;  % 标称运弓速度 (m/s)
center_pull_gain = 0.35;   % 每个段对中心位置的回拉系数
min_seg_move = 0.004;      % 单段最小位移，避免极短段完全不动
x_min = -stroke_limit + stroke_margin;
x_max = stroke_limit - stroke_margin;

last_valid_note_idx = 1;

% --- 连续滑块轨迹规划 ---
% 以“上一段结束时的真实位置”作为下一段起点，避免位置跳变
if ~isempty(segments) && segments(1).direction == -1
    x_prev = x_max;
else
    x_prev = x_min;
end
active_seg_idx = 0;
planned_seg_idx = -1;
seg_x_start = x_prev;
seg_x_end = x_prev;

for i = 1:num_steps
    t_curr = t(i);

    % 寻找当前时间点对应的音符
    note_idx = 0;
    for n = 1:length(notes)
        if t_curr >= notes(n).start && t_curr <= notes(n).end
            note_idx = n;
            break;
        end
    end

    if note_idx == 0
        note_idx = last_valid_note_idx;
    else
        last_valid_note_idx = note_idx;
    end

    curr_note = notes(note_idx);
    current_state_idx(i) = note_idx;

    % 映射当前弦的物理坐标与目标角度
    switch curr_note.string
        case 'G', P_target = P_G; th_target = State_Angles(1);
        case 'D', P_target = P_D; th_target = State_Angles(3);
        case 'A', P_target = P_A; th_target = State_Angles(5);
        case 'E', P_target = P_E; th_target = State_Angles(7);
        otherwise, P_target = P_A; th_target = State_Angles(5);
    end
    current_string_t(:, i) = P_target;
    theta_bow_target(i) = th_target;
    F_N_t(i) = 1.5 + (curr_note.velocity / 127) * 3.0;

    % 轨迹规划：按时间顺序推进 segment，段间保持连续位置
    while active_seg_idx < length(segments) && t_curr > segments(active_seg_idx + 1).end
        active_seg_idx = active_seg_idx + 1;
    end

    if active_seg_idx < length(segments) && t_curr >= segments(active_seg_idx + 1).start
        curr_seg_idx = active_seg_idx + 1;
        seg = segments(curr_seg_idx);
        seg_duration = max(seg.end - seg.start, 1e-4);

        % 段起点/终点仅在进入新段时初始化一次，避免每个采样点重复重规划
        if curr_seg_idx ~= planned_seg_idx
            seg_x_start = x_prev;

            % 折中策略：按段时长分配位移，并增加轻微回中项，避免短段冲到端点后停顿
            dx_nominal = seg.direction * nominal_bow_speed * seg_duration;
            dx_center = -center_pull_gain * seg_x_start;
            dx_plan = dx_nominal + dx_center;

            if seg.direction == 1
                dx_plan = max(dx_plan, min_seg_move);
                dx_plan = min(dx_plan, x_max - seg_x_start);
            else
                dx_plan = min(dx_plan, -min_seg_move);
                dx_plan = max(dx_plan, x_min - seg_x_start);
            end

            seg_x_end = seg_x_start + dx_plan;
            planned_seg_idx = curr_seg_idx;
        end

        tau = (t_curr - seg.start) / seg_duration;
        tau = max(min(tau, 1), 0);

        poly_factor = 10*tau^3 - 15*tau^4 + 6*tau^5;
        x_slide_t(i) = seg_x_start + (seg_x_end - seg_x_start) * poly_factor;

        s_prime = 30 * tau^2 * (1 - tau)^2;
        v_slide_t(i) = (seg_x_end - seg_x_start) * s_prime / seg_duration;
        s_double = 60 * tau * (1 - tau) * (1 - 2*tau);
        a_slide_t(i) = (seg_x_end - seg_x_start) * s_double / (seg_duration^2);

        x_prev = x_slide_t(i);
    else
        % 音符间隙：保持上一时刻滑块位置，避免未定义跳变
        x_slide_t(i) = x_prev;
        v_slide_t(i) = 0;
        a_slide_t(i) = 0;
    end
end

% 对位移轨迹做轻度平滑，再统一求导，减少段切换处的速度顿挫
if num_steps >= 7
    x_slide_t = smoothdata(x_slide_t, 'sgolay', 7);
elseif num_steps >= 3
    x_slide_t = smoothdata(x_slide_t, 'movmean', 3);
end
x_slide_t = min(max(x_slide_t, x_min), x_max);
v_slide_t = gradient(x_slide_t, dt);
a_slide_t = gradient(v_slide_t, dt);

% 对换弦角度进行高斯平滑
theta_bow_t = smoothdata(theta_bow_target, 'gaussian', 15);
if num_steps > 1
    theta_bow_t(end) = theta_bow_t(end-1);
end

%% 4. 铰接约束逆解 (左右双腿五杆闭环核心机构解析)
num_steps = length(t);
motor_L1_rad = zeros(1, num_steps); motor_L2_rad = zeros(1, num_steps);
motor_R1_rad = zeros(1, num_steps); motor_R2_rad = zeros(1, num_steps);

P_knee_L_all = zeros(2, num_steps); P_hinge_L_all = zeros(2, num_steps);
P_knee_R_all = zeros(2, num_steps); P_hinge_R_all = zeros(2, num_steps);

for i = 1:num_steps
    x_s = x_slide_t(i); th_b = theta_bow_t(i); P_contact = current_string_t(:, i);
    R_matrix = [cos(th_b), -sin(th_b); sin(th_b), cos(th_b)];

    % 左腿末端与基座位置
    P_hinge_L = P_contact + R_matrix * [-L_inter/2 + x_s; 0];
    P_hinge_L_all(:, i) = P_hinge_L;
    P_base_L = [x_s - L_hold/2; H_slide];

    V_L = P_hinge_L - P_base_L; D_L = norm(V_L);
    gamma_L = atan2(V_L(2), V_L(1));
    alpha_L = acos(max(min((L1^2 + D_L^2 - L2^2) / (2 * L1 * D_L), 1), -1));
    motor_L1_rad(i) = gamma_L - alpha_L;
    motor_L2_rad(i) = gamma_L + alpha_L;
    P_knee_L_all(:, i) = P_base_L + [L1*cos(motor_L1_rad(i)); L1*sin(motor_L1_rad(i))];

    % 右腿末端与基座位置
    P_hinge_R = P_contact + R_matrix * [L_inter/2 + x_s; 0];
    P_hinge_R_all(:, i) = P_hinge_R;
    P_base_R = [x_s + L_hold/2; H_slide];

    V_R = P_hinge_R - P_base_R; D_R = norm(V_R);
    gamma_R = atan2(V_R(2), V_R(1));
    alpha_R = acos(max(min((L1^2 + D_R^2 - L2^2) / (2 * L1 * D_R), 1), -1));
    motor_R1_rad(i) = gamma_R + alpha_R;
    motor_R2_rad(i) = gamma_R - alpha_R;
    P_knee_R_all(:, i) = P_base_R + [L1*cos(motor_R1_rad(i)); L1*sin(motor_R1_rad(i))];
end

%% 5. 所有电机速度、加速度解算
motor_L1_sm = smoothdata(motor_L1_rad, 'sgolay', 7);
motor_L2_sm = smoothdata(motor_L2_rad, 'sgolay', 7);
motor_R1_sm = smoothdata(motor_R1_rad, 'sgolay', 7);
motor_R2_sm = smoothdata(motor_R2_rad, 'sgolay', 7);

omega_L1 = gradient(motor_L1_sm, dt);
omega_L2 = gradient(motor_L2_sm, dt);
omega_R1 = gradient(motor_R1_sm, dt);
omega_R2 = gradient(motor_R2_sm, dt);

alpha_L1 = gradient(omega_L1, dt);
alpha_L2 = gradient(omega_L2, dt);
alpha_R1 = gradient(omega_R1, dt);
alpha_R2 = gradient(omega_R2, dt);

v_slide = v_slide_t;
a_slide = a_slide_t;
omega_slide_motor = (v_slide / Lead_slide) * 2 * pi;

a_y_calf_L = L1 * (cos(motor_L1_sm) .* alpha_L1 - sin(motor_L1_sm) .* omega_L1.^2) ...
           + L2 * (cos(motor_L2_sm) .* alpha_L2 - sin(motor_L2_sm) .* omega_L2.^2);

a_y_calf_R = L1 * (cos(motor_R1_sm) .* alpha_R1 - sin(motor_R1_sm) .* omega_R1.^2) ...
           + L2 * (cos(motor_R2_sm) .* alpha_R2 - sin(motor_R2_sm) .* omega_R2.^2);

%% 6. 核心：全车双腿4关节电机全动力学解算循环
torque_L1 = zeros(1, num_steps); torque_L2 = zeros(1, num_steps);
torque_R1 = zeros(1, num_steps); torque_R2 = zeros(1, num_steps);
torque_slide_motor = zeros(1, num_steps);

F_base_L_x = zeros(1, num_steps); F_base_L_y = zeros(1, num_steps);
F_base_R_x = zeros(1, num_steps); F_base_R_y = zeros(1, num_steps);

K_couple = 0.5 * m_calf * L1 * L2;
M11_const = I_arm1 + (1/8)*m_rod*L1^2 + m_calf*L1^2;
M22_const = I_crank + (1/8)*m_rod*r_crank^2 + 0.25*m_calf*L2^2 + I_calf_g;

G1_coeff = (0.5*m_arm1 + 0.25*m_rod + m_calf) * g * L1;
G2_coeff = (0.5*m_crank + 0.25*m_rod) * g * r_crank + 0.5 * m_calf * g * L2;

for i = 1:num_steps
    F_N_half = F_N_t(i) / 2;

    v_rel_current = v_slide(i);
    mu_current = 0.4 * exp(-100 * abs(v_rel_current)) + 0.45 * exp(-10 * abs(v_rel_current)) + 0.35;
    v0 = 2e-4;
    mu_smoothed = mu_current * (2 / pi) * atan(v_rel_current / v0);
    F_friction_half = mu_smoothed * F_N_half;

    m_bow_half = 0.5 * m_bow;

    % 左腿 2-DOF 动力学
    th1 = motor_L1_sm(i); th2 = motor_L2_sm(i);
    dth1 = omega_L1(i);   dth2 = omega_L2(i);
    ddth1 = alpha_L1(i);  ddth2 = alpha_L2(i);

    F_x_ext = -F_friction_half;
    F_y_ext = -F_N_half - m_bow_half * (g + a_y_calf_L(i));

    tau_J1 = -L1 * sin(th1) * F_x_ext + L1 * cos(th1) * F_y_ext;
    tau_J2 = -L2 * sin(th2) * F_x_ext + L2 * cos(th2) * F_y_ext;

    dth = th1 - th2;
    M11 = M11_const;
    M12 = K_couple * cos(dth);
    M22 = M22_const;

    sin_dth = sin(dth);
    h1 =  K_couple * sin_dth * dth2^2;
    h2 = -K_couple * sin_dth * dth1^2;

    G1 = G1_coeff * cos(th1);
    G2 = G2_coeff * cos(th2);

    tau1_raw = M11 * ddth1 + M12 * ddth2 + h1 + G1 + tau_J1;
    tau2_raw = M22 * ddth2 + M12 * ddth1 + h2 + G2 + tau_J2;

    torque_L1(i) = tau1_raw;
    torque_L2(i) = tau2_raw / eta_link;

    a_thigh_x = -0.5*L1*(cos(th1)*dth1^2 + sin(th1)*ddth1);
    a_thigh_y = -0.5*L1*(sin(th1)*dth1^2 - cos(th1)*ddth1);
    a_calf_x  = -L1*(cos(th1)*dth1^2 + sin(th1)*ddth1) - 0.5*L2*(cos(th2)*dth2^2 + sin(th2)*ddth2);
    a_calf_y  = -L1*(sin(th1)*dth1^2 - cos(th1)*ddth1) - 0.5*L2*(sin(th2)*dth2^2 - cos(th2)*ddth2);

    F_base_L_x(i) = m_arm1*a_thigh_x + 0.5*m_rod*a_thigh_x + m_crank*0 + m_calf*a_calf_x - F_x_ext;
    F_base_L_y(i) = m_arm1*(a_thigh_y + g) + 0.5*m_rod*(a_thigh_y + g) + m_crank*g + m_calf*(a_calf_y + g) - F_y_ext;

    % 右腿 2-DOF 动力学
    th1 = motor_R1_sm(i); th2 = motor_R2_sm(i);
    dth1 = omega_R1(i);   dth2 = omega_R2(i);
    ddth1 = alpha_R1(i);  ddth2 = alpha_R2(i);

    F_x_ext = -F_friction_half;
    F_y_ext = -F_N_half - m_bow_half * (g + a_y_calf_R(i));

    tau_J1 = -L1 * sin(th1) * F_x_ext + L1 * cos(th1) * F_y_ext;
    tau_J2 = -L2 * sin(th2) * F_x_ext + L2 * cos(th2) * F_y_ext;

    dth = th1 - th2;
    M12 = K_couple * cos(dth);
    sin_dth = sin(dth);
    h1 =  K_couple * sin_dth * dth2^2;
    h2 = -K_couple * sin_dth * dth1^2;

    G1 = G1_coeff * cos(th1);
    G2 = G2_coeff * cos(th2);

    tau1_raw = M11_const * ddth1 + M12 * ddth2 + h1 + G1 + tau_J1;
    tau2_raw = M22_const * ddth2 + M12 * ddth1 + h2 + G2 + tau_J2;

    torque_R1(i) = tau1_raw;
    torque_R2(i) = tau2_raw / eta_link;

    a_thigh_x = -0.5*L1*(cos(th1)*dth1^2 + sin(th1)*ddth1);
    a_thigh_y = -0.5*L1*(sin(th1)*dth1^2 - cos(th1)*ddth1);
    a_calf_x  = -L1*(cos(th1)*dth1^2 + sin(th1)*ddth1) - 0.5*L2*(cos(th2)*dth2^2 + sin(th2)*ddth2);
    a_calf_y  = -L1*(sin(th1)*dth1^2 - cos(th1)*ddth1) - 0.5*L2*(sin(th2)*dth2^2 - cos(th2)*ddth2);

    F_base_R_x(i) = m_arm1*a_thigh_x + 0.5*m_rod*a_thigh_x + m_crank*0 + m_calf*a_calf_x - F_x_ext;
    F_base_R_y(i) = m_arm1*(a_thigh_y + g) + 0.5*m_rod*(a_thigh_y + g) + m_crank*g + m_calf*(a_calf_y + g) - F_y_ext;

    % 滑轨电机扭矩
    torque_slide_motor(i) = (m_slider * a_slide(i) * Lead_slide) / (2 * pi * eta_slide);
end

omega_L1_deg = rad2deg(omega_L1);
omega_L2_deg = rad2deg(omega_L2);
omega_R1_deg = rad2deg(omega_R1);
omega_R2_deg = rad2deg(omega_R2);

% %% 7. 动态双腿同步演奏仿真动画
% 
% figure('Name', '双闭环平行双曲柄狗腿同步演奏仿真', 'Position', [50, 80, 1100, 700]);
% 
% for i = 1:2:length(t)
%     clf;
%     x_s = x_slide_t(i); th_b = theta_bow_t(i); P_contact = current_string_t(:, i);
%     R_matrix = [cos(th_b), -sin(th_b); sin(th_b), cos(th_b)];
% 
%     plot([-0.6, 0.6], [H_slide, H_slide], 'k--', 'LineWidth', 1.5); hold on;
%     slider_w = L_hold + 0.06;
%     rectangle('Position', [x_s - slider_w/2, H_slide, slider_w, 0.02], 'FaceColor', [0.7 0.7 0.7]);
% 
%     % 左腿
%     P_base_L = [x_s - L_hold/2; H_slide]; P_knee_L = P_knee_L_all(:, i); P_hinge_L = P_hinge_L_all(:, i);
%     plot([P_base_L(1), P_knee_L(1)], [P_base_L(2), P_knee_L(2)], 'b-o', 'LineWidth', 3, 'MarkerFaceColor','b');
%     P_crank_end_L = P_base_L + [r_crank*cos(motor_L2_rad(i)); r_crank*sin(motor_L2_rad(i))];
%     plot([P_base_L(1), P_crank_end_L(1)], [P_base_L(2), P_crank_end_L(2)], 'r-o', 'LineWidth', 4, 'MarkerFaceColor','r');
%     P_knee_jig_L = P_knee_L + [r_crank*cos(motor_L2_rad(i)); r_crank*sin(motor_L2_rad(i))];
%     plot([P_crank_end_L(1), P_knee_jig_L(1)], [P_crank_end_L(2), P_knee_jig_L(2)], 'm--', 'LineWidth', 1.5);
%     plot([P_knee_L(1), P_hinge_L(1)], [P_knee_L(2), P_hinge_L(2)], 'g-o', 'LineWidth', 2.5, 'MarkerFaceColor','g');
% 
%     % 右腿
%     P_base_R = [x_s + L_hold/2; H_slide]; P_knee_R = P_knee_R_all(:, i); P_hinge_R = P_hinge_R_all(:, i);
%     plot([P_base_R(1), P_knee_R(1)], [P_base_R(2), P_knee_R(2)], 'b-o', 'LineWidth', 3, 'MarkerFaceColor','b');
%     P_crank_end_R = P_base_R + [r_crank*cos(motor_R2_rad(i)); r_crank*sin(motor_R2_rad(i))];
%     plot([P_base_R(1), P_crank_end_R(1)], [P_base_R(2), P_crank_end_R(2)], 'r-o', 'LineWidth', 4, 'MarkerFaceColor','r');
%     P_knee_jig_R = P_knee_R + [r_crank*cos(motor_R2_rad(i)); r_crank*sin(motor_R2_rad(i))];
%     plot([P_crank_end_R(1), P_knee_jig_R(1)], [P_crank_end_R(2), P_knee_jig_R(2)], 'm--', 'LineWidth', 1.5);
%     plot([P_knee_R(1), P_hinge_R(1)], [P_knee_R(2), P_hinge_R(2)], 'g-o', 'LineWidth', 2.5, 'MarkerFaceColor','g');
% 
%     % 琴弓与接触点
%     P_bow_left = P_contact + R_matrix * [-L_bow/2 + x_s; 0]; P_bow_right = P_contact + R_matrix * [L_bow/2 + x_s; 0];
%     plot([P_bow_left(1), P_bow_right(1)], [P_bow_left(2), P_bow_right(2)], 'Color', [0.85 0.5 0], 'LineWidth', 3);
%     plot(P_hinge_L(1), P_hinge_L(2), 'ko', 'MarkerSize', 8, 'MarkerFaceColor', 'y');
%     plot(P_hinge_R(1), P_hinge_R(2), 'ko', 'MarkerSize', 8, 'MarkerFaceColor', 'y');
%     plot(Strings(1,:), Strings(2,:), 'ro', 'MarkerSize', 8, 'MarkerFaceColor', 'r');
%     for s = 1:4, text(Strings(1,s)-0.015, Strings(2,s)-0.03, String_Names{s}, 'FontWeight', 'bold'); end
%     plot(P_contact(1), P_contact(2), 'mx', 'MarkerSize', 15, 'LineWidth', 3);
% 
%     axis equal; xlim([-0.5, 0.5]); ylim([-0.5, 0.5]); grid on;
% 
%     data_str = {
%         sprintf('时间: %.2f s | 音符: %s (%s弦)', t(i), notes(current_state_idx(i)).note_name, notes(current_state_idx(i)).string), ...
%         sprintf('L1大腿: %5.1f RPM | %5.1f mN·m', abs(omega_L1_deg(i)/6), abs(torque_L1(i)*1000)), ...
%         sprintf('L2小腿: %5.1f RPM | %5.1f mN·m', abs(omega_L2_deg(i)/6), abs(torque_L2(i)*1000)), ...
%         sprintf('R1大腿: %5.1f RPM | %5.1f mN·m', abs(omega_R1_deg(i)/6), abs(torque_R1(i)*1000)), ...
%         sprintf('R2小腿: %5.1f RPM | %5.1f mN·m', abs(omega_R2_deg(i)/6), abs(torque_R2(i)*1000))
%     };
%     text(-0.48, 0.36, data_str, 'FontSize', 9, 'BackgroundColor', 'w', 'EdgeColor', 'k', 'FontName', 'Courier');
%     title('全系统平衡：4关节双曲柄狗腿动力学与压弦监测');
%     xlabel('X方向 (m)'); ylabel('Y方向 (m)'); drawnow;
% end
% 
% %% 8. 绘制完整的系统选型分析曲线图
% figure('Name', '全系统4电机全面选型曲线图', 'Position', [100, 50, 1200, 800]);
% 
% subplot(3,2,1);
% plot(t, v_slide, 'r', 'LineWidth', 2);
% title('滑块直线速度需求 (解析解)'); xlabel('时间 (s)'); ylabel('速度 (m/s)'); grid on;
% 
% subplot(3,2,2);
% plot(t, omega_L1_deg/6, 'b', t, omega_L2_deg/6, 'b--', t, omega_R1_deg/6, 'g', t, omega_R2_deg/6, 'g--', 'LineWidth', 1.5);
% title('全车4关节电机转速对比 (gradient中心差分)'); xlabel('时间 (s)'); ylabel('转速 (RPM)');
% legend('L1 大腿', 'L2 小腿', 'R1 大腿', 'R2 小腿'); grid on;
% 
% subplot(3,2,3);
% plot(t, torque_slide_motor, 'r', 'LineWidth', 2);
% title('滑轨驱动电机瞬时扭矩'); xlabel('时间 (s)'); ylabel('扭矩 (N·m)'); grid on;
% 
% subplot(3,2,4);
% plot(t, torque_L1, 'b', t, torque_L2, 'b--', t, torque_R1, 'g', t, torque_R2, 'g--', 'LineWidth', 1.5);
% title('4关节电机瞬时扭矩对比 (全耦合动力学)'); xlabel('时间 (s)'); ylabel('扭矩 (N·m)');
% legend('L1 大腿', 'L2 小腿', 'R1 大腿', 'R2 小腿'); grid on;
% 
% subplot(3,2,5);
% plot(t, torque_slide_motor .* omega_slide_motor, 'r', 'LineWidth', 2);
% title('滑轨电机机械功率'); xlabel('时间 (s)'); ylabel('功率 (W)'); grid on;
% 
% subplot(3,2,6);
% plot(t, abs(torque_L1 .* omega_L1), 'b', t, abs(torque_L2 .* omega_L2), 'b--', t, abs(torque_R1 .* omega_R1), 'g', t, abs(torque_R2 .* omega_R2), 'g--', 'LineWidth', 1.5);
% title('4关节电机轴向功率对比 (全耦合动力学)'); xlabel('时间 (s)'); ylabel('功率 (W)');
% legend('L1 大腿', 'L2 小腿', 'R1 大腿', 'R2 小腿'); grid on;
% 
% %% 9. 最终选型峰值打印报告
% fprintf('══════════════════════════════════════════════════════\n');
% fprintf(' Part 1: 全系统 4 电机选型数据报告 (全耦合动力学)\n');
% fprintf('══════════════════════════════════════════════════════\n');
% fprintf('【左腿 L1 电机 (大腿)】 -> 最大转速: %5.2f RPM | 峰值扭矩: %6.2f mN·m | 峰值功率: %.2f W\n', max(abs(omega_L1_deg))/6, max(abs(torque_L1))*1000, max(abs(torque_L1.*omega_L1)));
% fprintf('【左腿 L2 电机 (小腿)】 -> 最大转速: %5.2f RPM | 峰值扭矩: %6.2f mN·m | 峰值功率: %.2f W\n', max(abs(omega_L2_deg))/6, max(abs(torque_L2))*1000, max(abs(torque_L2.*omega_L2)));
% fprintf('【右腿 R1 电机 (大腿)】 -> 最大转速: %5.2f RPM | 峰值扭矩: %6.2f mN·m | 峰值功率: %.2f W\n', max(abs(omega_R1_deg))/6, max(abs(torque_R1))*1000, max(abs(torque_R1.*omega_R1)));
% fprintf('【右腿 R2 电机 (小腿)】 -> 最大转速: %5.2f RPM | 峰值扭矩: %6.2f mN·m | 峰值功率: %.2f W\n', max(abs(omega_R2_deg))/6, max(abs(torque_R2))*1000, max(abs(torque_R2.*omega_R2)));
% 
% %% 10. 滑轨与丝杠副工程选型指标核心解算
% fprintf('\n══════════════════════════════════════════════════════\n');
% fprintf(' Part 2: 滑轨与传动系统工程选型核心指标报告\n');
% fprintf('══════════════════════════════════════════════════════\n');
% 
% stroke_bow = max(x_slide_t) - min(x_slide_t);
% L_slider_hardware = L_hold + 0.06;
% safety_margin = 0.04 * 2;
% L_rail_min = stroke_bow + L_slider_hardware + safety_margin;
% 
% mu_rail = 0.005;
% F_axial_all = m_slider * a_slide ...
%             + mu_rail * (m_slider * g + abs(F_base_L_y + F_base_R_y)) ...
%             + (F_base_L_x + F_base_R_x);
% F_axial_peak = max(abs(F_axial_all));
% 
% My_moment_all = zeros(1, num_steps);
% for i = 1:num_steps
%     F_y_L_curr = F_base_L_y(i);
%     F_y_R_curr = F_base_R_y(i);
%     My_moment_all(i) = F_y_L_curr * (-L_hold/2) + F_y_R_curr * (L_hold/2);
% end
% My_moment_peak = max(abs(My_moment_all));
% 
% Mx_moment_all = F_base_L_x * (-L_hold/2) + F_base_R_x * (L_hold/2);
% Mx_moment_peak = max(abs(Mx_moment_all));
% 
% max_v_slide = max(abs(v_slide));
% max_n_screw = (max_v_slide / Lead_slide) * 60;
% 
% fprintf('【1. 几何尺寸指标】\n');
% fprintf('   * 纯运弓有效行程 (Stroke):       %5.2f mm\n', stroke_bow * 1000);
% fprintf('   * 建议滑轨最小物理总长 (Length):  %5.2f mm\n', L_rail_min * 1000);
% 
% fprintf('\n【2. 滚珠丝杠副选型核心参数】\n');
% fprintf('   * 轴向峰值动态推力 (Peak Force):  %5.2f N\n', F_axial_peak);
% fprintf('   * 丝杠峰值运转转速 (Peak Speed):  %5.2f RPM\n', max_n_screw);
% 
% fprintf('\n【3. 直线导轨动态力矩负载】\n');
% fprintf('   * 峰值动态颠覆力矩 My (Pitching): %5.2f N·m\n', My_moment_peak);
% fprintf('   * 峰值动态扭转力矩 Mx (Rolling):  %5.2f N·m\n', Mx_moment_peak);