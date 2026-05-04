"""
Генерация текста официального письма через Groq.

generate_letter(entries, manager, comment, feedback, previous_text, attachments) → str
generate_letter_stream(...)  — streaming-версия, yields text chunks
"""

import os
import httpx
from pathlib import Path
from dotenv import load_dotenv
from groq import Groq

load_dotenv(Path(__file__).parent / '.env')

_MODEL       = os.environ.get('GROQ_MODEL', 'llama-3.3-70b-versatile')
_TEMPERATURE = float(os.environ.get('GROQ_TEMPERATURE', '0.7'))


def _make_client(api_key: str) -> Groq:
    proxy = os.environ.get('HTTPS_PROXY') or os.environ.get('HTTP_PROXY')
    if proxy:
        return Groq(api_key=api_key, http_client=httpx.Client(proxy=proxy))
    return Groq(api_key=api_key)


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


def _build_prompt(
    entries: list[dict],
    manager: str,
    comment: str,
    feedback: str,
    previous_text: str,
    attachments: list[str],
) -> str:
    """Формирует промпт для генерации или перегенерации письма."""
    company      = entries[0]['company']
    contract_str = entries[0]['contract']
    spec_blocks  = '\n\n'.join(
        _build_spec_block(e, i, len(entries)) for i, e in enumerate(entries)
    )
    spec_intro = 'одну спецификацию' if len(entries) == 1 else f'{len(entries)} спецификации'

    prompt = f"""Ты — официальный представитель компании-поставщика. Напиши тело официального делового письма на русском языке от лица компании с уведомлением о переносе срока поставки и просьбой согласовать новые сроки.

Исходные данные:
- Компания-получатель: {company}
- Договор: {contract_str}
- Письмо охватывает {spec_intro}:

{spec_blocks}
- Подписывает письмо: {manager}

Структура письма (строго соблюдай порядок абзацев):
1. Вступление: кратко обозначь тему письма со ссылкой на договор и спецификацию(и).
2. Суть: изложи факт вынужденного переноса и причину по каждой спецификации / позиции; если причин несколько — опиши каждую отдельно.
3. Новые сроки: для каждой спецификации и/или позиции чётко укажи запрашиваемые даты.
4. Готовность к диалогу: вырази готовность обсудить ситуацию, принеси извинения за неудобства, при необходимости предложи компенсационные меры.
5. Заключение: выражение уважения к партнёрским отношениям и просьба о подтверждении согласования новых сроков.

Требования к стилю и форматированию:
- Официальный деловой стиль, вежливый и уважительный тон; письмо пишется от лица компании, а не от отдельного сотрудника
- Конкретные данные: номера и даты спецификаций, наименования позиций, количество, сроки
- Только тело письма — без обращения «Уважаемые…», без «Кому:», без подписи (они добавляются шаблоном отдельно)
- 3–6 абзацев, без маркированных списков внутри абзацев — всё в форме связного текста
- Не используй markdown-разметку (никаких **, ## и т.п.)"""

    if attachments:
        att_list = ', '.join(f'«{a}»' for a in attachments)
        prompt += (
            f'\n\nК письму прилагаются следующие документы: {att_list}. '
            f'Упомяни их в тексте письма в уместном месте '
            f'(например, «к настоящему письму прилагается…»).'
        )

    if comment:
        prompt += f'\n\nДополнительно необходимо включить в письмо: {comment}'

    if feedback and previous_text:
        prompt += (
            f'\n\nПредыдущая версия письма:\n{previous_text}'
            f'\n\nЗамечание пользователя: {feedback}'
            f'\n\nПерепиши письмо с учётом этого замечания, сохранив все исходные данные.'
        )

    return prompt


def generate_letter(
    entries: list[dict],
    manager: str,
    comment: str = '',
    feedback: str = '',
    previous_text: str = '',
    attachments: list[str] | None = None,
) -> str:
    api_key = os.environ.get('GROQ_API_KEY', '').strip()
    if not api_key:
        raise EnvironmentError(
            'GROQ_API_KEY не найден в .env файле.\n'
            'Получить бесплатный ключ: https://console.groq.com'
        )

    client = _make_client(api_key)
    prompt = _build_prompt(entries, manager, comment, feedback, previous_text, attachments or [])

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
    attachments: list[str] | None = None,
):
    """Streaming version of generate_letter — yields text chunks."""
    api_key = os.environ.get('GROQ_API_KEY', '').strip()
    if not api_key:
        raise EnvironmentError(
            'GROQ_API_KEY не найден в .env файле.\n'
            'Получить бесплатный ключ: https://console.groq.com'
        )

    client = _make_client(api_key)
    prompt = _build_prompt(entries, manager, comment, feedback, previous_text, attachments or [])

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
