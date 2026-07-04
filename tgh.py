#!/usr/bin/env python3
"""
Telegram Username Hunter
=========================
Ищет короткие, "красивые" (не набор случайных букв), СВОБОДНЫЕ юзернеймы
для Telegram: без цифр, без заглавных букв, длина на выбор (3-6 символов).

Проверка доступности идёт через официальный метод Telegram API
account.CheckUsername (библиотека Pyrogram) — точный ответ от самого
Telegram, а не догадки по парсингу t.me.

Если библиотека pyrogram не установлена, скрипт попробует поставить её
сам через pip при запуске.

ПОЛУЧЕНИЕ api_id / api_hash
----------------------------
    1. Зайти на https://my.telegram.org -> API development tools
    2. Создать приложение, скопировать api_id и api_hash

При первом запуске Pyrogram попросит номер телефона и код из Telegram —
это нужно один раз, дальше используется сохранённая сессия (файл .session).

ЗАПУСК
------
Без аргументов - интерактивный режим (задаст вопросы прямо в консоли):
    python tg_username_hunter.py

С аргументами - управление напрямую:
    export TG_API_ID=123456
    export TG_API_HASH=abcdef0123456789abcdef0123456789
    python tg_username_hunter.py --mode both --min-len 3 --max-len 6 --limit 200
"""

import importlib
import subprocess
import sys


def ensure_package(pip_name: str, import_name: str = None):
    """Импортирует пакет, а если его нет - ставит через pip и импортирует снова."""
    import_name = import_name or pip_name
    try:
        return importlib.import_module(import_name)
    except ImportError:
        print(f"[setup] Библиотека '{pip_name}' не найдена, устанавливаю через pip...")
        try:
            subprocess.check_call([sys.executable, "-m", "pip", "install", "--quiet", pip_name])
        except subprocess.CalledProcessError:
            print(f"Не удалось установить '{pip_name}' автоматически. "
                  f"Установите вручную: pip install {pip_name}")
            sys.exit(1)
        return importlib.import_module(import_name)


pyrogram_mod = ensure_package("pyrogram")
Client = pyrogram_mod.Client
from pyrogram.raw.functions.account import CheckUsername  # noqa: E402
from pyrogram.errors import FloodWait, UsernameInvalid, RPCError  # noqa: E402

import argparse
import os
import random
import re
import shutil
import time
from pathlib import Path


# ---------------------------------------------------------------------------
# Источники кандидатов (всё строго в нижнем регистре, без цифр)
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

VOWELS = "aeiou"
CONSONANTS = "bcdfghjklmnpqrstvwxyz"


def gen_syllable_candidates(min_len: int, max_len: int, limit: int):
    """Генерирует произносимые псевдослова (не рандомный набор букв)."""
    seen = set()
    attempts = 0
    max_attempts = limit * 60
    shapes = ["CV", "CVC", "CVCV", "CVCVC", "VCV", "VCVC"]
    while len(seen) < limit and attempts < max_attempts:
        attempts += 1
        shape = random.choice(shapes)
        word = ""
        for ch in shape:
            pool = VOWELS if ch == "V" else CONSONANTS
            word += random.choice(pool)
        while len(word) < min_len:
            shape2 = random.choice(["CV", "VC"])
            for ch in shape2:
                pool = VOWELS if ch == "V" else CONSONANTS
                word += random.choice(pool)
        word = word[:max_len]
        if min_len <= len(word) <= max_len and word not in seen:
            seen.add(word)
            yield word


def gen_dict_candidates(min_len: int, max_len: int, limit: int):
    words = [w for w in DICT_WORDS if min_len <= len(w) <= max_len]
    random.shuffle(words)
    for w in words[:limit]:
        yield w


def looks_beautiful(username: str) -> bool:
    """Отсекает наборы букв без гласных / с длинными сериями согласных."""
    u = username.lower()
    if not any(c in VOWELS for c in u):
        return False
    run_c = run_v = 0
    for c in u:
        if c in CONSONANTS:
            run_c += 1
            run_v = 0
        elif c in VOWELS:
            run_v += 1
            run_c = 0
        if run_c > 3 or run_v > 2:
            return False
    return True


def no_digits_no_uppercase(username: str) -> bool:
    """Требование пользователя: без цифр и без заглавных букв."""
    return username == username.lower() and not any(c.isdigit() for c in username)


TELEGRAM_USERNAME_RE = re.compile(r"^[a-zA-Z][a-zA-Z0-9_]{2,31}$")


def is_valid_telegram_format(username: str) -> bool:
    if not TELEGRAM_USERNAME_RE.match(username):
        return False
    if "__" in username or username.endswith("_"):
        return False
    return True


# ---------------------------------------------------------------------------
# Проверка доступности через Telegram API
# ---------------------------------------------------------------------------

def check_username(app, username: str):
    """
    True   = свободен напрямую
    False  = занят
    "fragment" = свободен, но только через аукцион Fragment (fragment.com)
    None   = неверный формат или Telegram вернул непредвиденную ошибку (пропускаем)
    """
    try:
        return app.invoke(CheckUsername(username=username))
    except UsernameInvalid:
        return None
    except FloodWait as e:
        wait = int(getattr(e, "value", None) or getattr(e, "x", 5)) + 1
        print(f"  [flood wait] Telegram просит подождать {wait} сек...")
        time.sleep(wait)
        return check_username(app, username)
    except RPCError as e:
        msg = str(e)
        if "USERNAME_PURCHASE_AVAILABLE" in msg:
            return "fragment"
        print(f"  [пропуск] {username}: Telegram вернул ошибку ({msg})")
        return None


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

    footer_plain = "by v0idk1d | help: @rlxmsa | powered by Claude AI"
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

    choice = ask_choice()
    if choice == "0":
        print(f"{GREEN}Выход.{RESET}")
        sys.exit(0)

    mode = {"1": "dict", "2": "syllable", "3": "both", "4": "list"}[choice]

    words = None
    if mode == "list":
        words = input(f"{GREEN}Введите ники через запятую: {RESET}").strip()
        return argparse.Namespace(
            api_id=None, api_hash=None, session="tg_hunter_session",
            mode=mode, words=words, min_len=3, max_len=6,
            limit=100, delay=1.0, output="found.txt",
        )

    def ask_int(prompt, valid_range):
        while True:
            raw = input(f"{GREEN}{prompt} ({'-'.join(map(str, valid_range))}): {RESET}").strip()
            if raw.isdigit() and int(raw) in valid_range:
                return int(raw)
            print(f"Введите число из диапазона {valid_range[0]}-{valid_range[-1]}.")

    min_len = ask_int("Минимальная длина ника", range(3, 7))
    max_len = ask_int("Максимальная длина ника", range(min_len, 7))

    limit_raw = input(f"{GREEN}Сколько кандидатов проверить за прогон (по умолчанию 100): {RESET}").strip()
    limit = int(limit_raw) if limit_raw.isdigit() else 100

    delay_raw = input(f"{GREEN}Пауза между запросами в секундах (по умолчанию 1.0): {RESET}").strip()
    try:
        delay = float(delay_raw) if delay_raw else 1.0
    except ValueError:
        delay = 1.0

    return argparse.Namespace(
        api_id=None, api_hash=None, session="tg_hunter_session",
        mode=mode, words=words, min_len=min_len, max_len=max_len,
        limit=limit, delay=delay, output="found.txt",
    )


def run(args):
    api_id = args.api_id or os.environ.get("TG_API_ID")
    api_hash = args.api_hash or os.environ.get("TG_API_HASH")
    if not api_id or not api_hash:
        api_id = api_id or input("Введите api_id (см. https://my.telegram.org): ").strip()
        api_hash = api_hash or input("Введите api_hash: ").strip()
    if not api_id or not api_hash:
        print("api_id/api_hash обязательны.")
        sys.exit(1)

    if args.mode == "dict":
        candidates = list(gen_dict_candidates(args.min_len, args.max_len, args.limit * 5))
    elif args.mode == "syllable":
        candidates = list(gen_syllable_candidates(args.min_len, args.max_len, args.limit * 5))
    elif args.mode == "list":
        if not args.words:
            print("Для --mode list нужно передать --words слово1,слово2,...")
            sys.exit(1)
        candidates = [w.strip() for w in args.words.split(",") if w.strip()]
    else:
        candidates = list(gen_dict_candidates(args.min_len, args.max_len, args.limit * 3)) + \
                     list(gen_syllable_candidates(args.min_len, args.max_len, args.limit * 3))

    filtered = []
    for c in candidates:
        if not is_valid_telegram_format(c):
            continue
        if not no_digits_no_uppercase(c):
            continue
        if args.mode != "list" and not looks_beautiful(c):
            continue
        filtered.append(c)

    random.shuffle(filtered)
    if args.mode != "list":
        filtered = filtered[: args.limit]

    if not filtered:
        print("Нет кандидатов, подходящих под критерии. Смягчите --min-len/--max-len.")
        return

    print(f"Кандидатов к проверке: {len(filtered)}")
    if args.min_len < 5:
        print("Внимание: юзернеймы короче 5 символов обычным пользователям "
              "напрямую недоступны — они распределяются через аукцион Fragment "
              "(fragment.com) либо резервируются для Premium-аккаунтов в "
              "отдельных случаях. Проверка всё равно покажет реальный статус.")

    app = Client(args.session, api_id=int(api_id), api_hash=api_hash)

    found = []
    found_fragment = []
    out_path = Path(args.output)
    fragment_path = out_path.with_name(out_path.stem + "_fragment" + out_path.suffix)

    with app:
        with out_path.open("a", encoding="utf-8") as out_f, \
             fragment_path.open("a", encoding="utf-8") as frag_f:
            for i, username in enumerate(filtered, 1):
                available = check_username(app, username)
                if available is True:
                    status = "СВОБОДЕН"
                elif available == "fragment":
                    status = "свободен, но только через Fragment (аукцион)"
                elif available is False:
                    status = "занят"
                else:
                    status = "пропущен"
                print(f"[{i}/{len(filtered)}] {username:<20} -> {status}")

                if available is True:
                    found.append(username)
                    out_f.write(username + "\n")
                    out_f.flush()
                elif available == "fragment":
                    found_fragment.append(username)
                    frag_f.write(username + "\n")
                    frag_f.flush()

                time.sleep(args.delay)

    print("\n" + "=" * 40)
    if found:
        print(f"Найдено свободных ников: {len(found)} (сохранено в {out_path})")
        for u in found:
            print(f"  @{u}")
    else:
        print("Свободных ников не найдено в этом прогоне. Попробуйте другой --mode "
              "или увеличьте --limit.")

    if found_fragment:
        print(f"\nЕщё {len(found_fragment)} ников свободны только через аукцион "
              f"Fragment (fragment.com), сохранено в {fragment_path}:")
        for u in found_fragment:
            print(f"  @{u}")


def parse_args():
    p = argparse.ArgumentParser(description="Поиск коротких свободных Telegram-юзернеймов")
    p.add_argument("--api-id", help="Telegram api_id (или переменная окружения TG_API_ID)")
    p.add_argument("--api-hash", help="Telegram api_hash (или переменная окружения TG_API_HASH)")
    p.add_argument("--session", default="tg_hunter_session", help="имя файла сессии")
    p.add_argument("--mode", choices=["dict", "syllable", "both", "list"], default="both")
    p.add_argument("--words", help="через запятую, только для --mode list")
    p.add_argument("--min-len", type=int, choices=range(3, 7), default=4,
                    help="минимальная длина ника, от 3 до 6")
    p.add_argument("--max-len", type=int, choices=range(3, 7), default=6,
                    help="максимальная длина ника, от 3 до 6")
    p.add_argument("--limit", type=int, default=100, help="сколько кандидатов проверить за прогон")
    p.add_argument("--delay", type=float, default=1.0, help="пауза между запросами, сек")
    p.add_argument("--output", default="found.txt", help="файл для сохранения найденных свободных ников")
    return p.parse_args()


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
    credit = "help: @rlxmsa   ·   powered by Claude AI"

    out = [""]
    out.append(_center(made_by, f"{DIM}{made_by}{RESET}", term_width))
    for plain, colored in zip(nick_rows, nick_lines):
        out.append(_center(plain, colored, term_width))
    out.append("")
    out.append(_center(credit, f"{DIM}{credit}{RESET}", term_width))
    out.append("")
    return "\n".join(out)


if __name__ == "__main__":
    print(_colored_banner())
    if len(sys.argv) == 1:
        settings = interactive_settings()
    else:
        settings = parse_args()
    if settings.min_len > settings.max_len:
        settings.min_len, settings.max_len = settings.max_len, settings.min_len
    run(settings)
