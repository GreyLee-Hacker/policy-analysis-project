import unittest
from src.core.analyzers import analyze_policy_data

class TestAnalyzers(unittest.TestCase):

    def test_analyze_policy_data(self):
        # Sample input data for testing
        sample_data = {
            "policy_object": "公共租赁住房（公租房）",
            "policy_stage": "需求端",
            "policy_type": "激励型",
            "policy_tool": "一次性补贴",
            "policy_geo_scope": "花都、番禺",
            "policy_target_scope": "本市户籍、企业",
            "tool_parameter": "最高不超过100万"
        }
        
        expected_output = {
            "policy_object": "公共租赁住房（公租房）",
            "housing_category": "保障性住房",
            "policy_stage": "需求端",
            "policy_type": "激励型",
            "policy_tool": "一次性补贴",
            "policy_geo_scope": "花都、番禺",
            "policy_target_scope": "本市户籍、企业",
            "tool_parameter": "最高不超过100万"
        }

        result = analyze_policy_data(sample_data)
        self.assertEqual(result, expected_output)

if __name__ == '__main__':
    unittest.main()