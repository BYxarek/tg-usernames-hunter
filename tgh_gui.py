#!/usr/bin/env python3
"""Bootstrap/pywebview desktop GUI for TG Username Hunter."""

from __future__ import annotations

import asyncio
import json
import os
import queue
import subprocess
import sys
import threading
from pathlib import Path

import tgh as core
from pyrogram.errors import SessionPasswordNeeded

try:
    import webview
except ImportError:
    print("pywebview не установлен. Выполните: pip install -r requirements.txt")
    raise


APP_VERSION = "1.2.0"
APP_TITLE = "TG USERNAME HUNTER"


def resource_path(*parts: str) -> str:
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
    return str(base.joinpath(*parts))


class Bridge:
    """Python backend exposed to the Bootstrap frontend through pywebview."""

    def __init__(self):
        self.window = None
        self.app_client = None
        self.pending_phone = None
        self.sent_code_hash = None
        self.stop_event = threading.Event()
        self.search_running = threading.Event()
        self.job_q: queue.Queue = queue.Queue()
        self.worker = threading.Thread(target=self._worker_loop, name="telegram-worker", daemon=True)
        self.worker.start()

    def bind_window(self, window):
        self.window = window

    def _worker_loop(self):
        asyncio.set_event_loop(asyncio.new_event_loop())
        while True:
            job = self.job_q.get()
            try:
                if job is None:
                    return
                job()
            except Exception as exc:
                core.LOGGER.exception("GUI worker fatal error: %s", exc)
                self._emit("fatal_error", message=str(exc))
            finally:
                self.job_q.task_done()

    def _emit(self, kind: str, **payload):
        if self.window is None:
            return
        event = {"kind": kind, **payload}
        script = f"window.dispatchBackendEvent({json.dumps(event, ensure_ascii=False)});"
        try:
            self.window.evaluate_js(script)
        except Exception as exc:
            core.LOGGER.debug("GUI: frontend event delivery failed: %s", exc, exc_info=True)

    # --------------------------- frontend API ---------------------------
    def bootstrap(self):
        local_config = core.load_config()
        return {
            "version": APP_VERSION,
            "config": {name: local_config.get(name, "") for name in core.CONFIG_NAMES},
            "auto_connect": bool(local_config) and all(local_config.get(name) for name in core.CONFIG_NAMES),
            "log_path": core.log_path(),
        }

    def connect(self, data):
        try:
            api_id = str(data.get("api_id", "")).strip()
            api_hash = str(data.get("api_hash", "")).strip()
            bot_token = str(data.get("bot_token", "")).strip()
            notify_ids = core.parse_notify_chat_ids(str(data.get("notify_ids", "")))
            if not api_id.isdigit() or not api_hash or ":" not in bot_token or not notify_ids:
                return {"ok": False, "error": "Заполните корректно API ID, API hash, токен бота и ID получателей."}

            # Only explicit frontend values are persisted. Environment/Registry
            # values are never imported into a newly created local config.py.
            core.save_config({
                "TG_API_ID": api_id,
                "TG_API_HASH": api_hash,
                "TG_BOT_TOKEN": bot_token,
                "TG_NOTIFY_CHAT_IDS": ",".join(notify_ids),
            })
            self.job_q.put(lambda: self._worker_connect(api_id, api_hash))
            return {"ok": True}
        except Exception as exc:
            core.LOGGER.exception("GUI: connect request failed: %s", exc)
            return {"ok": False, "error": str(exc)}

    def send_code(self, phone: str):
        phone = str(phone or "").strip()
        if not phone:
            return {"ok": False, "error": "Введите номер телефона."}
        self.pending_phone = phone
        self.job_q.put(lambda: self._worker_send_code(phone))
        return {"ok": True}

    def confirm_code(self, code: str):
        code = str(code or "").strip()
        if not code:
            return {"ok": False, "error": "Введите код."}
        self.job_q.put(lambda: self._worker_confirm_code(code))
        return {"ok": True}

    def confirm_password(self, password: str):
        password = str(password or "")
        if not password:
            return {"ok": False, "error": "Введите пароль."}
        self.job_q.put(lambda: self._worker_confirm_password(password))
        return {"ok": True}

    def start_search(self, settings):
        if self.search_running.is_set():
            return {"ok": False, "error": "Поиск уже запущен."}
        try:
            clean = self._validate_settings(settings)
        except (TypeError, ValueError) as exc:
            return {"ok": False, "error": str(exc)}

        self.stop_event.clear()
        self.search_running.set()
        self.job_q.put(lambda: self._worker_search(clean))
        return {"ok": True, "settings": clean}

    def stop_search(self):
        self.stop_event.set()
        return {"ok": True}

    def open_log(self):
        path = core.log_path()
        try:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            Path(path).touch(exist_ok=True)
            if os.name == "nt":
                os.startfile(path)
            elif sys.platform == "darwin":
                subprocess.Popen(["open", path])
            else:
                subprocess.Popen(["xdg-open", path])
            core.LOGGER.info("GUI: opened log %s", path)
            return {"ok": True, "path": path}
        except Exception as exc:
            core.LOGGER.exception("GUI: failed to open log: %s", exc)
            return {"ok": False, "error": str(exc)}

    def open_external(self, url: str):
        import webbrowser
        try:
            webbrowser.open(str(url))
            return {"ok": True}
        except Exception as exc:
            core.LOGGER.exception("GUI: failed to open URL %s: %s", url, exc)
            return {"ok": False, "error": str(exc)}

    # --------------------------- telegram jobs --------------------------
    def _worker_connect(self, api_id: str, api_hash: str):
        try:
            session_dir = os.path.join(
                os.environ.get("LOCALAPPDATA", os.path.expanduser("~")),
                "TGUsernameHunter",
            )
            os.makedirs(session_dir, exist_ok=True)
            if self.app_client is not None:
                try:
                    self.app_client.disconnect()
                except Exception:
                    pass
            app = core.Client("gui_session", api_id=int(api_id), api_hash=api_hash, workdir=session_dir)
            app.connect()
            self.app_client = app
            try:
                app.get_me()
                self._emit("authorized")
            except Exception as exc:
                core.LOGGER.info("GUI: Telegram session is not authorized: %s", exc)
                self._emit("need_phone")
        except Exception as exc:
            core.LOGGER.exception("GUI: Telegram connection error: %s", exc)
            self._emit("connect_error", message=str(exc))

    def _worker_send_code(self, phone: str):
        try:
            sent = self.app_client.send_code(phone)
            self.sent_code_hash = sent.phone_code_hash
            self._emit("need_code")
        except Exception as exc:
            core.LOGGER.exception("GUI: send code error: %s", exc)
            self._emit("phone_error", message=str(exc))

    def _worker_confirm_code(self, code: str):
        try:
            self.app_client.sign_in(self.pending_phone, self.sent_code_hash, code)
            self._emit("authorized")
        except SessionPasswordNeeded:
            self._emit("need_password")
        except Exception as exc:
            core.LOGGER.exception("GUI: confirm code error: %s", exc)
            self._emit("code_error", message=str(exc))

    def _worker_confirm_password(self, password: str):
        try:
            self.app_client.check_password(password)
            self._emit("authorized")
        except Exception as exc:
            core.LOGGER.exception("GUI: 2FA password error: %s", exc)
            self._emit("password_error", message=str(exc))

    def _validate_settings(self, settings: dict) -> dict:
        mode = str(settings.get("mode", "both"))
        if mode not in {"dict", "syllable", "both", "list"}:
            raise ValueError("Неизвестный режим поиска.")
        min_len = int(settings.get("min_len", 5))
        max_len = int(settings.get("max_len", 12))
        if not 5 <= min_len <= 32 or not 5 <= max_len <= 32 or min_len > max_len:
            raise ValueError("Длина username должна быть от 5 до 32, минимум не больше максимума.")
        limit = int(settings.get("limit", 100))
        if not 0 <= limit <= 10000:
            raise ValueError("Количество проверок: 0–10000. 0 означает без лимита.")
        delay = float(settings.get("delay", 1.0))
        if delay < 0:
            raise ValueError("Пауза не может быть отрицательной.")
        min_score = int(settings.get("min_score", 70))
        if not 0 <= min_score <= 100:
            raise ValueError("Красота должна быть от 0 до 100.")
        words = str(settings.get("words", "")).strip()
        if mode == "list" and not words:
            raise ValueError("Для режима «Свой список» введите username через запятую.")
        return {
            "mode": mode,
            "min_len": min_len,
            "max_len": max_len,
            "limit": limit,
            "delay": delay,
            "min_score": min_score,
            "words": words,
            "allow_digits": bool(settings.get("allow_digits", False)),
            "allow_underscore": bool(settings.get("allow_underscore", False)),
            "bot_usernames": bool(settings.get("bot_usernames", False)),
        }

    def _worker_search(self, settings: dict):
        notifier = None
        checked = 0
        try:
            common = dict(
                words=settings.get("words"),
                allow_digits=settings.get("allow_digits", False),
                allow_underscore=settings.get("allow_underscore", False),
                min_score=settings.get("min_score", 70),
                bot_usernames=settings.get("bot_usernames", False),
            )

            if settings["limit"] > 0:
                candidates = core.prepare_candidates(
                    settings["mode"], settings["min_len"], settings["max_len"],
                    settings["limit"], **common,
                )
                total = len(candidates)
                candidate_iter = iter(candidates)
            elif settings["mode"] == "list":
                natural_limit = max(1, len([x for x in settings.get("words", "").split(",") if x.strip()]))
                candidates = core.prepare_candidates(
                    settings["mode"], settings["min_len"], settings["max_len"],
                    natural_limit, **common,
                )
                total = len(candidates)
                candidate_iter = iter(candidates)
            else:
                total = None
                candidate_iter = core.iter_candidates(
                    settings["mode"], settings["min_len"], settings["max_len"], 0,
                    stop_event=self.stop_event, **common,
                )

            self._emit("search_started", total=total, unlimited=total is None)
            if total == 0:
                self._emit("search_done", checked=0, total=0)
                return

            bot_token = core.get_setting("TG_BOT_TOKEN")
            notify_ids = core.parse_notify_chat_ids(
                core.get_setting("TG_NOTIFY_CHAT_IDS") or core.get_setting("TG_NOTIFY_CHAT_ID")
            )
            notifier = core.BotNotificationWorker(
                bot_token, notify_ids,
                on_error=lambda error: self._emit("bot_error", message=error),
            )

            for username in candidate_iter:
                if self.stop_event.is_set():
                    self._emit("search_stopped", checked=checked, total=total)
                    return
                checked += 1
                available = core.check_username(self.app_client, username, self.stop_event)
                if self.stop_event.is_set():
                    self._emit("search_stopped", checked=checked - 1, total=total)
                    return
                if available is None:
                    core.LOGGER.warning("GUI: @%s marked skipped", username)
                if available is True:
                    notifier.submit(username)
                self._emit(
                    "search_result",
                    index=checked,
                    total=total,
                    username=username,
                    available=available,
                    score=core.score_username(username),
                )
                if settings["delay"] > 0 and self.stop_event.wait(settings["delay"]):
                    self._emit("search_stopped", checked=checked, total=total)
                    return

            self._emit("search_done", checked=checked, total=total if total is not None else checked)
        except Exception as exc:
            core.LOGGER.exception("GUI: username search error: %s", exc)
            self._emit("search_error", message=str(exc), checked=checked)
        finally:
            self.search_running.clear()
            if notifier is not None:
                notifier.close(wait=False)


def main():
    bridge = Bridge()
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
    index = base / "web" / "index.html"
    if not index.exists():
        raise FileNotFoundError(f"GUI frontend not found: {index}")

    # A relative local URL makes pywebview start its built-in HTTP server,
    # avoiding file:// limitations while keeping the frontend fully local.
    os.chdir(base)
    window = webview.create_window(
        APP_TITLE,
        "web/index.html",
        js_api=bridge,
        width=900,
        height=720,
        min_size=(680, 560),
        resizable=True,
        background_color="#0b0d12",
    )
    bridge.bind_window(window)
    core.LOGGER.info("GUI %s started; frontend=%s", APP_VERSION, index)
    webview.start(debug=False, private_mode=False)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        core.LOGGER.exception("Critical GUI error: %s", exc)
        raise
