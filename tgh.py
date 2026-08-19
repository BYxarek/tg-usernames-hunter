#!/usr/bin/env python3
"""
Telegram Username Hunter
=========================
Ищет короткие, "красивые" (не набор случайных букв), СВОБОДНЫЕ юзернеймы
для Telegram: длина 5–32 символа, с настраиваемыми цифрами и символом `_`.

Проверка доступности идёт через официальный метод Telegram API
account.CheckUsername (библиотека Pyrofork) — точный ответ от самого
Telegram, а не догадки по парсингу t.me.

Зависимости устанавливаются заранее командой pip install -r requirements.txt.

ПОЛУЧЕНИЕ api_id / api_hash
----------------------------
    1. Зайти на https://my.telegram.org -> API development tools
    2. Создать приложение, скопировать api_id и api_hash

При первом запуске Pyrofork попросит номер телефона и код из Telegram —
это нужно один раз, дальше используется сохранённая сессия (файл .session).

ЗАПУСК
------
Без аргументов - интерактивный режим (задаст вопросы прямо в консоли):
    python tgh.py

С аргументами - управление напрямую:
    export TG_API_ID=123456
    export TG_API_HASH=abcdef0123456789abcdef0123456789
    python tgh.py --mode both --min-len 5 --max-len 12 --limit 200 --min-score 70
"""

import importlib
import ast
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
import threading
import queue
import logging
from logging.handlers import RotatingFileHandler


def require_package(pip_name: str, import_name: str = None):
    """Импортирует пакет или завершает работу с командой установки."""
    import_name = import_name or pip_name
    try:
        return importlib.import_module(import_name)
    except ImportError:
        LOGGER.exception("Не установлена зависимость %s (import %s)", pip_name, import_name)
        requirements = os.path.join(os.path.dirname(__file__), "requirements.txt")
        print(f"Библиотека '{pip_name}' не установлена. Выполните: "
              f"{sys.executable} -m pip install -r {requirements}")
        sys.exit(1)


CONFIG_NAMES = ("TG_API_ID", "TG_API_HASH", "TG_BOT_TOKEN", "TG_NOTIFY_CHAT_IDS")


# ---------------------------------------------------------------------------
# Единый журнал ошибок CLI / GUI
# ---------------------------------------------------------------------------

def log_path() -> str:
    """Возвращает путь к общему ротационному логу приложения."""
    if os.name == "nt":
        base = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
        directory = os.path.join(base, "TGUsernameHunter", "logs")
    else:
        state_home = os.environ.get("XDG_STATE_HOME") or os.path.join(os.path.expanduser("~"), ".local", "state")
        directory = os.path.join(state_home, "tg_username_hunter")
    os.makedirs(directory, exist_ok=True)
    return os.path.join(directory, "tgh.log")


def setup_logging() -> logging.Logger:
    """Настраивает один logger с ротацией; повторные вызовы безопасны."""
    logger = logging.getLogger("tg_username_hunter")
    logger.setLevel(logging.INFO)
    logger.propagate = False
    if not any(getattr(handler, "_tgh_handler", False) for handler in logger.handlers):
        try:
            handler = RotatingFileHandler(
                log_path(), maxBytes=2 * 1024 * 1024, backupCount=5,
                encoding="utf-8",
            )
            handler._tgh_handler = True
            handler.setFormatter(logging.Formatter(
                "%(asctime)s | %(levelname)s | %(threadName)s | %(name)s | %(message)s",
                "%Y-%m-%d %H:%M:%S",
            ))
            logger.addHandler(handler)
        except Exception:
            # Логирование не должно мешать запуску программы даже при проблемах с диском.
            pass
    return logger


LOGGER = setup_logging()


def install_exception_hooks():
    """Пишет необработанные исключения главного и фоновых потоков в общий лог."""
    old_sys_hook = sys.excepthook

    def sys_hook(exc_type, exc_value, exc_traceback):
        if issubclass(exc_type, KeyboardInterrupt):
            old_sys_hook(exc_type, exc_value, exc_traceback)
            return
        LOGGER.critical("Необработанное исключение", exc_info=(exc_type, exc_value, exc_traceback))
        old_sys_hook(exc_type, exc_value, exc_traceback)

    sys.excepthook = sys_hook

    if hasattr(threading, "excepthook"):
        old_thread_hook = threading.excepthook

        def thread_hook(args):
            if args.exc_type is not SystemExit:
                LOGGER.critical(
                    "Необработанное исключение в потоке %s",
                    getattr(args.thread, "name", "unknown"),
                    exc_info=(args.exc_type, args.exc_value, args.exc_traceback),
                )
            old_thread_hook(args)

        threading.excepthook = thread_hook


install_exception_hooks()


def config_path() -> str:
    base = os.path.dirname(sys.executable if getattr(sys, "frozen", False) else __file__)
    return os.path.join(base, "config.py")


def load_config(path: str = None) -> dict[str, str]:
    try:
        with open(path or config_path(), encoding="utf-8") as file:
            tree = ast.parse(file.read())
    except FileNotFoundError:
        return {}
    except (OSError, SyntaxError) as exc:
        LOGGER.warning("Не удалось прочитать config.py: %s", exc, exc_info=True)
        return {}

    values = {}
    for node in tree.body:
        if not isinstance(node, ast.Assign) or len(node.targets) != 1:
            continue
        target = node.targets[0]
        if not isinstance(target, ast.Name) or target.id not in CONFIG_NAMES:
            continue
        try:
            value = ast.literal_eval(node.value)
        except (ValueError, TypeError):
            continue
        if isinstance(value, (str, int)):
            values[target.id] = str(value).strip()
    return values


def save_config(values: dict[str, str], path: str = None):
    target = path or config_path()
    temporary = target + ".tmp"
    content = "# Telegram Username Hunter — local settings, do not commit.\n" + "".join(
        f"{name} = {str(values.get(name, '')).strip()!r}\n" for name in CONFIG_NAMES
    )
    with open(temporary, "w", encoding="utf-8", newline="\n") as file:
        file.write(content)
        file.flush()
        os.fsync(file.fileno())
    os.replace(temporary, target)


def get_setting(name: str) -> str | None:
    value = load_config().get(name)
    if value:
        return value
    value = os.environ.get(name)
    if value or os.name != "nt":
        return value
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment") as key:
            return winreg.QueryValueEx(key, name)[0]
    except OSError:
        return None


pyrogram_mod = require_package("pyrofork", "pyrogram")
Client = pyrogram_mod.Client
from pyrogram.raw.functions.account import CheckUsername  # noqa: E402
from pyrogram.errors import FloodWait, UsernameInvalid, RPCError  # noqa: E402

import argparse
import random
import re
import shutil
import time


# ---------------------------------------------------------------------------
# Источники кандидатов и scoring
# ---------------------------------------------------------------------------

DICT_WORDS = [
    "nova", "echo", "vibe", "flux", "aura", "halo", "ion", "orbit",
    "onyx", "myst", "gale", "rune", "arc", "flow", "glow", "quartz", "ash",
    "vex", "lume", "dawn", "dusk", "frost", "spark", "storm", "wave",
    "atlas", "comet", "ember", "haze", "jolt", "nero", "opal", "pixel",
    "raze", "sable", "tide", "void", "wisp", "zen", "axis", "bolt", "cove",
    "drift", "edge", "flare", "grid", "hive", "iris", "jade", "kite",
    "loop", "mist", "nest", "peak", "quill", "reef", "silo", "trek",
    "unit", "vale", "wick", "yarn", "zinc", "beam", "cliff", "dune",
    "flint", "glint", "howl", "isle", "jazz", "keen", "lynx", "mint",
    "nook", "pulse", "quest", "ridge", "spire", "tusk", "veil", "wren",
    "cocoa", "amber", "coral", "delta", "ferro", "gamma", "helix", "inca",
    "juno", "koda", "luna", "mira", "nyx", "orin", "puma", "ravi", "silva",
    "terra", "ultra", "verse", "willo", "xylo", "yuki", "zara",
    "leo", "rex", "fox", "sky", "sun", "ray", "ice", "fire", "sol", "kai",
    "ada", "eva", "ivy", "jet", "kim", "leo", "max", "nik", "oz",
]

# Узнаваемые английские основы, которые смешиваются со словарём и псевдословами.
# Это не список «гарантированно свободных» username — доступность всё равно
# определяется только Telegram API.
POPULAR_WORDS = [
    "alpha", "audio", "boost", "brand", "chat", "cloud", "code", "cosmos",
    "daily", "design", "digital", "dream", "future", "games", "gaming", "global",
    "light", "magic", "market", "media", "mobile", "money", "music", "network",
    "night", "omega", "online", "photo", "planet", "prime", "rocket", "smart",
    "social", "space", "sport", "store", "stream", "studio", "tech", "travel",
    "vector", "video", "world", "matrix", "signal", "vision", "motion", "creator",
]

# Короткие части используются только как разнообразные компоненты комбинаций.
# Намеренно нет одного доминирующего суффикса вроде `_io`.
COMBO_PARTS = [
    "lab", "hub", "go", "pro", "one", "now", "app", "box", "zone", "base",
    "wave", "fox", "zen", "neo", "max", "sky", "ray", "bit", "byte", "core",
]

VOWELS = "aeiou"
CONSONANTS = "bcdfghjklmnpqrstvwxyz"


def gen_syllable_candidates(min_len: int, max_len: int, limit: int,
                            allow_digits: bool = False, allow_underscore: bool = False):
    """Генерирует произносимые псевдослова и опционально добавляет цифры/`_`."""
    seen = set()
    attempts = 0
    max_attempts = max(limit * 100, 500)
    shapes = ["CV", "CVC", "CVCV", "CVCVC", "VCV", "VCVC"]

    while len(seen) < limit and attempts < max_attempts:
        attempts += 1
        word = ""
        while len(word) < min_len:
            shape = random.choice(shapes)
            for ch in shape:
                pool = VOWELS if ch == "V" else CONSONANTS
                word += random.choice(pool)
                if len(word) >= max_len:
                    break

        word = word[:max_len]
        if allow_digits and len(word) < max_len and random.random() < 0.28:
            pos = random.randint(1, len(word))
            word = word[:pos] + random.choice("0123456789") + word[pos:]
        if allow_underscore and len(word) < max_len and len(word) > 2 and random.random() < 0.22:
            pos = random.randint(1, len(word) - 1)
            word = word[:pos] + "_" + word[pos:]

        word = word[:max_len]
        if min_len <= len(word) <= max_len and word not in seen and is_valid_telegram_format(word):
            seen.add(word)
            yield word


def gen_dict_candidates(min_len: int, max_len: int, limit: int,
                        allow_digits: bool = False, allow_underscore: bool = False):
    """Смешивает популярные основы, словарь и разнообразные случайные комбинации.

    Генератор специально не обходит словарь сериями с одним и тем же суффиксом.
    Базовые слова перемешиваются, а дополнительные варианты собираются случайно
    из разных пар/частей; `_` и цифры добавляются только к части кандидатов.
    """
    pool = list(dict.fromkeys(POPULAR_WORDS + DICT_WORDS))
    random.shuffle(pool)
    seen = set()

    def emit(candidate: str):
        candidate = candidate.lower()
        if (candidate not in seen and min_len <= len(candidate) <= max_len
                and is_valid_telegram_format(candidate)):
            seen.add(candidate)
            return candidate
        return None

    # Сначала даём прямые узнаваемые слова в случайном порядке.
    direct = [word for word in pool if min_len <= len(word) <= max_len]
    random.shuffle(direct)
    for word in direct:
        candidate = emit(word)
        if candidate is not None:
            yield candidate
            if len(seen) >= limit:
                return

    # Затем создаём разнообразные комбинации вместо word_io, word_io, word_io...
    attempts = 0
    max_attempts = max(limit * 80, 800)
    all_parts = pool + COMBO_PARTS
    while len(seen) < limit and attempts < max_attempts:
        attempts += 1
        left = random.choice(pool)
        right = random.choice(all_parts)
        if left == right:
            continue

        style = random.choice(("concat", "concat", "short", "underscore", "digit"))
        if style == "underscore":
            if not allow_underscore:
                continue
            candidate = f"{left}_{right}"
        elif style == "digit":
            if not allow_digits:
                continue
            # Одна случайная цифра, а не последовательный перебор 0..9.
            candidate = f"{left}{random.choice('0123456789')}"
        elif style == "short":
            # Короткая случайная часть позволяет получать варианты вроде cloudneo,
            # pixelhub, novacore без повторяющегося общего хвоста.
            candidate = left + random.choice(COMBO_PARTS)
        else:
            candidate = left + right

        candidate = emit(candidate)
        if candidate is not None:
            yield candidate


def looks_beautiful(username: str) -> bool:
    """Быстрый фильтр читаемости до более точного scoring."""
    letters = "".join(c for c in username.lower() if c.isalpha())
    if not letters or not any(c in VOWELS for c in letters):
        return False
    run_c = run_v = 0
    for c in letters:
        if c in CONSONANTS:
            run_c += 1
            run_v = 0
        elif c in VOWELS:
            run_v += 1
            run_c = 0
        if run_c > 4 or run_v > 3:
            return False
    return True


def _score_base(username: str) -> str:
    """Возвращает смысловую основу username для lexical scoring."""
    u = username.lower().strip("_")
    if u.endswith("_bot"):
        u = u[:-4]
    elif u.endswith("bot") and len(u) > 3:
        u = u[:-3].rstrip("_")
    # Цифры и разделители не должны превращать известное слово в неизвестное.
    return "".join(c for c in u if c.isalpha())


def _lexical_score(username: str) -> int:
    """Оценивает узнаваемость основы, а не только её фонетику.

    Максимальные баллы получают реальные/популярные основы из словаря.
    Естественные комбинации двух известных частей получают немного меньше.
    Случайные псевдослова не получают lexical bonus, поэтому не могут
    пересечь высокий порог вроде 80 только за счёт чередования гласных.
    """
    base = _score_base(username)
    if not base:
        return 0

    known_words = set(DICT_WORDS) | set(POPULAR_WORDS) | set(COMBO_PARTS)
    if base in known_words:
        return 35

    # Комбинации вроде cloudneo / pixelhub / novacore.
    for split in range(2, len(base) - 1):
        left, right = base[:split], base[split:]
        if left in known_words and right in known_words:
            return 30

    # Чуть меньший бонус, если заметная известная основа дополнена короткой
    # частью. Это допускает брендовые варианты, но не поднимает случайный
    # набор букв до уровня 80+.
    for word in known_words:
        if len(word) >= 4 and (base.startswith(word) or base.endswith(word)):
            remainder = len(base) - len(word)
            if 1 <= remainder <= 3:
                return 15
    return 0


def score_username(username: str) -> int:
    """Оценивает username 0–100 с сильным весом лексической узнаваемости.

    Порог 80+ означает «узнаваемое слово/естественная комбинация», а не
    просто фонетически правдоподобную случайную строку.
    """
    u = username.lower()
    letters = [c for c in u if c.isalpha()]
    if not letters:
        return 0

    length = len(u)
    if length <= 8:
        length_score = 25
    elif length <= 12:
        length_score = 22
    elif length <= 16:
        length_score = 18
    elif length <= 24:
        length_score = 13
    else:
        length_score = 8

    vowel_ratio = sum(c in VOWELS for c in letters) / len(letters)
    balance_score = max(0, 15 - int(abs(vowel_ratio - 0.42) * 35))
    readability_score = 15 if looks_beautiful(u) else 3

    repeats = sum(1 for a, b in zip(u, u[1:]) if a == b)
    unique_ratio = len(set(letters)) / len(letters)
    variety_score = max(0, 10 - repeats * 3)
    if unique_ratio < 0.5:
        variety_score = max(0, variety_score - 4)

    lexical_score = _lexical_score(u)
    penalty = sum(c.isdigit() for c in u) * 3 + u.count("_") * 4
    score = length_score + balance_score + readability_score + variety_score + lexical_score - penalty
    return max(0, min(100, int(score)))


TELEGRAM_USERNAME_RE = re.compile(r"^[a-zA-Z][a-zA-Z0-9_]{4,31}$")


def is_valid_telegram_format(username: str) -> bool:
    if not TELEGRAM_USERNAME_RE.fullmatch(username):
        return False
    if "__" in username or username.endswith("_"):
        return False
    return True


def prepare_candidates(mode: str, min_len: int, max_len: int, limit: int,
                       words: str = None, allow_digits: bool = False,
                       allow_underscore: bool = False, min_score: int = 70,
                       bot_usernames: bool = False) -> list[str]:
    """Генерирует, валидирует, оценивает и сортирует кандидатов для CLI и GUI.

    При ``bot_usernames=True`` каждый кандидат нормализуется в username для бота
    с обязательным окончанием ``bot``. Если разрешён ``_``, часть сгенерированных
    вариантов получает форму ``name_bot``; один и тот же шаблон не используется
    последовательно для всего пула.
    """
    min_len = max(5, int(min_len))
    max_len = min(32, int(max_len))
    if min_len > max_len or limit < 0:
        return []
    if limit == 0:
        return []
    min_score = max(0, min(100, int(min_score)))

    if mode == "dict":
        candidates = list(gen_dict_candidates(min_len, max_len, limit * 8, allow_digits, allow_underscore))
    elif mode == "syllable":
        candidates = list(gen_syllable_candidates(min_len, max_len, limit * 8, allow_digits, allow_underscore))
    elif mode == "list":
        candidates = [word.strip() for word in (words or "").split(",") if word.strip()]
    elif mode == "both":
        candidates = list(gen_dict_candidates(min_len, max_len, limit * 5, allow_digits, allow_underscore))
        candidates += list(gen_syllable_candidates(min_len, max_len, limit * 5, allow_digits, allow_underscore))
    else:
        raise ValueError(f"Неизвестный режим: {mode}")

    if bot_usernames:
        bot_candidates = []
        for raw_candidate in candidates:
            candidate = raw_candidate.strip().lower()
            if candidate.endswith("bot"):
                bot_candidates.append(candidate)
                continue

            # Всегда создаём обычную форму namebot. При разрешённом `_`
            # дополнительно смешиваем часть name_bot, не превращая весь пул
            # в один повторяющийся шаблон.
            plain_limit = max_len - 3
            if plain_limit >= 1:
                base = candidate[:plain_limit].rstrip("_")
                if base:
                    bot_candidates.append(base + "bot")

            if mode != "list" and allow_underscore and random.random() < 0.35:
                separated_limit = max_len - 4
                if separated_limit >= 1:
                    base = candidate[:separated_limit].rstrip("_")
                    if base:
                        bot_candidates.append(base + "_bot")
        candidates = bot_candidates

    scored = {}
    for candidate in candidates:
        if candidate != candidate.lower():
            continue
        if not (min_len <= len(candidate) <= max_len):
            continue
        if not is_valid_telegram_format(candidate):
            continue
        if not allow_digits and any(c.isdigit() for c in candidate):
            continue
        if not allow_underscore and "_" in candidate:
            continue
        score = score_username(candidate)
        if bot_usernames and candidate.endswith("_bot"):
            # В bot-режиме разделитель перед обязательным suffix является
            # естественной формой имени, поэтому не штрафуем его как обычный `_`.
            score = min(100, score + 5)
        if score >= min_score:
            scored.setdefault(candidate, score)

    # Приоритет score сохраняется, но равные по score/длине варианты
    # перемешиваются. Это предотвращает визуально последовательные серии
    # однотипных username из-за алфавитной сортировки.
    ordered = list(scored)
    random.shuffle(ordered)
    ordered.sort(key=lambda name: (-scored[name], len(name)))

    if bot_usernames and allow_underscore:
        # Не даём scoring полностью вытеснить варианты name_bot из первых
        # результатов: смешиваем примерно один такой вариант на три namebot.
        separated = [name for name in ordered if name.endswith("_bot")]
        plain = [name for name in ordered if not name.endswith("_bot")]
        mixed = []
        while len(mixed) < limit and (plain or separated):
            for _ in range(3):
                if plain and len(mixed) < limit:
                    mixed.append(plain.pop(0))
            if separated and len(mixed) < limit:
                mixed.append(separated.pop(0))
            if not plain and separated:
                mixed.extend(separated[:limit - len(mixed)])
                break
            if not separated and plain:
                mixed.extend(plain[:limit - len(mixed)])
                break
        return mixed[:limit]

    return ordered[:limit]


def iter_candidates(mode: str, min_len: int, max_len: int, limit: int,
                    words: str = None, allow_digits: bool = False,
                    allow_underscore: bool = False, min_score: int = 70,
                    bot_usernames: bool = False, stop_event=None):
    """Yield candidates for a search run.

    ``limit > 0`` yields at most that many candidates. ``limit == 0`` means
    no check-count limit. In generated modes fresh randomized batches are
    produced until ``stop_event`` is set. ``list`` remains naturally finite
    and yields every unique item from the supplied list.
    """
    limit = int(limit)
    if limit < 0:
        raise ValueError("limit должен быть >= 0")

    if limit > 0:
        yield from prepare_candidates(
            mode, min_len, max_len, limit, words,
            allow_digits=allow_digits, allow_underscore=allow_underscore,
            min_score=min_score, bot_usernames=bot_usernames,
        )
        return

    # Custom lists have a natural end even when the user selected unlimited.
    if mode == "list":
        requested = max(1, len([w for w in (words or "").split(",") if w.strip()]))
        yield from prepare_candidates(
            mode, min_len, max_len, requested, words,
            allow_digits=allow_digits, allow_underscore=allow_underscore,
            min_score=min_score, bot_usernames=bot_usernames,
        )
        return

    seen = set()
    empty_rounds = 0
    batch_size = 250
    while not stop_event or not stop_event.is_set():
        batch = prepare_candidates(
            mode, min_len, max_len, batch_size, words,
            allow_digits=allow_digits, allow_underscore=allow_underscore,
            min_score=min_score, bot_usernames=bot_usernames,
        )
        new_items = [name for name in batch if name not in seen]
        if not new_items:
            empty_rounds += 1
            # Re-randomize aggressively when a batch collided with prior output.
            # If many independent batches still produce nothing, the selected
            # constraints are effectively exhausted/impossible (e.g. syllable
            # mode with lexical min_score=80). End instead of spinning CPU forever.
            if empty_rounds in {8, 16}:
                batch_size = min(2000, batch_size * 2)
            if empty_rounds >= 24:
                LOGGER.info("Unlimited candidate stream exhausted by filters: mode=%s min_score=%s", mode, min_score)
                return
            continue
        empty_rounds = 0
        for name in new_items:
            if stop_event and stop_event.is_set():
                return
            seen.add(name)
            yield name


# ---------------------------------------------------------------------------
# Проверка доступности через Telegram API
# ---------------------------------------------------------------------------

def check_username(app, username: str, stop_event=None):
    """
    True   = свободен напрямую
    False  = занят
    "unavailable" = синтаксически похож на username, но Telegram не разрешает его назначить
    "fragment" = свободен, но только через аукцион Fragment (fragment.com)
    None   = остановка или реальная ошибка Telegram API (пропускаем)
    """
    while not stop_event or not stop_event.is_set():
        try:
            return app.invoke(CheckUsername(username=username))
        except UsernameInvalid as exc:
            # USERNAME_INVALID is a valid Telegram API result, not an application failure.
            # Such names may be reserved/otherwise non-assignable even when their local
            # syntax looks correct, so keep them out of the "skipped/error" bucket.
            LOGGER.debug("@%s недоступен: USERNAME_INVALID: %s", username, exc)
            return "unavailable"
        except FloodWait as exc:
            wait = int(getattr(exc, "value", None) or getattr(exc, "x", 5)) + 1
            LOGGER.warning("FloodWait при проверке @%s: ожидание %s сек; %s", username, wait, exc)
            print(f"  [flood wait] Telegram просит подождать {wait} сек...")
            if stop_event:
                if stop_event.wait(wait):
                    LOGGER.info("Проверка @%s остановлена пользователем во время FloodWait", username)
                    return None
            else:
                time.sleep(wait)
        except RPCError as exc:
            msg = str(exc)
            error_text = msg.upper()
            if "USERNAME_PURCHASE_AVAILABLE" in error_text:
                return "fragment"
            if "USERNAME_OCCUPIED" in error_text:
                return False
            if "USERNAME_INVALID" in error_text:
                return "unavailable"
            LOGGER.error("Пропуск @%s: Telegram RPCError: %s", username, msg, exc_info=True)
            print(f"  [пропуск] {username}: Telegram вернул ошибку ({msg})")
            return None
        except Exception as exc:
            LOGGER.exception("Пропуск @%s: непредвиденная ошибка проверки: %s", username, exc)
            print(f"  [пропуск] {username}: непредвиденная ошибка ({exc})")
            return None
    return None


class BotAPIError(RuntimeError):
    def __init__(self, description: str, error_code: int | None = None, retry_after: int | None = None):
        super().__init__(description)
        self.error_code = error_code
        self.retry_after = retry_after


def _bot_api(token: str, method: str, **data):
    request = urllib.request.Request(
        f"https://api.telegram.org/bot{token}/{method}",
        data=urllib.parse.urlencode(data).encode(),
    )
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            payload = json.load(response)
    except urllib.error.HTTPError as e:
        try:
            payload = json.loads(e.read())
            description = payload.get("description", f"HTTP {e.code}")
            retry_after = payload.get("parameters", {}).get("retry_after")
            error_code = payload.get("error_code", e.code)
        except Exception:
            description, retry_after, error_code = f"HTTP {e.code}", None, e.code
        LOGGER.error("Bot API HTTP error: code=%s description=%s retry_after=%s", error_code, description, retry_after)
        raise BotAPIError(description, error_code, retry_after) from None
    except urllib.error.URLError as e:
        LOGGER.error("Bot API network error: %s", e.reason, exc_info=True)
        raise BotAPIError(f"ошибка сети: {e.reason}") from None
    if not payload.get("ok"):
        LOGGER.error("Bot API returned ok=false: code=%s description=%s", payload.get("error_code"), payload.get("description"))
        raise BotAPIError(
            payload.get("description", "Telegram Bot API error"),
            payload.get("error_code"),
            payload.get("parameters", {}).get("retry_after"),
        )
    return payload.get("result")


def parse_notify_chat_ids(chat_ids: str = None) -> list[str]:
    return list(dict.fromkeys(
        chat_id.strip() for chat_id in (chat_ids or "").split(",")
        if chat_id.strip().isdigit()
    ))


_bot_rate_lock = threading.Lock()
_bot_last_sent: dict[str, float] = {}


def _respect_bot_chat_rate_limit(chat_id: str):
    # Telegram recommends staying at or below ~1 message/second in a single chat.
    with _bot_rate_lock:
        now = time.monotonic()
        wait = 1.05 - (now - _bot_last_sent.get(chat_id, 0.0))
        if wait > 0:
            time.sleep(wait)
        _bot_last_sent[chat_id] = time.monotonic()


def notify_available_username(token: str, chat_ids: list[str], username: str) -> bool:
    if not token or not chat_ids:
        return False
    sent = False
    for chat_id in chat_ids:
        for attempt in range(2):
            try:
                _respect_bot_chat_rate_limit(chat_id)
                _bot_api(token, "sendMessage", chat_id=chat_id,
                         text=f"Найден свободный Telegram username: @{username}")
                sent = True
                break
            except BotAPIError as e:
                if e.error_code == 429 and e.retry_after is not None and attempt == 0:
                    LOGGER.warning("Bot API Flood/429 для chat_id=%s, retry_after=%s", chat_id, e.retry_after)
                    time.sleep(max(1, int(e.retry_after)))
                    continue
                LOGGER.error("Не удалось отправить уведомление @%s chat_id=%s: %s", username, chat_id, e, exc_info=True)
                print(f"[bot] Не удалось отправить @{username} пользователю {chat_id}: {e}")
                break
            except Exception as e:
                LOGGER.exception("Непредвиденная ошибка уведомления @%s chat_id=%s: %s", username, chat_id, e)
                print(f"[bot] Не удалось отправить @{username} пользователю {chat_id}: {e}")
                break
    return sent


class BotNotificationWorker:
    """Отдельная очередь уведомлений, чтобы Bot API не блокировал scanner."""
    def __init__(self, token: str, chat_ids: list[str], on_error=None):
        self.token = token
        self.chat_ids = list(chat_ids)
        self.on_error = on_error
        self._queue = queue.Queue()
        self._closed = threading.Event()
        self._thread = threading.Thread(target=self._run, name="bot-notifier", daemon=True)
        self._thread.start()

    def submit(self, username: str):
        if self.token and self.chat_ids and not self._closed.is_set():
            self._queue.put(username)

    def _run(self):
        while True:
            item = self._queue.get()
            try:
                if item is None:
                    return
                try:
                    notify_available_username(self.token, self.chat_ids, item)
                except Exception as exc:
                    LOGGER.exception("Ошибка notification worker для @%s: %s", item, exc)
                    if self.on_error:
                        self.on_error(str(exc))
                    else:
                        print(f"[bot] Ошибка уведомления @{item}: {exc}")
            finally:
                self._queue.task_done()

    def flush(self):
        self._queue.join()

    def close(self, wait: bool = True):
        if self._closed.is_set():
            return
        self._closed.set()
        if wait:
            self.flush()
        self._queue.put(None)
        if wait:
            self._thread.join(timeout=15)


GREEN = "\033[92m"
BOLD = "\033[1m"
DIM = "\033[2m"
RESET = "\033[0m"

AMBER = "\033[93m"


def _term_width(default=80):
    try:
        return shutil.get_terminal_size(fallback=(default, 24)).columns
    except Exception:
        return default


def _center(line_plain, colored_line, term_width):
    pad = max((term_width - len(line_plain)) // 2, 0)
    return " " * pad + colored_line


def build_menu():
    """Собирает меню с заголовком и описаниями, отцентрованное по ширине терминала."""
    term_width = _term_width()

    title = "TG USERNAME HUNTER"
    subtitle = "выбери режим поиска"

    items = [
        ("1", "Поиск по словарю", "короткие реальные слова"),
        ("2", "Генератор слогов", "произносимые псевдослова"),
        ("3", "Оба режима", "словарь + слоги вместе"),
        ("4", "Свой список", "проверить конкретные ники"),
        None,  # разделитель
        ("0", "Выход", ""),
    ]

    label_col = max(len(f"[{num}] {t}") for item in items if item for num, t, _ in [item])

    def plain_row(num, t, desc):
        label = f"[{num}] {t}"
        return f"  {label}".ljust(label_col + 4) + desc

    content_width = max(
        [len(title) + 4, len(subtitle) + 4] +
        [len(plain_row(num, t, desc)) for item in items if item for num, t, desc in [item]]
    )

    def build_line(num, t, desc):
        label = f"[{num}] {t}"
        plain_full = plain_row(num, t, desc).ljust(content_width)
        colored = plain_full.replace(f"[{num}]", f"{AMBER}[{num}]{RESET}{GREEN}", 1)
        return plain_full, f"{GREEN}{colored}{RESET}"

    top = "╔" + "═" * (content_width + 2) + "╗"
    bottom = "╚" + "═" * (content_width + 2) + "╝"
    sep = "╟" + "─" * (content_width + 2) + "╢"

    title_plain = title.center(content_width)
    subtitle_plain = subtitle.center(content_width)

    lines = [
        (top, f"{GREEN}{top}{RESET}"),
        (f"║ {title_plain} ║", f"{GREEN}║{RESET} {GREEN}{BOLD}{title_plain}{RESET} {GREEN}║{RESET}"),
        (f"║ {subtitle_plain} ║", f"{GREEN}║{RESET} {DIM}{subtitle_plain}{RESET} {GREEN}║{RESET}"),
        (sep, f"{GREEN}{sep}{RESET}"),
    ]

    for item in items:
        if item is None:
            blank = " " * content_width
            lines.append((f"║ {blank} ║", f"{GREEN}║{RESET} {blank} {GREEN}║{RESET}"))
            continue
        num, t, desc = item
        plain_full, colored_full = build_line(num, t, desc)
        lines.append((f"║ {plain_full} ║", f"{GREEN}║{RESET} {colored_full} {GREEN}║{RESET}"))

    lines.append((bottom, f"{GREEN}{bottom}{RESET}"))

    out = [_center(plain, colored, term_width) for plain, colored in lines]

    footer_plain = "by v0idk1d | github.com/BYxarek | help: @rlxmsa | powered by Claude AI"
    footer_colored = f"{DIM}{footer_plain}{RESET}"
    out.append(_center(footer_plain, footer_colored, term_width))

    return "\n" + "\n".join(out) + "\n"


def interactive_settings():
    print(build_menu())

    def ask_choice():
        while True:
            raw = input(f"{GREEN}Выбор пункта меню: {RESET}").strip()
            if raw in {"0", "1", "2", "3", "4"}:
                return raw
            print("Введите число от 0 до 4.")

    def ask_int(prompt, low, high, default):
        raw = input(f"{GREEN}{prompt} ({low}-{high}, по умолчанию {default}): {RESET}").strip()
        if not raw:
            return default
        try:
            value = int(raw)
        except ValueError:
            return default
        return max(low, min(high, value))

    def ask_bool(prompt, default=False):
        suffix = "Y/n" if default else "y/N"
        raw = input(f"{GREEN}{prompt} [{suffix}]: {RESET}").strip().lower()
        if not raw:
            return default
        return raw in {"y", "yes", "д", "да", "1"}

    choice = ask_choice()
    if choice == "0":
        print(f"{GREEN}Выход.{RESET}")
        sys.exit(0)

    mode = {"1": "dict", "2": "syllable", "3": "both", "4": "list"}[choice]
    words = input(f"{GREEN}Введите ники через запятую: {RESET}").strip() if mode == "list" else None
    min_len = ask_int("Минимальная длина ника", 5, 32, 5)
    max_len = ask_int("Максимальная длина ника", min_len, 32, max(12, min_len))
    limit = ask_int("Сколько кандидатов проверить (0 = без лимита)", 0, 10000, 100)
    min_score = ask_int("Минимальная оценка красоты", 0, 100, 70)

    delay_raw = input(f"{GREEN}Пауза между запросами в секундах (по умолчанию 1.0): {RESET}").strip()
    try:
        delay = max(0.0, float(delay_raw) if delay_raw else 1.0)
    except ValueError:
        delay = 1.0

    return argparse.Namespace(
        api_id=None, api_hash=None, session="tg_hunter_session",
        mode=mode, words=words, min_len=min_len, max_len=max_len,
        limit=limit, delay=delay, min_score=min_score,
        allow_digits=ask_bool("Разрешить цифры 0-9"),
        allow_underscore=ask_bool("Разрешить символ _"),
    )


def run(args):
    LOGGER.info("CLI запуск: mode=%s min_len=%s max_len=%s limit=%s delay=%s min_score=%s digits=%s underscore=%s",
                args.mode, args.min_len, args.max_len, args.limit, args.delay, args.min_score,
                args.allow_digits, args.allow_underscore)
    api_id = args.api_id or get_setting("TG_API_ID")
    api_hash = args.api_hash or get_setting("TG_API_HASH")
    if not api_id or not api_hash:
        api_id = api_id or input("Введите api_id (см. https://my.telegram.org): ").strip()
        api_hash = api_hash or input("Введите api_hash: ").strip()
    if not api_id or not api_hash:
        LOGGER.error("CLI: отсутствуют обязательные api_id/api_hash")
        print("api_id/api_hash обязательны.")
        sys.exit(1)
    if not str(api_id).isdigit():
        LOGGER.error("CLI: api_id имеет неверный формат")
        print("api_id должен быть числом.")
        sys.exit(1)
    if args.mode == "list" and not args.words:
        LOGGER.error("CLI: mode=list запущен без --words")
        print("Для --mode list нужно передать --words слово1,слово2,...")
        sys.exit(1)

    stop_event = threading.Event()
    candidate_iter = iter_candidates(
        args.mode, args.min_len, args.max_len, args.limit, args.words,
        allow_digits=args.allow_digits, allow_underscore=args.allow_underscore,
        min_score=args.min_score, stop_event=stop_event,
    )
    if args.limit == 0:
        print("Кандидатов к проверке: без лимита (Ctrl+C для остановки)")
    else:
        print(f"Максимум кандидатов к проверке: {args.limit}")
    print(f"Лог ошибок: {log_path()}")
    app = Client(args.session, api_id=int(api_id), api_hash=api_hash)
    bot_token = get_setting("TG_BOT_TOKEN")
    notify_chat_ids = parse_notify_chat_ids(
        get_setting("TG_NOTIFY_CHAT_IDS") or get_setting("TG_NOTIFY_CHAT_ID")
    )
    notifier = BotNotificationWorker(bot_token, notify_chat_ids)
    found = []
    found_fragment = []

    try:
        with app:
            for i, username in enumerate(candidate_iter, 1):
                available = check_username(app, username)
                if available is True:
                    status = "СВОБОДЕН"
                    found.append(username)
                    notifier.submit(username)
                elif available == "fragment":
                    status = "свободен, но только через Fragment (аукцион)"
                    found_fragment.append(username)
                elif available is False:
                    status = "занят"
                elif available == "unavailable":
                    status = "недоступен для назначения"
                else:
                    status = "пропущен"
                    LOGGER.warning("CLI: @%s пропущен при проверке", username)
                total_label = "∞" if args.limit == 0 else str(args.limit)
                print(f"[{i}/{total_label}] {username:<32} score={score_username(username):>3} -> {status}")
                if args.delay > 0:
                    time.sleep(args.delay)
    except KeyboardInterrupt:
        stop_event.set()
        LOGGER.info("CLI: поиск остановлен пользователем")
        print("\nПоиск остановлен пользователем.")
    finally:
        notifier.close(wait=True)

    print("\n" + "=" * 40)
    if found:
        print(f"Найдено свободных ников: {len(found)}; уведомления отправлены через бота.")
        for username in found:
            print(f"  @{username}")
    else:
        print("Свободных ников не найдено в этом прогоне.")
    if found_fragment:
        print(f"\nЕщё {len(found_fragment)} ников доступны только через Fragment:")
        for username in found_fragment:
            print(f"  @{username}")


def parse_args():
    p = argparse.ArgumentParser(description="Поиск свободных Telegram-юзернеймов")
    p.add_argument("--api-id", help="Telegram api_id (или TG_API_ID)")
    p.add_argument("--api-hash", help="Telegram api_hash (или TG_API_HASH)")
    p.add_argument("--session", default="tg_hunter_session", help="имя файла сессии")
    p.add_argument("--mode", choices=["dict", "syllable", "both", "list"], default="both")
    p.add_argument("--words", help="через запятую, только для --mode list")
    p.add_argument("--min-len", type=int, choices=range(5, 33), default=5, help="минимальная длина ника, 5–32")
    p.add_argument("--max-len", type=int, choices=range(5, 33), default=12, help="максимальная длина ника, 5–32")
    p.add_argument("--limit", type=int, default=100, help="сколько кандидатов проверить; 0 = без лимита")
    p.add_argument("--delay", type=float, default=1.0, help="пауза между запросами, сек >= 0")
    p.add_argument("--allow-digits", action="store_true", help="разрешить цифры 0-9")
    p.add_argument("--allow-underscore", action="store_true", help="разрешить символ _")
    p.add_argument("--min-score", type=int, default=70, help="минимальная оценка красоты 0–100")
    args = p.parse_args()
    if not 0 <= args.limit <= 10000:
        LOGGER.error("CLI: неверный --limit=%s", args.limit)
        p.error("--limit должен быть в диапазоне 0–10000; 0 = без лимита")
    if args.delay < 0:
        LOGGER.error("CLI: неверный --delay=%s", args.delay)
        p.error("--delay не может быть отрицательным")
    if not 0 <= args.min_score <= 100:
        LOGGER.error("CLI: неверный --min-score=%s", args.min_score)
        p.error("--min-score должен быть в диапазоне 0–100")
    return args


PIXEL_FONT = {
    "A": [" ### ", "#   #", "#####", "#   #", "#   #"],
    "B": ["#### ", "#   #", "#### ", "#   #", "#### "],
    "C": [" ####", "#    ", "#    ", "#    ", " ####"],
    "D": ["#### ", "#   #", "#   #", "#   #", "#### "],
    "E": ["#####", "#    ", "#### ", "#    ", "#####"],
    "H": ["#   #", "#   #", "#####", "#   #", "#   #"],
    "I": ["#####", "  #  ", "  #  ", "  #  ", "#####"],
    "K": ["#   #", "#  # ", "###  ", "#  # ", "#   #"],
    "L": ["#    ", "#    ", "#    ", "#    ", "#####"],
    "O": [" ### ", "#   #", "#   #", "#   #", " ### "],
    "P": ["#### ", "#   #", "#### ", "#    ", "#    "],
    "R": ["#### ", "#   #", "#### ", "#  # ", "#   #"],
    "U": ["#   #", "#   #", "#   #", "#   #", " ### "],
    "V": ["#   #", "#   #", "#   #", " # # ", "  #  "],
    "W": ["#   #", "#   #", "# # #", "## ##", "#   #"],
    "Y": ["#   #", " # # ", "  #  ", "  #  ", "  #  "],
    "0": [" ### ", "#   #", "#   #", "#   #", " ### "],
    "1": ["  #  ", " ##  ", "  #  ", "  #  ", "#####"],
    " ": ["   ", "   ", "   ", "   ", "   "],
}


def render_pixel_word(word):
    """Строит крупные читаемые буквы из ASCII-блоков для заданного слова."""
    rows = ["", "", "", "", ""]
    for ch in word.upper():
        glyph = PIXEL_FONT.get(ch, PIXEL_FONT[" "])
        for i in range(5):
            rows[i] += glyph[i] + " "
    return [row.rstrip() for row in rows]


def _colored_banner():
    term_width = _term_width()

    nick_rows = render_pixel_word("V0IDK1D")
    nick_lines = [f"{GREEN}{BOLD}{row}{RESET}" for row in nick_rows]

    made_by = "made by"
    credit = "github.com/BYxarek   ·   help: @rlxmsa   ·   powered by Claude AI"

    out = [""]
    out.append(_center(made_by, f"{DIM}{made_by}{RESET}", term_width))
    for plain, colored in zip(nick_rows, nick_lines):
        out.append(_center(plain, colored, term_width))
    out.append("")
    out.append(_center(credit, f"{DIM}{credit}{RESET}", term_width))
    out.append("")
    return "\n".join(out)


if __name__ == "__main__":
    LOGGER.info("Запуск CLI; log=%s", log_path())
    print(_colored_banner())
    if len(sys.argv) == 1:
        settings = interactive_settings()
    else:
        settings = parse_args()
    if settings.min_len > settings.max_len:
        settings.min_len, settings.max_len = settings.max_len, settings.min_len
    run(settings)
