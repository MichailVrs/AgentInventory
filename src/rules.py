# -*- coding: utf-8 -*-
import re
import logging
from collections import namedtuple

import six


logger = logging.getLogger(__name__)


RuleInput = namedtuple('RuleInput', ['result_log', 'node'])
RuleMatch = namedtuple('RuleMatch', ['rule', 'result', 'node'])


class Network(object):
    """
    Группа узлов условий. Содержит базовую логику запуска условий
    на входных данных.
    """
    def __init__(self):
        self.conditions = {}
        self.alert_conditions = []

    def make_condition(self, klass, *args, **kwargs):
        """
        Конструктор условий с мемоизацией. Использует входную конфигурацию
        как ключ кэша.
        """
        # Вычисляем ключ мемоизации как кортеж из трех элементов:
        # (имя класса условия, args, kwargs). Здесь есть нюанс: args/kwargs
        # нужно привести к правильному формату. Мы рекурсивно обходим списки
        # и словари, преобразуем их в кортежи и извлекаем ключ мемоизации
        # из экземпляров BaseCondition.
        def tupleify(obj):
            if isinstance(obj, BaseCondition):
                return obj.__network_memo_key
            elif isinstance(obj, tuple):
                return tuple(tupleify(x) for x in obj)
            elif isinstance(obj, list):
                return tuple(tupleify(x) for x in obj)
            elif isinstance(obj, dict):
                items = ((tupleify(k), tupleify(v)) for k, v in obj.items())
                return tuple(sorted(items))
            else:
                return obj

        args_tuple = tupleify(args)
        kwargs_tuple = tupleify(kwargs)

        key = (klass.__name__, args_tuple, kwargs_tuple)
        if key in self.conditions:
            return self.conditions[key]

        # Создаем экземпляр класса условия. Также сохраняем ключ мемоизации
        # в экземпляре, чтобы его можно было получить выше.
        inst = klass(*args, **kwargs)
        inst.__network_memo_key = key

        # Сохраняем условие.
        self.conditions[key] = inst
        return inst

    def make_alert_condition(self, alert, dependent, rule_id=None):
        self.alert_conditions.append((alert, dependent, rule_id))

    def process(self, entry, node):
        input = RuleInput(result_log=entry, node=node)

        # Шаг 1: помечаем все условия как еще не вычисленные.
        for condition in self.conditions.values():
            condition.evaluated = False

        # Шаг 2: для каждого условия оповещения передаем новый вход на
        # обработку. Это поднимется вверх по цепочке к каждому узлу условия
        # и вычислит зависимую цепочку условий. Затем проверяем,
        # сработало ли условие.
        alerts = set()
        for (alert, upstream, rule_id) in self.alert_conditions:
            if upstream.run(input):
                alerts.add((alert, rule_id))

        # Шаг 3: возвращаем вызывающему коду все оповещения.
        return alerts

    def parse_query(self, query, alerters=None, rule_id=None):
        """
        Разбирает результат jQuery.QueryBuilder.
        """
        def parse_condition(d):
            op = d['operator']
            value = d['value']
            
            # Если это "оператор колонки", то есть операция над конкретным
            # значением в колонке, передаем пользовательскую функцию извлечения,
            # которая знает, как получить это значение из запроса.
            column_name = None
            if d['field'] == 'column':
                # Убираем префикс 'column_', чтобы получить реальный оператор.
                op = op[7:]

                if isinstance(value, six.string_types):
                    column_name = value
                else:
                    # Массив 'value' будет выглядеть как ['column_name', 'фактическое значение'].
                    column_name, value = value

            klass = OPERATOR_MAP.get(op)
            if not klass:
                raise ValueError("Unsupported operator: {0}".format(op))
            
            inst = self.make_condition(klass, d['field'], value, column_name=column_name)
            return inst
        
        def parse_group(d):
            if len(d['rules']) == 0:
                raise ValueError("A group contains no rules")

            upstreams = [parse(r) for r in d['rules']]

            condition = d['condition']
            if condition == 'AND':
                return self.make_condition(AndCondition, upstreams)
            elif condition == 'OR':
                return self.make_condition(OrCondition, upstreams)

            raise ValueError("Unknown condition: {0}".format(condition))

        def parse(d):
            if 'condition' in d:
                return parse_group(d)
            
            return parse_condition(d)

        # Корневой элемент всегда является группой.
        root = parse_group(query)

        # Добавляем условия оповещения, которые срабатывают вместе с этой группой.
        if alerters is not None:
            for alert in alerters:
                self.make_alert_condition(alert, root, rule_id)


class BaseCondition(object):
    """
    Базовый класс условий. Содержит логику добавления зависимости
    к условию и его человекочитаемого представления.
    """
    def __init__(self):
        self.evaluated = False
        self.cached_value = None
        self.network = None

    def init_network(self, network):
        self.network = network

    def run(self, input):
        """
        Запускает условие, если оно еще не было вычислено.
        """
        assert isinstance(input, RuleInput)

        logger.debug("Evaluating condition %r on input: %r", self, input)
        if self.evaluated:
            logger.debug("Returning cached value: %r", self.cached_value)
            return self.cached_value

        ret = self.local_run(input)
        logger.debug("Condition %r returned value: %r", self, ret)
        self.cached_value = ret
        self.evaluated = True
        return ret

    def local_run(self, input):
        """
        Подклассы должны реализовать этот метод для запуска логики условия.
        """
        raise NotImplementedError()

    def __repr__(self):
        return '<{0} (evaluated={1})>'.format(
            self.__class__.__name__,
            self.evaluated
        )


class AndCondition(BaseCondition):
    def __init__(self, upstream):
        super(AndCondition, self).__init__()
        self.upstream = upstream

    def local_run(self, input):
        for u in self.upstream:
            if not u.run(input):
                return False

        return True


class OrCondition(BaseCondition):
    def __init__(self, upstream):
        super(OrCondition, self).__init__()
        self.upstream = upstream

    def local_run(self, input):
        for u in self.upstream:
            if u.run(input):
                return True

        return False


class LogicCondition(BaseCondition):
    def __init__(self, key, expected, column_name=None):
        super(LogicCondition, self).__init__()
        self.key = key
        self.expected = self.maybe_make_number(expected)
        self.column_name = column_name

    def maybe_make_number(self, value):
        if not isinstance(value, six.string_types):
            return value

        if value.isdigit():
            return int(value)
        elif '.' in value and value.replace('.', '', 1).isdigit():
            return float(value)

        return value

    def local_run(self, input):
        # Если есть 'column_name', используем его для извлечения значения
        # из колонок входных данных. Иначе работаем с разрешенным списком
        # полей, которые можно получить из входа.
        if self.column_name is not None:
            value = input.result_log['columns'].get(self.column_name)
        elif self.key == 'query_name':
            value = input.result_log['name']
        elif self.key == 'timestamp':
            value = input.result_log['timestamp']
        elif self.key == 'action':
            value = input.result_log['action']
        elif self.key == 'host_identifier':
            value = input.node['host_identifier']
        else:
            raise KeyError('Unknown key: {0}'.format(self.key))

        # Пытаемся преобразовать значение в число, если оно похоже на число.
        value = self.maybe_make_number(value)

        # Передаем значение в реальную функцию логики.
        logger.debug("Running logic condition %r: %r | %r", self, self.expected, value)
        return self.compare(value)

    def compare(self, value):
        """
        Подклассы должны реализовать этот метод для выполнения сравнения.
        """
        raise NotImplementedError()


class EqualCondition(LogicCondition):
    def compare(self, value):
        return value == self.expected


class NotEqualCondition(LogicCondition):
    def compare(self, value):
        return value != self.expected


class BeginsWithCondition(LogicCondition):
    def compare(self, value):
        return value.startswith(self.expected)


class NotBeginsWithCondition(LogicCondition):
    def compare(self, value):
        return not value.startswith(self.expected)


class ContainsCondition(LogicCondition):
    def compare(self, value):
        return self.expected in value


class NotContainsCondition(LogicCondition):
    def compare(self, value):
        return self.expected not in value


class EndsWithCondition(LogicCondition):
    def compare(self, value):
        return value.endswith(self.expected)


class NotEndsWithCondition(LogicCondition):
    def compare(self, value):
        return not value.endswith(self.expected)


class IsEmptyCondition(LogicCondition):
    def compare(self, value):
        return value == ''


class IsNotEmptyCondition(LogicCondition):
    def compare(self, value):
        return value != ''


class LessCondition(LogicCondition):
    def compare(self, value):
        return value < self.expected


class LessEqualCondition(LogicCondition):
    def compare(self, value):
        return value <= self.expected


class GreaterCondition(LogicCondition):
    def compare(self, value):
        return value > self.expected


class GreaterEqualCondition(LogicCondition):
    def compare(self, value):
        return value >= self.expected


class MatchesRegexCondition(LogicCondition):
    def __init__(self, key, expected, **kwargs):
        # Предварительно компилируем ожидаемое значение, то есть регулярное выражение.
        expected = re.compile(expected)
        super(MatchesRegexCondition, self).__init__(key, expected, **kwargs)

    def compare(self, value):
        return self.expected.match(value) is not None


class NotMatchesRegexCondition(LogicCondition):
    def __init__(self, key, expected, **kwargs):
        # Предварительно компилируем ожидаемое значение, то есть регулярное выражение.
        expected = re.compile(expected)
        super(NotMatchesRegexCondition, self).__init__(key, expected, **kwargs)

    def compare(self, value):
        return self.expected.match(value) is None


# Должно оставаться в конце файла.
OPERATOR_MAP = {
    'equal': EqualCondition,
    'not_equal': NotEqualCondition,
    'begins_with': BeginsWithCondition,
    'not_begins_with': NotBeginsWithCondition,
    'contains': ContainsCondition,
    'not_contains': NotContainsCondition,
    'ends_with': EndsWithCondition,
    'not_ends_with': NotEndsWithCondition,
    'is_empty': IsEmptyCondition,
    'is_not_empty': IsNotEmptyCondition,
    'less': LessCondition,
    'less_or_equal': LessEqualCondition,
    'greater': GreaterCondition,
    'greater_or_equal': GreaterEqualCondition,
    'matches_regex': MatchesRegexCondition,
    'not_matches_regex': NotMatchesRegexCondition,
}
