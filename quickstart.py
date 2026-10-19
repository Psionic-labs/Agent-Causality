"""This creates .causality/events.db and records the causal event chain."""

import causality

causality.init()

@causality.agent(role="researcher")
def research(query):
    return {"answer": query}

@causality.merge_decision(ports=["research_summary"])
def approve(research_summary):
    return "approved" if research_summary["answer"] == "yes" else "rejected"

print(approve(research("yes")))