# -*- coding: utf-8 -*-
"""M2/M3 自测：本地假模型 + 蒸馏队列 + 横向聚合

跑法：python tools/test_corpus_distill.py
不联网、不需要 API Key，起一个本地假端点模拟模型返回。
"""
import json
import os
import random
import shutil
import sys
import tempfile
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
import corpus

random.seed(17)
POOL = "的一是在不了有和人这中大为上个国我以要他时来用们生到作地于出就分对成会可主发年动同工也能下过子说产种面而方后多定行学法所民得经十三之进着等部度家电力里如水化高自二理起小物现实加量都两体制机当使点从业本去把性好应开它合还因由其些然前外天政四日那社义事平形相全表间样与关各重新线内数正心反你明看原又么利比或但质气第向道命此变条只没结解问意建月公无系军很情者最立代想已通并提直题党程展五果料象员革位入常文总次品式活设及管特件长求老头基资边流路级少图山统接知较将组见计别她手角期根论运农指几九区强放决西被干做必战先回则任取据处队南给色光门即保治北造百规热领七海口东导器压志世金增争济阶油思术极交受联什认六共权收证改清己美再采转更单风切打白教速花带安场身车例真务具万每目至达走积示议声报斗完类八离华名确才科张信马节话米整空元况今集温传土许步群广石记需段研界拉林律叫且究观越织装影算低持音众书布复容儿须际商非验连断深难近矿千周委素技备半办青省列习响约支般史感劳便团往酸历市克何除消构府称太准精值号率族维划选标写存候毛亲快效斯院查江型眼王按格养易置派层片始却专状育厂京识适属圆包火住调满县局照参红细引听该铁价严龙飞"
NAMES = ["林昭", "沈砚", "苏晚", "陆沉"]
BLOCKS = ["".join(random.choice(POOL) for _ in range(150)) for _ in range(60)]

BEATS = ["conflict_thrill", "bond_deepening", "faction_building",
         "world_painting", "tension_escalation"]


class FakeModel(BaseHTTPRequestHandler):
    hits = {"n": 0}

    def do_POST(self):
        n = int(self.headers.get("Content-Length") or 0)
        _body = self.rfile.read(n)
        FakeModel.hits["n"] += 1
        content = json.dumps({
            "summary": "主角在废墟里捡到一枚会说话的种子，种子报出他的名字，他决定北上寻找绿洲。",
            "events": ["捡到种子", "种子开口", "决定北上"],
            "hook": "种子说出了主角的名字",
            "beat": BEATS[FakeModel.hits["n"] % len(BEATS)],
        }, ensure_ascii=False)
        data = json.dumps({"choices": [{"message": {"content": content},
                                        "finish_reason": "stop"}]}, ensure_ascii=False).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, *a):
        pass


def novel(nchap, ch_size=1200):
    out = []
    for i in range(1, nchap + 1):
        out.append("第%d章 第%d夜" % (i, i))
        body, n = [], 0
        while n < ch_size:
            s = random.choice(BLOCKS)
            if random.random() < 0.3:
                s = "“" + s[:30] + "。”" + random.choice(NAMES) + "说，" + s[30:]
            body.append(s)
            n += len(s)
        out.append("".join(body)[:ch_size])
    return "\n".join(out)


def check(label, cond, extra=""):
    print(("  [OK]   " if cond else "  [FAIL] ") + label + (("  " + str(extra)) if extra else ""))
    return cond


ok = True
d = tempfile.mkdtemp(prefix="corpus_m2_")
corpus.init(os.path.join(d, "corpus.db"))

srv = ThreadingHTTPServer(("127.0.0.1", 0), FakeModel)
port = srv.server_address[1]
threading.Thread(target=srv.serve_forever, daemon=True).start()
cfg = {"kind": "openai", "baseUrl": "http://127.0.0.1:%d/v1" % port,
       "apiKey": "test", "model": "fake-model"}

print("\n== 1. 建库 ==")
r1 = corpus.add_book("废土种田", novel(40), author="甲", genre="末世")
r2 = corpus.add_book("剑修飞升", novel(36), author="乙", genre="仙侠")
ok &= check("导入 2 本", r1["chapters"] == 40 and r2["chapters"] == 36,
            "%d/%d 章" % (r1["chapters"], r2["chapters"]))

print("\n== 2. 排任务 + 预算 ==")
for b in corpus.list_books():
    corpus.plan_jobs(b["sid"], "sample")
est = corpus.estimate()
ok &= check("任务数 > 0", est["jobs"] > 0, "%d 个" % est["jobs"])
ok &= check("token 预估为正", est["tokensIn"] > 0 and est["tokensOut"] > 0,
            "in %d / out %d" % (est["tokensIn"], est["tokensOut"]))

print("\n== 3. 并发蒸馏（假模型）==")
events = []
t0 = time.time()
res = corpus.run_jobs(cfg, concurrency=3, max_jobs=10,
                      on_event=lambda k, dd: events.append(k))
el = time.time() - t0
ok &= check("跑完 10 个任务", res["done"] == 10, "成功 %d / 失败 %d" % (res["done"], res["failed"]))
ok &= check("有 start/done/end 事件",
            "start" in events and events.count("done") == 10 and "end" in events, events[:3])
ok &= check("耗时合理", el < 30, "%.1fs" % el)

print("\n== 4. 断点续跑 ==")
before = corpus.overview()["jobs"]
res2 = corpus.run_jobs(cfg, concurrency=4, max_jobs=6)
ok &= check("再跑 6 个", res2["done"] == 6, "成功 %d" % res2["done"])
after = corpus.overview()["jobs"]
ok &= check("done 累加", after.get("done", 0) == before.get("done", 0) + 6,
            "%d → %d" % (before.get("done", 0), after.get("done", 0)))

print("\n== 5. 蒸馏产物 ==")
sd = corpus.search_distill("种子 绿洲", k=3)
ok &= check("能搜到摘要", len(sd) > 0, (sd[0]["summary"][:24] if sd else "无"))
con = corpus._conn()
beat_rows = con.execute("SELECT beat, COUNT(*) FROM distill GROUP BY beat").fetchall()
con.close()
ok &= check("beat 已落库", len(beat_rows) > 0, dict(beat_rows))

print("\n== 6. 文风指标（不花 token）==")
for b in corpus.list_books():
    m = corpus.style_metrics(b["sid"])
    ok &= check("《%s》指标可算" % b["title"], m is not None,
                "句长 %.1f / 短句 %.0f%% / 对话 %.0f%%" % (
                    m["avgSent"], m["shortRatio"] * 100, m["dialogue"] * 100) if m else "")

print("\n== 7. 聚合 ==")
base = corpus.genre_baseline()
ok &= check("按题材聚合", len(base) == 2, [g["genre"] for g in base])
ok &= check("有 beat 分布", any(g["beats"] for g in base),
            {g["genre"]: list(g["beats"])[:2] for g in base})

print("\n== 8. 报告 ==")
md = corpus.report_markdown()
ok &= check("报告有标题", md.startswith("# 语料库蒸馏报告"))
ok &= check("报告含表格", "| 题材 |" in md, "%d 行" % len(md.splitlines()))

print("\n结果:", "全部通过" if ok else "有失败项")
srv.shutdown()
shutil.rmtree(d, ignore_errors=True)
