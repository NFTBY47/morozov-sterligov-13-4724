# Исходные проверки ЛР3

Успешных проверок: **5**. Ожидаемых падений: **6**.

Не завершены общий интерфейс, алгоритмы исполнителей и основной метод сервиса. Поэтому один незаполненный метод может вызвать несколько падений — это не несколько независимых задач.

Падения ниже связаны с конкретными требованиями [TASK.md](TASK.md). После обязательной части все они должны пройти. Бонус проверяется отдельно и не входит в эти числа.

## Новые последовательности и конфигурации

- `tests.test_progression::test_progression_failed_add_does_not_reserve_id_or_change_snapshot`

## Предметный контракт и общий интерфейс

- `tests.test_contract::test_abc_is_abstract`
- `tests.test_contract::test_batch_sum_snapshot_and_isolation`
- `tests.test_contract::test_count_and_amount_boundaries`
- `tests.test_contract::test_global_duplicate_and_failure_does_not_reserve_id`
- `tests.test_contract::test_rule_used_by_coordinator`

## Порядок проверки

Из корня проекта: `python check.py lab03`. Сначала прочитайте первый traceback и ожидаемый результат сценария. Не отключайте тесты, которые пока не проходят.

Ошибка импорта или установки не относится к заданию. Если исходный набор результатов отличается, сохраните вывод и сообщите преподавателю; не удаляйте решения и служебные файлы.
