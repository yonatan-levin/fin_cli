from __future__ import annotations

from singleton import Singleton


def test_singleton_reuses_instance_and_initializes_once() -> None:
    calls: list[int] = []

    class Example(metaclass=Singleton):
        def __init__(self, value: int) -> None:
            calls.append(value)
            self.value = value

    first = Example(1)
    second = Example(2)

    assert first is second
    assert second.value == 1
    assert calls == [1]


def test_singleton_registry_is_scoped_by_class() -> None:
    class First(metaclass=Singleton):
        pass

    class Second(metaclass=Singleton):
        pass

    assert First() is First()
    assert Second() is Second()
    assert First() is not Second()
