"""Smoke the OpenCode ingest receiver on an OS-assigned port.

Parallel worktrees must never share a fixed ingest port, so the receiver binds
port 0 and this check posts one envelope to the resulting address.
"""

from __future__ import annotations

import json
import sys
import tempfile
import threading
from pathlib import Path
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def main() -> int:
    from adapters.opencode.server import OpenCodeIngestServer

    with tempfile.TemporaryDirectory() as tmp:
        server = OpenCodeIngestServer(Path(tmp) / "events.db", port=0)
        host, port = server.address
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            payload = {
                "kind": "event:session.created",
                "timestamp": 1000,
                "payload": {"sessionID": "verify-smoke", "info": {"id": "verify-smoke"}},
            }
            request = Request(
                f"http://{host}:{port}/v1/opencode/events",
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urlopen(request, timeout=5) as response:
                body = json.loads(response.read().decode("utf-8"))
            if body.get("persisted") != 1:
                print(f"FAIL ingest receiver: response {body}")
                return 1
            events = server.store.events()
            if len(events) != 1:
                print(f"FAIL ingest receiver: stored {len(events)} events")
                return 1
            print(f"PASS ingest receiver (ephemeral port {port}, 1 event persisted)")
            return 0
        finally:
            server.close()
            thread.join(timeout=5)


if __name__ == "__main__":
    raise SystemExit(main())
