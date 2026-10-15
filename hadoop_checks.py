"""Optional checks through documented Hadoop command-line interfaces.

These checks run only when explicitly requested and never simulate connectivity.
"""

from __future__ import annotations

import shutil
import subprocess
from typing import Any


def check_hadoop_services(config: dict[str, Any]) -> list[dict[str, Any]]:
    timeout = int(config.get("timeout_seconds", 10))
    if not 1 <= timeout <= 120:
        raise ValueError("hadoop.timeout_seconds must be between 1 and 120.")
    commands = [
        ("HDFS", ["hdfs", "dfsadmin", "-report"]),
        ("YARN", ["yarn", "node", "-list", "-all"]),
    ]
    results = []
    for component, command in commands:
        if shutil.which(command[0]) is None:
            results.append(
                {
                    "component": component,
                    "status": "WARNING",
                    "details": f"{command[0]} CLI not found; check not run.",
                }
            )
            continue
        try:
            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=timeout,
                check=False,
            )
            ok = result.returncode == 0
            if ok:
                detail = "CLI command completed successfully."
            else:
                output = (result.stderr or result.stdout).strip()[:300]
                detail = f"CLI exited with code {result.returncode}: {output}"
            results.append(
                {
                    "component": component,
                    "status": "HEALTHY" if ok else "CRITICAL",
                    "details": detail,
                }
            )
        except subprocess.TimeoutExpired:
            results.append(
                {
                    "component": component,
                    "status": "CRITICAL",
                    "details": f"CLI timed out after {timeout} seconds.",
                }
            )
        except OSError as exc:
            results.append(
                {
                    "component": component,
                    "status": "CRITICAL",
                    "details": f"Could not execute CLI: {exc}",
                }
            )
    return results
