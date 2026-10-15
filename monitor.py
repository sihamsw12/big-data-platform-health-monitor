"""Local system health checks for a data platform host."""

from __future__ import annotations

import argparse
import json
import logging
import platform
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import psutil

from hadoop_checks import check_hadoop_services

ROOT = Path(__file__).resolve().parent
DEFAULT_CONFIG = ROOT / "config.json"
DEFAULT_REPORT = ROOT / "reports" / "health-report.json"
DEFAULT_INCIDENTS = ROOT / "reports" / "incidents.jsonl"
COMPONENTS = ("disk", "memory", "cpu")
SEVERITIES = {"HEALTHY": 0, "WARNING": 1, "CRITICAL": 2}


class MonitorError(Exception):
    """An actionable configuration or execution error."""


def load_config(path: Path) -> dict[str, Any]:
    try:
        config = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise MonitorError(f"Configuration file not found: {path}") from exc
    except (OSError, json.JSONDecodeError) as exc:
        raise MonitorError(f"Cannot read configuration {path}: {exc}") from exc
    if not isinstance(config, dict) or not isinstance(config.get("thresholds"), dict):
        raise MonitorError("Configuration must contain a 'thresholds' object.")
    thresholds = config["thresholds"]
    for component in COMPONENTS:
        values = thresholds.get(component)
        if not isinstance(values, dict):
            raise MonitorError(f"Missing thresholds for '{component}'.")
        warning, critical = values.get("warning"), values.get("critical")
        if (not isinstance(warning, (int, float)) or isinstance(warning, bool)
                or not isinstance(critical, (int, float)) or isinstance(critical, bool)
                or not 0 <= warning < critical <= 100):
            raise MonitorError(
                f"Thresholds for '{component}' must satisfy 0 <= warning < critical <= 100."
            )
    return config


def status_for(value: float, thresholds: dict[str, float]) -> str:
    if value >= thresholds["critical"]:
        return "CRITICAL"
    if value >= thresholds["warning"]:
        return "WARNING"
    return "HEALTHY"


def check_disk(thresholds: dict[str, float], path: Path = Path.home(),
               usage: Any = None) -> dict[str, Any]:
    usage = usage if usage is not None else shutil.disk_usage(path)
    percent = usage.used / usage.total * 100
    return {"component": "Disk", "usage_percent": round(percent, 2),
            "total_bytes": usage.total, "free_bytes": usage.free,
            "status": status_for(percent, thresholds)}


def check_memory(thresholds: dict[str, float], metrics: Any = None) -> dict[str, Any]:
    memory = metrics if metrics is not None else psutil.virtual_memory()
    return {"component": "Memory", "usage_percent": round(float(memory.percent), 2),
            "total_gb": round(memory.total / (1024 ** 3), 2),
            "available_gb": round(memory.available / (1024 ** 3), 2),
            "status": status_for(float(memory.percent), thresholds)}


def check_cpu(thresholds: dict[str, float], usage: float | None = None) -> dict[str, Any]:
    percent = float(psutil.cpu_percent(interval=1) if usage is None else usage)
    return {"component": "CPU", "usage_percent": round(percent, 2),
            "status": status_for(percent, thresholds)}


def global_status(checks: list[dict[str, Any]]) -> str:
    return max((check["status"] for check in checks), key=SEVERITIES.__getitem__, default="HEALTHY")


def append_incidents(path: Path, checks: list[dict[str, Any]], timestamp: str) -> None:
    incidents = [
        {"timestamp": timestamp, "component": item["component"],
         "severity": item["status"],
         "description": (
             f"{item['component']} usage is {item['usage_percent']}%."
             if "usage_percent" in item else item.get("details", "Health check reported an issue.")
         )}
        for item in checks if item["status"] != "HEALTHY"
    ]
    if incidents:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as stream:
            for incident in incidents:
                stream.write(json.dumps(incident, ensure_ascii=False) + "\n")


def run_monitor(config_path: Path = DEFAULT_CONFIG, report_path: Path = DEFAULT_REPORT,
                incidents_path: Path = DEFAULT_INCIDENTS, *, cpu_usage: float | None = None,
                memory_metrics: Any = None, disk_usage: Any = None,
                include_hadoop: bool = False) -> dict[str, Any]:
    config = load_config(config_path)
    thresholds = config["thresholds"]
    disk_path = Path(config.get("disk_path", str(Path.home()))).expanduser()
    if disk_usage is not None:
        total, used, free = disk_usage
        disk = check_disk(thresholds["disk"], disk_path,
                          usage=SimpleNamespace(total=total, used=used, free=free))
    else:
        disk = check_disk(thresholds["disk"], disk_path)
    checks = [disk, check_memory(thresholds["memory"], memory_metrics),
              check_cpu(thresholds["cpu"], cpu_usage)]
    if include_hadoop:
        checks.extend(check_hadoop_services(config.get("hadoop", {})))
    timestamp = datetime.now(timezone.utc).isoformat()
    report = {"project": "Big Data Platform Health Monitor", "timestamp": timestamp,
              "host_os": platform.system(), "checks": checks,
              "overall_status": global_status(checks)}
    try:
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        append_incidents(incidents_path, checks, timestamp)
    except OSError as exc:
        raise MonitorError(f"Cannot write report or incident log: {exc}") from exc
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Check local host health for data platform operations.")
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--incidents", type=Path, default=DEFAULT_INCIDENTS)
    parser.add_argument("--hadoop", action="store_true", help="Run optional Hadoop CLI checks.")
    args = parser.parse_args(argv)
    try:
        report = run_monitor(args.config, args.report, args.incidents, include_hadoop=args.hadoop)
    except (MonitorError, OSError, ValueError) as exc:
        logging.error("Health monitor failed: %s", exc)
        return 1
    print("BIG DATA PLATFORM HEALTH MONITOR")
    for item in report["checks"]:
        usage = item.get("usage_percent")
        measure = f"{usage}%" if usage is not None else item.get("details", "")
        print(f"{item['component']}: {measure} - {item['status']}")
    print(f"Overall: {report['overall_status']}")
    print(f"Operating system: {report['host_os']}")
    print(f"Report saved to: {args.report}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
