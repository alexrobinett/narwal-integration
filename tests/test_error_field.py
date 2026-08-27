from narwal_client.const import RobotActivity as A
from narwal_client.models import NarwalState
from tests.fixtures import zultra_payloads as P


def test_error_block_is_decoded_on_zultra():
    s = NarwalState(profile="zultra")
    s.activity = A.CLEANING
    s.update_base_status(P.PAUSED_ON_DOCK_WITH_ERROR)
    assert s.error_code == 0x01010036
    assert s.error_message == "station sewage tank is abnormal when washing mop"


def test_error_clears_on_healthy_frame():
    s = NarwalState(profile="zultra")
    s.update_base_status(P.PAUSED_ON_DOCK_WITH_ERROR)
    s.update_base_status(P.COMBO_CLEANING)
    assert s.error_code is None and s.error_message is None


def test_legacy_profile_ignores_error_block():
    s = NarwalState()
    s.update_base_status(P.PAUSED_ON_DOCK_WITH_ERROR)
    assert s.error_code is None and s.error_message is None


def test_error_block_without_reason_line_uses_full_text():
    # hand-built field 1: {1: 5, 3: "boom"} (field 3 is the plain text, as in
    # the capture; the brief's `{1: text}` sub-message does not match it),
    # followed by field 3 = {1: 4}
    s = NarwalState(profile="zultra")
    s.update_base_status(bytes.fromhex("0a08" + "0805" + "1a04" + "626f6f6d") + bytes.fromhex("1a020804"))
    assert s.error_code == 5 and s.error_message == "boom"
