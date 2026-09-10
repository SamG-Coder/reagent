"""Bounded terminal views of provider-independent model-call audit files."""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any


class CallReports:
    def __init__(self) -> None:
        self.cache: dict[Path, tuple[tuple[int, int], dict[str, Any]]] = {}

    def read(self, root: Path, pattern: str) -> list[dict[str, Any]]:
        entries = []
        for path in root.glob(pattern):
            try:
                if path.is_file() and path.resolve().is_relative_to(root):
                    stat = path.stat()
                    entries.append((stat.st_mtime_ns, stat.st_size, path))
            except OSError:
                continue
        latest = sorted(entries, key=lambda item: (item[0], str(item[2])))[-128:]
        keep = {path for _, _, path in latest}
        self.cache = {path: data for path, data in self.cache.items() if path in keep}
        agents = []
        for stamp, size, path in latest:
            if size > 2 * 1024 * 1024:
                continue
            if path not in self.cache or self.cache[path][0] != (stamp, size):
                try:
                    with path.open('rb') as stream:
                        data = json.loads(stream.read(2 * 1024 * 1024 + 1))
                    if not isinstance(data, dict):
                        continue
                    self.cache[path] = ((stamp, size), data)
                except (OSError, ValueError):
                    continue
            data = self.cache[path][1]
            status = data.get('status') or ('failed' if data.get('error') else 'completed')
            duration = data.get('duration_s')
            if status == 'running' and isinstance(data.get('started_at'), (int, float)):
                duration = max(0, time.time() - data['started_at'])
            timing = f'{duration:.1f}s' if isinstance(duration, (float, int)) else 'unknown'
            label = (f"{data.get('target') or path.parent.name} · "
                     f"{data.get('role', 'model')} · call {data.get('call', '?')}")
            log = f"Request {status} · elapsed {timing} · queue wait {data.get('queue_wait_s', 0)}s"
            if data.get('error'):
                log += '\n' + str(data['error'])
            agents.append(dict(id='call:' + path.relative_to(root).as_posix(), label=label,
                               status=status, text=str(data.get('response') or '')[-65536:], log=log[-65536:]))
        return agents
