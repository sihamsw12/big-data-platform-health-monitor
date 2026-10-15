# Big Data Platform Health Monitor

A Python command-line tool that records disk, memory and CPU usage on the machine where it runs. It compares those measurements with configurable thresholds, writes a JSON report and appends non-healthy checks to a local incident log.

The standard run checks the local host. It does not connect to Cloudera or a Hadoop cluster.

## Requirements and installation

- Python 3.10 or newer
- `psutil` for local memory and CPU metrics
- `pytest` to run the test suite
- Hadoop command-line clients only if using the optional Hadoop checks

On macOS or Linux, create and activate a virtual environment, then install the dependencies:

```sh
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m pip install pytest
```

## Run locally

Run from the project root:

```sh
python monitor.py
```

The command samples CPU usage over one second. Disk usage is measured for the filesystem containing `disk_path` in `config.json` (`~` means the current user's home directory). Memory and CPU measurements come from `psutil`.

`config.json` sets warning and critical percentages for each resource. A measurement at or above the critical threshold is `CRITICAL`; at or above warning it is `WARNING`; otherwise it is `HEALTHY`. The overall status is the most severe status among the checks.

Each run replaces `reports/health-report.json` with a snapshot containing a UTC timestamp, operating system, measurements and statuses. Non-healthy findings are appended to `reports/incidents.jsonl`, preserving prior entries. A successful run exits with code 0 even when a check reports WARNING or CRITICAL. Configuration and output errors are printed and return a non-zero exit code.

Paths can be supplied on the command line:

```sh
python monitor.py --config config.json --report reports/health-report.json --incidents reports/incidents.jsonl
```

## Optional Hadoop CLI checks

Pass `--hadoop` to run these additional commands:

```sh
python monitor.py --hadoop
```

- HDFS: `hdfs dfsadmin -report`
- YARN: `yarn node -list -all`

The commands must be installed and configured in the environment. A missing CLI produces a WARNING and is not treated as a successful check. A command error or timeout produces CRITICAL. A successful exit only confirms that the command ran successfully; it is not a complete assessment of cluster health.

This project does not currently check Hive or Impala and has not been tested against a Cloudera cluster. Connecting those services would require separate, documented API or client checks and target-specific authentication and configuration. No credentials or cluster endpoints are included here.

## Tests

Install pytest as shown above, then run:

```sh
python3 -m pytest -q
```

Tests inject CPU, memory and disk values, so their status assertions do not depend on the machine's current CPU or memory load. Hadoop command checks are optional and are not part of these local metric tests.

## Limitations

- This is a one-shot local snapshot tool, not a background service, alerting system or time-series store.
- Container limits and operating-system filesystem semantics may affect how resource metrics should be interpreted.
- Incident history is stored locally and has no rotation or retention policy.

Possible next steps include log retention, alerts, historical storage and separately tested checks for Hive, Impala or Cloudera Manager.
