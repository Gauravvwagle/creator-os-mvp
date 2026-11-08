CRITERIA_GUIDE = {
    "audience_demand": "Whether a defined audience has recurring questions and demand. Look at search interest, video performance, communities, and audience problems.",
    "monetization_potential": "Whether creators in this niche can earn through ads, sponsorships, digital products, courses, paid communities, or services. Check real eligibility and real examples.",
    "affiliate_opportunities": "Actual active affiliate programs, commission rates, cookie duration, payment terms, eligibility, and regional availability (including Nepal).",
    "competition_accessibility": "Relevant channels and videos, including smaller channels: views, upload dates, audience response, and content gaps. Not just subscriber counts.",
    "production_feasibility": "Whether consistent videos can be made with ~8 GB RAM, Intel integrated graphics, limited time, and free tools (OBS Studio, VS Code, Kdenlive, GIMP, Audacity, Ollama).",
    "long_term_demand": "Evergreen learning needs and historical trends. Google Trends shows relative interest only. Separate sustained interest from temporary spikes.",
    "creator_capability": "The creator's real programming, teaching, production, and consistency ability, shown by completed projects and a sample video, not self-assessment alone.",
}


def build_planning_prompt(niche_name: str, criterion: str) -> str:
    guide = CRITERIA_GUIDE[criterion]
    return f"""You are a research planning assistant for a creator-business tool.

Niche: {niche_name}
Criterion: {criterion}
What this criterion means: {guide}

Write a research PLAN only. Do not answer the questions. Do not state facts, statistics, prices, or commission rates. Do not invent websites or URLs.

Use exactly these four sections:

1. RESEARCH QUESTIONS
Five specific questions a human should investigate.

2. SOURCE TYPES TO CHECK
Types of sources only (for example: official affiliate program pages, YouTube search results, Google Trends, platform policy pages).

3. EVIDENCE THAT WOULD SUPPORT A HIGH SCORE
Three short bullet points.

4. EVIDENCE THAT WOULD SUPPORT A LOW SCORE
Three short bullet points.

Keep the whole answer concise."""