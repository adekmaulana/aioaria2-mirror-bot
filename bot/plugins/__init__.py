import importlib
import pkgutil
from pathlib import Path

current_dir = str(Path(__file__).parent)
subplugins = [
    importlib.import_module("." + info.name, __name__)
    for info in pkgutil.iter_modules([current_dir])
]