import py_compile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def test_smoke():
    assert True


def test_entry_points_compile():
    """main.py e os scripts não são importados pelos outros testes."""
    for path in [ROOT / 'main.py', *ROOT.glob('scripts/*.py'), *ROOT.glob('services/*.py')]:
        py_compile.compile(str(path), doraise=True)
