"""
Генератор официальных писем о переносе срока поставки.
Запуск: python main.py [путь_к_excel]
"""

import sys
import os
import re
from datetime import date

from parser import parse_excel, get_managers, get_contracts, get_specs
from generator import generate_letter
from filler import fill_template
from config import OUTPUT_DIR, TEMPLATE_PATH


def _ask(prompt: str, default: str = '') -> str:
    val = input(prompt).strip()
    return val if val else default


def _choose(items: list, label_fn=None, title: str = '') -> int:
    """Выводит нумерованный список, возвращает индекс выбранного элемента."""
    if title:
        print(f'\n{title}')
        print('─' * len(title))
    for i, item in enumerate(items, 1):
        label = label_fn(item) if label_fn else str(item)
        print(f'  {i}. {label}')
    while True:
        raw = input('\nВведите номер: ').strip()
        if raw.isdigit() and 1 <= int(raw) <= len(items):
            return int(raw) - 1
        print('  Неверный номер, попробуйте ещё раз.')


def _safe_filename(text: str) -> str:
    """Убирает из строки символы, запрещённые в именах файлов."""
    return re.sub(r'[\\/:*?"<>|]', '_', text)


def _build_output_path(company: str, spec_number: str) -> str:
    today = date.today().strftime('%Y-%m-%d')
    fname = f'letter_{_safe_filename(company)}_{_safe_filename(spec_number)}_{today}.docx'
    return os.path.join(OUTPUT_DIR, fname)


def main():
    print('=' * 60)
    print('  Генератор писем о переносе срока поставки')
    print('=' * 60)

    # --- Шаг 1: Excel файл ---
    if len(sys.argv) > 1:
        excel_path = sys.argv[1]
    else:
        excel_path = _ask('\nПуть к Excel файлу (Enter = текущая папка): ')
        if not excel_path:
            # Ищем первый .xlsx в текущей папке
            xlsx_files = [f for f in os.listdir('.') if f.endswith('.xlsx') and not f.startswith('~')]
            if not xlsx_files:
                print('Excel файл не найден.')
                return
            if len(xlsx_files) == 1:
                excel_path = xlsx_files[0]
                print(f'  Найден файл: {excel_path}')
            else:
                idx = _choose(xlsx_files, title='Найдено несколько файлов:')
                excel_path = xlsx_files[idx]

    print(f'\nЧитаю файл: {excel_path} ...')
    try:
        data = parse_excel(excel_path)
    except Exception as e:
        print(f'Ошибка чтения файла: {e}')
        return

    managers = get_managers(data)
    if not managers:
        print('Менеджеры не найдены в файле.')
        return

    # --- Шаг 2: Менеджер ---
    manager_idx = _choose(managers, title='Выберите менеджера:')
    manager = managers[manager_idx]

    contracts = get_contracts(data, manager)
    if not contracts:
        print('У этого менеджера нет договоров.')
        return

    # --- Шаг 3: Договор ---
    def contract_label(c):
        return f"{c['contract']}  |  {c['company']}  ({len(c['specs'])} спец.)"

    contract_idx = _choose(contracts, label_fn=contract_label, title='Выберите договор:')
    contract = contracts[contract_idx]

    specs = get_specs(contract)
    if not specs:
        print('В этом договоре нет спецификаций.')
        return

    # --- Шаг 4: Спецификация ---
    def spec_label(s):
        signed = '✓' if s['signed'].lower() == 'да' else '–'
        return f"№{s['number']}  |  срок: {s['deadline']}  |  подписана: {signed}  |  позиций: {len(s['items'])}"

    spec_idx = _choose(specs, label_fn=spec_label, title='Выберите спецификацию:')
    spec = specs[spec_idx]

    # --- Показываем позиции ---
    print(f'\nПозиции спецификации №{spec["number"]}:')
    if spec['items']:
        for item in spec['items']:
            print(f'  • {item["name"]}  —  {item["qty"]} шт.')
    else:
        print('  (позиции не найдены)')

    # --- Шаг 5: Причина и новая дата ---
    print()
    reason = _ask('Причина переноса срока: ')
    if not reason:
        print('Причина обязательна.')
        return

    new_date = _ask('Новый запрашиваемый срок поставки (например 30.06.2026): ')
    if not new_date:
        print('Новая дата обязательна.')
        return

    # --- Шаг 6: Генерация ---
    print('\nГенерирую текст письма...')
    spec_data = {
        'company': contract['company'],
        'contract': contract['contract'],
        'number': spec['number'],
        'date': spec['date'],
        'deadline': spec['deadline'],
        'items': spec['items'],
    }
    try:
        body_text = generate_letter(spec_data, manager, reason, new_date)
    except Exception as e:
        print(f'Ошибка генерации: {e}')
        return

    print('\n' + '─' * 60)
    print('ПРЕДПРОСМОТР ТЕКСТА ПИСЬМА:')
    print('─' * 60)
    print(body_text)
    print('─' * 60)

    # --- Шаг 7: Сохранение ---
    save = _ask('\nСохранить письмо? (y/n): ', default='y').lower()
    if save not in ('y', 'д', 'да', 'yes', ''):
        print('Отменено.')
        return

    today_str = date.today().strftime('%d.%m.%Y')
    contact_info = f'Менеджер: {manager}\nТел.: ___________'

    fill_data = {
        'date': today_str,
        'company': contract['company'],
        'contact_info': contact_info,
        'body': body_text,
    }

    output_path = _build_output_path(contract['company'], spec['number'])
    try:
        fill_template(TEMPLATE_PATH, fill_data, output_path)
    except Exception as e:
        print(f'Ошибка создания документа: {e}')
        return

    print(f'\nГотово! Файл сохранён:\n  {output_path}')


if __name__ == '__main__':
    main()
