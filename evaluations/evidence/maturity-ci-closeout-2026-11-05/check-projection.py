import importlib.util,json,sys
from pathlib import Path
from playwright.sync_api import sync_playwright
repo=Path('/Users/yichen/tmp/membrain-review-20261029');root=Path(__file__).parent
sys.path.insert(0,str(repo/'tests'))
from test_brain_projection import payload
from test_memory_observatory_browser import _tab,click_node,settled
spec=importlib.util.spec_from_file_location('preview',repo/'scripts/measure_observatory.py');preview=importlib.util.module_from_spec(spec);spec.loader.exec_module(preview)
server=preview.StaticServer();report={'completed':False}
try:
 with sync_playwright() as pw:
  browser=pw.chromium.launch();context,tab=_tab(browser,reduced_motion='reduce');page=tab.page
  data=payload(24);server.set_map(data);page.goto(server.base_url+'/memory?demo=brain');settled(page)
  hidden=page.evaluate('''() => window.observatory.snapshot().nodes.find(id => {
    const p=window.observatory.project(id);
    return p?.inside && window.observatory.pickAt(p.x,p.y)!==id;
  })''')
  assert hidden,'The fixed fixture must actually contain an occluded node'
  before=page.evaluate('window.observatory.snapshot().view');click_node(page,hidden)
  after=page.evaluate('window.observatory.snapshot().view');assert before!=after
  assert page.evaluate('window.observatory.snapshot().selected')==hidden
  page.locator('#mode-2d').click();page.screenshot(path=str(root/'projection-24.png'))
  count=page.locator('#brain-canvas .brain-node').count();assert count==24
  report.update(completed=True,occluded_id=hidden,view_before=before,view_after=after,node_count=count,page_errors=tab.errors)
  context.close();browser.close()
finally:
 server.close();(root/'projection-check.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report))
