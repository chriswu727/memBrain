import json,os
from pathlib import Path
os.environ['MEMBRAIN_SEMANTIC']='0'
os.environ['PYTHON_DOTENV_DISABLED']='1'
from membrain import desktop,host
from membrain.client import MemoryActionError
from membrain.build_identity import BUILD_ID
from membrain.local_profile import ensure_profile
root=Path('/private/tmp/membrain-server-recording-restart')
ensure_profile(root,database_engine='embedded')
try:
    assert host.start(root)['ready']
    with host.ready_client(root) as client:
        before=client.recording_status()
        assert before=={'paused':False,'revision':0}
        changed=client.set_recording(paused=True,expected_revision=0)
    assert desktop.stop(root)['state']=='stopped'
    assert host.start(root)['ready']
    with host.ready_client(root) as client:
        after=client.recording_status()
        assert after==changed=={'paused':True,'revision':1}
        try:
            client.observe('Synthetic blocked restart input.',conversation_id='restart',branch_id='main',source_event_key='blocked')
        except MemoryActionError as error:
            assert error.code=='recording_paused'
        else:
            raise AssertionError('Paused write was accepted after restart')
        resumed=client.set_recording(paused=False,expected_revision=1)
        accepted=client.observe('Synthetic resumed input.',conversation_id='restart',branch_id='main',source_event_key='resumed')
        assert accepted['outcome']=='completed'
        assert len(client.timeline()['items'])==1
    print(json.dumps({'build_id':BUILD_ID,'fresh_start':True,'full_process_restart':True,'persisted_policy':after,'blocked_write_after_restart':True,'resumed_policy':resumed,'only_resumed_input_stored':True},indent=2))
finally:
    desktop.stop(root)
