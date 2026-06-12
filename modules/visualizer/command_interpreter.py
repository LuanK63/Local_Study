"""
modules/visualizer/command_interpreter.py
Interpret commands from algorithm_visualizer library into UI updates.
"""
import json
from typing import Dict, Any, List
from PyQt6.QtCore import QObject, pyqtSignal

from modules.algorithm_visualizer import Commander


class CommandInterpreter(QObject):
    """Interpret algorithm_visualizer commands into UI signals."""

    # Signals for UI updates
    frame_update = pyqtSignal(dict)  # payload for tracers
    delay_request = pyqtSignal(int)  # delay in ms

    def __init__(self, parent=None):
        super().__init__(parent)
        self._tracers = {}  # key -> tracer info
        self._current_delay = 500

    def interpret_commands(self, commands: List[Dict[str, Any]]):
        """Interpret a list of commands."""
        for cmd in commands:
            self._interpret_command(cmd)

    def _interpret_command(self, cmd: Dict[str, Any]):
        """Interpret a single command."""
        key = cmd.get('key')
        method = cmd.get('method')
        args = cmd.get('args', [])

        if method == 'delay':
            if args and isinstance(args[0], int):
                self.delay_request.emit(args[0])
            return

        # Handle tracer commands
        if key:
            # For now, emit all commands with key
            payload = {
                'method': method,
                'args': args,
                'key': key
            }
            self.frame_update.emit(payload)
        elif method in ('Array1DTracer', 'Array2DTracer', 'ChartTracer', 'GraphTracer', 'LogTracer'):
            # Create new tracer
            self._tracers[key] = {
                'type': method.lower().replace('tracer', ''),
                'title': args[0] if args else method
            }
        # Other commands can be handled as needed

    def reset(self):
        """Reset interpreter state."""
        self._tracers.clear()
        Commander.commands.clear()