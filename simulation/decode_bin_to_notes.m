function notes = decode_bin_to_notes(binPath)
%DECODE_BIN_TO_NOTES  解析 Binary Violin Event Protocol V1 数据包。
%   notes = decode_bin_to_notes(binPath)
%
%   输出结构与 JSON 版本兼容，方便后续直接复用现有仿真逻辑。
%   每个音符包含：start, end, duration, pitch, note_name, string,
%   finger, position, bow_direction, bow_speed, velocity, bow_force,
%   is_legato, needs_reset_bow, checksum_ok

    if nargin < 1 || isempty(binPath)
        binPath = fullfile(pwd, 'scores', '梁祝', 'liangzhu_lower.bin');
    end

    if ~exist(binPath, 'file')
        error('找不到 BIN 文件：%s', binPath);
    end

    fid = fopen(binPath, 'rb');
    if fid < 0
        error('无法打开 BIN 文件：%s', binPath);
    end

    raw = fread(fid, inf, 'uint8');
    fclose(fid);

    if isempty(raw)
        error('BIN 文件为空：%s', binPath);
    end

    if mod(numel(raw), 12) ~= 0
        error('BIN 文件长度不是 12 字节整数倍，当前长度为 %d', numel(raw));
    end

    packetCount = numel(raw) / 12;
    packets = reshape(raw, 12, packetCount).';

    header = packets(:, 1);
    if any(header ~= hex2dec('A5'))
        warning('检测到部分数据包头不是 0xA5，文件可能不是标准 Binary Violin Event Protocol V1 格式。');
    end

    tick = double(packets(:, 2)) + double(packets(:, 3)) * 256;
    pitch = double(packets(:, 4));
    durationTick = double(packets(:, 5)) + double(packets(:, 6)) * 256;
    stringFinger = packets(:, 7);
    bowByte = packets(:, 8);
    force = double(packets(:, 9));
    flags = packets(:, 10);
    reserved = packets(:, 11);
    checksum = packets(:, 12);

    checksumCalculated = mod(sum(packets(:, 1:11), 2), 256);
    checksumOK = checksum == checksumCalculated;
    if any(~checksumOK)
        warning('发现 %d 个数据包校验和不通过，建议检查串口传输或编码过程。', sum(~checksumOK));
    end

    stringNames = {'G', 'D', 'A', 'E'};
    notes = struct(...
        'start', {}, ...
        'end', {}, ...
        'duration', {}, ...
        'pitch', {}, ...
        'note_name', {}, ...
        'string', {}, ...
        'string_id', {}, ...
        'finger', {}, ...
        'position', {}, ...
        'bow_direction', {}, ...
        'bow_speed', {}, ...
        'velocity', {}, ...
        'bow_force', {}, ...
        'is_legato', {}, ...
        'needs_reset_bow', {}, ...
        'checksum_ok', {}, ...
        'reserved', {}, ...
        'direction', {});

    for i = 1:packetCount
        stringId = bitshift(stringFinger(i), -6);
        finger = bitand(bitshift(stringFinger(i), -3), 7);
        position = bitand(stringFinger(i), 7);

        if stringId >= 0 && stringId <= 3
            stringName = stringNames{stringId + 1};
        else
            stringName = 'Unknown';
        end

        bowDirectionBit = bitshift(bowByte(i), -7);
        bowDirection = 'down';
        if bowDirectionBit == 1
            bowDirection = 'up';
        end

        bowSpeed = bitand(bowByte(i), 127);
        isLegato = bitand(flags(i), uint8(4)) ~= 0;
        needsResetBow = bitand(flags(i), uint8(8)) ~= 0;

        note.start = double(tick(i)) * 0.01;
        note.end = note.start + double(durationTick(i)) * 0.01;
        note.duration = double(durationTick(i)) * 0.01;
        note.pitch = pitch(i);
        note.note_name = midi_to_note_name(pitch(i));
        note.string = stringName;
        note.string_id = double(stringId);
        note.finger = double(finger);
        note.position = double(position);
        note.bow_direction = bowDirection;
        note.bow_speed = double(bowSpeed);
        note.velocity = double(force(i));
        note.bow_force = double(force(i));
        note.is_legato = logical(isLegato);
        note.needs_reset_bow = logical(needsResetBow);
        note.checksum_ok = logical(checksumOK(i));
        note.reserved = double(reserved(i));
        if strcmp(note.bow_direction, 'down')
            note.direction = 1;
        else
            note.direction = -1;
        end

        notes(end + 1) = note;
    end

    if isempty(notes)
        error('解析后没有生成任何有效音符。');
    end
end

function noteName = midi_to_note_name(pitch)
    noteNames = {'C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B'};
    octave = floor(double(pitch) / 12) - 1;
    noteName = sprintf('%s%d', noteNames{mod(double(pitch), 12) + 1}, octave);
end
