#!/usr/bin/env python3
"""
Патч для исправления V2 UI
Исправляет:
1. V2_AVAILABLE = False -> удаляет дублирующую строку
2. Добавляет метод _update_v2_progress_bars

Запуск: python fix_v2_patch.py
"""

import os
import re
import shutil
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MAIN_FILE = os.path.join(BASE_DIR, "auto-short_v095_with_trainer_bridge.py")
BACKUP_FILE = MAIN_FILE + ".pre_fix_v2"

# Метод который нужно добавить
V2_PROGRESS_METHOD = '''
    def _update_v2_progress_bars(self):
        """Обновление прогресс-баров V2 в заголовках таблиц"""
        try:
            from core.engine_v2 import update_scan_timers, get_scan_state
            from ui.table_headers_v2 import get_header_manager
            from core.config_v2 import USE_NEW_UI
            
            if not USE_NEW_UI:
                return
            
            # Обновляем таймеры
            update_scan_timers()
            scan_state = get_scan_state()
            
            # Получаем header manager
            header_mgr = get_header_manager()
            
            # Обновляем таймеры уровней
            header_mgr.update_timers(
                level1_left=scan_state.get('level1_countdown', 0),
                level2_left=scan_state.get('level2_countdown', 0),
                level3_left=scan_state.get('level3_countdown', 0)
            )
            
            # Подсчёт по критериям из top200
            top200 = getattr(self, '_last_top200', []) or []
            class_count = sum(1 for r in top200 if r.get('watch_type'))
            pump5m_count = sum(1 for r in top200 if 'Памп' in str(r.get('watch_type', '')))
            extr1m_count = sum(1 for r in top200 if r.get('range_position', 0) > 90)
            combo_count = sum(1 for r in top200 if r.get('watch_type') and r.get('range_position', 0) > 85)
            
            header_mgr.update_criteria_counts(
                class_count=class_count,
                pump5m_count=pump5m_count,
                extr1m_count=extr1m_count,
                combo_count=combo_count
            )
            
            # Подсчёт статусов из кандидатов
            candidates = getattr(self, '_last_focus', []) or []
            watch_count = sum(1 for c in candidates if c.get('status') == 'Наблюдение')
            interest_count = sum(1 for c in candidates if c.get('status') == 'Интерес')
            ready_count = sum(1 for c in candidates if c.get('status') == 'Готовность')
            entry_count = sum(1 for c in candidates if c.get('status') == 'ВХОД')
            
            header_mgr.update_status_counts(
                watch=watch_count,
                interest=interest_count,
                ready=ready_count,
                entry=entry_count
            )
            
            # Генерируем текст заголовков
            top200_header = header_mgr.get_top200_header_text()
            candidates_header = header_mgr.get_candidates_header_text()
            
            # Обновляем метки
            if hasattr(self, 'lbl_top200_counter'):
                self.lbl_top200_counter.setText(top200_header)
            
            if hasattr(self, 'lbl_candidates_counter'):
                self.lbl_candidates_counter.setText(candidates_header)
                
        except Exception as e:
            # Тихо игнорируем ошибки, чтобы не ломать основной функционал
            pass
'''

def fix_patch():
    print("=" * 60)
    print("ИСПРАВЛЕНИЕ V2 ПАТЧА")
    print("=" * 60)
    print()
    
    # Проверяем существование файла
    if not os.path.exists(MAIN_FILE):
        print(f"ОШИБКА: Файл не найден: {MAIN_FILE}")
        return False
    
    # Читаем файл
    with open(MAIN_FILE, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Создаём бэкап
    shutil.copy(MAIN_FILE, BACKUP_FILE)
    print(f"[OK] Бэкап создан: {os.path.basename(BACKUP_FILE)}")
    
    lines = content.split('\n')
    changes = []
    
    # 1. Исправляем V2_AVAILABLE = False (удаляем лишнюю строку)
    new_lines = []
    removed_false = False
    for i, line in enumerate(lines):
        # Пропускаем строку V2_AVAILABLE = False если она НЕ в блоке except
        if "V2_AVAILABLE = False" in line:
            # Проверяем контекст - это в блоке except?
            in_except = False
            for j in range(max(0, i-3), i):
                if "except" in lines[j]:
                    in_except = True
                    break
            
            if in_except:
                new_lines.append(line)  # Оставляем в except блоке
            else:
                removed_false = True
                changes.append(f"Строка {i+1}: Удалено 'V2_AVAILABLE = False'")
                print(f"[OK] Удалена строка {i+1}: V2_AVAILABLE = False")
                continue
        new_lines.append(line)
    
    content = '\n'.join(new_lines)
    
    # 2. Добавляем метод _update_v2_progress_bars если его нет
    if "def _update_v2_progress_bars" not in content:
        # Ищем конец метода _tick_status_lines
        lines = content.split('\n')
        insert_idx = None
        in_tick_method = False
        indent_level = 0
        
        for i, line in enumerate(lines):
            if "def _tick_status_lines(self):" in line:
                in_tick_method = True
                indent_level = len(line) - len(line.lstrip())
                continue
            
            if in_tick_method:
                # Ищем следующий метод на том же уровне
                if line.strip().startswith("def ") and (len(line) - len(line.lstrip())) == indent_level:
                    insert_idx = i
                    break
        
        if insert_idx:
            lines.insert(insert_idx, V2_PROGRESS_METHOD)
            content = '\n'.join(lines)
            changes.append(f"Добавлен метод _update_v2_progress_bars перед строкой {insert_idx+1}")
            print(f"[OK] Добавлен метод _update_v2_progress_bars")
        else:
            # Альтернативный способ - ищем по паттерну
            # Добавляем перед методом _on_timer_focus если есть
            for i, line in enumerate(lines):
                if "def _on_timer_focus" in line or "def _build_focus_table" in line:
                    insert_idx = i
                    break
            
            if insert_idx:
                lines.insert(insert_idx, V2_PROGRESS_METHOD)
                content = '\n'.join(lines)
                changes.append(f"Добавлен метод _update_v2_progress_bars")
                print(f"[OK] Добавлен метод _update_v2_progress_bars (альт. способ)")
            else:
                print("[ОШИБКА] Не удалось найти место для вставки метода")
                return False
    else:
        print("[OK] Метод _update_v2_progress_bars уже существует")
    
    # Записываем
    with open(MAIN_FILE, 'w', encoding='utf-8') as f:
        f.write(content)
    
    print()
    print("=" * 60)
    print("РЕЗУЛЬТАТ:")
    print("=" * 60)
    
    if changes:
        print()
        for change in changes:
            print(f"  [+] {change}")
        print()
        print("[OK] Файл успешно исправлен!")
    else:
        print()
        print("[OK] Изменений не требуется - всё уже исправлено")
    
    print()
    print("=" * 60)
    print("СЛЕДУЮЩИЙ ШАГ:")
    print("=" * 60)
    print()
    print("Перезапустите сканер командой:")
    print()
    print("  python auto-short_v095_with_trainer_bridge.py")
    print()
    
    return True

if __name__ == "__main__":
    try:
        fix_patch()
    except Exception as e:
        print()
        print(f"[ОШИБКА] {e}")
        import traceback
        traceback.print_exc()
    
    print()
    print("=" * 60)
    print("Нажмите Enter для закрытия...")
    print("=" * 60)
    input()
