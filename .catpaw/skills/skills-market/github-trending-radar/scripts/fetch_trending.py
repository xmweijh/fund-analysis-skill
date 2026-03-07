#!/usr/bin/env python3
"""
GitHub Trending 数据抓取工具
从 GitHub Trending 页面抓取热门项目信息，支持按语言和时间范围筛选。
"""

import json
import sys
import re
import urllib.request
import urllib.error
from html.parser import HTMLParser


class TrendingParser(HTMLParser):
    """解析 GitHub Trending 页面 HTML"""

    def __init__(self):
        super().__init__()
        self.repos = []
        self.current = {}
        self.in_repo = False
        self.in_desc = False
        self.in_lang = False
        self.in_stars = False
        self.in_forks = False
        self.in_today_stars = False
        self.capture = ""
        self.tag_stack = []

    def handle_starttag(self, tag, attrs):
        attrs_dict = dict(attrs)
        cls = attrs_dict.get("class", "")

        if tag == "article" and "Box-row" in cls:
            self.in_repo = True
            self.current = {"name": "", "desc": "", "lang": "", "stars": "", "forks": "", "today_stars": "", "url": ""}

        if self.in_repo:
            if tag == "a" and "h2" not in cls:
                href = attrs_dict.get("href", "")
                if href and href.count("/") == 2 and not self.current["name"]:
                    self.current["name"] = href.strip("/")
                    self.current["url"] = f"https://github.com{href}"

            if tag == "p" and "col-9" in cls:
                self.in_desc = True
                self.capture = ""

            if tag == "span" and "d-inline-block" in cls and "ml-0" in cls:
                self.in_lang = True
                self.capture = ""

            if tag == "a" and "/stargazers" in attrs_dict.get("href", ""):
                self.in_stars = True
                self.capture = ""

            if tag == "a" and "/forks" in attrs_dict.get("href", ""):
                self.in_forks = True
                self.capture = ""

            if tag == "span" and "d-inline-block" in cls and "float-sm-right" in cls:
                self.in_today_stars = True
                self.capture = ""

    def handle_endtag(self, tag):
        if tag == "article" and self.in_repo:
            self.in_repo = False
            if self.current.get("name"):
                self.repos.append(self.current)
            self.current = {}

        if self.in_desc and tag == "p":
            self.in_desc = False
            self.current["desc"] = self.capture.strip()

        if self.in_lang and tag == "span":
            self.in_lang = False
            self.current["lang"] = self.capture.strip()

        if self.in_stars and tag == "a":
            self.in_stars = False
            self.current["stars"] = self.capture.strip().replace(",", "").replace(" ", "")

        if self.in_forks and tag == "a":
            self.in_forks = False
            self.current["forks"] = self.capture.strip().replace(",", "").replace(" ", "")

        if self.in_today_stars and tag == "span":
            self.in_today_stars = False
            self.current["today_stars"] = self.capture.strip()

    def handle_data(self, data):
        if any([self.in_desc, self.in_lang, self.in_stars, self.in_forks, self.in_today_stars]):
            self.capture += data


def fetch_trending(language="", since="daily"):
    """
    抓取 GitHub Trending
    language: 编程语言筛选 (python, javascript, go, rust, etc.)，空字符串为全部
    since: daily / weekly / monthly
    """
    url = f"https://github.com/trending/{language}?since={since}"
    req = urllib.request.Request(url)
    req.add_header("User-Agent", "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36")
    req.add_header("Accept", "text/html,application/xhtml+xml")
    req.add_header("Accept-Language", "en-US,en;q=0.9")

    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            html = resp.read().decode("utf-8", errors="ignore")
    except Exception as e:
        print(f"ERROR fetching trending: {e}", file=sys.stderr)
        return []

    parser = TrendingParser()
    parser.feed(html)
    return parser.repos


def fetch_readme(repo_name, max_chars=3000):
    """获取仓库 README 内容（截取前 max_chars 字符）"""
    for branch in ["main", "master"]:
        url = f"https://raw.githubusercontent.com/{repo_name}/{branch}/README.md"
        req = urllib.request.Request(url)
        req.add_header("User-Agent", "Mozilla/5.0")
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                content = resp.read().decode("utf-8", errors="ignore")
                if len(content) > max_chars:
                    content = content[:max_chars] + "\n... (truncated)"
                return content
        except:
            continue
    return ""


def fetch_repo_info(repo_name):
    """通过 GitHub API 获取仓库详情（无需 token，有频率限制）"""
    url = f"https://api.github.com/repos/{repo_name}"
    req = urllib.request.Request(url)
    req.add_header("User-Agent", "Mozilla/5.0")
    req.add_header("Accept", "application/vnd.github.v3+json")
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except:
        return {}


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Fetch GitHub Trending repos")
    parser.add_argument("--lang", default="", help="Language filter (python, javascript, go, rust, etc.)")
    parser.add_argument("--since", default="daily", choices=["daily", "weekly", "monthly"])
    parser.add_argument("--limit", type=int, default=10, help="Max repos to return")
    parser.add_argument("--readme", action="store_true", help="Also fetch README for each repo")
    parser.add_argument("--detail", action="store_true", help="Fetch detailed repo info via API")
    parser.add_argument("--format", default="json", choices=["json", "markdown"])
    args = parser.parse_args()

    print(f"Fetching GitHub Trending ({args.since}, lang={args.lang or 'all'})...", file=sys.stderr)
    repos = fetch_trending(language=args.lang, since=args.since)

    if not repos:
        print("No trending repos found.", file=sys.stderr)
        # 降级方案：通过 API 搜索
        print("Falling back to GitHub Search API...", file=sys.stderr)
        search_url = "https://api.github.com/search/repositories?q=stars:>100+pushed:>2026-01-01&sort=stars&order=desc&per_page=" + str(args.limit)
        req = urllib.request.Request(search_url)
        req.add_header("User-Agent", "Mozilla/5.0")
        req.add_header("Accept", "application/vnd.github.v3+json")
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                for item in data.get("items", [])[:args.limit]:
                    repos.append({
                        "name": item["full_name"],
                        "desc": item.get("description", ""),
                        "lang": item.get("language", ""),
                        "stars": str(item.get("stargazers_count", 0)),
                        "forks": str(item.get("forks_count", 0)),
                        "today_stars": "",
                        "url": item["html_url"],
                    })
        except Exception as e:
            print(f"Search API also failed: {e}", file=sys.stderr)

    repos = repos[:args.limit]

    if args.readme:
        for i, repo in enumerate(repos):
            print(f"  [{i+1}/{len(repos)}] Fetching README for {repo['name']}...", file=sys.stderr)
            repo["readme"] = fetch_readme(repo["name"])

    if args.detail:
        for i, repo in enumerate(repos):
            print(f"  [{i+1}/{len(repos)}] Fetching details for {repo['name']}...", file=sys.stderr)
            info = fetch_repo_info(repo["name"])
            if info:
                repo["topics"] = info.get("topics", [])
                repo["license"] = info.get("license", {}).get("spdx_id", "") if info.get("license") else ""
                repo["created_at"] = info.get("created_at", "")
                repo["open_issues"] = info.get("open_issues_count", 0)
                repo["watchers"] = info.get("subscribers_count", 0)

    if args.format == "markdown":
        print(f"\n# GitHub Trending ({args.since})\n")
        for i, repo in enumerate(repos, 1):
            print(f"## {i}. [{repo['name']}]({repo['url']})")
            print(f"- **Description**: {repo['desc']}")
            print(f"- **Language**: {repo['lang'] or 'N/A'}")
            print(f"- **Stars**: {repo['stars']} | **Forks**: {repo['forks']}")
            if repo.get("today_stars"):
                print(f"- **Today**: {repo['today_stars']}")
            if repo.get("topics"):
                print(f"- **Topics**: {', '.join(repo['topics'])}")
            if repo.get("license"):
                print(f"- **License**: {repo['license']}")
            print()
    else:
        print(json.dumps(repos, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()