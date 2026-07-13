# -*- coding: utf-8 -*-
import six

CMDB_RU_TRANSLATIONS = {
    # Типы объектов.
    'system_info': 'Сведения о системе',
    'os_version': 'Операционная система',
    'local_users': 'Учетные записи',
    'software': 'Установленное ПО',
    'programs': 'Установленное ПО',
    'network': 'Сетевые интерфейсы',
    'usb_devices': 'USB устройства',
    'logical_drives': 'Дисковое пространство',
    'uptime': 'Время работы',
    'patches': 'Установленные обновления',
    'startup_items': 'Автозагрузка',
    'services': 'Службы Windows',
    'scheduled_tasks': 'Запланированные задачи',
    'shared_folders': 'Общие ресурсы',
    'drivers': 'Установленные драйверы',
    'bitlocker': 'Шифрование BitLocker',
    'storage_mounts': 'Точки монтирования',

    # Действия.
    'added': 'Добавлено',
    'removed': 'Удалено',
}

def ru_translate(value):
    if not value:
        return value
    if isinstance(value, six.string_types):
        return CMDB_RU_TRANSLATIONS.get(value, value)
    return value
