# OpenLeaf System Architecture

## Overview

OpenLeaf uses a client-server architecture where:
- **Server** - Manages OBD2 connection, collects data, maintains vehicle state
- **Clients** - UI applications that display data and can request specific information

## Core Components

### 1. Server (FastAPI)
```
┌─────────────────────────────────────────┐
│            FastAPI Server               │
│  ┌─────────────────────────────────┐    │
│  │      State Store (singleton)     │    │
│  │  - Current vehicle state         │    │
│  │  - Timestamp of last update      │    │
│  │  - History buffer (optional)     │    │
│  └─────────────────────────────────┘    │
│                  ▲                       │
│                  │                       │
│  ┌─────────────────────────────────┐    │
│  │     Transport (OBD2/BLE/etc)    │    │
│  │  - Passive PID monitoring       │    │
│  │  - Active PID querying          │    │
│  │  - Connection management         │    │
│  └─────────────────────────────────┘    │
└─────────────────────────────────────────┘
```

### 2. Client (UI)
```
┌─────────────────────────────────────────┐
│              Kivy UI                    │
│  ┌─────────────────────────────────┐    │
│  │         Screen Manager          │    │
│  │  - Dashboard (basic PIDs)       │    │
│  │  - Cells (cell voltage PIDs)    │    │
│  │  - DTCs (diagnostic PIDs)       │    │
│  │  - Debug (system info)          │    │
│  └─────────────────────────────────┘    │
│                  │                       │
│                  ▼                       │
│  ┌─────────────────────────────────┐    │
│  │         API Client               │    │
│  │  - Polls /state endpoint        │    │
│  │  - Sends PID requests           │    │
│  │  - Manages connection            │    │
│  └─────────────────────────────────┘    │
└─────────────────────────────────────────┘
```

## PID Handling Strategy

### Passive PIDs (Always Monitored)
These are broadcast automatically on the CAN bus without queries:

```yaml
passive_pids:
  - 0x5BC: SOC%           # State of charge (every 500ms)
  - 0x5B3: SOH%, GIDs     # Battery health (every 500ms)
  - 0x1DB: Pack voltage   # Charging status (every 100ms)
  - 0x55B: Speed          # Vehicle speed (every 100ms)
  - 0x5C5: Odometer       # Total distance (every 1000ms)
```

**Implementation:**
- Transport puts adapter in `ATMA` (monitor all) mode periodically
- Captures all broadcast frames
- Decodes known passive PIDs automatically
- Updates state store with latest values

### Active PIDs (Query on Demand)
These must be explicitly requested via OBD2 queries:

```yaml
active_pids:
  dashboard:
    - pack_temp       # Battery temperature
    - motor_rpm       # Motor speed
    - power_kw        # Power consumption

  cells_screen:
    - cell_voltages   # All 96 cell voltages (expensive!)
    - cell_temps      # Temperature sensors

  dtc_screen:
    - dtc_list        # Diagnostic trouble codes
    - dtc_details     # Extended DTC information
```

## Communication Flow

### 1. Passive Monitoring (Continuous)
```
Vehicle ──broadcasts──> OBD2 Adapter ──BLE──> Server ──updates──> State Store
```

### 2. UI State Polling (Every 500ms)
```
UI ──GET /state──> Server ──returns──> Current State Store
```

### 3. Active PID Request (Screen-based)
```
UI ──POST /request_pids──> Server ──queries──> OBD2 ──updates──> State Store
   {"pids": ["cell_voltages"]}
```

## API Endpoints

### Core Endpoints
- **GET /health** - Server health and connection status
- **GET /state** - Complete vehicle state snapshot
- **GET /state/{category}** - Filtered state by category (battery, motor, charging, etc.)

### PID Control Endpoints
- **POST /pids/request** - Request specific PIDs be actively queried for a duration
- **POST /pids/subscribe** - Subscribe client to continuous updates for specific PIDs
- **POST /pids/unsubscribe** - Unsubscribe client from PID updates
- **GET /pids/active** - List currently active PID subscriptions
- **GET /pids/available** - List all PIDs the system can query

### DTC Endpoints
- **GET /dtcs** - Read DTCs from all ECUs (returns per-ECU results)
- **POST /command/clear_dtcs** - Clear DTCs from all ECUs

### Command Endpoints
- **POST /command/reset** - Reset adapter connection

## Transport Implementation

### OBD2Transport Loop
The transport layer operates in a continuous loop that:
1. **Monitors passive PIDs** - Captures broadcast CAN frames (fast, ~100ms)
2. **Queries active PIDs** - Polls PIDs based on screen needs and subscriptions
3. **Updates state store** - Merges passive and active data
4. **Manages requests** - Processes new PID requests from clients

### Passive Monitoring Strategy
The adapter enters monitor mode briefly to capture all broadcast frames on the CAN bus. This provides "free" data without queries, including SOC, speed, and charging status. The monitor duration is kept short (~100ms) to balance data freshness with bus availability for active queries.

## UI Screen → PID Mapping

Each UI screen has different data requirements:

- **Dashboard**: Primarily uses passive data (SOC, speed, voltage) with minimal active queries
- **Cells**: Requires expensive cell voltage queries when visible
- **DTCs**: Needs diagnostic queries for trouble codes and status
- **Charging**: Mix of passive charging status and active charger details

## State Store Architecture

The centralized state store maintains:
- **Current Values**: Latest data from passive monitoring and active queries
- **Timestamps**: When each value was last updated for freshness tracking
- **Metadata**: Active PID subscriptions, connection status, and data quality indicators

Data freshness categories:
- **Real-time**: < 100ms old (passive broadcasts)
- **Fresh**: < 1 second old (recent active query)
- **Cached**: < 10 seconds old (acceptable for most displays)
- **Stale**: > 10 seconds old (should refresh)

## Optimization Strategies

### 1. Hybrid Monitoring
- **80% Passive**: Monitor CAN bus for broadcasts (no queries)
- **20% Active**: Query only what the current UI screen needs

### 2. Smart Caching
- Cache expensive queries (like cell voltages) for 5-10 seconds
- Return cached data if age < threshold
- Background refresh based on screen visibility

### 3. Priority Queuing
PIDs are assigned priorities based on importance:
- **Critical**: Safety-related data (100ms intervals)
- **High**: Current screen data (500ms intervals)
- **Normal**: Background updates (2 second intervals)
- **Low**: Nice-to-have data (10 second intervals)

### 4. Adaptive Polling
- Increase poll rate when values are changing
- Decrease poll rate when values are stable
- Stop polling PIDs not viewed for >30 seconds

## Benefits of This Architecture

1. **Efficient**: Passive monitoring reduces bus traffic
2. **Responsive**: Active queries for current screen
3. **Scalable**: Multiple clients can connect
4. **Flexible**: Easy to add new PIDs or screens
5. **Robust**: Server maintains state even if UI disconnects
6. **Smart**: Only queries what's needed when it's needed

## Future Enhancements

1. **WebSocket Support**: Real-time updates instead of polling
2. **Historical Data**: Store time-series data in database
3. **Predictive Loading**: Pre-fetch PIDs for likely next screen
4. **Batch Queries**: Combine multiple PID requests
5. **Compression**: Reduce bandwidth for remote clients
6. **Multi-Vehicle**: Support multiple simultaneous connections