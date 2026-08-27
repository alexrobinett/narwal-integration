def test_narwal_client_imports_without_home_assistant():
    from narwal_client import NarwalState, WorkingStatus  # noqa: F401
    assert WorkingStatus.CLEANING.value == 4
