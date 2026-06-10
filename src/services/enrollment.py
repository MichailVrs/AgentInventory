# -*- coding: utf-8 -*-
import datetime as dt
from flask import current_app
from database import db
from models import Node, Tag
from tasks import notify_of_node_enrollment

def parse_enroll_secret(request_json):
    """
    Парсит секрет и теги из запроса.
    """
    enroll_secret_key = current_app.config.get('DOORMAN_ENROLL_OVERRIDE', 'enroll_secret')
    enroll_secret = request_json.get(enroll_secret_key)
    if not enroll_secret:
        return None, set()

    delimiter = current_app.config.get('DOORMAN_ENROLL_SECRET_TAG_DELIMITER')
    if delimiter:
        enroll_secret, _, enroll_tags_str = enroll_secret.partition(delimiter)
        enroll_tags = set([tag.strip() for tag in enroll_tags_str.split(delimiter)[:10]])
    else:
        enroll_tags = set()
        
    return enroll_secret, enroll_tags

def resolve_duplicate_node(host_identifier, remote_addr):
    """
    Разрешает конфликт дублирующихся хостов, если DOORMAN_EXPECTS_UNIQUE_HOST_ID = True.
    """
    if not host_identifier:
        return None

    existing_node = Node.query.filter(Node.host_identifier == host_identifier).first()
    if existing_node and not existing_node.enroll_secret:
        current_app.logger.warning(
            "%s - Duplicate host_identifier %s, already enrolled %s",
            remote_addr, host_identifier, existing_node.enrolled_on
        )

        if current_app.config['DOORMAN_EXPECTS_UNIQUE_HOST_ID'] is True:
            current_app.logger.info(
                "%s - Unique host identification is true, %s already enrolled "
                "returning existing node key %s",
                remote_addr, host_identifier, existing_node.node_key
            )
            existing_node.update(
                last_checkin=dt.datetime.utcnow(),
                last_ip=remote_addr
            )
            return existing_node
    return None

def assign_node_tags(node, enroll_tags):
    """
    Связывает теги с узлом (включая дефолтные теги).
    """
    enroll_tags = set(enroll_tags)
    enroll_tags.update(current_app.config.get('DOORMAN_ENROLL_DEFAULT_TAGS', []))

    for value in sorted((t.strip() for t in enroll_tags if t)):
        tag = Tag.query.filter_by(value=value).first()
        if tag and tag not in node.tags:
            node.tags.append(tag)
        elif not tag:
            node.tags.append(Tag(value=value))

def notify_enrollment(node):
    """
    Отправляет Celery-нотификацию о регистрации узла.
    """
    notify_of_node_enrollment.delay(node.to_dict())

def enroll_node(request_json, remote_addr):
    """
    Выполняет логику регистрации (enrollment) узла.
    Возвращает кортеж: (response_data, status_code)
    """
    # Сохраняем исходное поведение: при пустом/невалидном JSON возвращается пустая строка и статус 200
    if not request_json:
        current_app.logger.error(
            "%s - Request did not contain valid JSON data. This could "
            "be an attempt to gather information about this endpoint "
            "or an automated scanner.",
            remote_addr
        )
        return "", 200

    enroll_secret, enroll_tags = parse_enroll_secret(request_json)
    if not enroll_secret:
        current_app.logger.error(
            "%s - No enroll_secret provided by remote host",
            remote_addr
        )
        return {"node_invalid": True}, 200

    node = Node.query.filter(Node.enroll_secret == enroll_secret).first()

    if not node and enroll_secret != current_app.config['ENROLL_SECRET']:
        current_app.logger.error(
            "%s - Invalid enroll_secret %s",
            remote_addr, enroll_secret
        )
        return {"node_invalid": True}, 200

    host_identifier = request_json.get('host_identifier')

    # 1. Если узел уже полностью зарегистрирован
    if node and node.enrolled_on:
        current_app.logger.warning(
            "%s - %s already enrolled on %s, returning existing node_key",
            remote_addr, node, node.enrolled_on
        )

        if node.host_identifier != host_identifier:
            current_app.logger.info(
                "%s - %s changed their host_identifier to %s",
                remote_addr, node, host_identifier
            )
            node.host_identifier = host_identifier

        node.update(
            last_checkin=dt.datetime.utcnow(),
            last_ip=remote_addr
        )

        return {"node_key": node.node_key, "node_invalid": False}, 200

    # 2. Проверка на дублирование host_identifier
    duplicate_node = resolve_duplicate_node(host_identifier, remote_addr)
    if duplicate_node:
        return {"node_key": duplicate_node.node_key, "node_invalid": False}, 200

    # 3. Регистрация нового/существующего узла
    now = dt.datetime.utcnow()
    if node:
        node.update(
            host_identifier=host_identifier,
            last_checkin=now,
            enrolled_on=now,
            last_ip=remote_addr
        )
    else:
        node = Node(
            host_identifier=host_identifier,
            last_checkin=now,
            enrolled_on=now,
            last_ip=remote_addr
        )
        assign_node_tags(node, enroll_tags)
        node.save()

    current_app.logger.info(
        "%s - Enrolled new node %s",
        remote_addr, node
    )

    notify_enrollment(node)

    return {"node_key": node.node_key, "node_invalid": False}, 200
