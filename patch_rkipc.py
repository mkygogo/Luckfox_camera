import re
import sys


def split_lines_with_endings(text):
    return text.splitlines(keepends=True)


def find_section_bounds(lines, section):
    section_header = f"[{section}]"
    start_index = None

    for index, line in enumerate(lines):
        if line.strip() == section_header:
            start_index = index
            break

    if start_index is None:
        raise ValueError(f"未找到配置节: [{section}]")

    end_index = len(lines)
    for index in range(start_index + 1, len(lines)):
        if lines[index].lstrip().startswith("["):
            end_index = index
            break

    return start_index, end_index


def detect_newline(lines):
    for line in lines:
        if line.endswith("\r\n"):
            return "\r\n"
        if line.endswith("\n"):
            return "\n"
    return "\n"


def set_section_value(config, section, key, value):
    lines = split_lines_with_endings(config)
    start_index, end_index = find_section_bounds(lines, section)
    newline = detect_newline(lines)
    key_prefix = re.compile(rf"^(\s*{re.escape(key)}\s*=\s*)")

    for index in range(start_index + 1, end_index):
        match = key_prefix.match(lines[index])
        if match:
            suffix = newline if lines[index].endswith(("\n", "\r\n")) else ""
            lines[index] = f"{match.group(1)}{value}{suffix}"
            return "".join(lines)

    insert_at = end_index
    lines.insert(insert_at, f"{key} = {value}{newline}")
    return "".join(lines)


def get_section_value(config, section, key):
    lines = split_lines_with_endings(config)
    start_index, end_index = find_section_bounds(lines, section)
    key_prefix = re.compile(rf"^\s*{re.escape(key)}\s*=\s*(.*?)\s*$")

    for index in range(start_index + 1, end_index):
        match = key_prefix.match(lines[index].rstrip("\r\n"))
        if match:
            return match.group(1)

    return None


def apply_video_profile(config, section, width, height, frame_rate=None, rc_mode=None, gop=None):
    config = set_section_value(config, section, "max_width", width)
    config = set_section_value(config, section, "max_height", height)
    config = set_section_value(config, section, "width", width)
    config = set_section_value(config, section, "height", height)

    if frame_rate is not None:
        config = set_section_value(config, section, "src_frame_rate_num", frame_rate)
        config = set_section_value(config, section, "dst_frame_rate_num", frame_rate)

    if rc_mode is not None:
        config = set_section_value(config, section, "rc_mode", rc_mode)

    if gop is not None:
        config = set_section_value(config, section, "gop", gop)

    return config


def set_encoder_flags(config, enable_venc_0=True, enable_venc_1=True, enable_venc_2=False):
    config = set_section_value(config, "video.source", "enable_venc_0", "1" if enable_venc_0 else "0")
    config = set_section_value(config, "video.source", "enable_venc_1", "1" if enable_venc_1 else "0")
    config = set_section_value(config, "video.source", "enable_venc_2", "1" if enable_venc_2 else "0")
    config = set_section_value(config, "video.source", "enable_rtsp", "1")
    return config

def patch_rkipc_ini(mode="native", resolution="720"):
    print(f"\n🛠️ 正在注入配置: [模式={mode}] [分辨率={resolution}P]...")
    ini_path = "/userdata/rkipc.ini"
    
    try:
        with open(ini_path, "r") as f:
            config = f.read()

        # 1. 动态注入分辨率
        if resolution == "1080":
            main_width, main_height = "1920", "1080"
        else:
            main_width, main_height = "1280", "720"

        config = apply_video_profile(
            config,
            "video.0",
            main_width,
            main_height,
            frame_rate="15",
            rc_mode="VBR",
            gop="15",
        )
        config = apply_video_profile(
            config,
            "video.1",
            main_width,
            main_height,
            frame_rate="15",
            rc_mode="VBR",
            gop="15",
        )
        config = apply_video_profile(config, "video.2", "960", "540")
        config = set_encoder_flags(config, enable_venc_0=True, enable_venc_1=True, enable_venc_2=False)

        def apply_audio_profile(
            enable_audio,
            enable_storage,
            record_audio=None,
            sample_rate="8000",
            channels="1",
            frame_size="1152",
            bit_rate="16000",
        ):
            nonlocal config
            config = set_section_value(config, "audio.0", "enable", "1" if enable_audio else "0")
            config = set_section_value(config, "audio.0", "enable_vqe", "0")
            config = set_section_value(config, "audio.0", "encode_type", "G711A")
            config = set_section_value(config, "audio.0", "sample_rate", sample_rate)
            config = set_section_value(config, "audio.0", "channels", channels)
            config = set_section_value(config, "audio.0", "bit_rate", bit_rate)
            config = set_section_value(config, "audio.0", "frame_size", frame_size)
            config = set_section_value(config, "storage.0", "enable", "1" if enable_storage else "0")
            if record_audio is not None:
                config = set_section_value(config, "storage.0", "record_audio", "1" if record_audio else "0")

        # 3. 核心：按场景切换底层音频/存储策略
        if mode == "native":
            apply_audio_profile(enable_audio=True, enable_storage=True, record_audio=True)
            config = set_section_value(config, "storage.0", "file_duration", "30")
        elif mode == "live":
            apply_audio_profile(
                enable_audio=True,
                enable_storage=False,
                record_audio=False,
                sample_rate="8000",
                channels="1",
                frame_size="1152",
                bit_rate="16000",
            )
        else:
            apply_audio_profile(enable_audio=False, enable_storage=False, record_audio=False)

        with open(ini_path, "w") as f:
            f.write(config)

        print(
            "🔍 生效配置: "
            f"audio.enable={get_section_value(config, 'audio.0', 'enable')}, "
            f"audio.encode_type={get_section_value(config, 'audio.0', 'encode_type')}, "
            f"audio.sample_rate={get_section_value(config, 'audio.0', 'sample_rate')}, "
            f"audio.channels={get_section_value(config, 'audio.0', 'channels')}, "
            f"storage.enable={get_section_value(config, 'storage.0', 'enable')}, "
            f"storage.record_audio={get_section_value(config, 'storage.0', 'record_audio')}, "
            f"venc0={get_section_value(config, 'video.source', 'enable_venc_0')}, "
            f"venc1={get_section_value(config, 'video.source', 'enable_venc_1')}, "
            f"video.0={get_section_value(config, 'video.0', 'width')}x{get_section_value(config, 'video.0', 'height')}@{get_section_value(config, 'video.0', 'dst_frame_rate_num')}, "
            f"video.1={get_section_value(config, 'video.1', 'width')}x{get_section_value(config, 'video.1', 'height')}@{get_section_value(config, 'video.1', 'dst_frame_rate_num')}"
        )
            
        print("✅ 完美！系统底层已重构完毕。")
    except Exception as e:
        print(f"⚠️ 配置文件注入失败: {e}")

if __name__ == "__main__":
    work_mode = sys.argv[1] if len(sys.argv) > 1 else "native"
    target_res = sys.argv[2] if len(sys.argv) > 2 else "720"
    
    if work_mode not in ["native", "ffmpeg", "live"]:
        work_mode = "native"
    if target_res not in ["720", "1080"]:
        target_res = "720"
        
    patch_rkipc_ini(work_mode, target_res)