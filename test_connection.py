#!/usr/bin/env python3
"""Test script to verify OBD2 connection and PID queries without UI."""

import json
import logging
import sys
import time
from pathlib import Path
from typing import Any, Dict, Set

# Setup logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

from openleaf.config import load_config
from openleaf.state import LeafState
from openleaf.transports.obd2_unified import OBD2Transport

def main():
    """Test OBD2 connection and query a few PIDs."""

    # Load config
    config_path = Path("configs/leaf_2013_24kwh.yaml")
    if not config_path.exists():
        print(f"❌ Config not found: {config_path}")
        sys.exit(1)

    print(f"📄 Loading config from {config_path}")
    config = load_config(config_path)

    # Create transport
    print(f"🔌 Creating OBD2 transport...")
    transport = OBD2Transport(**config["transport"])

    print(f"✅ Loaded {len(transport.pids)} PID definitions")
    print(f"\nPIDs to query:")
    for pid in transport.pids:
        signals_list = ", ".join([s.key for s in pid.signals])
        print(f"  - {pid.name} (interval: {pid.poll_interval_sec}s)")
        print(f"    Signals: {signals_list}")

    # Track which fields get populated
    fields_populated: Set[str] = set()
    all_data_samples: list = []

    # Get all possible field names from LeafState
    expected_fields = set(LeafState.__dataclass_fields__.keys())

    print(f"\n🚗 Starting connection loop...")
    print(f"   (Press Ctrl+C to stop)")
    print(f"="*60)

    try:
        iteration = 0
        start_time = time.time()

        for state in transport.loop():
            iteration += 1

            # Print connection status
            if "_transport" in state:
                connected = state["_transport"].get("connected", False)
                status = "🟢 CONNECTED" if connected else "🔴 DISCONNECTED"
                print(f"\n[Iteration {iteration}] {status}")

                if "error" in state["_transport"]:
                    print(f"   Error: {state['_transport']['error']}")

            # Extract data (excluding metadata)
            data_keys = [k for k in state.keys() if not k.startswith("_")]

            if data_keys:
                print(f"   Data received: {len(data_keys)} values")
                for key in data_keys:
                    value = state[key]

                    # Track which fields got populated
                    if _is_populated(value):
                        fields_populated.add(key)
                        print(f"      ✅ {key}: {value}")
                    else:
                        print(f"      ⚪ {key}: {value} (empty)")

                # Save sample
                all_data_samples.append({
                    "iteration": iteration,
                    "timestamp": time.time() - start_time,
                    "data": {k: state[k] for k in data_keys}
                })
            else:
                print(f"   No data yet (still initializing or polling)")

            # Run for 10 iterations or 30 seconds, whichever comes first
            if iteration >= 10 or (time.time() - start_time) > 30:
                print(f"\n✅ Test complete! Stopping after {iteration} iterations.")
                break

    except KeyboardInterrupt:
        print(f"\n\n⚠️  Interrupted by user")
    except Exception as e:
        print(f"\n\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        print(f"\n👋 Shutting down...")

        # Print summary
        print(f"\n" + "="*60)
        print(f"📊 VALIDATION SUMMARY")
        print(f"="*60)
        print(f"\n✅ Fields that got data ({len(fields_populated)}):")
        for field in sorted(fields_populated):
            print(f"   - {field}")

        fields_not_populated = expected_fields - fields_populated - {"dtcs"}  # Exclude dtcs (not queried)
        if fields_not_populated:
            print(f"\n❌ Fields with no data ({len(fields_not_populated)}):")
            for field in sorted(fields_not_populated):
                print(f"   - {field}")

        # Save results to JSON
        results_path = Path("test_results.json")
        results = {
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "config": str(config_path),
            "iterations": iteration,
            "fields_populated": sorted(list(fields_populated)),
            "fields_not_populated": sorted(list(fields_not_populated)),
            "samples": all_data_samples,
        }

        with open(results_path, "w") as f:
            json.dump(results, f, indent=2)

        print(f"\n💾 Results saved to {results_path}")
        print(f"\n📈 Success rate: {len(fields_populated)}/{len(expected_fields)} fields ({len(fields_populated)/len(expected_fields)*100:.1f}%)")


def _is_populated(value: Any) -> bool:
    """Check if a value is considered 'populated' (non-default)."""
    if isinstance(value, (int, float)):
        return value != 0.0
    elif isinstance(value, list):
        return len(value) > 0
    elif isinstance(value, str):
        return len(value) > 0
    return value is not None


if __name__ == "__main__":
    main()
