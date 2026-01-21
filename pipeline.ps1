param(
    [string]$Workflow = "structured_output",
    [string]$Stage = "all",
    [string]$Provider = "ollama",
    [string]$Model = "ministral-3:14b-cloud",
    [switch]$Help
)

if ($Help) {
    Write-Host @"
Dataset Generation Pipeline Script
========================

Usage: .\pipeline.ps1 [-Provider <provider>] [-Model <model>] [-Stage <stage>] [-Help]

Stages:
  all                           - Run all stages (default)
  generate                      - Generate dataset using an LLM

Examples:
  .\pipeline.ps1                        # Run all stages
  .\pipeline.ps1 -Stage generate        # Run only generation stage
"@
    exit 0
}

# Set error action preference
$ErrorActionPreference = "Stop"

# Define colors for output
function Write-StageHeader {
    param([string]$Message)
    Write-Host ""
    Write-Host "==================== $Message ====================" -ForegroundColor Cyan
    Write-Host ""
}

function Write-StageInfo {
    param([string]$Message)
    Write-Host "[INFO] $Message" -ForegroundColor Green
}

function Write-StageError {
    param([string]$Message)
    Write-Host "[ERROR] $Message" -ForegroundColor Red
}

# ==================== ANALYSIS STAGES ====================

function Invoke-GenerateScript {
    Write-StageInfo "Running: generate.py"
    $ModelDir = $Model -replace ":", "-"
    python text2cypher/datasets/generate.py `
        --input-df ./data/raw/neo4j-2024v1/train-00000-of-00001.parquet `
        --output-df ./data/interim/neo4j-2024v1/$ModelDir/trajectories.csv `
        --workflow $Workflow `
        --provider $Provider `
        --model $Model `
        --verbose True `
        --log-dir-path ./logs/
    if ($LASTEXITCODE -ne 0) { throw "generate.py failed" }
}

# ==================== MAIN EXECUTION ====================

function Invoke-AllStages {
    Invoke-GenerateScript
}

# Main execution block
try {
    Write-Host "Dataset Generation Pipeline" -ForegroundColor Yellow
    Write-Host "=================" -ForegroundColor Yellow
    Write-Host "Stage: $Stage" -ForegroundColor Yellow
    
    switch ($Stage.ToLower()) {
        "all" { Invoke-AllStages }

        "generate" { Invoke-GenerateScript }
        
        default {
            Write-StageError "Unknown stage: $Stage"
            Write-Host "Use -Help to see available stages"
            exit 1
        }
    }
    
    Write-Host ""
    Write-Host "==================== PIPELINE COMPLETED ====================" -ForegroundColor Green
    Write-Host ""
    
} catch {
    Write-StageError $_.Exception.Message
    Write-Host ""
    Write-Host "==================== PIPELINE FAILED ====================" -ForegroundColor Red
    Write-Host ""
    exit 1
}
