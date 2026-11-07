def matched_excerpt(item):
    memory = item['memory']
    span = item.get('matched_statement_span')
    statement = memory['statement']
    if (memory.get('derivation', {}).get('method') != 'direct_capture' or not isinstance(span, dict)
            or type(span.get('start')) is not int or type(span.get('end')) is not int
            or span.get('unit') != 'unicode_code_point'
            or not 0 <= span['start'] < span['end'] <= len(statement)
            or span['end'] - span['start'] > 400 or len(statement) <= 400):
        return None
    return {'statement': statement[span['start']:span['end']], 'statement_span': dict(span),
            'statement_characters': len(statement), 'recall_detail': 'matched_excerpt_expandable',
            'excerpt_use': 'partial_original_statement_not_an_independent_fact'}
