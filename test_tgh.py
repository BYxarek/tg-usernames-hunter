import os
import tempfile
import threading
import time
from itertools import islice
from pathlib import Path

import tgh


def main():
    os.environ["TGH_SELF_CHECK"] = "configured"
    assert tgh.get_setting("TGH_SELF_CHECK") == "configured"
    del os.environ["TGH_SELF_CHECK"]

    with tempfile.TemporaryDirectory() as directory:
        path = os.path.join(directory, "config.py")
        values = {name: f"value-{name}" for name in tgh.CONFIG_NAMES}
        tgh.save_config(values, path)
        assert tgh.load_config(path) == values

    candidates = tgh.prepare_candidates(
        "list", 5, 32, 100, "novaa,novaa,echoo,bad-,UPPER", min_score=0
    )
    assert set(candidates) == {"novaa", "echoo"}

    # min/max length must apply to custom lists too.
    assert tgh.prepare_candidates(
        "list", 5, 32, 100, "nova7,nova_x,nova", min_score=0
    ) == []

    enabled = set(tgh.prepare_candidates(
        "list", 5, 32, 100, "nova7,nova_x",
        allow_digits=True, allow_underscore=True, min_score=0,
    ))
    assert enabled == {"nova7", "nova_x"}

    generated = tgh.prepare_candidates(
        "both", 5, 32, 200,
        allow_digits=True, allow_underscore=True, min_score=0,
    )
    assert generated
    assert all(5 <= len(name) <= 32 for name in generated)
    assert all(tgh.is_valid_telegram_format(name) for name in generated)

    # limit=0 is a streaming/unlimited mode for generated sources.
    unlimited = list(islice(tgh.iter_candidates(
        "both", 5, 16, 0, allow_digits=True, allow_underscore=True, min_score=0,
    ), 25))
    assert len(unlimited) == 25
    assert len(set(unlimited)) == 25

    scored = tgh.prepare_candidates(
        "list", 5, 32, 100, "novaa,zzzzz,nova7",
        allow_digits=True, min_score=0,
    )
    assert [tgh.score_username(name) for name in scored] == sorted(
        [tgh.score_username(name) for name in scored], reverse=True
    )
    assert all(0 <= tgh.score_username(name) <= 100 for name in scored)

    # High beauty thresholds must mean lexical quality, not merely pronounceable noise.
    assert tgh.score_username("zumiyim") < 80
    assert tgh.score_username("iqahyew") < 80
    assert tgh.score_username("cloud") >= 80
    assert tgh.score_username("novacore") >= 80
    random_state = tgh.random.getstate()
    try:
        tgh.random.seed(24680)
        high_quality = tgh.prepare_candidates("both", 5, 16, 100, min_score=80)
    finally:
        tgh.random.setstate(random_state)
    assert high_quality
    assert all(tgh.score_username(name) >= 80 for name in high_quality)
    assert all(tgh._lexical_score(name) > 0 for name in high_quality)

    # Dictionary generation must be mixed, not a sequential word_io sweep.
    random_state = tgh.random.getstate()
    try:
        tgh.random.seed(12345)
        mixed = list(tgh.gen_dict_candidates(
            5, 16, 200, allow_digits=True, allow_underscore=True,
        ))
    finally:
        tgh.random.setstate(random_state)
    assert mixed
    assert any("_" not in name for name in mixed)
    underscore_suffixes = {name.split("_", 1)[1] for name in mixed if "_" in name}
    assert len(underscore_suffixes) >= 2
    assert sum(name.endswith("_io") for name in mixed) <= 1

    # GUI bot mode uses the same core generator and must only emit bot usernames.
    random_state = tgh.random.getstate()
    try:
        tgh.random.seed(54321)
        bot_names = tgh.prepare_candidates(
            "both", 5, 20, 100, allow_underscore=True, min_score=0,
            bot_usernames=True,
        )
    finally:
        tgh.random.setstate(random_state)
    assert bot_names
    assert all(name.endswith("bot") for name in bot_names)
    assert all(5 <= len(name) <= 20 for name in bot_names)
    assert all(tgh.is_valid_telegram_format(name) for name in bot_names)
    assert any(name.endswith("_bot") for name in bot_names)

    # Custom-list bases are normalized by appending the required bot suffix.
    listed_bots = tgh.prepare_candidates(
        "list", 5, 20, 10, "novaa,cloudbot", min_score=0, bot_usernames=True,
    )
    assert set(listed_bots) == {"novaabot", "cloudbot"}

    assert tgh.parse_notify_chat_ids("1, 2,1,, bad, 3") == ["1", "2", "3"]

    stopped = threading.Event()
    stopped.set()
    assert tgh.check_username(None, "novaa", stopped) is None

    class FloodedApp:
        def invoke(self, request):
            raise tgh.FloodWait(10)

    stopped.clear()
    threading.Timer(0.05, stopped.set).start()
    started = time.monotonic()
    assert tgh.check_username(FloodedApp(), "novaa", stopped) is None
    assert time.monotonic() - started < 1

    # Telegram USERNAME_INVALID is an availability outcome, not a failed check.
    original_username_invalid = tgh.UsernameInvalid
    class FakeUsernameInvalid(Exception):
        pass
    class InvalidApp:
        def invoke(self, request):
            raise FakeUsernameInvalid("USERNAME_INVALID")
    try:
        tgh.UsernameInvalid = FakeUsernameInvalid
        assert tgh.check_username(InvalidApp(), "sable") == "unavailable"
    finally:
        tgh.UsernameInvalid = original_username_invalid

    sent_to = []
    original_bot_api = tgh._bot_api
    try:
        tgh._bot_api = lambda token, method, **data: sent_to.append(data["chat_id"])
        assert tgh.notify_available_username("token", ["1", "2"], "novaa")
    finally:
        tgh._bot_api = original_bot_api
    assert sent_to == ["1", "2"]

    # Logger must be writable and preserve diagnostic records.
    marker = f"self-check-log-{time.time_ns()}"
    tgh.LOGGER.error(marker)
    for handler in tgh.LOGGER.handlers:
        handler.flush()
    assert os.path.isfile(tgh.log_path())
    with open(tgh.log_path(), encoding="utf-8") as log_file:
        assert marker in log_file.read()

    class BrokenApp:
        def invoke(self, request):
            raise RuntimeError("diagnostic-test-error")

    assert tgh.check_username(BrokenApp(), "novaa") is None
    for handler in tgh.LOGGER.handlers:
        handler.flush()
    with open(tgh.log_path(), encoding="utf-8") as log_file:
        log_text = log_file.read()
    assert "diagnostic-test-error" in log_text
    assert "novaa" in log_text

    # Bootstrap frontend contract: responsive web UI, unlimited hint and new-search control.
    project_dir = Path(__file__).resolve().parent
    index_html = (project_dir / "web" / "index.html").read_text(encoding="utf-8")
    app_js = (project_dir / "web" / "app.js").read_text(encoding="utf-8")
    assert "bootstrap@5.3.8" in index_html
    assert "github.com/BYxarek" in index_html
    assert "limitHelp" in app_js and "0 — без ограничения" in app_js
    assert "newSearchBtn" in app_js

    print("self-check OK")


if __name__ == "__main__":
    main()
