from itertools import chain

def collect_items_from_string_lists(lists, delimiter=','):
    '''
    A fancy way to flatten a list of comma seperated lists into one list of strings
    '''
    return set(chain(*(s.split(',') for s in lists)))


def traverse(path, d, collected_path=[]):
    if isinstance(path, basestring):
        return traverse(path.split('/'), d, collected_path)
    if d is None:
        return []
    if not path or not path[0]:
        return [('/'.join(collected_path), d)]
    if len(path) == 0:
        return hb
    if path[0] == '*':
        if isinstance(d, dict):
            return chain(*[traverse(path[1:], v, collected_path + [k]) for (k, v) in d.iteritems()])
        if isinstance(d, list):
            return chain(*
                [traverse(path[1:], v, collected_path + [str(idx)]) for (idx, v) in enumerate(d)])
        else:
            return []
        raise Exception("Illegal path: value of type {} cannot be traversed via wildcard".format(type(d)))
    if isinstance(d, dict):
        return chain(*[traverse(path[1:], d.get(path[0]), collected_path + [path[0]])])
    try:
        if isinstance(d, list) and int(path[0]) < len(d):
            return chain(*[traverse(path[1:], d[int(path[0])], collected_path + [path[0]])])
    except ValueError:
        # Trying to access array with non numeric key
        return []
    return []



def pluck_result(result, field_list):
    if isinstance(result, list):
        return [pluck_result(x, field_list) for x in result]
    if not isinstance(result, dict) or len(field_list) == 0:
        return result
    key_value_pairs = chain(*(traverse(field, result) for field in collect_items_from_string_lists(field_list)))
    return {k: v for (k, v) in key_value_pairs}