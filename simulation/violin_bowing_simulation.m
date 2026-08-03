clear; clc; close all;

%% 1. 机械几何尺寸与质量参数 (两腿完全对称平衡)
L1 = 0.10;        % 大腿长度 (m) (由 L1/R1 电机直接驱动)
L2 = 0.10;        % 连杆和小腿外壳长度 (m)
H_slide = 0.10;   % 滑轨高度 (m)
L_hold = 0.13;    % 滑块上左右两条腿基座的间距 (m)
L_bow = 0.70;     % 琴弓总长度 70 cm (m)
L_inter = 0.13;   % 琴弓上左右两个铰接点之间的固定距离 (m)

% --- 髋关节平行双曲柄机构物理参数 (左右腿各一套) ---
r_crank = 0.04;   % 髋关节处由 L2/R2 电机直接驱动的“短曲柄”长度 (m)
m_crank = 0.05;   % 短曲柄质量 (kg)
m_rod = 0.08;     % 联结短曲柄与膝关节的“长传动连杆”质量 (kg)
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

%% 2. 小提琴 7 种演奏状态的弦坐标与绝对角度
P_G = [-0.034; -0.005]; P_D = [-0.012;  0.002];
P_A = [ 0.012;  0.002]; P_E = [ 0.034; -0.005];
P_GD = (P_G + P_D) / 2; P_DA = (P_D + P_A) / 2; P_AE = (P_A + P_E) / 2;
Strings = [P_G, P_D, P_A, P_E]; String_Names = {'G弦', 'D弦', 'A弦', 'E弦'};

State_Points = {P_G, P_GD, P_D, P_DA, P_A, P_AE, P_E};
State_Angles = deg2rad([28, 14, 5, 0, -5, -14, -28]); 
State_Names  = {'G单音', 'G-D双音', 'D单音', 'D-A双音', 'A单音', 'A-E双音', 'E单音'};

%% 3. 运弓动作定义（从 JSON 乐谱动态读入）
json_path = '/Users/anjiaxi/Desktop/Fudan/Projects/Denghui_violin/26Summer/software/MIDI/scores/梁祝/liangzhu_lower_from_midi.json';
raw_str = fileread(json_path);
score_data = jsondecode(raw_str);
notes = score_data.notes;

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
F_N_t = zeros(1, num_steps);
current_state_idx = zeros(1, num_steps); 

% 换弓平滑关键参数
stroke_limit = 0.12;       % 单次最大运弓半行程 (m)
T_bow_blend = 0.05;        % 换弓缓冲时间 (s)

% 运弓动作定义（从 JSON 乐谱动态读入） —— 修复间隙塌陷版
last_valid_note_idx = 1; % 记录上一个有效的音符索引

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
    
    % 如果当前时间处于音符之间的间隙，继承上一个音符的属性，防止跳回音符1
    if note_idx == 0
        note_idx = last_valid_note_idx;
    else
        last_valid_note_idx = note_idx; % 更新有效音符索引
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
    
    % 带换弓缓冲的 x_slide_t 轨迹规划
    note_start = curr_note.start;
    note_end = curr_note.end;
    
    % 确定当前音符的基础运弓方向（奇数推，偶数拉）
    if mod(note_idx, 2) == 1
        x_start_raw = -stroke_limit;
        x_end_raw = stroke_limit;
    else
        x_start_raw = stroke_limit;
        x_end_raw = -stroke_limit;
    end
    
    % 判断是否处于音符开头的“换弓缓冲期”
    if (t_curr - note_start < T_bow_blend) && (note_idx > 1)
        % 处于前一个音符向当前音符过渡的缓冲期
        tau = (t_curr - note_start) / T_bow_blend;
        poly_factor = 10*tau^3 - 15*tau^4 + 6*tau^5;
        
        % 上一个音符结束时的位置
        if mod(note_idx-1, 2) == 1
            x_prev_end = stroke_limit;
        else
            x_prev_end = -stroke_limit;
        end
        
        % 从上一个音符的终点，平滑过渡到当前音符正常运弓轨迹的起点
        x_slide_t(i) = x_prev_end + (x_start_raw - x_prev_end) * poly_factor;
        
    else
        % 缓冲期过后，走正常的线性运弓轨迹
        % 为了扣除缓冲期对行程的影响，重新规划剩余时间内的线性位移
        t_remain_start = note_start + T_bow_blend;
        if note_idx == 1, t_remain_start = note_start; end % 第一个音符无需缓冲
        
        tau_linear = (t_curr - t_remain_start) / (note_end - t_remain_start);
        tau_linear = max(min(tau_linear, 1), 0); % 截断保护
        
        x_slide_t(i) = x_start_raw + (x_end_raw - x_start_raw) * tau_linear;
    end
end

% 对换弦角度进行高斯平滑，消除换弦瞬间的阶跃
theta_bow_t = smoothdata(theta_bow_target, 'gaussian', 15);
theta_bow_t(end) = theta_bow_t(end-1);

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
    motor_L2_rad(i) = gamma_L + alpha_L; % L2控制短曲柄
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
    motor_R2_rad(i) = gamma_R - alpha_R; % R2控制短曲柄
    P_knee_R_all(:, i) = P_base_R + [L1*cos(motor_R1_rad(i)); L1*sin(motor_R1_rad(i))];
end

%% 5. 所有电机速度、加速度解算
omega_L1 = [0, diff(motor_L1_rad) / dt]; omega_L2 = [0, diff(motor_L2_rad) / dt];
alpha_L1 = [0, diff(omega_L1) / dt];     alpha_L2 = [0, diff(omega_L2) / dt];

omega_R1 = [0, diff(motor_R1_rad) / dt]; omega_R2 = [0, diff(motor_R2_rad) / dt];
alpha_R1 = [0, diff(omega_R1) / dt];     alpha_R2 = [0, diff(omega_R2) / dt];

v_slide = [0, diff(x_slide_t) / dt];    
a_slide = [0, diff(v_slide) / dt];    
omega_slide_motor = (v_slide / Lead_slide) * 2 * pi;

% 远端垂向加速度解算
a_y_calf_L = [0, diff([0, diff(P_hinge_L_all(2, :)) / dt]) / dt];
a_y_calf_R = [0, diff([0, diff(P_hinge_R_all(2, :)) / dt]) / dt];

%% 6. 核心：全车双腿4关节电机全动力学解算循环 (精准耦合修正版)
torque_L1 = zeros(1, num_steps); torque_L2 = zeros(1, num_steps);
torque_R1 = zeros(1, num_steps); torque_R2 = zeros(1, num_steps);
torque_slide_motor = zeros(1, num_steps);

% 补充定义连杆和小腿的转动惯量 (绕各自质心)
I_rod_g = (1/12) * m_rod * L2^2; 
I_calf_g = (1/12) * m_calf * L2^2; % 小腿外壳绕自身质心的转动惯量

for i = 1:num_steps
    % 从曲谱生成数组中提取当前帧的总压弦力，并双腿平摊
    F_N_half = F_N_t(i) / 2; 
    
    % --- 保持你原本的松香动态摩擦模型不变 ---
    v_rel_current = v_slide(i);
    mu_current = 0.4 * exp(-100 * abs(v_rel_current)) + 0.45 * exp(-10 * abs(v_rel_current)) + 0.35;
    v0 = 2e-4; 
    mu_smoothed = mu_current * (2 / pi) * atan(v_rel_current / v0);
    F_friction_half = mu_smoothed * F_N_half;
    
    % 末端琴弓分摊质量
    m_bow_half = 0.5 * m_bow;
    
    %% --- 左腿动力学精准解算 ---
    th_L1 = motor_L1_rad(i);
    th_L2 = motor_L2_rad(i);
    
    % 1. 末端外载荷 (仅含琴弓反力和外力)
    F_x_L_ext = -F_friction_half; 
    F_y_L_ext = -F_N_half - m_bow_half * (g + a_y_calf_L(i));
    
    % 2. 严格的雅可比映射 (基于绝对角度拓扑)
    tau_J_L1 = -L1 * sin(th_L1) * F_x_L_ext + L1 * cos(th_L1) * F_y_L_ext;
    tau_J_L2 = -L2 * sin(th_L2) * F_x_L_ext + L2 * cos(th_L2) * F_y_L_ext;
    
    % 3. 动态惯性与重力项精细重构 (加入多刚体耦合项)
    % 大腿电机L1负载：大腿自身 + 连杆的一半质量作为质点 + 跨运动耦合惯性
    M11 = I_arm1 + 0.25 * m_rod * L1^2;
    G1  = (0.5 * m_arm1 + 0.5 * m_rod) * g * L1 * cos(th_L1);
    
    % 小腿电机L2负载：小腿壳体绕髋关节的转动惯量 + 短曲柄 + 长连杆平动惯量
    M22 = I_crank + I_calf_g + m_calf * L2^2 + 0.25 * m_rod * r_crank^2;
    G2  = m_crank * g * (r_crank/2) * cos(th_L2) + m_calf * g * L2 * cos(th_L2);
    
    % 4. 计算最终输出力矩
    torque_L1(i) = M11 * alpha_L1(i) + G1 + tau_J_L1;
    torque_L2(i) = (M22 * alpha_L2(i) + G2 + tau_J_L2) / eta_link;

    %% --- 右腿动力学精准解算 ---
    th_R1 = motor_R1_rad(i);
    th_R2 = motor_R2_rad(i);
    
    F_x_R_ext = -F_friction_half; 
    F_y_R_ext = -F_N_half - m_bow_half * (g + a_y_calf_R(i));
    
    tau_J_R1 = -L1 * sin(th_R1) * F_x_R_ext + L1 * cos(th_R1) * F_y_R_ext;
    tau_J_R2 = -L2 * sin(th_R2) * F_x_R_ext + L2 * cos(th_R2) * F_y_R_ext;
    
    M11_R = I_arm1 + 0.25 * m_rod * L1^2;
    G1_R  = (0.5 * m_arm1 + 0.5 * m_rod) * g * L1 * cos(th_R1);
    
    M22_R = I_crank + I_calf_g + m_calf * L2^2 + 0.25 * m_rod * r_crank^2;
    G2_R  = m_crank * g * (r_crank/2) * cos(th_R2) + m_calf * g * L2 * cos(th_R2);
    
    torque_R1(i) = M11_R * alpha_R1(i) + G1_R + tau_J_R1;
    torque_R2(i) = (M22_R * alpha_R2(i) + G2_R + tau_J_R2) / eta_link;

    %% --- 滑轨电机 ---
    torque_slide_motor(i) = (m_slider * a_slide(i) * Lead_slide) / (2 * pi * eta_slide);
end

omega_L1_deg = rad2deg(omega_L1); 
omega_L2_deg = rad2deg(omega_L2);
omega_R1_deg = rad2deg(omega_R1); 
omega_R2_deg = rad2deg(omega_R2);

%% 7. 动态双腿同步演奏仿真动画
figure('Name', '双闭环平行双曲柄狗腿同步演奏仿真', 'Position', [50, 80, 1100, 700]);

for i = 1:2:length(t) 
    clf;
    x_s = x_slide_t(i); th_b = theta_bow_t(i); P_contact = current_string_t(:, i); 
    R_matrix = [cos(th_b), -sin(th_b); sin(th_b), cos(th_b)];
    
    plot([-0.6, 0.6], [H_slide, H_slide], 'k--', 'LineWidth', 1.5); hold on;
    slider_w = L_hold + 0.06; 
    rectangle('Position', [x_s - slider_w/2, H_slide, slider_w, 0.02], 'FaceColor', [0.7 0.7 0.7]);
    
    % --- 绘制左腿 (L1, L2) ---
    P_base_L = [x_s - L_hold/2; H_slide]; P_knee_L = P_knee_L_all(:, i); P_hinge_L = P_hinge_L_all(:, i);
    plot([P_base_L(1), P_knee_L(1)], [P_base_L(2), P_knee_L(2)], 'b-o', 'LineWidth', 3, 'MarkerFaceColor','b'); % 大腿
    P_crank_end_L = P_base_L + [r_crank*cos(motor_L2_rad(i)); r_crank*sin(motor_L2_rad(i))];
    plot([P_base_L(1), P_crank_end_L(1)], [P_base_L(2), P_crank_end_L(2)], 'r-o', 'LineWidth', 4, 'MarkerFaceColor','r'); % 左短曲柄
    P_knee_jig_L = P_knee_L + [r_crank*cos(motor_L2_rad(i)); r_crank*sin(motor_L2_rad(i))];
    plot([P_crank_end_L(1), P_knee_jig_L(1)], [P_crank_end_L(2), P_knee_jig_L(2)], 'm--', 'LineWidth', 1.5); % 左长连杆
    plot([P_knee_L(1), P_hinge_L(1)], [P_knee_L(2), P_hinge_L(2)], 'g-o', 'LineWidth', 2.5, 'MarkerFaceColor','g'); % 左小腿
    
    % --- 绘制右腿 (R1, R2) ---
    P_base_R = [x_s + L_hold/2; H_slide]; P_knee_R = P_knee_R_all(:, i); P_hinge_R = P_hinge_R_all(:, i);
    plot([P_base_R(1), P_knee_R(1)], [P_base_R(2), P_knee_R(2)], 'b-o', 'LineWidth', 3, 'MarkerFaceColor','b'); % 右大腿
    P_crank_end_R = P_base_R + [r_crank*cos(motor_R2_rad(i)); r_crank*sin(motor_R2_rad(i))];
    plot([P_base_R(1), P_crank_end_R(1)], [P_base_R(2), P_crank_end_R(2)], 'r-o', 'LineWidth', 4, 'MarkerFaceColor','r'); % 右短曲柄
    P_knee_jig_R = P_knee_R + [r_crank*cos(motor_R2_rad(i)); r_crank*sin(motor_R2_rad(i))];
    plot([P_crank_end_R(1), P_knee_jig_R(1)], [P_crank_end_R(2), P_knee_jig_R(2)], 'm--', 'LineWidth', 1.5); % 右长连杆
    plot([P_knee_R(1), P_hinge_R(1)], [P_knee_R(2), P_hinge_R(2)], 'g-o', 'LineWidth', 2.5, 'MarkerFaceColor','g'); % 右小腿
    
    % 绘制弓与接触点
    P_bow_left = P_contact + R_matrix * [-L_bow/2 + x_s; 0]; P_bow_right = P_contact + R_matrix * [L_bow/2 + x_s; 0];
    plot([P_bow_left(1), P_bow_right(1)], [P_bow_left(2), P_bow_right(2)], 'Color', [0.85 0.5 0], 'LineWidth', 3);
    plot(P_hinge_L(1), P_hinge_L(2), 'ko', 'MarkerSize', 8, 'MarkerFaceColor', 'y');
    plot(P_hinge_R(1), P_hinge_R(2), 'ko', 'MarkerSize', 8, 'MarkerFaceColor', 'y');
    plot(Strings(1,:), Strings(2,:), 'ro', 'MarkerSize', 8, 'MarkerFaceColor', 'r');
    for s = 1:4, text(Strings(1,s)-0.015, Strings(2,s)-0.03, String_Names{s}, 'FontWeight', 'bold'); end
    plot(P_contact(1), P_contact(2), 'mx', 'MarkerSize', 15, 'LineWidth', 3);
    
    axis equal; xlim([-0.5, 0.5]); ylim([-0.5, 0.5]); grid on;
    
    data_str = {
        sprintf('时间: %.2f s | 音符: %s (%s弦)', t(i), notes(current_state_idx(i)).note_name, notes(current_state_idx(i)).string), ...
        sprintf('L1大腿: %5.1f RPM | %5.1f mN·m', abs(omega_L1_deg(i)/6), abs(torque_L1(i)*1000)), ...
        sprintf('L2小腿: %5.1f RPM | %5.1f mN·m', abs(omega_L2_deg(i)/6), abs(torque_L2(i)*1000)), ...
        sprintf('R1大腿: %5.1f RPM | %5.1f mN·m', abs(omega_R1_deg(i)/6), abs(torque_R1(i)*1000)), ...
        sprintf('R2小腿: %5.1f RPM | %5.1f mN·m', abs(omega_R2_deg(i)/6), abs(torque_R2(i)*1000))
    };
    text(-0.48, 0.36, data_str, 'FontSize', 9, 'BackgroundColor', 'w', 'EdgeColor', 'k', 'FontName', 'Courier');
    title('全系统平衡：4关节双曲柄狗腿动力学与压弦监测');
    xlabel('X方向 (m)'); ylabel('Y方向 (m)'); drawnow;
end

%% 8. 绘制完整的系统选型分析曲线图 (包含全部 4 个关节电机负载)
figure('Name', '全系统4电机全面选型曲线图', 'Position', [100, 50, 1200, 800]);

subplot(3,2,1);
plot(t, v_slide, 'r', 'LineWidth', 2);
title('滑块直线速度需求'); xlabel('时间 (s)'); ylabel('速度 (m/s)'); grid on;

subplot(3,2,2);
plot(t, omega_L1_deg/6, 'b', t, omega_L2_deg/6, 'b--', t, omega_R1_deg/6, 'g', t, omega_R2_deg/6, 'g--', 'LineWidth', 1.5);
title('全车4关节电机转速对比'); xlabel('时间 (s)'); ylabel('转速 (RPM)'); 
legend('L1 大腿', 'L2 小腿', 'R1 大腿', 'R2 小腿'); grid on;

subplot(3,2,3);
plot(t, torque_slide_motor, 'r', 'LineWidth', 2);
title('滑轨驱动电机瞬时扭矩'); xlabel('时间 (s)'); ylabel('扭矩 (N·m)'); grid on;

subplot(3,2,4);
plot(t, torque_L1, 'b', t, torque_L2, 'b--', t, torque_R1, 'g', t, torque_R2, 'g--', 'LineWidth', 1.5);
title('4关节电机瞬时扭矩对比'); xlabel('时间 (s)'); ylabel('扭矩 (N·m)'); 
legend('L1 大腿', 'L2 小腿', 'R1 大腿', 'R2 小腿'); grid on;

subplot(3,2,5);
plot(t, torque_slide_motor .* omega_slide_motor, 'r', 'LineWidth', 2);
title('滑轨电机机械功率'); xlabel('时间 (s)'); ylabel('功率 (W)'); grid on;

subplot(3,2,6);
plot(t, abs(torque_L1 .* omega_L1), 'b', t, abs(torque_L2 .* omega_L2), 'b--', t, abs(torque_R1 .* omega_R1), 'g', t, abs(torque_R2 .* omega_R2), 'g--', 'LineWidth', 1.5);
title('4关节电机轴向功率对比'); xlabel('时间 (s)'); ylabel('功率 (W)'); 
legend('L1 大腿', 'L2 小腿', 'R1 大腿', 'R2 小腿'); grid on;

%% 9. 最终选型峰值打印报告
fprintf(' Part1:全系统 4 电机选型数据报告\n');
fprintf('【左腿 L1 电机 (大腿)】 -> 最大转速: %5.2f RPM | 峰值扭矩: %6.2f mN·m | 峰值功率: %.2f W\n', max(abs(omega_L1_deg))/6, max(abs(torque_L1))*1000, max(abs(torque_L1.*omega_L1)));
fprintf('【左腿 L2 电机 (小腿)】 -> 最大转速: %5.2f RPM | 峰值扭矩: %6.2f mN·m | 峰值功率: %.2f W\n', max(abs(omega_L2_deg))/6, max(abs(torque_L2))*1000, max(abs(torque_L2.*omega_L2)));
fprintf('【右腿 R1 电机 (大腿)】 -> 最大转速: %5.2f RPM | 峰值扭矩: %6.2f mN·m | 峰值功率: %.2f W\n', max(abs(omega_R1_deg))/6, max(abs(torque_R1))*1000, max(abs(torque_R1.*omega_R1)));
fprintf('【右腿 R2 电机 (小腿)】 -> 最大转速: %5.2f RPM | 峰值扭矩: %6.2f mN·m | 峰值功率: %.2f W\n', max(abs(omega_R2_deg))/6, max(abs(torque_R2))*1000, max(abs(torque_R2.*omega_R2)));


%% 故障排查
[max_val, max_idx] = max(abs(torque_L1)); % 以L1为例
fprintf('\n Part2:爆表时刻数据排查报告 (第 %d 帧) \n', max_idx);
fprintf('爆表时间点: %.4f 秒\n', t(max_idx));
fprintf('此时运弓速度 v_slide: %.4f m/s\n', v_slide(max_idx));
fprintf('此时大腿角度 motor_L1_rad: %.2f 度\n', rad2deg(motor_L1_rad(max_idx)));
fprintf('此时大腿角加速度 alpha_L1: %.2f rad/s^2\n', alpha_L1(max_idx));
fprintf('--- 动力学分项拆解 ---\n');
fprintf('1. 惯性扭矩项 (I * alpha): %.2f N·m\n', I_arm1 * alpha_L1(max_idx));
fprintf('2. 重力矩项 (m*g*L*cos): %.2f N·m\n', (0.5*m_arm1 + 0.5*m_rod)*g*L1*cos(motor_L1_rad(max_idx)));
fprintf('3. 雅可比力矩项 (J_x*F_x + J_y*F_y): %.2f N·m\n', (torque_L1(max_idx) - I_arm1 * alpha_L1(max_idx) - (0.5*m_arm1 + 0.5*m_rod)*g*L1*cos(motor_L1_rad(max_idx))));

%% 过滤
% 过滤掉前 5% 的极端奇异点尖峰，提取真实的工程选型数据
cutoff_percent = 99; % 提取 99% 置信度下的最大值（即滤除前 1% 的突变尖峰）

real_torque_L1 = prctile(abs(torque_L1), cutoff_percent);
real_torque_L2 = prctile(abs(torque_L2), cutoff_percent);
real_torque_R1 = prctile(abs(torque_R1), cutoff_percent);
real_torque_R2 = prctile(abs(torque_R2), cutoff_percent);

real_power_L1 = prctile(abs(torque_L1 .* omega_L1), cutoff_percent);
real_power_L2 = prctile(abs(torque_L2 .* omega_L2), cutoff_percent);
real_power_R1 = prctile(abs(torque_R1 .* omega_R1), cutoff_percent);
real_power_R2 = prctile(abs(torque_R2 .* omega_R2), cutoff_percent);

fprintf('\n Part 3:过滤突变尖峰后：健康选型参考数据报告\n');
fprintf('【左腿 L1 大腿电机】 -> 真实最大扭矩: %6.2f N·m | 真实最大功率: %.2f W\n', real_torque_L1, real_power_L1);
fprintf('【左腿 L2 小腿电机】 -> 真实最大扭矩: %6.2f N·m | 真实最大功率: %.2f W\n', real_torque_L2, real_power_L2);
fprintf('【右腿 R1 大腿电机】 -> 真实最大扭矩: %6.2f N·m | 真实最大功率: %.2f W\n', real_torque_R1, real_power_R1);
fprintf('【右腿 R2 小腿电机】 -> 真实最大扭矩: %6.2f N·m | 真实最大功率: %.2f W\n', real_torque_R2, real_power_R2);

%% 10. 滑轨与丝杠副工程选型指标核心解算
fprintf('Part 4: 滑轨与传动系统工程选型核心指标报告\n');

m_remote_total = 0.5 * m_rod + m_calf + 0.5 * m_bow;

% 1. 几何长度指标解算
stroke_bow = max(x_slide_t) - min(x_slide_t); % 琴弓纯运弓有效行程 (m)
% 实际工程中，滑轨总长度必须包含：有效行程 + 滑块自身长度 + 双侧安全裕量(通常各留20-50mm)
L_slider_hardware = L_hold + 0.06; % 滑块总装机械宽度 (m)
safety_margin = 0.04 * 2;          % 两侧极限保护间距 (m)
L_rail_min = stroke_bow + L_slider_hardware + safety_margin;

% 2. 丝杠驱动轴向力 (Axial Load) 解算
% 滑块受到的总轴向阻力由三部分组成：推滑块加速的惯性力 + 丝杠本身导轨摩擦力 + 左右两腿反作用于滑块的X方向合力
F_legs_to_slider_x = zeros(1, num_steps);
for i = 1:num_steps
    % 提取左右腿电机在X方向对滑块的动态反作用力 (根据牛顿第三定律与雅可比力映射)
    % 这里的反作用力来源于腿部克服接触摩擦力与自身动态加速在基座产生的撕扯力
    th_L1 = motor_L1_rad(i); th_L2 = motor_L2_rad(i);
    th_R1 = motor_R1_rad(i); th_R2 = motor_R2_rad(i);
    
    % 从关节扭矩逆推基座X方向受力 (近似项：主要由接触摩擦力 F_x 传导)
    F_legs_to_slider_x(i) = (torque_L1(i)/L1)*sin(th_L1) + (torque_R1(i)/L1)*sin(th_R1);
end

% 丝杠推力 = 滑块质量*加速度 + 导轨自身摩擦(假设摩擦系数0.005) + 两腿反作用合力
mu_rail = 0.005; 
F_axial_all = m_slider * a_slide + mu_rail * (m_slider * g) + F_legs_to_slider_x;
F_axial_peak = max(abs(F_axial_all));

% 3. 滑块动态侧向倾覆力矩 (Moments) 解算
% 这是双腿构型最伤滑轨的地方：两腿高频动态下压、换弦、摩擦，会在滑块基座上产生剧烈的颠覆力矩
% 俯仰力矩 My (Pitching): 主要由两腿 Y 方向压弦力的不对称，以及动态运弓时产生的 X 方向撕扯力矩引起
My_moment_all = zeros(1, num_steps); 
for i = 1:num_steps
    % 简化力矩核算：左腿反力 * 左力臂 + 右腿反力 * 右力臂
    F_y_L_curr = -3.0 - m_remote_total * (g + a_y_calf_L(i));
    F_y_R_curr = -3.0 - m_remote_total * (g + a_y_calf_R(i));
    My_moment_all(i) = F_y_L_curr * (-L_hold/2) + F_y_R_curr * (L_hold/2); 
end
My_moment_peak = max(abs(My_moment_all));

% 4. 丝杠转速与Dn值核算
max_v_slide = max(abs(v_slide));
max_n_screw = (max_v_slide / Lead_slide) * 60; % 丝杠最高设计转速 (RPM)

% --- 打印指标报告 ---
fprintf('【1. 几何尺寸指标】\n');
fprintf('   * 纯运弓有效行程 (Stroke):       %5.2f mm\n', stroke_bow * 1000);
fprintf('   * 建议滑轨最小物理总长 (Length):  %5.2f mm (已含滑块宽度与安全机械限位)\n', L_rail_min * 1000);

fprintf('\n【2. 滚珠丝杠副选型核心参数】\n');
fprintf('   * 建议导程 (Lead):               %5.2f mm/rev (当前设定)\n', Lead_slide * 1000);
fprintf('   * 轴向峰值动态推力 (Peak Force):  %5.2f N\n', F_axial_peak);
fprintf('   * 丝杠最高运转转速 (Max Speed):  %5.2f RPM\n', max_n_screw);
fprintf('   * 建议丝杠公称直径 (Diameter):   12 mm 或 16 mm (基于转速与拉压刚度常规工程推荐)\n');

fprintf('\n【3. 直线导轨动态力矩负载 (滑轨选型核心抗偏载指标)】\n');
fprintf('   * 峰值动态颠覆力矩 My (Pitching): %5.2f N·m\n', My_moment_peak);
fprintf('   * 选型专业建议: \n');
if My_moment_peak > 5.0
    fprintf('     ⚠️警告：由于双腿间距较大且存在动态换弦冲击，单根滑轨将承受高额颠覆力矩！\n');
    fprintf('     建议采用【双导轨 + 四滑块】（平行双轨布局）构型，利用两根导轨的跨距来彻底消除该偏载，\n');
    fprintf('     否则单根滑轨极易产生高频低幅晃动，直接摧毁小提琴演奏的压弦精度与音高控制。\n');
else
    fprintf('     偏载力矩在安全范围内，可选用高刚性单导轨加长型双滑块布局。\n');
end
