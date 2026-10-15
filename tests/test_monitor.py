import json
from types import SimpleNamespace

import pytest

from monitor import MonitorError, load_config, run_monitor, status_for


@pytest.fixture
def config_file(tmp_path):
    config = {
        "thresholds": {
            "disk": {"warning": 75, "critical": 90},
            "memory": {"warning": 75, "critical": 90},
            "cpu": {"warning": 75, "critical": 90},
        },
        "disk_path": str(tmp_path),
    }
    path = tmp_path / "config.json"
    path.write_text(json.dumps(config), encoding="utf-8")
    return path


def test_status_thresholds():
    thresholds = {"warning": 75, "critical": 90}
    assert status_for(40, thresholds) == "HEALTHY"
    assert status_for(75, thresholds) == "WARNING"
    assert status_for(90, thresholds) == "CRITICAL"


@pytest.mark.parametrize(
    ("cpu", "expected"),
    [(20, "HEALTHY"), (80, "WARNING"), (95, "CRITICAL")],
)
def test_report_status_and_incident_history(config_file, tmp_path, cpu, expected):
    report_path = tmp_path / "reports" / "health.json"
    incident_path = tmp_path / "reports" / "incidents.jsonl"
    metrics = SimpleNamespace(percent=20.0, total=8 * 1024**3, available=6 * 1024**3)
    report = run_monitor(
        config_file,
        report_path,
        incident_path,
        cpu_usage=cpu,
        memory_metrics=metrics,
        disk_usage=(100, 20, 80),
    )
    assert report["checks"][-1]["status"] == expected
    assert report["overall_status"] == expected
    assert json.loads(report_path.read_text()) == report
    if expected != "HEALTHY":
        assert len(incident_path.read_text().splitlines()) == 1


def test_incident_log_appends(config_file, tmp_path):
    log = tmp_path / "incidents.jsonl"
    metrics = SimpleNamespace(percent=96.0, total=100, available=4)
    for _ in range(2):
        run_monitor(
            config_file,
            tmp_path / "report.json",
            log,
            cpu_usage=10,
            memory_metrics=metrics,
            disk_usage=(100, 20, 80),
        )
    assert len(log.read_text().splitlines()) == 2


def test_invalid_thresholds_are_rejected(tmp_path):
    path = tmp_path / "bad.json"
    path.write_text(json.dumps({"thresholds": {"disk": {"warning": 90, "critical": 80}}}))
    with pytest.raises(MonitorError, match="must satisfy"):
        load_config(path)


def test_missing_config_is_actionable(tmp_path):
    with pytest.raises(MonitorError, match="not found"):
        load_config(tmp_path / "missing.json")
