from __future__ import annotations
from dataclasses import dataclass
from typing import cast, overload, NoReturn
from collections.abc import Iterable, Iterator
from enum import Enum
from functools import total_ordering
from re import compile, I


__all__ = ("Hyperions", "ProcessExtent", "HyperE")


# Constants
DEFAULT_BASE = 10
E_PREFIX_R = compile(r"E(\[(?P<base>\d+)\])?", I)
COMPONENT_R = compile(r"(?P<argument>\d+)|(?P<hyperions>#+)")


@dataclass(slots=True, order=True, frozen=True)
class Hyperions:
    count: int = 1

    def __add__(self, other: object) -> Hyperions:
        if isinstance(other, type(self)):
            return type(self)(self.count + other.count)
        else:
            return NotImplemented

    def __mul__(self, other: int) -> Hyperions:
        if isinstance(other, int):
            return type(self)(self.count * other)
        else:
            return NotImplemented


@total_ordering
class ProcessExtent(Enum):
    CONSTRUCT = 0
    VALIDATE = 1
    NORMALIZE = 2

    def __lt__(self, other: object) -> bool:
        if isinstance(other, type(self)):
            return self.value < other.value
        else:
            return NotImplemented


class ComponentsDescriptor:
    def __get__(
        self, obj: HyperE, objtype: type[HyperE] | None = None
    ) -> list[int | Hyperions]:
        return obj._components

    def __set__(self, obj: HyperE, value: Iterable[int | Hyperions]) -> None:
        obj._components = list(value)
        obj.is_validated = False
        obj.is_normalized = False


class HyperE:
    _components: list[int | Hyperions]
    components = ComponentsDescriptor()
    base: int
    is_validated: bool
    is_normalized: bool

    @overload
    def __init__(
        self,
        /,
        *args: int | Hyperions,
        base: int | None = ...,
        process_extent: ProcessExtent = ...,
    ):
        ...

    @overload
    def __init__(
        self,
        components: Iterable[int | Hyperions],
        /,
        *,
        base: int | None = ...,
        process_extent: ProcessExtent = ...,
    ):
        ...

    @overload
    def __init__(
        self,
        expression: str,
        /,
        *,
        base: int | None = ...,
        process_extent: ProcessExtent = ...,
    ):
        ...

    @overload
    def __init__(
        self,
        other: HyperE,
        /,
        *,
        base: int | None = ...,
        process_extent: ProcessExtent = ...,
    ):
        ...

    def __init__(
        self,
        /,
        *args: object,
        base: int | None = None,
        process_extent: ProcessExtent = ProcessExtent.NORMALIZE,
    ):
        copied = False
        match args:
            case []:
                raise TypeError("__init__() missing required arguments")
            case [str(expression)]:
                parsed_base, components = self._parse(expression)
                if parsed_base and base:
                    raise ValueError(
                        "base provided both in parsed string and as argument to constructor"
                    )

                base = parsed_base or base
                self._init(components, base or DEFAULT_BASE, True)
            case [HyperE() as other]:
                self.copy_from(other)
                self.base = base or self.base
                copied = True
            case [[*components]] | [*components]:
                self._init(
                    cast(Iterable[int | Hyperions], components),
                    base or DEFAULT_BASE
                    # This cast is ok because we later check the types
                )

        if process_extent == ProcessExtent.CONSTRUCT and not copied:
            for ix, component in enumerate(self.components):
                self._type_check(type(component), ix)

        if process_extent >= ProcessExtent.VALIDATE:
            self.validate()

        if process_extent >= ProcessExtent.NORMALIZE:
            self.normalize()

    def _init(
        self,
        components: Iterable[int | Hyperions],
        base: int,
        is_validated: bool = False,
        is_normalized: bool = False,
    ) -> None:
        self._components = list(components)
        self.base = base
        self.is_validated = is_validated
        self.is_normalized = is_normalized

    def copy_from(self, other: HyperE) -> None:
        self._components = other._components
        self.base = other.base
        self.is_validated = other.is_validated
        self.is_normalized = other.is_normalized

    @staticmethod
    def _parse(expression: str) -> tuple[int | None, list[int | Hyperions]]:
        e_prefix = E_PREFIX_R.match(expression)
        if e_prefix is None:
            raise SyntaxError("expression does not start with E[<base>]")

        base = e_prefix.group("base")
        if base is not None:
            base = int(base)

        components: list[int | Hyperions] = []
        ix = e_prefix.end()
        expression = expression[ix:]
        while len(expression) != 0:
            component = COMPONENT_R.match(expression)
            if component is None:
                raise SyntaxError(f"found non-digit non-hyperion at index {ix}")

            argument = component.group("argument")
            if argument is not None:
                argument = int(argument)
                if argument == 0:
                    raise ValueError(f"found zero argument at index {ix}")

                components.append(argument)
            elif (hyperions := component.group("hyperions")) is not None:
                components.append(Hyperions(int(len(hyperions))))

            end = component.end()
            ix += end
            expression = expression[end:]

        return base, components

    @staticmethod
    def _type_check(component_type: type, ix: int) -> None:
        if not issubclass(component_type, (int, Hyperions)):
            raise TypeError(
                f"component type must be int or Hyperions, found '{component_type.__name__}' at {ix}"
            )

    def validate(self) -> None:
        def nonpositive_check(value: int, ix: int, name: str = "component") -> None:
            if value <= 0:
                raise ValueError(
                    f"{name} cannot be zero or lower, found such a component at index {ix}"
                )

        if self.is_validated:
            return

        components = self.components
        if len(components) == 0:
            raise ValueError("component list cannot be empty")

        head = components[0]
        component_type = type(head)
        self._type_check(component_type, 0)
        if isinstance(head, Hyperions):
            raise ValueError("component list cannot start with hyperions")

        nonpositive_check(head, 0)
        previous_type: type[int] | type[Hyperions] = int
        for ix, component in enumerate(components[1:], 1):
            self._type_check(type(component), ix)
            if isinstance(component, int):
                nonpositive_check(component, ix)
                if issubclass(previous_type, int):
                    raise ValueError(
                        f"component list cannot contain adjacent integer components, found two at index {ix - 1}"
                    )

            else:
                nonpositive_check(component.count, ix, "count")

            previous_type = type(component)

        self._type_check(previous_type, len(components))
        if issubclass(previous_type, Hyperions):
            raise ValueError("component list cannot end with hyperions")

        self.is_validated = True

    def normalize(self) -> None:
        self.validate()
        self.components = list(self.normalized())

    def normalized(self) -> Iterator[int | Hyperions]:
        if not self.is_validated:
            raise ValueError("object is not validated")

        components = self.components
        if self.is_normalized or len(components) <= 1:
            yield from components
            return

        iterator = iter(components)
        yield next(iterator)  # First component is never hyperions
        try:
            previous = next(iterator)
        except StopIteration:
            return

        count: int | None = cast(Hyperions, previous).count
        # This cast is ok because the second component is always hyperions
        for component in iterator:
            if count is not None and isinstance(component, Hyperions):
                count += component.count
            else:
                if count is not None:
                    yield Hyperions(count)
                    count = None
                yield component

        # Last component is never hyperions

    def evaluate(self) -> int:
        self.validate()
        return self._evaluate(list(self.normalized()), self.base)

    # warning: components must be normalized
    @classmethod
    def _evaluate(cls, components: list[int | Hyperions], base: int) -> int:
        match components:
            case [argument]:
                return cast(int, base ** cast(int, argument))
                # These casts are valid because:
                # 1) integer to the power of an integer is an integer
                # 2) first component is never hyperions
            case [*components, 1]:
                return cls._evaluate(components[:-1], base)
            case [*components, argument_1, Hyperions(count), argument_2] if count > 1:
                return cls._evaluate(
                    components
                    + [
                        argument_1,
                        Hyperions(count - 1),
                        argument_1,
                        Hyperions(count),
                        cast(int, argument_2) - 1,
                    ],
                    base,
                )
                # This cast is ok because a hyperion sequence is succeeded by an argument
            case [*components, argument_1, Hyperions(1) as h1, argument_2]:
                return cls._evaluate(
                    components
                    + [
                        cls._evaluate(
                            components + [argument_1, h1, cast(int, argument_2) - 1],
                            base,
                        )
                    ],
                    base,
                )
                # This cast is ok because a hyperion sequence is succeeded by an argument

        raise ValueError(
            "_evaluate() called with unnormalized components-this should never happen"
        )

    def __str__(self) -> str:
        string_components = [f"E[{self.base}]"]
        for component in self.components:
            if isinstance(component, int):
                string_components.append(str(component))
            else:
                string_components.append("#" * component.count)

        return "".join(string_components)

    def __repr__(self) -> str:
        return f'{type(self).__name__}("{str(self)}")'
