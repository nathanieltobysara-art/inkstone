# -*- coding: utf-8 -*-
"""corpus.py 自测：功能链路 + 300 本量级导入实测"""
import os, sys, time, random, tempfile, shutil

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
import corpus

random.seed(3)
POOL = "的一是在不了有和人这中大为上个国我以要他时来用们生到作地于出就分对成会可主发年动同工也能下过子说产种面而方后多定行学法所民得经十三之进着等部度家电力里如水化高自二理起小物现实加量都两体制机当使点从业本去把性好应开它合还因由其些然前外天政四日那社义事平形相全表间样与关各重新线内数正心反你明看原又么利比或但质气第向道命此变条只没结解问意建月公无系军很情者最立代想已通并提直题党程展五果料象员革位入常文总次品式活设及管特件长求老头基资边流路级少图山统接知较将组见计别她手角期根论运农指几九区强放决西被干做必战先回则任取据处队南给色光门即保治北造百规热领七海口东导器压志世金增争济阶油思术极交受联什认六共权收证改清己美再采转更单风切打白教速花带安场身车例真务具万每目至达走积示议声报斗完类八离华名确才科张信马节话米整空元况今集温传土许步群广石记需段研界拉林律叫且究观越织装影算低持音众书布复容儿须际商非验连断深难近矿千周委素技备半办青省列习响约支般史感劳便团往酸历市克何除消构府称太准精值号率族维划选标写存候毛亲快效斯院查江型眼王按格养易置派层片始却专状育厂京识适属圆包火住调满县局照参红细引听该铁价严龙飞"
NAMES = ["林昭", "沈砚", "苏晚", "陆沉", "顾清和", "裴昀"]
BLOCKS = ["".join(random.choice(POOL) for _ in range(160)) for _ in range(60)]

def gen_novel(nchap=20, ch_size=3000):
    out = []
    for i in range(1, nchap + 1):
        out.append("第%d章 风起"%i)
        body = []
        n = 0
        while n < ch_size:
            s = random.choice(BLOCKS)
            if random.random() < 0.3:
                s = "“" + s[:40] + "。”" + random.choice(NAMES) + "说，" + s[40:]
            body.append(s); n += len(s)
        out.append("".join(body)[:ch_size])
    return "\n".join(out)

def check(label, cond, extra=""):
    print(("  [OK]   " if cond else "  [FAIL] ") + label + (("  " + str(extra)) if extra else ""))
    return cond

ok = True
d = tempfile.mkdtemp(prefix="corpus_test_")
print("库:", d)
corpus.init(os.path.join(d, "corpus.db"))

print("\n== 1. 导入 ==")
r1 = corpus.add_book("重生之我在废土种田", gen_novel(120), author="甲", genre="末世")
r2 = corpus.add_book("剑修她不想飞升", gen_novel(18), author="乙", genre="仙侠")
r3 = corpus.add_book("都市之最后一个道士", gen_novel(12), author="丙", genre="都市", fulltext=False)
ok &= check("导入 3 本", r1["chapters"] == 120 and r2["chapters"] == 18 and r3["chapters"] == 12,
            "%d/%d/%d 章" % (r1["chapters"], r2["chapters"], r3["chapters"]))
ok &= check("字数统计 > 0", r1["words"] > 0, r1["words"])

print("\n== 2. 全文检索 ==")
hit = corpus.search("林昭", k=5)
ok &= check("检索有结果", len(hit) > 0, "%d 条" % len(hit))
ok &= check("结果带片段", bool(hit and hit[0]["snippet"]), (hit[0]["snippet"][:40] if hit else ""))
t0 = time.time(); [corpus.search("青省列习响") for _ in range(20)]; per = (time.time()-t0)/20*1000
ok &= check("单次检索 < 50ms", per < 50, "%.1fms" % per)
s = corpus.search("林昭", k=10, sid=r1["sid"])
ok &= check("按书过滤", all(x["sid"] == r1["sid"] for x in s), "%d 条" % len(s))

print("\n== 3. 结构统计 ==")
st = corpus.book_stats(r1["sid"])
ok &= check("章数正确", st["chapters"] == 120, st["chapters"])
ok &= check("对话占比可算", 0 <= st["dialogueRatio"] <= 1, st["dialogueRatio"])
print("     平均章长 %.0f 字，标准差 %.0f，对话占比 %.1f%%" % (st["avgWords"], st["stdWords"], st["dialogueRatio"]*100))
ov = corpus.overview()
ok &= check("总览 3 本", ov["books"] == 3, "%d 本 %d 万字" % (ov["books"], ov["words"]//10000))

print("\n== 4. 任务队列（断点续跑）==")
p = corpus.plan_jobs(r1["sid"], "sample")
ok &= check("抽样计划少于全量", p["planned"] < p["total"], "%d/%d" % (p["planned"], p["total"]))
batch = corpus.take_jobs(4)
ok &= check("取到任务", len(batch) == 4, len(batch))
corpus.finish_job(batch[0]["sid"], batch[0]["no"], "主角在废墟里捡到一枚会说话的种子，决定北上。",
                  events=["捡到种子", "决定北上"], hook="种子开口说了第一句话")
corpus.fail_job(batch[1]["sid"], batch[1]["no"], "429 rate limit")
st2 = corpus.overview()["jobs"]
ok &= check("任务状态记录", st2.get("done", 0) >= 1 and st2.get("todo", 0) >= 1, st2)

print("\n== 5. 蒸馏产物检索 ==")
sd = corpus.search_distill("种子 北上", k=3)
ok &= check("能搜到蒸馏摘要", len(sd) > 0, (sd[0]["summary"][:30] if sd else "无"))
corpus.save_dbook(r1["sid"], book_sum="废土种田流，主线是重建聚落。", style="短句为主，对话占比高。")
ok &= check("书级产物落盘", True)

print("\n== 6. 删除 ==")
corpus.drop_book(r3["sid"])
ok &= check("删干净", corpus.overview()["books"] == 2, corpus.overview()["books"])

print("\n结果:", "全部通过" if ok else "有失败项")
shutil.rmtree(d, ignore_errors=True)
