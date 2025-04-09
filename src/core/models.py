class PolicyModel:
    def __init__(self, id, title, content, metadata):
        self.id = id
        self.title = title
        self.content = content
        self.metadata = metadata

class PolicyTool:
    def __init__(self, name, description):
        self.name = name
        self.description = description

class PolicyAnalysisResult:
    def __init__(self, policy_model, extracted_data, analysis_summary):
        self.policy_model = policy_model
        self.extracted_data = extracted_data
        self.analysis_summary = analysis_summary

class HousingPolicyModel(PolicyModel):
    def __init__(self, id, title, content, metadata, housing_type):
        super().__init__(id, title, content, metadata)
        self.housing_type = housing_type

class PolicyExtractor:
    def __init__(self, policy_model):
        self.policy_model = policy_model

    def extract_tools(self):
        # Logic to extract policy tools from the policy model
        pass

    def extract_housing_info(self):
        # Logic to extract housing-related information
        pass

class PolicyAnalyzer:
    def __init__(self, policy_analysis_result):
        self.policy_analysis_result = policy_analysis_result

    def generate_summary(self):
        # Logic to generate a summary of the analysis
        pass

    def analyze_tools(self):
        # Logic to analyze the extracted policy tools
        pass