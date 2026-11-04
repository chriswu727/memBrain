import math
import re

from jsonschema._utils import uniq


def prepare(nodes, formatter):
    built = {}
    supported = {'type', 'properties', 'required', 'additionalProperties', 'items', 'minItems', 'maxItems',
                 'uniqueItems', 'enum', 'const', 'minimum', 'maximum', 'minLength', 'maxLength', 'pattern',
                 'format', 'allOf', 'anyOf', 'oneOf', 'not', 'if', 'then', 'else', 'description'}
    native = {str, int, float, bool, type(None), dict, list}
    types = {'string': {str}, 'object': {dict}, 'array': {list}, 'null': {type(None)},
             'boolean': {bool}, 'integer': {int}, 'number': {int, float}}

    def conjunction(values):
        uncertain = False
        for value in values:
            if value is False:
                return False
            uncertain |= value is None
        return None if uncertain else True

    def scalar_equal(first, second):
        if type(first) is bool or type(second) is bool:
            return type(first) is type(second) and first == second
        return first == second

    def build(node):
        if node is True or node is False:
            return lambda value, depth: node
        key = id(node)
        if key in built:
            return lambda value, depth: built[key](value, depth)
        built[key] = lambda value, depth: None
        if type(node) is not dict or node.keys() - supported:
            return built[key]
        predicates = []
        declared = node.get('type')
        if declared is not None:
            names = [declared] if type(declared) is str else declared
            if type(names) is not list or any(name not in types for name in names):
                return built[key]
            accepted = set().union(*(types[name] for name in names))
            integral = 'integer' in names
            predicates.append(lambda value, depth: type(value) in accepted or
                              (integral and type(value) is float and value.is_integer()))
        if 'const' in node:
            constant = node['const']
            if type(constant) not in native - {dict, list}:
                return built[key]
            predicates.append(lambda value, depth: type(value) not in (dict, list)
                              and scalar_equal(value, constant))
        if 'enum' in node:
            choices = node['enum']
            if any(type(value) not in native - {dict, list} for value in choices):
                return built[key]
            predicates.append(lambda value, depth: type(value) not in (dict, list)
                              and any(scalar_equal(value, choice) for choice in choices))
        properties = node.get('properties', {})
        if 'properties' in node:
            children = {name: build(child) for name, child in properties.items()}
            predicates.append(lambda value, depth, children=children: conjunction(child(value[name], depth + 1)
                              for name, child in children.items() if name in value) if type(value) is dict else True)
        if 'required' in node:
            required = frozenset(node['required'])
            predicates.append(lambda value, depth: required <= value.keys() if type(value) is dict else True)
        if 'additionalProperties' in node:
            extra = build(node['additionalProperties'])
            names = properties.keys()
            predicates.append(lambda value, depth: conjunction(extra(value[name], depth + 1)
                              for name in value.keys() - names) if type(value) is dict else True)
        if 'items' in node:
            item = build(node['items'])
            predicates.append(lambda value, depth: conjunction(item(part, depth + 1) for part in value)
                              if type(value) is list else True)
        for minimum, maximum, kind in [('minLength', 'maxLength', str), ('minItems', 'maxItems', list)]:
            lower, upper = node.get(minimum), node.get(maximum)
            if lower is not None or upper is not None:
                predicates.append(lambda value, depth, kind=kind, lower=lower, upper=upper:
                                  ((lower is None or len(value) >= lower) and (upper is None or len(value) <= upper))
                                  if type(value) is kind else True)
        if node.get('uniqueItems'):
            predicates.append(lambda value, depth: uniq(value) if type(value) is list else True)
        lower, upper = node.get('minimum'), node.get('maximum')
        if lower is not None or upper is not None:
            predicates.append(lambda value, depth: ((lower is None or value >= lower) and
                              (upper is None or value <= upper)) if type(value) in (int, float) else True)
        if 'pattern' in node:
            pattern = re.compile(node['pattern'])
            predicates.append(lambda value, depth: pattern.search(value) is not None if type(value) is str else True)
        if 'format' in node and formatter is not None:
            name = node['format']
            expected = formatter.checkers.get(name)
            predicates.append(lambda value, depth: formatter.conforms(value, name)
                              if formatter.checkers.get(name) is expected else None)
        for keyword in ('allOf', 'anyOf', 'oneOf'):
            if keyword not in node:
                continue
            children = tuple(build(child) for child in node[keyword])
            def combine(value, depth, keyword=keyword, children=children):
                states = [child(value, depth + 1) for child in children]
                if keyword == 'allOf':
                    return conjunction(states)
                if keyword == 'anyOf':
                    return True if True in states else (None if None in states else False)
                count = sum(state is True for state in states)
                return False if count > 1 else (None if None in states else count == 1)
            predicates.append(combine)
        if 'not' in node:
            excluded = build(node['not'])
            def negate(value, depth):
                state = excluded(value, depth + 1)
                return None if state is None else not state
            predicates.append(negate)
        if 'if' in node:
            condition = build(node['if'])
            then, otherwise = build(node.get('then', True)), build(node.get('else', True))
            def conditional(value, depth):
                state = condition(value, depth + 1)
                if state is not None:
                    return (then if state else otherwise)(value, depth + 1)
                first, second = then(value, depth + 1), otherwise(value, depth + 1)
                return first if first is second else None
            predicates.append(conditional)

        def check(value, depth):
            kind = type(value)
            if depth >= 64 or kind not in native or (kind is float and not math.isfinite(value)):
                return None
            if kind is dict and any(type(name) is not str for name in value):
                return None
            return conjunction(predicate(value, depth) for predicate in predicates)
        built[key] = check
        return check

    for node in nodes:
        build(node)

    def accepts(node, value):
        check = built.get(id(node))
        return check is not None and check(value, 0) is True
    return accepts
