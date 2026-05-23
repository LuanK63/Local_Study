from .tracer import Tracer
from ..types import Serializable, SerializableSequence, UNDEFINED


class Array1DTracer(Tracer):
    def set(self, array1d = UNDEFINED):
        self.command("set", array1d)

    def patch(self, x: int, v: Serializable = UNDEFINED):
        self.command("patch", x, v)

    def depatch(self, x: int):
        self.command("depatch", x)

    def select(self, sx: int, ex: int = UNDEFINED):
        self.command("select", sx, ex)

    def deselect(self, sx: int, ex: int = UNDEFINED):
        self.command("deselect", sx, ex)