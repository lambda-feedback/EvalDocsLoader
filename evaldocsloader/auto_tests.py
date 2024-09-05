import json
import yaml
from dataclasses import dataclass

class TestFile:
    """An abstraction over a test file, which may be in one of several different formats.
    Currently, JSON and YAML are supported.
    """

    def __init__(self, file_content: str, file_name: str) -> None:
        self.groups = []

        # Get the file extension to determine which format should be used.
        extension = file_name.split(".")[-1]
        if extension == "json":
            try:
                questions = json.loads(file_content)

                for question in questions:
                    out = []
                    title = question["title"]
                    for part in question["parts"]:
                        for response_area in part["responseAreas"]:
                            params = response_area["params"]
                            answer = response_area["answer"]
                            for test in response_area["tests"]:
                                test.update({"answer": answer})
                                test.update({"params": params})
                                out.append(SingleTest(test))
                    self.groups.append({"title": title, "tests": out})

            except KeyError as e:
                raise Exception(f'The key "{e.args[0]}" doesn\'t exist, or is in the wrong place.')
            except json.JSONDecodeError as e:
                raise Exception(f'Error parsing JSON: "{e}"')
        elif extension == "yaml":
            try:
                # Tests are organised in groups of separate YAML documents (separated by "---")
                docs = yaml.safe_load_all(file_content)
                for test_group in docs:
                    tests = []
                    title = test_group.get("title", "")
                    for test in test_group.get("tests", []):
                        # Add an empty params field if none was provided.
                        if test.get("params") == None:
                            test["params"] = {}
                        
                        tests.append(SingleTest(test))

                    self.groups.append({"title": title, "tests": tests})
            except yaml.YAMLError as e:
                raise Exception(f'Error parsing YAML: {e}')
        else:
            raise Exception(f'"{extension}" files are not supported as a test format.')


class SingleTest:
    def __init__(self, test_dict: dict):
        self.answer = test_dict.get("answer", "")
        self.params = test_dict.get("params", {})
        self.desc = test_dict.get("description", "")

        self.sub_tests = []
        if "sub_tests" in test_dict:
            for sub_test in test_dict["sub_tests"]:
                expected_result = sub_test.get("expected_result")
                if not expected_result:
                    raise Exception("No expected result given for test")

                self.sub_tests.append(SubTest(
                    sub_test.get("description", ""),
                    sub_test.get("response", ""),
                    expected_result.get("is_correct"),
                    expected_result,
                ))
        else:
            expected_result = test_dict.get("expected_result")
            if not expected_result:
                raise Exception("No expected result given for test")

            self.sub_tests.append(SubTest(
                "",
                test_dict.get("response", ""),
                expected_result.get("is_correct"),
                expected_result,
            ))

    def evaluate_all(self, func) -> list[dict]:
        return [func(test.response, self.answer, self.params) for test in self.sub_tests]
    
    def compare_all(self, eval_results: list[dict]) -> tuple[bool, str]:
        for i, eval_result in enumerate(eval_results):
            eval_correct = eval_result["is_correct"]
                
            if eval_correct != self.sub_tests[i].is_correct:
                return (
                    False,
                    (f"response \"{self.sub_tests[i].response}\" with answer "
                     f"\"{self.answer}\" was {'' if eval_correct else 'in'}correct: "
                     f"{eval_result['feedback']}\nTest description: {self.sub_tests[i].desc}")
                )
            
            # Are there any other fields in the eval function result that need to be checked?
            if self.sub_tests[i].expected_result != None:
                # Check each one in turn
                for key, value in self.sub_tests[i].expected_result.items():
                    actual_result_val = eval_result.get(key)
                    if actual_result_val == None:
                        return (False, f"No value returned for \"{key}\"")
                    
                    if actual_result_val != value:
                        return (
                            False,
                            f"expected {key} = \"{value}\", got {key} = \"{actual_result_val}\"\nTest description: {self.desc}"
                        )
        
        return (True, "")

@dataclass
class SubTest:
    desc: str
    response: str
    is_correct: bool
    expected_result: dict
