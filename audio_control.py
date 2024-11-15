from flask import Flask, request, jsonify
import subprocess
import re
import os
import logging

from gevent import pywsgi

app = Flask(__name__)


COMPOSE_FILE = "/mnt/audio/NorthAudio/space/run_dfn_n_vol.yaml"


def check_device_exists():
    """檢查是否存在 "TEAC Corp. US-2x2HR" 裝置"""
    try:
        result = subprocess.run(["lsusb"], capture_output=True, text=True, check=True)
        return "TEAC Corp. US-2x2HR" in result.stdout
    except subprocess.CalledProcessError:
        return False


def query_default_audio_devices():
    """檢查預設 source 與 sink 是否都包含 "TASCAM_US-2x2HR" 字串"""

    default_source = None
    default_sink = None

    try:
        result = subprocess.run(
            ["pactl", "info"], capture_output=True, text=True, check=True
        )
        output = result.stdout
        default_source = (
            re.search(r"Default Source:\s*(.+)", output).group(1)
            if re.search(r"Default Source:\s*(.+)", output)
            else None
        )
        default_sink = (
            re.search(r"Default Sink:\s*(.+)", output).group(1)
            if re.search(r"Default Sink:\s*(.+)", output)
            else None
        )

        return default_source, default_sink
    except (
        subprocess.CalledProcessError,
        AttributeError,
    ):
        return default_source, default_sink


def set_volume_levels(device, kind: str):
    if kind == "source":
        commmand = "set-source-volume"
    elif kind == "sink":
        commmand = "set-sink-volume"
    else:
        return False

    try:
        subprocess.run(
            ["pactl", commmand, device, "100"],
            capture_output=True,
            text=True,
            check=True,
        )
        return True

    except subprocess.CalledProcessError as e:
        print(e.stderr)
        return False


def check_audio_vol():
    try:
        status = subprocess.run(
            [
                "docker",
                "ps",
                "-a",
                "--filter",
                "name=audio_api",
                "--format",
                "{{.Status}}",
            ],
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()

        if "Up" not in status:
            return False
        else:
            return True

    except subprocess.CalledProcessError:
        return False


def check_audio_enh():
    try:
        audio_enh_status = subprocess.run(
            [
                "docker",
                "ps",
                "-a",
                "--filter",
                "name=audio_enh",
                "--format",
                "{{.Status}}",
            ],
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()

        if "Up" not in audio_enh_status:
            return False, None

        audio_enh_command = subprocess.run(
            [
                "docker",
                "ps",
                "-a",
                "--filter",
                "name=audio_enh",
                "--format",
                "{{.Command}}",
            ],
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
        match = re.search(r"bash run_dfn.sh (\d+)", audio_enh_command)
        if match:
            parameter = int(match.group(1))
            return True, parameter
        else:
            raise ValueError

    except subprocess.CalledProcessError:
        return False, None


@app.route("/audio_status", methods=["GET"])
def get_audio_status():
    status = {
        "device": False,
        "source": False,
        "sink": False,
        "audio_vol": False,
        "audio_enh": False,
        "limit": None,
    }

    pre_flag = True
    if check_device_exists():
        status["device"] = True
        default_source, default_sink = query_default_audio_devices()
        if default_source is not None:
            if set_volume_levels(default_source, "source"):
                status["source"] = True
            else:
                pre_flag = False
        else:
            pre_flag = False

        if default_sink is not None:
            if set_volume_levels(default_sink, "sink"):
                status["sink"] = False
            else:
                pre_flag = False
        else:
            pre_flag = False
    else:
        pre_flag = False

    if pre_flag:
        audio_vol_status = check_audio_vol()
        if audio_vol_status:
            status["audio_vol"] = True

        audio_enh_status, limit = check_audio_enh()
        if audio_enh_status:
            status["audio_enh"] = True
            status["limit"] = limit

    return jsonify(status)


# @app.route("/restart", methods=["POST"])
# def restart_docker_compose():
#     if not check_device_exists():
#         return jsonify({"error": "TEAC Corp. US-2x2HR device not found"}), 400

#     if not check_default_audio_devices():
#         return jsonify({"error": "Default audio devices are not set correctly"}), 400

#     if not check_volume_levels():
#         return jsonify({"error": "Volume levels are not at 100%"}), 400

#     limit = request.json.get("limit")
#     compose_file_api = request.json.get("compose_file")

#     if not limit:
#         return jsonify({"error": "--limit parameter is required"}), 400

#     if compose_file_api:  # 如果 API 請求中提供了 compose 檔案路徑，則覆蓋預設值
#         compose_file = compose_file_api

#     if not compose_file or not os.path.exists(compose_file):
#         return jsonify({"error": "Compose file not found"}), 400

#     try:
#         # 停止 docker compose
#         subprocess.run(
#             ["docker", "compose", "-f", compose_file, "down"],
#             check=True,
#             capture_output=True,
#         )

#         # 啟動 docker compose with new limit
#         subprocess.run(
#             [
#                 "LIMIT=" + str(limit),
#                 "docker",
#                 "compose",
#                 "-f",
#                 compose_file,
#                 "up",
#                 "-d",
#             ],
#             check=True,
#             capture_output=True,
#         )

#         return (
#             jsonify(
#                 {
#                     "message": f"Docker Compose restarted with LIMIT={limit} and file={compose_file}"
#                 }
#             ),
#             200,
#         )

#     except subprocess.CalledProcessError as e:
#         return (
#             jsonify(
#                 {
#                     "error": f"Error restarting Docker Compose: {e.stderr.decode()}",
#                     "returncode": e.returncode,
#                 }
#             ),
#             500,
#         )

#     except Exception as e:  # 捕捉其他潛在的錯誤，例如檔案不存在
#         return jsonify({"error": f"An unexpected error occurred: {str(e)}"}), 500


if __name__ == "__main__":
    server = pywsgi.WSGIServer(("0.0.0.0", 9527), app)
    server.serve_forever()

    # Test
    # print(f"Detection of Audio Device: {check_device_exists()}")

    # default_source, default_sink = query_default_audio_devices()
    # if default_source is not None:
    #     set_volume_levels(default_source)
    #     print("Source Volume Level: 100")
    # if default_sink is not None:
    #     set_volume_levels(default_sink)
    #     print("Sink Volume Level: 100")

    # audio_vol_status = check_audio_vol()
    # if audio_vol_status:
    #     print("audio_vol is running")

    # audio_enh_status, limit = check_audio_enh()
    # if audio_enh_status:
    #     print(f"audio_enh is running with LIMIT={limit}")

    # if audio_vol_status or audio_enh_status:
    #     subprocess.run(
    #         ["docker", "compose", "-f", COMPOSE_FILE, "down"],
    #         check=True,
    #         capture_output=True,
    #     )

    # limit = 32
    # subprocess.run(
    #     [
    #         "docker",
    #         "compose",
    #         "-f",
    #         COMPOSE_FILE,
    #         "up",
    #         "-d",
    #     ],
    #     check=True,
    #     capture_output=True,
    #     env={**os.environ, "LIMIT": str(limit)},
    # )

    # audio_vol_status = check_audio_vol()
    # if audio_vol_status:
    #     print("audio_vol is running")

    # audio_enh_status, limit = check_audio_enh()
    # if audio_enh_status:
    #     print(f"audio_enh is running with LIMIT={limit}")
