from pathlib import Path
import membrain
from membrain.build_identity import BUILD_ID, SCHEMA_ID

def test_installed_identity():
    assert Path(membrain.__file__).parent == Path('/Users/yichen/tmp/membrain-ci-closeout-20261105/installed/site/membrain')
    assert BUILD_ID == '9029d20d74b2b7e3726e5fa6cb40c66e9ca59634a669851e7a61e8d7264a250e'
    assert SCHEMA_ID == 'e2f27d492746a4ac9942312b04a07a37cd5f19e44bd7770bcdcbac54a4a23693'
