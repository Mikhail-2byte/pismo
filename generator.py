"""
Генерация текста официального письма через Groq (бесплатный tier).

generate_letter(entries, manager, feedback, previous_text) → str
"""

import os
from pathlib import Path
from dotenv import load_dotenv
from groq import Groq

load_dotenv(Path(__file__).parent / '.env')

_MODEL       = os.environ.get('GROQ_MODEL', 'qwen/qwen3-32b')
_TEMPERATURE = float(os.environ.get('GROQ_TEMPERATURE', '0.7'))


def _build_spec_block(entry: dict, idx: int, total: int) -> str:
    """Форматирует одну спецификацию для промпта."""
    header = f'Спецификация №{entry["number"]} от {entry["date"]}'
    if total > 1:
        header = f'Спецификация {idx + 1}: №{entry["number"]} от {entry["date"]}'

    items = entry['items']
    reasons   = {it['reason']   for it in items}
    new_dates = {it['new_date'] for it in items}
    uniform   = len(reasons) == 1 and len(new_dates) == 1

    if uniform:
        items_text = '\n'.join(f'    - {it["name"]}: {it["qty"]} шт.' for it in items)
        return (
            f'- {header}\n'
            f'  Текущий договорной срок: {entry["deadline"]}\n'
            f'  Перечень позиций:\n{items_text}\n'
            f'  Причина переноса: {items[0]["reason"]}\n'
            f'  Запрашиваемый новый срок: {items[0]["new_date"]}'
        )
    else:
        lines = [
            f'- {header}\n'
            f'  Текущий договорной срок: {entry["deadline"]}\n'
            f'  Перечень позиций (у каждой своя причина и дата):'
        ]
        for it in items:
            lines.append(
                f'    - {it["name"]}: {it["qty"]} шт.\n'
                f'      Причина: {it["reason"]}\n'
                f'      Новый срок: {it["new_date"]}'
            )
        return '\n'.join(lines)


def generate_letter(
    entries: list[dict],
    manager: str,
    comment: str = '',
    feedback: str = '',
    previous_text: str = '',
) -> str:
    """
    entries:       список спецификаций, каждая содержит позиции с reason и new_date
    manager:       имя менеджера
    comment:       свободный комментарий пользователя (доп. информация или просьба)
    feedback:      замечание пользователя к предыдущей версии
    previous_text: предыдущий вариант письма (для контекста)
    """
    api_key = os.environ.get('GROQ_API_KEY', '').strip()
    if not api_key:
        raise EnvironmentError(
            'GROQ_API_KEY не найден в .env файле.\n'
            'Получить бесплатный ключ: https://console.groq.com'
        )

    client = Groq(api_key=api_key)

    company      = entries[0]['company']
    contract_str = entries[0]['contract']
    spec_blocks  = '\n\n'.join(
        _build_spec_block(e, i, len(entries)) for i, e in enumerate(entries)
    )
    spec_intro = 'одну спецификацию' if len(entries) == 1 else f'{len(entries)} спецификации'

    prompt = f"""Ты — сотрудник отдела продаж промышленной компании. Напиши официальное деловое письмо на русском языке с просьбой о переносе срока поставки.

Исходные данные:
- Компания-заказчик: {company}
- Договор: {contract_str}
- Письмо охватывает {spec_intro}:

{spec_blocks}
- Ответственный менеджер: {manager}

Требования:
1. Официальный деловой стиль, вежливый тон
2. Для каждой спецификации — ссылка на номер и дату, перечень позиций с количеством, обоснование причины и просьба перенести срок на указанную дату
3. Если у позиций разные причины или даты — упомяни каждую отдельно
4. Выражение готовности к диалогу и принесение извинений за неудобства
5. Только тело письма — без «Кому:», «От кого:», «Дата:», приветствия «Уважаемые» и подписи (они вставляются отдельно из шаблона)
6. Объём: 3–6 абзацев
7. Не используй markdown-разметку (никаких **, ## и т.п.)"""

    if comment:
        prompt += f'\n\nДополнительно необходимо включить в письмо: {comment}'

    if feedback and previous_text:
        prompt += (
            f'\n\nПредыдущая версия письма:\n{previous_text}'
            f'\n\nЗамечание пользователя: {feedback}'
            f'\n\nПерепиши письмо с учётом этого замечания, сохранив все исходные данные.'
        )

    response = client.chat.completions.create(
        model=_MODEL,
        messages=[{'role': 'user', 'content': prompt}],
        temperature=_TEMPERATURE,
    )

    return response.choices[0].message.content.strip()


def generate_letter_stream(
    entries: list[dict],
    manager: str,
    comment: str = '',
    feedback: str = '',
    previous_text: str = '',
):
    """Streaming version of generate_letter — yields text chunks."""
    api_key = os.environ.get('GROQ_API_KEY', '').strip()
    if not api_key:
        raise EnvironmentError(
            'GROQ_API_KEY не найден в .env файле.\n'
            'Получить бесплатный ключ: https://console.groq.com'
        )

    client = Groq(api_key=api_key)

    company      = entries[0]['company']
    contract_str = entries[0]['contract']
    spec_blocks  = '\n\n'.join(
        _build_spec_block(e, i, len(entries)) for i, e in enumerate(entries)
    )
    spec_intro = 'одну спецификацию' if len(entries) == 1 else f'{len(entries)} спецификации'

    prompt = f"""Ты — сотрудник отдела продаж промышленной компании. Напиши официальное деловое письмо на русском языке с просьбой о переносе срока поставки.

Исходные данные:
- Компания-заказчик: {company}
- Договор: {contract_str}
- Письмо охватывает {spec_intro}:

{spec_blocks}
- Ответственный менеджер: {manager}

Требования:
1. Официальный деловой стиль, вежливый тон
2. Для каждой спецификации — ссылка на номер и дату, перечень позиций с количеством, обоснование причины и просьба перенести срок на указанную дату
3. Если у позиций разные причины или даты — упомяни каждую отдельно
4. Выражение готовности к диалогу и принесение извинений за неудобства
5. Только тело письма — без «Кому:», «От кого:», «Дата:», приветствия «Уважаемые» и подписи (они вставляются отдельно из шаблона)
6. Объём: 3–6 абзацев
7. Не используй markdown-разметку (никаких **, ## и т.п.)"""

    if comment:
        prompt += f'\n\nДополнительно необходимо включить в письмо: {comment}'

    if feedback and previous_text:
        prompt += (
            f'\n\nПредыдущая версия письма:\n{previous_text}'
            f'\n\nЗамечание пользователя: {feedback}'
            f'\n\nПерепиши письмо с учётом этого замечания, сохранив все исходные данные.'
        )

    stream = client.chat.completions.create(
        model=_MODEL,
        messages=[{'role': 'user', 'content': prompt}],
        temperature=_TEMPERATURE,
        stream=True,
    )

    for chunk in stream:
        content = chunk.choices[0].delta.content
        if content:
            yield content
