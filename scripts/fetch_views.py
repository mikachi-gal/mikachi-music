"""チッケム再生リストの動画の累計再生数を YouTube Data API で取得し、data/views.json に日付ごとに記録する。

GitHub Actions から毎日1回実行する想定。
APIキーは環境変数 YT_API_KEY から読む（GitHub のリポジトリシークレットに登録する）。
標準ライブラリだけで動く。
"""
import datetime
import json
import os
import sys
import urllib.parse
import urllib.request

PLAYLIST_ID = "PLxfDWMKr7Nj5Jz5uYBF5tg-KGKDjhwA-d"
DATA_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "views.json")
FANS_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "fans.json")
API = "https://www.googleapis.com/youtube/v3/"
JST = datetime.timezone(datetime.timedelta(hours=9))


def call(endpoint, params):
    params = dict(params, key=os.environ["YT_API_KEY"])
    url = API + endpoint + "?" + urllib.parse.urlencode(params)
    with urllib.request.urlopen(url, timeout=30) as r:
        return json.load(r)


def playlist_video_ids():
    ids, token = [], None
    while True:
        p = {"part": "contentDetails", "playlistId": PLAYLIST_ID, "maxResults": 50}
        if token:
            p["pageToken"] = token
        d = call("playlistItems", p)
        ids += [it["contentDetails"]["videoId"] for it in d.get("items", [])]
        token = d.get("nextPageToken")
        if not token:
            return ids


def video_stats(ids):
    out = {}
    for i in range(0, len(ids), 50):
        d = call("videos", {"part": "snippet,statistics", "id": ",".join(ids[i:i + 50])})
        for it in d.get("items", []):
            out[it["id"]] = {
                "title": it["snippet"]["title"],
                "channel": it["snippet"]["channelTitle"],
                "published": it["snippet"]["publishedAt"][:10],
                "views": int(it["statistics"].get("viewCount", 0)),
            }
    return out


def main():
    if not os.environ.get("YT_API_KEY"):
        sys.exit("YT_API_KEY が設定されていません")
    try:
        with open(DATA_PATH, encoding="utf-8") as f:
            data = json.load(f)
    except FileNotFoundError:
        data = {}
    data.setdefault("videos", {})
    data.setdefault("history", {})

    # 再生リストの動画に加えて、みかちのおすすめ（fans.json）にある動画も記録する
    ids = playlist_video_ids()
    try:
        with open(FANS_PATH, encoding="utf-8") as f:
            ids += [v for v in json.load(f) if v not in ids]
    except FileNotFoundError:
        pass
    stats = video_stats(ids)
    today = datetime.datetime.now(JST).date().isoformat()
    data["history"][today] = {vid: s["views"] for vid, s in stats.items()}
    for vid, s in stats.items():
        data["videos"][vid] = {"title": s["title"], "channel": s["channel"], "published": s["published"]}
    data["playlist"] = list(stats.keys())
    data["updated"] = datetime.datetime.now(JST).isoformat(timespec="minutes")

    os.makedirs(os.path.dirname(DATA_PATH), exist_ok=True)
    with open(DATA_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1, sort_keys=True)
    print(f"{today}: {len(stats)} 本の再生数を記録しました")


if __name__ == "__main__":
    main()
