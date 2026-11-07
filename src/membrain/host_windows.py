def apply(client, response, query, messages, starts, qualifiers):
    reader = getattr(client, 'recall_windows', None)
    if not callable(reader):
        return
    selected = {}
    for item in (response.get('result') or {}).get('items', []):
        memory = item.get('memory') or {}
        refs = memory.get('evidence_refs') or []
        match = item.get('matched_statement_span')
        if (memory.get('derivation', {}).get('method') != 'direct_capture' or len(refs) != 1
                or not isinstance(match, dict) or not isinstance(memory.get('memory_id'), str)
                or type(memory.get('revision')) is not int):
            continue
        ref = refs[0]
        event = ref.get('event_id')
        if (event not in starts or event in selected or ref.get('relationship') != 'supports'
                or not isinstance(ref.get('span'), dict)):
            continue
        selected[event] = (item, {'memory_id': memory['memory_id'], 'revision': memory['revision'], 'span': match})
    if not selected:
        return
    # A failed fresh source read cannot fall back to an older/truncated timeline copy.
    for event in selected:
        messages.pop(event, None)
    try:
        result = reader([request for _, request in selected.values()], query)
        if not isinstance(result, dict) or not isinstance(result.get('items'), list):
            return
        accepted = {}
        for window in result['items']:
            if not isinstance(window, dict) or window.get('event_id') not in selected:
                return
            event = window['event_id']
            item, request = selected[event]
            ref = item['memory']['evidence_refs'][0]
            span = window.get('window_span') or {}
            text = window.get('text')
            if (event in accepted or window.get('memory_id') != request['memory_id']
                    or window.get('revision') != request['revision'] or window.get('evidence_ref') != ref
                    or not isinstance(text, str) or not 1 <= len(text) <= 700
                    or type(span.get('start')) is not int or type(span.get('end')) is not int
                    or span.get('unit') != 'unicode_code_point' or span['end'] - span['start'] != len(text)
                    or not ref['span']['start'] <= span['start'] <= starts[event] < span['end'] <= ref['span']['end']
                    or window.get('world') != item['memory'].get('world')
                    or not isinstance(window.get('world'), str)
                    or window.get('actor_role') not in ('user', 'operator')
                    or not isinstance(window.get('source_act'), str)):
                return
            accepted[event] = window
        for event, window in accepted.items():
            messages[event] = window
            starts[event] = 0
            labels = ['excerpt']
            if window['world'] not in ('real_world', 'unknown'):
                labels.append(window['world'].replace('_', ' '))
            if window['source_act'] not in ('direct_statement', 'unknown', 'not_applicable'):
                labels.append(window['source_act'].replace('_', ' ') + ' excerpt')
            qualifiers[event] = ', '.join(labels)
    except Exception:
        return
