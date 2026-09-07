#!/usr/bin/env python3
import subprocess,sys,tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parent.parent
def run(path,*extra):return subprocess.run([sys.executable,str(ROOT/"scripts/lint_direct_response.py"),str(path),*extra],capture_output=True,text=True)
def main():
    with tempfile.TemporaryDirectory() as temp:
        temp=Path(temp)
        good=temp/"good.md";good.write_text("依据公司公告，收入为100亿元（https://example.com/filing）。\n\n本内容仅供研究，不构成投资建议。",encoding="utf-8")
        assert run(good).returncode==0
        marker=temp/"marker.md";marker.write_text("收入增长 {fact:revenue}。",encoding="utf-8")
        assert run(marker).returncode!=0
        number=temp/"number.md";number.write_text("毛利率为35%，没有来源。",encoding="utf-8")
        assert run(number).returncode!=0
        route=temp/"route.md";route.write_text("当前请求不适用，请使用相邻任务。\n"+"扩写"*500,encoding="utf-8")
        assert run(route,"--route-only").returncode!=0
        blanket=temp/"blanket.md";blanket.write_text("缺少 Term Sheet，因此无法分析该项目。\n\n本内容仅供研究，不构成投资建议。",encoding="utf-8")
        assert run(blanket).returncode!=0
        meeting=temp/"meeting.md";meeting.write_text("补证全部完成后方可安排管理层初会。\n\n本内容仅供研究，不构成投资建议。",encoding="utf-8")
        assert run(meeting).returncode!=0
        mechanical=temp/"mechanical.md";mechanical.write_text("满足四项中的两项即可推进。\n\n本内容仅供研究，不构成投资建议。",encoding="utf-8")
        assert run(mechanical).returncode!=0
        conflated=temp/"conflated.md";conflated.write_text("进入数据室意味着投资推进通过。\n\n本内容仅供研究，不构成投资建议。",encoding="utf-8")
        assert run(conflated).returncode!=0
        adjacent=temp/"adjacent.md";adjacent.write_text("同类产品的销售证明目标技术已经商业化。\n\n本内容仅供研究，不构成投资建议。",encoding="utf-8")
        assert run(adjacent).returncode!=0
        incomplete_meeting=temp/"incomplete-meeting.md";incomplete_meeting.write_text("初会问题：只追问收入回款与交易。\n\n本内容仅供研究，不构成投资建议。",encoding="utf-8")
        assert run(incomplete_meeting).returncode!=0
        complete_meeting=temp/"complete-meeting.md";complete_meeting.write_text("初会问题按主体/技术、收入回款、临床增量、单位经济和交易五类展开，每题分别写升级与降级条件。\n\n本内容仅供研究，不构成投资建议。",encoding="utf-8")
        assert run(complete_meeting).returncode==0
        partial=temp/"partial.md";partial.write_text("公开信息支持方向性研究；交易条款缺失只使交易可行性与回报保持 unknown，仍值得用高信息价值问题开展证伪型初会。\n\n本内容仅供研究，不构成投资建议。",encoding="utf-8")
        assert run(partial).returncode==0
    print("PASS private-market-project-evaluation direct response");return 0
if __name__=="__main__":raise SystemExit(main())
