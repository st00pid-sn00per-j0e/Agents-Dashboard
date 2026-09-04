#!/usr/bin/env python3
"""Minimal local HTTP bridge for the Supervisor web console.

Run from the repository root:
    .\.venv\Scripts\python.exe src\SupervisorAPI.py
"""

import asyncio
import json
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlsplit

from Supervisor import PREVIEW_DIR, _client, discover_agents, execute_task

# Optional WebRTC support (aiortc)
try:
    from aiortc import RTCPeerConnection, RTCSessionDescription
    from aiortc import VideoStreamTrack
    import av
    from PIL import Image
    HAVE_AIORTC = True
except Exception:
    HAVE_AIORTC = False



class SupervisorRequestHandler(BaseHTTPRequestHandler):
    server_version = "NexusSupervisorAPI/1.0"
    allowed_origins = {"http://localhost:5173", "http://127.0.0.1:5173"}
    max_request_bytes = 25_000

    def _send_json(self, status: HTTPStatus, payload: dict) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Referrer-Policy", "no-referrer")
        origin = self.headers.get("Origin")
        if origin in self.allowed_origins:
            self.send_header("Access-Control-Allow-Origin", origin)
            self.send_header("Vary", "Origin")
        self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()
        self.wfile.write(body)

    def _send_preview(self, preview_path) -> None:
        image = preview_path.read_bytes()
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "image/png")
        self.send_header("Content-Length", str(len(image)))
        self.send_header("Cache-Control", "no-store, max-age=0")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.end_headers()
        self.wfile.write(image)

    def do_OPTIONS(self) -> None:
        # Allow OPTIONS for health, chat, and optional webrtc endpoints
        path = urlsplit(self.path).path
        allowed = {"/api/chat", "/api/health"}
        if path.startswith("/api/webrtc/"):
            allowed.add(path)
        if path not in allowed and not path.startswith("/api/webrtc/"):
            self._send_json(HTTPStatus.NOT_FOUND, {"error": "Endpoint not found."})
            return
        self._send_json(HTTPStatus.NO_CONTENT, {})

    def do_GET(self) -> None:
        if self.path == "/api/health":
            self._send_json(
                HTTPStatus.OK,
                {
                    "status": "ready" if _client is not None else "configuration_required",
                    "agents": sorted(discover_agents()),
                },
            )
            return

        preview_prefix = "/api/previews/"
        if self.path.startswith(preview_prefix):
            agent_name = self.path.removeprefix(preview_prefix).removesuffix(".png")
            if (
                not self.path.endswith(".png")
                or agent_name not in discover_agents()
                or "/" in agent_name
                or "\\" in agent_name
            ):
                self._send_json(HTTPStatus.NOT_FOUND, {"error": "Preview not found."})
                return
            preview_path = PREVIEW_DIR / f"{agent_name}.png"
            if not preview_path.is_file() or preview_path.stat().st_size > 8_000_000:
                self._send_json(HTTPStatus.NOT_FOUND, {"error": "Preview not available."})
                return
            self._send_preview(preview_path)
            return

        # WebRTC signaling: POST to /api/webrtc/<agent> with JSON { sdp, type }
        if self.path.startswith("/api/webrtc/"):
            if not HAVE_AIORTC:
                self._send_json(HTTPStatus.SERVICE_UNAVAILABLE, {"error": "WebRTC support not available on server (missing aiortc/av/Pillow)."})
                return
            agent_name = self.path.removeprefix("/api/webrtc/")
            if agent_name not in discover_agents():
                self._send_json(HTTPStatus.NOT_FOUND, {"error": "Agent not found."})
                return
            # Only accept POST for this path; GET isn't defined here
            self._send_json(HTTPStatus.NOT_FOUND, {"error": "Endpoint not found."})
            return

        if self.path != "/api/health":
            self._send_json(HTTPStatus.NOT_FOUND, {"error": "Endpoint not found."})
            return

    def do_POST(self) -> None:
        # WebRTC offer handling
        if self.path.startswith("/api/webrtc/"):
            if not HAVE_AIORTC:
                self._send_json(HTTPStatus.SERVICE_UNAVAILABLE, {"error": "WebRTC support not available on server (missing aiortc/av/Pillow)."})
                return
            agent_name = self.path.removeprefix("/api/webrtc/")
            if agent_name not in discover_agents():
                self._send_json(HTTPStatus.NOT_FOUND, {"error": "Agent not found."})
                return
            try:
                content_type = self.headers.get_content_type()
                if content_type != "application/json":
                    self._send_json(HTTPStatus.UNSUPPORTED_MEDIA_TYPE, {"error": "Content-Type must be application/json."})
                    return
                content_length = int(self.headers.get("Content-Length", "0"))
                if content_length <= 0 or content_length > self.max_request_bytes:
                    raise ValueError("Invalid request size.")
                payload = json.loads(self.rfile.read(content_length).decode("utf-8"))
                offer_sdp = payload.get("sdp")
                offer_type = payload.get("type")
                if not isinstance(offer_sdp, str) or not isinstance(offer_type, str):
                    raise ValueError("Invalid SDP payload.")
            except ValueError as error:
                self._send_json(HTTPStatus.BAD_REQUEST, {"error": str(error)})
                return

            # Create an RTC peer that will send a video track composed from the agent preview.
            class PreviewTrack(VideoStreamTrack):
                def __init__(self, preview_path):
                    super().__init__()
                    self.preview_path = preview_path

                async def recv(self):
                    pts, time_base = await self.next_timestamp()
                    # Read the latest PNG and convert to VideoFrame
                    try:
                        img = Image.open(self.preview_path).convert('RGB')
                        frame = av.VideoFrame.from_image(img)
                        frame.pts = pts
                        frame.time_base = time_base
                        return frame
                    except Exception as e:
                        # on error, return a black frame
                        w, h = 320, 180
                        img = Image.new('RGB', (w, h), (0, 0, 0))
                        frame = av.VideoFrame.from_image(img)
                        frame.pts = pts
                        frame.time_base = time_base
                        return frame

            try:
                pc = RTCPeerConnection()
                # Add the preview track
                preview_path = PREVIEW_DIR / f"{agent_name}.png"
                track = PreviewTrack(str(preview_path))
                pc.addTrack(track)

                offer = RTCSessionDescription(sdp=offer_sdp, type=offer_type)
                # run the async negotiation
                async def negotiate():
                    await pc.setRemoteDescription(offer)
                    answer = await pc.createAnswer()
                    await pc.setLocalDescription(answer)
                    # keep the connection alive - we won't close here
                    return pc.localDescription

                local_desc = asyncio.run(negotiate())
                self._send_json(HTTPStatus.OK, {"sdp": local_desc.sdp, "type": local_desc.type})
            except Exception as e:
                print(f"[Supervisor API] WebRTC offer handling failed: {type(e).__name__}: {e}")
                self._send_json(HTTPStatus.INTERNAL_SERVER_ERROR, {"error": "Failed to establish WebRTC session."})
            return

        # Fallback to the existing chat POST handler
        if self.path != "/api/chat":
            self._send_json(HTTPStatus.NOT_FOUND, {"error": "Endpoint not found."})
            return

        try:
            content_type = self.headers.get_content_type()
            if content_type != "application/json":
                self._send_json(
                    HTTPStatus.UNSUPPORTED_MEDIA_TYPE,
                    {"error": "Content-Type must be application/json."},
                )
                return
            content_length = int(self.headers.get("Content-Length", "0"))
            if content_length <= 0 or content_length > self.max_request_bytes:
                raise ValueError("Invalid request size.")
            payload = json.loads(self.rfile.read(content_length).decode("utf-8"))
            if not isinstance(payload, dict):
                raise ValueError("Request body must be a JSON object.")
            task = payload.get("message")
            if not isinstance(task, str):
                raise ValueError("The 'message' field must be a string.")
            result = asyncio.run(execute_task(task))
        except ValueError as error:
            self._send_json(HTTPStatus.BAD_REQUEST, {"error": str(error)})
        except Exception as error:
            # Do not expose provider credentials, paths, or raw subprocess
            # exceptions through the browser boundary.
            print(f"[Supervisor API] request failed: {type(error).__name__}: {error}")
            self._send_json(
                HTTPStatus.INTERNAL_SERVER_ERROR,
                {"error": "The supervisor could not complete this request. Check the server console."},
            )
        else:
            self._send_json(HTTPStatus.OK, result)

    def log_message(self, format: str, *args) -> None:
        print(f"[Supervisor API] {format % args}")


if __name__ == "__main__":
    server = HTTPServer(("127.0.0.1", 8000), SupervisorRequestHandler)
    print("Supervisor API listening at http://127.0.0.1:8000/api/chat")
    if HAVE_AIORTC:
        print("WebRTC signaling available at http://127.0.0.1:8000/api/webrtc/<agent>")
    else:
        print("Note: WebRTC support is NOT available. Install aiortc, av, and Pillow and restart the server to enable it.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nSupervisor API stopped.")
    finally:
        server.server_close()
