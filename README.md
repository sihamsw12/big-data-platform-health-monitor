# Big Data Platform Health Monitor

A small Python command-line tool for checking host resources that support data platform workloads. It reports disk, memory and CPU utilization with configurable thresholds, writes a JSON snapshot, and appends non-healthy findings to an incident history. The default checks inspect the local machine only; they do not imply a connection to Cloudera.

## Architecture

- `monitor.py` validates configuration, gathers local metrics, determines component and overall health, and writes reports.
- `hadoop_checks.py` optionally invokes installed Hadoop command-line clients for real HDFS and YARN checks.
- `config.json` contains percentage thresholds and the local filesystem path to inspect.
- `reports/health-report.json` is the latest snapshot; `reports/incidents.jsonl` is an append-only JSON Lines incident history.

## Requirements

- Python 3.10 or newer
- `psutil` (the only runtime dependency; used for portable memory and CPU metrics)
- `pytest` for the automated test suite
- Hadoop clients are optional and only needed for `--hadoop`

## Installation

### macOS

```sh
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m pip install pytest
```

### Linux

```sh
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m pip install pytest
```

## Run

Run from the repository root:

```sh
python monitor.py
```

The command exits with status 0 when it successfully completes, even if the host is in WARNING or CRITICAL health. Configuration or report-writing failures print an actionable error and exit non-zero.

Use custom paths when useful:

```sh
python monitor.py --config config.json --report reports/health-report.json --incidents reports/incidents.jsonl
```

The latest JSON report includes a UTC timestamp, operating system, per-component measurements and states, and `overall_status`. Each non-HEALTHY check creates one incident entry containing timestamp, component, severity and description. Existing incident entries are preserved.

## Thresholds

Thresholds are percentages in `config.json`. The warning value must be lower than the critical value, both between 0 and 100. Values at or above critical are CRITICAL; values at or above warning are WARNING.

```json
"thresholds": {
  "disk": {"warning": 75, "critical": 90},
  "memory": {"warning": 75, "critical": 90},
  "cpu": {"warning": 75, "critical": 90}
}
```

The disk check measures the filesystem containing `disk_path`; `~` selects the current user's home filesystem. CPU is sampled over one second through `psutil`.

## Optional Hadoop checks

If Hadoop CLI tools are installed and configured in the environment, opt in explicitly:

```sh
python monitor.py --hadoop
```

This invokes `hdfs dfsadmin -report` and `yarn node -list -all`, with a configurable timeout (`hadoop.timeout_seconds`). A missing CLI is reported as WARNING and is not simulated as a successful connection. A non-zero command result or timeout is reported as CRITICAL. Output is limited to a short diagnostic excerpt. These checks validate command execution, not comprehensive cluster health.

HDFS and YARN checks can be extended with documented Hadoop APIs or Cloudera Manager's documented API, using externally managed authentication and TLS. Hive and Impala could be checked through documented clients or service APIs, with connection settings supplied outside source control. Such integrations require target-specific configuration and credentials; this project does not currently implement them or claim to have tested them. Production monitoring should also cover service-specific health, capacity, replication, queues, query failures, alerting and access controls.

## Tests

Install pytest as above and run:

```sh
python -m pytest -q
```

Tests inject CPU, memory and disk metrics, so health-state assertions do not depend on the test machine's live CPU or memory load.

## Limitations

- This is a single-host snapshot tool, not a daemon, time-series store or alerting system.
- `psutil` reports operating-system metrics; container limits and platform-specific filesystem semantics can affect interpretation.
- Optional Hadoop CLI checks need a correctly configured client environment and network/authentication access. A successful command alone does not establish end-to-end service health.
- The latest report is overwritten on each run. Incident history is appended locally and has no rotation policy.

## Future improvements

- Add structured checks for Hive, Impala and Cloudera Manager APIs with secure external credential handling.
- Add log rotation, retention controls, alert delivery and historical trend storage.
- Add service-specific thresholds and deployment examples for scheduled execution.
