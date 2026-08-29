from lazynote import timer


def test_parse_start_commands():
    assert timer.parse_command("timer") == timer.TimerCommand("start", 25 * 60_000)
    assert timer.parse_command("timer 90s") == timer.TimerCommand("start", 90_000)
    assert timer.parse_command("timer 10m") == timer.TimerCommand("start", 600_000)
    assert timer.parse_command("timer 1h") == timer.TimerCommand("start", 3_600_000)


def test_parse_control_commands_and_rejects_non_commands():
    assert timer.parse_command("timer p") == timer.TimerCommand("pause", None)
    assert timer.parse_command("timer r") == timer.TimerCommand("resume", None)
    assert timer.parse_command(" timer") is None
    assert timer.parse_command("timer 0m") is None
    assert timer.parse_command("timer -1m") is None
    assert timer.parse_command("timer 1.5m") is None
    assert timer.parse_command("timer 2d") is None
    assert timer.parse_command("timer hello") is None


def test_format_remaining_rounds_up_to_the_next_visible_second():
    assert timer.format_remaining(0) == "00:00"
    assert timer.format_remaining(1) == "00:01"
    assert timer.format_remaining(60_000) == "01:00"
    assert timer.format_remaining(61_001) == "01:02"


def test_pause_resume_and_refresh_use_wall_clock_time():
    running = timer.start(10_000, now_ms=1_000)
    assert timer.remaining_ms(running, now_ms=4_250) == 6_750
    paused = timer.pause(running, now_ms=4_250)
    assert paused == timer.TimerState("paused", None, 6_750)
    assert timer.remaining_ms(paused, now_ms=99_000) == 6_750
    resumed = timer.resume(paused, now_ms=99_000)
    assert resumed == timer.TimerState("running", 105_750, 6_750)
    assert timer.refresh(resumed, now_ms=105_750).status == "done"


def test_state_round_trip_and_invalid_saved_values():
    original = timer.TimerState("paused", None, 123_456)
    assert timer.decode_state(timer.encode_state(original)) == original
    assert timer.decode_state(None) is None
    assert timer.decode_state("not json") is None
    assert timer.decode_state('{"status":"running","ends_at_ms":null,"remaining_ms":1}') is None
