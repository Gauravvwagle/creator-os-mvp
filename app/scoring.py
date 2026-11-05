from collections import defaultdict

WEIGHTS = {
    "audience_demand": 20,
    "monetization_potential": 20,
    "affiliate_opportunities": 15,
    "competition_accessibility": 10,
    "production_feasibility": 10,
    "long_term_demand": 15,
    "creator_capability": 10,
}


def evaluate_evidence(evidence_records):
    # Use the newest evidence record for each criterion.
    latest = {}
    for item in sorted(evidence_records, key=lambda x: x.observed_at):
        latest[item.criterion] = item

    missing = [key for key in WEIGHTS if key not in latest]
    breakdown = {}
    for criterion, weight in WEIGHTS.items():
        item = latest.get(criterion)
        breakdown[criterion] = {
            "weight": weight,
            "score": item.score if item else None,
            "weighted_contribution": round(item.score * weight / 100, 3) if item else None,
            "confidence": item.confidence if item else None,
            "observation": item.observation if item else None,
            "source_url": item.source_url if item else None,
            "is_demo": item.is_demo if item else None,
        }

    if missing:
        return {
            "status": "incomplete",
            "weighted_score": None,
            "criteria_present": [k for k in WEIGHTS if k in latest],
            "criteria_missing": missing,
            "breakdown": breakdown,
            "contains_demo_evidence": any(x.is_demo for x in latest.values()),
            "interpretation": "Insufficient evidence: add evidence for every missing criterion before ranking this niche.",
        }

    score = sum(latest[key].score * weight for key, weight in WEIGHTS.items()) / 100
    demo = any(x.is_demo for x in latest.values())
    if demo:
        interpretation = "Demonstration-only result. Replace demo evidence with verified research before making a business decision."
    elif score >= 8:
        interpretation = "Strong research score. Validate with a small publishing experiment before committing."
    elif score >= 6.5:
        interpretation = "Promising research score. Investigate weak criteria and run a controlled content test."
    elif score >= 5:
        interpretation = "Mixed opportunity. Improve evidence and compare against alternatives."
    else:
        interpretation = "Weak current fit. Reconsider the niche or gather better evidence."
    return {
        "status": "evaluated",
        "weighted_score": round(score, 2),
        "criteria_present": list(WEIGHTS),
        "criteria_missing": [],
        "breakdown": breakdown,
        "contains_demo_evidence": demo,
        "interpretation": interpretation,
    }
