param(
    [string]$DatasetType = "train",
    [string]$Workflow = "native_tool_call",
    [string]$Provider = "ollama",
    [string]$Model = "ministral-3:14b-cloud",
    [switch]$Help
)

if ($Help) {
    Write-Host @"
Dataset Generation Pipeline Script
========================

Usage: .\pipeline.ps1 [-Provider <provider>] [-Model <model>] [-Help]
Parameters:
  -Workflow <string>    Specifies the workflow type. Default is "native_tool_call".
  -Provider <string>    Specifies the model provider. Default is "ollama".
  -Model <string>       Specifies the model name. Default is "ministral-3:14b-cloud".
  -Help                 Displays this help message.
"@
    exit 0
}

# Set error action preference
$ErrorActionPreference = "Stop"

function Generate {
    Write-Host "[INFO] Running: generate.py" -ForegroundColor Green
    $ModelDir = $Model -replace ":", "-"
    python text2cypher/experiments/datasets/generate.py `
        --input-df ./data/raw/neo4j-2024v1/$DatasetType-00000-of-00001.parquet `
        --output-df ./data/interim/neo4j-2024v1/$ModelDir/$DatasetType-trajectories.csv `
        --workflow $Workflow `
        --provider $Provider `
        --model $Model `
        --verbose True `
        --log-dir-path ./logs/
    if ($LASTEXITCODE -ne 0) { throw "generate.py failed" }
}

function Evaluate {
    Write-Host "[INFO] Running: evaluate.py" -ForegroundColor Green
    $ModelDir = $Model -replace ":", "-"
    python text2cypher/experiments/evaluate.py `
        --dataset-df ./data/raw/neo4j-2024v1/$DatasetType-00000-of-00001.parquet `
        --predictions-df ./data/interim/neo4j-2024v1/$ModelDir/$DatasetType-trajectories.csv `
        --output-df ./data/interim/evaluations/$ModelDir/$DatasetType.csv
    if ($LASTEXITCODE -ne 0) { throw "evaluate.py failed" }
}

# Main execution block
try {
    Generate
    # Evaluate
} catch {
    $Message = $_.Exception.Message
    Write-Host "[ERROR] $Message" -ForegroundColor Red
    exit 1
}
