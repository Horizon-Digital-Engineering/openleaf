# OpenLeaf High-Level Design

## System Philosophy

OpenLeaf follows a **data-centric architecture** where:
- The server is the single source of truth for vehicle state
- Clients are stateless viewers that can request specific data
- The transport layer intelligently manages data collection

## Core Design Principles

### 1. Minimize Bus Traffic
- **Passive First**: Listen to what the car broadcasts naturally
- **Query Sparingly**: Only request data that's actually needed
- **Cache Aggressively**: Don't re-query data that hasn't changed

### 2. Responsive User Experience
- **Instant Updates**: Display passive data immediately
- **Progressive Loading**: Show available data while fetching details
- **Context-Aware**: Load data relevant to current user context

### 3. Scalable Architecture
- **Multi-Client**: Support multiple UIs simultaneously
- **Protocol Agnostic**: Abstract away OBD2/CAN details
- **Extensible**: Easy to add new data sources or displays

## Data Categories

### Always Available (Passive)
Data that broadcasts continuously without queries:
- State of Charge (SOC)
- Vehicle Speed
- Battery Pack Voltage
- Odometer
- Charging Status

### On-Demand (Active)
Data that requires explicit queries:
- Individual Cell Voltages
- Detailed Temperature Readings
- Diagnostic Trouble Codes
- Historical Statistics
- System Configuration

### Hybrid
Data that may be passive or active depending on vehicle state:
- Charging Current (passive when charging, active otherwise)
- Motor RPM (passive when driving, active when parked)
- Climate Control Status

## Communication Layers

### Layer 1: Vehicle ↔ Adapter
- **Passive Mode**: Listen to CAN broadcasts
- **Active Mode**: Send OBD2 queries
- **Mixed Mode**: Alternate between passive and active

### Layer 2: Adapter ↔ Server
- **Connection Types**: BLE, Serial, WiFi
- **Protocol**: ELM327 AT commands
- **Flow Control**: Managed by transport implementation

### Layer 3: Server ↔ Client
- **REST API**: Simple request/response
- **State Endpoint**: Complete vehicle state
- **Control Endpoints**: Request specific data

### Future Layer 4: Real-time Updates
- **WebSocket**: Push updates to clients
- **Subscriptions**: Clients subscribe to specific data
- **Events**: Notify on significant changes

## State Management Strategy

### Server State Store
The server maintains:
- **Current Values**: Latest data from vehicle
- **Timestamps**: When each value was last updated
- **Metadata**: Data quality, source, reliability

### Client State
Clients maintain:
- **Display State**: What screen/view is active
- **User Preferences**: Units, refresh rates
- **Cached Data**: Recent server responses

### Data Freshness
- **Real-time**: < 100ms old (passive broadcasts)
- **Fresh**: < 1 second old (recent active query)
- **Cached**: < 10 seconds old (acceptable for most uses)
- **Stale**: > 10 seconds old (should refresh)

## Polling Strategies

### Strategy 1: Screen-Based Polling
- Server knows which screen client is displaying
- Actively polls PIDs relevant to that screen
- Stops polling when screen changes

### Strategy 2: Subscription-Based Polling
- Clients subscribe to specific data points
- Server polls based on active subscriptions
- Multiple clients can share subscriptions

### Strategy 3: Priority-Based Polling
- Critical data polled frequently
- Nice-to-have data polled rarely
- Adaptive based on system load

### Strategy 4: Event-Driven Polling
- Certain events trigger specific queries
- Example: Gear change triggers motor data query
- Example: Charging start triggers charger data query

## Optimization Opportunities

### Bus Utilization
- Target: < 20% bus utilization from queries
- Monitor passive frames: ~80% of data needs
- Strategic active queries: ~20% of data needs

### Response Times
- Dashboard data: < 100ms
- Detail screens: < 1 second
- Diagnostic data: < 5 seconds

### Battery Impact
- Minimize BLE connection time
- Batch queries when possible
- Use appropriate update intervals

## Failure Modes

### Connection Lost
- Server continues trying to reconnect
- Clients show last known state with timestamp
- Cached data marked as stale

### Partial Data
- Display available data immediately
- Show loading indicators for pending data
- Graceful degradation of features

### Bus Errors
- Retry with exponential backoff
- Fall back to passive-only mode
- Alert user to degraded functionality

## Extension Points

### New Data Sources
- LeafSpy Pro integration
- Direct CAN connection
- Cloud services API
- Simulation/playback

### New Clients
- Web dashboard
- Mobile app
- Home automation integration
- Data logging service

### New Vehicle Support
- Different Leaf generations
- Other EVs with OBD2
- Generic OBD2 vehicles

## Open Questions

1. **How to handle multiple simultaneous clients with different screen contexts?**
   - Option A: Union of all requested PIDs
   - Option B: Prioritize primary client
   - Option C: Round-robin between clients

2. **Should passive monitoring be continuous or periodic?**
   - Continuous: More data but higher power usage
   - Periodic: Less data but better battery life

3. **How long to cache expensive queries like cell voltages?**
   - Too short: Excessive bus traffic
   - Too long: Stale data on screen

4. **Should the server pre-fetch likely next screen data?**
   - Pro: Instant screen transitions
   - Con: Wasted queries if prediction wrong

5. **How to handle degraded adapter connections?**
   - Automatic fallback strategies?
   - User notification thresholds?

## Next Design Decisions

1. Define exact passive CAN IDs to monitor
2. Map UI screens to required PIDs
3. Set polling intervals and priorities
4. Design subscription API
5. Plan WebSocket upgrade path
6. Specify caching policies