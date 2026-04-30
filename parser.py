"""
Парсинг Excel-отчёта по спецификациям.

Иерархия файла:
  Менеджер → Компания-заказчик → Договор → Спецификация → Позиции

parse_excel(path) → dict:
  {
    "Баяндин О. Н.": [
      {
        "company": "ООО Ромашка",
        "contract": "Договор №200/25 от 01.10.2025",
        "specs": [
          {
            "number": "1 (200/25) от 01.10.2025",
            "date": "21.10.2025",
            "deadline": "19.04.2026",
            "signed": "Да",
            "items": [
              {"name": "Вал дробилки ч.ЛБ.1.000.6", "qty": "2"}
            ]
          }
        ]
      }
    ]
  }
"""

import re
from datetime import datetime, date
import openpyxl

# Менеджер — Фамилия И. О. (одна или две инициалы)
_MANAGER_RE = re.compile(r'^[А-ЯЁ][а-яёА-ЯЁ\-]+\s+[А-ЯЁ]\.\s*[А-ЯЁ]\.$')


def _is_manager(text: str) -> bool:
    return bool(_MANAGER_RE.match(text.strip()))


def _to_date_str(val) -> str:
    if isinstance(val, (datetime, date)):
        return val.strftime('%d.%m.%Y')
    if isinstance(val, str):
        val = val.strip()
        for fmt in ('%d.%m.%Y', '%d/%m/%Y', '%Y-%m-%d'):
            try:
                return datetime.strptime(val, fmt).strftime('%d.%m.%Y')
            except ValueError:
                pass
    return str(val) if val is not None else ''


def _is_date(val) -> bool:
    if isinstance(val, (datetime, date)):
        return True
    if isinstance(val, str):
        val = val.strip()
        for fmt in ('%d.%m.%Y', '%d/%m/%Y', '%Y-%m-%d'):
            try:
                datetime.strptime(val, fmt)
                return True
            except ValueError:
                pass
    return False


def _count_total_cols(row) -> int:
    """Количество непустых значений в сводных колонках E-I (индексы 4-8)."""
    return sum(1 for i in range(4, 9) if row[i] is not None)


def parse_excel(path: str) -> dict:
    wb = openpyxl.load_workbook(path)
    ws = wb.active

    result: dict = {}

    current_manager: str | None = None
    current_company: str | None = None
    current_contract: dict | None = None
    current_spec: dict | None = None

    # Данные начинаются с 6-й строки (строки 1-5 — заголовки)
    for row in ws.iter_rows(min_row=6, values_only=True):
        col_a = str(row[0]).strip() if row[0] is not None else ''
        col_b = row[1]   # дата спецификации
        col_c = row[2]   # дата отгрузки
        col_d = str(row[3]).strip() if row[3] is not None else ''
        col_e = row[4]   # количество по спецификации
        col_j = row[9]   # поставщик (есть у позиций)

        if not col_a or col_a == 'None':
            continue

        # --- Договор ---
        if 'Договор' in col_a or 'договор' in col_a:
            current_spec = None
            if current_manager is None:
                continue
            current_contract = {
                'company': current_company or '',
                'contract': col_a,
                'specs': [],
            }
            result[current_manager].append(current_contract)
            continue

        # --- Спецификация (обе даты присутствуют) ---
        if _is_date(col_b) and _is_date(col_c):
            if current_contract is None:
                continue
            current_spec = {
                'number': col_a,
                'date': _to_date_str(col_b),
                'deadline': _to_date_str(col_c),
                'signed': col_d,
                'items': [],
            }
            current_contract['specs'].append(current_spec)
            continue

        # --- Менеджер ---
        if _is_manager(col_a):
            current_manager = col_a
            current_company = None
            current_contract = None
            current_spec = None
            result[current_manager] = []
            continue

        # --- Позиция или сводная строка ---
        if current_spec is not None:
            # Сводные строки (компания/договор-агрегат) имеют много заполненных
            # сводных колонок и не имеют поставщика (col_j).
            # Позиции обычно имеют поставщика ИЛИ мало сводных колонок.
            total_cols = _count_total_cols(row)
            if col_j is None and total_cols >= 4:
                # Это сводная строка нового уровня — спецификация закончилась.
                current_spec = None
                current_contract = None
                current_company = col_a
            else:
                qty = str(col_e) if col_e is not None else ''
                current_spec['items'].append({'name': col_a, 'qty': qty})
            continue

        # --- Компания-заказчик (между менеджером и первым договором) ---
        if current_manager is not None and current_contract is None:
            current_company = col_a

    return result


def get_managers(data: dict) -> list[str]:
    return list(data.keys())


def get_contracts(data: dict, manager: str) -> list[dict]:
    return data.get(manager, [])


def get_specs(contract: dict) -> list[dict]:
    return contract.get('specs', [])
