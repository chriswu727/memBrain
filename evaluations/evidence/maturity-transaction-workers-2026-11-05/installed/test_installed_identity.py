from pathlib import Path
import membrain
from membrain.build_identity import BUILD_ID, SCHEMA_ID

def test_installed_identity():
    assert Path(membrain.__file__).parent == Path('/Users/yichen/tmp/membrain-host-attribution-20261105/installed/site/membrain')
    assert BUILD_ID == 'c86dddc8c5656a8e150ff3b7f3a68466fafaf6145d26c92a87251e769aced9f6'
    assert SCHEMA_ID == 'e2f27d492746a4ac9942312b04a07a37cd5f19e44bd7770bcdcbac54a4a23693'
