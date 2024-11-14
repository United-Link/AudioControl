import subprocess


def check_device_exists():
    """檢查是否存在 "TEAC Corp. US-2x2HR" 裝置"""
    try:
        result = subprocess.run(["lsusb"], capture_output=True, text=True, check=True)
        return "TEAC Corp. US-2x2HR" in result.stdout
    except subprocess.CalledProcessError:
        return False


if __name__ == "__main__":
    print(check_device_exists())
