"""replica_lag: how far the reporting database trails production, from a fake runner."""
from convscan.runner import replica_lag

COLS = ["replica", "caught_up", "since_last_replay_s"]


class Fake:
    def __init__(self, row=None, error=None):
        self.row, self.error = row, error

    def query(self, sql):
        if self.error:
            raise self.error
        return COLS, [self.row]


def test_caught_up_is_zero_even_on_a_quiet_site():
    assert replica_lag(Fake((True, True, 5000.0)))["lag_s"] == 0.0


def test_lagging():
    lag = replica_lag(Fake((True, False, 742.4)))
    assert lag["lag_s"] == 742.4 and "behind" in lag["note"]


def test_not_a_replica():
    assert replica_lag(Fake((False, None, None)))["lag_s"] == 0.0


def test_unknown_when_not_allowed():
    lag = replica_lag(Fake(error=RuntimeError("permission denied for function pg_last_wal_receive_lsn")))
    assert lag["lag_s"] is None and "permission denied" in lag["note"]


def test_archive_recovery_falls_back_to_replay_time():
    assert replica_lag(Fake((True, None, 90.0)))["lag_s"] == 90.0
