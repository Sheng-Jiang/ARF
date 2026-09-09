import json
from datetime import date
from pathlib import Path

import pytest
import yaml

from arf.value_chain import compute_value_chain, load_value_chain_config


def test_load_value_chain_config_real_file():
    config_path = Path("config/value_chain.yaml")
    layers = load_value_chain_config(config_path)
    assert len(layers) == 5
    layer_ids = [layer_cfg["layer"] for layer_cfg in layers]
    assert layer_ids == ["L1", "L2", "L3", "L4", "L5"]
    for layer_cfg in layers:
        assert "name" in layer_cfg
        assert "US" in layer_cfg
        assert "China" in layer_cfg


def test_compute_value_chain_offline(tmp_path, monkeypatch):
    test_yaml = {
        "layers": [
            {
                "layer": "L1",
                "name": "L1 Energy",
                "US": [
                    {"name": "CompanyA", "ticker": "COMA", "source": "universe"},
                    {"name": "CompanyB", "ticker": "COMB", "source": "extra"},
                    {"name": "PrivateC", "static_usd_b": 10.0, "source": "static"},
                    {"name": "MissingD", "ticker": "MISS", "source": "universe"},
                ],
                "China": [
                    {"name": "ChinaCo", "ticker": "CHNA", "source": "universe"},
                ],
            }
        ]
    }
    cfg_file = tmp_path / "vc.yaml"
    cfg_file.write_text(yaml.dump(test_yaml), encoding="utf-8")

    # Mock _fetch_extra
    monkeypatch.setattr(
        "arf.value_chain._fetch_extra",
        lambda ticker, leg, as_of: 25.0 * 1e9 if ticker == "COMB" else None,
    )

    universe_market_caps = {
        "COMA": 50.0 * 1e9,
        "CHNA": 30.0 * 1e9,
        # MISS is omitted -> missing market cap
    }

    as_of = date(2026, 7, 19)
    rows = compute_value_chain(as_of, universe_market_caps, config_path=cfg_file)

    assert len(rows) == 2  # 1 layer * 2 legs (US, China)

    us_row = next(r for r in rows if r["leg"] == "US")
    assert us_row["layer"] == "L1"
    assert us_row["layer_name"] == "L1 Energy"
    # COMA (50B) + COMB (25B) + PrivateC (10B) = 85B; MissingD is excluded
    assert us_row["market_cap_usd"] == pytest.approx(85.0 * 1e9)

    constituents = json.loads(us_row["constituents_json"])
    assert len(constituents) == 3
    assert {c["name"] for c in constituents} == {"CompanyA", "CompanyB", "PrivateC"}

    china_row = next(r for r in rows if r["leg"] == "China")
    assert china_row["market_cap_usd"] == pytest.approx(30.0 * 1e9)


def test_compute_value_chain_unknown_source(tmp_path):
    test_yaml = {
        "layers": [
            {
                "layer": "L1",
                "name": "L1 Energy",
                "US": [
                    {"name": "BadCompany", "ticker": "BAD", "source": "invalid_source"},
                ],
                "China": [],
            }
        ]
    }
    cfg_file = tmp_path / "vc_bad.yaml"
    cfg_file.write_text(yaml.dump(test_yaml), encoding="utf-8")

    with pytest.raises(ValueError, match="Unknown source"):
        compute_value_chain(date(2026, 7, 19), {}, config_path=cfg_file)
