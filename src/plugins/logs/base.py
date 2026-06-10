# -*- coding: utf-8 -*-
from abc import ABCMeta, abstractmethod, abstractproperty

from compat import with_metaclass


class AbstractLogsPlugin(with_metaclass(ABCMeta)):
    @abstractproperty
    def name(self):
        pass

    @abstractmethod
    def handle_status(self, data, **kwargs):
        pass

    @abstractmethod
    def handle_result(self, data, **kwargs):
        pass
