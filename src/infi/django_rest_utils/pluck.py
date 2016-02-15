from itertools import chain

def collect_items_from_string_lists(lists, delimiter=','):
    '''
    A fancy way to flatten a list of comma seperated lists into one list of strings
    '''
    return set(chain(*(s.split(',') for s in lists)))


DELIMITER = '.'

def fragments(path):
    return [x for x in path.split(DELIMITER) if x != '']

def traverse(path, d, prefix=''):
    '''
    Returns a list of <path, value> pairs of paths matching 'path' within data object d.
    The first member of the tuple is the path within the data object under which the matching value was found (prefixed
    by the value given in 'prefix' member).
    '''
    # Convert input members to lists of path fragments.
    if isinstance(path, basestring):
        return traverse(fragments(path), d, prefix)
    if isinstance(prefix, basestring):
        return traverse(path, d, fragments(prefix))
    absolute_path = (DELIMITER.join(prefix + path))
    '''
    Use while as an inner scope and break when reaching branch that yields no result
    '''
    while True:
        if d is None:
            break
        if not path or not path[0]:
            return [(absolute_path, d)]
        if len(path) == 0:
            return hb
        if path[0] == '*':
            if isinstance(d, dict):
                return chain(*[traverse(path[1:], v, prefix + [str(idx)]) for (idx, v) in d.iteritems()])
            if isinstance(d, list):
                return chain(*[traverse(path[1:], v, prefix + [str(idx)]) for (idx, v) in enumerate(d)])
            else:
                break
        if isinstance(d, dict):
            return chain(*[traverse(path[1:], d.get(path[0]), prefix + [path[0]])])
        try:
            if isinstance(d, list):
                if int(path[0]) < len(d):
                    return chain(*[traverse(path[1:], d[int(path[0])], prefix + [path[0]])])
                else:
                    break
        except ValueError:
            # Trying to access array with non numeric key
            break
        break


    return [(DELIMITER.join(prefix + path), None)]



def pluck_result(result, field_list):
    if isinstance(result, list):
        return [pluck_result(x, field_list) for x in result]
    if not isinstance(result, dict) or len(field_list) == 0:
        return result
    key_value_pairs = chain(*(traverse(field, result) for field in collect_items_from_string_lists(field_list)))
    return {k: v for (k, v) in key_value_pairs}