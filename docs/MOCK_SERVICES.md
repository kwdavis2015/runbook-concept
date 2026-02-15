# Mock Services

## Purpose

Mock services allow anyone to run and evaluate Runbook Concept without access to real infrastructure or API credentials. They provide realistic, scenario-driven responses that demonstrate the full diagnostic workflow.

## How Mocks Work

Each mock provider loads data from JSON fixture files in `integrations/mock/fixtures/`. Mocks are not random — they follow **scripted scenarios** that tell a coherent troubleshooting story.

### Scenario-Based Design

Rather than returning random data, mocks are organized around complete incident scenarios. Each scenario includes all the data every integration would return for that specific problem:

```
fixtures/scenarios/high_cpu.json
{
  "scenario": "high_cpu_web_server",
  "description": "Production web server CPU spike caused by memory leak after deploy",

  "servicenow": {
    "incident": { "number": "INC0012345", "short_description": "High CPU on prod-web-03", ... },
    "recent_changes": [ { "number": "CHG0004567", "description": "Deploy v2.14.3", ... } ]
  },

  "datadog": {
    "alerts": [ { "name": "High CPU Alert", "host": "prod-web-03", "value": 94.2, ... } ],
    "metrics": { "cpu": [ { "timestamp": "...", "value": 94.2 }, ... ] },
    "logs": [ { "message": "OOM killer invoked for process java", ... } ]
  },

  "pagerduty": {
    "incident": { "id": "P1234", "status": "triggered", "urgency": "high", ... },
    "on_call": { "user": "Jane Smith", "schedule": "Primary On-Call" }
  },

  "aws": {
    "instance": { "id": "i-0abc123", "type": "c5.xlarge", "state": "running", ... },
    "top_processes": [ { "pid": 12345, "name": "java", "cpu_percent": 89.3, ... } ]
  }
}
```

### Active Scenario Selection

The mock system supports switching between scenarios via the UI settings page or environment variable:

```env
MOCK_SCENARIO=high_cpu          # default scenario
# Options: high_cpu, database_connection, deployment_failure, network_latency
```

## Available Scenarios

### 1. High CPU on Production Server (`high_cpu`)

**Story:** A recent deployment (v2.14.3) introduced a memory leak in the Java application on `prod-web-03`. CPU spikes to 94%, the OOM killer starts firing, and response times degrade.

**Diagnostic path the app should follow:**
1. Detect high CPU alert from monitoring
2. Identify Java process consuming 89% CPU
3. Find recent deployment CHG0004567 from 2 hours ago
4. Correlate CPU spike timing with deployment
5. Recommend: rollback deployment or restart service
6. On approval: execute service restart
7. Verify CPU returns to normal

### 2. Database Connection Exhaustion (`database_connection`)

**Story:** The connection pool on `db-primary-01` is exhausted. Application servers are throwing "too many connections" errors. Root cause: a new microservice was deployed without connection pooling configured.

**Diagnostic path:**
1. Detect database alert — connections at 100% capacity
2. Query active connections — identify source application
3. Find recent deployment of the offending service
4. Recommend: increase pool size temporarily + fix connection pooling config
5. On approval: execute config change
6. Verify connections drop to normal

### 3. Failed Deployment (`deployment_failure`)

**Story:** A deployment of `checkout-service` v3.1.0 failed mid-rollout. 3 of 8 instances are running the new version, 5 are still on v3.0.9. Health checks are failing on new instances.

**Diagnostic path:**
1. Detect deployment failure alert
2. Check instance health across fleet
3. Examine logs from failing instances
4. Identify missing environment variable in new version
5. Recommend: rollback to v3.0.9
6. On approval: execute rollback
7. Verify all instances healthy

### 4. Cross-Region Network Latency (`network_latency`)

**Story:** Users in EU region experiencing 3x normal latency. The CDN configuration was changed, routing EU traffic through US-East instead of EU-West.

**Diagnostic path:**
1. Detect latency alert for EU region
2. Check network metrics — confirm EU-specific issue
3. Query CDN configuration — find recent change
4. Identify misconfigured routing rule
5. Recommend: revert CDN configuration
6. On approval: execute config revert
7. Verify latency returns to baseline

## Mock Response Timing

Mocks include configurable artificial delays to simulate real API call latency:

```python
MOCK_DELAYS = {
    "servicenow": 0.5,   # seconds
    "datadog": 0.3,
    "pagerduty": 0.2,
    "aws": 0.4,
    "slack": 0.1,
}
```

Set `MOCK_DELAY_ENABLED=false` to disable delays for faster testing.

## Extending Mocks

To add a new scenario:

1. Create `fixtures/scenarios/your_scenario.json` following the schema above
2. Add the scenario key to `AVAILABLE_SCENARIOS` in mock config
3. The mock providers will automatically pick up the new fixture data
