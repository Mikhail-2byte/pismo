"""
Генератор официальных писем о переносе срока поставки.
Запуск: python main.py [путь_к_excel]
"""

import sys
import os
import re
from datetime import date, datetime

from parser import parse_excel, get_managers, get_contracts, get_specs
from generator import generate_letter
from filler import fill_template
from config import OUTPUT_DIR, TEMPLATE_PATH


def _ask(prompt: str, default: str = '') -> str:
    val = input(prompt).strip()
    return val if val else default


def _ask_date(prompt: str) -> str:
    while True:
        raw = input(prompt).strip()
        if not raw:
            print('  Дата обязательна.')
            continue
        try:
            datetime.strptime(raw, '%d.%m.%Y')
            return raw
        except ValueError:
            print('  Неверный формат. Введите дату в виде ДД.ММ.ГГГГ (например 30.06.2026).')


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


def _choose_multi(items: list, label_fn=None, title: str = '') -> list[int]:
    """Выводит список, возвращает индексы выбранных элементов. Enter = все."""
    if title:
        print(f'\n{title}')
        print('─' * len(title))
    for i, item in enumerate(items, 1):
        label = label_fn(item) if label_fn else str(item)
        print(f'  {i}. {label}')
    print('  (Enter — выбрать все)')
    while True:
        raw = input('\nНомера через запятую: ').strip()
        if not raw:
            return list(range(len(items)))
        parts = [p.strip() for p in raw.split(',')]
        if all(p.isdigit() and 1 <= int(p) <= len(items) for p in parts):
            return [int(p) - 1 for p in parts]
        print('  Неверный ввод, попробуйте ещё раз.')


def _ask_reason_and_date(item_names: list[str]) -> list[tuple[str, str]]:
    """Запрашивает причину и новую дату. Для нескольких позиций предлагает общие или индивидуальные значения."""
    if len(item_names) == 1:
        reason = _ask('  Причина переноса: ').strip()
        if not reason:
            raise ValueError('Причина обязательна.')
        new_date = _ask_date('  Новый срок (ДД.ММ.ГГГГ): ')
        return [(reason, new_date)]

    same = _ask('\n  Одинаковые причина и дата для всех позиций? [y/n, Enter=да] : ', default='y').lower()
    if same in ('y', 'д', 'да', 'yes', ''):
        reason = _ask('  Причина переноса (для всех): ').strip()
        if not reason:
            raise ValueError('Причина обязательна.')
        new_date = _ask_date('  Новый срок (для всех, ДД.ММ.ГГГГ): ')
        return [(reason, new_date)] * len(item_names)

    results = []
    for name in item_names:
        print(f'\n  Позиция: {name}')
        reason = _ask('    Причина переноса: ').strip()
        if not reason:
            raise ValueError('Причина обязательна.')
        new_date = _ask_date('    Новый срок (ДД.ММ.ГГГГ): ')
        results.append((reason, new_date))
    return results


def _safe_filename(text: str) -> str:
    """Убирает из строки символы, запрещённые в именах файлов."""
    return re.sub(r'[\\/:*?"<>|]', '_', text)


def _build_output_path(company: str, entries: list[dict]) -> str:
    today = date.today().strftime('%Y-%m-%d')
    if len(entries) == 1:
        spec_part = _safe_filename(entries[0]['number'])
    else:
        spec_part = '_'.join(_safe_filename(e['number']) for e in entries)
    fname = f'letter_{_safe_filename(company)}_{spec_part}_{today}.docx'
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

    # --- Шаг 4: Спецификации и позиции ---
    def spec_label(s):
        signed = '✓' if s['signed'].lower() == 'да' else '–'
        return f"№{s['number']}  |  срок: {s['deadline']}  |  подписана: {signed}  |  позиций: {len(s['items'])}"

    entries: list[dict] = []
    used_indices: set[int] = set()

    while True:
        available = [(i, s) for i, s in enumerate(specs) if i not in used_indices]
        if not available:
            print('\nВсе спецификации уже добавлены.')
            break

        avail_specs   = [s for _, s in available]
        avail_indices = [i for i, _ in available]

        spec_idx = _choose(avail_specs, label_fn=spec_label, title='Выберите спецификацию:')
        spec = specs[avail_indices[spec_idx]]
        used_indices.add(avail_indices[spec_idx])

        if not spec['items']:
            print(f'  Спецификация №{spec["number"]} не содержит позиций — пропускается.')
            used_indices.discard(avail_indices[spec_idx])
            continue

        item_indices = _choose_multi(
            spec['items'],
            label_fn=lambda it: f'{it["name"]}  —  {it["qty"]} шт.',
            title=f'Позиции спецификации №{spec["number"]}:',
        )
        selected_items = [spec['items'][i] for i in item_indices]

        try:
            rd_pairs = _ask_reason_and_date([it['name'] for it in selected_items])
        except ValueError as e:
            print(f'  Ошибка: {e}')
            used_indices.discard(avail_indices[spec_idx])
            continue

        entries.append({
            'company':  contract['company'],
            'contract': contract['contract'],
            'number':   spec['number'],
            'date':     spec['date'],
            'deadline': spec['deadline'],
            'items': [
                {**item, 'reason': reason, 'new_date': new_date}
                for item, (reason, new_date) in zip(selected_items, rd_pairs)
            ],
        })
        print(f'\n  Спецификация №{spec["number"]} добавлена ({len(selected_items)} поз.).')

        if len(available) == 1:
            break
        more = _ask('\nДобавить ещё одну спецификацию в это письмо? [y/n, Enter=нет] : ', default='n').lower()
        if more not in ('y', 'д', 'да', 'yes'):
            break

    if not entries:
        print('Нет данных для письма.')
        return

    # --- Шаг 5: Дополнительный комментарий ---
    print('\nДополнительный комментарий для письма (необязательно):')
    print('  Например: "позиция X уже готова и будет отгружена 15.06"')
    print('  или: "просим подтвердить получение письма до 01.06"')
    comment = _ask('  Комментарий (Enter — пропустить): ').strip()

    # --- Шаг 6: Генерация ---
    print('\nГенерирую текст письма...')
    try:
        body_text = generate_letter(entries, manager, comment=comment)
    except Exception as e:
        print(f'Ошибка генерации: {e}')
        return

    # --- Шаг 6: Предпросмотр и правки ---
    revision = 0
    while True:
        revision += 1
        print('\n' + '─' * 60)
        label = 'ТЕКСТ ПИСЬМА' if revision == 1 else f'ТЕКСТ ПИСЬМА — ВЕРСИЯ {revision}'
        print(label)
        print('─' * 60)
        print(body_text)
        print('─' * 60)

        action = _ask('\n[y] Сохранить  [n] Исправить  [q] Отмена : ', default='y').lower()
        if action in ('y', 'д', 'да', 'yes', ''):
            break
        if action in ('q', 'й', 'quit', 'exit'):
            print('Отменено.')
            return
        feedback = _ask('Что исправить? ').strip()
        if not feedback:
            continue
        print('\nПерегенерирую текст с учётом замечания...')
        try:
            body_text = generate_letter(entries, manager, comment=comment, feedback=feedback, previous_text=body_text)
        except Exception as e:
            print(f'Ошибка генерации: {e}')
            return

    # --- Шаг 7: Сохранение ---
    today_str = date.today().strftime('%d.%m.%Y')
    contact_info = f'Менеджер: {manager}\nТел.: ___________'

    fill_data = {
        'date': today_str,
        'company': contract['company'],
        'contact_info': contact_info,
        'body': body_text,
    }

    output_path = _build_output_path(contract['company'], entries)
    try:
        fill_template(TEMPLATE_PATH, fill_data, output_path)
    except Exception as e:
        print(f'Ошибка создания документа: {e}')
        return

    print(f'\nГотово! Файл сохранён:\n  {output_path}')


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print('\n\nОтменено.')
        sys.exit(0)
