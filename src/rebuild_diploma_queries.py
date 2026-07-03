# -*- coding: utf-8 -*-
"""
Rebuild scheduled osquery packs for a diploma demo stand.

The script keeps agents/nodes intact, removes old scheduled query packs, clears
old collected inventory rows, and creates one compact Windows inventory pack.
"""
from application import create_app
from database import db
from models import (
    CmdbObject,
    CmdbValue,
    DistributedQuery,
    DistributedQueryResult,
    DistributedQueryTask,
    Node,
    Pack,
    Query,
    ResultLog,
    Tag,
    pack_tags,
    query_tags,
    querypacks,
)
from settings import Config
from utils import validate_osquery_query


INTERVAL_SECONDS = 20
PACK_TAG = u"диплом"
PACK_NAME = u"Диплом: базовая инвентаризация"
PACK_DESCRIPTION = (
    u"Демонстрационный пакет для защиты диплома: сбор сведений о программном "
    u"обеспечении, аппаратной конфигурации ПК и сетевых параметрах Windows."
)

QUERY_SPECS = [
    {
        "name": u"Система и ОС",
        "category": u"Железо",
        "description": (
            u"Общие сведения о компьютере: имя, UUID, производитель, модель, "
            u"серийный номер, процессор, объем ОЗУ и версия Windows."
        ),
        "sql": (
            "SELECT s.hostname, s.computer_name, s.local_hostname, s.uuid, "
            "s.hardware_vendor, s.hardware_model, s.hardware_serial, "
            "s.cpu_brand, s.cpu_physical_cores, s.cpu_logical_cores, "
            "s.physical_memory, o.name AS os_name, o.version AS os_version, "
            "o.build AS os_build, o.platform, o.install_date "
            "FROM system_info s, os_version o;"
        ),
    },
    {
        "name": u"Процессор",
        "category": u"Железо",
        "description": (
            u"Информация о процессоре: модель, производитель, количество ядер, "
            u"логические процессоры и рабочие частоты."
        ),
        "sql": (
            "SELECT device_id, model, manufacturer, number_of_cores, "
            "logical_processors, address_width, current_clock_speed, "
            "max_clock_speed, socket_designation FROM cpu_info;"
        ),
    },
    {
        "name": u"Оперативная память",
        "category": u"Железо",
        "description": (
            u"Модули оперативной памяти: слот, производитель, серийный номер, "
            u"объем модуля, общий объем ОЗУ, количество модулей, тип и частота."
        ),
        "sql": (
            "SELECT m.device_locator, m.bank_locator, m.manufacturer, "
            "m.serial_number, m.part_number, m.size AS module_size_mb, "
            "s.physical_memory AS total_physical_memory, "
            "CAST(s.physical_memory / 1048576 AS INTEGER) AS total_physical_memory_mb, "
            "(SELECT COUNT(*) FROM memory_devices) AS memory_modules_count, "
            "m.memory_type, m.form_factor, m.max_speed, "
            "m.configured_clock_speed FROM memory_devices m, system_info s;"
        ),
    },
    {
        "name": u"Физические диски",
        "category": u"Железо",
        "description": (
            u"Физические накопители ПК: тип, производитель, модель, серийный "
            u"номер, объем и описание устройства."
        ),
        "sql": (
            "SELECT disk_index, type, id, pnp_device_id, disk_size, "
            "manufacturer, hardware_model, name, serial, description "
            "FROM disk_info;"
        ),
    },
    {
        "name": u"Логические диски",
        "category": u"Железо",
        "description": (
            u"Логические разделы и тома: буква диска, файловая система, общий "
            u"объем и свободное место."
        ),
        "sql": (
            "SELECT device_id, type, free_space, size, file_system, "
            "boot_partition FROM logical_drives;"
        ),
    },
    {
        "name": u"Установленное ПО",
        "category": u"ПО",
        "description": (
            u"Список установленного программного обеспечения Windows: название, "
            u"версия, издатель, дата установки и путь установки."
        ),
        "sql": (
            "SELECT name, version, publisher, install_date, install_location, "
            "identifying_number FROM programs;"
        ),
    },
    {
        "name": u"Сетевые интерфейсы",
        "category": u"Сеть",
        "description": (
            u"Сетевые адаптеры: имя интерфейса, MAC-адрес, производитель, "
            u"статус подключения, DHCP, DNS и скорость линка."
        ),
        "sql": (
            "SELECT interface, friendly_name, description, mac, manufacturer, "
            "connection_id, connection_status, enabled, physical_adapter, "
            "dhcp_enabled, dhcp_server, dns_server_search_order, link_speed "
            "FROM interface_details;"
        ),
    },
    {
        "name": u"IP-адреса",
        "category": u"Сеть",
        "description": (
            u"IP-адреса сетевых интерфейсов без loopback-адресов: интерфейс, "
            u"адрес, маска и тип адреса."
        ),
        "sql": (
            "SELECT interface, friendly_name, address, mask, type "
            "FROM interface_addresses "
            "WHERE address NOT IN ('127.0.0.1', '::1', '0.0.0.0');"
        ),
    },
    {
        "name": u"Маршруты",
        "category": u"Сеть",
        "description": (
            u"Таблица маршрутизации: назначение, маска, шлюз, интерфейс, "
            u"метрика и тип маршрута."
        ),
        "sql": (
            "SELECT destination, netmask, gateway, source, interface, metric, "
            "type FROM routes;"
        ),
    },
    {
        "name": u"Открытые порты",
        "category": u"Сеть",
        "description": (
            u"Локальные слушающие порты и процессы-владельцы для базовой "
            u"оценки сетевой поверхности ПК."
        ),
        "sql": (
            "SELECT lp.address, lp.port, lp.protocol, lp.family, lp.pid, "
            "p.name AS process_name, p.path AS process_path "
            "FROM listening_ports lp "
            "LEFT JOIN processes p ON lp.pid = p.pid "
            "WHERE lp.port != 0;"
        ),
    },
]


def get_or_create_tag(value):
    tag = Tag.query.filter_by(value=value).first()
    if tag:
        return tag
    tag = Tag(value=value)
    db.session.add(tag)
    db.session.flush()
    return tag


def add_tag_once(target, tag):
    if tag.value not in [existing.value for existing in target.tags]:
        target.tags.append(tag)


def validate_queries():
    invalid = []
    for spec in QUERY_SPECS:
        if not validate_osquery_query(spec["sql"]):
            invalid.append(spec["name"])
    if invalid:
        raise RuntimeError(
            u"Некорректные SQL-запросы: {0}".format(u", ".join(invalid))
        )


def rebuild():
    validate_queries()

    old_packs = Pack.query.count()
    old_queries = Query.query.count()
    old_results = ResultLog.query.count()

    db.session.execute(querypacks.delete())
    db.session.execute(pack_tags.delete())
    db.session.execute(query_tags.delete())

    deleted_distributed_results = DistributedQueryResult.query.delete(
        synchronize_session=False
    )
    deleted_distributed_tasks = DistributedQueryTask.query.delete(
        synchronize_session=False
    )
    deleted_distributed_queries = DistributedQuery.query.delete(
        synchronize_session=False
    )
    deleted_result_logs = ResultLog.query.delete(synchronize_session=False)
    deleted_cmdb_values = CmdbValue.query.delete(synchronize_session=False)
    deleted_cmdb_objects = CmdbObject.query.delete(synchronize_session=False)
    deleted_queries = Query.query.delete(synchronize_session=False)
    deleted_packs = Pack.query.delete(synchronize_session=False)

    diploma_tag = get_or_create_tag(PACK_TAG)
    pack = Pack(
        name=PACK_NAME,
        platform="windows",
        version="1.0.0",
        description=PACK_DESCRIPTION,
    )
    pack.tags = [diploma_tag]
    db.session.add(pack)

    for spec in QUERY_SPECS:
        category_tag = get_or_create_tag(spec["category"])
        query = Query(
            name=spec["name"],
            sql=spec["sql"],
            interval=INTERVAL_SECONDS,
            platform="windows",
            description=spec["description"],
            value=spec["category"],
            removed=False,
        )
        db.session.add(query)
        query.tags = [diploma_tag, category_tag]
        pack.queries.append(query)

    tagged_nodes = 0
    for node in Node.query.filter_by(is_active=True).all():
        before = len(node.tags)
        add_tag_once(node, diploma_tag)
        if len(node.tags) != before:
            tagged_nodes += 1

    db.session.commit()

    print(u"Готово.")
    print(u"Старые пакеты: {0}, удалено: {1}".format(old_packs, deleted_packs))
    print(u"Старые запросы: {0}, удалено: {1}".format(old_queries, deleted_queries))
    print(u"Новый пакет: {0}".format(PACK_NAME))
    print(u"Новых запросов: {0}".format(len(QUERY_SPECS)))
    print(u"Интервал каждого запроса: {0} секунд".format(INTERVAL_SECONDS))
    print(u"Метка пакета и агентов: {0}".format(PACK_TAG))
    print(u"Агентов промаркировано: {0}".format(tagged_nodes))
    print(u"Старые ResultLog: {0}, удалено: {1}".format(old_results, deleted_result_logs))
    print(u"Удалено CMDB objects/values: {0}/{1}".format(deleted_cmdb_objects, deleted_cmdb_values))
    print(
        u"Удалено оперативных запросов/tasks/results: {0}/{1}/{2}".format(
            deleted_distributed_queries,
            deleted_distributed_tasks,
            deleted_distributed_results,
        )
    )


if __name__ == "__main__":
    app = create_app(Config)
    with app.app_context():
        rebuild()
