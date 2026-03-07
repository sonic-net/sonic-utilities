import copy
import json
import jsonpatch
import sonic_yang
from collections import deque, OrderedDict
from enum import Enum
from .gu_common import OperationWrapper, OperationType, GenericConfigUpdaterError, \
                       JsonChange, PathAddressing, genericUpdaterLogging

class Diff:
    """
    A class that contains the diff info between current and target configs.
    """
    def __init__(self, current_config, target_config):
        self.current_config = current_config
        self.target_config = target_config

    def __hash__(self):
        cc = json.dumps(self.current_config, sort_keys=True)
        tc = json.dumps(self.target_config, sort_keys=True)
        return hash((cc,tc))

    def __eq__(self, other):
        """Overrides the default implementation"""
        if isinstance(other, Diff):
            return self.current_config == other.current_config and self.target_config == other.target_config

        return False

    # TODO: Can be optimized to apply the move in place. JsonPatch supports that using the option 'in_place=True'
    # Check: https://python-json-patch.readthedocs.io/en/latest/tutorial.html#applying-a-patch
    # NOTE: in case move is applied in place, we will need to support `undo_move` as well.
    def apply_move(self, move, in_place: bool = False):
        new_current_config = move.apply(self.current_config, in_place)
        return Diff(new_current_config, self.target_config)

    def undo_move(self, move, in_place: bool = False):
        new_current_config = move.undo(self.current_config, in_place)
        return Diff(new_current_config, self.target_config)

    def has_no_diff(self):
        return self.current_config == self.target_config

    def __str__(self):
        return f"""current_config: {self.current_config}
target_config: {self.target_config}"""

    def __repr__(self):
        return str(self)


class JsonMove:
    """
    A class similar to JsonPatch operation, but it allows the path to refer to non-existing middle elements.

    JsonPatch operation fails to update json if the path in the patch refers to element that do not exist.
    For example, assume json to be:
    {}
    The following path will be rejected:
    /elem1/key1
    The reason is 'elem1' does not exist in the json

    JsonMove on the other hand allows that given the target_config_tokens i.e. the target_config path,
    and current_config_tokens i.e. current_config path where the update needs to happen.
    """
    def __init__(self, diff, op_type, current_config_tokens, target_config_tokens=None):
        # Support for undo
        self.orig_value = None

        operation = self._to_jsonpatch_operation(diff, op_type, current_config_tokens, target_config_tokens)
        self.patch = jsonpatch.JsonPatch([operation])
        self.op_type = operation[OperationWrapper.OP_KEYWORD]
        self.path = operation[OperationWrapper.PATH_KEYWORD]
        self.value = operation.get(OperationWrapper.VALUE_KEYWORD, None)

        self.op_type = op_type
        self.current_config_tokens = current_config_tokens
        self.target_config_tokens = target_config_tokens

    def _to_jsonpatch_operation(self, diff, op_type, current_config_tokens, target_config_tokens):
        operation_wrapper = OperationWrapper()
        path_addressing = PathAddressing()

        if op_type == OperationType.REMOVE:
            path = path_addressing.create_path(current_config_tokens)
            return operation_wrapper.create(op_type, path)

        if op_type == OperationType.REPLACE:
            path = path_addressing.create_path(current_config_tokens)
            value = JsonMove._get_value(diff.target_config, target_config_tokens)
            return operation_wrapper.create(op_type, path, value)

        if op_type == OperationType.ADD:
            return JsonMove._to_jsonpatch_add_operation(diff, current_config_tokens, target_config_tokens)

        raise ValueError(f"OperationType {op_type} is not supported")

    @staticmethod
    def _get_value(config, tokens):
        for token in tokens:
            if isinstance(config, list):
                token = int(token)
            config = config[token]
        return copy.deepcopy(config)

    @staticmethod
    def _to_jsonpatch_add_operation(diff, current_config_tokens, target_config_tokens):
        """
        Check description of JsonMove class first.

        ADD operation path can refer to elements that do not exist, so to convert JsonMove to JsonPatch operation
        We need to remove the non-existing tokens from the current_config path and move them to the value.

        Example:
          Assume Target Config:
            {
                "dict1":{
                    "key11": "value11"
                }
            }
          Assume Current Config:
            {
            }
          Assume JsonMove:
            op_type=add, current_config_tokens=[dict1, key11], target_config_tokens=[dict1, key11]

          Converting this to operation directly would result in:
            {"op":"add", "path":"/dict1/key11", "value":"value11"}
          BUT this is not correct since 'dict1' which does not exist in Current Config.
          Instead we convert to:
            {"op":"add", "path":"/dict1", "value":{"key11": "value11"}}
        """
        operation_wrapper = OperationWrapper()
        path_addressing = PathAddressing()

        # if path refers to whole config i.e. no tokens, then just create the operation
        if not current_config_tokens:
            path = path_addressing.create_path(current_config_tokens)
            value = JsonMove._get_value(diff.target_config, target_config_tokens)
            return operation_wrapper.create(OperationType.ADD, path, value)

        # Start with getting target-config that match the path all the way to the value in json format
        # Example:
        #   Assume target-config:
        #     {
        #         "dict1":{
        #             "key11": "value11",
        #             "list12": [
        #                         "value121",
        #                         "value122"
        #                       ]
        #         },
        #         "dict2":{
        #             "key21": "value21"
        #         }
        #     }
        #   Assume target config tokens:
        #     dict1, list12, 1
        #   filtered_config will be
        #     {
        #         "dict1":{
        #             "list12": [
        #                         "value122"
        #                       ]
        #         }
        #     }
        target_ptr = diff.target_config
        filtered_config = {}
        filtered_config_ptr = filtered_config
        for token_index in range(len(target_config_tokens)):
            token = target_config_tokens[token_index]

            # Tokens are expected to be of the correct data-type i.e. string, int (list-index)
            # So not checking the type of the token before consuming it
            target_ptr = target_ptr[token]

            # if it is the last item, then just return the last target_ptr
            if token_index == len(target_config_tokens)-1:
                filtered_value = target_ptr
            elif isinstance(target_ptr, list):
                filtered_value = []
            else:
                filtered_value = {}

            if isinstance(filtered_config_ptr, list):
                filtered_config_ptr.append(filtered_value) # filtered_config list will contain only 1 value
            else: # otherwise it is a dict
                filtered_config_ptr[token] = filtered_value

            filtered_config_ptr = filtered_value

        # Then from the filtered_config get the all the tokens that exist in current_config
        # This will be the new path, and the new value will be the corresponding filtered_config
        # Example:
        #   Assume filtered_config
        #     {
        #         "dict1":{
        #             "key11": "value11"
        #         }
        #     }
        #   Assume current-config
        #     {
        #         "dict1":{
        #             "list12": [
        #                         "value122"
        #                       ]
        #         }
        #     }
        #   Then the JsonPatch path would be:
        #     /dict1/list12
        #   And JsonPatch value would be:
        #     [ "value122" ]
        current_ptr = diff.current_config
        new_tokens = []
        for token in current_config_tokens:
            new_tokens.append(token)
            was_list = isinstance(filtered_config, list)
            if was_list:
                # filtered_config list can only have 1 item
                filtered_config = filtered_config[0]
            else:
                filtered_config = filtered_config[token]

            if was_list and token >= len(current_ptr):
                break
            if not(was_list) and token not in current_ptr:
                break
            current_ptr = current_ptr[token]

        op_type = OperationType.ADD
        new_path = path_addressing.create_path(new_tokens)
        new_value = copy.deepcopy(filtered_config)

        return operation_wrapper.create(op_type, new_path, new_value)

    @staticmethod
    def from_patch(patch):
        ops = list(patch)
        if len(ops) != 1:
            raise GenericConfigUpdaterError(
                f"Only a patch of a single operation be converted to JsonMove. Patch has {len(ops)} operation/s")

        return JsonMove.from_operation(ops[0])

    @staticmethod
    def from_operation(operation):
        path_addressing = PathAddressing()
        op_type = OperationType[operation[OperationWrapper.OP_KEYWORD].upper()]
        path = operation[OperationWrapper.PATH_KEYWORD]
        if op_type in [OperationType.ADD, OperationType.REPLACE]:
            value = operation[OperationWrapper.VALUE_KEYWORD]
        else:
            value = None

        tokens = path_addressing.get_path_tokens(path)

        target_config = {}
        target_config_ptr = target_config
        current_config = {}
        current_config_ptr = current_config
        for token in tokens[:-1]:
            target_config_ptr[token] = {}
            current_config_ptr[token] = {}
            target_config_ptr = target_config_ptr[token]
            current_config_ptr = current_config_ptr[token]

        if tokens:
            target_config_ptr[tokens[-1]] = value
        else:
            # whole-config, just use value
            target_config = value

        current_config_tokens = tokens
        if op_type in [OperationType.ADD, OperationType.REPLACE]:
            target_config_tokens = tokens
        else:
            target_config_tokens = None

        diff = Diff(current_config, target_config)

        return JsonMove(diff, op_type, current_config_tokens, target_config_tokens)

    def apply(self, config, in_place: bool = False):
        if self.op_type == OperationType.REMOVE or self.op_type == OperationType.REPLACE:
            self.orig_value = JsonMove._get_value(config, sonic_yang.SonicYang.configdb_path_split(self.path))

        return self.patch.apply(config, in_place=in_place)

    def undo(self, config, in_place: bool = False):
        # Create new patch to undo previous application
        if self.patch.patch[0]['op'] == 'add':
            patch = jsonpatch.JsonPatch([{'op': 'remove', 'path': self.patch.patch[0]['path']}])
        elif self.patch.patch[0]['op'] == 'replace':
            patch = jsonpatch.JsonPatch([{
                                        'op': 'replace',
                                        'path': self.patch.patch[0]['path'],
                                        'value': self.orig_value
                                        }])
        elif self.patch.patch[0]['op'] == 'remove':
            patch = jsonpatch.JsonPatch([{'op': 'add', 'path': self.patch.patch[0]['path'], 'value': self.orig_value}])

        return patch.apply(config, in_place=in_place)

    def __str__(self):
        return str(self.patch)

    def __repr__(self):
        return str(self.patch)

    def __eq__(self, other):
        """Overrides the default implementation"""
        if isinstance(other, JsonMove):
            return self.patch == other.patch
        return False

    def __hash__(self):
        return hash((self.op_type, self.path, json.dumps(self.value)))


class JsonMoveGroup:
    """
    Group of JsonMove objects to be applied together
    """
    def __init__(self, move: JsonMove = None):
        self.patches = []
        if move is not None:
            self.append(move)

    def append(self, move: JsonMove):
        self.patches.append(move)

    def apply(self, config, in_place: bool = False):
        update = config
        for i, patch in enumerate(self.patches):
            if i != 0:
                in_place = True
            update = patch.apply(update, in_place=in_place)
            if update is None:
                return None
        return update

    def undo(self, config, in_place: bool = False):
        update = config
        for i, patch in enumerate(reversed(self.patches)):
            if i != 0:
                in_place = True
            update = patch.undo(update, in_place=in_place)
            if update is None:
                return None
        return update

    def get_jsonpatch(self):
        raw_patches = []
        for move in self.patches:
            raw_patches.extend(move.patch.patch)
        return jsonpatch.JsonPatch(raw_patches)

    def parentTableName(self):
        """
        This extracts the parent table name from the first patch associated
        with this grouping.  This is a bit special-cased for grouping purposes
        where it evaluates both '/' and '|' to look for parents to group.

        Examples:
         * /PORT/Ethernet0/description -> /PORT
         * /PORTCHANNEL_MEMBER/PortChannel0001|Ethernet16 -> /PORTCHANNEL_MEMBER/PortChannel0001
         * /ACL_RULE/V4-ACL-TABLE|Rule_20/DST_IP -> /ACL_RULE/V4-ACL-TABLE
        """
        tokens = sonic_yang.SonicYang.configdb_path_split(self.patches[0].path)

        # See if the last token has a |, if so just truncate and return
        token = tokens[-1]
        if "|" in token:
            tokens[-1] = token.rsplit("|", 1)[0]
            return sonic_yang.SonicYang.configdb_path_join(tokens)

        # Pop off the last element as we don't need it, its not a key
        tokens.pop()

        # See if the last token has a |, if so just truncate and return
        token = tokens[-1]
        if "|" in token:
            tokens[-1] = token.rsplit("|", 1)[0]
            return sonic_yang.SonicYang.configdb_path_join(tokens)

        # If we're here it means we're on a key to be removed, pop and return
        tokens.pop()
        return sonic_yang.SonicYang.configdb_path_join(tokens)

    def merge(self, group):
        self.patches.extend(group.patches)

    def __str__(self):
        return ",".join([str(patch) for patch in self.patches])

    def __repr__(self):
        return str(self)

    def __eq__(self, other):
        if isinstance(other, JsonMoveGroup):
            if len(other) != len(self.patches):
                return False
            for i, patch in enumerate(self.patches):
                if patch.patch != other.patches[i].patch:
                    return False
            return True
        return False

    def __hash__(self):
        return hash(str(self))

    def __len__(self):
        return len(self.patches)

    def __iter__(self):
        for patch in self.patches:
            yield patch


class MoveWrapper:
    def __init__(self, move_generators, move_non_extendable_generators, move_extenders, move_validators):
        self.move_generators = move_generators
        self.move_non_extendable_generators = move_non_extendable_generators
        self.move_extenders = move_extenders
        self.move_validators = move_validators

    def generate(self, diff):
        """
        Generates all possible moves to help transform diff.current_config to diff.target_config.

        It starts by generating the non-extendable moves i.e. moves that will not extended to e.g. change its parent.
        The non-extendable moves are mostly high level moves such as deleting/adding whole tables.

        After that it generates extendable moves i.e. moves that can be extended to e.g. change its parent.
        The extendable moves are typically very low level moves that can achieve the minimum disruption guarantee.

        Lastly the moves are extended for example to try to replace the parent config instead, or by deleting
        the dependencies of the config.
        """
        processed_moves = set()
        extended_moves = set()
        moves = deque([])
        for move in self._generate_non_extendable_moves(diff):
            if not(move in processed_moves):
                processed_moves.add(move)
                yield move

        for move in self._generate_moves(diff):
            if not(move in processed_moves):
                processed_moves.add(move)
                yield move

            if not(move in extended_moves):
                extended_moves.add(move)
                moves.extend(self._extend_moves(move, diff))

        while moves:
            move = moves.popleft()
            if not(move in processed_moves):
                processed_moves.add(move)
                yield move

            if not(move in extended_moves):
                extended_moves.add(move)
                moves.extend(self._extend_moves(move, diff))

    def validate(self, move, diff):
        # Generate simulated config once, not once per validator as this performs
        # a deep copy
        simulated_config = move.apply(diff.current_config)
        for validator in self.move_validators:
            if not validator.validate(move, diff, simulated_config):
                return False
        return True

    def simulate(self, move, diff, in_place: bool = False):
        return diff.apply_move(move, in_place)

    def undo_simulate(self, move, diff, in_place: bool = False):
        return diff.undo_move(move, in_place)

    def _generate_moves(self, diff):
        for generator in self.move_generators:
            for move in generator.generate(diff):
                yield move

    def _generate_non_extendable_moves(self, diff):
        for generator in self.move_non_extendable_generators:
            for move in generator.generate(diff):
                yield move

    def _extend_moves(self, moveGroup: JsonMoveGroup, diff) -> JsonMoveGroup:
        # The enxtender only operates on JsonMove, so iterate across the individual
        # moves within the group to generate the new moves.  In theory there
        # should be at most one move per group if we're running extenders.
        for move in moveGroup:
            for extender in self.move_extenders:
                for newmove in extender.extend(move, diff):
                    yield JsonMoveGroup(newmove)

class JsonPointerFilter:
    """
    A filtering class to get the paths matching the filter from the given config.
    The patterns:
    - Each pattern consist of multiple tokens
    - Tokens are matched with the config from the root level
    - Each token can be:
      - '*' Will match all keys at the current level
      - '@' Will be replaced by 'common_key' passed in 'get_paths'
      - <other> Will match other strings that are not * nor @
    - Token advanced options
      - '*|@' Will match keys that end with '|common_key'
      - '@|*' Will match keys that start with 'common_key|'
      - '*|<other>' Will match keys that end with '|<other>'
      - '<other>|*' Will match keys that start with '<other>|'
    """
    def __init__(self, patterns, path_addressing):
        self.patterns = patterns
        self.path_addressing = path_addressing

    def get_paths(self, config, common_key=None):
        for pattern in self.patterns:
            for path in self._get_paths_recursive(config, pattern, [], 0, common_key):
                yield path

    def _get_paths_recursive(self, config, pattern_tokens, matching_tokens, idx, common_key):
        if idx == len(pattern_tokens):
            yield self.path_addressing.create_path(matching_tokens)
            return

        token = pattern_tokens[idx]
        if common_key:
            token = token.replace("@", common_key)

        matching_keys = []
        if token == "*":
            matching_keys = config.keys()
        elif token.startswith("*|"):
            suffix = token[1:]
            matching_keys = [key for key in config.keys() if key.endswith(suffix)]
        elif token.endswith("|*"):
            prefix = token[:-1]
            matching_keys = [key for key in config.keys() if key.startswith(prefix)]
        elif token in config:
            matching_keys = [token]

        for key in matching_keys:
            matching_tokens.append(key)
            for path in self._get_paths_recursive(config[key], pattern_tokens, matching_tokens, idx+1, common_key):
                yield path
            matching_tokens.pop()

    def is_match(self, path):
        tokens = self.path_addressing.get_path_tokens(path)
        for pattern in self.patterns:
            if len(pattern) != len(tokens):
                return False

            for idx in range(len(pattern)):
                pattern_token = pattern[idx]
                token = tokens[idx]

                if not self._is_token_match(pattern_token, token):
                    return False

        return True

    def _is_token_match(self, pattern_token, token):
        if "|" in pattern_token:
            pattern_token_parts = pattern_token.split("|", 1)
            token_parts = token.split("|", 1)
            if len(pattern_token_parts) != len(token_parts):
                return False

            return self._is_simple_token_match(pattern_token_parts[0], token_part[0]) and \
                   self._is_simple_token_match(pattern_token_parts[1], token_part[1])

        return self._is_simple_token_match(pattern_token, token)


    def _is_simple_token_match(self, pattern_token, token):
        if pattern_token == "*" or pattern_token == "@":
            return True

        return pattern_token == token

class RequiredValueIdentifier:
    """
    A class that identifies the config that requires other fields to be of specific value
    The "requiring" config is the config that requires other fields to be of specific value.
    The "required" config is the config that needs to be of specific value.
    E.g. Changes to "QUEUE" table requires the corresponding "PORT" to be admin down.
    """
    def __init__(self, path_addressing):
        # TODO: port-critical fields are hard-coded for now, it should be moved to YANG models
        # settings format, each setting consist of:
        #   [
        #       "required_pattern": the list of tokens, where there is a single token with value '@' which is the common key
        #                           with the requiring patterns
        #       "required_value": the required value
        #       "default_value": the default value of the required paths
        #       "requiring_patterns": the patterns matching paths that requires the given value, each pattern can have '@'
        #                             which will be replaced with the common key, '*' will match any symbol
        #   }
        self.settings = [
            {
                "required_pattern": ["PORT", "@", "admin_status"],
                "required_value": "down",
                "default_value": "down",
                "requiring_patterns": [
                        ["BUFFER_PG", "@|*"],
                        ["BUFFER_PORT_EGRESS_PROFILE_LIST", "@"],
                        ["BUFFER_PORT_INGRESS_PROFILE_LIST", "@"],
                        ["BUFFER_QUEUE", "@|*"],
                        ["PORT_QOS_MAP", "@"],
                        ["QUEUE", "@|*"],
                    ]
            },
        ]
        self.path_addressing = path_addressing
        for setting in self.settings:
            required_pattern = setting["required_pattern"]
            required_parent_pattern = required_pattern[:-1]
            # replace the '@' with '*' so it can be used as a JsonPointerFilter
            required_parent_pattern_with_asterisk = [token.replace("@", "*") for token in required_parent_pattern]
            setting["required_parent_filter"] = JsonPointerFilter([required_parent_pattern_with_asterisk], path_addressing)
            setting["required_field_name"] = required_pattern[-1]
            for index, token in enumerate(required_pattern):
                if token == "@":
                    setting["common_key_index"] = index
            setting["requiring_filter"] = JsonPointerFilter(setting["requiring_patterns"], path_addressing)

    """
    Simple function to determine if the path tokens match any of the required patterns.
    This is used to avoid grouping such changes in bulk operations.
    """
    def target_in_required_pattern(self, configdb_path_tokens):
        for setting in self.settings:
            if len(setting["required_pattern"]) != len(configdb_path_tokens):
                continue

            is_match = True

            for idx, token in enumerate(setting["required_pattern"]):
                if token not in ["*", "@", configdb_path_tokens[idx]]:
                    is_match = False
                    break

            if is_match:
                return True

        return False

    def get_required_value_data(self, configs):
        data = {}
        for setting in self.settings:
            required_parent_filter = setting["required_parent_filter"]
            required_field_name = setting["required_field_name"]
            common_key_index = setting["common_key_index"]
            required_value = setting["required_value"]
            requiring_filter = setting["requiring_filter"]
            for config in configs:
                for required_parent_path in required_parent_filter.get_paths(config):
                    parent_tokens = self.path_addressing.get_path_tokens(required_parent_path)
                    required_path = self.path_addressing.create_path(parent_tokens+[required_field_name])
                    common_key = parent_tokens[common_key_index]
                    requires_paths = requiring_filter.get_paths(config, common_key)
                    for requires_path in requires_paths:
                        if requires_path not in data:
                            data[requires_path] = set()
                        data[requires_path].add((required_path, required_value))

        sorted_paths = sorted(data.keys())
        sorted_data = OrderedDict()
        for path in sorted_paths:
            sorted_data[path] = sorted(data[path])

        return sorted_data

    def get_value_or_default(self, config, path):
        value = self.path_addressing.get_from_path(config, path)
        if value is not None:
            return value

        # Check if parent exist
        tokens = self.path_addressing.get_path_tokens(path)
        parent_tokens = tokens[:-1]
        field_name = tokens[-1]
        parent_path = self.path_addressing.create_path(parent_tokens)
        parent_value = self.path_addressing.get_from_path(config, parent_path)

        if parent_value is None:
            return None

        return self._get_default_value_from_settings(parent_path, field_name)

    def _get_default_value_from_settings(self, parent_path, field_name):
        for setting in self.settings:
            if setting["required_parent_filter"].is_match(parent_path) and field_name == setting["required_field_name"]:
                return setting["default_value"]

        return None

class CreateOnlyFilter:
    """
    A filtering class for create-only fields.
    """
    def __init__(self, path_addressing):
        # TODO: create-only fields are hard-coded for now, it should be moved to YANG model
        self.path_addressing = path_addressing
        self.patterns = [
            ["PORT", "*", "lanes"],
            ["LOOPBACK_INTERFACE", "*", "vrf_name"],
            ["BGP_NEIGHBOR", "*", "holdtime"],
            ["BGP_NEIGHBOR", "*", "keepalive"],
            ["BGP_NEIGHBOR", "*", "name"],
            ["BGP_NEIGHBOR", "*", "asn"],
            ["BGP_NEIGHBOR", "*", "local_addr"],
            ["BGP_NEIGHBOR", "*", "nhopself"],
            ["BGP_NEIGHBOR", "*", "rrclient"],
            ["BGP_PEER_RANGE", "*", "*"],
            ["BGP_SENTINELS", "*", "*"],
            ["BGP_MONITORS", "*", "holdtime"],
            ["BGP_MONITORS", "*", "keepalive"],
            ["BGP_MONITORS", "*", "name"],
            ["BGP_MONITORS", "*", "asn"],
            ["BGP_MONITORS", "*", "local_addr"],
            ["BGP_MONITORS", "*", "nhopself"],
            ["BGP_MONITORS", "*", "rrclient"],
            ["MIRROR_SESSION", "*", "*"],
        ]

    def get_filter(self):
        return JsonPointerFilter(self.patterns,
                                 self.path_addressing)

class RemoveCreateOnlyDependencyMoveValidator:
    """
    A class to validate all dependencies of create-only fields have been removed before
    modifying the create-only fields.
    """
    def __init__(self, path_addressing):
        self.path_addressing = path_addressing
        self.create_only_filter = CreateOnlyFilter(path_addressing).get_filter()

    def validate(self, group: JsonMoveGroup, diff, simulated_config):
        # Note: group is not used by this validator
        current_config = diff.current_config
        target_config = diff.target_config # Final config after applying whole patch
        reload_config = True

        processed_tables = set()
        for path in self.create_only_filter.get_paths(current_config):
            tokens = self.path_addressing.get_path_tokens(path)
            table_to_check = tokens[0]

            if table_to_check in processed_tables:
                continue
            else:
                processed_tables.add(table_to_check)

            if table_to_check not in current_config:
                continue

            current_members = current_config[table_to_check]
            if not current_members:
                continue

            if table_to_check not in target_config:
                continue

            target_members = target_config[table_to_check]
            if not target_members:
                continue

            for member_name in current_members:
                if member_name not in target_members:
                    continue

                if not self._validate_member(tokens, member_name,
                                             current_config, target_config, simulated_config,
                                             reload_config=reload_config):
                    return False

                # After first call, no need to reload again
                reload_config = False

        return True

    def _validate_member(self, tokens, member_name, current_config, target_config, simulated_config,
                         reload_config: bool = True):
        table_to_check, create_only_field = tokens[0], tokens[-1]

        current_field = self._get_create_only_field(
            current_config, table_to_check, member_name, create_only_field)
        target_field = self._get_create_only_field(
            target_config, table_to_check, member_name, create_only_field)

        if current_field == target_field:
            return True

        simulated_member = self.path_addressing.get_from_path(
            simulated_config, f"/{table_to_check}/{member_name}")

        if simulated_member is None:
            return True

        if table_to_check == "PORT":
            current_admin_status = self.path_addressing.get_from_path(
                current_config, f"/{table_to_check}/{member_name}/admin_status"
            )
            simulated_admin_status = self.path_addressing.get_from_path(
                simulated_config, f"/{table_to_check}/{member_name}/admin_status"
            )
            if current_admin_status != simulated_admin_status and current_admin_status != "up":
                return False

        member_path = f"/{table_to_check}/{member_name}"
        for ref_path in self.path_addressing.find_ref_paths(member_path, simulated_config, reload_config=reload_config):
            if not self.path_addressing.has_path(current_config, ref_path):
                return False

        return True

    def _get_create_only_field(self, config, table_to_check,
                               member_name, create_only_field):
        return config[table_to_check][member_name].get(create_only_field, None)

class DeleteWholeConfigMoveValidator:
    """
    A class to validate not deleting whole config as it is not supported by JsonPatch lib.
    """
    def validate(self, group: JsonMoveGroup, diff, simulated_config):
        if group.patches[0].op_type == OperationType.REMOVE and group.patches[0].path == "":
            return False
        return True

class FullConfigMoveValidator:
    """
    A class to validate that full config is valid according to YANG models after applying the move.
    """
    def __init__(self, config_wrapper):
        self.config_wrapper = config_wrapper

    def validate(self, move, diff, simulated_config):
        is_valid, error = self.config_wrapper.validate_config_db_config(simulated_config)
        return is_valid

class CreateOnlyMoveValidator:
    """
    A class to validate create-only fields are only created, but never modified/updated. In other words:
    - Field cannot be replaced.
    - Field cannot be added, only if the parent is added.
    - Field cannot be deleted, only if the parent is deleted.
    """
    def __init__(self, path_addressing):
        self.path_addressing = path_addressing

        # TODO: create-only fields are hard-coded for now, it should be moved to YANG models
        self.create_only_filter = CreateOnlyFilter(path_addressing).get_filter()

    def validate(self, group: JsonMoveGroup, diff, simulated_config):
        # NOTE: group not used by this validator

        # get create-only paths from current config, simulated config and also target config
        # simulated config is the result of the move
        # target config is the final config
        paths = set(list(self._get_create_only_paths(diff.current_config)) +
                    list(self._get_create_only_paths(simulated_config)) +
                    list(self._get_create_only_paths(diff.target_config)))

        for path in paths:
            tokens = self.path_addressing.get_path_tokens(path)
            if self._value_exist_but_different(tokens, diff.current_config, simulated_config):
                return False
            if self._value_added_but_parent_exist(tokens, diff.current_config, simulated_config):
                return False
            if self._value_removed_but_parent_remain(tokens, diff.current_config, simulated_config):
                return False

            # if parent of create-only field is added, create-only field should be the same as target
            # i.e. if field is deleted in target, it should be deleted in the move, or
            #      if field is present in target, it should be present in the move
            if self._parent_added_child_not_as_target(tokens, diff.current_config, simulated_config, diff.target_config):
                return False

        return True

    def _parent_added_child_not_as_target(self, tokens, current_config, simulated_config, target_config):
        # if parent is not added, return false
        if not self._exist_only_in_first(tokens[:-1], simulated_config, current_config):
            return False

        child_path = self.path_addressing.create_path(tokens)

        # if child is in target, check if child is not in simulated
        if self.path_addressing.has_path(target_config, child_path):
            return not self.path_addressing.has_path(simulated_config, child_path)
        else:
            # if child is not in target, check if child is in simulated
            return self.path_addressing.has_path(simulated_config, child_path)

    def _get_create_only_paths(self, config):
        for path in self.create_only_filter.get_paths(config):
            yield path

    def _value_exist_but_different(self, tokens, current_config_ptr, simulated_config_ptr):
        for token in tokens:
            mod_token = int(token) if isinstance(current_config_ptr, list) else token

            if mod_token not in current_config_ptr:
                return False

            if mod_token not in simulated_config_ptr:
                return False

            current_config_ptr = current_config_ptr[mod_token]
            simulated_config_ptr = simulated_config_ptr[mod_token]

        return current_config_ptr != simulated_config_ptr

    def _value_added_but_parent_exist(self, tokens, current_config_ptr, simulated_config_ptr):
        # if value is not added, return false
        if not self._exist_only_in_first(tokens, simulated_config_ptr, current_config_ptr):
            return False

        # if parent is added, return false
        if self._exist_only_in_first(tokens[:-1], simulated_config_ptr, current_config_ptr):
            return False

        # otherwise parent exist and value is added
        return True

    def _value_removed_but_parent_remain(self, tokens, current_config_ptr, simulated_config_ptr):
        # if value is not removed, return false
        if not self._exist_only_in_first(tokens, current_config_ptr, simulated_config_ptr):
            return False

        # if parent is removed, return false
        if self._exist_only_in_first(tokens[:-1], current_config_ptr, simulated_config_ptr):
            return False

        # otherwise parent remained and value is removed
        return True

    def _exist_only_in_first(self, tokens, first_config_ptr, second_config_ptr):
        path = self.path_addressing.create_path(tokens)
        return self.path_addressing.has_path(first_config_ptr, path) and \
               not self.path_addressing.has_path(second_config_ptr, path)

class NoDependencyMoveValidator:
    """
    A class to validate that the modified configs do not have dependency on each other. This should prevent
    moves that update whole config in a single step where multiple changed nodes are dependent on each. This
    way dependent configs are never updated together.
    """
    def __init__(self, path_addressing, config_wrapper):
        self.path_addressing = path_addressing
        self.config_wrapper = config_wrapper

    def validate(self, group: JsonMoveGroup, diff, simulated_config):
        reload_config = True
        # Note: all moves in a group are guaranteed to be the same operation type
        for move in group:
            if not self.__validate_move(move, diff, simulated_config, reload_config=reload_config):
                return False
            reload_config = False
        return True

    def __validate_move(self, move, diff, simulated_config, reload_config: bool = True):
        operation_type = move.op_type
        path = move.path

        if operation_type == OperationType.ADD:
            # For add operation, we check the simulated config has no dependencies between nodes under the added path
            if not self._validate_paths_config([path], simulated_config, reload_config):
                return False
        elif operation_type == OperationType.REMOVE:
            # For remove operation, we check the current config has no dependencies between nodes under the removed path
            if not self._validate_paths_config([path], diff.current_config, reload_config):
                return False
        elif operation_type == OperationType.REPLACE:
            if not self._validate_replace(move, diff, simulated_config):
                return False

        return True

    # NOTE: this function can be used for validating JsonChange as well which might have more than one move.
    def _validate_replace(self, move, diff, simulated_config):
        """
        The table below shows how mixed deletion/addition within replace affect this validation.

        The table is answring the question whether the change is valid:
          Y = Yes
          N = No
          n/a = not applicable as the change itself is not valid

        symbols meaning;
          +A, -A: adding, removing config A
          +refA, -refA: adding, removing a reference to A config


           +refA|-refA|refA
        --|-----|-----|----
        +A| N   | n/a | n/a
        -A| n/a | N   | n/a
         A| Y   | Y   | Y

        The conclusion is that:
        +A, +refA is invalid because there is a dependency and a single move should not have dependency
        -A, -refA is invalid because there is a dependency and a single move should not have dependency
        A kept unchanged can be ignored, as it is always OK regardless of what happens to its reference
        Other states are all non applicable since they are invalid to begin with

        So verification would be:
        if A is deleted and refA is deleted: return False
        if A is added and refA is added: return False
        return True
        """
        deleted_paths, added_paths = self._get_paths(diff.current_config, simulated_config, [])

        # Note: on replace operations we are loading both current and simulated configs so we have to
        #       load twice :(

        # For deleted paths, we check the current config has no dependencies between nodes under the removed path
        if not self._validate_paths_config(deleted_paths, diff.current_config, reload_config=True):
            return False

        # For added paths, we check the simulated config has no dependencies between nodes under the added path
        if not self._validate_paths_config(added_paths, simulated_config, reload_config=True):
            return False

        return True

    def _get_paths(self, current_ptr, target_ptr, tokens):
        deleted_paths = []
        added_paths = []

        if isinstance(current_ptr, list) or isinstance(target_ptr, list):
            tmp_deleted_paths, tmp_added_paths = self._get_list_paths(current_ptr, target_ptr, tokens)
            deleted_paths.extend(tmp_deleted_paths)
            added_paths.extend(tmp_added_paths)
            return deleted_paths, added_paths

        if isinstance(current_ptr, dict):
            for token in current_ptr:
                tokens.append(token)
                if token not in target_ptr:
                    deleted_paths.append(self.path_addressing.create_path(tokens))
                else:
                    tmp_deleted_paths, tmp_added_paths = self._get_paths(current_ptr[token], target_ptr[token], tokens)
                    deleted_paths.extend(tmp_deleted_paths)
                    added_paths.extend(tmp_added_paths)
                tokens.pop()

            for token in target_ptr:
                tokens.append(token)
                if token not in current_ptr:
                    added_paths.append(self.path_addressing.create_path(tokens))
                tokens.pop()

            return deleted_paths, added_paths

        # current/target configs are not dict nor list, so handle them as string, int, bool, float
        if current_ptr != target_ptr:
            # tokens.append(token)
            deleted_paths.append(self.path_addressing.create_path(tokens))
            added_paths.append(self.path_addressing.create_path(tokens))
            # tokens.pop()

        return deleted_paths, added_paths

    def _get_list_paths(self, current_list, target_list, tokens):
        """
        Gets all paths within the given list, assume list items are unique
        """
        deleted_paths = []
        added_paths = []

        hashed_target = set(target_list)
        for index, value in enumerate(current_list):
            if value not in hashed_target:
                tokens.append(index)
                deleted_paths.append(self.path_addressing.create_path(tokens))
                tokens.pop()

        hashed_current = set(current_list)
        for index, value in enumerate(target_list):
            if value not in hashed_current:
                tokens.append(index)
                # added_paths refer to paths in the target config and not necessarily the current config
                added_paths.append(self.path_addressing.create_path(tokens))
                tokens.pop()

        return deleted_paths, added_paths

    def _validate_paths_config(self, paths, config, reload_config: bool = True):
        """
        validates all config under paths do not have config and its references
        """
        refs = self.path_addressing.find_ref_paths(paths, config, reload_config=reload_config)
        for ref in refs:
            for path in paths:
                if ref.startswith(path):
                    return False

        return True

class NoEmptyTableMoveValidator:
    """
    A class to validate that a move will not result in an empty table, because empty table do not show up in ConfigDB.
    """
    def __init__(self, path_addressing):
        self.path_addressing = path_addressing

    def validate(self, group, diff, simulated_config):
        for move in group:
            if not self.__validate_move(move, diff, simulated_config):
                return False
        return True

    def __validate_move(self, move, diff, simulated_config):
        op_path = move.path

        if op_path == "": # If updating whole file
            tables_to_check = simulated_config.keys()
        else:
            tokens = self.path_addressing.get_path_tokens(op_path)
            tables_to_check = [tokens[0]]

        return self._validate_tables(tables_to_check, simulated_config)

    def _validate_tables(self, tables, config):
        for table in tables:
            if not(self._validate_table(table, config)):
                return False
        return True

    def _validate_table(self, table, config):
        # the only invalid case is if table exists and is empty
        return table not in config or config[table]

class RequiredValueMoveValidator:
    """
    Check RequiredValueIdentifier class description first.

    The validator checks the following:
    - A move that is changing a requiring config, while the required path is not equal to the required value is rejected
      E.g. A move that is changing "QUEUE" table while the corresponding "PORT" is not admin down is rejected
    - A move that is changing the required path value to something other than the required value, while there are
      requiring changes left is rejected
      E.g. A move is changing "PORT" to admin up from down, while "QUEUE" table still have changes left is rejected.
    """
    def __init__(self, path_addressing):
        self.path_addressing = path_addressing
        self.identifier = RequiredValueIdentifier(path_addressing)

    def validate(self, group: JsonMoveGroup, diff, simulated_config):
        # ignore full config removal because it is not possible by JsonPatch lib
        if group.patches[0].op_type == OperationType.REMOVE and group.patches[0].path == "":
            return

        current_config = diff.current_config
        target_config = diff.target_config # Final config after applying whole patch

        # data dictionary:
        # {
        #   <path>: [(required_path, required_value), ...],
        #   ...
        # }
        data = self.identifier.get_required_value_data([current_config, simulated_config, target_config])

        # If move is changing a requiring path while the required path does not have the required value, reject the move
        # E.g. if the move is changing port-critical configs while the port is up, reject the move
        for path in data:
            if self.path_addressing.is_config_different(path, current_config, simulated_config):
                for required_path, required_value in data[path]:
                    actual_value = self.identifier.get_value_or_default(current_config, required_path)
                    if actual_value is None: # current config does not have this value at all
                        continue
                    if actual_value != required_value:
                        return False

        # If some changes to the requiring paths are still to take place and the move has changes
        # to the required path, reject the move
        # E.g. if there are still port-critical changes left and the move has changes to the port
        #      admin status, reject the move
        # This makes sure we don't change the required path unnecessarily.
        for path in data:
            if self.path_addressing.is_config_different(path, current_config, target_config):
                for required_path, required_value in data[path]:
                    current_value = self.identifier.get_value_or_default(current_config, required_path)
                    simulated_value = self.identifier.get_value_or_default(simulated_config, required_path)
                    if simulated_value is None: # Simulated config does not have this value at all.
                        continue
                    if current_value != simulated_value and simulated_value != required_value:
                        return False

        return True

class TableLevelMoveGenerator:
    """
    A class that key level moves. The item name at the root level of ConfigDB is called 'Table'.

    e.g.
    {
        "Table": ...
    }

    This class will generate moves to remove tables if they are in current, but not target. It also add tables
    if they are in target but not current configs.
    """
    def __init__(self, path_addressing):
        self.path_addressing = path_addressing

    def generate(self, diff):
        # Removing tables in current but not target
        for tokens in self._get_non_existing_tables_tokens(diff.current_config, diff.target_config, False):
            yield JsonMoveGroup(JsonMove(diff, OperationType.REMOVE, tokens))

        # Adding tables in target but not current
        for tokens in self._get_non_existing_tables_tokens(diff.target_config, diff.current_config, True):
            yield JsonMoveGroup(JsonMove(diff, OperationType.ADD, tokens, tokens))

    def _get_non_existing_tables_tokens(self, config1, config2, reverse):
        for table in self.path_addressing.configdb_sorted_keys_by_backlinks("/", config1, reverse=reverse):
            if not(table in config2):
                yield [table]

class KeyLevelMoveGenerator:
    """
    A class that key level moves. The item name at the root level of ConfigDB is called 'Table', the item
    name in the Table level of ConfigDB is called key.

    e.g.
    {
        "Table": {
            "Key": ...
        }
    }

    This class will generate moves to remove keys if they are in current, but not target. It also add keys
    if they are in target but not current configs.
    """
    def __init__(self, path_addressing):
        self.path_addressing = path_addressing

    def generate(self, diff):
        # Removing keys in current but not target
        for tokens in self._get_non_existing_keys_tokens(diff.current_config, diff.target_config, reverse=False):
            table = tokens[0]
            # if table has a single key, delete the whole table because empty tables are not allowed in ConfigDB
            if len(diff.current_config[table]) == 1:
                yield JsonMoveGroup(JsonMove(diff, OperationType.REMOVE, [table]))
            else:
                yield JsonMoveGroup(JsonMove(diff, OperationType.REMOVE, tokens))

        # Adding keys in target but not current
        for tokens in self._get_non_existing_keys_tokens(diff.target_config, diff.current_config, reverse=True):
            yield JsonMoveGroup(JsonMove(diff, OperationType.ADD, tokens, tokens))

    def _get_non_existing_keys_tokens(self, config1, config2, reverse):
        for table in self.path_addressing.configdb_sorted_keys_by_backlinks("/", config1, reverse=reverse):
            for key in self.path_addressing.configdb_sorted_keys_by_backlinks("/" + table, config1, reverse=reverse):
                if not(table in config2) or not (key in config2[table]):
                    yield [table, key]


class BulkKeyLevelMoveGenerator:
    """
    Same concept as KeyLevelMoveGenerator, but groups additions and removals of sibling keys.
    """
    def __init__(self, path_addressing):
        self.path_addressing = path_addressing

    def generate(self, diff):
        prev_num_separators = -1
        group = None
        prev_table = ""

        # Removing keys in current but not target
        for tokens in self._get_non_existing_keys_tokens(diff.current_config, diff.target_config, reverse=False):
            table = tokens[0]
            key = tokens[1]

            # If the number of separators changed, do not group these operations with the previous ones.
            num_separators = key.count("|")
            if group is not None and (prev_num_separators != num_separators or table != prev_table):
                # Special case if we are deleting all the current keys in a table to emit a table delete too
                if len(list(group)) == len(diff.current_config[table if prev_table == "" else prev_table]):
                    group.append(JsonMove(diff, OperationType.REMOVE, [table]))
                yield group
                group = None

            prev_table = table
            prev_num_separators = num_separators
            if group is None:
                group = JsonMoveGroup()

            group.append(JsonMove(diff, OperationType.REMOVE, tokens))

        # Pending group, emit
        if group is not None:
            # Special case if we are deleting all the current keys in a table to emit a table delete too
            if len(list(group)) == len(diff.current_config[table]):
                group.append(JsonMove(diff, OperationType.REMOVE, [table]))
            yield group

        prev_num_separators = -1
        group = None
        prev_table = ""

        # Adding keys in target but not current
        for tokens in self._get_non_existing_keys_tokens(diff.target_config, diff.current_config, reverse=True):
            table = tokens[0]
            key = tokens[1]

            # We do not support adding the whole table, only grouping key entry creation.
            if table not in diff.current_config:
                continue

            # If the number of separators changed, do not group these operations with the previous ones.
            num_separators = key.count("|")
            if group is not None and (prev_num_separators != num_separators or table != prev_table):
                yield group
                group = None

            prev_table = table
            prev_num_separators = num_separators
            if group is None:
                group = JsonMoveGroup()

            group.append(JsonMove(diff, OperationType.ADD, tokens, tokens))

        # Pending group, emit
        if group is not None:
            yield group

    def _get_non_existing_keys_tokens(self, config1, config2, reverse):
        for table in self.path_addressing.configdb_sorted_keys_by_backlinks("/", config1, reverse=reverse):
            for key in self.path_addressing.configdb_sorted_keys_by_backlinks("/" + table, config1, reverse=reverse):
                if not(table in config2) or not (key in config2[table]):
                    yield [table, key]


class BulkKeyGroupLowLevelMoveGenerator:
    """
    This is a Wrapper around BulkLowLevelMoveGenerator that groups the leaf
    operations together spanning multiple table keys.  For example if someone
    wants to update PORT/Ethernet0/description and PORT/Ethernet1/description
    at the same time, it is safe to do so in the same patch group. This grouping
    exists in order to attempt to optimize the fast path when there are a lot
    of changes to the same table and there are often very few
    cross-dependencies.  This will bring down the patch set count considerably
    for a lot of change operations.  We do still fall back to other more
    primitive generators if the validators fail so this is an optimization that
    otherwise doesn't have any impact on the overall outcome, only performance.

    As a secondary optimization, restricted keys (primarily PORT/*/admin_status)
    operations are grouped together as typically it is ok for all restricted keys
    to change at the same time for the same table.  If its not, the validator
    will simply fail it and the generator will move on and "try" something else.
    """
    def __init__(self, path_addressing):
        self.generator = BulkLowLevelMoveGenerator(path_addressing)

    def generate(self, diff):
        # Handle removals first
        for move in self.generate_groups(diff, self.generator.generate_remove):
            yield move

        # Handle removals for restricted keys in bulk independently
        for move in self.generate_groups(diff, self.generator.generate_remove, restricted_only=True):
            yield move

        # Handle replacements next
        for move in self.generate_groups(diff, self.generator.generate_replace):
            yield move

        # Handle replacements for restricted keys in bulk independently
        for move in self.generate_groups(diff, self.generator.generate_replace, restricted_only=True):
            yield move

        # Handle additions last
        for move in self.generate_groups(diff, self.generator.generate_add):
            yield move

        # Handle additions for restricted keys in bulk independently
        for move in self.generate_groups(diff, self.generator.generate_add, restricted_only=True):
            yield move

    def generate_groups(self, diff, cb, restricted_only: bool = False):
        group = None
        for move in cb(diff, min_moves=1, restricted_only=restricted_only):
            if group is None:
                group = move
                continue

            if move.parentTableName() != group.parentTableName():
                # Don't yield if one entry, we will let the extendable move generator
                # generate it.
                if len(group) > 1:
                    yield group
                group = move
                continue

            # group matches move, merge them.
            group.merge(move)

        # Don't yield if one entry, we will let the extendable move generator
        # generate it.
        if group is not None and len(group) > 1:
            yield group


class BulkLowLevelMoveGenerator:
    """
    A class that generates low level moves that can be grouped together as a single patch
    that operate on at most one key at a time. These are moves where the path of the move
    has no children, these are the end leafs. We are going to use this as a non-extendable
    generator as the normal LowLevelMoveGenerator will generate the extendable moves.
    """
    def __init__(self, path_addressing):
        self.diff = None
        self.path_addressing = path_addressing
        self.requiredval = RequiredValueIdentifier(path_addressing)

    def generate(self, diff):
        # Handle removals first
        for move in self.generate_remove(diff):
            yield move

        # Handle replacements next
        for move in self.generate_replace(diff):
            yield move

        # Finally handle additions
        for move in self.generate_add(diff):
            yield move

    def generate_remove(self, diff, min_moves: int = 2, restricted_only: bool = False):
        self.diff = diff
        tokens = []

        for move in self.__traverse(OperationType.REMOVE, self.diff.current_config, self.diff.target_config, tokens,
                                    min_moves, restricted_only):
            yield move

    def generate_replace(self, diff, min_moves: int = 2, restricted_only: bool = False):
        self.diff = diff
        tokens = []

        for move in self.__traverse(OperationType.REPLACE, self.diff.current_config, self.diff.target_config, tokens,
                                    min_moves, restricted_only):
            yield move

    def generate_add(self, diff, min_moves: int = 2, restricted_only: bool = False):
        self.diff = diff
        tokens = []

        for move in self.__traverse(OperationType.ADD, self.diff.current_config, self.diff.target_config, tokens,
                                    min_moves, restricted_only):
            yield move

    def __restricted_key(self, tokens, key, invert: bool = False):
        tokens.append(key)
        rv = self.requiredval.target_in_required_pattern(tokens)
        tokens.pop()
        if invert:
            if rv:
                return False
            return True
        return rv

    def __traverse(self, op, current_ptr, target_ptr, tokens, min_moves, restricted_only: bool = False):
        if isinstance(current_ptr, dict):
            if self.__children_are_leafs(current_ptr) and self.__children_are_leafs(target_ptr):
                for move in self.__output_bulk_move(op, current_ptr, target_ptr, tokens, min_moves, restricted_only):
                    yield move
                return

            # If current and target are different types, skip
            if not isinstance(target_ptr, dict):
                return

            # Recurse across children, sorted by backlinks
            reverse = True
            if op == OperationType.REMOVE:
                reverse = False

            for key in self.path_addressing.configdb_sorted_keys_by_backlinks(
                    self.path_addressing.create_path(tokens), current_ptr, reverse=reverse, configdb_relative=True):

                # Does not exist in target, skip
                if target_ptr.get(key) is None:
                    continue

                tokens.append(key)
                for move in self.__traverse(op, current_ptr[key], target_ptr[key], tokens, min_moves, restricted_only):
                    yield move
                tokens.pop()
            return

        # TODO: implement list support
        return

    def __children_are_leafs(self, config_ptr):
        for key in config_ptr:
            if isinstance(config_ptr[key], dict) or isinstance(config_ptr[key], list):
                return False
        return True

    def __output_bulk_move(self, op, current_ptr, target_ptr, tokens, min_moves, restricted_only):
        match op:
            case OperationType.REMOVE:
                for move in self.__output_bulk_remove(current_ptr, target_ptr, tokens, min_moves, restricted_only):
                    yield move
            case OperationType.REPLACE:
                for move in self.__output_bulk_replace(current_ptr, target_ptr, tokens, min_moves, restricted_only):
                    yield move
            case OperationType.ADD:
                for move in self.__output_bulk_add(current_ptr, target_ptr, tokens, min_moves, restricted_only):
                    yield move

    def __output_bulk_add(self, current_ptr, target_ptr, tokens, min_moves, restricted_only):
        group = JsonMoveGroup()
        for key in target_ptr:
            if current_ptr.get(key) is None and not self.__restricted_key(tokens, key, invert=restricted_only):
                tokens.append(key)
                group.append(JsonMove(self.diff, OperationType.ADD, tokens, tokens))
                tokens.pop()

        # Not a bulk move if there's not more than one action to take
        if len(group) >= min_moves:
            yield group

    def __output_bulk_remove(self, current_ptr, target_ptr, tokens, min_moves, restricted_only):
        group = JsonMoveGroup()
        for key in current_ptr:
            if target_ptr.get(key) is None and not self.__restricted_key(tokens, key, invert=restricted_only):
                tokens.append(key)
                group.append(JsonMove(self.diff, OperationType.REMOVE, tokens))
                tokens.pop()

        # Not a bulk move if there's not more than one action to take
        if len(group) >= min_moves:
            yield group

    def __output_bulk_replace(self, current_ptr, target_ptr, tokens, min_moves, restricted_only):
        group = JsonMoveGroup()
        for key in current_ptr:
            target_val = target_ptr.get(key)
            if (target_val is not None and target_val != current_ptr.get(key) and
                    not self.__restricted_key(tokens, key, invert=restricted_only)):
                tokens.append(key)
                group.append(JsonMove(self.diff, OperationType.REPLACE, tokens, tokens))
                tokens.pop()

        # Not a bulk move if there's not more than one action to take
        if len(group) >= min_moves:
            yield group


class RemoveCreateOnlyDependencyMoveGenerator:
    """
    A class to generate the create-only fields' dependency removing moves
    """
    def __init__(self, path_addressing):
        self.path_addressing = path_addressing
        self.create_only_filter = CreateOnlyFilter(path_addressing).get_filter()

    def generate(self, diff):
        current_config = diff.current_config
        target_config = diff.target_config # Final config after applying whole patch
        reload_config = True

        processed_tables = set()
        for path in self.create_only_filter.get_paths(current_config):
            tokens = self.path_addressing.get_path_tokens(path)
            table_to_check, create_only_field = tokens[0], tokens[-1]

            if table_to_check in processed_tables:
                continue
            else:
                processed_tables.add(table_to_check)

            if table_to_check not in current_config:
                continue

            current_members = current_config[table_to_check]
            if not current_members:
                continue

            if table_to_check not in target_config:
                continue

            target_members = target_config[table_to_check]
            if not target_members:
                continue

            for member_name in current_members:
                if member_name not in target_members:
                    continue

                current_field = self._get_create_only_field(
                    current_config, table_to_check, member_name, create_only_field)
                target_field = self._get_create_only_field(
                    target_config, table_to_check, member_name, create_only_field)

                if current_field == target_field:
                    continue

                member_path = f"/{table_to_check}/{member_name}"

                for ref_path in self.path_addressing.find_ref_paths(member_path, current_config,
                                                                    reload_config=reload_config):
                    yield JsonMoveGroup(JsonMove(diff, OperationType.REMOVE,
                                        self.path_addressing.get_path_tokens(ref_path)))

                # No need to reload config after first call
                reload_config = False

    def _get_create_only_field(self, config, table_to_check,
                               member_name, create_only_field):
        return config[table_to_check][member_name].get(create_only_field, None)


class LowLevelMoveGenerator:
    """
    A class to generate the low level moves i.e. moves corresponding to differences between current/target config
    where the path of the move does not have children.
    """
    def __init__(self, path_addressing):
        self.diff = None
        self.path_addressing = path_addressing

    def generate(self, diff):
        self.diff = diff
        current_ptr = self.diff.current_config
        target_ptr = self.diff.target_config
        current_tokens = []
        target_tokens = []

        for move in self._traverse(current_ptr, target_ptr, current_tokens, target_tokens):
            yield move

    def _traverse(self, current_ptr, target_ptr, current_tokens, target_tokens):
        """
        Traverses the current/target config trees.
        The given ptrs can be:
          dict
          list of string, number, boolean, int
          string, number, boolean, int

        list of dict is not allowed
        """
        if isinstance(current_ptr, list) or isinstance(target_ptr, list):
            for move in self._traverse_list(current_ptr, target_ptr, current_tokens, target_tokens):
                yield move
            return

        if isinstance(current_ptr, dict) or isinstance(target_ptr, dict):
            for key in current_ptr:
                current_tokens.append(key)
                if key in target_ptr:
                    target_tokens.append(key)
                    for move in self._traverse(current_ptr[key], target_ptr[key], current_tokens, target_tokens):
                        yield move
                    target_tokens.pop()
                else:
                    for move in self._traverse_current(current_ptr[key], current_tokens):
                        yield move

                current_tokens.pop()

            for key in target_ptr:
                if key in current_ptr:
                    continue # Already tried in the previous loop

                target_tokens.append(key)
                current_tokens.append(key)
                for move in self._traverse_target(target_ptr[key], current_tokens, target_tokens):
                    yield move
                current_tokens.pop()
                target_tokens.pop()

            return

        # The current/target ptr are neither dict nor list, so they might be string, int, float, bool
        for move in self._traverse_value(current_ptr, target_ptr, current_tokens, target_tokens):
            yield move

    def _traverse_list(self, current_ptr, target_ptr, current_tokens, target_tokens):
        # if same elements different order, just sort by replacing whole list
        # Example:
        #   current: [1, 2, 3, 4]
        #   target: [4, 3, 2, 1]
        #   returned move: REPLACE, current, target
        current_dict_cnts = self._list_to_dict_with_count(current_ptr)
        target_dict_cnts = self._list_to_dict_with_count(target_ptr)
        if current_dict_cnts == target_dict_cnts:
            for move in self._traverse_value(current_ptr, target_ptr, current_tokens, target_tokens):
                yield move
            return

        # Otherwise try add missing and remove additional elements
        # Try remove
        if current_ptr is not None:
            for current_index, current_item in enumerate(current_ptr):
                if current_dict_cnts[current_item] > target_dict_cnts.get(current_item, 0):
                    current_tokens.append(current_index)
                    for move in self._traverse_current_value(current_item, current_tokens):
                        yield move
                    current_tokens.pop()
        # Try add
        if target_ptr is not None:
            current_cnt = len(current_ptr) if current_ptr is not None else 0
            for target_index, target_item in enumerate(target_ptr):
                if target_dict_cnts[target_item] > current_dict_cnts.get(target_item, 0):
                    index = min(current_cnt, target_index)
                    current_tokens.append(index)
                    target_tokens.append(target_index)
                    for move in self._traverse_target_value(target_item, current_tokens, target_tokens):
                        yield move
                    target_tokens.pop()
                    current_tokens.pop()

        # Try replace
        if current_ptr is not None and target_ptr is not None:
            for current_index, current_item in enumerate(current_ptr):
                for target_index, target_item in enumerate(target_ptr):
                    if current_dict_cnts[current_item] > target_dict_cnts.get(current_item, 0) and \
                    target_dict_cnts[target_item] > current_dict_cnts.get(target_item, 0):
                        current_tokens.append(current_index)
                        target_tokens.append(target_index)
                        for move in self._traverse_value(current_item, target_item, current_tokens, target_tokens):
                            yield move
                        target_tokens.pop()
                        current_tokens.pop()

    def _traverse_value(self, current_value, target_value, current_tokens, target_tokens):
        if current_value == target_value:
            return

        yield JsonMoveGroup(JsonMove(self.diff, OperationType.REPLACE, current_tokens, target_tokens))

    def _traverse_current(self, ptr, current_tokens):
        if isinstance(ptr, list):
            for move in self._traverse_current_list(ptr, current_tokens):
                yield move
            return

        if isinstance(ptr, dict):
            if len(ptr) == 0:
                yield JsonMoveGroup(JsonMove(self.diff, OperationType.REMOVE, current_tokens))
                return

            for key in ptr:
                current_tokens.append(key)
                for move in self._traverse_current(ptr[key], current_tokens):
                    yield move
                current_tokens.pop()

            return

        # ptr is not a dict nor a list, it can be string, int, float, bool
        for move in self._traverse_current_value(ptr, current_tokens):
            yield move

    def _traverse_current_list(self, ptr, current_tokens):
        if len(ptr) == 0:
            yield JsonMoveGroup(JsonMove(self.diff, OperationType.REMOVE, current_tokens))
            return

        for index, val in enumerate(ptr):
            current_tokens.append(index)
            for move in self._traverse_current_value(val, current_tokens):
                yield move
            current_tokens.pop()

    def _traverse_current_value(self, val, current_tokens):
        yield JsonMoveGroup(JsonMove(self.diff, OperationType.REMOVE, current_tokens))

    def _traverse_target(self, ptr, current_tokens, target_tokens):
        if isinstance(ptr, list):
            for move in self._traverse_target_list(ptr, current_tokens, target_tokens):
                yield move
            return

        if isinstance(ptr, dict):
            if len(ptr) == 0:
                yield JsonMoveGroup(JsonMove(self.diff, OperationType.ADD, current_tokens, target_tokens))
                return

            for key in ptr:
                current_tokens.append(key)
                target_tokens.append(key)
                for move in self._traverse_target(ptr[key], current_tokens, target_tokens):
                    yield move
                target_tokens.pop()
                current_tokens.pop()

            return

        # target configs are not dict nor list, so handle them as string, int, bool, float
        for move in self._traverse_target_value(ptr, current_tokens, target_tokens):
            yield move

    def _traverse_target_list(self, ptr, current_tokens, target_tokens):
        if len(ptr) == 0:
            yield JsonMoveGroup(JsonMove(self.diff, OperationType.ADD, current_tokens, target_tokens))
            return

        for index, val in enumerate(ptr):
            # _traverse_target_list is called when the whole list is missing
            # in such case any item should be added at first location i.e. 0
            current_tokens.append(0)
            target_tokens.append(index)
            for move in self._traverse_target_value(val, current_tokens, target_tokens):
                yield move
            target_tokens.pop()
            current_tokens.pop()

    def _traverse_target_value(self, val, current_tokens, target_tokens):
        yield JsonMoveGroup(JsonMove(self.diff, OperationType.ADD, current_tokens, target_tokens))

    def _list_to_dict_with_count(self, items):
        counts = dict()

        if items is None:
            return counts

        for item in items:
            counts[item] = counts.get(item, 0) + 1

        return counts


class RequiredValueMoveExtender:
    """
    Check RequiredValueIdentifier class description first.

    The extender does the following:
    - If the move that is changing a requiring config, while the required path is not equal to the required value, then
      generate a move to turn the required path to the required value.
      E.g. A move that is changing "QUEUE" table while the corresponding "PORT" is not admin down, then generate
           a move to turn the "PORT" to admin down.
    - If a move that is changing the required path value to something other than the required value, while there are
      requiring changes left, then flip all the required paths in the move to the required value.
      E.g. A move is changing "PORT" to admin up from down, while "QUEUE" table still have changes left, then flip
           the "PORT" to admin down in the move.
    """
    def __init__(self, path_addressing, operation_wrapper):
        self.path_addressing = path_addressing
        self.identifier = RequiredValueIdentifier(path_addressing)
        self.operation_wrapper = operation_wrapper

    def extend(self, move: JsonMove, diff):
        # ignore full config removal because it is not possible by JsonPatch lib
        if move.op_type == OperationType.REMOVE and move.path == "":
            return

        current_config = diff.current_config
        simulated_config = move.apply(current_config) # Config after applying just this move
        target_config = diff.target_config # Final config after applying whole patch

        # data dictionary:
        # {
        #   <path>: [(required_path, required_value), ...],
        #   ...
        # }
        data = self.identifier.get_required_value_data([current_config, simulated_config, target_config])

        # If move is changing a requiring path while the required path does not have the required value,
        # flip the required path to the required value
        # E.g. if the move is changing port-critical config while the port is admin up, create a move to
        #      turn the port admin down
        processed_moves = set()
        for path in data:
            if self.path_addressing.is_config_different(path, current_config, simulated_config):
                for required_path, required_value in data[path]:
                    actual_value = self.identifier.get_value_or_default(current_config, required_path)
                    if actual_value is None: # current config does not have this value at all
                        continue
                    if actual_value != required_value:
                        extended_move = JsonMove.from_operation({"op":"replace", "path":required_path, "value":required_value})
                        if extended_move not in processed_moves:
                            processed_moves.add(extended_move)
                            yield extended_move

        # If some changes to the requiring paths are still to take place and the move has changes
        # to the required path, flip the required path to the required value.
        # E.g. if there are still port-critical changes left and the move has changes to the port
        #      admin status, flip the port to admin down in the move
        # This makes sure we don't change the required path unnecessarily.
        flip_path_value_tuples = set()
        for path in data:
            if self.path_addressing.is_config_different(path, current_config, target_config):
                for required_path, required_value in data[path]:
                    current_value = self.identifier.get_value_or_default(current_config, required_path)
                    simulated_value = self.identifier.get_value_or_default(simulated_config, required_path)
                    if simulated_value is None: # Simulated config does not have this value at all.
                        continue
                    if current_value != simulated_value and simulated_value != required_value:
                        flip_path_value_tuples.add((required_path, required_value))

        if flip_path_value_tuples:
            extended_move = self._flip(move, flip_path_value_tuples)
            yield extended_move

    def _flip(self, move: JsonMove, flip_path_value_tuples):
        new_value = copy.deepcopy(move.value)
        move_tokens = self.path_addressing.get_path_tokens(move.path)
        for field_path, field_value in flip_path_value_tuples:
            field_tokens = self.path_addressing.get_path_tokens(field_path)
            new_value = self._change_value(field_tokens, field_value, move_tokens, new_value)

        operation = self.operation_wrapper.create(move.op_type, move.path, new_value)
        return JsonMove.from_operation(operation)

    def _change_value(self, field_tokens, field_value, move_tokens, move_value):
        rem_tokens = field_tokens[len(move_tokens):]
        if not rem_tokens:
            return field_value

        move_value_ptr = move_value
        for token in rem_tokens[:-1]:
            move_value_ptr = move_value_ptr[token]

        last_token = rem_tokens[-1]
        move_value_ptr[last_token] = field_value
        return move_value

class UpperLevelMoveExtender:
    """
    A class to extend the given move by including its parent. It has 3 cases:
      1) If parent was in current and target, then replace the parent
      2) If parent was in current but not target, then delete the parent
      3) If parent was in target but not current, then add the parent
    """
    def extend(self, move: JsonMove, diff):
        # if no tokens i.e. whole config
        if not move.current_config_tokens:
            return

        upper_current_tokens = move.current_config_tokens[:-1]
        operation_type = self._get_upper_operation(upper_current_tokens, diff)

        upper_target_tokens = None
        if operation_type in [OperationType.ADD, OperationType.REPLACE]:
            upper_target_tokens = upper_current_tokens

        yield JsonMove(diff, operation_type, upper_current_tokens, upper_target_tokens)

    # get upper operation assumes ConfigDb to not have list-of-objects, only list-of-values
    def _get_upper_operation(self, tokens, diff):
        current_ptr = diff.current_config
        target_ptr = diff.target_config

        for token in tokens:
            if token not in current_ptr:
                return OperationType.ADD
            current_ptr = current_ptr[token]
            if token not in target_ptr:
                return OperationType.REMOVE
            target_ptr = target_ptr[token]

        return OperationType.REPLACE

class DeleteInsteadOfReplaceMoveExtender:
    """
    A class to extend the given REPLACE move by adding a REMOVE move.
    """
    def extend(self, move: JsonMove, diff):
        operation_type = move.op_type

        if operation_type != OperationType.REPLACE:
            return

        # Cannot delete the whole config, JsonPatch lib does not support it
        if not move.current_config_tokens:
            return

        new_move = JsonMove(diff, OperationType.REMOVE, move.current_config_tokens)

        yield new_move


class DeleteRefsMoveExtender:
    """
    A class to extend the given DELETE move by adding DELETE moves to configs referring to the path in the move.
    """
    def __init__(self, path_addressing):
        self.path_addressing = path_addressing

    def extend(self, move: JsonMove, diff):
        operation_type = move.op_type

        if operation_type != OperationType.REMOVE:
            return

        for ref_path in self.path_addressing.find_ref_paths(move.path, diff.current_config, reload_config=True):
            yield JsonMove(diff, OperationType.REMOVE, self.path_addressing.get_path_tokens(ref_path))


class DfsSorter:
    def __init__(self, move_wrapper):
        self.visited = {}
        self.move_wrapper = move_wrapper

    def sort(self, diff):
        if diff.has_no_diff():
            return []

        diff_hash = hash(diff)
        if diff_hash in self.visited:
            return None
        self.visited[diff_hash] = True

        moves = self.move_wrapper.generate(diff)

        for move in moves:
            if self.move_wrapper.validate(move, diff):
                # NOTE: due to the recursive nature, we can't modify in-place as on error we will
                #       receive "RuntimeError: dictionary changed size during iteration"
                new_diff = self.move_wrapper.simulate(move, diff, in_place=False)
                new_moves = self.sort(new_diff)
                if new_moves is not None:
                    return [move] + new_moves

        return None


class BfsSorter:
    def __init__(self, move_wrapper):
        self.visited = {}
        self.move_wrapper = move_wrapper

    def sort(self, diff):
        diff_queue = deque([])
        prv_moves_queue = deque([])

        diff_queue.append(diff)
        prv_moves_queue.append([])

        while len(diff_queue):
            diff = diff_queue.popleft()
            prv_moves = prv_moves_queue.popleft()

            diff_hash = hash(diff)
            if diff_hash in self.visited:
                continue
            self.visited[diff_hash] = True

            if diff.has_no_diff():
                return prv_moves

            moves = self.move_wrapper.generate(diff)
            for move in moves:
                if self.move_wrapper.validate(move, diff):
                    new_diff = self.move_wrapper.simulate(move, diff)
                    new_prv_moves = prv_moves + [move]

                    diff_queue.append(new_diff)
                    prv_moves_queue.append(new_prv_moves)

        return None


class MemoizationSorter:
    def __init__(self, move_wrapper):
        self.visited = {}
        self.move_wrapper = move_wrapper
        self.mem = {}

    def sort(self, diff):
        if diff.has_no_diff():
            return []

        diff_hash = hash(diff)
        if diff_hash in self.mem:
            return self.mem[diff_hash]
        if diff_hash in self.visited:
            return None
        self.visited[diff_hash] = True

        moves = self.move_wrapper.generate(diff)

        bst_moves = None
        for move in moves:
            if self.move_wrapper.validate(move, diff):
                new_diff = self.move_wrapper.simulate(move, diff)
                new_moves = self.sort(new_diff)
                if new_moves != None and (bst_moves is None or len(bst_moves) > len(new_moves)+1):
                    bst_moves = [move] + new_moves

        self.mem[diff_hash] = bst_moves
        return bst_moves


class Algorithm(Enum):
    DFS = 1
    BFS = 2
    MEMOIZATION = 3


class SortAlgorithmFactory:
    def __init__(self, operation_wrapper, config_wrapper, path_addressing):
        self.operation_wrapper = operation_wrapper
        self.config_wrapper = config_wrapper
        self.path_addressing = path_addressing

    def create(self, algorithm=Algorithm.DFS):
        move_generators = [RemoveCreateOnlyDependencyMoveGenerator(self.path_addressing),
                           LowLevelMoveGenerator(self.path_addressing)]
        # TODO: Enable TableLevelMoveGenerator once it is confirmed whole table can be updated at the same time
        move_non_extendable_generators = [BulkKeyLevelMoveGenerator(self.path_addressing),
                                          KeyLevelMoveGenerator(self.path_addressing),
                                          BulkKeyGroupLowLevelMoveGenerator(self.path_addressing),
                                          BulkLowLevelMoveGenerator(self.path_addressing)]
        move_extenders = [RequiredValueMoveExtender(self.path_addressing, self.operation_wrapper),
                          UpperLevelMoveExtender(),
                          DeleteInsteadOfReplaceMoveExtender(),
                          DeleteRefsMoveExtender(self.path_addressing)]
        move_validators = [DeleteWholeConfigMoveValidator(),
                           FullConfigMoveValidator(self.config_wrapper),
                           NoDependencyMoveValidator(self.path_addressing, self.config_wrapper),
                           CreateOnlyMoveValidator(self.path_addressing),
                           RequiredValueMoveValidator(self.path_addressing),
                           RemoveCreateOnlyDependencyMoveValidator(self.path_addressing),
                           NoEmptyTableMoveValidator(self.path_addressing)]

        move_wrapper = MoveWrapper(move_generators, move_non_extendable_generators, move_extenders, move_validators)

        if algorithm == Algorithm.DFS:
            sorter = DfsSorter(move_wrapper)
        elif algorithm == Algorithm.BFS:
            sorter = BfsSorter(move_wrapper)
        elif algorithm == Algorithm.MEMOIZATION:
            sorter = MemoizationSorter(move_wrapper)
        else:
            raise ValueError(f"Algorithm {algorithm} is not supported")

        return sorter


class StrictPatchSorter:
    def __init__(self, config_wrapper, patch_wrapper, inner_patch_sorter=None):
        self.logger = genericUpdaterLogging.get_logger(title="Patch Sorter - Strict", print_all_to_console=True)
        self.config_wrapper = config_wrapper
        self.patch_wrapper = patch_wrapper
        self.inner_patch_sorter = inner_patch_sorter if inner_patch_sorter else PatchSorter(config_wrapper, patch_wrapper)

    def sort(self, patch, algorithm=Algorithm.DFS):
        current_config = self.config_wrapper.get_config_db_as_json()

        # Validate patch is only updating tables with yang models
        self.logger.log_info("Validating patch is not making changes to tables without YANG models.")
        if not(self.patch_wrapper.validate_config_db_patch_has_yang_models(patch)):
            raise ValueError(f"Given patch is not valid because it has changes to tables without YANG models")

        target_config = self.patch_wrapper.simulate_patch(patch, current_config)

        # Validate target config
        self.logger.log_info("Validating target config according to YANG models.")
        is_valid, error = self.config_wrapper.validate_config_db_config(target_config)
        if not is_valid:
            raise ValueError(f"Given patch will produce invalid config. Error: {error}")

        # Generate list of changes to apply
        self.logger.log_info("Sorting patch updates.")
        changes = self.inner_patch_sorter.sort(patch, algorithm)

        return changes

class TablesWithoutYangConfigSplitter:
    def __init__(self, config_wrapper):
        self.config_wrapper = config_wrapper

    def split_yang_non_yang_distinct_field_path(self, config):
        config_with_yang = self.config_wrapper.crop_tables_without_yang(config)
        config_without_yang = {}

        for key in config:
            if key not in config_with_yang:
                config_without_yang[key] = copy.deepcopy(config[key])

        return config_with_yang, config_without_yang

class IgnorePathsFromYangConfigSplitter:
    def __init__(self, ignore_paths_from_yang_list, config_wrapper):
        self.ignore_paths_from_yang_list = ignore_paths_from_yang_list
        self.config_wrapper = config_wrapper
        self.path_addressing = PathAddressing(config_wrapper)

    def split_yang_non_yang_distinct_field_path(self, config):
        config_with_yang = copy.deepcopy(config)
        config_without_yang = {}

        # ignore more config from config_with_yang
        for path in self.ignore_paths_from_yang_list:
            if not self.path_addressing.has_path(config_with_yang, path):
                continue
            if path == '': # whole config to be ignored
                return {}, copy.deepcopy(config)

            # Add to config_without_yang from config_with_yang
            tokens = self.path_addressing.get_path_tokens(path)
            add_move = JsonMoveGroup(JsonMove(Diff(config_without_yang, config_with_yang), OperationType.ADD, tokens,
                                              tokens))
            config_without_yang = add_move.apply(config_without_yang)

            # Remove from config_with_yang
            remove_move = JsonMoveGroup(JsonMove(Diff(config_with_yang, {}), OperationType.REMOVE, tokens))
            config_with_yang = remove_move.apply(config_with_yang)

        # Splitting the config based on 'ignore_paths_from_yang_list' can result in empty tables.
        # Remove empty tables because they are not allowed in ConfigDb
        config_with_yang_without_empty_tables = self.config_wrapper.remove_empty_tables(config_with_yang)
        config_without_yang_without_empty_tables = self.config_wrapper.remove_empty_tables(config_without_yang)
        return config_with_yang_without_empty_tables, config_without_yang_without_empty_tables

class ConfigSplitter:
    def __init__(self, config_wrapper, inner_config_splitters):
        self.config_wrapper = config_wrapper
        self.inner_config_splitters = inner_config_splitters

    def split_yang_non_yang_distinct_field_path(self, config):
        empty_tables = self.config_wrapper.get_empty_tables(config)
        empty_tables_txt = ", ".join(empty_tables)
        if empty_tables:
            raise ValueError(f"Given config has empty tables. Table{'s' if len(empty_tables) != 1 else ''}: {empty_tables_txt}")

        # Start by assuming all config should be YANG covered
        config_with_yang = copy.deepcopy(config)
        config_without_yang = {}

        for config_splitter in self.inner_config_splitters:
            config_with_yang, additional_config_without_yang = config_splitter.split_yang_non_yang_distinct_field_path(config_with_yang)
            config_without_yang = self.merge_configs_with_distinct_field_path(config_without_yang, additional_config_without_yang)

        return config_with_yang, config_without_yang

    def merge_configs_with_distinct_field_path(self, config1, config2):
        merged_config = copy.deepcopy(config1)
        self.__recursive_append(merged_config, config2)
        return merged_config

    def __recursive_append(self, target, additional, path=""):
        if not isinstance(target, dict):
            raise ValueError(f"Found a field that exist in both config1 and config2. Path: {path}")
        for key in additional:
            if key not in target:
                target[key] = copy.deepcopy(additional[key])
            else:
                self.__recursive_append(target[key], additional[key], f"{path}/{key}")

class ChangeWrapper:
    def __init__(self, patch_wrapper, config_splitter):
        self.patch_wrapper = patch_wrapper
        self.config_splitter = config_splitter

    def adjust_changes(self, assumed_changes, assumed_curr_config, remaining_distinct_curr_config):
        """
        The merging of 'assumed_curr_config' and 'remaining_distinct_curr_config' will generate the full config.
        The list of 'assumed_changes' are applicable to 'assumed_curr_config' but they cannot be applied directly to the full config.
        'assumed_changes' can blindly alter existing config in 'remaining_distinct_curr_config' but they should not. Check example below.

        Example:
          assumed_curr_config:
          {
            "ACL_TABLE":
            {
              "Everflow": { "type": "L3" }
            }
          }

          remaining_distinct_curr_config:
          {
            "ACL_TABLE":
            {
              "Everflow": { "policy_desc": "some-description" }
            }
          }

          assumed_changes (these are only applicable to assumed_curr_config):
          {
            [{"op":"replace", "path":"/ACL_TABLE/EVERFLOW", "value":{"type":"MIRROR"}}]
          }

          The merging of assumed_curr_config and remaining_distinct_curr_config to get the full config is:
          {
            "ACL_TABLE":
            {
              "Everflow": { "type": "L3", "policy_desc": "some-description" }
            }
          }

          Applying changes to the merging i.e. full config will result in:
          {
            "ACL_TABLE":
            {
              "Everflow": { "type": "MIRROR" }
            }
          }

          This is not correct, as we have deleted /ACL_TABLE/EVERFLOW/policy_desc
          This problem happened because we used 'assumed_changes' for 'assumed_curr_config' on the full config.

          The solution is to adjust the 'assumed_changes' list to be:
          {
            [{"op":"replace", "path":"/ACL_TABLE/EVERFLOW/type", "value":"MIRROR"}]
          }

          This method adjust the given 'assumed_changes' to be applicable to the full config.

          Check unit-test for more examples.
       """
        adjusted_changes = []
        assumed_curr_config = copy.deepcopy(assumed_curr_config)
        for change in assumed_changes:
            assumed_target_config = change.apply(assumed_curr_config)

            adjusted_curr_config = self.config_splitter.merge_configs_with_distinct_field_path(assumed_curr_config, remaining_distinct_curr_config)
            adjusted_target_config = self.config_splitter.merge_configs_with_distinct_field_path(assumed_target_config, remaining_distinct_curr_config)

            adjusted_patch = self.patch_wrapper.generate_patch(adjusted_curr_config, adjusted_target_config)

            adjusted_change = JsonChange(adjusted_patch)
            adjusted_changes.append(adjusted_change)

            assumed_curr_config = assumed_target_config

        return adjusted_changes

class NonStrictPatchSorter:
    def __init__(self, config_wrapper, patch_wrapper, config_splitter, change_wrapper=None, patch_sorter=None):
        self.logger = genericUpdaterLogging.get_logger(title="Patch Sorter - Non-Strict", print_all_to_console=True)
        self.config_wrapper = config_wrapper
        self.patch_wrapper = patch_wrapper
        self.config_splitter = config_splitter
        self.change_wrapper = change_wrapper if change_wrapper else ChangeWrapper(patch_wrapper, config_splitter)
        self.inner_patch_sorter = patch_sorter if patch_sorter else PatchSorter(config_wrapper, patch_wrapper)

    def sort(self, patch, algorithm=Algorithm.DFS):
        current_config = self.config_wrapper.get_config_db_as_json()
        target_config = self.patch_wrapper.simulate_patch(patch, current_config)

        # Splitting current/target config based on YANG covered vs non-YANG covered configs
        self.logger.log_info("Splitting current/target config based on YANG covered vs non-YANG covered configs.")
        current_config_yang, current_config_non_yang = self.config_splitter.split_yang_non_yang_distinct_field_path(current_config)
        target_config_yang, target_config_non_yang = self.config_splitter.split_yang_non_yang_distinct_field_path(target_config)

        # Validate YANG covered target config
        self.logger.log_info("Validating YANG covered target config according to YANG models.")
        is_valid, error = self.config_wrapper.validate_config_db_config(target_config_yang)
        if not is_valid:
            raise ValueError(f"Given patch will produce invalid config. Error: {error}")

        # Generating changes associated with non-YANG covered configs
        self.logger.log_info("Sorting non-YANG covered configs patch updates.")
        non_yang_patch = self.patch_wrapper.generate_patch(current_config_non_yang, target_config_non_yang)
        non_yang_changes = [JsonChange(non_yang_patch)] if non_yang_patch else []
        changes_len = len(non_yang_changes)
        self.logger.log_debug(f"The Non-YANG covered config update was sorted into {changes_len} " \
                             f"change{'s' if changes_len != 1 else ''}{':' if changes_len > 0 else '.'}")
        for change in non_yang_changes:
            self.logger.log_debug(f"  * {change}")

        # Regenerating patch for YANG covered configs
        self.logger.log_info("Regenerating patch for YANG covered configs only.")
        yang_patch = self.patch_wrapper.generate_patch(current_config_yang, target_config_yang)
        self.logger.log_info(f"Generated patch {yang_patch}")

        # Validate YANG covered config patch is only updating tables with yang models
        self.logger.log_info("Validating YANG covered config patch is not making changes to tables without YANG models.")
        if not(self.patch_wrapper.validate_config_db_patch_has_yang_models(yang_patch)):
            raise ValueError(f"Given YANG covered config patch is not valid because it has changes to tables without YANG models")

        # Generating changes associated with YANG covered configs
        self.logger.log_info("Sorting YANG-covered configs patch updates.")
        yang_changes = self.inner_patch_sorter.sort(yang_patch, algorithm, current_config_yang)
        changes_len = len(yang_changes)
        self.logger.log_debug(f"The YANG covered config update was sorted into {changes_len} " \
                             f"change{'s' if changes_len != 1 else ''}{':' if changes_len > 0 else '.'}")
        for change in yang_changes:
            self.logger.log_debug(f"  * {change}")

        # Merging non-YANG and YANG covered changes.
        self.logger.log_info("Merging non-YANG and YANG covered changes.")
        adjusted_non_yang_changes = self.change_wrapper.adjust_changes(non_yang_changes, current_config_non_yang, current_config_yang)
        adjusted_yang_changes = self.change_wrapper.adjust_changes(yang_changes, current_config_yang, target_config_non_yang)
        changes = adjusted_non_yang_changes + adjusted_yang_changes

        return changes

class PatchSorter:
    def __init__(self, config_wrapper, patch_wrapper, sort_algorithm_factory=None):
        self.config_wrapper = config_wrapper
        self.patch_wrapper = patch_wrapper
        self.operation_wrapper = OperationWrapper()
        self.path_addressing = PathAddressing(self.config_wrapper)
        self.sort_algorithm_factory = sort_algorithm_factory if sort_algorithm_factory else \
            SortAlgorithmFactory(self.operation_wrapper, config_wrapper, self.path_addressing)

    def sort(self, patch, algorithm=Algorithm.DFS, preloaded_current_config=None):
        current_config = preloaded_current_config if preloaded_current_config else self.config_wrapper.get_config_db_as_json()
        target_config = self.patch_wrapper.simulate_patch(patch, current_config)

        diff = Diff(copy.deepcopy(current_config), target_config)

        sort_algorithm = self.sort_algorithm_factory.create(algorithm)
        moves = sort_algorithm.sort(diff)

        if moves is None:
            raise GenericConfigUpdaterError("There is no possible sorting")

        changes = [JsonChange(move.get_jsonpatch()) for move in moves]

        return changes
