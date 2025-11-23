# Nissan Leaf OBD2 and CAN Bus Summary

This document provides a comprehensive overview of how the Nissan Leaf communicates over its OBD-II and CAN networks. It is designed to support the development of a flexible, lightweight diagnostics and telemetry display system using open-source tools. This guide introduces CAN bus access, differentiates between passive and active data collection, and outlines a modular architecture for decoding and visualizing EV data.

---

## OBD-II Connector & CAN Bus Access

The Leaf’s standard 16-pin OBD-II connector provides access to multiple CAN buses used by different subsystems:

| CAN Bus  | Pins     | Description                            |
|----------|----------|----------------------------------------|
| Car-CAN  | 6 / 14   | Primary vehicle systems (VCM, etc.)    |
| EV-CAN   | 12 / 13  | EV-specific systems (battery, charger) |
| AV-CAN   | 3 / 11   | Telematics, infotainment               |

Most commercial Bluetooth adapters such as ELM327 devices interface only with **Car-CAN** by default. Gaining access to **EV-CAN** often requires hardware mods (re-pinning) or professional CAN interfaces (USB-CAN, MCP2515, etc.).

However, **most useful diagnostic data for battery health, charging state, temperatures, and driving performance is available over Car-CAN**, eliminating the need for additional connections in typical applications.

---

## Types of Data Access

### 1. Broadcast CAN Frames (Passive Listening)

Many ECUs periodically broadcast messages without needing to be polled. These are easy to capture using tools like ELM327 in monitoring mode (`ATMA`) or SocketCAN sniffing.

| CAN ID  | Contents                         |
|---------|----------------------------------|
| 0x5B3   | Battery SoH, GIDs, capacity      |
| 0x5BC   | State of Charge (SoC %)         |
| 0x5C5   | Odometer                         |
| 0x1DB   | Charging state & voltage         |

Passive monitoring is efficient and non-intrusive but limited to broadcasted information.

### 2. Diagnostic Queries (Active Polling)

Some advanced data—such as individual battery cell voltages, DTCs, or internal ECU parameters—requires initiating communication with specific control units using diagnostic protocols (ISO-TP, UDS, or proprietary extensions).

| ECU     | Request ID | Response ID | Function            |
|---------|------------|-------------|---------------------|
| LBC     | 0x79B      | 0x7BB       | Battery Controller  |
| VCM     | 0x797      | 0x79A       | Vehicle Control     |
| TCU     | 0x743      | 0x763       | Telematics Control  |

These require flow-controlled sessions. A typical interaction might look like:
```
> 02 21 04              # Request battery temperature
< 10 10 61 04 ...       # Multi-frame ISO-TP response
```

---

## System Design Strategy

To enable modularity and adaptability, the architecture separates data transport, decoding, and display layers:

- **Input interfaces**: Bluetooth (ELM327), USB-CAN, simulated log replay
- **Data definitions**: YAML/JSON schemas describing message formats
- **Output**: GUI or logging system to show/record decoded values

### Example YAML definition
```yaml
id: 0x5B3
name: Battery Status
fields:
  - name: SOH
    offset: 2
    length: 1
    scale: 0.5
  - name: GIDs
    offset: 4
    length: 1
```
This model enables rapid development, testability, and portability.

---

## Modes of Operation

The system can be run in multiple modes:

- **Live Data**: Stream from a real vehicle via Bluetooth or USB-CAN
- **Replay**: Load previously recorded log files for UI and decoding testing
- **Emulation**: Feed synthetic data for mock testing or development demos

Each mode uses the same decoding layer, ensuring consistent behavior.

---

## Development Considerations

- **Start with passive sniffing**: Validate wiring, observe traffic, and confirm adapter functionality without sending traffic
- **Build decoding incrementally**: Add YAML definitions as new signals are discovered
- **Prioritize Car-CAN access**: It contains most of the useful metrics
- **Use log replay to test the stack** without needing to be in the vehicle
- **Modularize transport layers** so different sources can be swapped easily

### Direct CAN Access vs. OBD-II Adapter
For many projects, staying with standard ELM327-based access to the **Car-CAN** is sufficient. It avoids hardware complexity and covers nearly all metrics desired for:

- Displaying SoC, GIDs, SOH
- Logging charge/discharge rates
- Battery temperature and voltage summaries
- Detecting DTCs

Direct access to EV-CAN is valuable only when seeking:

- More granular or high-frequency data
- Data not exposed on Car-CAN (e.g., raw cell voltages for all cells)
- Full custom integration (e.g., automation, aftermarket control)

Otherwise, diagnostic query support and replayable logs will meet most user and developer needs.

---

## Further Reading & Resources

- [Nissan Leaf CAN Wiki (GitHub)](https://github.com/dalathegreat/Nissan-Leaf-CAN-Bus/wiki)
- [Open Vehicles Leaf Module](https://github.com/openvehicles/Open-Vehicle-Monitoring-System-3)
- [ELM327 Command Reference PDF](https://www.elmelectronics.com/wp-content/uploads/2021/06/ELM327DS.pdf)
- [SocketCAN Introduction (Linux)](https://man7.org/linux/man-pages/man7/can.7.html)
- [CAN Decoder Tools](https://github.com/commaai/can-dbc)

---
This reference document helps contributors and users understand how the system operates across input modes, what information is available, and why certain hardware paths are optional vs. required. It's aimed at supporting fast development, effective debugging, and future extensibility.

