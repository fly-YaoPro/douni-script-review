#!/usr/bin/env python3
import argparse,json
from pathlib import Path
def annuity(contribution,rate,years):return contribution*years if rate==0 else contribution*((1+rate)**years-1)/rate
def project(goal,rate,inflation):
    years=int(goal["years"]);assets=float(goal.get("allocated_assets",0));contribution=float(goal.get("annual_contribution",0));target=float(goal["target_today"])
    if years<=0 or assets<0 or contribution<0 or target<=0 or rate<=-1 or inflation<=-1:raise SystemExit("invalid goal inputs")
    projected=assets*(1+rate)**years+annuity(contribution,rate,years);future=target*(1+inflation)**years
    return {"name":goal["name"],"priority":goal["priority"],"projected_assets":projected,"goal_future_value":future,"funding_gap":future-projected,"funded_ratio":projected/future}
def main():
    p=argparse.ArgumentParser();p.add_argument("input");p.add_argument("--pretty",action="store_true");a=p.parse_args()
    d=json.loads(Path(a.input).read_text(encoding="utf-8"));jurisdiction=d.get("jurisdiction");currency=d.get("currency");goals=d.get("goals")
    if not jurisdiction or not currency:raise SystemExit("jurisdiction and currency required")
    if not isinstance(goals,list) or not goals:raise SystemExit("goals required")
    rate=float(d["return_rate"]);inflation=float(d.get("inflation_rate",0));base=[project(goal,rate,inflation) for goal in goals]
    stress=[]
    for scenario in d.get("stress_scenarios",[]):
        scenario_rate=rate+float(scenario.get("return_rate_delta",0));scenario_inflation=inflation+float(scenario.get("inflation_rate_delta",0))
        stress.append({"name":scenario["name"],"goals":[project(goal,scenario_rate,scenario_inflation) for goal in goals]})
    out={"capabilities":{"can_plan":True,"can_quantify_tax":False},"jurisdiction":jurisdiction,"currency":currency,"goals":base,"stress_scenarios":stress,"warning":"funded_ratio is a deterministic projection, not a success probability"}
    print(json.dumps(out,ensure_ascii=False,indent=2 if a.pretty else None));return 0
if __name__=="__main__":raise SystemExit(main())
