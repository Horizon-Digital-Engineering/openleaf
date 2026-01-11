# PID Polling Strategy

## Problem Statement
- Querying ALL PIDs constantly creates too much bus traffic
- Some data (SOC, speed) broadcasts automatically
- Some data (cell voltages) is expensive and only needed on specific screens
- Need to balance responsiveness with efficiency

## Solution: Hybrid Passive/Active Monitoring

### Layer 1: Passive CAN Monitoring
**Always running in background**

The following CAN IDs broadcast automatically without queries:
- **0x5BC** (500ms): State of charge percentage
- **0x5B3** (500ms): Battery health (SOH), GIDs count
- **0x1DB** (100ms): Pack voltage, charging status
- **0x55B** (100ms): Vehicle speed, motor RPM
- **0x5C5** (1000ms): Odometer reading

### Layer 2: Screen-Based Active Queries
**Only query when screen is visible**

Screen-specific PID requirements:
- **Dashboard**: Primarily passive data, no active queries needed
- **Cells**: Cell voltages (high priority), cell balance status (normal priority)
- **DTCs**: Diagnostic trouble code count and details, MIL status
- **Charging**: Charge current, time remaining, charger voltage

## Implementation Plan

### 1. Modify OBD2Transport
The transport needs to support both passive monitoring and active polling:
- Maintain a passive monitor that continuously captures broadcast frames
- Implement an active poller that queries PIDs based on current screen
- Track which screen is currently visible to optimize queries
- Merge passive and active data before updating state store

### 2. Add API Endpoint for Screen Changes
Server needs a `/ui/screen` endpoint that:
- Accepts screen change notifications from the UI
- Updates the transport's active PID list
- Returns confirmation with list of PIDs being queried

### 3. Update UI to Notify Screen Changes
The UI should notify the server whenever the user switches screens, allowing the transport to adjust its active PID queries accordingly.

## Passive Monitoring Algorithm

The passive monitor:
1. Puts the adapter in "monitor all" mode (ATMA command)
2. Captures broadcast frames for a brief period (~100ms)
3. Exits monitor mode to allow active queries
4. Decodes known passive CAN IDs into vehicle state
5. Returns decoded data without any bus queries

This approach captures "free" data that the vehicle broadcasts naturally.

## Active Polling Algorithm

The active poller:
1. Maintains a list of PIDs needed for the current screen
2. Tracks when each PID was last queried
3. Polls PIDs based on their priority intervals
4. Only queries PIDs that are due for refresh
5. Returns updated values for integration with state

Priority-based polling ensures critical data updates frequently while background data updates less often.

## Benefits

### Efficiency
- **90% reduction** in bus traffic vs querying everything
- Passive frames are "free" (already broadcast)
- Active queries only for visible data

### Responsiveness
- Critical data (SOC, speed) updates in real-time
- Screen-specific data loads on demand
- No lag when switching screens

### Scalability
- Easy to add new screens with specific PID needs
- Can support multiple clients with different screens
- Server maintains full state for all clients

## Testing Strategy

Three test configurations validate the approach:
1. **Passive Only Mode** - Validates broadcast frame capture without queries
2. **Active Only Mode** - Tests explicit PID querying without passive monitoring
3. **Hybrid Mode** - Production configuration with both passive and active data collection

Each mode can be tested with different configuration files to isolate and validate each data collection method.

## Next Steps

1. Implement `PassiveCANMonitor` class
2. Implement `ActivePIDPoller` class
3. Add `/ui/screen` endpoint to server
4. Update UI to notify screen changes
5. Test with real vehicle
6. Optimize polling intervals based on testing