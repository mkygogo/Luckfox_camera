import http.server
import shlex
import socket
import socketserver
import subprocess
import sys
import threading
import time


INPUT_RTSP_URL = "rtsp://127.0.0.1/live/0"
LISTEN_HOST = "0.0.0.0"
LISTEN_PORT = "8080"
AUDIO_DELAY_SECONDS = "2.0"
STREAM_PATH = "/live.ts"
TS_CHUNK_SIZE = 188 * 64


def wait_for_rtsp_server(host="127.0.0.1", port=554, timeout_seconds=30):
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        try:
            with socket.create_connection((host, port), timeout=1.0):
                return True
        except OSError:
            time.sleep(1)
    return False


def build_command():
    return [
        "ffmpeg",
        "-hide_banner",
        "-loglevel",
        "warning",
        "-fflags",
        "+genpts+nobuffer",
        "-flags",
        "low_delay",
        "-thread_queue_size",
        "1024",
        "-allowed_media_types",
        "video",
        "-rtsp_transport",
        "tcp",
        "-i",
        INPUT_RTSP_URL,
        "-thread_queue_size",
        "1024",
        "-f",
        "alsa",
        "-ac",
        "2",
        "-ar",
        "48000",
        "-itsoffset",
        AUDIO_DELAY_SECONDS,
        "-i",
        "hw:0,0",
        "-map",
        "0:v:0",
        "-map",
        "1:a:0",
        "-c:v",
        "copy",
        "-c:a",
        "mp2",
        "-b:a",
        "128k",
        "-ac",
        "1",
        "-ar",
        "48000",
        "-af",
        "aresample=async=1:first_pts=0",
        "-flush_packets",
        "1",
        "-muxdelay",
        "0",
        "-muxpreload",
        "0",
        "-mpegts_flags",
        "+resend_headers",
        "-f",
        "mpegts",
        "pipe:1",
    ]


def drain_stderr(stderr_pipe):
    try:
        for raw_line in iter(stderr_pipe.readline, b""):
            line = raw_line.decode("utf-8", errors="ignore").strip()
            if line:
                print(f"[relay][ffmpeg] {line}")
    finally:
        stderr_pipe.close()


class LiveRelayHandler(http.server.BaseHTTPRequestHandler):
    server_version = "LuckfoxLiveRelay/1.0"

    def do_GET(self):
        if self.path != STREAM_PATH:
            self.send_error(404)
            return

        if not wait_for_rtsp_server():
            self.send_error(503, "Local RTSP server not ready")
            return

        cmd = build_command()
        print(f"[relay] Client connected from {self.client_address[0]}:{self.client_address[1]}")
        print(f"[relay] Launching: {shlex.join(cmd)}")
        process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, bufsize=0)
        stderr_thread = threading.Thread(target=drain_stderr, args=(process.stderr,), daemon=True)
        stderr_thread.start()

        self.send_response(200)
        self.send_header("Content-Type", "video/mp2t")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Connection", "close")
        self.end_headers()

        try:
            while True:
                chunk = process.stdout.read(TS_CHUNK_SIZE)
                if not chunk:
                    break
                self.wfile.write(chunk)
                self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError):
            print(f"[relay] Client disconnected from {self.client_address[0]}:{self.client_address[1]}")
        finally:
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    process.kill()
            stderr_thread.join(timeout=1)

    def log_message(self, format, *args):
        return


class ThreadedHTTPServer(socketserver.ThreadingMixIn, http.server.HTTPServer):
    daemon_threads = True


def main():
    board_ip = sys.argv[1] if len(sys.argv) > 1 else "<board-ip>"
    public_url = f"http://{board_ip}:{LISTEN_PORT}{STREAM_PATH}"
    print("[relay] Starting external live audio relay")
    print(f"[relay] Public AV URL: {public_url}")
    print(f"[relay] Using local video source: {INPUT_RTSP_URL}")
    print(f"[relay] Applying audio delay: {AUDIO_DELAY_SECONDS}s")
    server = ThreadedHTTPServer((LISTEN_HOST, int(LISTEN_PORT)), LiveRelayHandler)
    print(f"[relay] Waiting for HTTP clients on {public_url}")
    server.serve_forever()


if __name__ == "__main__":
    main()