import os
import tempfile
import threading
import time

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
        "list", 5, 32, 100, "novaa,novaa,echoo,bad-,UPPER"
    )
    assert set(candidates) == {"novaa", "echoo"}

    assert tgh.prepare_candidates(
        "list", 5, 32, 100, "nova7,nova_x,nova"
    ) == []
    enabled = set(tgh.prepare_candidates(
        "list", 5, 32, 100, "nova7,nova_x",
        allow_digits=True, allow_underscore=True,
    ))
    assert enabled == {"nova7", "nova_x"}

    generated = tgh.prepare_candidates(
        "both", 5, 32, 200, allow_digits=True, allow_underscore=True
    )
    assert generated
    assert all(5 <= len(name) <= 32 for name in generated)
    assert all(tgh.is_valid_telegram_format(name) for name in generated)

    assert tgh.parse_notify_chat_ids("1, 2,1,, bad, 3") == ["1", "2", "3"]

    stopped = threading.Event()
    stopped.set()
    assert tgh.check_username(None, "nova", stopped) is None

    class FloodedApp:
        def invoke(self, request):
            raise tgh.FloodWait(10)

    stopped.clear()
    threading.Timer(0.05, stopped.set).start()
    started = time.monotonic()
    assert tgh.check_username(FloodedApp(), "nova", stopped) is None
    assert time.monotonic() - started < 1

    sent_to = []
    original_bot_api = tgh._bot_api
    try:
        tgh._bot_api = lambda token, method, **data: sent_to.append(data["chat_id"])
        assert tgh.notify_available_username("token", ["1", "2"], "nova")
    finally:
        tgh._bot_api = original_bot_api
    assert sent_to == ["1", "2"]

    print("self-check OK")


if __name__ == "__main__":
    main()
