# -*- coding: utf-8 -*-
from abc import ABCMeta, abstractmethod

from compat import with_metaclass


class AbstractAlerterPlugin(with_metaclass(ABCMeta)):
    """
    AbstractAlerterPlugin - базовый класс для всех оповещателей Inventory.
    Он определяет интерфейс, который должен реализовать оповещатель
    для поддержки отправки оповещений.
    """
    @abstractmethod
    def handle_alert(self, node, match):
        raise NotImplementedError()
