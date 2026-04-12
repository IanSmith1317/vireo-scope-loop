import keyring
from anthropic import Anthropic
from config import API_KEY, MODEL_LOW, MODEL_HIGH

def run_agent(systempt_prompt: str, user_input: str, model:str = MODEL_LOW, max_tokens: int = 4096)->str:
    client = Anthropic(
        api_key=API_KEY
    )

    message = client.messages.create(
        max_tokens=max_tokens,
        system = systempt_prompt,
        messages=[
            {
            "role":"user",
            "content": user_input,
            }
        ],
        model=model
    )

    return message.content[0].text

print(run_agent(systempt_prompt="", user_input="say hello in one word"))

iterations = 3


if __name__=="__main___":
    i=0
    while i < iterations:
        #TODO: put scope agents here
        #Scope agent creates realistic task based on role
        scope_agent_resp = scope_agent()
        
        #Canonicalizer Agent de duplicates and clusters the primitives
        canonical_scope = canonicalizer_agent(scope_agent_resp)
        
        #Translator Agent translates the extracts into key inputs, outputs, steps, transformations, and constraints
        translated_scope = translator_agent(canonical_scope)

        #Auditor maps each step to capabilty within Vireo. Returns bool pass fail
        audit_pass = auditor_agent(translated_scope)
        if audit_pass:
            #TODO: implement frequency counter
            #TODO: implement PM Agent
            #TODO: execute build decision logic
            #TODO: implement spec writer
            #TODO: implement human reviewer gate
            #TODO: implement code executor (to operate within the actual Vireo Project)
            #TODO: implement code reviewer

            i+=1
        else:
            i+=1


