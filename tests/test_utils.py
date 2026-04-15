from utils import clean_json_response


class TestCleanJsonResponse:
    def test_plain_json(self):
        assert clean_json_response('{"key": "value"}') == '{"key": "value"}'

    def test_strips_whitespace(self):
        assert clean_json_response("  {} ") == "{}"

    def test_strips_json_code_fence(self):
        assert clean_json_response('```json\n{"a": 1}\n```') == '{"a": 1}'

    def test_strips_plain_code_fence(self):
        assert clean_json_response('```\n{"a": 1}\n```') == '{"a": 1}'

    def test_only_opening_fence(self):
        result = clean_json_response('```json\n{"a": 1}')
        assert result == '{"a": 1}'

    def test_only_closing_fence(self):
        result = clean_json_response('{"a": 1}\n```')
        assert result == '{"a": 1}'

    def test_empty_string(self):
        assert clean_json_response("") == ""

    def test_multiline_json_in_fences(self):
        text = '```json\n{\n  "a": 1,\n  "b": 2\n}\n```'
        result = clean_json_response(text)
        assert '"a": 1' in result
        assert not result.startswith("```")
        assert not result.endswith("```")
