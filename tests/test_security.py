from clinic_queue.security import LoginLimiter, hash_pin, verify_pin


def test_correct_pin_verifies():
    assert verify_pin("4821", hash_pin("4821"))


def test_wrong_pin_fails():
    assert not verify_pin("4822", hash_pin("4821"))


def test_same_pin_hashes_differently_each_time():
    # A random salt per hash means equal PINs don't produce equal hashes.
    assert hash_pin("4821") != hash_pin("4821")


def test_malformed_hash_fails_instead_of_crashing():
    assert not verify_pin("4821", "not-a-hash")
    assert not verify_pin("4821", "bcrypt$1$2$3$c2FsdA==$aGFzaA==")


class FakeClock:
    def __init__(self):
        self.now = 1000.0

    def __call__(self):
        return self.now


def test_limiter_locks_after_max_failures_then_unlocks():
    clock = FakeClock()
    limiter = LoginLimiter(max_failures=3, lockout_seconds=60, clock=clock)

    for _ in range(2):
        limiter.record_failure("phone")
    assert limiter.seconds_locked("phone") == 0

    limiter.record_failure("phone")
    assert limiter.seconds_locked("phone") == 60

    clock.now += 61
    assert limiter.seconds_locked("phone") == 0


def test_limiter_success_clears_failures():
    limiter = LoginLimiter(max_failures=3, clock=FakeClock())
    limiter.record_failure("phone")
    limiter.record_failure("phone")
    limiter.record_success("phone")
    limiter.record_failure("phone")
    assert limiter.seconds_locked("phone") == 0


def test_limiter_tracks_clients_separately():
    limiter = LoginLimiter(max_failures=1, clock=FakeClock())
    limiter.record_failure("phone-a")
    assert limiter.seconds_locked("phone-a") > 0
    assert limiter.seconds_locked("phone-b") == 0
