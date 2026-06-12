from .tracer import Tracer
from ..types import Serializable, UNDEFINED


class LogTracer(Tracer):
    def set(self, log = UNDEFINED):
        self.command("set", log)

    def print(self, message):
        self.command("print", message)

    def println(self, message):
        self.command("println", message)

    def printf(self, format, *args):
        self.command("printf", format, *args)