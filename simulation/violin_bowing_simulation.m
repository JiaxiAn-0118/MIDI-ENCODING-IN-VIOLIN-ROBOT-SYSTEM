function violin_bowing_simulation()
    %% 1. 机械结构尺寸参数初始化 (可根据需要调整以进行选型)
    L1 = 0.15;       % 连杆1长度 (m)
    L2 = 0.18;       % 连杆2长度 (m)
    W_slider = 0.08; % 滑块上两铰链点的间距 (m)
    W_bow = 0.12;    % 琴弓上两铰链点的间距 (m)
    
    % 导轨高度（假设固定在基座上方 Y = 0.4m 处）
    Y_rail = 0.40; 
    
    %% 2. 定义期望的琴弓运动轨迹 (时间序列)
    t = linspace(0, 4, 100); % 4秒钟，100个采样点
    
    % 期望的琴弓中心轨迹 (X, Y) 和倾斜角 (Phi, 弧度)
    % 模拟运弓：在拉弓的同时，角度发生微调（比如从 -5度 到 5度）
    x_b_traj = 0.1 * sin(2*pi*0.25*t);          % 琴弓X向左右平移
    y_b_traj = 0.15 + 0.02 * cos(2*pi*0.25*t);   % 琴弓Y向高度
    phi_traj = deg2rad(5) * sin(2*pi*0.25*t);    % 琴弓倾角
    
    %% 3. 循环计算逆运动学并存储结果
    N = length(t);
    xs_res = zeros(1, N);
    theta_L_res = zeros(1, N);
    theta_R_res = zeros(1, N);
    
    % 创建动画窗口
    figure('Name', '小提琴运弓机构运动学模拟', 'Position', [200, 200, 800, 500]);
    
    for i = 1:N
        % 当前帧的目标位姿
        xb = x_b_traj(i);
        yb = y_b_traj(i);
        phi = phi_traj(i);
        
        % (1) 策略：让滑块的水平位置跟随琴弓中心
        xs = xb; 
        xs_res(i) = xs;
        
        % 滑块上左右两关节的绝对坐标
        Base_L = [xs - W_slider/2, Y_rail];
        Base_R = [xs + W_slider/2, Y_rail];
        
        % (2) 计算琴弓上左右两铰接点的绝对坐标
        Target_L = [xb - (W_bow/2)*cos(phi), yb - (W_bow/2)*sin(phi)];
        Target_R = [xb + (W_bow/2)*cos(phi), yb + (W_bow/2)*sin(phi)];
        
        % (3) 调用2R逆运动学子函数求电机角度
        % 注意：根据你草图的折叠方向，左侧取肘节向左(Elbow Left/Up)，右侧对称
        th1L = solve_2R_IK(Base_L, Target_L, L1, L2, 'left');
        th1R = solve_2R_IK(Base_R, Target_R, L1, L2, 'right');
        
        if isnan(th1L) || isnan(th1R)
            error('当前机械尺寸下，轨迹超出工作空间！请检查尺寸设计。');
        end
        
        theta_L_res(i) = th1L;
        theta_R_res(i) = th1R;
        
        %% 4. 实时绘制机构图形
        clf; hold on; grid on; axis equal;
        xlim([-0.4, 0.4]); ylim([0, 0.5]);
        xlabel('X 轴 (m)'); ylabel('Y 轴 (m)');
        title(['运弓模拟中... 当前时间: ', num2str(t(i), '%.2f'), 's']);
        
        % 绘制导轨
        plot([-0.4, 0.4], [Y_rail, Y_rail], 'k--', 'LineWidth', 1.5);
        % 绘制滑块
        plot([Base_L(1), Base_R(1)], [Y_rail, Y_rail], 'ks-', 'LineWidth', 4, 'MarkerFaceColor', 'k');
        
        % 计算左连杆中间关节坐标
        Joint_L = Base_L + [L1*cos(th1L), L1*sin(th1L)];
        % 绘制左连杆
        plot([Base_L(1), Joint_L(1), Target_L(1)], [Base_L(2), Joint_L(2), Target_L(2)], 'b-o', 'LineWidth', 2);
        
        % 计算右连杆中间关节坐标
        Joint_R = Base_R + [L1*cos(th1R), L1*sin(th1R)];
        % 绘制右连杆
        plot([Base_R(1), Joint_R(1), Target_R(1)], [Base_R(2), Joint_R(2), Target_R(2)], 'b-o', 'LineWidth', 2);
        
        % 绘制琴弓
        plot([Target_L(1), Target_R(1)], [Target_L(2), Target_R(2)], 'm-', 'LineWidth', 3);
        % 延伸绘制整把弓的效果
        Bow_Ext_L = Target_L + 0.15 * [cos(phi+pi), sin(phi+pi)];
        Bow_Ext_R = Target_R + 0.15 * [cos(phi), sin(phi)];
        plot([Bow_Ext_L(1), Bow_Ext_R(1)], [Bow_Ext_L(2), Bow_Ext_R(2)], 'Color', [0.8 0.5 0], 'LineWidth', 2);
        
        pause(0.04); % 控制动画刷新频率
    end
    
    %% 5. 绘制电机曲线（选型参考数据）
    figure('Name', '驱动动特性数据');
    subplot(3,1,1); plot(t, xs_res, 'r', 'LineWidth', 1.5); ylabel('滑块位移 (m)'); grid on;
    title('驱动器目标运动曲线（选型依据）');
    subplot(3,1,2); plot(t, rad2deg(theta_L_res), 'b', 'LineWidth', 1.5); ylabel('左电机角度 (deg)'); grid on;
    subplot(3,1,3); plot(t, rad2deg(theta_R_res), 'g', 'LineWidth', 1.5); ylabel('右电机角度 (deg)'); xlabel('时间 (s)'); grid on;
end

%% 2R 机器人逆运动学求解子函数
function theta1 = solve_2R_IK(Base, Target, L1, L2, side)
    % 计算基点到目标点的相对距离
    dx = Target(1) - Base(1);
    dy = Target(2) - Base(2);
    distSq = dx^2 + dy^2;
    dist = sqrt(distSq);
    
    % 检查是否超出臂展极限
    if dist > (L1 + L2) || dist < abs(L1 - L2)
        theta1 = NaN;
        return;
    end
    
    % 基础方位角
    alpha = atan2(dy, dx);
    
    % 利用余弦定理求内部角
    cos_beta = (L1^2 + distSq - L2^2) / (2 * L1 * dist);
    beta = acos(max(-1, min(1, cos_beta))); % 防止浮点数误差溢出[-1,1]
    
    % 根据机构形态（左侧通常关节向外凸，右侧向外凸）选择正负分支
    if strcmp(side, 'left')
        theta1 = alpha + beta; % 对应左侧弯曲形态
    else
        theta1 = alpha - beta; % 对应右侧弯曲形态
    end
end