import json


class DuplicateJsonKeyError(ValueError):
    pass


def _reject_duplicate_keys(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise DuplicateJsonKeyError(
                "Duplicate JSON key {!r}".format(key)
            )
        result[key] = value
    return result


def load_json_with_duplicate_check(config_file):
    return json.load(config_file, object_pairs_hook=_reject_duplicate_keys)
