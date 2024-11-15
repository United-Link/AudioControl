# from flask import Flask, request, jsonify
import subprocess
import re
import os

# from gevent import pywsgi

# app = Flask(__name__)


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

    default_sink = None
    default_source = None

    try:
        result = subprocess.run(
            ["pactl", "info"], capture_output=True, text=True, check=True
        )
        output = result.stdout
        default_sink = (
            re.search(r"Default Sink:\s*(.+)", output).group(1)
            if re.search(r"Default Sink:\s*(.+)", output)
            else None
        )
        default_source = (
            re.search(r"Default Source:\s*(.+)", output).group(1)
            if re.search(r"Default Source:\s*(.+)", output)
            else None
        )

        return default_source, default_sink
    except (
        subprocess.CalledProcessError,
        AttributeError,
    ):  # 處理 pactl 錯誤或 regex 找不到的情況
        return default_source, default_sink


def set_volume_levels(device):
    try:
        subprocess.run(
            ["pactl", "set-sink-volume", device, "100"],
            capture_output=True,
            text=True,
            check=True,
        )
        return True

    except (
        subprocess.CalledProcessError,
        AttributeError,
        ValueError,
    ):  # 處理錯誤或找不到數值
        return False


def check_audio_api():
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

        # 如果 audio_enh 正在運行，提取 COMMAND 參數
        if "Up" in audio_enh_status:
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

        return True, None  # audio_enh 沒有運行或沒有找到參數

    except subprocess.CalledProcessError:
        return False, None


# @app.route("/check_status", methods=["POST"])
def check_status() -> tuple:
    status = {}

    status["device_exists"] = False
    if check_device_exists():
        status["device_exists"] = True

        # return jsonify({"error": "TEAC Corp. US-2x2HR device not found"}), 400

    status["default_device"] = "System"
    if check_default_audio_devices():
        status["default_device"] = "TASCAM_US-2x2HR"
    #     status["default_device"] = False
    #     return jsonify({"error": "Default audio devices are not set correctly"}), 400
    # else:
    #     s

    status["volume_100%"] = False
    if check_volume_levels():
        status["volume_100%"] = True

    containers_running, parameter = check_containers()

    if not containers_running:
        return jsonify({"error": "Containers are not running"}), 400

    limit = request.json.get("limit")
    compose_file_api = request.json.get("compose_file")

    if not limit:
        return jsonify({"error": "--limit parameter is required"}), 400

    if compose_file_api:  # 如果 API 請求中提供了 compose 檔案路徑，則覆蓋預設值
        compose_file = compose_file_api

    if not compose_file or not os.path.exists(compose_file):
        return jsonify({"error": "Compose file not found"}), 400

    try:
        # 停止 docker compose
        subprocess.run(
            ["docker", "compose", "-f", compose_file, "down"],
            check=True,
            capture_output=True,
        )

        # 啟動 docker compose with new limit
        subprocess.run(
            [
                "LIMIT=" + str(limit),
                "docker",
                "compose",
                "-f",
                compose_file,
                "up",
                "-d",
            ],
            check=True,
            capture_output=True,
        )

        return (
            jsonify(
                {
                    "message": f"Docker Compose restarted with LIMIT={limit} and file={compose_file}"
                }
            ),
            200,
        )

    except subprocess.CalledProcessError as e:
        return (
            jsonify(
                {
                    "error": f"Error restarting Docker Compose: {e.stderr.decode()}",
                    "returncode": e.returncode,
                }
            ),
            500,
        )

    except Exception as e:  # 捕捉其他潛在的錯誤，例如檔案不存在
        return jsonify({"error": f"An unexpected error occurred: {str(e)}"}), 500


# @app.route("/restart", methods=["POST"])
def restart_docker_compose():
    if not check_device_exists():
        return jsonify({"error": "TEAC Corp. US-2x2HR device not found"}), 400

    if not check_default_audio_devices():
        return jsonify({"error": "Default audio devices are not set correctly"}), 400

    if not check_volume_levels():
        return jsonify({"error": "Volume levels are not at 100%"}), 400

    limit = request.json.get("limit")
    compose_file_api = request.json.get("compose_file")

    if not limit:
        return jsonify({"error": "--limit parameter is required"}), 400

    if compose_file_api:  # 如果 API 請求中提供了 compose 檔案路徑，則覆蓋預設值
        compose_file = compose_file_api

    if not compose_file or not os.path.exists(compose_file):
        return jsonify({"error": "Compose file not found"}), 400

    try:
        # 停止 docker compose
        subprocess.run(
            ["docker", "compose", "-f", compose_file, "down"],
            check=True,
            capture_output=True,
        )

        # 啟動 docker compose with new limit
        subprocess.run(
            [
                "LIMIT=" + str(limit),
                "docker",
                "compose",
                "-f",
                compose_file,
                "up",
                "-d",
            ],
            check=True,
            capture_output=True,
        )

        return (
            jsonify(
                {
                    "message": f"Docker Compose restarted with LIMIT={limit} and file={compose_file}"
                }
            ),
            200,
        )

    except subprocess.CalledProcessError as e:
        return (
            jsonify(
                {
                    "error": f"Error restarting Docker Compose: {e.stderr.decode()}",
                    "returncode": e.returncode,
                }
            ),
            500,
        )

    except Exception as e:  # 捕捉其他潛在的錯誤，例如檔案不存在
        return jsonify({"error": f"An unexpected error occurred: {str(e)}"}), 500


if __name__ == "__main__":
    # server = pywsgi.WSGIServer(("0.0.0.0", 5000), app)
    # server.serve_forever()
    #

    # Test
    print(f"Detection of Audio Device: {check_device_exists()}")

    default_source, default_sink = query_default_audio_devices()
    if default_source is not None:
        set_volume_levels(default_source)
        print("Source Volume Level: 100")
    if default_sink is not None:
        set_volume_levels(default_sink)
        print("Sink Volume Level: 100")

    if check_audio_api():
        print("audio_api is running")

    audio_enh_status, limit = check_audio_enh()
    if audio_enh_status:
        print(f"audio_enh is running with LIMIT={limit}")

    limit = 32
    subprocess.run(
        ["docker", "compose", "-f", COMPOSE_FILE, "down"],
        check=True,
        capture_output=True,
    )

    subprocess.run(
        [
            "LIMIT=" + str(limit),
            "docker",
            "compose",
            "-f",
            COMPOSE_FILE,
            "up",
            "-d",
        ],
        check=True,
        capture_output=True,
    )

    if check_audio_api():
        print("audio_api is running")

    audio_enh_status, limit = check_audio_enh()
    if audio_enh_status:
        print(f"audio_enh is running with LIMIT={limit}")
