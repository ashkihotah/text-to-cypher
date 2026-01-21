## SCHEMA DISCOVERY TOOLS

{tools_definition}

## OUTPUT FORMAT CONSTRAINT

Trace, in each of your turn, your reasoning and tool calls in a structured JSON format, derived from the following Python `pydantic` model.
```json
{model_json_schema}
```
**IMPORTANT**: Ensure that you do not output unescaped double quotes (") in the JSON output since this would break the JSON format. Always use single quotes (') or escaped double quotes (\") for strings inside the JSON.