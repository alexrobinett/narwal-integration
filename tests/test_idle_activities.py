from narwal_client.const import IDLE_ACTIVITIES, RobotActivity


def test_idle_activities_members():
    assert IDLE_ACTIVITIES == frozenset({
        RobotActivity.SLEEPING, RobotActivity.DOCKED, RobotActivity.CHARGING,
    })
