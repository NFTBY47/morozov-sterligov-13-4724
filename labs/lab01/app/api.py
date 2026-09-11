"""Готовая Python-граница: студент не меняет этот файл."""
from app.services.assembly import build_service
from app.services import clearing_service as implementation


def create(**kwargs):
    return build_service(**kwargs)


def make(*args, **kwargs):
    return implementation.make_entity(*args, **kwargs)


def call(service, method, *args, **kwargs):
    return implementation.invoke(service, method, *args, **kwargs)


def view(entity):
    return implementation.view(entity)
