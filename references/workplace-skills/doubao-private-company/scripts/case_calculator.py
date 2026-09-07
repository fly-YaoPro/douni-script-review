#!/usr/bin/env python3
import argparse,json
from pathlib import Path

REQUIRED_TRANSACTION_FIELDS=("instrument","investor_rights","dilution_treatment","currency")

def npv(rate,flows):return sum(value/(1+rate)**year for year,value in enumerate(flows))
def irr(flows):
    if not flows or flows[0]>=0 or not any(x>0 for x in flows[1:]):raise SystemExit("cash_flows require an initial outflow and later inflow")
    lo,hi=-0.9999,10.0
    if npv(lo,flows)*npv(hi,flows)>0:raise SystemExit("IRR root not bracketed")
    for _ in range(200):
        mid=(lo+hi)/2
        if npv(lo,flows)*npv(mid,flows)<=0:hi=mid
        else:lo=mid
    return (lo+hi)/2
def main():
    p=argparse.ArgumentParser();p.add_argument("input");p.add_argument("--pretty",action="store_true");a=p.parse_args()
    d=json.loads(Path(a.input).read_text(encoding="utf-8"))
    transaction=d.get("transaction_context")
    if not isinstance(transaction,dict):raise SystemExit("transaction_context required before return calculation")
    missing=[field for field in REQUIRED_TRANSACTION_FIELDS if not transaction.get(field)]
    if missing:raise SystemExit("transaction_context missing: "+", ".join(missing))
    scenarios=d.get("scenarios")
    if not isinstance(scenarios,list) or not scenarios:raise SystemExit("scenarios required")
    rows=[];probability_sum=0;expected_exit=0
    for scenario in scenarios:
        probability=float(scenario["probability"]);entry=float(scenario["entry_investment"]);exit_value=float(scenario["exit_proceeds_to_investor"]);years=float(scenario["years"])
        if not 0<=probability<=1 or entry<=0 or exit_value<=0 or years<=0:raise SystemExit("invalid scenario")
        moic=exit_value/entry;cagr=moic**(1/years)-1
        row={"name":scenario["name"],"probability":probability,"moic":moic,"cagr":cagr,"methodology":"single-entry single-exit CAGR"}
        if scenario.get("cash_flows"):row["irr"]=irr([float(x) for x in scenario["cash_flows"]])
        rows.append(row);probability_sum+=probability;expected_exit+=probability*exit_value
    if abs(probability_sum-1)>1e-6:raise SystemExit("probabilities must sum to 1")
    out={"capabilities":{"can_compute_returns":{"allowed":True,"missing":[],"blockers":[],"blocked_slots":["return_calculation"]}},"probability_sum":probability_sum,"expected_exit_proceeds_to_investor":expected_exit,"scenarios":rows}
    print(json.dumps(out,ensure_ascii=False,indent=2 if a.pretty else None));return 0
if __name__=="__main__":raise SystemExit(main())
