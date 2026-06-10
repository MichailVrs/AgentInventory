-- Представление для Программного обеспечения
CREATE OR REPLACE VIEW software_view AS
SELECT 
    o.node_id,
    o.id AS object_id,
    MAX(CASE WHEN a.name = 'name' THEN v.value END) AS name,
    MAX(CASE WHEN a.name = 'version' THEN v.value END) AS version,
    MAX(CASE WHEN a.name = 'publisher' THEN v.value END) AS publisher,
    MAX(CASE WHEN a.name = 'install_date' THEN v.value END) AS install_date
FROM cmdb_object o
JOIN cmdb_value v ON v.object_id = o.id
JOIN cmdb_attribute_dict a ON v.attribute_id = a.id
WHERE o.object_type = 'software'
GROUP BY o.id, o.node_id;

-- Представление для USB-устройств
CREATE OR REPLACE VIEW usb_view AS
SELECT 
    o.node_id,
    o.id AS object_id,
    MAX(CASE WHEN a.name = 'vendor' THEN v.value END) AS vendor,
    MAX(CASE WHEN a.name = 'model' THEN v.value END) AS model,
    MAX(CASE WHEN a.name = 'serial' THEN v.value END) AS serial,
    MAX(CASE WHEN a.name = 'usb_port' THEN v.value END) AS usb_port
FROM cmdb_object o
JOIN cmdb_value v ON v.object_id = o.id
JOIN cmdb_attribute_dict a ON v.attribute_id = a.id
WHERE o.object_type = 'usb'
GROUP BY o.id, o.node_id;

-- Представление для Сетевых интерфейсов
CREATE OR REPLACE VIEW network_view AS
SELECT 
    o.node_id,
    o.id AS object_id,
    MAX(CASE WHEN a.name = 'interface' THEN v.value END) AS interface,
    MAX(CASE WHEN a.name = 'mac' THEN v.value END) AS mac,
    MAX(CASE WHEN a.name = 'address' THEN v.value END) AS ip_address,
    MAX(CASE WHEN a.name = 'mask' THEN v.value END) AS mask
FROM cmdb_object o
JOIN cmdb_value v ON v.object_id = o.id
JOIN cmdb_attribute_dict a ON v.attribute_id = a.id
WHERE o.object_type = 'network'
GROUP BY o.id, o.node_id;

-- Представление для информации о системе
CREATE OR REPLACE VIEW system_info_view AS
SELECT 
    o.node_id,
    o.id AS object_id,
    MAX(CASE WHEN a.name = 'hostname' THEN v.value END) AS hostname,
    MAX(CASE WHEN a.name = 'cpu_brand' THEN v.value END) AS cpu_brand,
    MAX(CASE WHEN a.name = 'cpu_physical_cores' THEN v.value END) AS cpu_physical_cores,
    MAX(CASE WHEN a.name = 'cpu_logical_cores' THEN v.value END) AS cpu_logical_cores,
    MAX(CASE WHEN a.name = 'physical_memory' THEN v.value END) AS physical_memory,
    MAX(CASE WHEN a.name = 'hardware_vendor' THEN v.value END) AS hardware_vendor,
    MAX(CASE WHEN a.name = 'hardware_model' THEN v.value END) AS hardware_model,
    MAX(CASE WHEN a.name = 'hardware_serial' THEN v.value END) AS hardware_serial
FROM cmdb_object o
JOIN cmdb_value v ON v.object_id = o.id
JOIN cmdb_attribute_dict a ON v.attribute_id = a.id
WHERE o.object_type = 'system_info'
GROUP BY o.id, o.node_id;

-- Представление для версии ОС
CREATE OR REPLACE VIEW os_version_view AS
SELECT 
    o.node_id,
    o.id AS object_id,
    MAX(CASE WHEN a.name = 'name' THEN v.value END) AS os_name,
    MAX(CASE WHEN a.name = 'version' THEN v.value END) AS version,
    MAX(CASE WHEN a.name = 'build' THEN v.value END) AS build,
    MAX(CASE WHEN a.name = 'platform' THEN v.value END) AS platform,
    MAX(CASE WHEN a.name = 'install_date' THEN v.value END) AS install_date
FROM cmdb_object o
JOIN cmdb_value v ON v.object_id = o.id
JOIN cmdb_attribute_dict a ON v.attribute_id = a.id
WHERE o.object_type = 'os_version'
GROUP BY o.id, o.node_id;

-- Представление для служб Windows
CREATE OR REPLACE VIEW services_view AS
SELECT 
    o.node_id,
    o.id AS object_id,
    MAX(CASE WHEN a.name = 'name' THEN v.value END) AS service_name,
    MAX(CASE WHEN a.name = 'display_name' THEN v.value END) AS display_name,
    MAX(CASE WHEN a.name = 'status' THEN v.value END) AS status,
    MAX(CASE WHEN a.name = 'start_type' THEN v.value END) AS start_type,
    MAX(CASE WHEN a.name = 'path' THEN v.value END) AS path,
    MAX(CASE WHEN a.name = 'user_account' THEN v.value END) AS user_account
FROM cmdb_object o
JOIN cmdb_value v ON v.object_id = o.id
JOIN cmdb_attribute_dict a ON v.attribute_id = a.id
WHERE o.object_type = 'services'
GROUP BY o.id, o.node_id;

-- Представление для запланированных задач
CREATE OR REPLACE VIEW scheduled_tasks_view AS
SELECT 
    o.node_id,
    o.id AS object_id,
    MAX(CASE WHEN a.name = 'name' THEN v.value END) AS task_name,
    MAX(CASE WHEN a.name = 'action' THEN v.value END) AS action,
    MAX(CASE WHEN a.name = 'path' THEN v.value END) AS path,
    MAX(CASE WHEN a.name = 'last_run_time' THEN v.value END) AS last_run_time,
    MAX(CASE WHEN a.name = 'next_run_time' THEN v.value END) AS next_run_time
FROM cmdb_object o
JOIN cmdb_value v ON v.object_id = o.id
JOIN cmdb_attribute_dict a ON v.attribute_id = a.id
WHERE o.object_type = 'scheduled_tasks'
GROUP BY o.id, o.node_id;

-- Представление для драйверов
CREATE OR REPLACE VIEW drivers_view AS
SELECT 
    o.node_id,
    o.id AS object_id,
    MAX(CASE WHEN a.name = 'device_name' THEN v.value END) AS device_name,
    MAX(CASE WHEN a.name = 'provider' THEN v.value END) AS provider,
    MAX(CASE WHEN a.name = 'version' THEN v.value END) AS version,
    MAX(CASE WHEN a.name = 'date' THEN v.value END) AS driver_date,
    MAX(CASE WHEN a.name = 'signed' THEN v.value END) AS signed
FROM cmdb_object o
JOIN cmdb_value v ON v.object_id = o.id
JOIN cmdb_attribute_dict a ON v.attribute_id = a.id
WHERE o.object_type = 'drivers'
GROUP BY o.id, o.node_id;

-- Представление для BitLocker
CREATE OR REPLACE VIEW bitlocker_view AS
SELECT 
    o.node_id,
    o.id AS object_id,
    MAX(CASE WHEN a.name = 'drive_letter' THEN v.value END) AS drive_letter,
    MAX(CASE WHEN a.name = 'protection_status' THEN v.value END) AS protection_status,
    MAX(CASE WHEN a.name = 'encryption_method' THEN v.value END) AS encryption_method
FROM cmdb_object o
JOIN cmdb_value v ON v.object_id = o.id
JOIN cmdb_attribute_dict a ON v.attribute_id = a.id
WHERE o.object_type = 'bitlocker'
GROUP BY o.id, o.node_id;
