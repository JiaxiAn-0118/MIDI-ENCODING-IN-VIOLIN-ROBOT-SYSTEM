% simulate_legato_from_json.m
% Read violin_midi_json output JSON and simulate bow direction/speed/force
% Usage:
%   - Edit `json_path` to point to the JSON produced by violin_midi_json
%   - Run in MATLAB: simulate_legato_from_json

clear; close all; clc;

% Path to JSON output from violin_midi_json (edit as needed)
json_path = '/Users/anjiaxi/Desktop/Fudan/Projects/Denghui_violin/Violin_GitHub/MIDI-ENCODING-IN-VIOLIN-ROBOT-SYSTEM/scores/梁祝/liangzhu_lower_from_midi.json';

if ~exist(json_path, 'file')
    fprintf('JSON not found at %s\n', json_path);
    return;
end

raw = fileread(json_path);
data = jsondecode(raw);
notes = data.notes;

if isempty(notes)
    error('No notes found in JSON');
end

% Build events table: start, duration, requested_dir, bow_speed, bow_force, legato
n = numel(notes);
events = zeros(n,6);

% initial bow direction: 1 = down, 0 = up (match Python default)
current_direction = 1;
prev_legato = false;

for i = 1:n
    note = notes(i);
    start_t = note.start;
    dur = note.duration;
    legato = false;
    if isfield(note, 'is_legato')
        legato = logical(note.is_legato);
    end
    % simple mapping: velocity -> bow_speed (1..10), bow_force (1..10)
    vel = 64;
    if isfield(note, 'velocity')
        vel = note.velocity;
    end
    bow_speed = max(1, min(10, round(1 + (vel / 127) * 9)));
    bow_force = max(1, min(10, round(1 + (vel / 127) * 9)));

    if legato && prev_legato
        use_dir = current_direction; % continue
    else
        % start new stroke: flip direction
        current_direction = 1 - current_direction; % flip 1<->0
        use_dir = current_direction;
    end

    events(i,:) = [start_t, dur, use_dir, bow_speed, bow_force, legato];
    prev_legato = legato;
end

% Build time axis
total_duration = data.meta.tempo; % placeholder
% better: compute from last note end
total_duration = notes(end).end;
fs = 200; dt = 1/fs; t = 0:dt:total_duration;

dir_sig = nan(size(t)); speed_sig = zeros(size(t)); force_sig = zeros(size(t));

for i = 1:size(events,1)
    s = events(i,1); d = events(i,2);
    dir = events(i,3);
    spd = events(i,4);
    frc = events(i,5);
    idx = (t >= s) & (t < s + d);
    dir_sig(idx) = dir;
    speed_sig(idx) = spd;
    force_sig(idx) = frc;
end

% hold previous values for gaps
last_dir = 0;
for k=1:length(t)
    if isnan(dir_sig(k))
        dir_sig(k) = last_dir;
    else
        last_dir = dir_sig(k);
    end
end

% Plot
figure('Position',[100 100 900 600]);
subplot(3,1,1);
stairs(t, dir_sig, 'LineWidth',2);
ylim([-0.2 1.2]); yticks([0 1]); yticklabels({'up','down'});
title('Bow Direction (0=up, 1=down)'); xlabel('Time (s)');

subplot(3,1,2);
plot(t, speed_sig, '-','LineWidth',1.5); ylabel('Bow Speed'); xlabel('Time (s)'); title('Bow Speed');

subplot(3,1,3);
plot(t, force_sig, '-','LineWidth',1.5); ylabel('Bow Force'); xlabel('Time (s)'); title('Bow Force');

sgtitle(sprintf('Simulation from %s', json_path));

% Optional: export events to workspace
assignin('base', 'sim_events', events);
assignin('base', 'sim_time', t);
assignin('base', 'sim_dir', dir_sig);
assignin('base', 'sim_speed', speed_sig);
assignin('base', 'sim_force', force_sig);

fprintf('Simulation finished. Events exported to workspace as ''sim_events''.
');
