from core.utils import truthy_flag
from sources.goplus import _creator_malicious, _feature_enabled


def test_current_solana_status_objects_are_parsed() -> None:
    raw = {
        "freezable": {"authority": [], "status": "0"},
        "metadata_mutable": {
            "metadata_upgrade_authority": [{"address": "a", "malicious_address": 0}],
            "status": "1",
        },
        "transfer_hook": [],
        "transfer_fee_upgradable": {"authority": [{"address": "b"}], "status": "1"},
    }
    assert _feature_enabled(raw, ("freezable",)) is False
    assert _feature_enabled(raw, ("metadata_mutable",)) is True
    assert _feature_enabled(raw, ("transfer_hook",)) is False
    assert truthy_flag(raw["transfer_fee_upgradable"]) is True
    assert _creator_malicious(raw) is False
