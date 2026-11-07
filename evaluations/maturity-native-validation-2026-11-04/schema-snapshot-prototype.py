import json

from jsonschema import Draft202012Validator, FormatChecker

from membrain import contracts

KEYWORDS = {'$ref', 'type', 'properties', 'required', 'additionalProperties', 'items', 'minItems', 'maxItems',
            'minLength', 'maxLength', 'minimum', 'maximum', 'uniqueItems', 'enum', 'const',
            'allOf', 'anyOf', 'oneOf', 'not', 'if', 'then', 'else', 'format', 'pattern',
            'description', 'title'}
PATTERNS = {'^[0-9a-f]{64}$', '^[a-f0-9]{64}$', '^[A-Z]{3}$',
            '^[A-Za-z][A-Za-z0-9_.:-]{0,127}$', '^[a-zA-Z][a-zA-Z0-9_]{0,63}$'}
CHECKERS = FormatChecker().checkers.copy()
CHECK = FormatChecker.check
ROOT_KEYWORDS = tuple(contracts._prepared_root().VALIDATORS.items())


class Ineligible(Exception):
    pass


def snapshot(current):
    root = contracts._prepared_root()
    if (root is None or type(current) is not type(root)
            or current.TYPE_CHECKER is not Draft202012Validator.TYPE_CHECKER
            or tuple(current.VALIDATORS.items()) != ROOT_KEYWORDS
            or type(root.schema) is not dict or set(root.schema) != {'$schema', '$defs'}
            or root.schema['$schema'] != 'https://json-schema.org/draft/2020-12/schema'):
        return None
    definitions = root.schema['$defs']
    if current.schema is not definitions.get('ActionResponse'):
        return None
    checker = current.format_checker
    if (type(checker) is not FormatChecker or checker.checkers != CHECKERS
            or getattr(checker.check, '__func__', None) is not CHECK):
        return None
    ids = {id(value): name for name, value in definitions.items() if type(value) is dict}

    def node(value, *, top=False, depth=0):
        if depth > 64:
            raise Ineligible
        if type(value) is bool:
            return value
        if type(value) is not dict:
            raise Ineligible
        if not top and id(value) in ids:
            return {'$ref': '#/$defs/' + ids[id(value)].replace('~', '~0').replace('/', '~1')}
        if any(key not in KEYWORDS for key in value):
            raise Ineligible
        if '$ref' in value and (len(value) != 1 or contracts._local(value) not in definitions):
            raise Ineligible
        if 'pattern' in value and value['pattern'] not in PATTERNS:
            raise Ineligible
        if 'format' in value and value['format'] != 'date-time':
            raise Ineligible
        result = {}
        for key, child in value.items():
            if key in contracts._SCHEMA_MAPS:
                if type(child) is not dict:
                    raise Ineligible
                result[key] = {name: node(inner, depth=depth + 1) for name, inner in child.items()}
            elif key in contracts._SCHEMA_ONE:
                result[key] = node(child, depth=depth + 1)
            elif key in contracts._SCHEMA_LISTS:
                if type(child) is not list:
                    raise Ineligible
                result[key] = [node(inner, depth=depth + 1) for inner in child]
            else:
                result[key] = child
        return result

    try:
        document = {'$schema': root.schema['$schema'], '$defs': {
            name: node(value, top=True) for name, value in definitions.items()}, '$ref': '#/$defs/ActionResponse'}
        return json.dumps(document, ensure_ascii=True, allow_nan=False, separators=(',', ':'))
    except (Ineligible, TypeError, ValueError, RecursionError):
        return None
