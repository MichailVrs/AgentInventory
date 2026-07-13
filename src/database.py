# -*- coding: utf-8 -*-
"""Модуль базы данных: объект SQLAlchemy и связанные с БД утилиты."""
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, INET  # noqa
from sqlalchemy.ext.declarative import declared_attr
from sqlalchemy.orm import relationship

from compat import basestring
from extensions import db


# Псевдонимы для часто используемых имен SQLAlchemy.
Column = db.Column
Table = db.Table
ForeignKey = db.ForeignKey
UniqueConstraint = db.UniqueConstraint
relationship = relationship
Index = db.Index


class CRUDMixin(object):
    """Миксин с удобными методами для CRUD-операций."""

    @classmethod
    def create(cls, **kwargs):
        """Создает новую запись и сохраняет ее в базе данных."""
        instance = cls(**kwargs)
        return instance.save()

    def update(self, commit=True, **kwargs):
        """Обновляет указанные поля записи."""
        for attr, value in kwargs.items():
            setattr(self, attr, value)
        return commit and self.save() or self

    def save(self, commit=True):
        """Сохраняет запись."""
        db.session.add(self)
        if commit:
            db.session.commit()
        return self

    def delete(self, commit=True):
        """Удаляет запись из базы данных."""
        db.session.delete(self)
        return commit and db.session.commit()


class Model(CRUDMixin, db.Model):
    """Базовый класс модели с удобными CRUD-методами."""

    __abstract__ = True


# Из доклада Майка Байера "Building the app".
# https://speakerdeck.com/zzzeek/building-the-app
class SurrogatePK(object):
    """Миксин, добавляющий суррогатный целочисленный первичный ключ ``id``."""

    __table_args__ = {'extend_existing': True}

    id = db.Column(db.Integer, primary_key=True)

    @classmethod
    def get_by_id(cls, record_id):
        """Возвращает запись по ID."""
        if any(
                (isinstance(record_id, basestring) and record_id.isdigit(),
                 isinstance(record_id, (int, float))),
        ):
            return cls.query.get(int(record_id))
        return None


def reference_col(tablename, nullable=False, pk_name='id', **kwargs):
    """Колонка, добавляющая внешний ключ на первичный ключ.

    Использование: ::

        category_id = reference_col('category')
        category = relationship('Category', backref='categories')
    """
    return db.Column(
        ForeignKey('{0}.{1}'.format(tablename, pk_name)),
        nullable=nullable, **kwargs)
