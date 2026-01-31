import unittest
from generic_config_updater.patch_sorter import JsonMove


class TestJsonMoveGetValue(unittest.TestCase):
    def setUp(self):
        self.config = {
            "table1": {
                "key1": {
                    "field": "value1"
                },
                "1": {
                    "field": "value2"
                }
            },
            "table2": [
                {"name": "item0"},
                {"name": "item1"}
            ]
        }

    def test_get_value_dict(self):
        tokens = ["table1", "key1", "field"]
        self.assertEqual(JsonMove._get_value(self.config, tokens), "value1")

    def test_get_value_dict_numeric_string(self):
        tokens = ["table1", "1", "field"]
        self.assertEqual(JsonMove._get_value(self.config, tokens), "value2")

    def test_get_value_list(self):
        tokens = ["table2", 1, "name"]
        with self.assertRaises(TypeError):
            JsonMove._get_value(self.config, tokens)
        # Should use string index for list
        tokens = ["table2", "1", "name"]
        self.assertEqual(JsonMove._get_value(self.config, tokens), "item1")

    def test_get_value_missing_key(self):
        tokens = ["table1", "not_exist"]
        with self.assertRaises(KeyError):
            JsonMove._get_value(self.config, tokens)

    def test_get_value_list_invalid_index(self):
        tokens = ["table2", "10", "name"]
        with self.assertRaises(IndexError):
            JsonMove._get_value(self.config, tokens)

    def test_get_value_non_container(self):
        tokens = ["table1", "key1", "field", "extra"]
        with self.assertRaises(TypeError):
            JsonMove._get_value(self.config, tokens)
