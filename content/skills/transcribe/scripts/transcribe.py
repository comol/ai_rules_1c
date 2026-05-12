"""
Транскрибация аудио и видео через Gemini API.

Два режима:
- Generic (по умолчанию): verbatim-транскрипция речи с таймкодами
- Analyze-UI (--analyze-ui, только видео): саммари + детальный лог + скриншоты + транскрипция

Установка:
    pip install google-genai python-dotenv

Использование:
    python transcribe.py "запись.mp3"
    python transcribe.py "встреча.mp4" --analyze-ui
    python transcribe.py "подкаст.wav" --with-summary --output-dir "./результат"

API-ключ: переменная окружения GEMINI_API_KEY или файл .env
(ищет в ~/.claude/skills/transcribe/.env, ~/.claude/skills/video-transcribe/.env, затем в cwd).
"""

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from dotenv import load_dotenv

# Загрузка .env: приоритет transcribe > video-transcribe > cwd
_home = Path.home()
for _env_path in [
    _home / ".claude" / "skills" / "transcribe" / ".env",
    _home / ".claude" / "skills" / "video-transcribe" / ".env",
]:
    if _env_path.exists():
        load_dotenv(_env_path)
        break
load_dotenv()  # cwd/.env как fallback

from google import genai

VIDEO_EXTENSIONS = {".mp4", ".mkv", ".webm", ".avi", ".mov"}
AUDIO_EXTENSIONS = {".mp3", ".wav", ".ogg", ".m4a", ".flac", ".aac", ".wma"}
ALL_EXTENSIONS = VIDEO_EXTENSIONS | AUDIO_EXTENSIONS

# === Промпты: Generic ===

PROMPT_TRANSCRIBE = """Транскрибируй всю речь из этой записи дословно.

Требования:
1. Таймкоды [MM:SS] каждые 30-60 секунд или при смене спикера
2. Идентификация спикеров (Спикер 1, Спикер 2, или по имени если названо)
3. Значимые неречевые звуки в скобках: [смех], [пауза], [шум]
4. Сохраняй оригинальный язык записи
5. Дословная транскрипция, не пересказ

Отвечай на языке записи. Формат - Markdown с таймкодами."""

PROMPT_SUMMARY_GENERIC = """Составь структурированный протокол встречи по этой записи.

Формат протокола (строго соблюдай структуру и заголовки):

---

## Цель встречи
Один абзац - зачем собрались, что хотели обсудить/решить.

## Участники
Список участников с именами и ролями (если определяются из записи).

## Ключевые темы и фокус обсуждения
Нумерованный список основных тем. Каждая тема - заголовок и 1-2 предложения пояснения что именно обсуждали.

## Решения
Нумерованный список конкретных решений, принятых на встрече. Каждое решение - отдельным пунктом, подробно.

## Открытые вопросы
Нумерованный список вопросов, которые остались нерешенными и требуют уточнения. Для каждого - пояснение почему отложено или что нужно для решения.

## Задачи
Группируй по ответственному. Для каждого человека - нумерованный список задач с описанием.
Формат:
### Имя (Роль)
1. Описание задачи. Срок: дата или "не определен"
2. ...

---

Отвечай на языке записи. Формат - по делу, без воды, но с достаточной детализацией чтобы человек не присутствовавший на встрече понял контекст."""

# === Промпты: Analyze-UI (анализ интерфейсов) ===

PROMPT_UI_SUMMARY = """Ты анализируешь видеозапись рабочей встречи, на которой демонстрируются бизнес-процессы
и интерфейсы программ (1С и другие).

Составь структурированный протокол встречи. Формат (строго соблюдай структуру и заголовки):

---

## Цель встречи
Один абзац - зачем собрались, что хотели обсудить/решить.

## Участники
Список участников с именами и ролями (если определяются из записи).

## Ключевые темы и фокус обсуждения
Нумерованный список основных тем. Каждая тема - заголовок и 1-2 предложения пояснения.
Отдельно отметь какие системы и интерфейсы демонстрировались.

## Решения
Нумерованный список конкретных решений, принятых на встрече. Каждое решение - отдельным пунктом, подробно.

## Открытые вопросы
Нумерованный список нерешенных вопросов. Для каждого - пояснение почему отложено или что нужно для решения.

## Задачи
Группируй по ответственному. Для каждого человека - нумерованный список задач.
Формат:
### Имя (Роль)
1. Описание задачи. Срок: дата или "не определен"
2. ...

---

Отвечай на русском языке. Формат - по делу, без воды, но с достаточной детализацией.
Таймкоды в формате MM:SS."""

PROMPT_UI_DETAILED = """Ты анализируешь видеозапись рабочей встречи, на которой демонстрируются бизнес-процессы
и интерфейсы программ (1С и другие).

Сделай МАКСИМАЛЬНО ДЕТАЛЬНЫЙ пошаговый анализ видео. Не обобщай - описывай каждое действие.

## Требования к детализации:

### 1. Пошаговый хронологический лог (основная часть)
Для каждого значимого момента (каждые 10-30 секунд или при смене экрана/действия):
- **[MM:SS]** Что именно происходит на экране
- Какое окно/форма открыта (полное название из заголовка)
- Какие поля видны и какие значения в них заполнены (читай весь текст с экрана)
- Какие кнопки нажимаются, какие пункты меню выбираются
- Куда переходит пользователь (навигационный путь)
- Что говорят участники в этот момент (если слышно речь - перескажи суть)

### 2. Распознанные данные
- Все названия справочников, документов, регистров, отчетов которые видны
- Все значения полей которые можно прочитать с экрана (наименования, числа, даты)
- Структура меню и навигации которая видна
- Названия колонок таблиц, значения в ячейках

### 3. Речь участников
- Кто говорит и что именно обсуждается (пересказ близко к тексту, не обобщение)
- Вопросы, ответы, решения, замечания - каждое отдельно с таймкодом
- Если кто-то что-то объясняет - передай суть объяснения подробно

### 4. Итоги
- Общая тема встречи
- Список всех показанных интерфейсов/форм
- Принятые решения и открытые вопросы
- Участники и их роли

Отвечай на русском языке. Будь максимально подробным - лучше написать слишком много, чем упустить детали.
Таймкоды в формате MM:SS."""

PROMPT_SCREENSHOTS = """Проанализируй видео и определи ключевые моменты, для которых нужно сделать скриншоты.

Выбери моменты где:
- Показан новый интерфейс/форма/документ (первое появление)
- Виден важный результат (отчет, таблица с данными)
- Демонстрируется ключевое действие (заполнение формы, настройка)

Верни ТОЛЬКО JSON-массив объектов, без markdown-форматирования, без ```json блоков:
[
  {"time": "MM:SS", "description": "Краткое описание что на скриншоте"}
]

Выбери 5-15 ключевых моментов, равномерно распределенных по видео."""


# === Утилиты ===

def upload_file(client, path):
    """Загрузка файла в Gemini File API с workaround для кириллических имен."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir) / f"media{path.suffix}"
        shutil.copy2(path, tmp_path)
        media_file = client.files.upload(file=str(tmp_path))
    return media_file


def wait_for_processing(client, media_file):
    """Ожидание обработки файла."""
    while media_file.state.name == "PROCESSING":
        print("  Обработка файла...")
        time.sleep(5)
        media_file = client.files.get(name=media_file.name)
    if media_file.state.name == "FAILED":
        print(f"Ошибка обработки файла: {media_file.state}")
        sys.exit(1)
    return media_file


def get_media_duration(path):
    """Получение длительности медиафайла в секундах через ffprobe."""
    try:
        result = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1", str(path)],
            capture_output=True, text=True, timeout=30,
        )
        return float(result.stdout.strip())
    except Exception as e:
        print(f"  Предупреждение: не удалось определить длительность ({e}). Разбивка длинных файлов отключена.")
        return 0


def split_media(path, max_duration=3600):
    """Разбивка медиафайла на части если превышает max_duration (сек)."""
    duration = get_media_duration(path)
    if duration <= max_duration:
        return [path], [0]

    parts = []
    offsets = []
    num_parts = int(duration // max_duration) + 1
    part_duration = int(duration // num_parts) + 1
    tmp_dir = tempfile.mkdtemp()

    print(f"  Файл {duration/60:.0f} мин > {max_duration/60:.0f} мин лимита, разбиваю на {num_parts} частей...")

    for i in range(num_parts):
        start = i * part_duration
        out_path = Path(tmp_dir) / f"part_{i+1}{path.suffix}"
        subprocess.run(
            ["ffmpeg", "-y", "-ss", str(start), "-i", str(path),
             "-t", str(part_duration), "-c", "copy", str(out_path)],
            capture_output=True, timeout=120,
        )
        if out_path.exists():
            parts.append(out_path)
            offsets.append(start)
            end = min(start + part_duration, int(duration))
            print(f"  Часть {i+1}: {start//60}:{start%60:02d} - {end//60}:{end%60:02d}")

    return parts, offsets


def offset_timestamps_in_text(text, offset_seconds):
    """Сдвиг таймкодов [MM:SS] в тексте на offset_seconds."""
    if offset_seconds == 0:
        return text

    def replace_ts(match):
        mm, ss = int(match.group(1)), int(match.group(2))
        total = mm * 60 + ss + offset_seconds
        new_mm, new_ss = divmod(total, 60)
        return f"[{new_mm:02d}:{new_ss:02d}]"

    return re.sub(r"\[(\d{1,2}):(\d{2})\]", replace_ts, text)


def extract_screenshots(video_path, timestamps, output_dir):
    """Извлечение скриншотов через ffmpeg по таймкодам."""
    screenshots_dir = output_dir / "screenshots"
    screenshots_dir.mkdir(exist_ok=True)

    extracted = []
    for i, item in enumerate(timestamps, 1):
        ts = item["time"]
        desc = item["description"]
        out_file = screenshots_dir / f"{i:02d}_{ts.replace(':', '-')}.png"

        parts = ts.split(":")
        seconds = int(parts[0]) * 60 + int(parts[1])

        try:
            subprocess.run(
                [
                    "ffmpeg", "-y",
                    "-ss", str(seconds),
                    "-i", str(video_path),
                    "-frames:v", "1",
                    "-q:v", "2",
                    str(out_file),
                ],
                capture_output=True,
                timeout=30,
            )
            if out_file.exists():
                extracted.append({"file": out_file.name, "time": ts, "description": desc})
                print(f"  [{ts}] {out_file.name} - {desc}")
        except Exception as e:
            print(f"  [{ts}] Ошибка: {e}")

    return extracted


def insert_screenshots_into_text(text, extracted):
    """Вставка ссылок на скриншоты в детальный анализ рядом с соответствующими таймкодами."""
    if not extracted:
        return text

    for s in reversed(extracted):
        ts = s["time"]
        img_md = f"\n\n![{s['description']}](screenshots/{s['file']})\n"

        pattern = re.compile(
            r"^(.*?" + re.escape(ts) + r".*?)$",
            re.MULTILINE,
        )
        match = pattern.search(text)
        if match:
            insert_pos = match.end()
            text = text[:insert_pos] + img_md + text[insert_pos:]
        else:
            text += f"\n\n**[{ts}]** {s['description']}{img_md}"

    return text


def offset_screenshot_times(timestamps, offset_seconds):
    """Сдвиг таймкодов скриншотов на offset_seconds."""
    if offset_seconds == 0:
        return timestamps
    result = []
    for item in timestamps:
        parts = item["time"].split(":")
        total = int(parts[0]) * 60 + int(parts[1]) + offset_seconds
        mm, ss = divmod(total, 60)
        result.append({"time": f"{mm:02d}:{ss:02d}", "description": item["description"]})
    return result


def is_video(path):
    return path.suffix.lower() in VIDEO_EXTENSIONS


def is_audio(path):
    return path.suffix.lower() in AUDIO_EXTENSIONS


# === Генерация через Gemini ===

def generate(client, media_file, prompt):
    """Вызов Gemini с медиафайлом и промптом."""
    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=[media_file, prompt],
    )
    if not response.text:
        raise RuntimeError(
            f"Gemini вернул пустой ответ (возможно, сработал фильтр безопасности). "
            f"finish_reason: {getattr(response.candidates[0], 'finish_reason', 'unknown') if response.candidates else 'no candidates'}"
        )
    return response.text


def transcribe_generic(client, media_file, time_offset=0):
    """Generic-транскрипция: verbatim речь с таймкодами."""
    text = generate(client, media_file, PROMPT_TRANSCRIBE)
    return offset_timestamps_in_text(text, time_offset)


def generate_summary_generic(client, media_file):
    """Generic-саммари."""
    return generate(client, media_file, PROMPT_SUMMARY_GENERIC)


def analyze_ui_single(client, media_file, video_path, output_dir, part_label="", time_offset=0):
    """Analyze-UI: саммари + детальный + скриншоты для одного видео."""
    suffix = f" (часть {part_label})" if part_label else ""

    # 1. Саммари
    print(f"\n  [UI 1/4] Генерация саммари{suffix}...")
    summary_text = generate(client, media_file, PROMPT_UI_SUMMARY)

    # 2. Детальный анализ
    print(f"  [UI 2/4] Генерация детального анализа{suffix}...")
    detailed_text = generate(client, media_file, PROMPT_UI_DETAILED)
    detailed_text = offset_timestamps_in_text(detailed_text, time_offset)

    # 3. Скриншоты
    print(f"  [UI 3/4] Определение скриншотов{suffix}...")
    screenshots_response = generate(client, media_file, PROMPT_SCREENSHOTS)

    timestamps = []
    try:
        text = screenshots_response.strip()
        text = re.sub(r"^```json\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
        timestamps = json.loads(text)
        timestamps = offset_screenshot_times(timestamps, time_offset)
    except (json.JSONDecodeError, ValueError) as e:
        print(f"    Не удалось распарсить таймкоды: {e}")

    extracted = []
    if timestamps:
        print(f"    Извлекаю {len(timestamps)} скриншотов...")
        extracted = extract_screenshots(video_path, timestamps, output_dir)
        detailed_text = insert_screenshots_into_text(detailed_text, extracted)

    # 4. Generic-транскрипция
    print(f"  [UI 4/4] Генерация транскрипции{suffix}...")
    transcript_text = transcribe_generic(client, media_file, time_offset)

    return summary_text, detailed_text, transcript_text


# === Основная логика ===

def process_file(path, output_dir, mode, with_summary, output_format):
    """Обработка одного файла."""
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print("API-ключ не найден. Варианты:")
        print("  1. Файл ~/.claude/skills/transcribe/.env с GEMINI_API_KEY=...")
        print("  2. Файл ~/.claude/skills/video-transcribe/.env с GEMINI_API_KEY=...")
        print("  3. Файл .env в текущей директории")
        print("  4. Переменная окружения: set GEMINI_API_KEY=ваш_ключ")
        sys.exit(1)

    size_mb = path.stat().st_size / (1024 * 1024)
    media_type = "видео" if is_video(path) else "аудио"
    print(f"Файл: {path.name} ({size_mb:.1f} MB, {media_type})")

    output_dir.mkdir(parents=True, exist_ok=True)
    client = genai.Client(api_key=api_key)

    # Разбивка длинных файлов
    parts, offsets = split_media(path)

    if mode == "analyze-ui":
        _process_analyze_ui(client, path, parts, offsets, output_dir)
    else:
        _process_generic(client, path, parts, offsets, output_dir, with_summary, output_format)

    # Очистка временных файлов
    for part_path in parts:
        if part_path != path:
            part_path.unlink(missing_ok=True)
            try:
                part_path.parent.rmdir()
            except OSError:
                pass

    print(f"\n{'=' * 60}")
    print(f"Готово! Результаты в: {output_dir}")
    print(f"{'=' * 60}")


def _process_generic(client, path, parts, offsets, output_dir, with_summary, output_format):
    """Generic-режим: транскрипция (+ опционально саммари)."""
    if len(parts) == 1:
        print("Загрузка файла в Gemini...")
        media_file = upload_file(client, path)
        print(f"Загружено: {media_file.name}")
        media_file = wait_for_processing(client, media_file)

        print("\n  Генерация транскрипции...")
        transcript_text = transcribe_generic(client, media_file)

        summary_text = None
        if with_summary:
            print("  Генерация саммари...")
            summary_text = generate_summary_generic(client, media_file)

        _cleanup_file(client, media_file)
    else:
        all_transcripts = []
        all_summaries = []

        for i, (part_path, offset) in enumerate(zip(parts, offsets), 1):
            print(f"\n{'='*40} Часть {i}/{len(parts)} {'='*40}")
            print("Загрузка части в Gemini...")
            media_file = upload_file(client, part_path)
            print(f"Загружено: {media_file.name}")
            media_file = wait_for_processing(client, media_file)

            print("  Генерация транскрипции...")
            t_text = transcribe_generic(client, media_file, offset)
            all_transcripts.append(f"## Часть {i} (с {offset//60}:{offset%60:02d})\n\n{t_text}")

            if with_summary:
                print("  Генерация саммари...")
                s_text = generate_summary_generic(client, media_file)
                all_summaries.append(f"## Часть {i}\n\n{s_text}")

            _cleanup_file(client, media_file)

        transcript_text = "\n\n---\n\n".join(all_transcripts)
        summary_text = "\n\n---\n\n".join(all_summaries) if with_summary else None

    # Сохранение
    ext = ".txt" if output_format == "txt" else ".md"
    transcript_path = output_dir / f"{path.stem} - транскрипция{ext}"
    transcript_path.write_text(transcript_text, encoding="utf-8")
    print(f"\nСохранено: {transcript_path.name}")

    if summary_text:
        summary_path = output_dir / f"{path.stem} - саммари{ext}"
        summary_path.write_text(summary_text, encoding="utf-8")
        print(f"Сохранено: {summary_path.name}")


def _process_analyze_ui(client, path, parts, offsets, output_dir):
    """Analyze-UI режим: саммари + детальный + скриншоты + транскрипция."""
    if len(parts) == 1:
        print("Загрузка видео в Gemini...")
        media_file = upload_file(client, path)
        print(f"Загружено: {media_file.name}")
        media_file = wait_for_processing(client, media_file)

        summary_text, detailed_text, transcript_text = analyze_ui_single(
            client, media_file, path, output_dir
        )

        _cleanup_file(client, media_file)
    else:
        all_summaries = []
        all_detailed = []
        all_transcripts = []

        for i, (part_path, offset) in enumerate(zip(parts, offsets), 1):
            print(f"\n{'='*40} Часть {i}/{len(parts)} {'='*40}")
            print("Загрузка части в Gemini...")
            media_file = upload_file(client, part_path)
            print(f"Загружено: {media_file.name}")
            media_file = wait_for_processing(client, media_file)

            s_text, d_text, t_text = analyze_ui_single(
                client, media_file, path, output_dir,
                part_label=f"{i}/{len(parts)}", time_offset=offset
            )
            all_summaries.append(f"## Часть {i}\n\n{s_text}")
            all_detailed.append(f"## Часть {i} (с {offset//60}:{offset%60:02d})\n\n{d_text}")
            all_transcripts.append(f"## Часть {i} (с {offset//60}:{offset%60:02d})\n\n{t_text}")

            _cleanup_file(client, media_file)

        summary_text = "\n\n---\n\n".join(all_summaries)
        detailed_text = "\n\n---\n\n".join(all_detailed)
        transcript_text = "\n\n---\n\n".join(all_transcripts)

    # Сохранение (всегда .md в analyze-ui)
    summary_path = output_dir / f"{path.stem} - саммари.md"
    summary_path.write_text(summary_text, encoding="utf-8")
    print(f"\nСохранено: {summary_path.name}")

    detailed_path = output_dir / f"{path.stem} - детальный.md"
    detailed_path.write_text(detailed_text, encoding="utf-8")
    print(f"Сохранено: {detailed_path.name}")

    transcript_path = output_dir / f"{path.stem} - транскрипция.md"
    transcript_path.write_text(transcript_text, encoding="utf-8")
    print(f"Сохранено: {transcript_path.name}")


def _cleanup_file(client, media_file):
    """Удаление загруженного файла из Gemini."""
    try:
        client.files.delete(name=media_file.name)
    except Exception as e:
        print(f"  Предупреждение: не удалось удалить файл из Gemini ({media_file.name}): {e}")


# === CLI ===

def main():
    parser = argparse.ArgumentParser(
        description="Транскрибация аудио и видео через Gemini API"
    )
    parser.add_argument("file", help="Путь к аудио/видеофайлу")
    parser.add_argument(
        "--output-dir", "-o",
        help="Каталог для результатов (по умолчанию: рядом с файлом в Транскрипция/<имя>/)",
    )
    parser.add_argument(
        "--analyze-ui",
        action="store_true",
        help="Режим анализа интерфейсов (только видео): саммари + детальный лог + скриншоты + транскрипция",
    )
    parser.add_argument(
        "--with-summary",
        action="store_true",
        help="Добавить саммари (для generic-режима)",
    )
    parser.add_argument(
        "--format",
        choices=["md", "txt"],
        default="md",
        help="Формат вывода (по умолчанию: md)",
    )
    args = parser.parse_args()

    path = Path(args.file)
    if not path.exists():
        print(f"Файл не найден: {args.file}")
        sys.exit(1)

    if path.suffix.lower() not in ALL_EXTENSIONS:
        print(f"Неподдерживаемый формат: {path.suffix}")
        print(f"Видео: {', '.join(sorted(VIDEO_EXTENSIONS))}")
        print(f"Аудио: {', '.join(sorted(AUDIO_EXTENSIONS))}")
        sys.exit(1)

    # Определение режима
    mode = "generic"
    if args.analyze_ui:
        if is_audio(path):
            print("Предупреждение: --analyze-ui доступен только для видео. Переключаюсь на generic + саммари.",
                  file=sys.stderr)
            args.with_summary = True
        else:
            mode = "analyze-ui"

    # Определение output_dir
    if args.output_dir:
        output_dir = Path(args.output_dir)
    else:
        output_dir = path.parent / "Транскрипция" / path.stem

    process_file(path, output_dir, mode, args.with_summary, args.format)


if __name__ == "__main__":
    main()
