from argparse import ArgumentParser
import os

import dotenv
from langchain_core.language_models import BaseChatModel
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_ollama import ChatOllama
from langchain_openai import AzureChatOpenAI, ChatOpenAI
from langchain_azure_ai.chat_models import AzureAIChatCompletionsModel

def add_agent_args(parser: ArgumentParser):
    parser.add_argument("--provider", type=str, choices=["azure", "google", "ollama", "openai"], default="google",
        help="The LLM provider to use.",
    )
    parser.add_argument("--model", type=str, default="gemini-2.5-flash",
        help="The LLM model to use.",
    )


def get_llm(
        provider: str = "google", 
        model: str = "gemini-2.5-pro",
    ) -> BaseChatModel:
    if provider == "azure":

        endpoint = dotenv.get_key(".env", f"{model.upper()}-ENDPOINT")
        api_key = dotenv.get_key(".env", f"{model.upper()}-KEY")
        api_version = dotenv.get_key(".env", f"{model.upper()}-API-VERSION")

        # print(f"Using Azure AI Endpoint: {endpoint}")
        # print(f"Using Azure AI Credential: {api_key}")
        # print(f"Using model: {model}")
        # print(f"Using API Version: {api_version}")
        # input('>')

        os.environ["AZURE_OPENAI_ENDPOINT"] = endpoint
        os.environ["AZURE_OPENAI_API_KEY"] = api_key

        # os.environ["AZURE_AI_ENDPOINT"] = endpoint
        # os.environ["AZURE_AI_CREDENTIAL"] = api_key

        if "gpt" in model.lower():
            llm = AzureChatOpenAI(
                azure_deployment=model,
                api_version=api_version,
            )
        else:
            llm = AzureAIChatCompletionsModel(
                model=model,
                endpoint=endpoint,
                credential=api_key,
                api_version=api_version,
            )
    elif provider == "google": # GOOGLE_API_KEY
        llm = ChatGoogleGenerativeAI(
            model=model,
            # model_kwargs={
            #     "generation_config": {
            #         "thinking_config": { 
            #             "include_thoughts": True 
            #         }
            #     }
            # }
        )
    elif provider == "ollama":
        llm = ChatOllama(model=model)
    elif provider == "openai":
        llm = ChatOpenAI(model_name=model, base_url="http://127.0.0.1:1234/v1", api_key="lm-studio")
    else:
        raise ValueError(f"Unsupported provider: {provider}")

    return llm
