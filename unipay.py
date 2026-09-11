#!/usr/bin/env python3
"""UniPay: получить лабораторную по номеру. Один файл, только стандартная библиотека."""
import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import sys
import stat

VARIANTS = frozenset(('customer', 'card', 'account', 'merchant', 'authorization',
                     'limits', 'fraud', 'fx', 'ledger', 'notification', 'audit',
                     'reporting', 'clearing', 'settlement'))
ROOT_FILES = frozenset(('README.md', 'START_HERE.md', 'check.py', 'requirements.txt',
                        '.gitignore', '.gitattributes', '.unipay/course.json'))
RUNTIME_FILES = frozenset(('check.py', 'requirements.txt', '.gitattributes'))
LOCK = '.unipay-issue.lock'


class DeliveryError(Exception):
    """Отказ выдачи: прежние решения нельзя исправлять или затирать автоматически."""


def json_bytes(value):
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + '\n').encode('utf-8')


def digest(data):
    return hashlib.sha256(data).hexdigest()


def no_links(path):
    # Проверка исходного пути до нормализации не прячет ссылку за resolve().
    for part in (path, *path.parents):
        if part.is_symlink() or (hasattr(part, 'is_junction') and part.is_junction()):
            raise DeliveryError(f'Ссылки и junction не поддерживаются: {part}')
        # Path.is_junction появился позже Python 3.10. Проверяем Windows
        # reparse-атрибут без перехода по ссылке и на старых интерпретаторах.
        try:
            attributes = getattr(part.lstat(), 'st_file_attributes', 0)
        except FileNotFoundError:
            continue
        if attributes & stat.FILE_ATTRIBUTE_REPARSE_POINT:
            raise DeliveryError(f'Ссылки и reparse points не поддерживаются: {part}')


def absolute_folder(path):
    path = Path(path).absolute()
    no_links(path)
    path = Path(os.path.abspath(path))
    if path.exists() and not path.is_dir():
        raise DeliveryError(f'Нужна папка: {path}')
    return path


def relative_file(name):
    if not isinstance(name, str) or not name or '\\' in name:
        raise DeliveryError(f'Недопустимый путь: {name!r}')
    parts = name.split('/')
    for part in parts:
        if (not re.fullmatch(r'[A-Za-z0-9_.-]+', part) or part in ('.', '..')
                or part.lower() == '.git' or part.endswith('.')
                or re.fullmatch(r'(con|prn|aux|nul|com[1-9]|lpt[1-9])(\..*)?', part, re.I)):
            raise DeliveryError(f'Недопустимый путь: {name!r}')
    if PurePosixPath(name).is_absolute():
        raise DeliveryError(f'Абсолютный путь в выдаче: {name}')
    return name


def read_json(path):
    try:
        return json.loads(path.read_text(encoding='utf-8'))
    except (OSError, ValueError) as error:
        raise DeliveryError(f'Не удалось прочитать {path}: {error}') from error


def course(variant):
    return {'format': 1, 'course': 'unipay-oop', 'variant': variant}


def load_bundle(directory):
    """Прочитать и проверить содержимое; не исполняет ни один файл payload."""
    directory = absolute_folder(directory)
    no_links(directory / 'ISSUE.json')
    manifest = read_json(directory / 'ISSUE.json')
    if (not isinstance(manifest, dict) or manifest.get('format') != 1
            or manifest.get('course') != 'unipay-oop'
            or not isinstance(manifest.get('variant'), str) or manifest['variant'] not in VARIANTS
            or type(manifest.get('lab')) is not int or manifest['lab'] not in range(1, 7)):
        raise DeliveryError('Неизвестный формат, вариант или номер работы')
    for key in ('source_commit', 'source_tree'):
        if not re.fullmatch('[0-9a-f]{40}', str(manifest.get(key))):
            raise DeliveryError(f'Не указан полный Git SHA: {key}')
    hashes = manifest.get('files')
    runtime = manifest.get('runtime_sha256')
    if (not isinstance(hashes, dict) or not hashes or not isinstance(runtime, dict)
            or set(runtime) != RUNTIME_FILES):
        raise DeliveryError('Некорректный перечень файлов/требований к запускателю')
    lab = f"lab{manifest['lab']:02d}"
    prefix = f'labs/{lab}/'
    workflow = f'.github/workflows/{lab}.yml'
    for name, value in [*hashes.items(), *runtime.items()]:
        relative_file(name)
        if not isinstance(value, str) or not re.fullmatch('[0-9a-f]{64}', value):
            raise DeliveryError(f'Некорректная SHA-256: {name}')
    for name in hashes:
        if not (name.startswith(prefix) or name == workflow
                or (manifest['lab'] == 1 and name in (ROOT_FILES | {'START_HERE.pdf'}))):
            raise DeliveryError(f'Файл вне выдаваемой работы: {name}')
    required = {prefix + 'TASK.md', prefix + 'app/api.py', prefix + 'tests/test_contract.py', workflow}
    if manifest['lab'] == 1:
        required.update(ROOT_FILES)
    if not required <= hashes.keys():
        raise DeliveryError('В выдаче отсутствуют обязательные файлы')
    payload = directory / 'payload'
    no_links(payload)
    if not payload.is_dir():
        raise DeliveryError('Нет папки payload')
    actual = {}
    for root, dirs, files in os.walk(payload, followlinks=False):
        for name in [*dirs, *files]:
            no_links(Path(root) / name)
        for name in files:
            file = Path(root) / name
            key = relative_file(file.relative_to(payload).as_posix())
            if not file.is_file():
                raise DeliveryError(f'Не обычный файл: {file}')
            actual[key] = file.read_bytes()
    if set(actual) != set(hashes):
        raise DeliveryError('Состав payload не совпадает с ISSUE.json')
    for name, data in actual.items():
        if digest(data) != hashes[name]:
            raise DeliveryError(f'Не совпадает контрольная сумма: {name}')
    if manifest['lab'] == 1:
        if actual['.unipay/course.json'] != json_bytes(course(manifest['variant'])):
            raise DeliveryError('Вариант в course.json не совпадает с выдачей')
        if any(hashes[name] != runtime[name] for name in RUNTIME_FILES):
            raise DeliveryError('Начальные файлы запуска не соответствуют манифесту')
    return manifest, actual


def target_path(root, name):
    path = root / relative_file(name)
    no_links(path)
    for parent in path.parents:
        if parent == root:
            break
        if parent.exists() and not parent.is_dir():
            raise DeliveryError(f'Путь занят файлом: {parent}')
    return path


def plan(root, manifest, data, own_lock=False):
    """Сначала проверяем все условия. Ничего не записывается."""
    if (root / LOCK).exists() and not own_lock:
        raise DeliveryError('Папка занята другой выдачей или остался её lock. Разберите причину; файл не удаляется автоматически.')
    number, variant = manifest['lab'], manifest['variant']
    receipt = f'.unipay/issues/lab{number:02d}.json'
    receipt_path = target_path(root, receipt)
    course_path = target_path(root, '.unipay/course.json')
    if course_path.exists():
        if read_json(course_path) != course(variant):
            raise DeliveryError('Репозиторий принадлежит другому варианту/формату курса')
        for name, expected in manifest['runtime_sha256'].items():
            path = target_path(root, name)
            if not path.is_file() or digest(path.read_bytes()) != expected:
                raise DeliveryError(f'Файл запуска изменён или несовместим: {name}. Автоматическая замена запрещена.')
        if receipt_path.exists():
            if read_json(receipt_path) == manifest:
                return {}  # Повтор выдачи никогда не восстанавливает starter поверх решения.
            raise DeliveryError('Этот номер уже выдан в другой версии. Нужна отдельная согласованная правка, не перезапись.')
        if number == 1:
            raise DeliveryError('Незавершённая первая выдача: есть course.json без квитанции')
        for previous in range(1, number):
            path = target_path(root, f'.unipay/issues/lab{previous:02d}.json')
            value = read_json(path)
            if (not isinstance(value, dict) or value.get('variant') != variant
                    or value.get('lab') != previous or value.get('course') != 'unipay-oop'):
                raise DeliveryError('Не совпадают сведения о предыдущей выдаче')
    else:
        if number != 1:
            raise DeliveryError('Сначала примените выдачу ЛР1. Старый ручной экспорт автоматически не мигрируется.')
        existing = {p.name for p in root.iterdir()} if root.exists() else set()
        if existing - {'.git', *([LOCK] if own_lock else []), *keep_client(root)}:
            raise DeliveryError('Первая выдача требует пустую папку (допускается только .git). Ничего не перезаписано.')
    lab_path = target_path(root, f'labs/lab{number:02d}')
    if lab_path.exists():
        raise DeliveryError(f'{lab_path} уже существует без квитанции. Не перезаписываем даже пустую папку.')
    changes = dict(data)
    changes[receipt] = json_bytes(manifest)
    for name in changes:
        if target_path(root, name).exists():
            raise DeliveryError(f'Коллизия: {name} уже существует. Ничего не перезаписано.')
    return changes


def create_parents(path, root, created):
    if path == root or path.exists():
        return
    create_parents(path.parent, root, created)
    path.mkdir()  # Не заменяет и не принимает чужой файл/ссылку.
    created.append(path)


def apply_bundle(bundle, target, apply=False):
    manifest, data = load_bundle(bundle)
    root = absolute_folder(target)
    changes = plan(root, manifest, data)
    if not apply or not changes:
        return {'variant': manifest['variant'], 'lab': manifest['lab'], 'target': str(root),
                'files': sorted(changes), 'applied': False, 'already_applied': not changes}
    root.mkdir(parents=True, exist_ok=True)
    no_links(root)
    lock = root / LOCK
    try:
        handle = lock.open('xb')
    except FileExistsError as error:
        raise DeliveryError('Одновременно уже выполняется другая выдача') from error
    created_files, created_dirs = [], []
    try:
        with handle:
            handle.write(b'UniPay delivery in progress\n')
        # Повторный preflight после захвата lock, затем только создание новых файлов.
        changes = plan(root, manifest, data, own_lock=True)
        for name, content in changes.items():  # Квитанция всегда последняя.
            path = target_path(root, name)
            create_parents(path.parent, root, created_dirs)
            with path.open('xb') as output:
                created_files.append(path)
                output.write(content)
    except BaseException:
        # Откат обычного сбоя записи; не удаляются файлы прошлых работ.
        for path in reversed(created_files):
            path.unlink()
        for directory in reversed(created_dirs):
            directory.rmdir()
        raise
    finally:
        lock.unlink()
    return {'variant': manifest['variant'], 'lab': manifest['lab'], 'target': str(root),
            'files': sorted(changes), 'applied': True, 'already_applied': not changes}



"""Сетевой интерфейс, добавляемый publish.py к проверенному локальному установщику.

Не запускается отдельно. Публичный unipay.py содержит этот код и функции установки
обычным Python-текстом; загруженные материалы никогда не исполняются при получении.
"""
import base64
import binascii
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
import lzma

PUBLIC_ROOT = 'https://raw.githubusercontent.com/kandrusyak/unipay-course/main/'
CLIENT_VERSION = 2
MAX_CATALOG = 128 * 1024
MAX_DOWNLOAD = 4 * 1024 * 1024
MAX_UNPACKED = 16 * 1024 * 1024
MAX_FILES = 200
ORDER = ('customer', 'card', 'account', 'merchant', 'authorization', 'limits',
         'fraud', 'fx', 'ledger', 'notification', 'audit', 'reporting', 'clearing', 'settlement')


def keep_client(root):
    """В пустом клоне допустим скачанный unipay.py, но не произвольные чужие файлы."""
    path = root / 'unipay.py'
    no_links(path)
    if path.is_file():
        if path.read_bytes() != Path(__file__).read_bytes():
            raise DeliveryError('В папке есть другой unipay.py. Используйте скачанный файл или --target для пустой папки.')
        return {'unipay.py'}
    return set()


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise DeliveryError(f'Повтор ключа в полученных данных: {key}')
        result[key] = value
    return result


def decode_json(data):
    try:
        return json.loads(data.decode('utf-8'), object_pairs_hook=unique_object)
    except (UnicodeError, ValueError, RecursionError) as error:
        raise DeliveryError('Ответ не является корректными данными UniPay. Проверьте подключение и источник файла.') from error


class SameRepositoryRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if not newurl.startswith(PUBLIC_ROOT):
            raise DeliveryError('Сервер перенаправил загрузку за пределы публичного репозитория курса.')
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def download(name, limit):
    if name != 'catalog.json' and not re.fullmatch(r'bundles/[0-9a-f]{64}\.json', name):
        raise DeliveryError('Недопустимый адрес материала в каталоге.')
    # Не читаем токены/credentials и не используем приватный API GitHub.
    suffix = f'?t={time.time_ns()}' if name == 'catalog.json' else ''
    request = urllib.request.Request(PUBLIC_ROOT + name + suffix,
                                    headers={'User-Agent': 'UniPay-Labs/1', 'Cache-Control': 'no-cache'})
    try:
        with urllib.request.build_opener(SameRepositoryRedirect()).open(request, timeout=20) as response:
            if response.status != 200 or not response.geturl().startswith(PUBLIC_ROOT):
                raise DeliveryError('Неожиданный ответ сервера материалов.')
            declared = response.headers.get('Content-Length')
            if declared is not None and (not declared.isdecimal() or int(declared) > limit):
                raise DeliveryError('Размер ответа превышает предел загрузки.')
            data = response.read(limit + 1)
    except urllib.error.HTTPError as error:
        if error.code == 404:
            message = 'Материал пока недоступен на сервере. Сообщите преподавателю; локальные решения не изменены.'
        elif error.code in (403, 429):
            message = 'GitHub временно ограничил доступ. Повторите позже; токен для курса не нужен.'
        else:
            message = f'Сервер ответил HTTP {error.code}. Локальные решения не изменены.'
        raise DeliveryError(message) from error
    except (urllib.error.URLError, TimeoutError, OSError) as error:
        raise DeliveryError('Не удалось скачать материал по HTTPS. Проверьте интернет, proxy и сертификаты; защиту TLS не отключайте.') from error
    if len(data) > limit:
        raise DeliveryError('Слишком большой ответ сервера; установка не выполнялась.')
    return data


def validate_catalog(catalog):
    if (not isinstance(catalog, dict) or catalog.get('format') != 1
            or catalog.get('course') != 'unipay-oop'
            or type(catalog.get('minimum_client')) is not int):
        raise DeliveryError('Неизвестный формат каталога.')
    if catalog['minimum_client'] > CLIENT_VERSION:
        raise DeliveryError('Нужна новая версия unipay.py. Скачайте её со страницы курса; автообновление не выполняется.')
    labs = catalog.get('labs')
    if not isinstance(labs, dict) or len(labs) > 6:
        raise DeliveryError('Некорректный список лабораторных.')
    for number, packages in labs.items():
        if number not in ('1', '2', '3', '4', '5', '6') or not isinstance(packages, dict) or set(packages) != set(ORDER):
            raise DeliveryError('Некорректный номер или набор вариантов в каталоге.')
        for variant, entry in packages.items():
            if not isinstance(entry, dict):
                raise DeliveryError('Некорректная запись варианта.')
            sha = entry.get('sha256')
            if not isinstance(sha, str) or not re.fullmatch('[0-9a-f]{64}', sha):
                raise DeliveryError('В каталоге нет корректной контрольной суммы.')
            if entry.get('path') != f'bundles/{sha}.json':
                raise DeliveryError('Адрес материала не соответствует контрольной сумме.')
            if type(entry.get('size')) is not int or not 1 <= entry['size'] <= MAX_DOWNLOAD:
                raise DeliveryError('Некорректный размер материала.')
            if entry.get('variant') != variant:
                raise DeliveryError('В каталоге перепутаны варианты.')
            for key in ('source_commit', 'source_tree'):
                if not re.fullmatch('[0-9a-f]{40}', str(entry.get(key))):
                    raise DeliveryError('В каталоге отсутствует версия исходных материалов.')
    return catalog


def decode_public_bundle(data, entry, number, variant):
    if len(data) != entry['size'] or digest(data) != entry['sha256']:
        raise DeliveryError('Контрольная сумма или размер материала не совпали. Ничего не установлено.')
    wrapper = decode_json(data)
    if (not isinstance(wrapper, dict) or set(wrapper) != {'encoding', 'data'}
            or wrapper['encoding'] != 'xz+base64' or not isinstance(wrapper['data'], str)):
        raise DeliveryError('Некорректная упаковка материала.')
    try:
        compressed = base64.b64decode(wrapper['data'], validate=True)
        decoder = lzma.LZMADecompressor(format=lzma.FORMAT_XZ, memlimit=64 * 1024 * 1024)
        raw = decoder.decompress(compressed, MAX_UNPACKED + 1)
        if len(raw) > MAX_UNPACKED or not decoder.eof or decoder.unused_data:
            raise DeliveryError('Материал повреждён или превышает предел распаковки.')
    except (ValueError, binascii.Error, lzma.LZMAError) as error:
        raise DeliveryError('Материал повреждён; распаковка не выполнена.') from error
    document = decode_json(raw)
    if (not isinstance(document, dict) or document.get('format') != 1
            or document.get('course') != 'unipay-oop'
            or type(document.get('lab')) is not int or document['lab'] != number
            or document.get('variant') != variant or set(document) != {'format','course','lab','variant','manifest','files'}):
        raise DeliveryError('Состав полученного номера не соответствует каталогу.')
    manifest, files = document['manifest'], document['files']
    if (not isinstance(manifest, dict) or manifest.get('variant') != variant
            or type(manifest.get('lab')) is not int or manifest['lab'] != number
            or manifest.get('source_commit') != entry['source_commit']
            or manifest.get('source_tree') != entry['source_tree']):
        raise DeliveryError('Не совпали вариант, номер или исходная версия.')
    if not isinstance(files, dict) or not 1 <= len(files) <= MAX_FILES:
        raise DeliveryError('Некорректное количество файлов.')
    names = set()
    for name, text in files.items():
        relative_file(name)
        if name.casefold() in names or len(public_file_bytes(name, text)) > MAX_DOWNLOAD:
            raise DeliveryError('Неоднозначное имя или слишком большой файл.')
        names.add(name.casefold())
    return manifest, files


def current_variant(root):
    path = target_path(root, '.unipay/course.json')
    if not path.exists():
        return None
    value = read_json(path)
    if (not isinstance(value, dict) or not isinstance(value.get('variant'), str)
            or value['variant'] not in VARIANTS or value != course(value['variant'])):
        raise DeliveryError('В папке некорректная запись варианта. Не удаляйте решения; обратитесь к преподавателю.')
    return value['variant']


def install(number, variant, target, catalog, *, yes=False, dry_run=False, fetch=download, ask=input, update_guide=False):
    """Получить только выбранный номер. До подтверждения нет изменений в репозитории."""
    root = absolute_folder(target)
    chosen = current_variant(root)
    if chosen and chosen != variant:
        raise DeliveryError(f'В этой папке уже выбран {chosen}; переключение на {variant} запрещено.')
    packages = catalog['labs'].get(str(number))
    if packages is None:
        raise DeliveryError(f'ЛР{number} ещё не опубликована преподавателем. Будущие файлы на сервер не загружены.')
    entry = packages[variant]
    data = fetch(entry['path'], MAX_DOWNLOAD)
    manifest, files = decode_public_bundle(data, entry, number, variant)
    with tempfile.TemporaryDirectory(prefix='unipay-download-') as temporary:
        bundle = Path(temporary)
        (bundle / 'ISSUE.json').write_bytes(json_bytes(manifest))
        for name, text in files.items():
            path = bundle / 'payload' / relative_file(name)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(public_file_bytes(name, text))
        installer = apply_guide_update if update_guide else apply_bundle
        preview = installer(bundle, root, False)
        if preview['already_applied']:
            print(f'ЛР{number} уже получена в этой версии. Ваше решение не изменено.')
            return preview
        print(f'{variant}: ЛР{number}. Источник {manifest["source_commit"][:12]}. Папка: {root}')
        for name in preview['files']:
            print(('  ~ ' if update_guide else '  + ') + name)
        if dry_run:
            print('Только просмотр: файлы репозитория не менялись.')
            return preview
        if not yes and ask('Обновить только памятку? [y/N]: ' if update_guide else 'Добавить эти файлы? [y/N]: ').strip().lower() not in ('y', 'yes', 'д', 'да'):
            print('Отменено. Файлы репозитория не менялись.')
            return preview
        result = installer(bundle, root, True)
    print(f'ЛР{number} получена. Откройте labs/lab{number:02d}/TASK.md.')
    print(f'Проверка: python check.py lab{number:02d}. Git status, commit и push выполните сами.')
    return result



"""Включается в один unipay.py; обновляет только памятку при явном --update-guide."""
GUIDE_FILES = frozenset(('START_HERE.md', 'START_HERE.pdf'))


def public_file_bytes(name, value):
    """Текстовый формат остаётся прежним; бинарным может быть только PDF памятки."""
    if isinstance(value, str):
        data = value.encode('utf-8')
    elif (name == 'START_HERE.pdf' and isinstance(value, dict)
          and set(value) == {'encoding', 'data'} and value['encoding'] == 'base64'
          and isinstance(value['data'], str)):
        if len(value['data']) > MAX_DOWNLOAD * 2:
            raise DeliveryError('PDF превышает предел загрузки.')
        try:
            data = base64.b64decode(value['data'], validate=True)
        except (ValueError, binascii.Error) as error:
            raise DeliveryError('Некорректная упаковка PDF.') from error
        if not data.startswith(b'%PDF-') or not data.rstrip().endswith(b'%%EOF'):
            raise DeliveryError('Полученный файл не является PDF памятки.')
    else:
        raise DeliveryError('Неподдерживаемый формат файла: ' + name)
    if len(data) > MAX_DOWNLOAD:
        raise DeliveryError('Файл превышает предел загрузки.')
    return data


def guide_plan(root, manifest, data, own_lock=False):
    """Сопоставить старую квитанцию с разрешённой правкой; не читать решения."""
    if manifest['lab'] != 1:
        raise DeliveryError('Обновление памятки относится только к ЛР1.')
    if (root / LOCK).exists() and not own_lock:
        raise DeliveryError('Папка занята другой установкой. Ничего не изменено.')
    if read_json(target_path(root, '.unipay/course.json')) != course(manifest['variant']):
        raise DeliveryError('Не совпадает вариант курса.')
    receipt_name = '.unipay/issues/lab01.json'
    receipt_path = target_path(root, receipt_name)
    before_receipt = receipt_path.read_bytes()
    old = read_json(receipt_path)
    if old == manifest:
        return {}, {}  # Повтор не восстанавливает даже изменённую памятку.
    update = manifest.get('guide_update')
    if (not isinstance(update, dict) or set(update) != {'previous_manifest_sha256'}
            or update['previous_manifest_sha256'] != digest(json_bytes(old))):
        raise DeliveryError('Эта версия выдачи не подходит для обновления памятки. Обратитесь к преподавателю.')
    old_fixed = {k: v for k, v in old.items() if k not in ('files', 'guide_update')}
    new_fixed = {k: v for k, v in manifest.items() if k not in ('files', 'guide_update')}
    old_other = {k: v for k, v in old['files'].items() if k not in GUIDE_FILES}
    new_other = {k: v for k, v in manifest['files'].items() if k not in GUIDE_FILES}
    if old_fixed != new_fixed or old_other != new_other:
        raise DeliveryError('Обновление затрагивает не только памятку. Автоматическое применение запрещено.')
    if not GUIDE_FILES <= data.keys() or not GUIDE_FILES <= manifest['files'].keys():
        raise DeliveryError('Не хватает Markdown или PDF памятки.')
    for name, expected in manifest['runtime_sha256'].items():
        if digest(target_path(root, name).read_bytes()) != expected:
            raise DeliveryError('Файл запуска изменён: ' + name)
    changes, before = {}, {}
    for name in sorted(GUIDE_FILES):
        path = target_path(root, name)
        if path.exists() and not path.is_file():
            raise DeliveryError('Путь памятки занят не файлом: ' + name)
        current = path.read_bytes() if path.exists() else None
        wanted = data[name]
        if current == wanted:
            continue
        previous_hash = old['files'].get(name)
        if current is None:
            if previous_hash is not None:
                raise DeliveryError('Прежняя памятка удалена: ' + name + '. Нужен ручной разбор.')
        elif previous_hash is None or digest(current) != previous_hash:
            raise DeliveryError('В памятке есть свои изменения: ' + name + '. Они не перезаписаны.')
        changes[name], before[name] = wanted, current
    # История старой выдачи сохраняется отдельно; квитанция нового состояния последняя.
    history = '.unipay/history/lab01-' + update['previous_manifest_sha256'] + '.json'
    history_path = target_path(root, history)
    if history_path.exists():
        if not history_path.is_file() or history_path.read_bytes() != json_bytes(old):
            raise DeliveryError('Конфликт сохранённой квитанции: ' + history)
    else:
        changes[history], before[history] = json_bytes(old), None
    changes[receipt_name], before[receipt_name] = json_bytes(manifest), before_receipt
    return changes, before


def replace_guide_file(path, content):
    """Один атомарный rename в том же каталоге; файл назначения предварительно проверен."""
    descriptor, temporary_name = tempfile.mkstemp(prefix='.unipay-guide-', dir=path.parent)
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, 'wb') as output:
            output.write(content)
        no_links(path)
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


def apply_guide_update(bundle, target, apply=False):
    manifest, data = load_bundle(bundle)
    root = absolute_folder(target)
    changes, before = guide_plan(root, manifest, data)
    result = dict(variant=manifest['variant'], lab=1, target=str(root), files=sorted(changes),
                  applied=False, already_applied=not changes, guide_only=True)
    if not apply or not changes:
        return result
    lock = target_path(root, LOCK)
    try:
        handle = lock.open('xb')
    except FileExistsError as error:
        raise DeliveryError('Одновременно уже выполняется другая выдача.') from error
    created_dirs, written = [], []
    release_lock = True
    try:
        with handle:
            handle.write(b'UniPay guide update in progress\n')
        # Повторная проверка после lock. Файлы лабораторных вообще не заменяются.
        changes, before = guide_plan(root, manifest, data, own_lock=True)
        for name, content in changes.items():
            path = target_path(root, name)
            current = path.read_bytes() if path.exists() else None
            if current != before[name]:
                raise DeliveryError('Файл изменился во время обновления: ' + name)
            create_parents(path.parent, root, created_dirs)
            replace_guide_file(path, content)
            written.append(name)
    except BaseException as original:
        try:
            for name in reversed(written):
                path = target_path(root, name)
                if path.read_bytes() != changes[name]:
                    raise DeliveryError('Файл изменён параллельно: ' + name)
                if before[name] is None:
                    path.unlink()
                else:
                    replace_guide_file(path, before[name])
            for directory in reversed(created_dirs):
                directory.rmdir()
        except BaseException as rollback_error:
            release_lock = False
            raise DeliveryError('Обновление памятки прервано; lock сохранён. Не удаляйте файлы, обратитесь к преподавателю.') from rollback_error
        raise original
    finally:
        if release_lock:
            lock.unlink()
    result.update(files=sorted(changes), applied=bool(changes), already_applied=not changes)
    return result


def main():
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, 'reconfigure'):
            stream.reconfigure(encoding='utf-8', errors='backslashreplace')
    parser = argparse.ArgumentParser(description='UniPay: получить лабораторную по номеру из публичного репозитория.')
    parser.add_argument('lab', nargs='?', type=int, choices=range(1, 7))
    parser.add_argument('--variant', choices=ORDER, help='При первой загрузке; затем вариант берётся из .unipay/course.json')
    parser.add_argument('--target', type=Path, default=Path('.'), help='Корень репозитория группы; по умолчанию текущая папка')
    parser.add_argument('--update-guide', action='store_true', help='Обновить только памятку уже полученной ЛР1; решения не менять')
    parser.add_argument('--list', action='store_true', help='Показать опубликованные номера без установки')
    parser.add_argument('--dry-run', action='store_true', help='Показать изменения без записи')
    parser.add_argument('--yes', action='store_true', help='Явно подтвердить добавление без интерактивного вопроса')
    parser.add_argument('--version', action='version', version='UniPay client 2')
    args = parser.parse_args()
    try:
        if sys.version_info < (3, 10):
            raise DeliveryError('Для курса нужен Python 3.10 или новее. Проверьте: python --version.')
        if args.yes and args.dry_run:
            raise DeliveryError('Выберите --yes или --dry-run, не оба сразу.')
        catalog = validate_catalog(decode_json(download('catalog.json', MAX_CATALOG)))
        if args.list:
            print('Открытые лабораторные: ' + (', '.join(sorted(catalog['labs'], key=int)) or 'пока нет'))
            print('Варианты: ' + ', '.join(ORDER))
            return 0
        root = absolute_folder(args.target)
        variant = args.variant or current_variant(root)
        if variant is None:
            if not sys.stdin.isatty():
                raise DeliveryError('При первом запуске укажите --variant, например --variant card.')
            for number, name in enumerate(ORDER, 1):
                print(f'{number:2d}. {name}')
            choice = input('Вариант, назначенный преподавателем (номер или имя): ').strip().lower()
            if choice.isdecimal() and int(choice) in range(1, 15):
                choice = ORDER[int(choice) - 1]
            if choice not in VARIANTS:
                raise DeliveryError('Неизвестный вариант.')
            variant = choice
        number = args.lab
        if number is None:
            if not sys.stdin.isatty():
                raise DeliveryError('Укажите номер лабораторной, например: python unipay.py 1 --variant card')
            print('Открытые номера: ' + ', '.join(sorted(catalog['labs'], key=int)))
            choice = input('Номер лабораторной: ').strip()
            if choice not in ('1', '2', '3', '4', '5', '6'):
                raise DeliveryError('Номер должен быть от 1 до 6.')
            number = int(choice)
        install(number, variant, root, catalog, yes=args.yes, dry_run=args.dry_run, update_guide=args.update_guide)
    except (DeliveryError, OSError, EOFError) as error:
        parser.exit(2, f'Получение остановлено: {error}\n')
    except KeyboardInterrupt:
        parser.exit(130, '\nОстановлено пользователем. При конфликте не удаляйте решения.\n')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
