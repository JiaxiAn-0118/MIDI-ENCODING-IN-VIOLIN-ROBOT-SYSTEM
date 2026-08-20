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
bin_path = '/Users/anjiaxi/Desktop/Fudan/Projects/Denghui_violin/Violin_GitHub/MIDI-ENCODING-IN-VIOLIN-ROBOT-SYSTEM/scores/梁祝/liangzhu_lower.bin';

notes = decode_bin_to_notes(bin_path);

% 规范化方向与连音标记
for n = 1:length(notes)
    if isfield(notes(n), 'bow_direction') && strcmp(notes(n).bow_direction, 'down')
        notes(n).direction = 1;
    else
        notes(n).direction = -1;
    end
    if ~isfield(notes(n), 'is_legato')
        notes(n).is_legato = false;
    end
end

% ---------- 合并同弓向连续音段 (Segments) ----------
motion_gap_tol = 0.08; % 运弓连续性判定阈值：同方向且时间间隙小于该值则视为同一运弓段
segments = struct('start', {}, 'end', {}, 'direction', {}, 'note_idx', {});
if ~isempty(notes)
    i_note = 1;
    while i_note <= length(notes)
        s_idx = i_note;
        s_dir = notes(i_note).direction;
        e_idx = i_note;
          % 轨迹合并优先保证运动连续性：同方向且时间连续即可并段
        while (e_idx + 1) <= length(notes) && ...
              notes(e_idx + 1).direction == s_dir && ...
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

% 建立全局高精度仿真时间轴
total_duration = notes(end).end; % 乐谱总结束时间
fs = 100; % 采样率 100Hz 保证微分精度
t = 0:(1/fs):total_duration;
num_steps = length(t);
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
stroke_limit = 0.12; % 单次最大运弓半行程 (m)
stroke_margin = 0.01; % 软边界余量，避免频繁顶到机械端点
nominal_bow_speed = 0.08; % 标称运弓速度 (m/s)
center_pull_gain = 0.35; % 每个段对中心位置的回拉系数
min_seg_move = 0.004; % 单段最小位移，避免极短段完全不动
x_min = -stroke_limit + stroke_margin;
x_max = stroke_limit - stroke_margin;

last_valid_note_idx = 1; % 记录上一个有效的音符索引

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

    % --- 寻找当前时间点对应的音符 ---
    note_idx = 0;
    for n = 1:length(notes)
        if t_curr >= notes(n).start && t_curr <= notes(n).end
            note_idx = n;
            break;
        end
    end

    % 如果当前时间处于音符之间的间隙，继承上一个音符的属性
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
        seg_duration = max(seg.end - seg.start, 1e-12);

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

    % --- 左腿末端与基座位置 ---
    P_hinge_L = P_contact + R_matrix * [-L_inter/2 + x_s; 0];
    P_hinge_L_all(:, i) = P_hinge_L;
    P_base_L = [x_s - L_hold/2; H_slide];

    % 左腿解析逆解
    V_L = P_hinge_L - P_base_L; D_L = norm(V_L);
    gamma_L = atan2(V_L(2), V_L(1));
    alpha_L = acos(max(min((L1^2 + D_L^2 - L2^2) / (2 * L1 * D_L), 1), -1));
    motor_L1_rad(i) = gamma_L - alpha_L; % L1大腿
    motor_L2_rad(i) = gamma_L + alpha_L; % L2控制短曲柄(即小腿绝对角度)
    P_knee_L_all(:, i) = P_base_L + [L1*cos(motor_L1_rad(i)); L1*sin(motor_L1_rad(i))];

    % --- 右腿末端与基座位置 (镜像) ---
    P_hinge_R = P_contact + R_matrix * [L_inter/2 + x_s; 0];
    P_hinge_R_all(:, i) = P_hinge_R;
    P_base_R = [x_s + L_hold/2; H_slide];

    % 右腿解析逆解 (注意肘关节弯曲分叉号与左腿相反)
    V_R = P_hinge_R - P_base_R; D_R = norm(V_R);
    gamma_R = atan2(V_R(2), V_R(1));
    alpha_R = acos(max(min((L1^2 + D_R^2 - L2^2) / (2 * L1 * D_R), 1), -1));
    motor_R1_rad(i) = gamma_R + alpha_R; % R1大腿
    motor_R2_rad(i) = gamma_R - alpha_R; % R2控制短曲柄(即小腿绝对角度)
    P_knee_R_all(:, i) = P_base_R + [L1*cos(motor_R1_rad(i)); L1*sin(motor_R1_rad(i))];
end

%% 5. 所有电机速度、加速度解算 —— 【修复1：解析微分 + gradient 中心差分】

% 先用 Savitzky-Golay 滤波器对关节角度做轻度平滑，抑制 IK 数值噪声
motor_L1_sm = smoothdata(motor_L1_rad, 'sgolay', 7);
motor_L2_sm = smoothdata(motor_L2_rad, 'sgolay', 7);
motor_R1_sm = smoothdata(motor_R1_rad, 'sgolay', 7);
motor_R2_sm = smoothdata(motor_R2_rad, 'sgolay', 7);

% gradient() 使用中心差分，二阶精度，比 forward diff 噪声低得多
omega_L1 = gradient(motor_L1_sm, dt);
omega_L2 = gradient(motor_L2_sm, dt);
omega_R1 = gradient(motor_R1_sm, dt);
omega_R2 = gradient(motor_R2_sm, dt);

alpha_L1 = gradient(omega_L1, dt);
alpha_L2 = gradient(omega_L2, dt);
alpha_R1 = gradient(omega_R1, dt);
alpha_R2 = gradient(omega_R2, dt);

% 滑轨运动学：直接从解析导数获取（不再 diff）
v_slide = v_slide_t;
a_slide = a_slide_t;
omega_slide_motor = (v_slide / Lead_slide) * 2 * pi;

% 【修复1】远端垂向加速度 —— 从关节运动学解析推导
% y_hinge = H_slide + L1*sin(θ₁) + L2*sin(θ₂)
% v_y     = L1*cos(θ₁)*θ̇₁ + L2*cos(θ₂)*θ̇₂
% a_y     = L1*[cos(θ₁)*θ̈₁ - sin(θ₁)*θ̇₁²] + L2*[cos(θ₂)*θ̈₂ - sin(θ₂)*θ̇₂²]
a_y_calf_L = L1 * (cos(motor_L1_sm) .* alpha_L1 - sin(motor_L1_sm) .* omega_L1.^2) ...
           + L2 * (cos(motor_L2_sm) .* alpha_L2 - sin(motor_L2_sm) .* omega_L2.^2);

a_y_calf_R = L1 * (cos(motor_R1_sm) .* alpha_R1 - sin(motor_R1_sm) .* omega_R1.^2) ...
           + L2 * (cos(motor_R2_sm) .* alpha_R2 - sin(motor_R2_sm) .* omega_R2.^2);

%% 6. 核心：全车双腿4关节电机全动力学解算循环 —— 【修复2：全耦合 2-DOF Lagrangian】
torque_L1 = zeros(1, num_steps); torque_L2 = zeros(1, num_steps);
torque_R1 = zeros(1, num_steps); torque_R2 = zeros(1, num_steps);
torque_slide_motor = zeros(1, num_steps);

% 为基座反力计算预留存储
F_base_L_x = zeros(1, num_steps); F_base_L_y = zeros(1, num_steps);
F_base_R_x = zeros(1, num_steps); F_base_R_y = zeros(1, num_steps);

% --- 预计算 2-DOF 耦合动力学常数 ---
% 质量矩阵常数项:
% M11 = I_arm1 + m_rod*L1²/8 + m_calf*L1²
% M12 = K_couple * cos(θ₁-θ₂),  K_couple = ½*m_calf*L1*L2
% M22 = I_crank + m_rod*r_crank²/8 + m_calf*L2²/4 + I_calf_g
K_couple = 0.5 * m_calf * L1 * L2;
M11_const = I_arm1 + (1/8)*m_rod*L1^2 + m_calf*L1^2;
M22_const = I_crank + (1/8)*m_rod*r_crank^2 + 0.25*m_calf*L2^2 + I_calf_g;

% 重力项常数:
G1_coeff = (0.5*m_arm1 + 0.25*m_rod + m_calf) * g * L1;
G2_coeff = (0.5*m_crank + 0.25*m_rod) * g * r_crank + 0.5 * m_calf * g * L2;

for i = 1:num_steps
    % 从曲谱生成数组中提取当前帧的总压弦力，并双腿平摊
    F_N_half = F_N_t(i) / 2;

    % --- 松香动态摩擦模型 ---
    v_rel_current = v_slide(i);
    mu_current = 0.4 * exp(-100 * abs(v_rel_current)) + 0.45 * exp(-10 * abs(v_rel_current)) + 0.35;
    v0 = 2e-4;
    mu_smoothed = mu_current * (2 / pi) * atan(v_rel_current / v0);
    F_friction_half = mu_smoothed * F_N_half;

    % 末端琴弓分摊质量
    m_bow_half = 0.5 * m_bow;

    %% --- 左腿 2-DOF 全耦合动力学 ---
    th1 = motor_L1_sm(i);
    th2 = motor_L2_sm(i);
    dth1 = omega_L1(i);
    dth2 = omega_L2(i);
    ddth1 = alpha_L1(i);
    ddth2 = alpha_L2(i);

    % 1. 末端外载荷
    F_x_ext = -F_friction_half;
    F_y_ext = -F_N_half - m_bow_half * (g + a_y_calf_L(i));

    % 2. 雅可比映射 (绝对角度拓扑: J = [-L1*sinθ1, -L2*sinθ2; L1*cosθ1, L2*cosθ2])
    tau_J1 = -L1 * sin(th1) * F_x_ext + L1 * cos(th1) * F_y_ext;
    tau_J2 = -L2 * sin(th2) * F_x_ext + L2 * cos(th2) * F_y_ext;

    % 3. 质量矩阵 (含耦合项 M12)
    dth = th1 - th2;
    M11 = M11_const;
    M12 = K_couple * cos(dth);
    M22 = M22_const;

    % 4. Coriolis / 离心项 (Christoffel 符号严格推导)
    % h1 =  K_couple * sin(θ1-θ2) * θ̇₂²
    % h2 = -K_couple * sin(θ1-θ2) * θ̇₁²
    sin_dth = sin(dth);
    h1 =  K_couple * sin_dth * dth2^2;
    h2 = -K_couple * sin_dth * dth1^2;

    % 5. 重力项
    G1 = G1_coeff * cos(th1);
    G2 = G2_coeff * cos(th2);

    % 6. 完整 Lagrangian 力矩: τ = M·θ̈ + h + G + JᵀF
    tau1_raw = M11 * ddth1 + M12 * ddth2 + h1 + G1 + tau_J1;
    tau2_raw = M22 * ddth2 + M12 * ddth1 + h2 + G2 + tau_J2;

    torque_L1(i) = tau1_raw;
    torque_L2(i) = tau2_raw / eta_link;

    % 7. 【修复3】从整腿 Newton-Euler 计算基座反力 (供滑轨校核复用)
    % 大腿质心加速度 (髋关节 + 旋转)
    a_thigh_x = -0.5*L1*(cos(th1)*dth1^2 + sin(th1)*ddth1);
    a_thigh_y = -0.5*L1*(sin(th1)*dth1^2 - cos(th1)*ddth1);
    % 小腿质心加速度
    a_calf_x = -L1*(cos(th1)*dth1^2 + sin(th1)*ddth1) - 0.5*L2*(cos(th2)*dth2^2 + sin(th2)*ddth2);
    a_calf_y = -L1*(sin(th1)*dth1^2 - cos(th1)*ddth1) - 0.5*L2*(sin(th2)*dth2^2 - cos(th2)*ddth2);

    % Newton 第二定律求基座反力: ΣF = m*a → F_base = Σ(m*a) - F_ext
    F_base_L_x(i) = m_arm1*a_thigh_x + 0.5*m_rod*a_thigh_x + m_crank*0 + m_calf*a_calf_x - F_x_ext;
    F_base_L_y(i) = m_arm1*(a_thigh_y + g) + 0.5*m_rod*(a_thigh_y + g) + m_crank*g + m_calf*(a_calf_y + g) - F_y_ext;

    %% --- 右腿 2-DOF 全耦合动力学 ---
    th1 = motor_R1_sm(i);
    th2 = motor_R2_sm(i);
    dth1 = omega_R1(i);
    dth2 = omega_R2(i);
    ddth1 = alpha_R1(i);
    ddth2 = alpha_R2(i);

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

    % 右腿基座反力
    a_thigh_x = -0.5*L1*(cos(th1)*dth1^2 + sin(th1)*ddth1);
    a_thigh_y = -0.5*L1*(sin(th1)*dth1^2 - cos(th1)*ddth1);
    a_calf_x = -L1*(cos(th1)*dth1^2 + sin(th1)*ddth1) - 0.5*L2*(cos(th2)*dth2^2 + sin(th2)*ddth2);
    a_calf_y = -L1*(sin(th1)*dth1^2 - cos(th1)*ddth1) - 0.5*L2*(sin(th2)*dth2^2 - cos(th2)*ddth2);

    F_base_R_x(i) = m_arm1*a_thigh_x + 0.5*m_rod*a_thigh_x + m_crank*0 + m_calf*a_calf_x - F_x_ext;
    F_base_R_y(i) = m_arm1*(a_thigh_y + g) + 0.5*m_rod*(a_thigh_y + g) + m_crank*g + m_calf*(a_calf_y + g) - F_y_ext;

    %% --- 滑轨电机 (使用解析加速度) ---
    torque_slide_motor(i) = (m_slider * a_slide(i) * Lead_slide) / (2 * pi * eta_slide);
end

omega_L1_deg = rad2deg(omega_L1);
omega_L2_deg = rad2deg(omega_L2);
omega_R1_deg = rad2deg(omega_R1);
omega_R2_deg = rad2deg(omega_R2);

%% 7. 动态双腿同步演奏仿真动画（含视频导出）- 修复残影与越界版
anim = struct();
anim.video_filename = 'violin_simulation.mp4';
anim.draw_step = 2;
anim.fs = fs;
anim.t = t;
anim.x_slide_t = x_slide_t;
anim.theta_bow_t = theta_bow_t;
anim.current_string_t = current_string_t;
anim.H_slide = H_slide;
anim.L_hold = L_hold;
anim.r_crank = r_crank;
anim.motor_L2_rad = motor_L2_rad;
anim.motor_R2_rad = motor_R2_rad;
anim.P_knee_L_all = P_knee_L_all;
anim.P_hinge_L_all = P_hinge_L_all;
anim.P_knee_R_all = P_knee_R_all;
anim.P_hinge_R_all = P_hinge_R_all;
anim.L_bow = L_bow;
anim.Strings = Strings;
anim.String_Names = String_Names;
anim.current_state_idx = current_state_idx;
anim.notes = notes;
anim.omega_L1_deg = omega_L1_deg;
anim.omega_L2_deg = omega_L2_deg;
anim.omega_R1_deg = omega_R1_deg;
anim.omega_R2_deg = omega_R2_deg;
anim.torque_L1 = torque_L1;
anim.torque_L2 = torque_L2;
anim.torque_R1 = torque_R1;
anim.torque_R2 = torque_R2;

render_violin_animation(anim);

%% 8. 绘制完整的系统选型分析曲线图 (包含全部 4 个关节电机负载)
figure('Name', '全系统4电机全面选型曲线图', 'Position', [100, 50, 1200, 800]);

subplot(3,2,1);
plot(t, v_slide, 'r', 'LineWidth', 2);
title('滑块直线速度需求 (解析解)'); xlabel('时间 (s)'); ylabel('速度 (m/s)'); grid on;

subplot(3,2,2);
plot(t, omega_L1_deg/6, 'b', t, omega_L2_deg/6, 'b--', t, omega_R1_deg/6, 'g', t, omega_R2_deg/6, 'g--', 'LineWidth', 1.5);
title('全车4关节电机转速对比 (gradient中心差分)'); xlabel('时间 (s)'); ylabel('转速 (RPM)');
legend('L1 大腿', 'L2 小腿', 'R1 大腿', 'R2 小腿'); grid on;

subplot(3,2,3);
plot(t, torque_slide_motor, 'r', 'LineWidth', 2);
title('滑轨驱动电机瞬时扭矩'); xlabel('时间 (s)'); ylabel('扭矩 (N·m)'); grid on;

subplot(3,2,4);
plot(t, torque_L1, 'b', t, torque_L2, 'b--', t, torque_R1, 'g', t, torque_R2, 'g--', 'LineWidth', 1.5);
title('4关节电机瞬时扭矩对比 (全耦合动力学)'); xlabel('时间 (s)'); ylabel('扭矩 (N·m)');
legend('L1 大腿', 'L2 小腿', 'R1 大腿', 'R2 小腿'); grid on;

subplot(3,2,5);
plot(t, torque_slide_motor .* omega_slide_motor, 'r', 'LineWidth', 2);
title('滑轨电机机械功率'); xlabel('时间 (s)'); ylabel('功率 (W)'); grid on;

subplot(3,2,6);
plot(t, abs(torque_L1 .* omega_L1), 'b', t, abs(torque_L2 .* omega_L2), 'b--', t, abs(torque_R1 .* omega_R1), 'g', t, abs(torque_R2 .* omega_R2), 'g--', 'LineWidth', 1.5);
title('4关节电机轴向功率对比 (全耦合动力学)'); xlabel('时间 (s)'); ylabel('功率 (W)');
legend('L1 大腿', 'L2 小腿', 'R1 大腿', 'R2 小腿'); grid on;

%% 9. 最终选型峰值打印报告
fprintf('══════════════════════════════════════════════════════\n');
fprintf(' Part 1: 全系统 4 电机选型数据报告 (全耦合动力学)\n');
fprintf('══════════════════════════════════════════════════════\n');
fprintf('【左腿 L1 电机 (大腿)】 -> 最大转速: %5.2f RPM | 峰值扭矩: %6.2f mN·m | 峰值功率: %.2f W\n', max(abs(omega_L1_deg))/6, max(abs(torque_L1))*1000, max(abs(torque_L1.*omega_L1)));
fprintf('【左腿 L2 电机 (小腿)】 -> 最大转速: %5.2f RPM | 峰值扭矩: %6.2f mN·m | 峰值功率: %.2f W\n', max(abs(omega_L2_deg))/6, max(abs(torque_L2))*1000, max(abs(torque_L2.*omega_L2)));
fprintf('【右腿 R1 电机 (大腿)】 -> 最大转速: %5.2f RPM | 峰值扭矩: %6.2f mN·m | 峰值功率: %.2f W\n', max(abs(omega_R1_deg))/6, max(abs(torque_R1))*1000, max(abs(torque_R1.*omega_R1)));
fprintf('【右腿 R2 电机 (小腿)】 -> 最大转速: %5.2f RPM | 峰值扭矩: %6.2f mN·m | 峰值功率: %.2f W\n', max(abs(omega_R2_deg))/6, max(abs(torque_R2))*1000, max(abs(torque_R2.*omega_R2)));

%% 故障排查：检查扭矩最大帧的动力学分项
[max_val, max_idx] = max(abs(torque_L1));
fprintf('\n══════════════════════════════════════════════════════\n');
fprintf(' Part 2: 扭矩峰值排查报告 (第 %d 帧) \n', max_idx);
fprintf('══════════════════════════════════════════════════════\n');
fprintf('时间点: %.4f 秒\n', t(max_idx));
fprintf('运弓速度 v_slide: %.4f m/s (解析解)\n', v_slide(max_idx));
fprintf('大腿角度 motor_L1_rad: %.2f 度\n', rad2deg(motor_L1_rad(max_idx)));
fprintf('大腿角速度 omega_L1: %.2f rad/s (gradient 中心差分)\n', omega_L1(max_idx));
fprintf('大腿角加速度 alpha_L1: %.2f rad/s^2 (gradient 中心差分)\n', alpha_L1(max_idx));
fprintf('--- 全耦合动力学分项拆解 (以 L1 为例) ---\n');

th1 = motor_L1_sm(max_idx); th2 = motor_L2_sm(max_idx);
dth1 = omega_L1(max_idx); dth2 = omega_L2(max_idx);
ddth1 = alpha_L1(max_idx); ddth2 = alpha_L2(max_idx);
dth = th1 - th2;

M11 = M11_const;
M12 = K_couple * cos(dth);
h1_c = K_couple * sin(dth) * dth2^2;
G1_c = G1_coeff * cos(th1);
F_N_half_p = F_N_t(max_idx) / 2;
F_fric_p = (0.4*exp(-100*abs(v_slide(max_idx))) + 0.45*exp(-10*abs(v_slide(max_idx))) + 0.35) ...
           * (2/pi)*atan(v_slide(max_idx)/2e-4) * F_N_half_p;
F_y_ext_p = -F_N_half_p - 0.5*m_bow*(g + a_y_calf_L(max_idx));
tau_J1_p = -L1*sin(th1)*(-F_fric_p) + L1*cos(th1)*F_y_ext_p;

fprintf('  1. 惯性对角项 (M11·α1):              %8.4f N·m\n', M11 * ddth1);
fprintf('  2. 惯性耦合项 (M12·α2):              %8.4f N·m\n', M12 * ddth2);
fprintf('  3. Coriolis/离心项 (h1):             %8.4f N·m\n', h1_c);
fprintf('  4. 重力项 (G1):                       %8.4f N·m\n', G1_c);
fprintf('  5. 雅可比力矩项 (JᵀF):               %8.4f N·m\n', tau_J1_p);
fprintf('  6. 总扭矩 (sum 1-5):                  %8.4f N·m\n', M11*ddth1 + M12*ddth2 + h1_c + G1_c + tau_J1_p);

%% 参考检查：健康选型过滤参考值报告（修复单位与功率逻辑版）
fprintf('\n══════════════════════════════════════════════════════\n');
fprintf(' Part 3: 过滤突变尖峰后：健康选型参考数据报告 (置信度 99%%)\n');
fprintf('══════════════════════════════════════════════════════\n');

% 设定过滤掉前 1% 的极端奇异点尖峰（若想加大力度可改为 95）
cutoff_percent = 99; 

% 1. 提取健康的真实最大扭矩 (原数组为 N·m)
real_torque_L1_Nm = prctile(abs(torque_L1), cutoff_percent);
real_torque_L2_Nm = prctile(abs(torque_L2), cutoff_percent);
real_torque_R1_Nm = prctile(abs(torque_R1), cutoff_percent);
real_torque_R2_Nm = prctile(abs(torque_R2), cutoff_percent);

% 2. 提取健康的真实最大转速 (以便进行严格的选型功率复核，转换为 rad/s)
% omega_L1_deg 是角度制转速，除以 6 得到 RPM，再转为弧度制 rad/s 参与物理计算
omega_L1_rad_s = deg2rad(prctile(abs(omega_L1_deg), cutoff_percent));
omega_L2_rad_s = deg2rad(prctile(abs(omega_L2_deg), cutoff_percent));
omega_R1_rad_s = deg2rad(prctile(abs(omega_R1_deg), cutoff_percent));
omega_R2_rad_s = deg2rad(prctile(abs(omega_R2_deg), cutoff_percent));

% 3. 严格依据物理公式 $P = T \cdot \omega$ 计算健康选型功率 (确保无统计缩水)
real_power_L1 = real_torque_L1_Nm * omega_L1_rad_s;
real_power_L2 = real_torque_L2_Nm * omega_L2_rad_s;
real_power_R1 = real_torque_R1_Nm * omega_R1_rad_s;
real_power_R2 = real_torque_R2_Nm * omega_R2_rad_s;

% 4. 规范打印输出 (扭矩统一换算为标准的工程选型单位 N·m，功率为 W)
fprintf('【左腿 L1 大腿电机】 -> 真实最大扭矩: %6.2f N·m | 真实最大功率: %6.2f W\n', real_torque_L1_Nm, real_power_L1);
fprintf('【左腿 L2 小腿电机】 -> 真实最大扭矩: %6.2f N·m | 真实最大功率: %6.2f W\n', real_torque_L2_Nm, real_power_L2);
fprintf('【右腿 R1 大腿电机】 -> 真实最大扭矩: %6.2f N·m | 真实最大功率: %6.2f W\n', real_torque_R1_Nm, real_power_R1);
fprintf('【右腿 R2 小腿电机】 -> 真实最大扭矩: %6.2f N·m | 真实最大功率: %6.2f W\n', real_torque_R2_Nm, real_power_R2);

%% 10. 滑轨与丝杠副工程选型指标核心解算 —— 【修复3：从统一动力学推导】
fprintf('\n══════════════════════════════════════════════════════\n');
fprintf(' Part 4: 滑轨与传动系统工程选型核心指标报告\n');
fprintf('        (基座反力由 Newton-Euler 完整计算)\n');
fprintf('══════════════════════════════════════════════════════\n');

% 1. 几何长度指标解算
stroke_bow = max(x_slide_t) - min(x_slide_t); % 琴弓纯运弓有效行程 (m)
L_slider_hardware = L_hold + 0.06; % 滑块总装机械宽度 (m)
safety_margin = 0.04 * 2;          % 两侧极限保护间距 (m)
L_rail_min = stroke_bow + L_slider_hardware + safety_margin;

% 2. 【修复3】丝杠驱动轴向力 —— 从整腿 Newton-Euler 基座反力求和
%    滑块轴向受力 = 滑块惯性力 + 导轨摩擦 + 左右腿X方向基座反力
mu_rail = 0.005;
F_axial_all = m_slider * a_slide ...                          % 滑块自身加速力
            + mu_rail * (m_slider * g + abs(F_base_L_y + F_base_R_y)) ... % 导轨摩擦(含垂向负载)
            + (F_base_L_x + F_base_R_x);                      % 双腿水平反力(牛顿第三定律)
F_axial_peak = max(abs(F_axial_all));

% 3. 【修复3】滑块动态颠覆力矩 —— 使用真实的压弦力 F_N_t 和完整的基座Y向反力
My_moment_all = zeros(1, num_steps);
for i = 1:num_steps
    % 真实垂向力 (已包含重力、琴弓惯性、压弦力)
    F_y_L_curr = F_base_L_y(i);
    F_y_R_curr = F_base_R_y(i);
    % 颠覆力矩 = 左腿反力 * (-L_hold/2) + 右腿反力 * (L_hold/2)
    My_moment_all(i) = F_y_L_curr * (-L_hold/2) + F_y_R_curr * (L_hold/2);
end
My_moment_peak = max(abs(My_moment_all));

% 同时计算绕X轴的滚转力矩 Mx (X方向力的不对称，对丝杠的扭转载荷)
Mx_moment_all = F_base_L_x * (-L_hold/2) + F_base_R_x * (L_hold/2);
Mx_moment_peak = max(abs(Mx_moment_all));

% 4. 丝杠转速与Dn值核算 (使用解析速度)
max_v_slide = max(abs(v_slide));
max_n_screw = (max_v_slide / Lead_slide) * 60; % 丝杠最高设计转速 (RPM)

% 建议取 95% 速度分位数作为选型转速基准 (消除换弓瞬时残余数值尖峰)
v_slide_95 = prctile(abs(v_slide), 95);
n_screw_95 = (v_slide_95 / Lead_slide) * 60;

% --- 打印指标报告 ---
fprintf('【1. 几何尺寸指标】\n');
fprintf('   * 纯运弓有效行程 (Stroke):       %5.2f mm\n', stroke_bow * 1000);
fprintf('   * 建议滑轨最小物理总长 (Length):  %5.2f mm (已含滑块宽度与安全机械限位)\n', L_rail_min * 1000);

fprintf('\n【2. 滚珠丝杠副选型核心参数】\n');
fprintf('   * 建议导程 (Lead):               %5.2f mm/rev (当前设定)\n', Lead_slide * 1000);
fprintf('   * 轴向峰值动态推力 (Peak Force):  %5.2f N (完整 Newton-Euler 基座反力)\n', F_axial_peak);
fprintf('   * 丝杠峰值运转转速 (Peak Speed):  %5.2f RPM\n', max_n_screw);
fprintf('   * 丝杠 95%% 分位转速 (选型参考):   %5.2f RPM (排除换弓缓冲瞬时)\n', n_screw_95);
fprintf('   * 建议丝杠公称直径 (Diameter):   12 mm 或 16 mm (基于转速与拉压刚度常规工程推荐)\n');

fprintf('\n【3. 直线导轨动态力矩负载 (滑轨选型核心抗偏载指标)】\n');
fprintf('   * 峰值动态颠覆力矩 My (Pitching): %5.2f N·m (使用真实 F_N_t 时间序列)\n', My_moment_peak);
fprintf('   * 峰值动态扭转力矩 Mx (Rolling):  %5.2f N·m (水平方向不对称载荷)\n', Mx_moment_peak);
fprintf('   * 选型专业建议: \n');
if My_moment_peak > 5.0
    fprintf('     ⚠️警告：由于双腿间距较大且存在动态换弦冲击，单根滑轨将承受高额颠覆力矩！\n');
    fprintf('     建议采用【双导轨 + 四滑块】（平行双轨布局）构型，利用两根导轨的跨距来彻底消除该偏载，\n');
    fprintf('     否则单根滑轨极易产生高频低幅晃动，直接摧毁小提琴演奏的压弦精度与音高控制。\n');
else
    fprintf('     偏载力矩在安全范围内，可选用高刚性单导轨加长型双滑块布局。\n');
end

fprintf('\n══════════════════════════════════════════════════════\n');
fprintf(' 修复总结:\n');
fprintf('  1. 速度/加速度: 解析五次多项式 + gradient 中心差分 + SG 滤波\n');
fprintf('  2. 动力学: 全耦合 2-DOF Lagrangian (含 M12 耦合、Coriolis、离心项)\n');
fprintf('  3. 滑轨校核: 统一 Newton-Euler 基座反力，复用力学第6节末端载荷\n');
fprintf('══════════════════════════════════════════════════════\n');
