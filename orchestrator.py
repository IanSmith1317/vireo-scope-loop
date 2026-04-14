import keyring
from anthropic import Anthropic
import json

from config import API_KEY, MODEL_LOW, MODEL_HIGH
from agents.scope_agents import ScopeAgent, ScopeAgentOutput
from agents.canonicalizer_agents import CanonicalizerAgent, CanonicalizerOutput
from agents.translator_agents import TranslatorAgent
from agents.auditor_agents import AuditorAgent
from agents.base_agent import BaseAgent

def clean_json_response(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1]  # remove first line
    if text.endswith("```"):
        text = text.rsplit("```", 1)[0]
    return text.strip()

if __name__=="__main__":

    print(">>>> SESSION START!")

    iterations = 2
    i=0

    role_list = [
        "FP&A Analyst",
        # "Project Manager",
        # "Investment Banker",
        # "Private Equity Portfolio Company Associate",
        # "Director of Finance",
        # "Vice President of Corporate Development",
        # "Equity Research Analyst"
    ]

    all_workflows: list[ScopeAgentOutput] = []

    print("Spinning Up Agents")
    #Instantiate agents...
    canonicalizer_agent = CanonicalizerAgent(model=MODEL_LOW)
    translator_agent = TranslatorAgent(model=MODEL_LOW)
    auditor_agent = AuditorAgent(model=MODEL_LOW)
    print("...OK!")
    
    for role in role_list:

        #Scope agent creates realistic task based on role
        print("Spinning Up Scope Agent...")
        scope_agent = ScopeAgent(model=MODEL_LOW, role = "FP&A Analyst")
        print("...OK!")
        print("Sending Scope Agent API Request...")
        scope_agent_resp = scope_agent.ask(user_prompt = f"""
                                            Generate {iterations} realistic Microsoft Excel workflows for the following job function:

                                            Role: {scope_agent.role}

                                            Instructions:
                                            - Focus on recurring and common spreadsheet work this role would realistically perform in Excel.
                                            - Include a mix of reporting, analysis, modeling, reconciliation, tracker maintenance, and review-preparation workflows where appropriate for the role.
                                            - Use Microsoft Excel language naturally.
                                            - Make the workflows specific enough that someone in the profession would recognize them as realistic.
                                            - Keep the focus on workbook actions, spreadsheet structure, and business purpose.
                                            - Do not write generic job duties.
                                            - Do not describe work outside Excel except where another system provides an input file or export.

                                            Return the response exactly in the format described in the system instructions. Do NOT generate more or fewer workflows than reqeuested in this prompt.
                                            """ 
                                           )
        
        print("...OK!")
        


        #Load the JSON and check against the pydantic model in scope_agents.py
        try:
            print("Pasring JSON...")
            #returns a list of ScopeAgentOutput pydantic models
            scope_parsed = ScopeAgentOutput.model_validate(json.loads(clean_json_response(scope_agent_resp)))
            print("...OK!")
            print("///////PARSED///////")
            print(scope_parsed)
            print("/////// END ////////")

            all_workflows.extend(scope_parsed.workflows)

        except:
            print(">>>>>>JSON PARSE ERROR!")
            print(scope_agent_resp)
        

    print("CANONIZING WORKFLOWS.....")
    #Canonicalizer Agent de duplicates and clusters the primitives
    canonical_input = [w.model_dump() for w in all_workflows]
    canonical_user_prompt = canonicalizer_agent.build_user_prompt(canonical_input)
    canonical_resp = canonicalizer_agent.ask(user_prompt= canonical_user_prompt)
    canonical_result = CanonicalizerOutput.model_validate(json.loads(clean_json_response(canonical_resp)))

    print(canonical_result)
    print("....done!")
     
            # #Translator Agent translates the extracts into key inputs, outputs, steps, transformations, and constraints
            # translated_scope = translator_agent.ask(canonical_scope)

            # #Auditor maps each step to capabilty within Vireo. Returns bool pass fail
            # audit_pass = auditor_agent.ask(translated_scope)

            # if audit_pass:
            #     #TODO: implement frequency counter
            #     #TODO: implement PM Agent
            #     #TODO: execute build decision logic
            #     #TODO: implement spec writer
            #     #TODO: implement human reviewer gate
            #     #TODO: implement code executor (to operate within the actual Vireo Project)
            #     #TODO: implement code reviewer

            #     pass
            # else:
            #     pass

    print("...SESSION END!")

