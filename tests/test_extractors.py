import unittest
from src.core.extractors import extract_policy_tools  # Adjust the import based on the actual function name

class TestExtractors(unittest.TestCase):

    def test_extract_policy_tools(self):
        # Example input and expected output
        input_sentence = "[1-1] 政府将实施保障性住房政策。"
        expected_output = "保障性住房政策"
        
        # Call the extractor function
        result = extract_policy_tools(input_sentence)
        
        # Assert the result
        self.assertEqual(result, expected_output)

    def test_extract_policy_tools_no_tool(self):
        input_sentence = "[2-1] 这是一个没有政策工具的句子。"
        expected_output = ""
        
        result = extract_policy_tools(input_sentence)
        
        self.assertEqual(result, expected_output)

if __name__ == '__main__':
    unittest.main()