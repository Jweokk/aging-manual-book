#!/usr/bin/env python3
"""引用与版权自检（《变老说明书》）
用法: python3 tools/check_citation.py [--book DIR] [--corpus DIR] [--n 12]
语料放 .citation-corpus/（**.gitignore 排除，绝不入公开仓库**）。
"""
import argparse, glob, os, re, sys

def norm(s):
    s = re.sub(r"[\s，。、；：\"'“”‘’（）()《》？！…\-—\*#\[\]]+", "", s)
    return s

def grams(s, n):
    return {s[i:i+n] for i in range(len(s)-n+1)}

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--book", default=os.path.join(os.path.dirname(__file__), "..", "book"))
    ap.add_argument("--corpus", default=os.path.join(os.path.dirname(__file__), "..", ".citation-corpus"))
    ap.add_argument("--n", type=int, default=12)
    ap.add_argument("--allow", default=os.path.join(os.path.dirname(__file__), "..", ".citation-corpus", "allow.txt"))
    a = ap.parse_args()

    def body(path):
        """正文才比对：标题行（# 开头）不受版权保护，且沿用外部提纲的章题已登记。"""
        lines = [l for l in open(path, encoding="utf-8").read().splitlines()
                 if not re.match(r"\s*#{1,6}\s", l)]
        return norm("\n".join(lines))
    book = {os.path.basename(f): body(f)
            for f in sorted(glob.glob(os.path.join(a.book, "*.md")))}
    if not book:
        print("没找到正文文件:", a.book); return 1
    print(f"正文文件 {len(book)} 个｜阈值 {a.n} 字\n")

    corpus = sorted(f for f in glob.glob(os.path.join(a.corpus, "*.txt"))
                    if os.path.basename(f) not in ("allow.txt",))
    # allow.txt 是白名单不是语料
    if not corpus:
        print("⚠ 没有语料文件。把来源文本放到", a.corpus, "（该目录不入公开仓库）")
    allow = set()
    if os.path.exists(a.allow):
        for line in open(a.allow, encoding="utf-8"):
            line = line.split("#")[0].strip()
            if line: allow.add(norm(line))
    bad = 0
    for p in corpus:
        name = os.path.basename(p)
        sc = norm(open(p, encoding="utf-8").read())
        g = grams(sc, a.n)
        for f, t in book.items():
            hits = [h for h in sorted(grams(t, a.n) & g)
                    if not any(h in x or x in h for x in allow)]
            if hits:
                bad += len(hits)
                print(f"✗ {name} ↔ {f}: {len(hits)} 处")
                for h in hits[:10]:
                    print("    ·", h)

    # 引号配对 + 有引号无出处
    print("\n— 引号与出处 —")
    for f, t in book.items():
        raw = open(os.path.join(a.book, f), encoding="utf-8").read()
        sq = raw.count("「") + raw.count("」")
        q = raw.count('"')
        if sq % 2 or q % 2:
            print(f"✗ {f}: 引号不成对（「」{sq} / \" {q}）")
    # 转引标注
    for f, t in book.items():
        raw = open(os.path.join(a.book, f), encoding="utf-8").read()
        if "变老之前要知道" in raw and "转引" not in raw and "转述" not in raw:
            print(f"✗ {f}: 提到《变老之前要知道》但没有\"转引/转述\"标注")
            bad += 1
    print("\n结论:", "无 ≥%d 字重合" % a.n if bad == 0 else f"发现 {bad} 处需人工判定")
    return 0

if __name__ == "__main__":
    sys.exit(main())
