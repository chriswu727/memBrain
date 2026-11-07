from pathlib import Path
import membrain
from membrain.build_identity import BUILD_ID, SCHEMA_ID

def test_installed_identity():
    assert Path(membrain.__file__).parent == Path('/Users/yichen/tmp/membrain-mood-succession-20261105/installed/site/membrain')
    assert BUILD_ID == '44d734997161280f8970f267340636184f01985fa3a98bea82f24a4a77200014'
    assert SCHEMA_ID == 'e2f27d492746a4ac9942312b04a07a37cd5f19e44bd7770bcdcbac54a4a23693'
