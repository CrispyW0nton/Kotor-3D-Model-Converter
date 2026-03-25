import sys

from pathlib import Path

src = Path(r"G:/GitHub/Andastra/vendor/PyKotor/Libraries/PyKotor/src")
if str(src) not in sys.path:
    sys.path.insert(0, str(src))
print("src in sys.path:", str(src) in sys.path)
try:
    import importlib

    mod = importlib.import_module("utility.gui.qt.widgets.itemviews.file_size_delegate")
    print("Imported OK:", mod.__name__)
except Exception as e:
    import traceback

    traceback.print_exc()
