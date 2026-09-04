"""두 서버(FastAPI / 표준 라이브러리)가 같은 API 를 제공하는지 검증.

★ 왜 필요한가
   서버 구현이 두 개라서, 한쪽만 고치고 다른 쪽을 잊으면
   "어제는 되던 게 오늘은 안 된다"가 됩니다.
   FastAPI 는 이 환경에 설치할 수 없으므로 import 대신
   소스를 파싱해서 검사합니다.
"""

import ast
import unittest
from pathlib import Path

from services.api import routes

API_DIR = Path(__file__).resolve().parents[1] / "services" / "api"


def _parse(name: str) -> ast.Module:
    return ast.parse((API_DIR / name).read_text(encoding="utf-8"), filename=name)


class TestFastAPISource(unittest.TestCase):
    """main.py 는 여기서 실행할 수 없으므로 구문/참조만 검사합니다."""

    @classmethod
    def setUpClass(cls):
        cls.tree = _parse("main.py")

    def test_main_py_is_valid_python(self):
        self.assertIsInstance(self.tree, ast.Module)

    def test_every_routes_function_referenced_exists(self):
        missing = []
        for node in ast.walk(self.tree):
            if (isinstance(node, ast.Attribute)
                    and isinstance(node.value, ast.Name)
                    and node.value.id == "routes"):
                if not hasattr(routes, node.attr):
                    missing.append(node.attr)
        self.assertEqual(missing, [], f"routes 에 없는 함수 참조: {missing}")

    def test_declares_expected_paths(self):
        paths = set()
        for node in ast.walk(self.tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                if node.func.attr in ("get", "post", "websocket") and node.args:
                    arg = node.args[0]
                    if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                        paths.add(arg.value)
        expected = {
            "/health", "/api/system/health",
            "/api/office/layout", "/api/office/agents",
            "/api/agents", "/api/agents/{agent_id}",
            "/api/learning", "/api/learning/{agent_id}",
            "/api/research", "/api/research/{job_id}",
            "/api/data/providers", "/api/audit/events",
            "/api/audit/knowledge", "/api/audit/predictions",
            "/ws/events",
        }
        self.assertTrue(expected <= paths, f"빠진 경로: {sorted(expected - paths)}")


class TestStandaloneSource(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tree = _parse("standalone.py")
        cls.src = (API_DIR / "standalone.py").read_text(encoding="utf-8")

    def test_standalone_is_valid_python(self):
        self.assertIsInstance(self.tree, ast.Module)

    def test_standalone_uses_only_stdlib(self):
        """설치 없이 돌아야 하므로 외부 패키지를 쓰면 안 됩니다."""
        stdlib_ok = {
            "argparse", "asyncio", "base64", "hashlib", "json", "mimetypes",
            "queue", "socket", "struct", "threading", "time",
            "http", "http.server", "pathlib", "urllib", "urllib.parse",
            "__future__",
        }
        for node in ast.walk(self.tree):
            if isinstance(node, ast.Import):
                for n in node.names:
                    self.assertIn(n.name.split(".")[0], {m.split(".")[0] for m in stdlib_ok},
                                  f"외부 패키지 import: {n.name}")
            elif isinstance(node, ast.ImportFrom):
                mod = node.module or ""
                if mod.startswith("packages") or mod.startswith("services") or mod == "":
                    continue
                self.assertIn(mod.split(".")[0], {m.split(".")[0] for m in stdlib_ok},
                              f"외부 패키지 import: {mod}")

    def test_covers_same_paths_as_fastapi(self):
        for path in ["/health", "/api/system/health", "/api/office/layout",
                     "/api/office/agents", "/api/agents", "/api/learning",
                     "/api/research", "/api/data/providers",
                     "/api/audit/events", "/api/audit/knowledge",
                     "/api/audit/predictions", "/ws/events"]:
            self.assertIn(f'"{path}"', self.src, f"standalone 에 {path} 없음")


class TestWebSocketPrimitives(unittest.TestCase):
    """직접 구현한 WebSocket 인코딩/디코딩 검증."""

    def setUp(self):
        from services.api import standalone

        self.m = standalone

    def test_handshake_accept_rfc_example(self):
        # RFC 6455 의 예제 값
        self.assertEqual(
            self.m.ws_handshake_accept("dGhlIHNhbXBsZSBub25jZQ=="),
            "s3pPLMBiTxaQ9kYGzzhZRbK+xOo=",
        )

    def test_short_frame(self):
        f = self.m.encode_text_frame("hi")
        self.assertEqual(f[0], 0x81)
        self.assertEqual(f[1], 2)
        self.assertEqual(f[2:], b"hi")

    def test_medium_frame_uses_16bit_length(self):
        f = self.m.encode_text_frame("a" * 300)
        self.assertEqual(f[1], 126)

    def test_large_frame_uses_64bit_length(self):
        f = self.m.encode_text_frame("a" * 70000)
        self.assertEqual(f[1], 127)

    def test_roundtrip_with_masked_client_frame(self):
        import os
        import struct

        payload = "안녕하세요 world".encode("utf-8")
        mask = os.urandom(4)
        masked = bytes(b ^ mask[i % 4] for i, b in enumerate(payload))
        frame = bytes([0x81, 0x80 | len(payload)]) + mask + masked
        frames, rest = self.m.decode_frames(bytearray(frame))
        self.assertEqual(len(frames), 1)
        self.assertEqual(frames[0][1].decode("utf-8"), "안녕하세요 world")
        self.assertEqual(len(rest), 0)

    def test_partial_frame_is_buffered_not_lost(self):
        full = self.m.encode_text_frame("hello world")
        frames, rest = self.m.decode_frames(bytearray(full[:4]))
        self.assertEqual(frames, [])
        self.assertEqual(len(rest), 4)

    def test_close_frame(self):
        f = self.m.encode_close_frame()
        self.assertEqual(f[0], 0x88)


if __name__ == "__main__":
    unittest.main()
