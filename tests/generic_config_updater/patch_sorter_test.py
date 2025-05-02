from collections import OrderedDict
import jsonpatch
import unittest
from unittest.mock import MagicMock, Mock

import generic_config_updater.patch_sorter as ps
from .gutest_helpers import Files, create_side_effect_dict
from generic_config_updater.gu_common import ConfigWrapper, PatchWrapper, OperationWrapper, \
                                             GenericConfigUpdaterError, OperationType, JsonChange, PathAddressing

class TestDiff(unittest.TestCase):
    def test_apply_move__updates_current_config(self):
        # Arrange
        diff = ps.Diff(current_config=Files.CROPPED_CONFIG_DB_AS_JSON, target_config=Files.ANY_CONFIG_DB)
        move = ps.JsonMove.from_patch(Files.SINGLE_OPERATION_CONFIG_DB_PATCH)

        expected = ps.Diff(current_config=Files.CONFIG_DB_AFTER_SINGLE_OPERATION, target_config=Files.ANY_CONFIG_DB)

        # Act
        actual = diff.apply_move(move)

        # Assert
        self.assertEqual(expected.current_config, actual.current_config)
        self.assertEqual(expected.target_config, actual.target_config)

    def test_has_no_diff__diff_exists__returns_false(self):
        # Arrange
        diff = ps.Diff(current_config=Files.CROPPED_CONFIG_DB_AS_JSON,
                       target_config=Files.CONFIG_DB_AFTER_SINGLE_OPERATION)

        # Act and Assert
        self.assertFalse(diff.has_no_diff())

    def test_has_no_diff__no_diff__returns_true(self):
        # Arrange
        diff = ps.Diff(current_config=Files.CROPPED_CONFIG_DB_AS_JSON,
                       target_config=Files.CROPPED_CONFIG_DB_AS_JSON)

        # Act and Assert
        self.assertTrue(diff.has_no_diff())

    def test_hash__different_current_config__different_hashes(self):
        # Arrange
        diff1 = ps.Diff(current_config=Files.CROPPED_CONFIG_DB_AS_JSON, target_config=Files.ANY_CONFIG_DB)
        diff2 = ps.Diff(current_config=Files.CROPPED_CONFIG_DB_AS_JSON, target_config=Files.ANY_CONFIG_DB)
        diff3 = ps.Diff(current_config=Files.CONFIG_DB_AFTER_SINGLE_OPERATION, target_config=Files.ANY_CONFIG_DB)

        # Act
        hash1 = hash(diff1)
        hash2 = hash(diff2)
        hash3 = hash(diff3)

        # Assert
        self.assertEqual(hash1, hash2) # same current config
        self.assertNotEqual(hash1, hash3)

    def test_hash__different_target_config__different_hashes(self):
        # Arrange
        diff1 = ps.Diff(current_config=Files.ANY_CONFIG_DB, target_config=Files.CROPPED_CONFIG_DB_AS_JSON)
        diff2 = ps.Diff(current_config=Files.ANY_CONFIG_DB, target_config=Files.CROPPED_CONFIG_DB_AS_JSON)
        diff3 = ps.Diff(current_config=Files.ANY_CONFIG_DB, target_config=Files.CONFIG_DB_AFTER_SINGLE_OPERATION)

        # Act
        hash1 = hash(diff1)
        hash2 = hash(diff2)
        hash3 = hash(diff3)

        # Assert
        self.assertEqual(hash1, hash2) # same target config
        self.assertNotEqual(hash1, hash3)

    def test_hash__swapped_current_and_target_configs__different_hashes(self):
        # Arrange
        diff1 = ps.Diff(current_config=Files.ANY_CONFIG_DB, target_config=Files.ANY_OTHER_CONFIG_DB)
        diff2 = ps.Diff(current_config=Files.ANY_OTHER_CONFIG_DB, target_config=Files.ANY_CONFIG_DB)

        # Act
        hash1 = hash(diff1)
        hash2 = hash(diff2)

        # Assert
        self.assertNotEqual(hash1, hash2)

    def test_eq__different_current_config__returns_false(self):
        # Arrange
        diff = ps.Diff(Files.ANY_CONFIG_DB, Files.ANY_CONFIG_DB)
        other_diff = ps.Diff(Files.ANY_OTHER_CONFIG_DB, Files.ANY_CONFIG_DB)

        # Act and assert
        self.assertNotEqual(diff, other_diff)
        self.assertFalse(diff == other_diff)

    def test_eq__different_target_config__returns_false(self):
        # Arrange
        diff = ps.Diff(Files.ANY_CONFIG_DB, Files.ANY_CONFIG_DB)
        other_diff = ps.Diff(Files.ANY_CONFIG_DB, Files.ANY_OTHER_CONFIG_DB)

        # Act and assert
        self.assertNotEqual(diff, other_diff)
        self.assertFalse(diff == other_diff)

    def test_eq__different_target_config__returns_true(self):
        # Arrange
        diff = ps.Diff(Files.ANY_CONFIG_DB, Files.ANY_CONFIG_DB)
        other_diff = ps.Diff(Files.ANY_CONFIG_DB, Files.ANY_CONFIG_DB)

        # Act and assert
        self.assertEqual(diff, other_diff)
        self.assertTrue(diff == other_diff)

class TestJsonMove(unittest.TestCase):
    def setUp(self):
        self.operation_wrapper = OperationWrapper()
        self.any_op_type = OperationType.REPLACE
        self.any_tokens = ["table1", "key11"]
        self.any_path = "/table1/key11"
        self.any_config = {
            "table1": {
                "key11": "value11"
            }
        }
        self.any_value = "value11"
        self.any_operation = self.operation_wrapper.create(self.any_op_type, self.any_path, self.any_value)
        self.any_diff = ps.Diff(self.any_config, self.any_config)

    def test_ctor__delete_op_whole_config__none_value_and_empty_path(self):
        # Arrange
        path = ""
        diff = ps.Diff(current_config={}, target_config=self.any_config)

        # Act
        jsonmove = ps.JsonMove(diff, OperationType.REMOVE, [])

        # Assert
        self.verify_jsonmove(self.operation_wrapper.create(OperationType.REMOVE, path),
                             OperationType.REMOVE,
                             [],
                             None,
                             jsonmove)
    def test_ctor__remove_op__operation_created_directly(self):
        # Arrange and Act
        jsonmove = ps.JsonMove(self.any_diff, OperationType.REMOVE, self.any_tokens)

        # Assert
        self.verify_jsonmove(self.operation_wrapper.create(OperationType.REMOVE, self.any_path),
                             OperationType.REMOVE,
                             self.any_tokens,
                             None,
                             jsonmove)

    def test_ctor__replace_op_whole_config__whole_config_value_and_empty_path(self):
        # Arrange
        path = ""
        diff = ps.Diff(current_config={}, target_config=self.any_config)

        # Act
        jsonmove = ps.JsonMove(diff, OperationType.REPLACE, [], [])

        # Assert
        self.verify_jsonmove(self.operation_wrapper.create(OperationType.REPLACE, path, self.any_config),
                             OperationType.REPLACE,
                             [],
                             [],
                             jsonmove)

    def test_ctor__replace_op__operation_created_directly(self):
        # Arrange and Act
        jsonmove = ps.JsonMove(self.any_diff, OperationType.REPLACE, self.any_tokens, self.any_tokens)

        # Assert
        self.verify_jsonmove(self.operation_wrapper.create(OperationType.REPLACE, self.any_path, self.any_value),
                             OperationType.REPLACE,
                             self.any_tokens,
                             self.any_tokens,
                             jsonmove)

    def test_ctor__add_op_whole_config__whole_config_value_and_empty_path(self):
        # Arrange
        path = ""
        diff = ps.Diff(current_config={}, target_config=self.any_config)

        # Act
        jsonmove = ps.JsonMove(diff, OperationType.ADD, [], [])

        # Assert
        self.verify_jsonmove(self.operation_wrapper.create(OperationType.ADD, path, self.any_config),
                             OperationType.ADD,
                             [],
                             [],
                             jsonmove)

    def test_ctor__add_op_path_exist__same_value_and_path(self):
        # Arrange and Act
        jsonmove = ps.JsonMove(self.any_diff, OperationType.ADD, self.any_tokens, self.any_tokens)

        # Assert
        self.verify_jsonmove(self.operation_wrapper.create(OperationType.ADD, self.any_path, self.any_value),
                             OperationType.ADD,
                             self.any_tokens,
                             self.any_tokens,
                             jsonmove)

    def test_ctor__add_op_path_exist_include_list__same_value_and_path(self):
        # Arrange
        current_config = {
            "table1": {
                "list1": ["value11", "value13"]
            }
        }
        target_config = {
            "table1": {
                "list1": ["value11", "value12", "value13", "value14"]
            }
        }
        diff = ps.Diff(current_config, target_config)
        op_type = OperationType.ADD
        current_config_tokens = ["table1", "list1", 1] # Index is 1 which does not exist in target
        target_config_tokens = ["table1", "list1", 1]
        expected_jsonpatch_path = "/table1/list1/1"
        expected_jsonpatch_value = "value12"
        # NOTE: the target config can contain more diff than the given move.

        # Act
        jsonmove = ps.JsonMove(diff, op_type, current_config_tokens, target_config_tokens)

        # Assert
        self.verify_jsonmove(self.operation_wrapper.create(op_type, expected_jsonpatch_path, expected_jsonpatch_value),
                             op_type,
                             current_config_tokens,
                             target_config_tokens,
                             jsonmove)

    def test_ctor__add_op_path_exist_list_index_doesnot_exist_in_target___same_value_and_path(self):
        # Arrange
        current_config = {
            "table1": {
                "list1": ["value11"]
            }
        }
        target_config = {
            "table1": {
                "list1": ["value12"]
            }
        }
        diff = ps.Diff(current_config, target_config)
        op_type = OperationType.ADD
        current_config_tokens = ["table1", "list1", 1] # Index is 1 which does not exist in target
        target_config_tokens = ["table1", "list1", 0]
        expected_jsonpatch_path = "/table1/list1/1"
        expected_jsonpatch_value = "value12"
        # NOTE: the target config can contain more diff than the given move.

        # Act
        jsonmove = ps.JsonMove(diff, op_type, current_config_tokens, target_config_tokens)

        # Assert
        self.verify_jsonmove(self.operation_wrapper.create(op_type, expected_jsonpatch_path, expected_jsonpatch_value),
                             op_type,
                             current_config_tokens,
                             target_config_tokens,
                             jsonmove)

    def test_ctor__add_op_path_doesnot_exist__value_and_path_of_parent(self):
        # Arrange
        current_config = {
        }
        target_config = {
            "table1": {
                "key11": {
                    "key111": "value111"
                }
            }
        }
        diff = ps.Diff(current_config, target_config)
        op_type = OperationType.ADD
        current_config_tokens = ["table1", "key11", "key111"]
        target_config_tokens = ["table1", "key11", "key111"]
        expected_jsonpatch_path = "/table1"
        expected_jsonpatch_value = {
            "key11": {
                "key111": "value111"
            }
        }
        # NOTE: the target config can contain more diff than the given move.

        # Act
        jsonmove = ps.JsonMove(diff, op_type, current_config_tokens, target_config_tokens)

        # Assert
        self.verify_jsonmove(self.operation_wrapper.create(op_type, expected_jsonpatch_path, expected_jsonpatch_value),
                             op_type,
                             current_config_tokens,
                             target_config_tokens,
                             jsonmove)

    def test_ctor__add_op_path_doesnot_exist_include_list__value_and_path_of_parent(self):
        # Arrange
        current_config = {
        }
        target_config = {
            "table1": {
                "list1": ["value11", "value12", "value13", "value14"]
            }
        }
        diff = ps.Diff(current_config, target_config)
        op_type = OperationType.ADD
        current_config_tokens = ["table1", "list1", 0]
        target_config_tokens = ["table1", "list1", 1]
        expected_jsonpatch_path = "/table1"
        expected_jsonpatch_value = {
            "list1": ["value12"]
        }
        # NOTE: the target config can contain more diff than the given move.

        # Act
        jsonmove = ps.JsonMove(diff, op_type, current_config_tokens, target_config_tokens)

        # Assert
        self.verify_jsonmove(self.operation_wrapper.create(op_type, expected_jsonpatch_path, expected_jsonpatch_value),
                             op_type,
                             current_config_tokens,
                             target_config_tokens,
                             jsonmove)

    def test_from_patch__more_than_1_op__failure(self):
        # Arrange
        patch = jsonpatch.JsonPatch([self.any_operation, self.any_operation])

        # Act and Assert
        self.assertRaises(GenericConfigUpdaterError, ps.JsonMove.from_patch, patch)

    def test_from_patch__delete_op__delete_jsonmove(self):
        # Arrange
        operation = self.operation_wrapper.create(OperationType.REMOVE, self.any_path)
        patch = jsonpatch.JsonPatch([operation])

        # Act
        jsonmove = ps.JsonMove.from_patch(patch)

        # Assert
        self.verify_jsonmove(operation,
                             OperationType.REMOVE,
                             self.any_tokens,
                             None,
                             jsonmove)

    def test_from_patch__replace_op__replace_jsonmove(self):
        # Arrange
        operation = self.operation_wrapper.create(OperationType.REPLACE, self.any_path, self.any_value)
        patch = jsonpatch.JsonPatch([operation])

        # Act
        jsonmove = ps.JsonMove.from_patch(patch)

        # Assert
        self.verify_jsonmove(operation,
                             OperationType.REPLACE,
                             self.any_tokens,
                             self.any_tokens,
                             jsonmove)

    def test_from_patch__add_op__add_jsonmove(self):
        # Arrange
        operation = self.operation_wrapper.create(OperationType.ADD, self.any_path, self.any_value)
        patch = jsonpatch.JsonPatch([operation])

        # Act
        jsonmove = ps.JsonMove.from_patch(patch)

        # Assert
        self.verify_jsonmove(operation,
                             OperationType.ADD,
                             self.any_tokens,
                             self.any_tokens,
                             jsonmove)

    def test_from_patch__add_op_with_list_indexes__add_jsonmove(self):
        # Arrange
        path = "/table1/key11/list1111/3"
        value = "value11111"
         # From a JsonPatch it is not possible to figure out if the '3' is an item in a list or a dictionary,
         # will assume by default a dictionary for simplicity.
        tokens = ["table1", "key11", "list1111", "3"]
        operation = self.operation_wrapper.create(OperationType.ADD, path, value)
        patch = jsonpatch.JsonPatch([operation])

        # Act
        jsonmove = ps.JsonMove.from_patch(patch)

        # Assert
        self.verify_jsonmove(operation,
                             OperationType.ADD,
                             tokens,
                             tokens,
                             jsonmove)

    def test_from_patch__replace_whole_config__whole_config_jsonmove(self):
        # Arrange
        tokens = []
        path = ""
        value = {"table1": {"key1": "value1"} }
        operation = self.operation_wrapper.create(OperationType.REPLACE, path, value)
        patch = jsonpatch.JsonPatch([operation])

        # Act
        jsonmove = ps.JsonMove.from_patch(patch)

        # Assert
        self.verify_jsonmove(operation,
                             OperationType.REPLACE,
                             tokens,
                             tokens,
                             jsonmove)

    def verify_jsonmove(self,
                        expected_operation,
                        expected_op_type,
                        expected_current_config_tokens,
                        expected_target_config_tokens,
                        jsonmove):
        expected_patch = jsonpatch.JsonPatch([expected_operation])
        self.assertEqual(expected_patch, jsonmove.patch)
        self.assertEqual(expected_op_type, jsonmove.op_type)
        self.assertListEqual(expected_current_config_tokens, jsonmove.current_config_tokens)
        self.assertEqual(expected_target_config_tokens, jsonmove.target_config_tokens)

class TestMoveWrapper(unittest.TestCase):
    def setUp(self):
        self.any_current_config = {}
        self.any_target_config = {}
        self.any_diff = ps.Diff(self.any_current_config, self.any_target_config)
        self.any_move = Mock()
        self.any_other_move1 = Mock()
        self.any_other_move2 = Mock()
        self.any_extended_move = Mock()
        self.any_other_extended_move1 = Mock()
        self.any_other_extended_move2 = Mock()

        self.single_move_generator = Mock()
        self.single_move_generator.generate.side_effect = \
            create_side_effect_dict({(str(self.any_diff),): [self.any_move]})

        self.another_single_move_generator = Mock()
        self.another_single_move_generator.generate.side_effect = \
            create_side_effect_dict({(str(self.any_diff),): [self.any_other_move1]})

        self.multiple_move_generator = Mock()
        self.multiple_move_generator.generate.side_effect = create_side_effect_dict(
            {(str(self.any_diff),): [self.any_move, self.any_other_move1, self.any_other_move2]})

        self.single_move_extender = Mock()
        self.single_move_extender.extend.side_effect = create_side_effect_dict(
            {
                (str(self.any_move), str(self.any_diff)): [self.any_extended_move],
                (str(self.any_extended_move), str(self.any_diff)): [], # As first extended move will be extended
                (str(self.any_other_extended_move1), str(self.any_diff)): [] # Needed when mixed with other extenders
            })

        self.another_single_move_extender = Mock()
        self.another_single_move_extender.extend.side_effect = create_side_effect_dict(
            {
                (str(self.any_move), str(self.any_diff)): [self.any_other_extended_move1],
                (str(self.any_other_extended_move1), str(self.any_diff)): [], # As first extended move will be extended
                (str(self.any_extended_move), str(self.any_diff)): [] # Needed when mixed with other extenders
            })

        self.multiple_move_extender = Mock()
        self.multiple_move_extender.extend.side_effect = create_side_effect_dict(
            {
                (str(self.any_move), str(self.any_diff)): \
                    [self.any_extended_move, self.any_other_extended_move1, self.any_other_extended_move2],
                # All extended moves will be extended
                (str(self.any_extended_move), str(self.any_diff)): [],
                (str(self.any_other_extended_move1), str(self.any_diff)): [],
                (str(self.any_other_extended_move2), str(self.any_diff)): [],
            })

        self.mixed_move_extender = Mock()
        self.mixed_move_extender.extend.side_effect = create_side_effect_dict(
            {
                (str(self.any_move), str(self.any_diff)): [self.any_extended_move],
                (str(self.any_other_move1), str(self.any_diff)): [self.any_other_extended_move1],
                (str(self.any_extended_move), str(self.any_diff)): \
                    [self.any_other_extended_move1, self.any_other_extended_move2],
                # All extended moves will be extended
                (str(self.any_other_extended_move1), str(self.any_diff)): [],
                (str(self.any_other_extended_move2), str(self.any_diff)): [],
            })

        self.fail_move_validator = Mock()
        self.fail_move_validator.validate.side_effect = create_side_effect_dict(
            {(str(self.any_move), str(self.any_diff)): False})

        self.success_move_validator = Mock()
        self.success_move_validator.validate.side_effect = create_side_effect_dict(
            {(str(self.any_move), str(self.any_diff)): True})

    def test_ctor__assigns_values_correctly(self):
        # Arrange
        move_generators = Mock()
        move_non_extendable_generators = Mock()
        move_extenders = Mock()
        move_validators = Mock()

        # Act
        move_wrapper = ps.MoveWrapper(move_generators, move_non_extendable_generators, move_extenders, move_validators)

        # Assert
        self.assertIs(move_generators, move_wrapper.move_generators)
        self.assertIs(move_non_extendable_generators, move_wrapper.move_non_extendable_generators)
        self.assertIs(move_extenders, move_wrapper.move_extenders)
        self.assertIs(move_validators, move_wrapper.move_validators)

    def test_generate__single_move_generator__single_move_returned(self):
        # Arrange
        move_generators = [self.single_move_generator]
        move_wrapper = ps.MoveWrapper(move_generators, [], [], [])
        expected = [self.any_move]

        # Act
        actual = list(move_wrapper.generate(self.any_diff))

        # Assert
        self.assertListEqual(expected, actual)

    def test_generate__multiple_move_generator__multiple_move_returned(self):
        # Arrange
        move_generators = [self.multiple_move_generator]
        move_wrapper = ps.MoveWrapper(move_generators, [], [], [])
        expected = [self.any_move, self.any_other_move1, self.any_other_move2]

        # Act
        actual = list(move_wrapper.generate(self.any_diff))

        # Assert
        self.assertListEqual(expected, actual)

    def test_generate__different_move_generators__different_moves_returned(self):
        # Arrange
        move_generators = [self.single_move_generator, self.another_single_move_generator]
        move_wrapper = ps.MoveWrapper(move_generators, [], [], [])
        expected = [self.any_move, self.any_other_move1]

        # Act
        actual = list(move_wrapper.generate(self.any_diff))

        # Assert
        self.assertListEqual(expected, actual)

    def test_generate__duplicate_generated_moves__unique_moves_returned(self):
        # Arrange
        move_generators = [self.single_move_generator, self.single_move_generator]
        move_wrapper = ps.MoveWrapper(move_generators, [], [], [])
        expected = [self.any_move]

        # Act
        actual = list(move_wrapper.generate(self.any_diff))

        # Assert
        self.assertListEqual(expected, actual)

    def test_generate__different_move_non_extendable_generators__different_moves_returned(self):
        # Arrange
        move_non_extendable_generators = [self.single_move_generator, self.another_single_move_generator]
        move_wrapper = ps.MoveWrapper([], move_non_extendable_generators, [], [])
        expected = [self.any_move, self.any_other_move1]

        # Act
        actual = list(move_wrapper.generate(self.any_diff))

        # Assert
        self.assertListEqual(expected, actual)

    def test_generate__duplicate_generated_non_extendable_moves__unique_moves_returned(self):
        # Arrange
        move_non_extendable_generators = [self.single_move_generator, self.single_move_generator]
        move_wrapper = ps.MoveWrapper([], move_non_extendable_generators, [], [])
        expected = [self.any_move]

        # Act
        actual = list(move_wrapper.generate(self.any_diff))

        # Assert
        self.assertListEqual(expected, actual)

    def test_generate__duplicate_move_between_extendable_and_non_extendable_generators__unique_move_returned(self):
        # Arrange
        move_generators = [self.single_move_generator]
        move_non_extendable_generators = [self.single_move_generator]
        move_wrapper = ps.MoveWrapper(move_generators, move_non_extendable_generators, [], [])
        expected = [self.any_move]

        # Act
        actual = list(move_wrapper.generate(self.any_diff))

        # Assert
        self.assertListEqual(expected, actual)

    def test_generate__single_move_extender__one_extended_move_returned(self):
        # Arrange
        move_generators = [self.single_move_generator]
        move_extenders = [self.single_move_extender]
        move_wrapper = ps.MoveWrapper(move_generators, [], move_extenders, [])
        expected = [self.any_move, self.any_extended_move]

        # Act
        actual = list(move_wrapper.generate(self.any_diff))

        # Assert
        self.assertListEqual(expected, actual)

    def test_generate__multiple_move_extender__multiple_extended_move_returned(self):
        # Arrange
        move_generators = [self.single_move_generator]
        move_extenders = [self.multiple_move_extender]
        move_wrapper = ps.MoveWrapper(move_generators, [], move_extenders, [])
        expected = [self.any_move, self.any_extended_move, self.any_other_extended_move1, self.any_other_extended_move2]

        # Act
        actual = list(move_wrapper.generate(self.any_diff))

        # Assert
        self.assertListEqual(expected, actual)

    def test_generate__different_move_extenders__different_extended_moves_returned(self):
        # Arrange
        move_generators = [self.single_move_generator]
        move_extenders = [self.single_move_extender, self.another_single_move_extender]
        move_wrapper = ps.MoveWrapper(move_generators, [], move_extenders, [])
        expected = [self.any_move, self.any_extended_move, self.any_other_extended_move1]

        # Act
        actual = list(move_wrapper.generate(self.any_diff))

        # Assert
        self.assertListEqual(expected, actual)

    def test_generate__duplicate_extended_moves__unique_moves_returned(self):
        # Arrange
        move_generators = [self.single_move_generator]
        move_extenders = [self.single_move_extender, self.single_move_extender]
        move_wrapper = ps.MoveWrapper(move_generators, [], move_extenders, [])
        expected = [self.any_move, self.any_extended_move]

        # Act
        actual = list(move_wrapper.generate(self.any_diff))

        # Assert
        self.assertListEqual(expected, actual)

    def test_generate__mixed_extended_moves__unique_moves_returned(self):
        # Arrange
        move_generators = [self.single_move_generator, self.another_single_move_generator]
        move_extenders = [self.mixed_move_extender]
        move_wrapper = ps.MoveWrapper(move_generators, [], move_extenders, [])
        expected = [self.any_move,
                    self.any_other_move1,
                    self.any_extended_move,
                    self.any_other_extended_move1,
                    self.any_other_extended_move2]

        # Act
        actual = list(move_wrapper.generate(self.any_diff))

        # Assert
        self.assertListEqual(expected, actual)

    def test_generate__multiple_non_extendable_moves__no_moves_extended(self):
        # Arrange
        move_non_extendable_generators = [self.single_move_generator, self.another_single_move_generator]
        move_extenders = [self.mixed_move_extender]
        move_wrapper = ps.MoveWrapper([], move_non_extendable_generators, move_extenders, [])
        expected = [self.any_move, self.any_other_move1]

        # Act
        actual = list(move_wrapper.generate(self.any_diff))

        # Assert
        self.assertListEqual(expected, actual)

    def test_generate__mixed_extendable_non_extendable_moves__only_extendable_moves_extended(self):
        # Arrange
        move_generators = [self.another_single_move_generator] # generates: any_other_move1, extends: any_other_extended_move1
        move_non_extendable_generators = [self.single_move_generator] # generates: any_move
        move_extenders = [self.mixed_move_extender]
        move_wrapper = ps.MoveWrapper(move_generators, move_non_extendable_generators, move_extenders, [])
        expected = [self.any_move,
                    self.any_other_move1,
                    self.any_other_extended_move1]

        # Act
        actual = list(move_wrapper.generate(self.any_diff))

        # Assert
        self.assertListEqual(expected, actual)

    def test_generate__move_is_extendable_and_non_extendable__move_is_extended(self):
        # Arrange
        move_generators = [self.single_move_generator]
        move_non_extendable_generators = [self.single_move_generator]
        move_extenders = [self.single_move_extender]
        move_wrapper = ps.MoveWrapper(move_generators, move_non_extendable_generators, move_extenders, [])
        expected = [self.any_move,
                    self.any_extended_move]

        # Act
        actual = list(move_wrapper.generate(self.any_diff))

        # Assert
        self.assertListEqual(expected, actual)

    def test_validate__validation_fail__false_returned(self):
        # Arrange
        move_validators = [self.fail_move_validator]
        move_wrapper = ps.MoveWrapper([], [], [], move_validators)

        # Act and assert
        self.assertFalse(move_wrapper.validate(self.any_move, self.any_diff))

    def test_validate__validation_succeed__true_returned(self):
        # Arrange
        move_validators = [self.success_move_validator]
        move_wrapper = ps.MoveWrapper([], [], [], move_validators)

        # Act and assert
        self.assertTrue(move_wrapper.validate(self.any_move, self.any_diff))

    def test_validate__multiple_validators_last_fail___false_returned(self):
        # Arrange
        move_validators = [self.success_move_validator, self.success_move_validator, self.fail_move_validator]
        move_wrapper = ps.MoveWrapper([], [], [], move_validators)

        # Act and assert
        self.assertFalse(move_wrapper.validate(self.any_move, self.any_diff))

    def test_validate__multiple_validators_succeed___true_returned(self):
        # Arrange
        move_validators = [self.success_move_validator, self.success_move_validator, self.success_move_validator]
        move_wrapper = ps.MoveWrapper([], [], [], move_validators)

        # Act and assert
        self.assertTrue(move_wrapper.validate(self.any_move, self.any_diff))

    def test_simulate__applies_move(self):
        # Arrange
        diff = Mock()
        diff.apply_move.side_effect = create_side_effect_dict({(str(self.any_move), ): self.any_diff})
        move_wrapper = ps.MoveWrapper(None, None, None, None)

        # Act
        actual = move_wrapper.simulate(self.any_move, diff)

        # Assert
        self.assertIs(self.any_diff, actual)

class TestJsonPointerFilter(unittest.TestCase):
    def test_get_paths__common_prefix__exact_match_returned(self):
        config = {
            "BUFFER_PG": {
                "Ethernet1|0": {},
                "Ethernet12|0": {},
                "Ethernet120|0": {},  # 'Ethernet12' is a common prefix with the previous line
            },
        }

        filter = ps.JsonPointerFilter([["BUFFER_PG", "Ethernet12|*"]], PathAddressing())

        expected_paths = ["/BUFFER_PG/Ethernet12|0"]

        actual_paths = list(filter.get_paths(config))

        self.assertCountEqual(expected_paths, actual_paths)

    def test_get_paths__common_suffix__exact_match_returned(self):
        config = {
            "QUEUE": {
                "Ethernet1|0": {},
                "Ethernet1|10": {},
                "Ethernet1|110": {}, # 10 is a common suffix with the previous line
            },
        }

        filter = ps.JsonPointerFilter([["QUEUE", "*|10"]], PathAddressing())

        expected_paths = ["/QUEUE/Ethernet1|10"]

        actual_paths = list(filter.get_paths(config))

        self.assertCountEqual(expected_paths, actual_paths)

class TestRequiredValueIdentifier(unittest.TestCase):
    def test_hard_coded_required_value_data(self):
        identifier = ps.RequiredValueIdentifier(PathAddressing())
        config = {
            "BUFFER_PG": {
                "Ethernet4|0": {
                    "profile": "ingress_lossy_profile"
                },
                "Ethernet8|3-4": {
                    "profile": "pg_lossless_40000_40m_profile"
                }
            },
            "BUFFER_QUEUE": {
                "Ethernet0|5-6": {
                    "profile": "egress_lossless_profile"
                },
                "Ethernet4|1": {
                    "profile": "egress_lossy_profile"
                }
            },
            "QUEUE": {
                "Ethernet4|2": {
                    "scheduler": "scheduler.0"
                },
                "Ethernet4|7-8": {
                    "scheduler": "scheduler.0"
                }
            },
            "BUFFER_PORT_INGRESS_PROFILE_LIST": {
                "Ethernet0": {
                    "profile_list": ["ingress_lossy_profile"]
                },
                "Ethernet4": {
                    "profile_list": ["ingress_lossy_profile"]
                },
            },
            "BUFFER_PORT_EGRESS_PROFILE_LIST": {
                "Ethernet4": {
                    "profile_list": ["egress_lossless_profile", "egress_lossy_profile"]
                },
                "Ethernet8": {
                    "profile_list": ["ingress_lossy_profile"]
                },
            },
            "PORT_QOS_MAP": {
                "Ethernet4": {
                    "dscp_to_tc_map": "AZURE",
                    "pfc_enable": "3,4",
                    "pfc_to_queue_map": "AZURE",
                    "tc_to_pg_map": "AZURE",
                    "tc_to_queue_map": "AZURE"
                },
                "Ethernet12": {
                    "dscp_to_tc_map": "AZURE",
                    "pfc_enable": "3,4",
                    "pfc_to_queue_map": "AZURE",
                    "tc_to_pg_map": "AZURE",
                    "tc_to_queue_map": "AZURE"
                },
            },
            "PORT": {
                "Ethernet4": {}
            }
        }
        expected = OrderedDict([
            ('/BUFFER_PG/Ethernet4|0', [('/PORT/Ethernet4/admin_status', 'down')]),
            ('/BUFFER_PORT_EGRESS_PROFILE_LIST/Ethernet4', [('/PORT/Ethernet4/admin_status', 'down')]),
            ('/BUFFER_PORT_INGRESS_PROFILE_LIST/Ethernet4', [('/PORT/Ethernet4/admin_status', 'down')]),
            ('/BUFFER_QUEUE/Ethernet4|1', [('/PORT/Ethernet4/admin_status', 'down')]),
            ('/PORT_QOS_MAP/Ethernet4', [('/PORT/Ethernet4/admin_status', 'down')]),
            ('/QUEUE/Ethernet4|2', [('/PORT/Ethernet4/admin_status', 'down')]),
            ('/QUEUE/Ethernet4|7-8', [('/PORT/Ethernet4/admin_status', 'down')]),
        ])

        actual = identifier.get_required_value_data([config])

        self.assertEqual(expected, actual)

class TestDeleteWholeConfigMoveValidator(unittest.TestCase):
    def setUp(self):
        self.operation_wrapper = OperationWrapper()
        self.validator = ps.DeleteWholeConfigMoveValidator()
        self.any_diff = Mock()
        self.any_non_whole_config_path = "/table1"
        self.whole_config_path = ""

    def test_validate__non_remove_op_non_whole_config__success(self):
        self.verify(OperationType.REPLACE, self.any_non_whole_config_path, True)
        self.verify(OperationType.ADD, self.any_non_whole_config_path, True)

    def test_validate__remove_op_non_whole_config__success(self):
        self.verify(OperationType.REMOVE, self.any_non_whole_config_path, True)

    def test_validate__non_remove_op_whole_config__success(self):
        self.verify(OperationType.REPLACE, self.whole_config_path, True)
        self.verify(OperationType.ADD, self.whole_config_path, True)

    def test_validate__remove_op_whole_config__failure(self):
        self.verify(OperationType.REMOVE, self.whole_config_path, False)

    def verify(self, operation_type, path, expected):
        # Arrange
        value = None
        if operation_type in [OperationType.ADD, OperationType.REPLACE]:
            value = Mock()

        operation = self.operation_wrapper.create(operation_type, path, value)
        move = ps.JsonMove.from_operation(operation)

        # Act
        actual = self.validator.validate(move, self.any_diff)

        # Assert
        self.assertEqual(expected, actual)

class TestFullConfigMoveValidator(unittest.TestCase):
    def setUp(self):
        self.any_current_config = Mock()
        self.any_target_config = Mock()
        self.any_simulated_config = Mock()
        self.any_diff = ps.Diff(self.any_current_config, self.any_target_config)
        self.any_move = Mock()
        self.any_move.apply.side_effect = \
            create_side_effect_dict({(str(self.any_current_config),): self.any_simulated_config})

    def test_validate__invalid_config_db_after_applying_move__failure(self):
        # Arrange
        config_wrapper = Mock()
        config_wrapper.validate_config_db_config.side_effect = \
            create_side_effect_dict({(str(self.any_simulated_config),): (False, None)})
        validator = ps.FullConfigMoveValidator(config_wrapper)

        # Act and assert
        self.assertFalse(validator.validate(self.any_move, self.any_diff))

    def test_validate__valid_config_db_after_applying_move__success(self):
        # Arrange
        config_wrapper = Mock()
        config_wrapper.validate_config_db_config.side_effect = \
            create_side_effect_dict({(str(self.any_simulated_config),): (True, None)})
        validator = ps.FullConfigMoveValidator(config_wrapper)

        # Act and assert
        self.assertTrue(validator.validate(self.any_move, self.any_diff))

class TestCreateOnlyMoveValidator(unittest.TestCase):
    def setUp(self):
        self.validator = ps.CreateOnlyMoveValidator(ps.PathAddressing())
        self.any_diff = ps.Diff({}, {})

    def test_validate__no_create_only_field__success(self):
        current_config = {"PORT": {}}
        target_config = {"PORT": {}, "ACL_TABLE": {}}
        self.verify_diff(current_config, target_config)

    def test_validate__same_create_only_field__success(self):
        current_config = {"PORT": {"Ethernet0":{"lanes":"65"}}}
        target_config = {"PORT": {"Ethernet0":{"lanes":"65"}}, "ACL_TABLE": {}}
        self.verify_diff(current_config, target_config)

    def test_validate__different_create_only_field__failure(self):
        current_config = {"PORT": {"Ethernet0":{"lanes":"65"}}}
        target_config = {"PORT": {"Ethernet0":{"lanes":"66"}}, "ACL_TABLE": {}}
        self.verify_diff(current_config, target_config, expected=False)

    def test_validate__different_create_only_field_directly_updated__failure(self):
        current_config = {"PORT": {"Ethernet0":{"lanes":"65"}}}
        target_config = {"PORT": {"Ethernet0":{"lanes":"66"}}, "ACL_TABLE": {}}
        self.verify_diff(current_config,
                         target_config,
                         ["PORT", "Ethernet0", "lanes"],
                         ["PORT", "Ethernet0", "lanes"],
                         False)

    def test_validate__different_create_only_field_updating_parent__failure(self):
        current_config = {"PORT": {"Ethernet0":{"lanes":"65"}}}
        target_config = {"PORT": {"Ethernet0":{"lanes":"66"}}, "ACL_TABLE": {}}
        self.verify_diff(current_config,
                         target_config,
                         ["PORT", "Ethernet0"],
                         ["PORT", "Ethernet0"],
                         False)

    def test_validate__different_create_only_field_updating_grandparent__failure(self):
        current_config = {"PORT": {"Ethernet0":{"lanes":"65"}}}
        target_config = {"PORT": {"Ethernet0":{"lanes":"66"}}, "ACL_TABLE": {}}
        self.verify_diff(current_config,
                         target_config,
                         ["PORT"],
                         ["PORT"],
                         False)

    def test_validate__same_create_only_field_directly_updated__success(self):
        current_config = {"PORT": {"Ethernet0":{"lanes":"65"}}}
        target_config = {"PORT": {"Ethernet0":{"lanes":"65"}}, "ACL_TABLE": {}}
        self.verify_diff(current_config,
                         target_config,
                         ["PORT", "Ethernet0", "lanes"],
                         ["PORT", "Ethernet0", "lanes"])

    def test_validate__same_create_only_field_updating_parent__success(self):
        current_config = {"PORT": {"Ethernet0":{"lanes":"65"}}}
        target_config = {"PORT": {"Ethernet0":{"lanes":"65"}}, "ACL_TABLE": {}}
        self.verify_diff(current_config,
                         target_config,
                         ["PORT", "Ethernet0"],
                         ["PORT", "Ethernet0"])

    def test_validate__same_create_only_field_updating_grandparent__success(self):
        current_config = {"PORT": {"Ethernet0":{"lanes":"65"}}}
        target_config = {"PORT": {"Ethernet0":{"lanes":"65"}}, "ACL_TABLE": {}}
        self.verify_diff(current_config,
                         target_config,
                         ["PORT"],
                         ["PORT"])

    def test_validate__added_create_only_field_parent_exist__failure(self):
        current_config = {"PORT": {"Ethernet0":{}}}
        target_config = {"PORT": {"Ethernet0":{"lanes":"65"}}, "ACL_TABLE": {}}
        self.verify_diff(current_config,
                         target_config,
                         ["PORT"],
                         ["PORT"],
                         expected=False)

    def test_validate__added_create_only_field_parent_doesnot_exist__success(self):
        current_config = {"PORT": {}}
        target_config = {"PORT": {"Ethernet0":{"lanes":"65"}}, "ACL_TABLE": {}}
        self.verify_diff(current_config,
                         target_config,
                         ["PORT"],
                         ["PORT"])

    def test_validate__removed_create_only_field_parent_remain__failure(self):
        current_config = {"PORT": {"Ethernet0":{"lanes":"65"}}, "ACL_TABLE": {}}
        target_config = {"PORT": {"Ethernet0":{}}}
        self.verify_diff(current_config,
                         target_config,
                         ["PORT"],
                         ["PORT"],
                         expected=False)

    def test_validate__removed_create_only_field_parent_doesnot_remain__success(self):
        current_config = {"PORT": {"Ethernet0":{"lanes":"65"}}, "ACL_TABLE": {}}
        target_config = {"PORT": {}}
        self.verify_diff(current_config,
                         target_config,
                         ["PORT"],
                         ["PORT"])

    def test_validate__parent_added_with_all_create_only_field_that_target_has__success(self):
        added_parent_value = {
            "admin_status": "up",
            "asn": "64600", # <== create-only field
            "holdtime": "50", # <== create-only field
        }
        self.verify_parent_adding(added_parent_value, True)

    def test_validate__parent_added_with_create_only_field_but_target_does_not_have_the_field__failure(self):
        added_parent_value = {
            "admin_status": "up",
            "asn": "64600", # <== create-only field
            "holdtime": "50", # <== create-only field
            "rrclient": "1", # <== create-only field but not in target-config
        }
        self.verify_parent_adding(added_parent_value, False)

    def test_validate__parent_added_without_create_only_field_but_target_have_the_field__failure(self):
        added_parent_value = {
            "admin_status": "up",
            "asn": "64600", # <== create-only field
            # Not adding: "holdtime": "50"
        }
        self.verify_parent_adding(added_parent_value, False)

    def test_hard_coded_create_only_paths(self):
        config = {
            "PORT": {
                "Ethernet0":{"lanes":"65"},
                "Ethernet1":{},
                "Ethernet2":{"lanes":"66,67"}
            },
            "LOOPBACK_INTERFACE": {
                "Loopback0":{"vrf_name":"vrf0"},
                "Loopback1":{},
                "Loopback2":{"vrf_name":"vrf1"},
            },
            "BGP_NEIGHBOR": {
                "10.0.0.57": {
                    "admin_status": "up",
                    "asn": "64600",
                    "holdtime": "10",
                    "keepalive": "3",
                    "local_addr": "10.0.0.56",
                    "name": "ARISTA01T1",
                    "nhopself": "0",
                    "rrclient": "0"
                }
            },
            "BGP_PEER_RANGE": {
                "BGPSLBPassive": {
                    "ip_range": [
                        "10.255.0.0/25"
                    ],
                    "name": "BGPSLBPassive",
                    "peer_asn": "65543",
                    "src_address": "10.1.0.32"
                }
            },
            "BGP_SENTINELS": {
                "BGPSentinelV6": {
                    "ip_range": [
                        "2603:10a0:321:82f9::/64",
                        "2603:10a1:30a:8000::/59"
                    ],
                    "name": "BGPSentinelV6",
                    "src_address": "fc00:1::32"
                },
                "BGPSentinel": {
                    "ip_range": [
                        "10.1.0.0/24"
                    ],
                    "name": "BGPSentinel",
                    "src_address": "10.1.0.32"
                }
            },
            "BGP_MONITORS": {
                "5.6.7.8": {
                    "admin_status": "up",
                    "asn": "65000",
                    "holdtime": "180",
                    "keepalive": "60",
                    "local_addr": "10.0.0.11",
                    "name": "BGPMonitor",
                    "nhopself": "0",
                    "rrclient": "0"
                }
            },
            "MIRROR_SESSION": {
                "mirror_session_dscp": {
                    "dscp": "5",
                    "dst_ip": "2.2.2.2",
                    "src_ip": "1.1.1.1",
                    "ttl": "32",
                    "type": "ERSPAN"
                }
            },
            "VLAN_SUB_INTERFACE": {
                "Ethernet0.10": {
                    "vlan": 10,
                    "vnet_name": "Vnet1"
                }
            },
            "VLAN_INTERFACE": {
                "Vlan100": {
                    "vnet_name": "Vnet2"
                }
            },
            "INTERFACE": {
                "Ethernet2": {
                    "vnet_name": "Vnet3"
                }
            }
        }
        expected = [
            "/PORT/Ethernet0/lanes",
            "/PORT/Ethernet2/lanes",
            "/LOOPBACK_INTERFACE/Loopback0/vrf_name",
            "/LOOPBACK_INTERFACE/Loopback2/vrf_name",
            "/BGP_NEIGHBOR/10.0.0.57/asn",
            "/BGP_NEIGHBOR/10.0.0.57/holdtime",
            "/BGP_NEIGHBOR/10.0.0.57/keepalive",
            "/BGP_NEIGHBOR/10.0.0.57/local_addr",
            "/BGP_NEIGHBOR/10.0.0.57/name",
            "/BGP_NEIGHBOR/10.0.0.57/nhopself",
            "/BGP_NEIGHBOR/10.0.0.57/rrclient",
            "/BGP_PEER_RANGE/BGPSLBPassive/ip_range",
            "/BGP_PEER_RANGE/BGPSLBPassive/name",
            "/BGP_PEER_RANGE/BGPSLBPassive/peer_asn",
            "/BGP_PEER_RANGE/BGPSLBPassive/src_address",
            "/BGP_SENTINELS/BGPSentinelV6/ip_range",
            "/BGP_SENTINELS/BGPSentinelV6/name",
            "/BGP_SENTINELS/BGPSentinelV6/src_address",
            "/BGP_SENTINELS/BGPSentinel/ip_range",
            "/BGP_SENTINELS/BGPSentinel/name",
            "/BGP_SENTINELS/BGPSentinel/src_address",
            "/BGP_MONITORS/5.6.7.8/asn",
            "/BGP_MONITORS/5.6.7.8/holdtime",
            "/BGP_MONITORS/5.6.7.8/keepalive",
            "/BGP_MONITORS/5.6.7.8/local_addr",
            "/BGP_MONITORS/5.6.7.8/name",
            "/BGP_MONITORS/5.6.7.8/nhopself",
            "/BGP_MONITORS/5.6.7.8/rrclient",
            "/MIRROR_SESSION/mirror_session_dscp/dscp",
            "/MIRROR_SESSION/mirror_session_dscp/dst_ip",
            "/MIRROR_SESSION/mirror_session_dscp/src_ip",
            "/MIRROR_SESSION/mirror_session_dscp/ttl",
            "/MIRROR_SESSION/mirror_session_dscp/type",
            "/VLAN_SUB_INTERFACE/Ethernet0.10/vnet_name",
            "/VLAN_INTERFACE/Vlan100/vnet_name",
            "/INTERFACE/Ethernet2/vnet_name",
        ]

        actual = self.validator._get_create_only_paths(config)

        self.assertCountEqual(expected, actual)

    def verify_parent_adding(self, added_parent_value, expected):
        current_config = {
            "BGP_NEIGHBOR": {}
        }

        target_config = {
            "BGP_NEIGHBOR": {
                "10.0.0.57": {
                    "admin_status": "up",
                    "asn": "64600",
                    "holdtime": "50",
                }
            }
        }
        diff = ps.Diff(current_config, target_config)
        move = ps.JsonMove.from_operation({"op":"add", "path":"/BGP_NEIGHBOR/10.0.0.57", "value": added_parent_value})

        actual = self.validator.validate(move, diff)

        self.assertEqual(expected, actual)

    def verify_diff(self, current_config, target_config, current_config_tokens=None, target_config_tokens=None, expected=True):
        # Arrange
        current_config_tokens = current_config_tokens if current_config_tokens else []
        target_config_tokens = target_config_tokens if target_config_tokens else []
        diff = ps.Diff(current_config, target_config)
        move = ps.JsonMove(diff, OperationType.REPLACE, current_config_tokens, target_config_tokens)

        # Act
        actual = self.validator.validate(move, diff)

        # Assert
        self.assertEqual(expected, actual)

class TestNoDependencyMoveValidator(unittest.TestCase):
    def setUp(self):
        config_wrapper = ConfigWrapper()
        path_addressing = ps.PathAddressing(config_wrapper)
        self.validator = ps.NoDependencyMoveValidator(path_addressing, config_wrapper)

    def test_validate__add_full_config_has_dependencies__failure(self):
        # Arrange
        # CROPPED_CONFIG_DB_AS_JSON has dependencies between PORT and ACL_TABLE
        diff = ps.Diff(Files.EMPTY_CONFIG_DB, Files.CROPPED_CONFIG_DB_AS_JSON)
        move = ps.JsonMove(diff, OperationType.ADD, [], [])

        # Act and assert
        self.assertFalse(self.validator.validate(move, diff))

    def test_validate__add_full_config_no_dependencies__success(self):
        # Arrange
        diff = ps.Diff(Files.EMPTY_CONFIG_DB, Files.CONFIG_DB_NO_DEPENDENCIES)
        move = ps.JsonMove(diff, OperationType.ADD, [], [])

        # Act and assert
        self.assertTrue(self.validator.validate(move, diff))

    def test_validate__add_table_has_no_dependencies__success(self):
        # Arrange
        target_config = Files.CROPPED_CONFIG_DB_AS_JSON
        # prepare current config by removing ACL_TABLE from current config
        current_config = self.prepare_config(target_config, jsonpatch.JsonPatch([
            {"op": "remove", "path":"/ACL_TABLE"}
        ]))
        diff = ps.Diff(current_config, target_config)
        move = ps.JsonMove(diff, OperationType.ADD, ["ACL_TABLE"], ["ACL_TABLE"])

        # Act and assert
        self.assertTrue(self.validator.validate(move, diff))

    def test_validate__remove_full_config_has_dependencies__failure(self):
        # Arrange
        # CROPPED_CONFIG_DB_AS_JSON has dependencies between PORT and ACL_TABLE
        diff = ps.Diff(Files.CROPPED_CONFIG_DB_AS_JSON, Files.EMPTY_CONFIG_DB)
        move = ps.JsonMove(diff, OperationType.REMOVE, [], [])

        # Act and assert
        self.assertFalse(self.validator.validate(move, diff))

    def test_validate__remove_full_config_no_dependencies__success(self):
        # Arrange
        diff = ps.Diff(Files.EMPTY_CONFIG_DB, Files.CONFIG_DB_NO_DEPENDENCIES)
        move = ps.JsonMove(diff, OperationType.REMOVE, [], [])

        # Act and assert
        self.assertTrue(self.validator.validate(move, diff))

    def test_validate__remove_table_has_no_dependencies__success(self):
        # Arrange
        current_config = Files.CROPPED_CONFIG_DB_AS_JSON
        target_config = self.prepare_config(current_config, jsonpatch.JsonPatch([
            {"op": "remove", "path":"/ACL_TABLE"}
        ]))
        diff = ps.Diff(current_config, target_config)
        move = ps.JsonMove(diff, OperationType.REMOVE, ["ACL_TABLE"])

        # Act and assert
        self.assertTrue(self.validator.validate(move, diff))

    def test_validate__replace_whole_config_item_added_ref_added__failure(self):
        # Arrange
        target_config = Files.SIMPLE_CONFIG_DB_INC_DEPS
        # prepare current config by removing an item and its ref from target config
        current_config = self.prepare_config(target_config, jsonpatch.JsonPatch([
            {"op": "replace", "path":"/ACL_TABLE/EVERFLOW/ports/0", "value":""},
            {"op": "remove", "path":"/PORT/Ethernet0"}
        ]))

        diff = ps.Diff(current_config, target_config)
        move = ps.JsonMove(diff, OperationType.REPLACE, [], [])

        # Act and assert
        self.assertFalse(self.validator.validate(move, diff))

    def test_validate__replace_whole_config_item_removed_ref_removed__false(self):
        # Arrange
        current_config = Files.SIMPLE_CONFIG_DB_INC_DEPS
        # prepare target config by removing an item and its ref from current config
        target_config = self.prepare_config(current_config, jsonpatch.JsonPatch([
            {"op": "replace", "path":"/ACL_TABLE/EVERFLOW/ports/0", "value":""},
            {"op": "remove", "path":"/PORT/Ethernet0"}
        ]))

        diff = ps.Diff(current_config, target_config)
        move = ps.JsonMove(diff, OperationType.REPLACE, [], [])

        # Act and assert
        self.assertFalse(self.validator.validate(move, diff))

    def test_validate__replace_whole_config_item_same_ref_added__true(self):
        # Arrange
        target_config = Files.SIMPLE_CONFIG_DB_INC_DEPS
        # prepare current config by removing ref from target config
        current_config = self.prepare_config(target_config, jsonpatch.JsonPatch([
            {"op": "replace", "path":"/ACL_TABLE/EVERFLOW/ports/0", "value":""}
        ]))

        diff = ps.Diff(current_config, target_config)
        move = ps.JsonMove(diff, OperationType.REPLACE, [], [])

        # Act and assert
        self.assertTrue(self.validator.validate(move, diff))

    def test_validate__replace_whole_config_item_same_ref_removed__true(self):
        # Arrange
        current_config= Files.SIMPLE_CONFIG_DB_INC_DEPS
        # prepare target config by removing ref from current config
        target_config = self.prepare_config(current_config, jsonpatch.JsonPatch([
            {"op": "replace", "path":"/ACL_TABLE/EVERFLOW/ports/0", "value":""}
        ]))

        diff = ps.Diff(current_config, target_config)
        move = ps.JsonMove(diff, OperationType.REPLACE, [], [])

        # Act and assert
        self.assertTrue(self.validator.validate(move, diff))

    def test_validate__replace_whole_config_item_same_ref_same__true(self):
        # Arrange
        current_config= Files.SIMPLE_CONFIG_DB_INC_DEPS
        # prepare target config by removing ref from current config
        target_config = current_config

        diff = ps.Diff(current_config, target_config)
        move = ps.JsonMove(diff, OperationType.REPLACE, [], [])

        # Act and assert
        self.assertTrue(self.validator.validate(move, diff))

    def test_validate__replace_list_item_different_location_than_target_and_no_deps__true(self):
        # Arrange
        current_config = {
            "VLAN": {
                "Vlan100": {
                    "vlanid": "100",
                    "dhcp_servers": [
                        "192.0.0.1",
                        "192.0.0.2"
                    ]
                }
            }
        }
        target_config = {
            "VLAN": {
                "Vlan100": {
                    "vlanid": "100",
                    "dhcp_servers": [
                        "192.0.0.3"
                    ]
                }
            }
        }
        diff = ps.Diff(current_config, target_config)
        # the target tokens point to location 0 which exist in target_config
        # but the replace operation is operating on location 1 in current_config
        move = ps.JsonMove(diff, OperationType.REPLACE, ["VLAN", "Vlan100", "dhcp_servers", 1], ["VLAN", "Vlan100", "dhcp_servers", 0])

        # Act and assert
        self.assertTrue(self.validator.validate(move, diff))

    def prepare_config(self, config, patch):
        return patch.apply(config)

class TestNoEmptyTableMoveValidator(unittest.TestCase):
    def setUp(self):
        path_addressing = ps.PathAddressing()
        self.validator = ps.NoEmptyTableMoveValidator(path_addressing)

    def test_validate__no_changes__success(self):
        # Arrange
        current_config = {"some_table":{"key1":"value1", "key2":"value2"}}
        target_config = {"some_table":{"key1":"value1", "key2":"value22"}}
        diff = ps.Diff(current_config, target_config)
        move = ps.JsonMove(diff, OperationType.REPLACE, ["some_table", "key1"], ["some_table", "key1"])

        # Act and assert
        self.assertTrue(self.validator.validate(move, diff))

    def test_validate__change_but_no_empty_table__success(self):
        # Arrange
        current_config = {"some_table":{"key1":"value1", "key2":"value2"}}
        target_config = {"some_table":{"key1":"value1", "key2":"value22"}}
        diff = ps.Diff(current_config, target_config)
        move = ps.JsonMove(diff, OperationType.REPLACE, ["some_table", "key2"], ["some_table", "key2"])

        # Act and assert
        self.assertTrue(self.validator.validate(move, diff))

    def test_validate__single_empty_table__failure(self):
        # Arrange
        current_config = {"some_table":{"key1":"value1", "key2":"value2"}}
        target_config = {"some_table":{}}
        diff = ps.Diff(current_config, target_config)
        move = ps.JsonMove(diff, OperationType.REPLACE, ["some_table"], ["some_table"])

        # Act and assert
        self.assertFalse(self.validator.validate(move, diff))

    def test_validate__whole_config_replace_single_empty_table__failure(self):
        # Arrange
        current_config = {"some_table":{"key1":"value1", "key2":"value2"}}
        target_config = {"some_table":{}}
        diff = ps.Diff(current_config, target_config)
        move = ps.JsonMove(diff, OperationType.REPLACE, [], [])

        # Act and assert
        self.assertFalse(self.validator.validate(move, diff))

    def test_validate__whole_config_replace_mix_of_empty_and_non_empty__failure(self):
        # Arrange
        current_config = {"some_table":{"key1":"value1"}, "other_table":{"key2":"value2"}}
        target_config = {"some_table":{"key1":"value1"}, "other_table":{}}
        diff = ps.Diff(current_config, target_config)
        move = ps.JsonMove(diff, OperationType.REPLACE, [], [])

        # Act and assert
        self.assertFalse(self.validator.validate(move, diff))

    def test_validate__whole_config_multiple_empty_tables__failure(self):
        # Arrange
        current_config = {"some_table":{"key1":"value1"}, "other_table":{"key2":"value2"}}
        target_config = {"some_table":{}, "other_table":{}}
        diff = ps.Diff(current_config, target_config)
        move = ps.JsonMove(diff, OperationType.REPLACE, [], [])

        # Act and assert
        self.assertFalse(self.validator.validate(move, diff))

    def test_validate__remove_key_empties_a_table__failure(self):
        # Arrange
        current_config = {"some_table":{"key1":"value1"}, "other_table":{"key2":"value2"}}
        target_config = {"some_table":{"key1":"value1"}, "other_table":{}}
        diff = ps.Diff(current_config, target_config)
        move = ps.JsonMove(diff, OperationType.REMOVE, ["other_table", "key2"], [])

        # Act and assert
        self.assertFalse(self.validator.validate(move, diff))

    def test_validate__remove_key_but_table_has_other_keys__success(self):
        # Arrange
        current_config = {"some_table":{"key1":"value1"}, "other_table":{"key2":"value2", "key3":"value3"}}
        target_config = {"some_table":{"key1":"value1"}, "other_table":{"key3":"value3"}}
        diff = ps.Diff(current_config, target_config)
        move = ps.JsonMove(diff, OperationType.REMOVE, ["other_table", "key2"], [])

        # Act and assert
        self.assertTrue(self.validator.validate(move, diff))

    def test_validate__remove_whole_table__success(self):
        # Arrange
        current_config = {"some_table":{"key1":"value1"}, "other_table":{"key2":"value2"}}
        target_config = {"some_table":{"key1":"value1"}}
        diff = ps.Diff(current_config, target_config)
        move = ps.JsonMove(diff, OperationType.REMOVE, ["other_table"], [])

        # Act and assert
        self.assertTrue(self.validator.validate(move, diff))

    def test_validate__add_empty_table__failure(self):
        # Arrange
        current_config = {"some_table":{"key1":"value1"}, "other_table":{"key2":"value2"}}
        target_config = {"new_table":{}}
        diff = ps.Diff(current_config, target_config)
        move = ps.JsonMove(diff, OperationType.ADD, ["new_table"], ["new_table"])

        # Act and assert
        self.assertFalse(self.validator.validate(move, diff))

    def test_validate__add_non_empty_table__success(self):
        # Arrange
        current_config = {"some_table":{"key1":"value1"}, "other_table":{"key2":"value2"}}
        target_config = {"new_table":{"key3":"value3"}}
        diff = ps.Diff(current_config, target_config)
        move = ps.JsonMove(diff, OperationType.ADD, ["new_table"], ["new_table"])

        # Act and assert
        self.assertTrue(self.validator.validate(move, diff))

class TestRequiredValueMoveValidator(unittest.TestCase):
    def setUp(self):
        self.operation_wrapper = OperationWrapper()
        path_addressing = PathAddressing()
        self.validator = ps.RequiredValueMoveValidator(path_addressing)
        self.validator.identifier.settings[0]["requiring_filter"] = ps.JsonPointerFilter([
                ["BUFFER_PG", "@|*"],
                ["PORT", "@", "mtu"]
            ],
            path_addressing)

    def test_validate__critical_port_change(self):
        # Each test format:
        #   "<test-name>": {
        #       "expected": "<True|False>",
        #       "config": <config>,
        #       "move": <move>,
        #       "target_config": <OPTIONAL> <target-config-if-different-than-applying-move-to-config>
        #   }
        # Each test is testing different flag of:
        #  - port-up: if port is up or not in current_config
        #  - status-changing: if admin_status is changing from any state to another
        #  - under-port: if the port-critical config is under port
        #  - port-exist: if the port already exist in current_config
        test_cases = self._get_critical_port_change_test_cases()
        for test_case_name in test_cases:
            with self.subTest(name=test_case_name):
                self._run_single_test(test_cases[test_case_name])

    def _run_single_test(self, test_case):
        # Arrange
        expected = test_case['expected']
        current_config = test_case['config']
        move = test_case['move']
        target_config = test_case.get('target_config', move.apply(current_config))
        diff = ps.Diff(current_config, target_config)

        # Act and Assert
        self.assertEqual(expected, self.validator.validate(move, diff))

    def _get_critical_port_change_test_cases(self):
        # port-up  status-changing  under-port  port-exist  verdict
        # 1        1                1           1           0
        # 1        1                1           0           invalid - port cannot be up while it does not exist
        # 1        1                0           1           0
        # 1        1                0           0           invalid - port cannot be up while it does not exist
        # 1        0                1           1           0
        # 1        0                1           0           invalid - port cannot be up while it does not exist
        # 1        0                0           1           0
        # 1        0                0           0           invalid - port cannot be up while it does not exist
        # 0        1                1           1           0
        # 0        1                1           0           0    can be 1?
        # 0        1                0           1           0
        # 0        1                0           0           0
        # 0        0                1           1           1
        # 0        0                1           0           1
        # 0        0                0           1           1
        # 0        0                0           0           invalid - port does not exist anyway
        return {
            "PORT_UP__STATUS_CHANGING__UNDER_PORT__PORT_EXIST": {
                "expected": False,
                "config": Files.CONFIG_DB_WITH_PORT_CRITICAL,
                "move": ps.JsonMove.from_operation({
                    "op": "replace",
                    "path": "/PORT/Ethernet4",
                    "value": { # only admin_status and mtu are different
                        "admin_status": "down", # <== status changing
                        "alias": "fortyGigE0/4",
                        "description": "Servers0:eth0",
                        "index": "1",
                        "lanes": "29,30,31,32",
                        "mtu": "9000", # <== critical config under port
                        "pfc_asym": "off",
                        "speed": "40000"
                    }
                })
            },
            # cannot test "port-up, status-changing, under-port, not port-exist"
            #   because if port does not exist, it cannot be admin up
            "PORT_UP__STATUS_CHANGING__NOT_UNDER_PORT__PORT_EXIST": {
                "expected": False,
                "config": Files.CONFIG_DB_WITH_PORT_CRITICAL,
                "move": ps.JsonMove.from_operation({
                    "op": "replace",
                    "path": "",
                    "value": self._apply_operations(Files.CONFIG_DB_WITH_PORT_CRITICAL,
                            [
                                # status-changing
                                {"op":"replace", "path":"/PORT/Ethernet4/admin_status", "value": "down"},
                                # port-critical config is not under port
                                {"op":"replace", "path":"/BUFFER_PG/Ethernet4|0/profile", "value": "egress_lossy_profile"},
                            ])
                })
            },
            # cannot test "port-up, status-changing, not under-port, not port-exist"
            #   because if port does not exist, it cannot be admin up
            "PORT_UP__NOT_STATUS_CHANGING__UNDER_PORT__PORT_EXIST": {
                "expected": False,
                "config": Files.CONFIG_DB_WITH_PORT_CRITICAL,
                "move": ps.JsonMove.from_operation({
                    "op": "replace",
                    "path": "/PORT/Ethernet4/mtu",
                    "value": "9000"
                })
            },
            # cannot test "port-up, not status-changing, under-port, not port-exist"
            #   because if port does not exist, it cannot be admin up
            "PORT_UP__NOT_STATUS_CHANGING__NOT_UNDER_PORT__PORT_EXIST": {
                "expected": False,
                "config": Files.CONFIG_DB_WITH_PORT_CRITICAL,
                "move": ps.JsonMove.from_operation({
                    "op":"replace",
                    "path":"/BUFFER_PG/Ethernet4|0/profile",
                    "value": "egress_lossy_profile"
                })
            },
            # cannot test "port-up, not status-changing, not under-port, not port-exist"
            #   because if port does not exist, it cannot be admin up
            "NOT_PORT_UP__STATUS_CHANGING__UNDER_PORT__PORT_EXIST": {
                "expected": False,
                "config": Files.CONFIG_DB_WITH_PORT_CRITICAL,
                "move": ps.JsonMove.from_operation({
                    "op": "add",
                    "path": "/PORT/Ethernet12",
                    "value": {
                        "admin_status": "up", # <== status changing
                        "alias": "fortyGigE0/12",
                        "description": "Servers2:eth0",
                        "index": "3",
                        "lanes": "37,38,39,40",
                        "mtu": "9000", # <== critical config under port
                        "pfc_asym": "off",
                        "speed": "40000"
                    }
                })
            },
            "NOT_PORT_UP__STATUS_CHANGING__UNDER_PORT__NOT_PORT_EXIST": {
                "expected": False,
                "config": Files.CONFIG_DB_WITH_PORT_CRITICAL,
                "move": ps.JsonMove.from_operation({
                    "op": "add",
                    "path": "/PORT/Ethernet20",
                    "value": {
                        "admin_status": "up", # <== status-changing from not-existing i.e "down" to "up"
                        "alias": "fortyGigE0/20",
                        "description": "Servers4:eth0",
                        "index": "5",
                        "mtu": "9100",  # <== critical config under port
                        "lanes": "45,46,47,48",
                        "pfc_asym": "off",
                        "speed": "40000"
                    }
                })
            },
            "NOT_PORT_UP__STATUS_CHANGING__NOT_UNDER_PORT__PORT_EXIST": {
                "expected": False,
                "config": Files.CONFIG_DB_WITH_PORT_CRITICAL,
                "move": ps.JsonMove.from_operation({
                    "op": "replace",
                    "path": "",
                    "value": self._apply_operations(Files.CONFIG_DB_WITH_PORT_CRITICAL,
                        [
                            # status-changing
                            {"op":"replace", "path":"/PORT/Ethernet12/admin_status", "value": "up"},
                            # port-critical config is not under port
                            {"op":"replace", "path":"/BUFFER_PG/Ethernet4|0/profile", "value": "egress_lossy_profile"},
                        ]
                    )
                })
            },
            "NOT_PORT_UP__STATUS_CHANGING__NOT_UNDER_PORT__NOT_PORT_EXIST": {
                "expected": False,
                "config": Files.CONFIG_DB_WITH_PORT_CRITICAL,
                "move": ps.JsonMove.from_operation({
                    "op": "replace",
                    "path": "",
                    "value": self._apply_operations(Files.CONFIG_DB_WITH_PORT_CRITICAL,
                        [
                            # status-changing
                            {
                                "op":"add",
                                "path":"/PORT/Ethernet20",
                                "value": {
                                    "admin_status": "up", # <== status-changing from not-existing i.e. "down" to "up"
                                    "alias": "fortyGigE0/20",
                                    "description": "Servers4:eth0",
                                    "index": "5",
                                    "lanes": "45,46,47,48",
                                    "pfc_asym": "off",
                                    "speed": "40000"
                                }
                            },
                            # port-critical config is not under port
                            {
                                "op":"add",
                                "path":"/BUFFER_PG/Ethernet20|0",
                                "value": {
                                    "profile": "ingress_lossy_profile"
                                }
                            },
                        ]
                    )
                })
            },
            "NOT_PORT_UP__NOT_STATUS_CHANGING__UNDER_PORT__PORT_EXIST": {
                "expected": True,
                "config": Files.CONFIG_DB_WITH_PORT_CRITICAL,
                "move": ps.JsonMove.from_operation({
                    "op": "replace",
                    "path": "/PORT/Ethernet12/mtu",
                    "value": "9000"
                })
            },
            "NOT_PORT_UP__NOT_STATUS_CHANGING__UNDER_PORT__NOT_PORT_EXIST": {
                "expected": True,
                "config": Files.CONFIG_DB_WITH_PORT_CRITICAL,
                "move": ps.JsonMove.from_operation({
                    "op": "add",
                    "path": "/PORT/Ethernet20",
                    "value": {
                        "alias": "fortyGigE0/20",
                        "description": "Servers4:eth0",
                        "index": "5",
                        "mtu": "9100",  # <== critical config under port
                        "lanes": "45,46,47,48",
                        "pfc_asym": "off",
                        "speed": "40000"
                    }
                })
            },
            "NOT_PORT_UP__NOT_STATUS_CHANGING__NOT_UNDER_PORT__PORT_EXIST": {
                "expected": True,
                "config": Files.CONFIG_DB_WITH_PORT_CRITICAL,
                "move": ps.JsonMove.from_operation({
                    "op":"replace",
                    "path":"/BUFFER_PG/Ethernet12|0/profile",
                    "value": "egress_lossy_profile"
                })
            },
            # cannot test "not port-up, not status-changing, not under-port, not port-exist"
            #   because if port does not exist, it cannot be admin up

            # The following set of cases check validation failure when a move is turning a port admin up, while still
            # some critical changes not included at all in the move
            "NOT_PORT_UP__STATUS_CHANGING__UNDER_PORT__PORT_EXIST__NOT_ALL_CRITICAL_CHANGES_INCLUDED": {
                "expected": False,
                "config": Files.CONFIG_DB_WITH_PORT_CRITICAL,
                "target_config": self._apply_operations(Files.CONFIG_DB_WITH_PORT_CRITICAL,
                    [
                        # The following critical change is not part of the move below.
                        {"op": "replace", "path": "/PORT/Ethernet12/mtu", "value": "9000"}
                    ]),
                "move": ps.JsonMove.from_operation({"op":"replace", "path":"/PORT/Ethernet12/admin_status", "value": "up"})
            },
            "NOT_PORT_UP__STATUS_CHANGING__UNDER_PORT__NOT_PORT_EXIST__NOT_ALL_CRITICAL_CHANGES_INCLUDED": {
                "expected": False,
                "config": Files.CONFIG_DB_WITH_PORT_CRITICAL,
                "target_config": self._apply_operations(Files.CONFIG_DB_WITH_PORT_CRITICAL,
                    [
                        {
                            "op": "add",
                            "path": "/PORT/Ethernet20",
                            "value": {
                                "admin_status": "up", # <== status-changing from not-existing i.e "down" to "up"
                                "alias": "fortyGigE0/20",
                                "description": "Servers4:eth0",
                                "index": "5",
                                "mtu": "9100",  # <== critical config under port which is not part of the move below
                                "lanes": "45,46,47,48",
                                "pfc_asym": "off",
                                "speed": "40000"
                            }
                        }
                    ]),
                "move": ps.JsonMove.from_operation({
                    "op": "add",
                    "path": "/PORT/Ethernet20",
                    "value": {
                        "admin_status": "up", # <== status-changing from not-existing i.e "down" to "up"
                        "alias": "fortyGigE0/20",
                        "description": "Servers4:eth0",
                        "index": "5",
                        # "mtu": "9100", # <== critical change is left out
                        "lanes": "45,46,47,48",
                        "pfc_asym": "off",
                        "speed": "40000"
                    }
                })
            },
            "NOT_PORT_UP__STATUS_CHANGING__NOT_UNDER_PORT__PORT_EXIST__NOT_ALL_CRITICAL_CHANGES_INCLUDED": {
                "expected": False,
                "config": Files.CONFIG_DB_WITH_PORT_CRITICAL,
                "target_config": self._apply_operations(Files.CONFIG_DB_WITH_PORT_CRITICAL,
                    [
                        # The following critical change is not part of the move below
                        {"op":"replace", "path":"/BUFFER_PG/Ethernet12|0/profile", "value": "egress_lossy_profile"},
                    ]),
                "move": ps.JsonMove.from_operation({"op":"replace", "path":"/PORT/Ethernet12/admin_status", "value": "up"})
            },
            "NOT_PORT_UP__STATUS_CHANGING__NOT_UNDER_PORT__NOT_PORT_EXIST__NOT_ALL_CRITICAL_CHANGES_INCLUDED": {
                "expected": False,
                "config": Files.CONFIG_DB_WITH_PORT_CRITICAL,
                "target_config": self._apply_operations(Files.CONFIG_DB_WITH_PORT_CRITICAL,
                    [
                        {
                            "op":"add",
                            "path":"/BUFFER_PG/Ethernet20|0",
                            "value": {
                                "profile": "ingress_lossy_profile"
                            }
                        },
                        {
                            "op": "add",
                            "path": "/PORT/Ethernet20",
                            "value": {
                                "admin_status": "up", # <== status-changing from not-existing i.e "down" to "up"
                                "alias": "fortyGigE0/20",
                                "description": "Servers4:eth0",
                                "index": "5",
                                "lanes": "45,46,47,48",
                                "pfc_asym": "off",
                                "speed": "40000"
                            }
                        }
                    ]),
                "move": ps.JsonMove.from_operation({
                    "op": "add",
                    "path": "/PORT/Ethernet20",
                    "value": {
                        "admin_status": "up", # <== status-changing from not-existing i.e "down" to "up"
                        "alias": "fortyGigE0/20",
                        "description": "Servers4:eth0",
                        "index": "5",
                        # "mtu": "9100", # <== critical change is left out
                        "lanes": "45,46,47,48",
                        "pfc_asym": "off",
                        "speed": "40000"
                    }
                })
            },
            # Additional cases trying different operation to port-critical config i.e. REPLACE, REMOVE, ADD
            "PORT_UP__NOT_STATUS_CHANGING__UNDER_PORT__PORT_EXIST__REMOVE": {
                "expected": False,
                "config": Files.CONFIG_DB_WITH_PORT_CRITICAL,
                "move": ps.JsonMove.from_operation({
                    "op": "remove",
                    "path": "/PORT/Ethernet4/mtu"
                })
            },
            "PORT_UP__NOT_STATUS_CHANGING__UNDER_PORT__PORT_EXIST__ADD": {
                "expected": False,
                "config": Files.CONFIG_DB_WITH_PORT_CRITICAL,
                "move": ps.JsonMove.from_operation({
                    "op": "add",
                    "path": "/PORT/Ethernet8/mtu",
                    "value": "9000"
                })
            },
            "PORT_UP__NOT_STATUS_CHANGING__NOT_UNDER_PORT__PORT_EXIST__REMOVE": {
                "expected": False,
                "config": Files.CONFIG_DB_WITH_PORT_CRITICAL,
                "move": ps.JsonMove.from_operation({
                    "op":"remove",
                    "path":"/BUFFER_PG/Ethernet4|0/profile"
                })
            },
            "PORT_UP__NOT_STATUS_CHANGING__NOT_UNDER_PORT__PORT_EXIST__ADD": {
                "expected": False,
                "config": Files.CONFIG_DB_WITH_PORT_CRITICAL,
                "move": ps.JsonMove.from_operation({
                    "op":"add",
                    "path":"/BUFFER_PG/Ethernet8|0",
                    "value":{
                        "profile": "ingress_lossy_profile"
                    }
                })
            },
            "NOT_PORT_UP__NOT_STATUS_CHANGING__UNDER_PORT__PORT_EXIST__REMOVE": {
                "expected": True,
                "config": Files.CONFIG_DB_WITH_PORT_CRITICAL,
                "move": ps.JsonMove.from_operation({
                    "op": "remove",
                    "path": "/PORT/Ethernet12/mtu"
                })
            },
            "NOT_PORT_UP__NOT_STATUS_CHANGING__UNDER_PORT__PORT_EXIST__ADD": {
                "expected": True,
                "config": Files.CONFIG_DB_WITH_PORT_CRITICAL,
                "move": ps.JsonMove.from_operation({
                    "op": "add",
                    "path": "/PORT/Ethernet16/mtu",
                    "value": "9000"
                })
            },
            "NOT_PORT_UP__NOT_STATUS_CHANGING__NOT_UNDER_PORT__PORT_EXIST__REMOVE": {
                "expected": True,
                "config": Files.CONFIG_DB_WITH_PORT_CRITICAL,
                "move": ps.JsonMove.from_operation({
                    "op":"remove",
                    "path":"/BUFFER_PG/Ethernet12|0"
                })
            },
            "NOT_PORT_UP__NOT_STATUS_CHANGING__NOT_UNDER_PORT__PORT_EXIST__ADD": {
                "expected": True,
                "config": Files.CONFIG_DB_WITH_PORT_CRITICAL,
                "move": ps.JsonMove.from_operation({
                    "op":"add",
                    "path":"/BUFFER_PG/Ethernet16|0",
                    "value": {
                        "profile": "ingress_lossy_profile"
                    }
                })
            },
            # Additional cases where the full port is getting deleted
            # If port is getting deleted, there is no point in checking if there are critical changes depending on it
            "NOT_PORT_UP__STATUS_CHANGING__UNDER_PORT__PORT_EXIST__PORT_DELETION": {
                "expected": True,
                "config": Files.CONFIG_DB_WITH_PORT_CRITICAL,
                "move": ps.JsonMove.from_operation({ "op": "remove", "path": "/PORT/Ethernet32" })
            },
            "NOT_PORT_UP__STATUS_CHANGING__NOT_UNDER_PORT__PORT_EXIST__PORT_DELETION": {
                "expected": True,
                "config": Files.CONFIG_DB_WITH_PORT_CRITICAL,
                "target_config": self._apply_operations(Files.CONFIG_DB_WITH_PORT_CRITICAL, [
                    { "op": "remove", "path": "/PORT/Ethernet28" },
                    { "op": "remove", "path": "/BUFFER_PG/Ethernet28|0" },
                ]),
                "move": ps.JsonMove.from_operation({ "op": "remove", "path": "/PORT/Ethernet28" })
            },
        }

    def test_validate__no_critical_port_changes(self):
        # Each test format:
        #   "<test-name>": {
        #       "expected": "<True|False>",
        #       "config": <config>,
        #       "move": <move>,
        #       "target_config": <OPTIONAL> <target-config-if-different-than-applying-move-to-config>
        #   }
        # Each test is testing different flag of:
        #  - port-up: if port is up or not in current_config
        #  - status-changing: if admin_status is changing from any state to another
        #  - under-port: if the port-critical config is under port
        #  - port-exist: if the port already exist in current_config
        test_cases = self._get_no_critical_port_change_test_cases()
        for test_case_name in test_cases:
            with self.subTest(name=test_case_name):
                self._run_single_test(test_cases[test_case_name])

    def _get_no_critical_port_change_test_cases(self):
        return {
            "REPLACE_NON_CRITICAL_CONFIG": {
                "expected": True,
                "config": Files.CONFIG_DB_WITH_PORT_CRITICAL,
                "move": ps.JsonMove.from_operation({
                    "op": "replace",
                    "path": "/PORT/Ethernet4/description",
                    "value": "desc4"
                })
            },
            "REMOVE_NON_CRITICAL_CONFIG": {
                "expected": True,
                "config": Files.CONFIG_DB_WITH_PORT_CRITICAL,
                "move": ps.JsonMove.from_operation({
                    "op": "remove",
                    "path": "/PORT/Ethernet4/description"
                })
            },
            "ADD_NON_CRITICAL_CONFIG": {
                "expected": True,
                "config": Files.CONFIG_DB_WITH_PORT_CRITICAL,
                "move": ps.JsonMove.from_operation({
                    "op": "add",
                    "path": "/PORT/Ethernet8/description",
                    "value": "desc8"
                })
            },
        }

    def _apply_operations(self, config, operations):
        return jsonpatch.JsonPatch(operations).apply(config)

class RemoveCreateOnlyDependencyMoveValidator(unittest.TestCase):
    def setUp(self):
        path_addressing = PathAddressing(ConfigWrapper())
        self.validator = ps.RemoveCreateOnlyDependencyMoveValidator(path_addressing)

    def test_validate__lane_replacement_change(self):
        test_cases = self._get_lane_replacement_change_test_cases()
        for test_case_name in test_cases:
            with self.subTest(name=test_case_name):
                self._run_single_test(test_cases[test_case_name])

    def _run_single_test(self, test_case):
        # Arrange
        expected = test_case['expected']
        current_config = test_case['config']
        move = test_case['move']
        target_config = test_case.get('target_config', move.apply(current_config))
        diff = ps.Diff(current_config, target_config)

        # Act and Assert
        self.assertEqual(expected, self.validator.validate(move, diff))

    def _apply_operations(self, config, operations):
        return jsonpatch.JsonPatch(operations).apply(config)

    def _get_lane_replacement_change_test_cases(self):
        return {
            "PORT_NOT_IN_CURRENT_CONFIG": {
                "expected": True,
                "config": {},
                "move": Mock(),
                "target_config": Files.DPB_1_SPLIT_FULL_CONFIG
            },
            "PORT_NOT_IN_TARGET_CONFIG": {
                "expected": True,
                "config": Files.DPB_1_SPLIT_FULL_CONFIG,
                "move": Mock(),
                "target_config": {}
            },
            "PORT_EMPTY_IN_CURRENT_CONFIG": {
                "expected": True,
                "config": {"PORT": {}},
                "move": Mock(),
                "target_config": Files.DPB_1_SPLIT_FULL_CONFIG
            },
            "PORT_EMPTY_IN_TARGET_CONFIG": {
                "expected": True,
                "config": Files.DPB_1_SPLIT_FULL_CONFIG,
                "move": Mock(),
                "target_config": {"PORT": {}}
            },
            "SAME_LANE_IN_BOTH_CONFIG": {
                "expected": True,
                "config": Files.DPB_1_SPLIT_FULL_CONFIG,
                "move": ps.JsonMove.from_operation({
                    "op": "remove",
                    "path": "/ACL_TABLE"
                })
            },
            "LANE_DIFF__CURRENT_DOWN__SIMULATED_UP": {
                "expected": False,
                "config": Files.DPB_1_SPLIT_FULL_CONFIG,
                "move": ps.JsonMove.from_operation({
                    "op": "add",
                    "path": "/PORT/Ethernet0/admin_status",
                    "value": "up"
                }),
                "target_config":Files.DPB_4_SPLITS_FULL_CONFIG,
            },
            "LANE_DIFF__STATUS_SAME__SIMULATED_EXTRA_DEPDENDENCY": {
                "expected": False,
                "config": self._apply_operations(Files.DPB_1_SPLIT_FULL_CONFIG, [
                    {"op": "remove", "path": "/ACL_TABLE"},
                ]),
                "move": ps.JsonMove.from_operation({
                    "op": "add",
                    "path": "/ACL_TABLE",
                    "value": {
                        "NO-NSW-PACL-V4": {
                            "type": "L3",
                            "policy_desc": "NO-NSW-PACL-V4",
                            "ports": [
                                "Ethernet0"
                            ]
                        }
                    }
                }),
                "target_config": Files.DPB_4_SPLITS_FULL_CONFIG
            },
            "LANE_DIFF__STATUS_SAME__SIMULATED_LESS_DEPDENDENCY": {
                "expected": True,
                "config": Files.DPB_1_SPLIT_FULL_CONFIG,
                "move": ps.JsonMove.from_operation({
                    "op": "remove",
                    "path": "/ACL_TABLE"
                }),
                "target_config": Files.DPB_4_SPLITS_FULL_CONFIG
            }
        }

class TestTableLevelMoveGenerator(unittest.TestCase):
    def setUp(self):
        self.generator = ps.TableLevelMoveGenerator()

    def test_generate__tables_in_current_but_not_target__tables_deleted_moves(self):
        self.verify(current = {"ExistingTable": {}, "NonExistingTable1": {}, "NonExistingTable2": {}},
                    target = {"ExistingTable": {}},
                    ex_ops = [{"op": "remove", 'path': '/NonExistingTable1'},
                              {"op": "remove", 'path': '/NonExistingTable2'}])

    def test_generate__tables_in_target_but_not_current__tables_added_moves(self):
        self.verify(current = {"ExistingTable": {}},
                    target = {"ExistingTable": {}, "NonExistingTable1": {}, "NonExistingTable2": {}},
                    ex_ops = [{"op": "add", 'path': '/NonExistingTable1', 'value': {}},
                              {"op": "add", 'path': '/NonExistingTable2', 'value': {}}])

    def test_generate__all_tables_exist__no_moves(self):
        self.verify(current = {"ExistingTable1": { "Key1": "Value1" }, "ExistingTable2": {}},
                    target = {"ExistingTable1": {}, "ExistingTable2": { "Key2": "Value2" }},
                    ex_ops = [])
    
    def test_generate__multiple_cases__deletion_precedes_addition(self):
        self.verify(current = {"CommonTable": { "Key1": "Value1" }, "CurrentTable": {}},
                    target = {"CommonTable": {}, "TargetTable": { "Key2": "Value2" }},
                    ex_ops = [{"op": "remove", 'path': '/CurrentTable'},
                              {"op": "add", 'path': '/TargetTable', 'value': { "Key2": "Value2" }}])

    def verify(self, current, target, ex_ops):
        # Arrange
        diff = ps.Diff(current, target)

        # Act
        moves = self.generator.generate(diff)

        # Assert
        self.verify_moves(ex_ops,
                          moves)

    def verify_moves(self, ops, moves):
        moves_ops = [list(move.patch)[0] for move in moves]
        self.assertCountEqual(ops, moves_ops)

class TestKeyLevelMoveGenerator(unittest.TestCase):
    def setUp(self):
        self.generator = ps.KeyLevelMoveGenerator()

    def test_generate__keys_in_current_but_not_target__keys_deleted_moves(self):
        self.verify(current = {
                            "ExistingTable1": {
                                "ExistingKey11": "Value11",
                                "NonExistingKey12" : "Value12",
                                "NonExistingKey13" : "Value13"
                            },
                            "NonExistingTable2":
                            {
                                "NonExistingKey21" : "Value21",
                                "NonExistingKey22" : "Value22"
                            }
                        },
                    target = {
                            "ExistingTable1": {
                                "ExistingKey11": "Value11"
                            }
                        },
                    ex_ops = [{"op": "remove", 'path': '/ExistingTable1/NonExistingKey12'},
                              {"op": "remove", 'path': '/ExistingTable1/NonExistingKey13'},
                              {"op": "remove", 'path': '/NonExistingTable2/NonExistingKey21'},
                              {"op": "remove", 'path': '/NonExistingTable2/NonExistingKey22'}])


    def test_generate__single_key_in_current_but_not_target__whole_table_deleted(self):
        self.verify(current = { "ExistingTable1": { "NonExistingKey11" : "Value11" }},
                    target = {},
                    ex_ops = [{"op": "remove", 'path': '/ExistingTable1'}])

    def test_generate__keys_in_target_but_not_current__keys_added_moves(self):
        self.verify(current = {
                            "ExistingTable1": {
                                "ExistingKey11": "Value11"
                            }
                        },
                    target = {
                            "ExistingTable1": {
                                "ExistingKey11": "Value11",
                                "NonExistingKey12" : "Value12",
                                "NonExistingKey13" : "Value13"
                            },
                            "NonExistingTable2":
                            {
                                "NonExistingKey21" : "Value21",
                                "NonExistingKey22" : "Value22"
                            }
                        },
                    ex_ops = [{"op": "add", 'path': '/ExistingTable1/NonExistingKey12', "value": "Value12"},
                              {"op": "add", 'path': '/ExistingTable1/NonExistingKey13', "value": "Value13"},
                              {"op": "add", 'path': '/NonExistingTable2', "value": { "NonExistingKey21": "Value21" }},
                              {"op": "add", 'path': '/NonExistingTable2', "value": { "NonExistingKey22": "Value22" }}])

    def test_generate__all_keys_exist__no_moves(self):
        self.verify(current = {"ExistingTable1": { "Key1": "Value1Current" }, "ExistingTable2": { "Key2": "Value2" }},
                    target = {"ExistingTable1": { "Key1": "Value1Target" }, "ExistingTable2": { "Key2": {} } },
                    ex_ops = [])

    def test_generate__multiple_cases__deletion_precedes_addition(self):
        self.verify(current = {"AnyTable": { "CommonKey": "CurrentValue1", "CurrentKey": "CurrentValue2" }},
                    target = {"AnyTable": { "CommonKey": "TargetValue1", "TargetKey": "TargetValue2" }},
                    ex_ops = [{"op": "remove", 'path': '/AnyTable/CurrentKey'},
                              {"op": "add", 'path': '/AnyTable/TargetKey', 'value': "TargetValue2"}])

    def verify(self, current, target, ex_ops):
        # Arrange
        diff = ps.Diff(current, target)

        # Act
        moves = self.generator.generate(diff)

        # Assert
        self.verify_moves(ex_ops,
                          moves)

    def verify_moves(self, ops, moves):
        moves_ops = [list(move.patch)[0] for move in moves]
        self.assertCountEqual(ops, moves_ops)

class TestLowLevelMoveGenerator(unittest.TestCase):
    def setUp(self):
        path_addressing = PathAddressing()
        self.generator = ps.LowLevelMoveGenerator(path_addressing)

    def test_generate__no_diff__no_moves(self):
        self.verify()

    def test_generate__replace_key__replace_move(self):
        self.verify(tc_ops=[{"op": "replace", 'path': '/PORT/Ethernet0/description', 'value':'any-desc'}])

    def test_generate__leaf_key_missing__add_move(self):
        self.verify(
            cc_ops=[{"op": "remove", 'path': '/ACL_TABLE/EVERFLOW/policy_desc'}],
            ex_ops=[{"op": "add", 'path': '/ACL_TABLE/EVERFLOW/policy_desc', 'value':'EVERFLOW'}]
            )

    def test_generate__leaf_key_additional__remove_move(self):
        self.verify(
            tc_ops=[{"op": "remove", 'path': '/ACL_TABLE/EVERFLOW/policy_desc'}]
            )

    def test_generate__table_missing__add_leafs_moves(self):
        self.verify(
            cc_ops=[{"op": "remove", 'path': '/VLAN'}],
            ex_ops=[{'op': 'add', 'path': '/VLAN', 'value': {'Vlan1000': {'vlanid': '1000'}}},
                    {'op': 'add', 'path': '/VLAN', 'value': {'Vlan1000': {'dhcp_servers': ['192.0.0.1']}}},
                    {'op': 'add', 'path': '/VLAN', 'value': {'Vlan1000': {'dhcp_servers': ['192.0.0.2']}}},
                    {'op': 'add', 'path': '/VLAN', 'value': {'Vlan1000': {'dhcp_servers': ['192.0.0.3']}}},
                    {'op': 'add', 'path': '/VLAN', 'value': {'Vlan1000': {'dhcp_servers': ['192.0.0.4']}}}]
            )

    def test_generate__table_additional__remove_leafs_moves(self):
        self.verify(
            tc_ops=[{"op": "remove", 'path': '/VLAN'}],
            ex_ops=[{'op': 'remove', 'path': '/VLAN/Vlan1000/vlanid'},
                    {'op': 'remove', 'path': '/VLAN/Vlan1000/dhcp_servers/0'},
                    {'op': 'remove', 'path': '/VLAN/Vlan1000/dhcp_servers/1'},
                    {'op': 'remove', 'path': '/VLAN/Vlan1000/dhcp_servers/2'},
                    {'op': 'remove', 'path': '/VLAN/Vlan1000/dhcp_servers/3'}]
            )

    def test_generate__leaf_table_missing__add_table(self):
        self.verify(
            tc_ops=[{"op": "add", 'path': '/NEW_TABLE', 'value':{}}]
            )

    def test_generate__leaf_table_additional__remove_table(self):
        self.verify(
            cc_ops=[{"op": "add", 'path': '/NEW_TABLE', 'value':{}}],
            ex_ops=[{"op": "remove", 'path': '/NEW_TABLE'}]
            )

    def test_generate__replace_list_item__remove_add_replace_moves(self):
        self.verify(
            tc_ops=[{"op": "replace", 'path': '/ACL_TABLE/EVERFLOW/ports/0', 'value':'Ethernet0'}],
            ex_ops=[
                {"op": "remove", 'path': '/ACL_TABLE/EVERFLOW/ports/0'},
                {"op": "add", 'path': '/ACL_TABLE/EVERFLOW/ports/0', 'value':'Ethernet0'},
                {"op": "replace", 'path': '/ACL_TABLE/EVERFLOW/ports/0', 'value':'Ethernet0'},
            ])

    def test_generate__remove_list_item__remove_move(self):
        self.verify(
            tc_ops=[{"op": "remove", 'path': '/VLAN/Vlan1000/dhcp_servers/0'}])

    def test_generate__remove_multiple_list_items__multiple_remove_moves(self):
        self.verify(
            tc_ops=[{"op": "remove", 'path': '/VLAN/Vlan1000/dhcp_servers/0'},
                    {"op": "remove", 'path': '/VLAN/Vlan1000/dhcp_servers/0'}],
            ex_ops=[{"op": "remove", 'path': '/VLAN/Vlan1000/dhcp_servers/0'},
                    {"op": "remove", 'path': '/VLAN/Vlan1000/dhcp_servers/1'}]
            )

    def test_generate__remove_all_list_items__multiple_remove_moves(self):
        self.verify(
            tc_ops=[{"op": "replace", 'path': '/VLAN/Vlan1000/dhcp_servers', 'value':[]}],
            ex_ops=[{"op": "remove", 'path': '/VLAN/Vlan1000/dhcp_servers/0'},
                    {"op": "remove", 'path': '/VLAN/Vlan1000/dhcp_servers/2'},
                    {"op": "remove", 'path': '/VLAN/Vlan1000/dhcp_servers/3'},
                    {"op": "remove", 'path': '/VLAN/Vlan1000/dhcp_servers/1'}]
            )

    def test_generate__add_list_items__add_move(self):
        self.verify(
            tc_ops=[{"op": "add", 'path': '/VLAN/Vlan1000/dhcp_servers/0', 'value':'192.168.1.5'}]
            )

    def test_generate__add_multiple_list_items__multiple_add_moves(self):
        self.verify(
            tc_ops=[{"op": "add", 'path': '/VLAN/Vlan1000/dhcp_servers/0', 'value':'192.168.1.5'},
                    {"op": "add", 'path': '/VLAN/Vlan1000/dhcp_servers/3', 'value':'192.168.1.6'}]
            )

    def test_generate__add_all_list_items__multiple_add_moves(self):
        self.verify(
            cc_ops=[{"op": "replace", 'path': '/VLAN/Vlan1000/dhcp_servers', 'value':[]}],
            ex_ops=[{"op": "add", 'path': '/VLAN/Vlan1000/dhcp_servers/0', 'value':'192.0.0.1'},
                    {"op": "add", 'path': '/VLAN/Vlan1000/dhcp_servers/0', 'value':'192.0.0.2'},
                    {"op": "add", 'path': '/VLAN/Vlan1000/dhcp_servers/0', 'value':'192.0.0.3'},
                    {"op": "add", 'path': '/VLAN/Vlan1000/dhcp_servers/0', 'value':'192.0.0.4'}]
            )

    def test_generate__replace_multiple_list_items__multiple_remove_add_replace_moves(self):
        self.verify(
            tc_ops=[{"op": "replace", 'path': '/VLAN/Vlan1000/dhcp_servers/0', 'value':'192.168.1.5'},
                    {"op": "replace", 'path': '/VLAN/Vlan1000/dhcp_servers/3', 'value':'192.168.1.6'}],
            ex_ops=[{"op": "remove", 'path': '/VLAN/Vlan1000/dhcp_servers/0'},
                    {"op": "remove", 'path': '/VLAN/Vlan1000/dhcp_servers/3'},
                    {"op": "add", 'path': '/VLAN/Vlan1000/dhcp_servers/0', 'value':'192.168.1.5'},
                    {"op": "add", 'path': '/VLAN/Vlan1000/dhcp_servers/3', 'value':'192.168.1.6'},
                    {"op": "replace", 'path': '/VLAN/Vlan1000/dhcp_servers/0', 'value':'192.168.1.5'},
                    {"op": "replace", 'path': '/VLAN/Vlan1000/dhcp_servers/3', 'value':'192.168.1.6'},
                    {"op": "replace", 'path': '/VLAN/Vlan1000/dhcp_servers/3', 'value':'192.168.1.5'},
                    {"op": "replace", 'path': '/VLAN/Vlan1000/dhcp_servers/0', 'value':'192.168.1.6'}]
            )

    def test_generate__different_order_list_items__whole_list_replace_move(self):
        self.verify(
            tc_ops=[{"op": "replace", 'path': '/VLAN/Vlan1000/dhcp_servers', 'value':[
                "192.0.0.4",
                "192.0.0.3",
                "192.0.0.2",
                "192.0.0.1"
            ]}])

    def test_generate__whole_list_missing__add_items_moves(self):
        self.verify(
            cc_ops=[{"op": "remove", 'path': '/VLAN/Vlan1000/dhcp_servers'}],
            ex_ops=[{'op': 'add', 'path': '/VLAN/Vlan1000/dhcp_servers', 'value': ['192.0.0.1']},
                    {'op': 'add', 'path': '/VLAN/Vlan1000/dhcp_servers', 'value': ['192.0.0.2']},
                    {'op': 'add', 'path': '/VLAN/Vlan1000/dhcp_servers', 'value': ['192.0.0.3']},
                    {'op': 'add', 'path': '/VLAN/Vlan1000/dhcp_servers', 'value': ['192.0.0.4']}])

    def test_generate__whole_list_additional__remove_items_moves(self):
        self.verify(
            tc_ops=[{"op": "remove", 'path': '/VLAN/Vlan1000/dhcp_servers'}],
            ex_ops=[{'op': 'remove', 'path': '/VLAN/Vlan1000/dhcp_servers/0'},
                    {'op': 'remove', 'path': '/VLAN/Vlan1000/dhcp_servers/1'},
                    {'op': 'remove', 'path': '/VLAN/Vlan1000/dhcp_servers/2'},
                    {'op': 'remove', 'path': '/VLAN/Vlan1000/dhcp_servers/3'}])

    def test_generate__empty_list_missing__add_whole_list(self):
        self.verify(
            tc_ops=[{"op": "replace", 'path': '/VLAN/Vlan1000/dhcp_servers', 'value':[]}],
            cc_ops=[{"op": "remove", 'path': '/VLAN/Vlan1000/dhcp_servers'}],
            ex_ops=[{'op': 'add', 'path': '/VLAN/Vlan1000/dhcp_servers', 'value':[]}])

    def test_generate__empty_list_additional__remove_whole_list(self):
        self.verify(
            tc_ops=[{"op": "remove", 'path': '/VLAN/Vlan1000/dhcp_servers'}],
            cc_ops=[{"op": "replace", 'path': '/VLAN/Vlan1000/dhcp_servers', 'value':[]}],
            ex_ops=[{'op': 'remove', 'path': '/VLAN/Vlan1000/dhcp_servers'}])

    def test_generate__dpb_1_to_4_example(self):
        # Arrange
        diff = ps.Diff(Files.DPB_1_SPLIT_FULL_CONFIG, Files.DPB_4_SPLITS_FULL_CONFIG)

        # Act
        moves = list(self.generator.generate(diff))

        # Assert
        self.verify_moves([{'op': 'replace', 'path': '/PORT/Ethernet0/alias', 'value': 'Eth1/1'},
                           {'op': 'replace', 'path': '/PORT/Ethernet0/lanes', 'value': '65'},
                           {'op': 'replace', 'path': '/PORT/Ethernet0/description', 'value': ''},
                           {'op': 'replace', 'path': '/PORT/Ethernet0/speed', 'value': '10000'},
                           {'op': 'add', 'path': '/PORT/Ethernet1', 'value': {'alias': 'Eth1/2'}},
                           {'op': 'add', 'path': '/PORT/Ethernet1', 'value': {'lanes': '66'}},
                           {'op': 'add', 'path': '/PORT/Ethernet1', 'value': {'description': ''}},
                           {'op': 'add', 'path': '/PORT/Ethernet1', 'value': {'speed': '10000'}},
                           {'op': 'add', 'path': '/PORT/Ethernet2', 'value': {'alias': 'Eth1/3'}},
                           {'op': 'add', 'path': '/PORT/Ethernet2', 'value': {'lanes': '67'}},
                           {'op': 'add', 'path': '/PORT/Ethernet2', 'value': {'description': ''}},
                           {'op': 'add', 'path': '/PORT/Ethernet2', 'value': {'speed': '10000'}},
                           {'op': 'add', 'path': '/PORT/Ethernet3', 'value': {'alias': 'Eth1/4'}},
                           {'op': 'add', 'path': '/PORT/Ethernet3', 'value': {'lanes': '68'}},
                           {'op': 'add', 'path': '/PORT/Ethernet3', 'value': {'description': ''}},
                           {'op': 'add', 'path': '/PORT/Ethernet3', 'value': {'speed': '10000'}},
                           {'op': 'add', 'path': '/ACL_TABLE/NO-NSW-PACL-V4/ports/1', 'value': 'Ethernet1'},
                           {'op': 'add', 'path': '/ACL_TABLE/NO-NSW-PACL-V4/ports/1', 'value': 'Ethernet2'},
                           {'op': 'add', 'path': '/ACL_TABLE/NO-NSW-PACL-V4/ports/1', 'value': 'Ethernet3'},
                           {'op': 'add', 'path': '/VLAN_MEMBER/Vlan100|Ethernet1', 'value': {'tagging_mode': 'untagged'}},
                           {'op': 'add', 'path': '/VLAN_MEMBER/Vlan100|Ethernet2', 'value': {'tagging_mode': 'untagged'}},
                           {'op': 'add', 'path': '/VLAN_MEMBER/Vlan100|Ethernet3', 'value': {'tagging_mode': 'untagged'}}],
                          moves)

    def test_generate__dpb_4_to_1_example(self):
        # Arrange
        diff = ps.Diff(Files.DPB_4_SPLITs_FULL_CONFIG, Files.DPB_1_SPLIT_FULL_CONFIG)

        # Act
        moves = list(self.generator.generate(diff))

        # Assert
        self.verify_moves([{'op': 'replace', 'path': '/PORT/Ethernet0/alias', 'value': 'Eth1'},
                           {'op': 'replace', 'path': '/PORT/Ethernet0/lanes', 'value': '65, 66, 67, 68'},
                           {'op': 'replace', 'path': '/PORT/Ethernet0/description', 'value': 'Ethernet0 100G link'},
                           {'op': 'replace', 'path': '/PORT/Ethernet0/speed', 'value': '100000'},
                           {'op': 'remove', 'path': '/PORT/Ethernet1/alias'},
                           {'op': 'remove', 'path': '/PORT/Ethernet1/lanes'},
                           {'op': 'remove', 'path': '/PORT/Ethernet1/description'},
                           {'op': 'remove', 'path': '/PORT/Ethernet1/speed'},
                           {'op': 'remove', 'path': '/PORT/Ethernet2/alias'},
                           {'op': 'remove', 'path': '/PORT/Ethernet2/lanes'},
                           {'op': 'remove', 'path': '/PORT/Ethernet2/description'},
                           {'op': 'remove', 'path': '/PORT/Ethernet2/speed'},
                           {'op': 'remove', 'path': '/PORT/Ethernet3/alias'},
                           {'op': 'remove', 'path': '/PORT/Ethernet3/lanes'},
                           {'op': 'remove', 'path': '/PORT/Ethernet3/description'},
                           {'op': 'remove', 'path': '/PORT/Ethernet3/speed'},
                           {'op': 'remove', 'path': '/ACL_TABLE/NO-NSW-PACL-V4/ports/1'},
                           {'op': 'remove', 'path': '/ACL_TABLE/NO-NSW-PACL-V4/ports/2'},
                           {'op': 'remove', 'path': '/ACL_TABLE/NO-NSW-PACL-V4/ports/3'},
                           {'op': 'remove', 'path': '/VLAN_MEMBER/Vlan100|Ethernet1/tagging_mode'},
                           {'op': 'remove', 'path': '/VLAN_MEMBER/Vlan100|Ethernet2/tagging_mode'},
                           {'op': 'remove', 'path': '/VLAN_MEMBER/Vlan100|Ethernet3/tagging_mode'}],
                          moves)

    def verify(self, tc_ops=None, cc_ops=None, ex_ops=None):
        """
        Generate a diff where target config is modified using the given tc_ops.
        The expected low level moves should ex_ops if it is not None, otherwise tc_ops
        """
        # Arrange
        diff = self.get_diff(target_config_ops=tc_ops, current_config_ops=cc_ops)
        expected = ex_ops if ex_ops is not None else \
                   tc_ops if tc_ops is not None else \
                   []

        # Act
        actual = self.generator.generate(diff)

        # Assert
        self.verify_moves(expected, actual)

    def verify_moves(self, ops, moves):
        moves_ops = [list(move.patch)[0] for move in moves]
        self.assertCountEqual(ops, moves_ops)

    def get_diff(self, target_config_ops = None, current_config_ops = None):
        current_config = Files.CROPPED_CONFIG_DB_AS_JSON
        if current_config_ops:
            cc_patch = jsonpatch.JsonPatch(current_config_ops)
            current_config = cc_patch.apply(current_config)

        target_config = Files.CROPPED_CONFIG_DB_AS_JSON
        if target_config_ops:
            tc_patch = jsonpatch.JsonPatch(target_config_ops)
            target_config = tc_patch.apply(target_config)

        return ps.Diff(current_config, target_config)

class RemoveCreateOnlyDependencyMoveGenerator(unittest.TestCase):
    def setUp(self):
        config_wrapper = ConfigWrapper()
        path_addressing = PathAddressing(config_wrapper)
        self.generator = ps.RemoveCreateOnlyDependencyMoveGenerator(path_addressing)

    def test_generate__no_port_table__no_moves(self):
        current_config = {}
        target_config = {"PORT": {"Ethernet0": {}}}

        # No PORT table in current_config
        diff = ps.Diff(current_config, target_config)
        moves = list(self.generator.generate(diff))
        self.verify_moves([], moves)

        # No PORT table in target_config
        diff = ps.Diff(target_config, current_config)
        moves = list(self.generator.generate(diff))
        self.verify_moves([], moves)

    def test_generate__empty_port_content__no_moves(self):
        current_config = {"PORT": {}}
        target_config = {"PORT": {"Ethernet0": {}}}

        # Empty PORT content in current_config
        diff = ps.Diff(current_config, target_config)
        moves = list(self.generator.generate(diff))
        self.verify_moves([], moves)

        # Empty PORT content in target_config
        diff = ps.Diff(target_config, current_config)
        moves = list(self.generator.generate(diff))
        self.verify_moves([], moves)

    def test_generate__same_lanes__no_moves(self):
        current_config = Files.CROPPED_CONFIG_DB_AS_JSON
        patch = jsonpatch.JsonPatch([
            {'op': 'remove', 'path': '/VLAN_MEMBER'}
        ])
        target_config = patch.apply(Files.CROPPED_CONFIG_DB_AS_JSON)

        # Remove VLAN_MEMBER in target_config, lanes are same
        diff = ps.Diff(current_config, target_config)
        moves = list(self.generator.generate(diff))
        self.verify_moves([], moves)

        # Add VLAN_MEMBER in current_config, lanes are same
        diff = ps.Diff(target_config, current_config)
        moves = list(self.generator.generate(diff))
        self.verify_moves([], moves)

    def test_generate__dpb_4_to_1_example(self):
        # Arrange
        diff = ps.Diff(Files.DPB_4_SPLITs_FULL_CONFIG, Files.DPB_1_SPLIT_FULL_CONFIG)

        # Act
        moves = list(self.generator.generate(diff))

        # Assert
        self.verify_moves([{'op': 'remove', 'path': '/ACL_TABLE/NO-NSW-PACL-V4/ports/0'},
                           {'op': 'remove', 'path': '/VLAN_MEMBER/Vlan100|Ethernet0'}],
                          moves)

    def test_generate__dpb_1_to_4_example(self):
        # Arrange
        diff = ps.Diff(Files.DPB_1_SPLIT_FULL_CONFIG, Files.DPB_4_SPLITS_FULL_CONFIG)

        # Act
        moves = list(self.generator.generate(diff))

        # Assert
        self.verify_moves([{'op': 'remove', 'path': '/ACL_TABLE/NO-NSW-PACL-V4/ports/0'},
                           {'op': 'remove', 'path': '/VLAN_MEMBER/Vlan100|Ethernet0'}],
                          moves)

    def verify_moves(self, ops, moves):
        moves_ops = [list(move.patch)[0] for move in moves]
        self.assertCountEqual(ops, moves_ops)

class TestRequiredValueMoveExtender(unittest.TestCase):
    def setUp(self):
        path_addressing = PathAddressing()
        self.extender = ps.RequiredValueMoveExtender(path_addressing, OperationWrapper())
        self.extender.identifier.settings[0]["requiring_filter"] = ps.JsonPointerFilter([
                ["BUFFER_PG", "@|*"],
                ["PORT", "@", "mtu"]
            ],
            path_addressing)

    def test_extend__remove_whole_config__no_extended_moves(self):
        # Arrange
        move = ps.JsonMove.from_operation({"op":"remove", "path":""})
        diff = ps.Diff(Files.ANY_CONFIG_DB, Files.ANY_OTHER_CONFIG_DB)
        expected = []

        # Act
        actual = self.extender.extend(move, diff)

        # Assert
        self._verify_moves(expected, actual)

    def test_extend__port_up_and_no_critical_move__no_extended_moves(self):
        # Arrange
        move = ps.JsonMove.from_operation({"op":"replace", "path":"/PORT/Ethernet4/description", "value":"desc4"})
        current_config = Files.CONFIG_DB_WITH_PORT_CRITICAL
        target_config = move.apply(current_config)
        diff = ps.Diff(current_config, target_config)
        expected = []

        # Act
        actual = self.extender.extend(move, diff)

        # Assert
        self._verify_moves(expected, actual)

    def test_extend__port_up_and_critical_move__turn_admin_status_down(self):
        # Arrange
        move = ps.JsonMove.from_operation({"op":"replace", "path":"/PORT/Ethernet4/mtu", "value":"9000"})
        current_config = Files.CONFIG_DB_WITH_PORT_CRITICAL
        target_config = move.apply(current_config)
        diff = ps.Diff(current_config, target_config)
        expected = [{"op":"replace", "path":"/PORT/Ethernet4/admin_status", "value":"down"}]

        # Act
        actual = self.extender.extend(move, diff)

        # Assert
        self._verify_moves(expected, actual)

    def test_extend__port_turn_up_and_no_critical_move__no_extended_moves(self):
        # Arrange
        move = ps.JsonMove.from_operation({"op":"replace", "path":"/PORT/Ethernet12/admin_status", "value":"up"})
        current_config = Files.CONFIG_DB_WITH_PORT_CRITICAL
        target_config = move.apply(current_config)
        diff = ps.Diff(current_config, target_config)
        expected = []

        # Act
        actual = self.extender.extend(move, diff)

        # Assert
        self._verify_moves(expected, actual)

    def test_extend__port_turn_up_and_critical_move__flip_to_turn_down(self):
        # Arrange
        move = ps.JsonMove.from_operation({
            "op":"replace",
            "path":"/PORT/Ethernet12",
            "value":{
                "admin_status": "up", # <== Turn admin_status up
                "alias": "fortyGigE0/12",
                "description": "Servers2:eth0",
                "index": "3",
                "lanes": "37,38,39,40",
                "mtu": "9000", # <== Critical move
                "pfc_asym": "off",
                "speed": "40000"
            },
        })
        current_config = Files.CONFIG_DB_WITH_PORT_CRITICAL
        target_config = move.apply(current_config)
        diff = ps.Diff(current_config, target_config)
        expected = [{
            "op":"replace",
            "path":"/PORT/Ethernet12",
            "value":{
                "admin_status": "down", # <== Leave admin_status as down
                "alias": "fortyGigE0/12",
                "description": "Servers2:eth0",
                "index": "3",
                "lanes": "37,38,39,40",
                "mtu": "9000", # <== Critical move
                "pfc_asym": "off",
                "speed": "40000"
            },
        }]

        # Act
        actual = self.extender.extend(move, diff)

        # Assert
        self._verify_moves(expected, actual)

    def test_extend__multi_port_turn_up_and_critical_move__multi_flip_to_turn_down(self):
        # Arrange
        current_config = Files.CONFIG_DB_WITH_PORT_CRITICAL
        target_config = self._apply_operations(Files.CONFIG_DB_WITH_PORT_CRITICAL, [
            {"op":"replace", "path":"/PORT/Ethernet12/admin_status", "value":"up"},
            {"op":"add", "path":"/PORT/Ethernet16/admin_status", "value":"up"},
            {"op":"add", "path":"/PORT/Ethernet12/mtu", "value":"9000"},
            # Will not be part of the move, only in the final target config
            {"op":"add", "path":"/PORT/Ethernet16/mtu", "value":"9000"}, 
        ])
        move = ps.JsonMove.from_operation({
            "op":"replace",
            "path":"/PORT",
            # Following value is for the PORT part of the config
            "value": self._apply_operations(Files.CONFIG_DB_WITH_PORT_CRITICAL["PORT"], [
                {"op":"replace", "path":"/Ethernet12/admin_status", "value":"up"},
                {"op":"add", "path":"/Ethernet16/admin_status", "value":"up"},
                {"op":"add", "path":"/Ethernet12/mtu", "value":"9000"},
            ])
        })
        diff = ps.Diff(current_config, target_config)
        expected = [{
            "op":"replace",
            "path":"/PORT",
            # Following value is for the PORT part of the config
            "value": self._apply_operations(Files.CONFIG_DB_WITH_PORT_CRITICAL["PORT"], [
                {"op":"replace", "path":"/Ethernet12/admin_status", "value":"down"},
                {"op":"add", "path":"/Ethernet16/admin_status", "value":"down"},
                {"op":"add", "path":"/Ethernet12/mtu", "value":"9000"},
            ])
        }]

        # Act
        actual = self.extender.extend(move, diff)

        # Assert
        self._verify_moves(expected, actual)

    def test_extend__multiple_changes__multiple_extend_moves(self):
        # Arrange
        current_config = Files.CONFIG_DB_WITH_PORT_CRITICAL
        target_config = self._apply_operations(Files.CONFIG_DB_WITH_PORT_CRITICAL, [
            {"op":"replace", "path":"/BUFFER_PG/Ethernet4|0/profile", "value": "egress_lossy_profile"},
            {"op": "add", "path": "/PORT/Ethernet8/mtu", "value": "9000"},
            {
                "op": "add",
                "path": "/PORT/Ethernet20", # <== adding a non-existing port
                "value": {
                    "admin_status": "up", # <== status-changing from not-existing i.e "down" to "up"
                    "alias": "fortyGigE0/20",
                    "description": "Servers4:eth0",
                    "index": "5",
                    "mtu": "9100",  # <== critical config under port
                    "lanes": "45,46,47,48",
                    "pfc_asym": "off",
                    "speed": "40000"
                }
            },
            {"op":"replace", "path":"/PORT/Ethernet12/admin_status", "value":"up"},
            {"op":"add", "path":"/PORT/Ethernet16/admin_status", "value":"up"},
            {"op":"add", "path":"/PORT/Ethernet12/mtu", "value":"9000"},
            # Will not be part of the move, only in the final target config
            {"op":"add", "path":"/PORT/Ethernet16/mtu", "value":"9000"}, 
        ])
        move = ps.JsonMove.from_operation({
            "op":"replace",
            "path":"",
            "value": self._apply_operations(Files.CONFIG_DB_WITH_PORT_CRITICAL, [
                {"op":"replace", "path":"/BUFFER_PG/Ethernet4|0/profile", "value": "egress_lossy_profile"},
                {"op": "add", "path": "/PORT/Ethernet8/mtu", "value": "9000"},
                {
                    "op": "add",
                    "path": "/PORT/Ethernet20", # <== adding a non-existing port
                    "value": {
                        "admin_status": "up", # <== status-changing from not-existing i.e "down" to "up"
                        "alias": "fortyGigE0/20",
                        "description": "Servers4:eth0",
                        "index": "5",
                        "mtu": "9100",  # <== critical config under port
                        "lanes": "45,46,47,48",
                        "pfc_asym": "off",
                        "speed": "40000"
                    }
                },
                {"op":"replace", "path":"/PORT/Ethernet12/admin_status", "value":"up"},
                {"op":"add", "path":"/PORT/Ethernet16/admin_status", "value":"up"},
                {"op":"add", "path":"/PORT/Ethernet12/mtu", "value":"9000"},
            ])
        })
        diff = ps.Diff(current_config, target_config)
        expected = [
            {"op":"replace", "path":"/PORT/Ethernet4/admin_status", "value":"down"},
            {"op":"replace", "path":"/PORT/Ethernet8/admin_status", "value":"down"},
            {
                "op":"replace",
                "path":"",
                "value": self._apply_operations(Files.CONFIG_DB_WITH_PORT_CRITICAL, [
                    {"op":"replace", "path":"/BUFFER_PG/Ethernet4|0/profile", "value": "egress_lossy_profile"},
                    {"op": "add", "path": "/PORT/Ethernet8/mtu", "value": "9000"},
                    {
                        "op": "add",
                        "path": "/PORT/Ethernet20", # <== adding a non-existing port
                        "value": {
                            "admin_status": "down", # <== flipping to down admin_status
                            "alias": "fortyGigE0/20",
                            "description": "Servers4:eth0",
                            "index": "5",
                            "mtu": "9100",  # <== critical config under port
                            "lanes": "45,46,47,48",
                            "pfc_asym": "off",
                            "speed": "40000"
                        }
                    },
                    {"op":"replace", "path":"/PORT/Ethernet12/admin_status", "value":"down"},
                    {"op":"add", "path":"/PORT/Ethernet16/admin_status", "value":"down"},
                    {"op":"add", "path":"/PORT/Ethernet12/mtu", "value":"9000"},
                ])
            }
        ]

        # Act
        actual = self.extender.extend(move, diff)

        # Assert
        self._verify_moves(expected, actual)

    def test_extend__port_deletion__no_extension(self):
        # Arrange
        move = ps.JsonMove.from_operation({
            "op":"remove",
            "path":"/PORT/Ethernet28"
        })
        current_config = Files.CONFIG_DB_WITH_PORT_CRITICAL
        target_config = self._apply_operations(Files.CONFIG_DB_WITH_PORT_CRITICAL, [
            { "op": "remove", "path": "/PORT/Ethernet28" },
            { "op": "remove", "path": "/BUFFER_PG/Ethernet28|0" }
        ])
        diff = ps.Diff(current_config, target_config)
        expected = []

        # Act
        actual = self.extender.extend(move, diff)

        # Assert
        self._verify_moves(expected, actual)

    def _verify_moves(self, ex_ops, moves):
        moves_ops = [list(move.patch)[0] for move in moves]
        self.assertCountEqual(ex_ops, moves_ops)

    def _apply_operations(self, config, operations):
        return jsonpatch.JsonPatch(operations).apply(config)

    def test_flip(self):
        test_cases = {
            "ADD_ADMIN_STATUS": {
                "move": ps.JsonMove.from_operation({"op":"add", "path":"/PORT/Ethernet200/admin_status", "value": "up"}),
                "port_names": ["Ethernet200"],
                "expected": ps.JsonMove.from_operation({"op":"add", "path":"/PORT/Ethernet200/admin_status", "value": "down"})
            },
            "ADD_ETHERNET": {
                "move": ps.JsonMove.from_operation({"op":"add", "path":"/PORT/Ethernet200", "value": {
                    "admin_status": "up",
                }}),
                "port_names": ["Ethernet200"],
                "expected": ps.JsonMove.from_operation({"op":"add", "path":"/PORT/Ethernet200", "value": {
                    "admin_status": "down",
                }})
            },
            "ADD_ETHERNET_NO_ADMIN_STATUS": {
                "move": ps.JsonMove.from_operation({"op":"add", "path":"/PORT/Ethernet200", "value": {
                    "admin_status": "up",
                }}),
                "port_names": ["Ethernet200"],
                "expected": ps.JsonMove.from_operation({"op":"add", "path":"/PORT/Ethernet200", "value": {
                    "admin_status": "down",
                }})
            },
            "ADD_PORT": {
                "move": ps.JsonMove.from_operation({"op":"add", "path":"/PORT", "value": {
                    "Ethernet200":{
                        "admin_status": "up",
                    }
                }}),
                "port_names": ["Ethernet200"],
                "expected": ps.JsonMove.from_operation({"op":"add", "path":"/PORT", "value": {
                    "Ethernet200":{
                        "admin_status": "down",
                    }
                }})
            },
            "ADD_WHOLE_CONFIG": {
                "move": ps.JsonMove.from_operation({"op":"add", "path":"", "value": {
                    "PORT": {
                        "Ethernet200": {
                            "admin_status": "up",
                        }
                    }
                }}),
                "port_names": ["Ethernet200"],
                "expected": ps.JsonMove.from_operation({"op":"add", "path":"", "value": {
                    "PORT": {
                        "Ethernet200":{
                            "admin_status": "down",
                        }
                    }
                }}),
            },
            "ADD_WHOLE_CONFIG_NO_ADMIN_STATUS": {
                "move": ps.JsonMove.from_operation({"op":"add", "path":"", "value": {
                    "PORT": {
                        "Ethernet200": {
                        }
                    }
                }}),
                "port_names": ["Ethernet200"],
                "expected": ps.JsonMove.from_operation({"op":"add", "path":"", "value": {
                    "PORT": {
                        "Ethernet200":{
                            "admin_status": "down",
                        }
                    }
                }}),
            },
            "REPLACE_ADMIN_STATUS": {
                "move": ps.JsonMove.from_operation({"op":"replace", "path":"/PORT/Ethernet200/admin_status", "value": "up"}),
                "port_names": ["Ethernet200"],
                "expected": ps.JsonMove.from_operation({"op":"replace", "path":"/PORT/Ethernet200/admin_status", "value": "down"})
            },
            "REPLACE_ETHERNET": {
                "move": ps.JsonMove.from_operation({"op":"replace", "path":"/PORT/Ethernet200", "value": {
                    "admin_status": "up",
                }}),
                "port_names": ["Ethernet200"],
                "expected": ps.JsonMove.from_operation({"op":"replace", "path":"/PORT/Ethernet200", "value": {
                    "admin_status": "down",
                }})
            },
            "REPLACE_PORT": {
                "move": ps.JsonMove.from_operation({"op":"replace", "path":"/PORT", "value": {
                    "Ethernet200":{
                        "admin_status": "up",
                    }
                }}),
                "port_names": ["Ethernet200"],
                "expected": ps.JsonMove.from_operation({"op":"replace", "path":"/PORT", "value": {
                    "Ethernet200":{
                        "admin_status": "down",
                    }
                }})
            },
            "REPLACE_WHOLE_CONFIG": {
                "move": ps.JsonMove.from_operation({"op":"replace", "path":"", "value": {
                    "PORT": {
                        "Ethernet200": {
                            "admin_status": "up",
                        }
                    }
                }}),
                "port_names": ["Ethernet200"],
                "expected": ps.JsonMove.from_operation({"op":"replace", "path":"", "value": {
                    "PORT": {
                        "Ethernet200":{
                            "admin_status": "down",
                        }
                    }
                }}),
            },
            "MULTIPLE_PORTS" :{
                "move": ps.JsonMove.from_operation({"op":"replace", "path":"", "value": {
                    "PORT": {
                        "Ethernet200": {
                            "admin_status": "up",
                        },
                        "Ethernet300": {
                            "admin_status": "down",
                        },
                        "Ethernet400": {
                            "admin_status": "up",
                        },
                        "Ethernet500": {
                        },
                    }
                }}),
                "port_names": ["Ethernet200", "Ethernet300", "Ethernet400", "Ethernet500"],
                "expected": ps.JsonMove.from_operation({"op":"replace", "path":"", "value": {
                    "PORT": {
                        "Ethernet200": {
                            "admin_status": "down",
                        },
                        "Ethernet300": {
                            "admin_status": "down",
                        },
                        "Ethernet400": {
                            "admin_status": "down",
                        },
                        "Ethernet500": {
                            "admin_status": "down",
                        },
                    }
                }}),
            },
        }

        for test_case_name, test_case in test_cases.items():
            with self.subTest(name=test_case_name):
                move = test_case["move"]
                port_names = test_case["port_names"]
                expected = test_case["expected"]

                path_value_tuples = [(f"/PORT/{port_name}/admin_status", "down") for port_name in port_names]

                actual = self.extender._flip(move, path_value_tuples)
                self.assertEqual(expected, actual)

class TestUpperLevelMoveExtender(unittest.TestCase):
    def setUp(self):
        self.extender = ps.UpperLevelMoveExtender()
        self.any_diff = ps.Diff(Files.ANY_CONFIG_DB, Files.ANY_CONFIG_DB)

    def test_extend__root_level_move__no_extended_moves(self):
        self.verify(OperationType.REMOVE, [])
        self.verify(OperationType.ADD, [], [])
        self.verify(OperationType.REPLACE, [], [])

    def test_extend__remove_key_upper_level_does_not_exist__remove_upper_level(self):
        self.verify(OperationType.REMOVE,
                    ["ACL_TABLE", "EVERFLOW", "policy_desc"],
                    tc_ops=[{'op':'remove', 'path':'/ACL_TABLE/EVERFLOW'}],
                    ex_ops=[{'op':'remove', 'path':'/ACL_TABLE/EVERFLOW'}])

    def test_extend__remove_key_upper_level_does_exist__replace_upper_level(self):
        self.verify(OperationType.REMOVE,
                    ["ACL_TABLE", "EVERFLOW", "policy_desc"],
                    tc_ops=[{'op':'remove', 'path':'/ACL_TABLE/EVERFLOW/policy_desc'}],
                    ex_ops=[{'op':'replace', 'path':'/ACL_TABLE/EVERFLOW', 'value':{
                        "ports": [
                            "Ethernet8"
                        ],
                        "stage": "ingress",
                        "type": "MIRROR"
                    }}])

    def test_extend__remove_list_item_upper_level_does_not_exist__remove_upper_level(self):
        self.verify(OperationType.REMOVE,
                    ["VLAN", "Vlan1000", "dhcp_servers", 1],
                    tc_ops=[{'op':'remove', 'path':'/VLAN/Vlan1000/dhcp_servers'}],
                    ex_ops=[{'op':'remove', 'path':'/VLAN/Vlan1000/dhcp_servers'}])

    def test_extend__remove_list_item_upper_level_does_exist__replace_upper_level(self):
        self.verify(OperationType.REMOVE,
                    ["VLAN", "Vlan1000", "dhcp_servers", 1],
                    tc_ops=[{'op':'remove', 'path':'/VLAN/Vlan1000/dhcp_servers/1'}],
                    ex_ops=[{'op':'replace', 'path':'/VLAN/Vlan1000/dhcp_servers', 'value':[
                        "192.0.0.1",
                        "192.0.0.3",
                        "192.0.0.4"
                    ]}])

    def test_extend__add_key_upper_level_missing__add_upper_level(self):
        self.verify(OperationType.ADD,
                    ["ACL_TABLE", "EVERFLOW", "policy_desc"],
                    ["ACL_TABLE", "EVERFLOW", "policy_desc"],
                    cc_ops=[{'op':'remove', 'path':'/ACL_TABLE/EVERFLOW'}],
                    ex_ops=[{'op':'add', 'path':'/ACL_TABLE/EVERFLOW', 'value':{
                        "policy_desc": "EVERFLOW",
                        "ports": [
                            "Ethernet8"
                        ],
                        "stage": "ingress",
                        "type": "MIRROR"
                    }}])

    def test_extend__add_key_upper_level_exist__replace_upper_level(self):
        self.verify(OperationType.ADD,
                    ["ACL_TABLE", "EVERFLOW", "policy_desc"],
                    ["ACL_TABLE", "EVERFLOW", "policy_desc"],
                    cc_ops=[{'op':'remove', 'path':'/ACL_TABLE/EVERFLOW/policy_desc'}],
                    ex_ops=[{'op':'replace', 'path':'/ACL_TABLE/EVERFLOW', 'value':{
                        "policy_desc": "EVERFLOW",
                        "ports": [
                            "Ethernet8"
                        ],
                        "stage": "ingress",
                        "type": "MIRROR"
                    }}])

    def test_extend__add_list_item_upper_level_missing__add_upper_level(self):
        self.verify(OperationType.ADD,
                    ["VLAN", "Vlan1000", "dhcp_servers", 1],
                    ["VLAN", "Vlan1000", "dhcp_servers", 1],
                    cc_ops=[{'op':'remove', 'path':'/VLAN/Vlan1000/dhcp_servers'}],
                    ex_ops=[{'op':'add', 'path':'/VLAN/Vlan1000/dhcp_servers', 'value':[
                        "192.0.0.1",
                        "192.0.0.2",
                        "192.0.0.3",
                        "192.0.0.4"
                    ]}])

    def test_extend__add_list_item_upper_level_exist__replace_upper_level(self):
        self.verify(OperationType.ADD,
                    ["VLAN", "Vlan1000", "dhcp_servers", 1],
                    ["VLAN", "Vlan1000", "dhcp_servers", 1],
                    cc_ops=[{'op':'remove', 'path':'/VLAN/Vlan1000/dhcp_servers/1'}],
                    ex_ops=[{'op':'replace', 'path':'/VLAN/Vlan1000/dhcp_servers', 'value':[
                        "192.0.0.1",
                        "192.0.0.2",
                        "192.0.0.3",
                        "192.0.0.4"
                    ]}])

    def test_extend__add_table__replace_whole_config(self):
        self.verify(OperationType.ADD,
                    ["ACL_TABLE"],
                    ["ACL_TABLE"],
                    cc_ops=[{'op':'remove', 'path':'/ACL_TABLE'}],
                    ex_ops=[{'op':'replace', 'path':'', 'value':Files.CROPPED_CONFIG_DB_AS_JSON}])

    def test_extend__replace_key__replace_upper_level(self):
        self.verify(OperationType.REPLACE,
                    ["ACL_TABLE", "EVERFLOW", "policy_desc"],
                    ["ACL_TABLE", "EVERFLOW", "policy_desc"],
                    cc_ops=[{'op':'replace', 'path':'/ACL_TABLE/EVERFLOW/policy_desc', 'value':'old_desc'}],
                    ex_ops=[{'op':'replace', 'path':'/ACL_TABLE/EVERFLOW', 'value':{
                        "policy_desc": "EVERFLOW",
                        "ports": [
                            "Ethernet8"
                        ],
                        "stage": "ingress",
                        "type": "MIRROR"
                    }}])

    def test_extend__replace_list_item__replace_upper_level(self):
        self.verify(OperationType.REPLACE,
                    ["VLAN", "Vlan1000", "dhcp_servers", 1],
                    ["VLAN", "Vlan1000", "dhcp_servers", 1],
                    cc_ops=[{'op':'replace', 'path':'/VLAN/Vlan1000/dhcp_servers/1', 'value':'192.0.0.7'}],
                    ex_ops=[{'op':'replace', 'path':'/VLAN/Vlan1000/dhcp_servers', 'value':[
                        "192.0.0.1",
                        "192.0.0.2",
                        "192.0.0.3",
                        "192.0.0.4"
                    ]}])

    def test_extend__replace_table__replace_whole_config(self):
        self.verify(OperationType.REPLACE,
                    ["VLAN"],
                    ["VLAN"],
                    cc_ops=[{'op':'replace', 'path':'/VLAN/Vlan1000/dhcp_servers/1', 'value':'192.0.0.7'}],
                    ex_ops=[{'op':'replace', 'path':'', 'value':Files.CROPPED_CONFIG_DB_AS_JSON}])

    def test_extend__remove_table_while_config_has_only_that_table__replace_whole_config_with_empty_config(self):
        self.verify(OperationType.REMOVE,
                    ["VLAN"],
                    ["VLAN"],
                    cc_ops=[{'op':'replace', 'path':'', 'value':{'VLAN':{}}}],
                    tc_ops=[{'op':'replace', 'path':'', 'value':{}}],
                    ex_ops=[{'op':'replace', 'path':'', 'value':{}}])

    def verify(self, op_type, ctokens, ttokens=None, cc_ops=[], tc_ops=[], ex_ops=[]):
        """
        cc_ops, tc_ops are used to build the diff object.
        diff, op_type, ctokens, ttokens  are used to build the move.
        move is extended and the result should match ex_ops.
        """
        # Arrange
        current_config=jsonpatch.JsonPatch(cc_ops).apply(Files.CROPPED_CONFIG_DB_AS_JSON)
        target_config=jsonpatch.JsonPatch(tc_ops).apply(Files.CROPPED_CONFIG_DB_AS_JSON)
        diff = ps.Diff(current_config, target_config)
        move = ps.JsonMove(diff, op_type, ctokens, ttokens)

        # Act
        moves = self.extender.extend(move, diff)

        # Assert
        self.verify_moves(ex_ops, moves)

    def verify_moves(self, ex_ops, moves):
        moves_ops = [list(move.patch)[0] for move in moves]
        self.assertCountEqual(ex_ops, moves_ops)

class TestDeleteInsteadOfReplaceMoveExtender(unittest.TestCase):
    def setUp(self):
        self.extender = ps.DeleteInsteadOfReplaceMoveExtender()

    def test_extend__non_replace__no_extended_moves(self):
        self.verify(OperationType.REMOVE,
                    ["ACL_TABLE"],
                    tc_ops=[{'op':'remove', 'path':'/ACL_TABLE'}],
                    ex_ops=[])
        self.verify(OperationType.ADD,
                    ["ACL_TABLE"],
                    ["ACL_TABLE"],
                    cc_ops=[{'op':'remove', 'path':'/ACL_TABLE'}],
                    ex_ops=[])

    def test_extend__replace_key__delete_key(self):
        self.verify(OperationType.REPLACE,
                    ["ACL_TABLE", "EVERFLOW", "policy_desc"],
                    ["ACL_TABLE", "EVERFLOW", "policy_desc"],
                    cc_ops=[{'op':'replace', 'path':'/ACL_TABLE/EVERFLOW/policy_desc', 'value':'old_desc'}],
                    ex_ops=[{'op':'remove', 'path':'/ACL_TABLE/EVERFLOW/policy_desc'}])

    def test_extend__replace_list_item__delete_list_item(self):
        self.verify(OperationType.REPLACE,
                    ["VLAN", "Vlan1000", "dhcp_servers", 1],
                    ["VLAN", "Vlan1000", "dhcp_servers", 1],
                    cc_ops=[{'op':'replace', 'path':'/VLAN/Vlan1000/dhcp_servers/1', 'value':'192.0.0.7'}],
                    ex_ops=[{'op':'remove', 'path':'/VLAN/Vlan1000/dhcp_servers/1'}])

    def test_extend__replace_table__delete_table(self):
        self.verify(OperationType.REPLACE,
                    ["ACL_TABLE"],
                    ["ACL_TABLE"],
                    cc_ops=[{'op':'replace', 'path':'/ACL_TABLE/EVERFLOW/policy_desc', 'value':'old_desc'}],
                    ex_ops=[{'op':'remove', 'path':'/ACL_TABLE'}])

    def test_extend__replace_whole_config__no_moves(self):
        self.verify(OperationType.REPLACE,
                    [],
                    [],
                    cc_ops=[{'op':'replace', 'path':'/ACL_TABLE/EVERFLOW/policy_desc', 'value':'old_desc'}],
                    ex_ops=[])

    def verify(self, op_type, ctokens, ttokens=None, cc_ops=[], tc_ops=[], ex_ops=[]):
        """
        cc_ops, tc_ops are used to build the diff object.
        diff, op_type, ctokens, ttokens  are used to build the move.
        move is extended and the result should match ex_ops.
        """
        # Arrange
        current_config=jsonpatch.JsonPatch(cc_ops).apply(Files.CROPPED_CONFIG_DB_AS_JSON)
        target_config=jsonpatch.JsonPatch(tc_ops).apply(Files.CROPPED_CONFIG_DB_AS_JSON)
        diff = ps.Diff(current_config, target_config)
        move = ps.JsonMove(diff, op_type, ctokens, ttokens)

        # Act
        moves = self.extender.extend(move, diff)

        # Assert
        self.verify_moves(ex_ops, moves)

    def verify_moves(self, ex_ops, moves):
        moves_ops = [list(move.patch)[0] for move in moves]
        self.assertCountEqual(ex_ops, moves_ops)

class DeleteRefsMoveExtender(unittest.TestCase):
    def setUp(self):
        self.extender = ps.DeleteRefsMoveExtender(PathAddressing(ConfigWrapper()))

    def test_extend__non_delete_ops__no_extended_moves(self):
        self.verify(OperationType.ADD,
                    ["ACL_TABLE"],
                    ["ACL_TABLE"],
                    cc_ops=[{'op':'remove', 'path':'/ACL_TABLE'}],
                    ex_ops=[])
        self.verify(OperationType.REPLACE,
                    ["ACL_TABLE"],
                    ["ACL_TABLE"],
                    cc_ops=[{'op':'remove', 'path':'/ACL_TABLE/EVERFLOW'}],
                    ex_ops=[])

    def test_extend__path_with_no_refs__no_extended_moves(self):
        self.verify(OperationType.REMOVE,
                    ["ACL_TABLE"],
                    tc_ops=[{'op':'remove', 'path':'/ACL_TABLE'}],
                    ex_ops=[])

    def test_extend__path_with_direct_refs__extended_moves(self):
        self.verify(OperationType.REMOVE,
                    ["PORT", "Ethernet0"],
                    tc_ops=[{'op':'remove', 'path':'/PORT/Ethernet0'}],
                    ex_ops=[{'op': 'remove', 'path': '/VLAN_MEMBER/Vlan1000|Ethernet0'},
                            {'op': 'remove', 'path': '/ACL_TABLE/NO-NSW-PACL-V4/ports/0'}])

    def test_extend__path_with_refs_to_children__extended_moves(self):
        self.verify(OperationType.REMOVE,
                    ["PORT"],
                    tc_ops=[{'op':'remove', 'path':'/PORT/Ethernet0'}],
                    ex_ops=[{'op': 'remove', 'path': '/VLAN_MEMBER/Vlan1000|Ethernet0'},
                            {'op': 'remove', 'path': '/ACL_TABLE/NO-NSW-PACL-V4/ports/0'},
                            {'op': 'remove', 'path': '/VLAN_MEMBER/Vlan1000|Ethernet4'},
                            {'op': 'remove', 'path': '/ACL_TABLE/DATAACL/ports/0'},
                            {'op': 'remove', 'path': '/VLAN_MEMBER/Vlan1000|Ethernet8'},
                            {'op': 'remove', 'path': '/ACL_TABLE/EVERFLOWV6/ports/0'},
                            {'op': 'remove', 'path': '/ACL_TABLE/EVERFLOW/ports/0'},
                            {'op': 'remove', 'path': '/ACL_TABLE/EVERFLOWV6/ports/1'}])

    def verify(self, op_type, ctokens, ttokens=None, cc_ops=[], tc_ops=[], ex_ops=[]):
        """
        cc_ops, tc_ops are used to build the diff object.
        diff, op_type, ctokens, ttokens  are used to build the move.
        move is extended and the result should match ex_ops.
        """
        # Arrange
        current_config=jsonpatch.JsonPatch(cc_ops).apply(Files.CROPPED_CONFIG_DB_AS_JSON)
        target_config=jsonpatch.JsonPatch(tc_ops).apply(Files.CROPPED_CONFIG_DB_AS_JSON)
        diff = ps.Diff(current_config, target_config)
        move = ps.JsonMove(diff, op_type, ctokens, ttokens)

        # Act
        moves = self.extender.extend(move, diff)

        # Assert
        self.verify_moves(ex_ops, moves)

    def verify_moves(self, ex_ops, moves):
        moves_ops = [list(move.patch)[0] for move in moves]
        self.assertCountEqual(ex_ops, moves_ops)

class TestSortAlgorithmFactory(unittest.TestCase):
    def test_dfs_sorter(self):
        self.verify(ps.Algorithm.DFS, ps.DfsSorter)

    def test_bfs_sorter(self):
        self.verify(ps.Algorithm.BFS, ps.BfsSorter)

    def test_memoization_sorter(self):
        self.verify(ps.Algorithm.MEMOIZATION, ps.MemoizationSorter)

    def verify(self, algo, algo_class):
        # Arrange
        config_wrapper = ConfigWrapper()
        factory = ps.SortAlgorithmFactory(OperationWrapper(), config_wrapper, PathAddressing(config_wrapper))
        expected_generators = [ps.RemoveCreateOnlyDependencyMoveGenerator,
                               ps.LowLevelMoveGenerator]
        expected_non_extendable_generators = [ps.KeyLevelMoveGenerator]
        expected_extenders = [ps.RequiredValueMoveExtender,
                              ps.UpperLevelMoveExtender,
                              ps.DeleteInsteadOfReplaceMoveExtender,
                              ps.DeleteRefsMoveExtender]
        expected_validator = [ps.DeleteWholeConfigMoveValidator,
                              ps.FullConfigMoveValidator,
                              ps.NoDependencyMoveValidator,
                              ps.CreateOnlyMoveValidator,
                              ps.RequiredValueMoveValidator,
                              ps.RemoveCreateOnlyDependencyMoveValidator,
                              ps.NoEmptyTableMoveValidator,
                              ps.VNETAssociationChangeValidator]

        # Act
        sorter = factory.create(algo)
        actual_generators = [type(item) for item in sorter.move_wrapper.move_generators]
        actual_non_extendable_generators = [type(item) for item in sorter.move_wrapper.move_non_extendable_generators]
        actual_extenders = [type(item) for item in sorter.move_wrapper.move_extenders]
        actual_validators = [type(item) for item in sorter.move_wrapper.move_validators]

        # Assert
        self.assertIsInstance(sorter, algo_class)
        self.assertCountEqual(expected_generators, actual_generators)
        self.assertCountEqual(expected_non_extendable_generators, actual_non_extendable_generators)
        self.assertCountEqual(expected_extenders, actual_extenders)
        self.assertCountEqual(expected_validator, actual_validators)

class TestPatchSorter(unittest.TestCase):
    def setUp(self):
        self.config_wrapper = ConfigWrapper()

    def test_patch_sorter_success(self):
        # Format of the JSON file containing the test-cases:
        #
        # {
        #     "<unique_name_for_the_test>":{
        #         "desc":"<brief explanation of the test case>",
        #         "current_config":<the running config to be modified>,
        #         "patch":<the JsonPatch to apply>,
        #         "expected_changes":[<list of expected changes after sorting>]
        #     },
        #     .
        #     .
        #     .
        # }
        data = Files.PATCH_SORTER_TEST_SUCCESS
        skip_exact_change_list_match = False
        for test_case_name in data:
            with self.subTest(name=test_case_name):
                self.run_single_success_case(data[test_case_name], skip_exact_change_list_match)

    def run_single_success_case(self, data, skip_exact_change_list_match):
        current_config = data["current_config"]
        patch = jsonpatch.JsonPatch(data["patch"])
        expected_changes = []
        for item in data["expected_changes"]:
            expected_changes.append(JsonChange(jsonpatch.JsonPatch(item)))

        sorter = self.create_patch_sorter(current_config)

        actual_changes = sorter.sort(patch)

        if not skip_exact_change_list_match:
            self.assertEqual(expected_changes, actual_changes)

        target_config = patch.apply(current_config)
        simulated_config = current_config
        for change in actual_changes:
            simulated_config = change.apply(simulated_config)
            is_valid, error = self.config_wrapper.validate_config_db_config(simulated_config)
            self.assertTrue(is_valid, f"Change will produce invalid config. Error: {error}")
        self.assertEqual(target_config, simulated_config)

    def test_patch_sorter_failure(self):
        # Format of the JSON file containing the test-cases:
        #
        # {
        #     "<unique_name_for_the_test>":{
        #         "desc":"<brief explanation of the test case>",
        #         "current_config":<the running config to be modified>,
        #         "patch":<the JsonPatch to apply>,
        #         "expected_error_substrings":[<list of expected error substrings>]
        #     },
        #     .
        #     .
        #     .
        # }
        data = Files.PATCH_SORTER_TEST_FAILURE
        for test_case_name in data:
            with self.subTest(name=test_case_name):
                self.run_single_failure_case(data[test_case_name])

    def run_single_failure_case(self, data):
        current_config = data["current_config"]
        patch = jsonpatch.JsonPatch(data["patch"])
        expected_error_substrings = data["expected_error_substrings"]

        try:
            sorter = self.create_patch_sorter(current_config)
            sorter.sort(patch)
            self.fail("An exception was supposed to be thrown")
        except Exception as ex:
            notfound_substrings = []
            error = str(ex)
            for substring in expected_error_substrings:
                if substring not in error:
                    notfound_substrings.append(substring)

            if notfound_substrings:
                self.fail(f"Did not find the substrings {notfound_substrings} in the error: '{error}'")

    def test_sort__does_not_remove_tables_without_yang_unintentionally_if_generated_change_replaces_whole_config(self):
        # Arrange
        current_config = Files.CONFIG_DB_AS_JSON # has a table without yang named 'TABLE_WITHOUT_YANG'
        any_patch = Files.SINGLE_OPERATION_CONFIG_DB_PATCH
        target_config = any_patch.apply(current_config)
        sort_algorithm = Mock()
        sort_algorithm.sort = lambda diff: [ps.JsonMove(diff, OperationType.REPLACE, [], [])]
        patch_sorter = self.create_patch_sorter(current_config, sort_algorithm)
        expected = [JsonChange(jsonpatch.JsonPatch([OperationWrapper().create(OperationType.REPLACE, "", target_config)]))]

        # Act
        actual = patch_sorter.sort(any_patch)

        # Assert
        self.assertEqual(expected, actual)

    def create_patch_sorter(self, config=None, sort_algorithm=None):
        if config is None:
            config=Files.CROPPED_CONFIG_DB_AS_JSON
        config_wrapper = self.config_wrapper
        config_wrapper.get_config_db_as_json = MagicMock(return_value=config)
        patch_wrapper = PatchWrapper(config_wrapper)
        operation_wrapper = OperationWrapper()
        path_addressing= ps.PathAddressing(config_wrapper)
        sort_algorithm_factory = ps.SortAlgorithmFactory(operation_wrapper, config_wrapper, path_addressing)
        if sort_algorithm:
            sort_algorithm_factory.create = MagicMock(return_value=sort_algorithm)

        return ps.PatchSorter(config_wrapper, patch_wrapper, sort_algorithm_factory)

class TestChangeWrapper(unittest.TestCase):
    def setUp(self):
        config_splitter = ps.ConfigSplitter(ConfigWrapper(), [])
        self.wrapper = ps.ChangeWrapper(PatchWrapper(), config_splitter)

    def test_adjust_changes(self):
        def check(changes, assumed, remaining, expected):
            actual = self.wrapper.adjust_changes(changes, assumed, remaining)
            self.assertEqual(len(expected), len(actual))

            for idx in range(len(expected)):
                self.assertCountEqual(expected[idx].patch, actual[idx].patch, f"JsonChange idx {idx} did not match")

        check([], {}, {}, [])
        # Add table to empty config
        check(changes=[JsonChange(jsonpatch.JsonPatch([{"op":"add", "path":"/TABLE1", "value":{}}]))],
              assumed={},
              remaining={},
              expected=[JsonChange(jsonpatch.JsonPatch([{"op":"add", "path":"/TABLE1", "value":{}}]))])
        # Add table, while tables exist in assumed and remaining
        check(changes=[JsonChange(jsonpatch.JsonPatch([{"op":"add", "path":"/TABLE3", "value":{}}]))],
              assumed={"TABLE1":{}},
              remaining={"TABLE2":{}},
              expected=[JsonChange(jsonpatch.JsonPatch([{"op":"add", "path":"/TABLE3", "value":{}}]))])
        # Add table with single field, while table has multiple fields in remaining
        check(changes=[JsonChange(jsonpatch.JsonPatch([{"op":"add", "path":"/TABLE3", "value":{"key3":"value3"}}]))],
              assumed={"TABLE1":{}},
              remaining={"TABLE2":{}, "TABLE3":{"key1":"value1", "key2":"value2"}},
              expected=[JsonChange(jsonpatch.JsonPatch([{"op":"add", "path":"/TABLE3/key3", "value":"value3"}]))])
        # Remove table to empty the config
        check(changes=[JsonChange(jsonpatch.JsonPatch([{"op":"remove", "path":"/TABLE1"}]))],
              assumed={"TABLE1":{}},
              remaining={},
              expected=[JsonChange(jsonpatch.JsonPatch([{"op":"remove", "path":"/TABLE1"}]))])
        # Remove table, while other tables exist in assumed and remaining
        check(changes=[JsonChange(jsonpatch.JsonPatch([{"op":"remove", "path":"/TABLE3"}]))],
              assumed={"TABLE1":{}, "TABLE3":{}},
              remaining={"TABLE2":{}},
              expected=[JsonChange(jsonpatch.JsonPatch([{"op":"remove", "path":"/TABLE3"}]))])
        # Remove table with single field, while table has multiple fields in remaining
        check(changes=[JsonChange(jsonpatch.JsonPatch([{"op":"remove", "path":"/TABLE3"}]))],
              assumed={"TABLE1":{}, "TABLE3":{"key3":"value3"}},
              remaining={"TABLE2":{}, "TABLE3":{"key1":"value1", "key2":"value2"}},
              expected=[JsonChange(jsonpatch.JsonPatch([{"op":"remove", "path":"/TABLE3/key3"}]))])
        # Change that does nothing
        check(changes=[JsonChange(jsonpatch.JsonPatch([{"op":"replace", "path":"/TABLE1", "value":{}}]))],
              assumed={"TABLE1":{}},
              remaining={},
              expected=[JsonChange(jsonpatch.JsonPatch([]))])
        # Replace table that exist in remaining
        check(changes=[JsonChange(jsonpatch.JsonPatch(
                      [{"op":"replace", "path":"/TABLE2", "value":{"key3":"value3", "key4":"value4"}}]))],
              assumed={"TABLE1":{}, "TABLE2":{}},
              remaining={"TABLE2":{"key1":"value1", "key2":"value2"}},
              expected=[JsonChange(jsonpatch.JsonPatch(
                        [{"op":"add", "path":"/TABLE2/key3", "value":"value3"},
                         {"op":"add", "path":"/TABLE2/key4", "value":"value4"}]))])
        # Multiple changes
        check(changes=[JsonChange(jsonpatch.JsonPatch([{"op":"replace", "path":"/TABLE1", "value":{}}])),
                       JsonChange(jsonpatch.JsonPatch([{"op":"add", "path":"/TABLE3", "value":{"key34":"value34"}}])),
                       JsonChange(jsonpatch.JsonPatch([{"op":"replace", "path":"/TABLE3", "value":{}}])),
                       JsonChange(jsonpatch.JsonPatch([{"op":"add", "path":"/TABLE3/key33", "value":"value33"}])),
                       JsonChange(jsonpatch.JsonPatch([{"op":"remove", "path":"/TABLE3"}]))],
              assumed={"TABLE1":{},"TABLE3":{}},
              remaining={"TABLE3":{"key31":"value31", "key32":"value32"}},
              expected=[JsonChange(jsonpatch.JsonPatch([])),
                        JsonChange(jsonpatch.JsonPatch([{"op":"add", "path":"/TABLE3/key34", "value":"value34"}])),
                        JsonChange(jsonpatch.JsonPatch([{"op":"remove", "path":"/TABLE3/key34"}])),
                        JsonChange(jsonpatch.JsonPatch([{"op":"add", "path":"/TABLE3/key33", "value":"value33"}])),
                        JsonChange(jsonpatch.JsonPatch([{"op":"remove", "path":"/TABLE3/key33"}]))])

class TestConfigSplitter(unittest.TestCase):
    def test_split_yang_non_yang_distinct_field_path(self):
        def check(config, expected_yang, expected_non_yang, ignore_paths_list=[], ignore_tables_without_yang=False):
            config_wrapper = ConfigWrapper()
            inner_config_splitters = []
            if ignore_tables_without_yang:
                inner_config_splitters.append(ps.TablesWithoutYangConfigSplitter(config_wrapper))
            if ignore_paths_list:
                inner_config_splitters.append(ps.IgnorePathsFromYangConfigSplitter(ignore_paths_list, config_wrapper))

            # ConfigWrapper() loads yang models from YANG_DIR
            splitter = ps.ConfigSplitter(ConfigWrapper(), inner_config_splitters)
            actual_yang, actual_non_yang = splitter.split_yang_non_yang_distinct_field_path(config)

            self.assertDictEqual(expected_yang, actual_yang)
            self.assertDictEqual(expected_non_yang, actual_non_yang)

        # test no flags
        check({}, {}, {})
        check(config={"ACL_TABLE":{"key1":"value1"}, "NON_YANG":{"key2":"value2"}, "VLAN":{"key31":"value31"}, "ANOTHER_NON_YANG":{"key41":"value41"}},
              expected_yang={"ACL_TABLE":{"key1":"value1"}, "VLAN":{"key31":"value31"}, "NON_YANG":{"key2":"value2"}, "ANOTHER_NON_YANG":{"key41":"value41"}},
              expected_non_yang={})

        # test ignore_tables_without_yang
        check({}, {}, {}, [], True)
        self.assertRaises(ValueError, check, {"ACL_TABLE":{}}, {"ACL_TABLE":{}}, {}, [], True) # ACL_TABLE has YANG model
        check({"ACL_TABLE":{"key1":"value1"}}, {"ACL_TABLE":{"key1":"value1"}}, {}, [], True)
        self.assertRaises(ValueError, check, {"ACL_TABLE":{}, "NON_YANG":{}}, {"ACL_TABLE":{}}, {"NON_YANG":{}},[], True)
        check(config={"ACL_TABLE":{"key1":"value1"}, "NON_YANG":{"key2":"value2"}, "VLAN":{"key31":"value31"}, "ANOTHER_NON_YANG":{"key41":"value41"}},
              expected_yang={"ACL_TABLE":{"key1":"value1"}, "VLAN":{"key31":"value31"}},
              expected_non_yang={"NON_YANG":{"key2":"value2"}, "ANOTHER_NON_YANG":{"key41":"value41"}},
              ignore_tables_without_yang=True)

        # test ignore_paths_list
        check({}, {}, {}, [""])
        self.assertRaises(ValueError, check, {"ACL_TABLE":{}}, {"ACL_TABLE":{}}, {}, ["/VLAN"]) # VLAN has YANG model
        self.assertRaises(ValueError, check, {"ACL_TABLE":{}}, {}, {"ACL_TABLE":{}}, ["/ACL_TABLE"])
        check({"ACL_TABLE":{"key1":"value1"}}, {}, {"ACL_TABLE":{"key1":"value1"}}, ["/ACL_TABLE"])
        check({"ACL_TABLE":{"key1":"value1"}}, {}, {"ACL_TABLE":{"key1":"value1"}}, ["/ACL_TABLE/key1"])
        check(config={"NON_YANG":{"key1":"value1"},"ACL_TABLE":{"key2":"value2"}},
              expected_yang={"NON_YANG":{"key1":"value1"}},
              expected_non_yang={"ACL_TABLE":{"key2":"value2"}},
              ignore_paths_list= ["/ACL_TABLE"])
        check(config={"ACL_TABLE":{"key1":"value1"}, "VLAN":{"key31":"value31"}, "NON_YANG":{"key2":"value2"}, "ANOTHER_NON_YANG":{"key41":"value41"}},
              expected_yang={"NON_YANG":{"key2":"value2"}, "ANOTHER_NON_YANG":{"key41":"value41"}},
              expected_non_yang={"ACL_TABLE":{"key1":"value1"}, "VLAN":{"key31":"value31"}},
              ignore_paths_list=["/VLAN/key31", "/ACL_TABLE"])
        check(config={"ACL_TABLE":{"key1":"value1"}, "NON_YANG":{"key2":"value2"}, "VLAN":{"key31":"value31"}, "ANOTHER_NON_YANG":{"key41":"value41"}},
              expected_yang={},
              expected_non_yang={"ACL_TABLE":{"key1":"value1"}, "VLAN":{"key31":"value31"}, "NON_YANG":{"key2":"value2"}, "ANOTHER_NON_YANG":{"key41":"value41"}},
              ignore_paths_list=["/VLAN/key31", "", "/ACL_TABLE"])

        # test ignore_paths_list and ignore_tables_without_yang
        check({}, {}, {}, [""])
        self.assertRaises(ValueError, check, {"ACL_TABLE":{}}, {"ACL_TABLE":{}}, {}, ["/VLAN"], True) # VLAN has YANG model
        self.assertRaises(ValueError, check, {"ACL_TABLE":{}}, {}, {"ACL_TABLE":{}}, ["/ACL_TABLE"], True)
        check({"ACL_TABLE":{"key1":"value1"}}, {}, {"ACL_TABLE":{"key1":"value1"}}, ["/ACL_TABLE"], True)
        check({"ACL_TABLE":{"key1":"value1"}}, {}, {"ACL_TABLE":{"key1":"value1"}}, ["/ACL_TABLE/key1"], True)
        check(config={"NON_YANG":{"key1":"value1"},"ACL_TABLE":{"key2":"value2"}},
              expected_yang={},
              expected_non_yang={"NON_YANG":{"key1":"value1"},"ACL_TABLE":{"key2":"value2"}},
              ignore_paths_list= ["/ACL_TABLE"],
              ignore_tables_without_yang=True)
        check(config={"ACL_TABLE":{"key1":"value1"}, "NON_YANG":{"key2":"value2"}, "VLAN":{"key31":"value31"}, "ANOTHER_NON_YANG":{"key41":"value41"}},
              expected_yang={},
              expected_non_yang={"ACL_TABLE":{"key1":"value1"}, "VLAN":{"key31":"value31"}, "NON_YANG":{"key2":"value2"}, "ANOTHER_NON_YANG":{"key41":"value41"}},
              ignore_paths_list=["/VLAN/key31", "/ACL_TABLE"],
              ignore_tables_without_yang=True)
        check(config={"ACL_TABLE":{"key1":"value1"}, "NON_YANG":{"key2":"value2"}, "VLAN":{"key31":"value31"}, "ANOTHER_NON_YANG":{"key41":"value41"}},
              expected_yang={},
              expected_non_yang={"ACL_TABLE":{"key1":"value1"}, "VLAN":{"key31":"value31"}, "NON_YANG":{"key2":"value2"}, "ANOTHER_NON_YANG":{"key41":"value41"}},
              ignore_paths_list=["/VLAN/key31", "", "/ACL_TABLE"],
              ignore_tables_without_yang=True)

    def test_merge_configs_with_distinct_field_path(self):
        def check(config1, config2, expected=None):
            splitter = ps.ConfigSplitter(ConfigWrapper(), [])

            # merging config1 and config2
            actual = splitter.merge_configs_with_distinct_field_path(config1, config2)
            self.assertDictEqual(expected, actual)

            # merging config2 and config1 - should be the same result
            actual = splitter.merge_configs_with_distinct_field_path(config2, config1)
            self.assertDictEqual(expected, actual)

        check({}, {}, {})
        check({"TABLE1":{}}, {}, {"TABLE1":{}})
        check({"TABLE1":{}}, {"TABLE2": {}}, {"TABLE1":{}, "TABLE2":{}})
        check({"TABLE1":{"key1": "value1"}}, {}, {"TABLE1":{"key1": "value1"}})
        check({"TABLE1":{"key1": "value1"}}, {"TABLE1":{}}, {"TABLE1":{"key1": "value1"}})
        check({"TABLE1":{"key1": "value1"}},
              {"TABLE1":{"key2": "value2"}},
              {"TABLE1":{"key1": "value1", "key2": "value2"}})
        # keys the same
        self.assertRaises(ValueError, check, {"TABLE1":{"key1": "value1"}}, {"TABLE1":{"key1": "value2"}})

class TestNonStrictPatchSorter(unittest.TestCase):
    def test_sort__invalid_yang_covered_config__failure(self):
        # Arrange
        sorter = self.__create_patch_sorter(valid_yang_covered_config=False)

        # Act and assert
        self.assertRaises(ValueError, sorter.sort, Files.MULTI_OPERATION_CONFIG_DB_PATCH)

    def test_sort__invalid_yang_covered_config_patch_updating_tables_without_yang__failure(self):
        # Arrange
        sorter = self.__create_patch_sorter(valid_patch_only_tables_with_yang_models=False)

        # Act and assert
        self.assertRaises(ValueError, sorter.sort, Files.MULTI_OPERATION_CONFIG_DB_PATCH)

    def test_sort__no_errors_algorithm_specified__calls_inner_patch_sorter(self):
        # Arrange
        patch = Mock()
        algorithm = Mock()
        non_yang_changes = [Mock()]
        yang_changes = [Mock(), Mock()]
        expected = non_yang_changes + yang_changes
        sorter = self.__create_patch_sorter(patch, algorithm, non_yang_changes, yang_changes)

        # Act
        actual = sorter.sort(patch, algorithm)

        # Assert
        self.assertListEqual(expected, actual)

    def test_sort__no_errors_algorithm_not_specified__calls_inner_patch_sorter(self):
        # Arrange
        patch = Mock()
        non_yang_changes = [Mock()]
        yang_changes = [Mock(), Mock()]
        expected = non_yang_changes + yang_changes
        sorter = self.__create_patch_sorter(patch, None, non_yang_changes, yang_changes)

        # Act
        actual = sorter.sort(patch)

        # Assert
        self.assertListEqual(expected, actual)

    def __create_patch_sorter(self,
                              patch=None,
                              any_algorithm=None,
                              any_adjusted_changes_non_yang=None,
                              any_adjusted_changes_yang=None,
                              valid_yang_covered_config=True,
                              valid_patch_only_tables_with_yang_models=True):
        ignore_paths_list = Mock()
        config_wrapper = Mock()
        patch_wrapper = Mock()
        inner_patch_sorter = Mock()
        change_wrapper = Mock()
        config_splitter = Mock()

        patch = patch if patch else Mock()
        any_algorithm = any_algorithm if any_algorithm else ps.Algorithm.DFS
        any_current_config = Mock()
        any_target_config = Mock()
        any_current_config_yang = Mock()
        any_current_config_non_yang = Mock()
        any_target_config_yang = Mock()
        any_target_config_non_yang = Mock()
        any_patch_non_yang = jsonpatch.JsonPatch([{"op":"add", "path":"/NON_YANG_TABLE", "value":{}}])
        any_patch_yang = Mock()
        any_changes_yang = [Mock()]
        any_changes_non_yang = [JsonChange(any_patch_non_yang)]

        config_wrapper.get_config_db_as_json.side_effect = \
            [any_current_config]

        patch_wrapper.simulate_patch.side_effect = \
            create_side_effect_dict(
                {(str(patch), str(any_current_config)):
                    any_target_config})

        config_splitter.split_yang_non_yang_distinct_field_path.side_effect = \
            create_side_effect_dict(
                {(str(any_current_config),): (any_current_config_yang, any_current_config_non_yang),
                 (str(any_target_config),): (any_target_config_yang, any_target_config_non_yang)})

        config_wrapper.validate_config_db_config.side_effect = \
            create_side_effect_dict({(str(any_target_config_yang),): (valid_yang_covered_config, None)})

        patch_wrapper.generate_patch.side_effect = \
            create_side_effect_dict(
                {(str(any_current_config_non_yang), str(any_target_config_non_yang)): any_patch_non_yang,
                 (str(any_current_config_yang), str(any_target_config_yang)): any_patch_yang})

        patch_wrapper.validate_config_db_patch_has_yang_models.side_effect = \
            create_side_effect_dict(
                {(str(any_patch_yang),): valid_patch_only_tables_with_yang_models})

        inner_patch_sorter.sort.side_effect = \
            create_side_effect_dict(
                {(str(any_patch_yang), str(any_algorithm), str(any_current_config_yang)): any_changes_yang})

        change_wrapper.adjust_changes.side_effect = \
            create_side_effect_dict(
                {(str(any_changes_non_yang), str(any_current_config_non_yang), str(any_current_config_yang)): any_adjusted_changes_non_yang,
                 (str(any_changes_yang), str(any_current_config_yang), str(any_target_config_non_yang)): any_adjusted_changes_yang})

        return ps.NonStrictPatchSorter(config_wrapper, patch_wrapper, config_splitter, change_wrapper, inner_patch_sorter)

class TestStrictPatchSorter(unittest.TestCase):
    def test_sort__patch_updating_tables_without_yang__failure(self):
        # Arrange
        patch = Mock()
        sorter = self.__create_patch_sorter(patch, valid_patch_only_tables_with_yang_models=False)

        # Act and assert
        self.assertRaises(ValueError, sorter.sort, patch)

    def test_sort__target_config_not_valid_according_to_yang__failure(self):
        # Arrange
        patch = Mock()
        sorter = self.__create_patch_sorter(patch, valid_config_db=False)

        # Act and assert
        self.assertRaises(ValueError, sorter.sort, patch)

    def test_sort__no_errors_algorithm_specified__calls_inner_patch_sorter(self):
        # Arrange
        patch = Mock()
        algorithm = Mock()
        changes = [Mock(), Mock(), Mock()]
        sorter = self.__create_patch_sorter(patch, algorithm, changes)

        # Act
        actual = sorter.sort(patch, algorithm)

        # Assert
        self.assertListEqual(changes, actual)

    def test_sort__no_errors_algorithm_not_specified__calls_inner_patch_sorter(self):
        # Arrange
        patch = Mock()
        changes = [Mock(), Mock(), Mock()]
        sorter = self.__create_patch_sorter(patch, None, changes)

        # Act
        actual = sorter.sort(patch)

        # Assert
        self.assertListEqual(changes, actual)

    def __create_patch_sorter(self,
                              patch=None,
                              algorithm=None,
                              changes=None,
                              valid_patch_only_tables_with_yang_models=True,
                              valid_config_db=True):
        config_wrapper = Mock()
        patch_wrapper = Mock()
        inner_patch_sorter = Mock()

        any_current_config = Mock()
        any_target_config = Mock()
        patch = patch if patch else Mock()
        algorithm = algorithm if algorithm else ps.Algorithm.DFS

        config_wrapper.get_config_db_as_json.side_effect = \
            [any_current_config, any_target_config]

        patch_wrapper.simulate_patch.side_effect = \
            create_side_effect_dict(
                {(str(patch), str(any_current_config)):
                    any_target_config})

        patch_wrapper.validate_config_db_patch_has_yang_models.side_effect = \
            create_side_effect_dict(
                {(str(patch),): valid_patch_only_tables_with_yang_models})

        config_wrapper.validate_config_db_config.side_effect = \
            create_side_effect_dict(
                {(str(any_target_config),): (valid_config_db, None)})


        inner_patch_sorter.sort.side_effect = \
            create_side_effect_dict(
                {(str(patch), str(algorithm)): changes})

        return ps.StrictPatchSorter(config_wrapper, patch_wrapper, inner_patch_sorter)
