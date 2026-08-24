#!/usr/bin/env python3
"""自动重建首页文章表格。

扫描内容目录下的文章，重建 index.md 的「## 目录」区块（文章索引以首页为准，README 不再重复维护），
表格列：文章标题（超链接到文档页）｜文章简介｜发布时间。

- 简介：文章 front matter 的 `description`；缺失时取正文首个非空段落。
- 发布时间：front matter 的 `date` → git 首次提交日期 → 今天。
"""
import os
import re
import subprocess
import sys
from datetime import date

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SITE_BASE = 'https://coderliux.github.io/blog/'
SKIP_DIRS = {'.git', '_layouts', 'assets', '.github', 'scripts', 'docs'}
TARGETS = ['index.md']


def read(path):
    with open(path, encoding='utf-8') as f:
        return f.read()


def write(path, text):
    with open(path, 'w', encoding='utf-8') as f:
        f.write(text)


def parse_fm(text):
    fm = {}
    m = re.match(r'\A---\s*\n(.*?)\n---\s*\n', text, re.S)
    if m:
        for line in m.group(1).splitlines():
            k, sep, v = line.partition(':')
            if sep:
                fm[k.strip()] = v.strip().strip('"\'')
    return fm


def git_first_commit_date(relpath):
    try:
        out = subprocess.check_output(
            ['git', 'log', '--follow', '--reverse', '--format=%cs', '--', relpath],
            cwd=ROOT, text=True).strip()
        lines = [x for x in out.splitlines() if x]
        return lines[0] if lines else None
    except Exception:
        return None


def title_of(path):
    text = read(path)
    fm = parse_fm(text)
    if fm.get('title'):
        return fm['title']
    m = re.search(r'^#\s+(.+)$', text, re.M)
    return m.group(1).strip() if m else os.path.basename(path)[:-3]


def summary_of(path):
    text = read(path)
    fm = parse_fm(text)
    if fm.get('description'):
        return fm['description']
    body = re.sub(r'\A---.*?---\s*\n', '', text, flags=re.S)
    body = re.sub(r'^#{1,6}\s.*$', '', body, flags=re.M)
    for line in body.splitlines():
        line = line.strip()
        if line and not line.startswith(('#', '|', '>', '```')):
            return line[:120]
    return ''


def date_of(path, relpath):
    fm = parse_fm(read(path))
    d = fm.get('date')
    if d and re.match(r'^\d{4}-\d{2}-\d{2}$', d):
        return d
    d = git_first_commit_date(relpath)
    return d or date.today().isoformat()


def collect():
    articles = {}
    for name in sorted(os.listdir(ROOT)):
        if name.startswith('.') or name in SKIP_DIRS:
            continue
        dpath = os.path.join(ROOT, name)
        if not os.path.isdir(dpath):
            continue
        for dirpath, dirnames, filenames in os.walk(dpath):
            dirnames[:] = [d for d in dirnames if not d.startswith('_')]
            for fn in filenames:
                if not fn.endswith('.md'):
                    continue
                full = os.path.join(dirpath, fn)
                rel = os.path.relpath(full, ROOT)
                page = os.path.relpath(full, ROOT)[:-3] + '/'
                articles.setdefault(name, []).append({
                    'title': title_of(full),
                    'summary': summary_of(full),
                    'rel': page,
                    'abs': SITE_BASE + page,
                    'date': date_of(full, rel),
                })
    return articles


def build_section(articles, link_key):
    body = ['']
    for d in sorted(articles):
        lst = sorted(articles[d], key=lambda x: x['date'], reverse=True)
        body.append(f'### {d}')
        body.append('')
        body.append('| 标题 | 简介 | 发布时间 |')
        body.append('|------|------|----------|')
        for a in lst:
            body.append(f'| [{a["title"]}]({a[link_key]}) | {a["summary"]} | {a["date"]} |')
        body.append('')
    return '\n'.join(body)


def replace_toc(text, section):
    lines = text.splitlines()
    try:
        toc_idx = next(i for i, l in enumerate(lines) if l.strip() == '## 目录')
    except StopIteration:
        return text
    next_idx = next((i for i in range(toc_idx + 1, len(lines)) if lines[i].startswith('## ')), len(lines))
    block = lines[:toc_idx + 1] + section.splitlines() + [''] + lines[next_idx:]
    return '\n'.join(block) + '\n'


def main():
    articles = collect()
    if not articles:
        print('未找到文章，跳过')
        return 1
    for fname in TARGETS:
        path = os.path.join(ROOT, fname)
        old = read(path)
        key = 'rel' if fname == 'index.md' else 'abs'
        new = replace_toc(old, build_section(articles, key))
        if new != old:
            write(path, new)
            print(f'已更新: {fname}')
        else:
            print(f'无需更新: {fname}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
