import os
import shutil
import subprocess
import logging
from typing import Optional

from fs42.station_manager import StationManager


class LiveOutputStream:
    def __init__(self):
        self._l = logging.getLogger("LiveOutputStream")
        self._process: Optional[subprocess.Popen] = None
        self._live_dir = StationManager().server_conf.get("live_stream_dir", "runtime/live")
        self._manifest = os.path.join(self._live_dir, "index.m3u8")

    @property
    def live_dir(self):
        return self._live_dir

    @property
    def manifest_path(self):
        return self._manifest

    def clear_output(self):
        os.makedirs(self._live_dir, exist_ok=True)
        for name in os.listdir(self._live_dir):
            path = os.path.join(self._live_dir, name)
            if os.path.isfile(path):
                try:
                    os.remove(path)
                except Exception as exc:
                    self._l.debug("Failed to remove %s: %s", path, exc)

    def stop(self, clear_output=True):
        if self._process and self._process.poll() is None:
            try:
                self._process.terminate()
                self._process.wait(timeout=2)
            except Exception:
                try:
                    self._process.kill()
                except Exception:
                    pass
        self._process = None
        if clear_output:
            self.clear_output()

    def start(self, source: str, is_stream=False):
        if not shutil.which("ffmpeg"):
            self._l.warning("ffmpeg is not installed; skipping browser live output")
            return

        self.stop(clear_output=True)
        os.makedirs(self._live_dir, exist_ok=True)

        command = [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "warning",
            "-y",
        ]

        if is_stream:
            command.extend(
                [
                    "-fflags",
                    "+genpts",
                    "-reconnect",
                    "1",
                    "-reconnect_streamed",
                    "1",
                    "-reconnect_delay_max",
                    "2",
                ]
            )

        command.extend(
            [
                "-i",
                source,
                "-map",
                "0:v:0",
                "-map",
                "0:a:0?",
                "-c:v",
                "libx264",
                "-preset",
                "veryfast",
                "-tune",
                "zerolatency",
                "-pix_fmt",
                "yuv420p",
                "-c:a",
                "aac",
                "-ar",
                "48000",
                "-ac",
                "2",
                "-f",
                "hls",
                "-hls_time",
                "2",
                "-hls_list_size",
                "6",
                "-hls_flags",
                "delete_segments+append_list+independent_segments",
                "-hls_segment_filename",
                os.path.join(self._live_dir, "segment_%05d.ts"),
                self._manifest,
            ]
        )

        try:
            self._process = subprocess.Popen(command)
        except Exception as exc:
            self._l.warning("Failed to start ffmpeg live output: %s", exc)
            self._process = None
