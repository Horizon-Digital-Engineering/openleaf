from __future__ import annotations

from openleaf.transports.synthetic import SyntheticTransport


def test_synthetic_transport_single_iteration() -> None:
    transport = SyntheticTransport(update_interval_sec=0.0)
    iterator = iter(transport.loop())
    update = next(iterator)

    expected_keys = {
        "soc_true",
        "soh",
        "pack_voltage",
        "pack_temp_c",
        "cell_delta_mv",
        "cell_voltages",
        "dtcs",
    }
    assert expected_keys.issubset(update.keys())
    assert isinstance(update["cell_voltages"], list)
    assert len(update["cell_voltages"]) == transport.cell_count
    for key, value in update.items():
        if key == "cell_voltages":
            continue
        if key == "dtcs":
            assert isinstance(value, list)
            continue
        assert isinstance(value, (int, float))
