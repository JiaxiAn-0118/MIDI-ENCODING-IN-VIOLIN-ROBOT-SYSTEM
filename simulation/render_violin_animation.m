function render_violin_animation(anim)
% Shared animation/video rendering for violin robot simulation scripts.

fig = figure('Name', '双闭环平行双曲柄狗腿同步演奏仿真', 'Position', [50, 80, 1100, 700]);

video_filename = anim.video_filename;
draw_step = anim.draw_step;

v = VideoWriter(video_filename, 'MPEG-4');
v.FrameRate = anim.fs / draw_step;
v.Quality = 95;
open(v);

fprintf('正在生成并录制仿真视频，请稍候...\n');

for i = 1:draw_step:length(anim.t)
    % Clear previous frame and reset hold state.
    clf(fig);
    ax = axes('Parent', fig);
    hold(ax, 'on');

    x_s = anim.x_slide_t(i);
    th_b = anim.theta_bow_t(i);
    P_contact = anim.current_string_t(:, i);
    R_matrix = [cos(th_b), -sin(th_b); sin(th_b), cos(th_b)];

    % 1. Rail and slider
    plot(ax, [-0.6, 0.6], [anim.H_slide, anim.H_slide], 'k--', 'LineWidth', 1.5);
    slider_w = anim.L_hold + 0.06;
    rectangle(ax, 'Position', [x_s - slider_w/2, anim.H_slide, slider_w, 0.02], 'FaceColor', [0.7 0.7 0.7]);

    % 2. Left leg
    P_base_L = [x_s - anim.L_hold/2; anim.H_slide];
    P_knee_L = anim.P_knee_L_all(:, i);
    P_hinge_L = anim.P_hinge_L_all(:, i);
    plot(ax, [P_base_L(1), P_knee_L(1)], [P_base_L(2), P_knee_L(2)], 'b-o', 'LineWidth', 3, 'MarkerFaceColor', 'b');
    P_crank_end_L = P_base_L + [anim.r_crank*cos(anim.motor_L2_rad(i)); anim.r_crank*sin(anim.motor_L2_rad(i))];
    plot(ax, [P_base_L(1), P_crank_end_L(1)], [P_base_L(2), P_crank_end_L(2)], 'r-o', 'LineWidth', 4, 'MarkerFaceColor', 'r');
    P_knee_jig_L = P_knee_L + [anim.r_crank*cos(anim.motor_L2_rad(i)); anim.r_crank*sin(anim.motor_L2_rad(i))];
    plot(ax, [P_crank_end_L(1), P_knee_jig_L(1)], [P_crank_end_L(2), P_knee_jig_L(2)], 'm--', 'LineWidth', 1.5);
    plot(ax, [P_knee_L(1), P_hinge_L(1)], [P_knee_L(2), P_hinge_L(2)], 'g-o', 'LineWidth', 2.5, 'MarkerFaceColor', 'g');

    % 3. Right leg
    P_base_R = [x_s + anim.L_hold/2; anim.H_slide];
    P_knee_R = anim.P_knee_R_all(:, i);
    P_hinge_R = anim.P_hinge_R_all(:, i);
    plot(ax, [P_base_R(1), P_knee_R(1)], [P_base_R(2), P_knee_R(2)], 'b-o', 'LineWidth', 3, 'MarkerFaceColor', 'b');
    P_crank_end_R = P_base_R + [anim.r_crank*cos(anim.motor_R2_rad(i)); anim.r_crank*sin(anim.motor_R2_rad(i))];
    plot(ax, [P_base_R(1), P_crank_end_R(1)], [P_base_R(2), P_crank_end_R(2)], 'r-o', 'LineWidth', 4, 'MarkerFaceColor', 'r');
    P_knee_jig_R = P_knee_R + [anim.r_crank*cos(anim.motor_R2_rad(i)); anim.r_crank*sin(anim.motor_R2_rad(i))];
    plot(ax, [P_crank_end_R(1), P_knee_jig_R(1)], [P_crank_end_R(2), P_knee_jig_R(2)], 'm--', 'LineWidth', 1.5);
    plot(ax, [P_knee_R(1), P_hinge_R(1)], [P_knee_R(2), P_hinge_R(2)], 'g-o', 'LineWidth', 2.5, 'MarkerFaceColor', 'g');

    % 4. Bow and strings
    P_bow_left = P_contact + R_matrix * [-anim.L_bow/2 + x_s; 0];
    P_bow_right = P_contact + R_matrix * [anim.L_bow/2 + x_s; 0];
    plot(ax, [P_bow_left(1), P_bow_right(1)], [P_bow_left(2), P_bow_right(2)], 'Color', [0.85 0.5 0], 'LineWidth', 3);

    plot(ax, P_hinge_L(1), P_hinge_L(2), 'ko', 'MarkerSize', 8, 'MarkerFaceColor', 'y');
    plot(ax, P_hinge_R(1), P_hinge_R(2), 'ko', 'MarkerSize', 8, 'MarkerFaceColor', 'y');
    plot(ax, anim.Strings(1,:), anim.Strings(2,:), 'ro', 'MarkerSize', 8, 'MarkerFaceColor', 'r');

    for s = 1:4
        text(ax, anim.Strings(1,s)-0.015, anim.Strings(2,s)-0.03, anim.String_Names{s}, 'FontWeight', 'bold');
    end
    plot(ax, P_contact(1), P_contact(2), 'mx', 'MarkerSize', 15, 'LineWidth', 3);

    axis(ax, 'equal');
    xlim(ax, [-0.5, 0.5]);
    ylim(ax, [-0.5, 0.5]);
    grid(ax, 'on');

    idx = anim.current_state_idx(i);
    data_str = {
        sprintf('时间: %.2f s | 音符: %s (%s弦)', anim.t(i), anim.notes(idx).note_name, anim.notes(idx).string), ...
        sprintf('L1大腿: %5.1f RPM | %5.1f mN·m', abs(anim.omega_L1_deg(i)/6), abs(anim.torque_L1(i)*1000)), ...
        sprintf('L2小腿: %5.1f RPM | %5.1f mN·m', abs(anim.omega_L2_deg(i)/6), abs(anim.torque_L2(i)*1000)), ...
        sprintf('R1大腿: %5.1f RPM | %5.1f mN·m', abs(anim.omega_R1_deg(i)/6), abs(anim.torque_R1(i)*1000)), ...
        sprintf('R2小腿: %5.1f RPM | %5.1f mN·m', abs(anim.omega_R2_deg(i)/6), abs(anim.torque_R2(i)*1000))
    };

    text(ax, -0.48, 0.36, data_str, 'FontSize', 9, 'BackgroundColor', 'w', 'EdgeColor', 'k', 'FontName', 'Courier');
    title(ax, '全系统平衡：4关节双曲柄狗腿动力学与压弦监测');
    xlabel(ax, 'X方向 (m)');
    ylabel(ax, 'Y方向 (m)');

    drawnow limitrate;
    frame = getframe(fig);
    writeVideo(v, frame);

    hold(ax, 'off');
end

close(v);
fprintf('视频已成功保存！\n');

end