from pathlib import Path

RAW_DATA_PATH = Path("data/raw/")
INTERIM_DATA_PATH = Path("data/interim/")

CYPHERBENCH_SCHEMAS_PATH = RAW_DATA_PATH / "text-to-cypher" / "CypherBench" / "schemas"

def format_schema_with_special_tokens(schema: dict) -> str:
    schema_str = "<schema:>\n"
    for node in schema['entities']:
        schema_str += f"    <node:> {node['label']}\n"
        for prop_name, prop_type in node['properties'].items():
            schema_str += f"        <prop:> {prop_name} <type:{prop_type}>\n"

    for rel in schema['relations']:
        schema_str += f"    <rel:>\n"
        schema_str += f"        <from:> {rel['subj_label']}\n"
        schema_str += f"        <label:> {rel['label']}\n"
        schema_str += f"        <to:> {rel['obj_label']}\n"
        for prop_name, prop_type in rel['properties'].items():
            schema_str += f"            <prop:> {prop_name} <type:{prop_type}>\n"
    
    return schema_str

def format_sample_with_special_tokens(sample: str) -> str:
    return f"<cmd:> {sample}"

SCHEMA_FORMAT_FUNCTIONS = {
    "special_tokens": format_schema_with_special_tokens,
}

SAMPLE_FORMAT_FUNCTIONS = {
    "special_tokens": format_sample_with_special_tokens
}

HF_ENC_DEC_MODELS = [
    "Salesforce/codet5-base",

    # T5-GEMMA models
    "google/t5gemma-9b-9b-ul2",

    # Flan-T5 models
    "google/flan-t5-small",
    "google/flan-t5-base",
    "google/flan-t5-large",
    "google/flan-t5-xxl",

    # Standard T5 and mT5 models
    "google/t5-small",
    "google/t5-base",
    "google/t5-large",

    "google/mt5-small",
    "google/mt5-base",
    "google/umt5-large",
    "google/umt5-xl"
]