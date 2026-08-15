#!/usr/bin/env python3
"""
tg_username_hunter — GUI
=========================
Графический интерфейс поверх tgh.py: тёмная минималистичная
тема с белыми акцентами, плавные переходы между экранами, поддержка
русского и английского языков.

УСТАНОВКА
---------
    pip install -r requirements.txt

ВАЖНО: этот файл должен лежать в той же папке, что и tgh.py — он
используется как модуль (генерация кандидатов, фильтры, проверка через
Telegram API).

ЗАПУСК
------
    python tgh_gui.py
"""

import importlib
import sys
import os
import queue
import threading


def require_package(pip_name: str, import_name: str = None):
    import_name = import_name or pip_name
    try:
        return importlib.import_module(import_name)
    except ImportError:
        requirements = os.path.join(os.path.dirname(__file__), "requirements.txt")
        print(f"Библиотека '{pip_name}' не установлена. Выполните: "
              f"{sys.executable} -m pip install -r {requirements}")
        sys.exit(1)


require_package("customtkinter")
import customtkinter as ctk  # noqa: E402

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
try:
    import tgh as core  # обычный import — так PyInstaller сам подхватит файл при сборке .exe
except ImportError:
    try:
        import importlib.util as _ilu
        _core_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "tgh.py")
        _spec = _ilu.spec_from_file_location("tgh", _core_path)
        core = _ilu.module_from_spec(_spec)
        _spec.loader.exec_module(core)
    except Exception as e:
        print("Не удалось загрузить tgh.py — положите его рядом с этим файлом.")
        print(f"Ошибка: {e}")
        sys.exit(1)

from pyrogram.errors import SessionPasswordNeeded, RPCError  # noqa: E402


# ---------------------------------------------------------------------------
# Палитра и переводы
# ---------------------------------------------------------------------------

BG = "#0c0c0c"
BG_PANEL = "#161616"
BG_INPUT = "#1e1e1e"
FG = "#f4f4f4"
FG_MUTED = "#8f8f8f"
BORDER = "#2a2a2a"
WHITE = "#ffffff"
BLACK = "#0c0c0c"

FONT_TITLE = ("Helvetica", 22, "bold")
FONT_SUB = ("Helvetica", 12)
FONT_BODY = ("Helvetica", 13)
FONT_MONO = ("Consolas", 12)
FONT_SMALL = ("Helvetica", 11)

TEXTS = {
    "ru": {
        "app_title": "TG USERNAME HUNTER",
        "app_sub": "найди свободный ник в Telegram",
        "lang_btn": "EN",

        "cred_title": "Данные приложения",
        "cred_hint": "Получить api_id и api_hash можно на my.telegram.org",
        "cred_get_link": "Открыть my.telegram.org",
        "api_id_ph": "api_id",
        "api_hash_ph": "api_hash",
        "bot_token_ph": "токен бота",
        "notify_ids_ph": "ID получателей через запятую",
        "connect_btn": "Подключиться",
        "connecting": "Подключение...",

        "phone_title": "Вход в Telegram",
        "phone_hint": "Введите номер телефона в международном формате",
        "phone_ph": "+79991234567",
        "send_code_btn": "Отправить код",
        "sending_code": "Отправка кода...",

        "code_title": "Введите код",
        "code_hint": "Код придёт в приложение Telegram или по SMS",
        "code_ph": "12345",
        "confirm_code_btn": "Подтвердить",
        "checking_code": "Проверка...",

        "password_title": "Двухфакторная аутентификация",
        "password_hint": "Введите облачный пароль вашего аккаунта",
        "password_ph": "пароль",
        "confirm_password_btn": "Войти",

        "settings_title": "Параметры поиска",
        "mode_label": "Режим",
        "mode_dict": "Словарь",
        "mode_syllable": "Слоги",
        "mode_both": "Оба",
        "mode_list": "Свой список",
        "list_hint": "Ники через запятую",
        "length_label": "Длина ника",
        "limit_label": "Сколько проверить",
        "delay_label": "Пауза (сек)",
        "start_btn": "Начать поиск",
        "back_btn": "Назад",

        "results_title": "Результаты",
        "stop_btn": "Остановить",
        "status_idle": "Готово к запуску",
        "status_running": "Проверяю: {username}",
        "status_done": "Готово. Проверено {n} ников.",
        "status_stopped": "Остановлено пользователем.",
        "copy_btn": "копировать",
        "copied_btn": "скопировано",
        "no_results_yet": "Пока ничего не найдено — результаты появятся здесь по мере проверки.",
        "status_available": "свободен",
        "status_fragment": "только Fragment",
        "status_taken": "занят",
        "status_error": "ошибка / пропущен",

        "error_title": "Ошибка",
        "error_generic": "Что-то пошло не так: {msg}",
        "error_api_fields": "Заполните оба поля: api_id и api_hash.",
        "error_config_fields": "Заполните API ID, API hash, токен бота и ID получателей.",
        "error_config_save": "Не удалось сохранить config.py: {msg}",
        "error_phone": "Заполните номер телефона.",
        "error_code": "Введите код.",
        "error_password": "Введите пароль.",

        "footer": "made by v0idk1d · github.com/BYxarek · help: @rlxmsa · powered by Claude AI",
    },
    "en": {
        "app_title": "TG USERNAME HUNTER",
        "app_sub": "find a free Telegram username",
        "lang_btn": "RU",

        "cred_title": "App credentials",
        "cred_hint": "Get your api_id and api_hash at my.telegram.org",
        "cred_get_link": "Open my.telegram.org",
        "api_id_ph": "api_id",
        "api_hash_ph": "api_hash",
        "bot_token_ph": "bot token",
        "notify_ids_ph": "recipient IDs, comma-separated",
        "connect_btn": "Connect",
        "connecting": "Connecting...",

        "phone_title": "Log in to Telegram",
        "phone_hint": "Enter your phone number in international format",
        "phone_ph": "+15551234567",
        "send_code_btn": "Send code",
        "sending_code": "Sending code...",

        "code_title": "Enter the code",
        "code_hint": "The code will arrive in the Telegram app or via SMS",
        "code_ph": "12345",
        "confirm_code_btn": "Confirm",
        "checking_code": "Checking...",

        "password_title": "Two-factor authentication",
        "password_hint": "Enter your account's cloud password",
        "password_ph": "password",
        "confirm_password_btn": "Sign in",

        "settings_title": "Search settings",
        "mode_label": "Mode",
        "mode_dict": "Dictionary",
        "mode_syllable": "Syllables",
        "mode_both": "Both",
        "mode_list": "Custom list",
        "list_hint": "Usernames, comma-separated",
        "length_label": "Username length",
        "limit_label": "How many to check",
        "delay_label": "Delay (sec)",
        "start_btn": "Start search",
        "back_btn": "Back",

        "results_title": "Results",
        "stop_btn": "Stop",
        "status_idle": "Ready to start",
        "status_running": "Checking: {username}",
        "status_done": "Done. Checked {n} usernames.",
        "status_stopped": "Stopped by user.",
        "copy_btn": "copy",
        "copied_btn": "copied",
        "no_results_yet": "Nothing found yet — results will appear here as they're checked.",
        "status_available": "available",
        "status_fragment": "Fragment only",
        "status_taken": "taken",
        "status_error": "error / skipped",

        "error_title": "Error",
        "error_generic": "Something went wrong: {msg}",
        "error_api_fields": "Fill in both api_id and api_hash.",
        "error_config_fields": "Fill in API ID, API hash, bot token, and recipient IDs.",
        "error_config_save": "Could not save config.py: {msg}",
        "error_phone": "Enter your phone number.",
        "error_code": "Enter the code.",
        "error_password": "Enter the password.",

        "footer": "made by v0idk1d · github.com/BYxarek · help: @rlxmsa · powered by Claude AI",
    },
}


# ---------------------------------------------------------------------------
# Приложение
# ---------------------------------------------------------------------------

class App(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.lang = "ru"
        self.title(TEXTS[self.lang]["app_title"])
        self.geometry("560x760")
        self.minsize(480, 680)
        self.configure(fg_color=BG)

        ctk.set_appearance_mode("dark")

        # очереди для общения с рабочим потоком
        self.out_q = queue.Queue()
        self.in_q = queue.Queue()
        self.stop_flag = threading.Event()

        # ОДИН постоянный поток с ОДНИМ event loop — все вызовы Pyrofork
        # обязаны идти через него, иначе клиент "теряет" свой loop между шагами
        self.job_q = queue.Queue()
        self.worker_thread = threading.Thread(target=self._worker_loop, daemon=True)
        self.worker_thread.start()

        self.app_client = None
        self.pending_phone = None
        self.sent_code_hash = None

        self._build_chrome()
        self.current_screen = "credentials"
        self.show_credentials_screen()
        if all(core.get_setting(name) for name in core.CONFIG_NAMES):
            self._on_connect_clicked()

        self._fade_in()
        self.after(80, self._poll_queue)

    # ---- window fade-in animation ----
    def _fade_in(self, alpha=0.0):
        try:
            self.attributes("-alpha", alpha)
            if alpha < 1.0:
                self.after(15, lambda: self._fade_in(min(alpha + 0.08, 1.0)))
        except Exception:
            pass

    def t(self, key, **kwargs):
        text = TEXTS[self.lang].get(key, key)
        return text.format(**kwargs) if kwargs else text

    def _worker_loop(self):
        """Живёт всё время работы приложения в одном потоке с одним event loop.
        Все вызовы Pyrofork должны идти через self.job_q.put(...), иначе
        клиент окажется привязан к другому loop и начнёт падать со
        странными ошибками asyncio."""
        import asyncio
        asyncio.set_event_loop(asyncio.new_event_loop())
        while True:
            job = self.job_q.get()
            try:
                job()
            except Exception as e:
                self.out_q.put(("fatal_error", str(e)))

    # ---- persistent chrome (header/footer) ----
    def _build_chrome(self):
        header = ctk.CTkFrame(self, fg_color=BG, corner_radius=0)
        header.pack(fill="x", padx=24, pady=(20, 0))

        title_box = ctk.CTkFrame(header, fg_color="transparent")
        title_box.pack(side="left", anchor="w")

        self.title_label = ctk.CTkLabel(title_box, text=self.t("app_title"), font=FONT_TITLE, text_color=WHITE)
        self.title_label.pack(anchor="w")
        self.sub_label = ctk.CTkLabel(title_box, text=self.t("app_sub"), font=FONT_SUB, text_color=FG_MUTED)
        self.sub_label.pack(anchor="w")

        self.lang_btn = ctk.CTkButton(
            header, text=self.t("lang_btn"), width=44, height=30,
            fg_color="transparent", border_width=1, border_color=BORDER,
            text_color=FG, hover_color=BG_PANEL, font=FONT_SMALL,
            command=self._toggle_lang,
        )
        self.lang_btn.pack(side="right", anchor="e")

        sep = ctk.CTkFrame(self, fg_color=BORDER, height=1, corner_radius=0)
        sep.pack(fill="x", padx=24, pady=(16, 0))

        # основной контейнер, куда подставляются экраны
        self.content = ctk.CTkFrame(self, fg_color=BG, corner_radius=0)
        self.content.pack(fill="both", expand=True, padx=24, pady=16)

        footer_sep = ctk.CTkFrame(self, fg_color=BORDER, height=1, corner_radius=0)
        footer_sep.pack(fill="x", padx=24)
        self.footer_label = ctk.CTkLabel(self, text=self.t("footer"), font=FONT_SMALL, text_color=FG_MUTED)
        self.footer_label.pack(pady=10)

    def _toggle_lang(self):
        self.lang = "en" if self.lang == "ru" else "ru"
        self.title_label.configure(text=self.t("app_title"))
        self.sub_label.configure(text=self.t("app_sub"))
        self.lang_btn.configure(text=self.t("lang_btn"))
        self.footer_label.configure(text=self.t("footer"))
        self._rebuild_current_screen()

    def _rebuild_current_screen(self):
        screen = self.current_screen
        if screen == "credentials":
            self.show_credentials_screen()
        elif screen == "phone":
            self.show_phone_screen()
        elif screen == "code":
            self.show_code_screen()
        elif screen == "password":
            self.show_password_screen()
        elif screen == "settings":
            self.show_settings_screen()
        elif screen == "results":
            self.show_results_screen(rebuild_only=True)

    def _clear_content(self):
        for w in self.content.winfo_children():
            w.destroy()

    def _slide_in(self, frame):
        """Небольшая анимация появления экрана — сдвиг + фейд через смену цвета не поддерживается
        нативно у CTk, поэтому имитируем через постепенное увеличение отступа."""
        frame.pack(fill="both", expand=True)

    # ---- error banner helper ----
    def _show_inline_error(self, parent, message):
        lbl = ctk.CTkLabel(parent, text=message, text_color="#ff8080", font=FONT_SMALL, wraplength=460, justify="left")
        lbl.pack(anchor="w", pady=(6, 0))
        return lbl

    # =========================================================
    # ЭКРАН 1 — api_id / api_hash
    # =========================================================
    def show_credentials_screen(self):
        self.current_screen = "credentials"
        self._clear_content()
        frame = ctk.CTkFrame(self.content, fg_color="transparent")
        self._slide_in(frame)

        ctk.CTkLabel(frame, text=self.t("cred_title"), font=("Helvetica", 16, "bold"), text_color=WHITE).pack(anchor="w", pady=(0, 4))
        ctk.CTkLabel(frame, text=self.t("cred_hint"), font=FONT_BODY, text_color=FG_MUTED, wraplength=460, justify="left").pack(anchor="w", pady=(0, 14))

        link_btn = ctk.CTkButton(
            frame, text=self.t("cred_get_link"), fg_color="transparent",
            border_width=1, border_color=BORDER, text_color=FG, hover_color=BG_PANEL,
            font=FONT_SMALL, command=lambda: self._open_link("https://my.telegram.org"),
        )
        link_btn.pack(anchor="w", pady=(0, 20))

        self.api_id_entry = ctk.CTkEntry(frame, placeholder_text=self.t("api_id_ph"), fg_color=BG_INPUT,
                                          border_color=BORDER, text_color=FG, height=42)
        self.api_id_entry.pack(fill="x", pady=(0, 10))
        if core.get_setting("TG_API_ID"):
            self.api_id_entry.insert(0, core.get_setting("TG_API_ID"))

        self.api_hash_entry = ctk.CTkEntry(frame, placeholder_text=self.t("api_hash_ph"), fg_color=BG_INPUT,
                                            border_color=BORDER, text_color=FG, height=42, show="•")
        self.api_hash_entry.pack(fill="x", pady=(0, 10))
        if core.get_setting("TG_API_HASH"):
            self.api_hash_entry.insert(0, core.get_setting("TG_API_HASH"))

        self.bot_token_entry = ctk.CTkEntry(frame, placeholder_text=self.t("bot_token_ph"), fg_color=BG_INPUT,
                                            border_color=BORDER, text_color=FG, height=42, show="•")
        self.bot_token_entry.pack(fill="x", pady=(0, 10))
        if core.get_setting("TG_BOT_TOKEN"):
            self.bot_token_entry.insert(0, core.get_setting("TG_BOT_TOKEN"))

        self.notify_ids_entry = ctk.CTkEntry(frame, placeholder_text=self.t("notify_ids_ph"), fg_color=BG_INPUT,
                                             border_color=BORDER, text_color=FG, height=42)
        self.notify_ids_entry.pack(fill="x", pady=(0, 20))
        if core.get_setting("TG_NOTIFY_CHAT_IDS"):
            self.notify_ids_entry.insert(0, core.get_setting("TG_NOTIFY_CHAT_IDS"))

        self.cred_error_holder = ctk.CTkFrame(frame, fg_color="transparent")
        self.cred_error_holder.pack(fill="x")

        self.connect_btn = ctk.CTkButton(
            frame, text=self.t("connect_btn"), fg_color=WHITE, text_color=BLACK,
            hover_color="#dddddd", height=44, font=("Helvetica", 13, "bold"),
            command=self._on_connect_clicked,
        )
        self.connect_btn.pack(fill="x", pady=(10, 0))

    def _open_link(self, url):
        import webbrowser
        webbrowser.open(url)

    def _on_connect_clicked(self):
        for w in self.cred_error_holder.winfo_children():
            w.destroy()
        api_id = self.api_id_entry.get().strip()
        api_hash = self.api_hash_entry.get().strip()
        bot_token = self.bot_token_entry.get().strip()
        notify_chat_ids = core.parse_notify_chat_ids(self.notify_ids_entry.get())
        if not api_id.isdigit() or not api_hash or ":" not in bot_token or not notify_chat_ids:
            self._show_inline_error(self.cred_error_holder, self.t("error_config_fields"))
            return

        try:
            core.save_config({
                "TG_API_ID": api_id,
                "TG_API_HASH": api_hash,
                "TG_BOT_TOKEN": bot_token,
                "TG_NOTIFY_CHAT_IDS": ",".join(notify_chat_ids),
            })
        except OSError as e:
            self._show_inline_error(
                self.cred_error_holder, self.t("error_config_save", msg=e)
            )
            return

        self.connect_btn.configure(state="disabled", text=self.t("connecting"))
        self.job_q.put(lambda: self._worker_connect(api_id, api_hash))

    def _worker_connect(self, api_id, api_hash):
        try:
            session_dir = os.path.join(
                os.environ.get("LOCALAPPDATA", os.path.expanduser("~")),
                "TGUsernameHunter",
            )
            os.makedirs(session_dir, exist_ok=True)
            app = core.Client(
                "gui_session", api_id=int(api_id), api_hash=api_hash,
                workdir=session_dir,
            )
            app.connect()
        except Exception as e:
            self.out_q.put(("connect_error", str(e)))
            return

        self.app_client = app
        try:
            app.get_me()
            self.out_q.put(("authorized",))
        except Exception:
            self.out_q.put(("need_phone",))

    # =========================================================
    # ЭКРАН 2 — телефон
    # =========================================================
    def show_phone_screen(self):
        self.current_screen = "phone"
        self._clear_content()
        frame = ctk.CTkFrame(self.content, fg_color="transparent")
        self._slide_in(frame)

        ctk.CTkLabel(frame, text=self.t("phone_title"), font=("Helvetica", 16, "bold"), text_color=WHITE).pack(anchor="w", pady=(0, 4))
        ctk.CTkLabel(frame, text=self.t("phone_hint"), font=FONT_BODY, text_color=FG_MUTED, wraplength=460, justify="left").pack(anchor="w", pady=(0, 16))

        self.phone_entry = ctk.CTkEntry(frame, placeholder_text=self.t("phone_ph"), fg_color=BG_INPUT,
                                         border_color=BORDER, text_color=FG, height=42)
        self.phone_entry.pack(fill="x", pady=(0, 16))

        self.phone_error_holder = ctk.CTkFrame(frame, fg_color="transparent")
        self.phone_error_holder.pack(fill="x")

        self.send_code_btn = ctk.CTkButton(
            frame, text=self.t("send_code_btn"), fg_color=WHITE, text_color=BLACK,
            hover_color="#dddddd", height=44, font=("Helvetica", 13, "bold"),
            command=self._on_send_code_clicked,
        )
        self.send_code_btn.pack(fill="x", pady=(10, 0))

    def _on_send_code_clicked(self):
        for w in self.phone_error_holder.winfo_children():
            w.destroy()
        phone = self.phone_entry.get().strip()
        if not phone:
            self._show_inline_error(self.phone_error_holder, self.t("error_phone"))
            return
        self.pending_phone = phone
        self.send_code_btn.configure(state="disabled", text=self.t("sending_code"))
        self.job_q.put(lambda: self._worker_send_code(phone))

    def _worker_send_code(self, phone):
        try:
            sent = self.app_client.send_code(phone)
            self.sent_code_hash = sent.phone_code_hash
            self.out_q.put(("need_code",))
        except Exception as e:
            self.out_q.put(("phone_error", str(e)))

    # =========================================================
    # ЭКРАН 3 — код подтверждения
    # =========================================================
    def show_code_screen(self):
        self.current_screen = "code"
        self._clear_content()
        frame = ctk.CTkFrame(self.content, fg_color="transparent")
        self._slide_in(frame)

        ctk.CTkLabel(frame, text=self.t("code_title"), font=("Helvetica", 16, "bold"), text_color=WHITE).pack(anchor="w", pady=(0, 4))
        ctk.CTkLabel(frame, text=self.t("code_hint"), font=FONT_BODY, text_color=FG_MUTED, wraplength=460, justify="left").pack(anchor="w", pady=(0, 16))

        self.code_entry = ctk.CTkEntry(frame, placeholder_text=self.t("code_ph"), fg_color=BG_INPUT,
                                        border_color=BORDER, text_color=FG, height=42)
        self.code_entry.pack(fill="x", pady=(0, 16))

        self.code_error_holder = ctk.CTkFrame(frame, fg_color="transparent")
        self.code_error_holder.pack(fill="x")

        self.confirm_code_btn = ctk.CTkButton(
            frame, text=self.t("confirm_code_btn"), fg_color=WHITE, text_color=BLACK,
            hover_color="#dddddd", height=44, font=("Helvetica", 13, "bold"),
            command=self._on_confirm_code_clicked,
        )
        self.confirm_code_btn.pack(fill="x", pady=(10, 0))

    def _on_confirm_code_clicked(self):
        for w in self.code_error_holder.winfo_children():
            w.destroy()
        code = self.code_entry.get().strip()
        if not code:
            self._show_inline_error(self.code_error_holder, self.t("error_code"))
            return
        self.confirm_code_btn.configure(state="disabled", text=self.t("checking_code"))
        self.job_q.put(lambda: self._worker_confirm_code(code))

    def _worker_confirm_code(self, code):
        try:
            self.app_client.sign_in(self.pending_phone, self.sent_code_hash, code)
            self.out_q.put(("authorized",))
        except SessionPasswordNeeded:
            self.out_q.put(("need_password",))
        except Exception as e:
            self.out_q.put(("code_error", str(e)))

    # =========================================================
    # ЭКРАН 4 — пароль 2FA
    # =========================================================
    def show_password_screen(self):
        self.current_screen = "password"
        self._clear_content()
        frame = ctk.CTkFrame(self.content, fg_color="transparent")
        self._slide_in(frame)

        ctk.CTkLabel(frame, text=self.t("password_title"), font=("Helvetica", 16, "bold"), text_color=WHITE).pack(anchor="w", pady=(0, 4))
        ctk.CTkLabel(frame, text=self.t("password_hint"), font=FONT_BODY, text_color=FG_MUTED, wraplength=460, justify="left").pack(anchor="w", pady=(0, 16))

        self.password_entry = ctk.CTkEntry(frame, placeholder_text=self.t("password_ph"), fg_color=BG_INPUT,
                                            border_color=BORDER, text_color=FG, height=42, show="•")
        self.password_entry.pack(fill="x", pady=(0, 16))

        self.password_error_holder = ctk.CTkFrame(frame, fg_color="transparent")
        self.password_error_holder.pack(fill="x")

        self.confirm_password_btn = ctk.CTkButton(
            frame, text=self.t("confirm_password_btn"), fg_color=WHITE, text_color=BLACK,
            hover_color="#dddddd", height=44, font=("Helvetica", 13, "bold"),
            command=self._on_confirm_password_clicked,
        )
        self.confirm_password_btn.pack(fill="x", pady=(10, 0))

    def _on_confirm_password_clicked(self):
        for w in self.password_error_holder.winfo_children():
            w.destroy()
        password = self.password_entry.get()
        if not password:
            self._show_inline_error(self.password_error_holder, self.t("error_password"))
            return
        self.confirm_password_btn.configure(state="disabled")
        self.job_q.put(lambda: self._worker_confirm_password(password))

    def _worker_confirm_password(self, password):
        try:
            self.app_client.check_password(password)
            self.out_q.put(("authorized",))
        except Exception as e:
            self.out_q.put(("password_error", str(e)))

    # =========================================================
    # ЭКРАН 5 — настройки поиска
    # =========================================================
    def show_settings_screen(self):
        self.current_screen = "settings"
        self._clear_content()
        frame = ctk.CTkFrame(self.content, fg_color="transparent")
        self._slide_in(frame)

        ctk.CTkLabel(frame, text=self.t("settings_title"), font=("Helvetica", 16, "bold"), text_color=WHITE).pack(anchor="w", pady=(0, 16))

        ctk.CTkLabel(frame, text=self.t("mode_label"), font=FONT_SMALL, text_color=FG_MUTED).pack(anchor="w")
        self.mode_var = ctk.StringVar(value="both")
        mode_row = ctk.CTkFrame(frame, fg_color="transparent")
        mode_row.pack(fill="x", pady=(4, 16))
        modes = [("dict", self.t("mode_dict")), ("syllable", self.t("mode_syllable")),
                 ("both", self.t("mode_both")), ("list", self.t("mode_list"))]
        for value, label in modes:
            ctk.CTkRadioButton(
                mode_row, text=label, value=value, variable=self.mode_var,
                fg_color=WHITE, border_color=BORDER, text_color=FG,
                command=self._on_mode_change,
            ).pack(side="left", padx=(0, 14))
        self.mode_row_ref = mode_row

        self.list_entry = ctk.CTkEntry(frame, placeholder_text=self.t("list_hint"), fg_color=BG_INPUT,
                                        border_color=BORDER, text_color=FG, height=40)

        len_row = ctk.CTkFrame(frame, fg_color="transparent")
        len_row.pack(fill="x", pady=(0, 16))
        ctk.CTkLabel(len_row, text=self.t("length_label"), font=FONT_SMALL, text_color=FG_MUTED).pack(anchor="w")

        self.min_len_var = ctk.IntVar(value=4)
        self.max_len_var = ctk.IntVar(value=6)
        self.len_label = ctk.CTkLabel(len_row, text="4 – 6", font=FONT_MONO, text_color=WHITE)
        self.len_label.pack(anchor="w", pady=(4, 4))

        min_slider_row = ctk.CTkFrame(len_row, fg_color="transparent")
        min_slider_row.pack(fill="x", pady=(2, 2))
        ctk.CTkLabel(min_slider_row, text="min", font=FONT_SMALL, text_color=FG_MUTED, width=30).pack(side="left")
        self.min_slider = ctk.CTkSlider(min_slider_row, from_=3, to=6, number_of_steps=3,
                                         button_color=WHITE, button_hover_color="#dddddd",
                                         progress_color=WHITE, fg_color=BG_INPUT,
                                         command=self._on_len_slider_change, variable=self.min_len_var)
        self.min_slider.pack(fill="x", side="left", expand=True)

        max_slider_row = ctk.CTkFrame(len_row, fg_color="transparent")
        max_slider_row.pack(fill="x", pady=(2, 0))
        ctk.CTkLabel(max_slider_row, text="max", font=FONT_SMALL, text_color=FG_MUTED, width=30).pack(side="left")
        self.max_slider = ctk.CTkSlider(max_slider_row, from_=3, to=6, number_of_steps=3,
                                         button_color=WHITE, button_hover_color="#dddddd",
                                         progress_color=WHITE, fg_color=BG_INPUT,
                                         command=self._on_len_slider_change, variable=self.max_len_var)
        self.max_slider.pack(fill="x", side="left", expand=True)

        num_row = ctk.CTkFrame(frame, fg_color="transparent")
        num_row.pack(fill="x", pady=(0, 16))

        limit_col = ctk.CTkFrame(num_row, fg_color="transparent")
        limit_col.pack(side="left", fill="x", expand=True, padx=(0, 8))
        ctk.CTkLabel(limit_col, text=self.t("limit_label"), font=FONT_SMALL, text_color=FG_MUTED).pack(anchor="w")
        self.limit_entry = ctk.CTkEntry(limit_col, fg_color=BG_INPUT, border_color=BORDER, text_color=FG, height=38)
        self.limit_entry.insert(0, "100")
        self.limit_entry.pack(fill="x", pady=(4, 0))

        delay_col = ctk.CTkFrame(num_row, fg_color="transparent")
        delay_col.pack(side="left", fill="x", expand=True, padx=(8, 0))
        ctk.CTkLabel(delay_col, text=self.t("delay_label"), font=FONT_SMALL, text_color=FG_MUTED).pack(anchor="w")
        self.delay_entry = ctk.CTkEntry(delay_col, fg_color=BG_INPUT, border_color=BORDER, text_color=FG, height=38)
        self.delay_entry.insert(0, "1.0")
        self.delay_entry.pack(fill="x", pady=(4, 0))

        btn_row = ctk.CTkFrame(frame, fg_color="transparent")
        btn_row.pack(fill="x", pady=(10, 0))
        ctk.CTkButton(
            btn_row, text=self.t("back_btn"), fg_color="transparent", border_width=1,
            border_color=BORDER, text_color=FG, hover_color=BG_PANEL, height=44,
            command=self.show_credentials_screen,
        ).pack(side="left", fill="x", expand=True, padx=(0, 8))

        ctk.CTkButton(
            btn_row, text=self.t("start_btn"), fg_color=WHITE, text_color=BLACK,
            hover_color="#dddddd", height=44, font=("Helvetica", 13, "bold"),
            command=self._on_start_clicked,
        ).pack(side="left", fill="x", expand=True, padx=(8, 0))

        self._on_mode_change()

    def _on_mode_change(self):
        if self.mode_var.get() == "list":
            self.list_entry.pack(fill="x", pady=(0, 16), after=self.mode_row_ref)
        else:
            self.list_entry.pack_forget()

    def _on_len_slider_change(self, _value=None):
        lo = int(self.min_len_var.get())
        hi = int(self.max_len_var.get())
        if lo > hi:
            hi = lo
            self.max_len_var.set(hi)
        self.len_label.configure(text=f"{lo} – {hi}")

    def _on_start_clicked(self):
        mode = self.mode_var.get()
        try:
            limit = int(self.limit_entry.get().strip() or "100")
        except ValueError:
            limit = 100
        try:
            delay = float(self.delay_entry.get().strip() or "1.0")
        except ValueError:
            delay = 1.0
        min_len = int(self.min_len_var.get())
        max_len = max(min_len, int(self.max_len_var.get()))
        words = self.list_entry.get().strip() if mode == "list" else None

        settings = {
            "mode": mode, "min_len": min_len, "max_len": max_len,
            "limit": limit, "delay": delay, "words": words,
        }
        self.show_results_screen(settings=settings)

    # =========================================================
    # ЭКРАН 6 — результаты
    # =========================================================
    def show_results_screen(self, settings=None, rebuild_only=False):
        self.current_screen = "results"
        if settings is not None:
            self._active_settings = settings
        self._clear_content()

        frame = ctk.CTkFrame(self.content, fg_color="transparent")
        self._slide_in(frame)

        top_row = ctk.CTkFrame(frame, fg_color="transparent")
        top_row.pack(fill="x", pady=(0, 10))
        ctk.CTkLabel(top_row, text=self.t("results_title"), font=("Helvetica", 16, "bold"), text_color=WHITE).pack(side="left")
        self.stop_btn = ctk.CTkButton(
            top_row, text=self.t("stop_btn"), fg_color="transparent", border_width=1,
            border_color=BORDER, text_color=FG, hover_color=BG_PANEL, width=100, height=32,
            command=self._on_stop_clicked,
        )
        self.stop_btn.pack(side="right")

        self.status_label = ctk.CTkLabel(frame, text=self.t("status_idle"), font=FONT_SMALL, text_color=FG_MUTED)
        self.status_label.pack(anchor="w", pady=(0, 8))

        self.progress = ctk.CTkProgressBar(frame, progress_color=WHITE, fg_color=BG_INPUT, height=6)
        self.progress.set(0)
        self.progress.pack(fill="x", pady=(0, 16))

        self.results_scroll = ctk.CTkScrollableFrame(frame, fg_color=BG_PANEL, corner_radius=10)
        self.results_scroll.pack(fill="both", expand=True)

        self._placeholder_label = ctk.CTkLabel(
            self.results_scroll, text=self.t("no_results_yet"), font=FONT_SMALL,
            text_color=FG_MUTED, wraplength=440, justify="left",
        )
        self._placeholder_label.pack(pady=20)

        self._result_rows = []
        self._checked_count = 0
        self._total_count = 0

        if not rebuild_only:
            self.stop_flag.clear()
            self.job_q.put(lambda: self._worker_search(self._active_settings))

    def _on_stop_clicked(self):
        self.stop_flag.set()
        self.stop_btn.configure(state="disabled")

    def _worker_search(self, settings):
        mode = settings["mode"]
        min_len, max_len, limit = settings["min_len"], settings["max_len"], settings["limit"]
        filtered = core.prepare_candidates(
            mode, min_len, max_len, limit, settings.get("words")
        )
        bot_token = core.get_setting("TG_BOT_TOKEN")
        notify_chat_ids = core.parse_notify_chat_ids(
            core.get_setting("TG_NOTIFY_CHAT_IDS") or core.get_setting("TG_NOTIFY_CHAT_ID")
        )

        total = len(filtered)
        self.out_q.put(("search_total", total))

        for i, username in enumerate(filtered, 1):
            if self.stop_flag.is_set():
                self.out_q.put(("search_stopped", i))
                return
            available = core.check_username(self.app_client, username, self.stop_flag)
            if self.stop_flag.is_set():
                self.out_q.put(("search_stopped", i))
                return
            self.out_q.put(("search_result", i, total, username, available))
            if available is True:
                core.notify_available_username(bot_token, notify_chat_ids, username)
            if self.stop_flag.wait(settings["delay"]):
                self.out_q.put(("search_stopped", i))
                return

        self.out_q.put(("search_done", total))

    def _add_result_row(self, username, available):
        if self._placeholder_label is not None:
            self._placeholder_label.destroy()
            self._placeholder_label = None

        if available is True:
            mark, status_text, weight = "●", self.t("status_available"), "bold"
        elif available == "fragment":
            mark, status_text, weight = "○", self.t("status_fragment"), "normal"
        elif available is False:
            mark, status_text, weight = "·", self.t("status_taken"), "normal"
        else:
            mark, status_text, weight = "!", self.t("status_error"), "normal"

        row = ctk.CTkFrame(self.results_scroll, fg_color="transparent")
        row.pack(fill="x", padx=8, pady=3)

        text_color = WHITE if available in (True, "fragment") else FG_MUTED
        ctk.CTkLabel(row, text=mark, font=("Helvetica", 14), text_color=text_color, width=16).pack(side="left")
        ctk.CTkLabel(row, text=f"@{username}", font=(FONT_MONO[0], 13, weight), text_color=text_color, width=180, anchor="w").pack(side="left")
        ctk.CTkLabel(row, text=status_text, font=FONT_SMALL, text_color=FG_MUTED).pack(side="left", padx=(6, 0))

        if available in (True, "fragment"):
            copy_btn = ctk.CTkButton(
                row, text=self.t("copy_btn"), width=70, height=24, fg_color="transparent",
                border_width=1, border_color=BORDER, text_color=FG, hover_color=BG_PANEL,
                font=("Helvetica", 10),
            )
            copy_btn.configure(command=lambda u=username, b=copy_btn: self._copy_username(u, b))
            copy_btn.pack(side="right")

            # мягкая вспышка при появлении новой находки
            self._flash(row)

    def _flash(self, widget, step=0):
        colors = ["#2a2a2a", "#3a3a3a", "#2a2a2a", BG_PANEL]
        if step < len(colors):
            try:
                widget.configure(fg_color=colors[step])
            except Exception:
                return
            self.after(90, lambda: self._flash(widget, step + 1))
        else:
            try:
                widget.configure(fg_color="transparent")
            except Exception:
                pass

    def _copy_username(self, username, button):
        self.clipboard_clear()
        self.clipboard_append(f"@{username}")
        button.configure(text=self.t("copied_btn"))
        self.after(1200, lambda: button.configure(text=self.t("copy_btn")))

    # ---- animated progress bar ----
    def _animate_progress_to(self, target, current=None):
        if current is None:
            current = self.progress.get()
        step = (target - current) / 6
        if abs(target - current) < 0.005:
            self.progress.set(target)
            return
        new_val = current + step
        self.progress.set(new_val)
        self.after(16, lambda: self._animate_progress_to(target, new_val))

    # =========================================================
    # Обработка сообщений от рабочего потока
    # =========================================================
    def _poll_queue(self):
        try:
            while True:
                msg = self.out_q.get_nowait()
                kind = msg[0]

                if kind == "connect_error":
                    self.connect_btn.configure(state="normal", text=self.t("connect_btn"))
                    self._show_inline_error(self.cred_error_holder, self.t("error_generic", msg=msg[1]))

                elif kind == "authorized":
                    self.show_settings_screen()

                elif kind == "need_phone":
                    self.show_phone_screen()

                elif kind == "phone_error":
                    self.send_code_btn.configure(state="normal", text=self.t("send_code_btn"))
                    self._show_inline_error(self.phone_error_holder, self.t("error_generic", msg=msg[1]))

                elif kind == "need_code":
                    self.show_code_screen()

                elif kind == "code_error":
                    self.confirm_code_btn.configure(state="normal", text=self.t("confirm_code_btn"))
                    self._show_inline_error(self.code_error_holder, self.t("error_generic", msg=msg[1]))

                elif kind == "need_password":
                    self.show_password_screen()

                elif kind == "password_error":
                    self.confirm_password_btn.configure(state="normal", text=self.t("confirm_password_btn"))
                    self._show_inline_error(self.password_error_holder, self.t("error_generic", msg=msg[1]))

                elif kind == "search_total":
                    self._total_count = msg[1]

                elif kind == "search_result":
                    _, i, total, username, available = msg
                    self._checked_count = i
                    self.status_label.configure(text=self.t("status_running", username=username))
                    self._animate_progress_to(i / total if total else 0)
                    self._add_result_row(username, available)

                elif kind == "search_done":
                    total = msg[1]
                    self.status_label.configure(text=self.t("status_done", n=total))
                    self._animate_progress_to(1.0)
                    self.stop_btn.configure(state="disabled")

                elif kind == "search_stopped":
                    self.status_label.configure(text=self.t("status_stopped"))
                    self.stop_btn.configure(state="disabled")

                elif kind == "fatal_error":
                    print(f"[fatal] {msg[1]}")

        except queue.Empty:
            pass
        finally:
            self.after(80, self._poll_queue)


if __name__ == "__main__":
    app = App()
    app.mainloop()
