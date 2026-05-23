import atexit
import json
import os

from . import randomize as Randomize
from .commander import Commander
from .tracers import *

__all__ = (
    "Randomize", "Commander",
    "Array1DTracer", "Array2DTracer", "ChartTracer", "GraphTracer", "LogTracer", "Tracer",
)


@atexit.register
def execute():
    commands = json.dumps(Commander.commands, separators=(",", ":"))
    if os.getenv("ALGORITHM_VISUALIZER"):
        with open("visualization.json", "w", encoding="UTF-8") as file:
            file.write(commands)
    else:
        # For desktop app, we will interpret commands internally
        pass