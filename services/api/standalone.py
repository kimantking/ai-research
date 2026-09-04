"""표준 라이브러리만으로 동작하는 서버.

★ 왜 이게 있는가
   "아무것도 설치되지 않아도 일단 화면이 떠야 한다"가 목표입니다.
   pip 이 막히거나 Node 가 없어도, 파이썬만 있으면 픽셀 사무실이 뜹니다.

   FastAPI 가 설치되어 있으면 services/api/main.py 쪽이 기본입니다.
   두 서버는 services/api/routes.py 의 같은 로직을 쓰므로
   응답이 서로 달라질 수 없습니다.

실행:
    python -m services.api.standalone
    python -m services.api.standalone --port 8010
"""

from __future__ import annotations

import argparse
import asyncio
import base64
import hashlib
import json
import mimetypes
import queue
import socket
import struct
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from packages.shared.config import get_settings
from packages.shared.logging import get_logger
from services.agent_runtime.engine import Engine

from . import routes

log = get_logger("standalone")

WS_GUID = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"


# ====================================================================== WebSocket


def ws_handshake_accept(key: str) -> str:
    digest = hashlib.sha1((key + WS_GUID).encode("utf-8")).digest()
    return base64.b64encode(digest).decode("ascii")


def encode_text_frame(payload: str) -> bytes:
    """서버 → 클라이언트 텍스트 프레임 (마스킹 없음)."""
    data = payload.encode("utf-8")
    header = bytearray([0x81])  # FIN + text opcode
    n = len(data)
    if n < 126:
        header.append(n)
    elif n < 65536:
        header.append(126)
        header += struct.pack(">H", n)
    else:
        header.append(127)
        header += struct.pack(">Q", n)
    return bytes(header) + data


def encode_close_frame(code: int = 1000) -> bytes:
    return bytes([0x88, 0x02]) + struct.pack(">H", code)


def decode_frames(buffer: bytearray) -> tuple[list[tuple[int, bytes]], bytearray]:
    """버퍼에서 완성된 프레임을 뽑아냅니다. (opcode, payload) 목록을 반환."""
    out: list[tuple[int, bytes]] = []
    while True:
        if len(buffer) < 2:
            break
        b0, b1 = buffer[0], buffer[1]
        opcode = b0 & 0x0F
        masked = bool(b1 & 0x80)
        length = b1 & 0x7F
        idx = 2
        if length == 126:
            if len(buffer) < idx + 2:
                break
            length = struct.unpack(">H", buffer[idx : idx + 2])[0]
            idx += 2
        elif length == 127:
            if len(buffer) < idx + 8:
                break
            length = struct.unpack(">Q", buffer[idx : idx + 8])[0]
            idx += 8
        mask = b""
        if masked:
            if len(buffer) < idx + 4:
                break
            mask = bytes(buffer[idx : idx + 4])
            idx += 4
        if len(buffer) < idx + length:
            break
        payload = bytes(buffer[idx : idx + length])
        if masked:
            payload = bytes(p ^ mask[i % 4] for i, p in enumerate(payload))
        out.append((opcode, payload))
        buffer = buffer[idx + length :]
    return out, buffer


# ====================================================================== 서버 상태


class AppState:
    def __init__(self, engine: Engine, settings):
        self.engine = engine
        self.settings = settings
        self._stop = threading.Event()

    # ---- 엔진 틱 스레드 ----
    def start_engine(self, interval: float = 1.5) -> None:
        def loop():
            while not self._stop.is_set():
                try:
                    self.engine.tick()
                except Exception as exc:
                    log.error("tick_failed", error=str(exc))
                self._stop.wait(interval)

        t = threading.Thread(target=loop, name="engine-tick", daemon=True)
        t.start()
        self.engine.bus.emit(
            "system.started", is_mock=self.engine.mock_mode,
            detail="런타임 시작 (standalone 서버)",
            active_agents=len(self.engine.registry.active()),
            total_agents=len(self.engine.registry.all()),
        )

    def stop(self) -> None:
        self._stop.set()

    # ---- 리서치 잡은 코루틴이므로 워커 스레드에서 실행 ----
    def run_job_async(self, job_id: str) -> None:
        def work():
            try:
                asyncio.run(self.engine.run_research(job_id))
            except Exception as exc:
                log.error("research_failed", job_id=job_id, error=str(exc))
                job = self.engine.jobs.get(job_id)
                if job:
                    job["status"] = "FAILED"
                    job["error"] = str(exc)

        threading.Thread(target=work, name=f"job-{job_id}", daemon=True).start()


STATE: AppState | None = None


# ====================================================================== 핸들러


class Handler(BaseHTTPRequestHandler):
    server_version = "AIRO/0.1"
    protocol_version = "HTTP/1.1"

    # 로그를 조용히 (구조화 로거로 대체)
    def log_message(self, fmt, *args):
        pass

    # ------------------------------------------------------------------
    def _json(self, status: int, payload: dict) -> None:
        body = json.dumps(payload, ensure_ascii=False, default=str).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _file(self, path: Path) -> None:
        if not path.exists() or not path.is_file():
            self._json(404, {"error": "파일을 찾을 수 없습니다"})
            return
        ctype = mimetypes.guess_type(str(path))[0] or "application/octet-stream"
        if ctype.startswith("text/") or ctype in ("application/javascript",):
            ctype += "; charset=utf-8"
        body = path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    # ------------------------------------------------------------------
    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Content-Length", "0")
        self.end_headers()

    def do_POST(self):
        assert STATE is not None
        parsed = urlparse(self.path)
        length = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(length) if length else b"{}"
        try:
            body = json.loads(raw.decode("utf-8") or "{}")
        except json.JSONDecodeError:
            self._json(400, {"error": "JSON 형식이 아닙니다"})
            return

        if parsed.path == "/api/data/load":
            status, payload = routes.load_market(
                STATE.engine,
                symbols=str(body.get("symbols", "")),
                provider=str(body.get("provider", "csv_file")),
                start=str(body.get("start", "")),
                end=str(body.get("end", "")),
            )
            self._json(status, payload)
            return

        if parsed.path == "/api/persistence/save":
            status, payload = routes.save_state(STATE.engine)
            self._json(status, payload)
            return

        if parsed.path == "/api/research":
            status, payload = routes.create_research(
                STATE.engine, body.get("ticker", ""), body.get("sector")
            )
            if status == 200:
                STATE.run_job_async(payload["job_id"])
            self._json(status, payload)
            return

        if parsed.path == "/api/backtest":
            status, payload = routes.run_backtest(
                STATE.engine,
                body.get("ticker", ""),
                body.get("strategy", "sma_crossover"),
                float(body.get("commission_bps", 5.0)),
                float(body.get("slippage_bps", 5.0)),
            )
            self._json(status, payload)
            return

        self._json(404, {"error": f"알 수 없는 경로: {parsed.path}"})

    # ------------------------------------------------------------------
    def do_GET(self):
        assert STATE is not None
        parsed = urlparse(self.path)
        path = parsed.path
        q = parse_qs(parsed.query)

        def one(name, default=None):
            v = q.get(name)
            return v[0] if v else default

        # ---- WebSocket ----
        if path == "/ws/events":
            self._serve_websocket()
            return

        e = STATE.engine
        s = STATE.settings

        # ---- 정적 파일 ----
        if path in ("/", "/index.html", "/office"):
            self._file(s.static_dir / "office.html")
            return
        if path.startswith("/static/"):
            rel = path[len("/static/") :]
            target = (s.static_dir / rel).resolve()
            # 경로 탈출 방지
            if not str(target).startswith(str(s.static_dir.resolve())):
                self._json(403, {"error": "허용되지 않은 경로"})
                return
            self._file(target)
            return

        # ---- API ----
        table = {
            "/health": lambda: routes.health(e, s.llm_available),
            "/api/system/health": lambda: routes.system_health(e),
            "/api/office/layout": lambda: routes.office_layout(e),
            "/api/office/agents": lambda: routes.office_agents(e),
            "/api/agents": lambda: routes.list_agents(
                e, one("status"), one("department"), one("sector"),
                int(one("limit", "500")),
            ),
            "/api/learning": lambda: routes.learning_overview(e),
            "/api/research": lambda: routes.list_jobs(e, int(one("limit", "20"))),
            "/api/backtest": lambda: routes.list_backtests(e, int(one("limit", "20"))),
            "/api/patterns": lambda: routes.patterns(
                e, int(one("horizon", "5")), one("force", "0") == "1"
            ),
            "/api/data/providers": lambda: routes.data_providers(e),
            "/api/markets": lambda: routes.markets(e),
            "/api/calendar": lambda: routes.calendar_info(
                e, one("exchange", "XNYS"), one("start", ""), one("end", "")
            ),
            "/api/sec/filings": lambda: routes.sec_filings(
                e, one("cik", ""), one("forms", ""), int(one("limit", "20"))
            ),
            "/api/dart/filings": lambda: routes.dart_filings(
                e, one("stock_code", ""), one("begin", ""), one("end", ""),
                int(one("limit", "30"))
            ),
            "/api/persistence": lambda: routes.persistence(e),
            "/api/audit/events": lambda: routes.audit_events(e, int(one("limit", "100"))),
            "/api/audit/knowledge": lambda: routes.audit_knowledge(e),
            "/api/audit/predictions": lambda: routes.audit_predictions(e),
        }
        if path in table:
            status, payload = table[path]()
            self._json(status, payload)
            return

        if path.startswith("/api/agents/"):
            status, payload = routes.agent_detail(e, path.split("/api/agents/", 1)[1])
            self._json(status, payload)
            return
        if path.startswith("/api/learning/"):
            status, payload = routes.learning_detail(e, path.split("/api/learning/", 1)[1])
            self._json(status, payload)
            return
        if path.startswith("/api/research/"):
            status, payload = routes.get_job(e, path.split("/api/research/", 1)[1])
            self._json(status, payload)
            return
        if path.startswith("/api/backtest/"):
            status, payload = routes.get_backtest(e, path.split("/api/backtest/", 1)[1])
            self._json(status, payload)
            return

        self._json(404, {"error": f"알 수 없는 경로: {path}"})

    # ------------------------------------------------------------------
    def _serve_websocket(self) -> None:
        assert STATE is not None
        key = self.headers.get("Sec-WebSocket-Key")
        upgrade = (self.headers.get("Upgrade") or "").lower()
        if not key or upgrade != "websocket":
            self._json(400, {"error": "WebSocket 업그레이드 요청이 아닙니다"})
            return

        accept = ws_handshake_accept(key)
        self.send_response(101, "Switching Protocols")
        self.send_header("Upgrade", "websocket")
        self.send_header("Connection", "Upgrade")
        self.send_header("Sec-WebSocket-Accept", accept)
        self.end_headers()

        conn: socket.socket = self.connection
        engine = STATE.engine
        sub = engine.bus.subscribe_thread()
        alive = threading.Event()
        alive.set()

        def reader():
            """클라이언트 프레임을 읽어 버립니다 (close 감지용)."""
            buf = bytearray()
            try:
                conn.settimeout(1.0)
                while alive.is_set():
                    try:
                        chunk = conn.recv(4096)
                    except socket.timeout:
                        continue
                    except OSError:
                        break
                    if not chunk:
                        break
                    buf += chunk
                    frames, buf = decode_frames(buf)
                    for opcode, _payload in frames:
                        if opcode == 0x8:  # close
                            alive.clear()
                            return
            finally:
                alive.clear()

        t = threading.Thread(target=reader, name="ws-reader", daemon=True)
        t.start()

        try:
            conn.sendall(encode_text_frame(
                json.dumps(routes.snapshot(engine), ensure_ascii=False, default=str)
            ))
            last_beat = time.time()
            while alive.is_set():
                try:
                    event = sub.get(timeout=1.0)
                    conn.sendall(encode_text_frame(
                        json.dumps(event, ensure_ascii=False, default=str)
                    ))
                except queue.Empty:
                    if time.time() - last_beat > 15:
                        last_beat = time.time()
                        conn.sendall(encode_text_frame(json.dumps({
                            "type": "heartbeat",
                            "ts": routes._now(),
                            "is_mock": engine.mock_mode,
                        }, ensure_ascii=False)))
                except (BrokenPipeError, ConnectionResetError, OSError):
                    break
        finally:
            alive.clear()
            engine.bus.unsubscribe_thread(sub)
            try:
                conn.sendall(encode_close_frame())
            except OSError:
                pass
            self.close_connection = True


# ====================================================================== 진입점


def build_state() -> AppState:
    settings = get_settings()
    db_path = None
    if settings.persistence == "sqlite":
        db_path = settings.project_root / settings.sqlite_path
    engine = Engine(config_dir=settings.config_dir, mock_mode=settings.mock_mode,
                    db_path=db_path,
                    autosave_every=settings.autosave_every_ticks)
    # 실데이터 설정을 엔진에 붙여둡니다 (라우트가 읽습니다)
    engine.market_data_dir = str(settings.project_root / settings.market_data_dir)
    engine.market_exchange = settings.market_exchange
    engine.sec_contact_email = settings.sec_contact_email
    engine.data_go_kr_key = settings.data_go_kr_key
    engine.dart_api_key = settings.dart_api_key
    return AppState(engine, settings)


def serve(port: int | None = None, host: str = "127.0.0.1",
          tick_interval: float = 1.5, state: AppState | None = None):
    global STATE
    STATE = state or build_state()
    port = port or STATE.settings.api_port
    STATE.start_engine(tick_interval)

    httpd = ThreadingHTTPServer((host, port), Handler)
    httpd.daemon_threads = True
    log.info(
        "server_ready",
        url=f"http://{host}:{port}",
        agents_total=len(STATE.engine.registry.all()),
        agents_active=len(STATE.engine.registry.active()),
        mock_mode=STATE.engine.mock_mode,
    )
    return httpd


def main() -> None:
    ap = argparse.ArgumentParser(description="AI Stock Research Office (standalone)")
    ap.add_argument("--port", type=int, default=None)
    ap.add_argument("--host", type=str, default="127.0.0.1")
    ap.add_argument("--tick", type=float, default=1.5)
    args = ap.parse_args()

    httpd = serve(args.port, args.host, args.tick)
    sa = httpd.socket.getsockname()
    print()
    print("=" * 62)
    print("  AI STOCK RESEARCH OFFICE — standalone 모드")
    print("  (외부 패키지 없이 파이썬 표준 기능만으로 동작 중)")
    print("=" * 62)
    print(f"  픽셀 사무실 :  http://{sa[0]}:{sa[1]}")
    print(f"  API 상태    :  http://{sa[0]}:{sa[1]}/health")
    print("  종료        :  Ctrl+C")
    print()
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n종료합니다...")
    finally:
        if STATE:
            STATE.stop()
        httpd.shutdown()


if __name__ == "__main__":
    main()
