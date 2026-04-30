"""
Генерация текста официального письма через Groq (бесплатный tier).

generate_letter(spec_data, manager, reason, new_date) → str
"""

import os
from pathlib import Path
from dotenv import load_dotenv
from groq import Groq

load_dotenv(Path(__file__).parent / '.env')

_MODEL = 'llama-3.3-70b-versatile'


def generate_letter(spec_data: dict, manager: str, reason: str, new_date: str) -> str:
    """
    spec_data: company, contract, number, date, deadline, items
    manager:   имя менеджера
    reason:    причина переноса (от пользователя)
    new_date:  новая дата (от пользователя)
    """
    api_key = os.environ.get('GROQ_API_KEY', '').strip()
    if not api_key:
        raise EnvironmentError(
            'GROQ_API_KEY не найден в .env файле.\n'
            'Получить бесплатный ключ: https://console.groq.com'
        )

    client = Groq(api_key=api_key)

    items_lines = '\n'.join(
        f'  - {item["name"]}: {item["qty"]} шт.'
        for item in spec_data.get('items', [])
    ) or '  (позиции не указаны)'

    prompt = f"""Ты — сотрудник отдела продаж промышленной компании. Напиши официальное деловое письмо на русском языке с просьбой о переносе срока поставки.

Исходные данные:
- Компания-заказчик: {spec_data['company']}
- Договор: {spec_data['contract']}
- Спецификация: №{spec_data['number']} от {spec_data['date']}
- Текущий договорной срок поставки: {spec_data['deadline']}
- Перечень позиций:
{items_lines}
- Причина переноса: {reason}
- Запрашиваемый новый срок поставки: {new_date}
- Ответственный менеджер: {manager}

Требования:
1. Официальный деловой стиль, вежливый тон
2. Письмо должно содержать: ссылку на договор и спецификацию, перечень позиций с количеством, обоснование причины, конкретную просьбу перенести срок на {new_date}
3. Выражение готовности к диалогу и принесение извинений за неудобства
4. Только тело письма — без «Кому:», «От кого:», «Дата:», приветствия «Уважаемые» и подписи (они вставляются отдельно из шаблона)
5. Объём: 3–5 абзацев
6. Не используй markdown-разметку (никаких **, ## и т.п.)"""

    response = client.chat.completions.create(
        model=_MODEL,
        messages=[{'role': 'user', 'content': prompt}],
        temperature=0.7,
    )

    return response.choices[0].message.content.strip()
