#!/usr/bin/env python3
"""Publish a staged post to Instagram via the Meta Graph API.

Instagram's Content Publishing API does not accept file uploads — it fetches
media from a PUBLIC URL. In the GitHub Actions flow, the image is committed to
the repo first, so it is reachable at raw.githubusercontent.com. This script
turns the staged image(s) into that public URL, creates a media container, and
publishes it.

Env vars:
    IG_USER_ID        Instagram Business/Creator account id (numeric)
    IG_ACCESS_TOKEN   long-lived user token or (better) System User token
    PUBLIC_BASE       e.g. https://raw.githubusercontent.com/<owner>/<repo>/main
    POST_JSON         path to the staged post.json (default from arg)
Optional:
    GRAPH_VERSION     default v21.0
"""
import os, sys, json, time, urllib.parse, urllib.request

GRAPH = os.environ.get("GRAPH_VERSION", "v21.0")
BASE = f"https://graph.facebook.com/{GRAPH}"

def _env():
    return (os.environ["IG_USER_ID"], os.environ["IG_ACCESS_TOKEN"],
            os.environ["PUBLIC_BASE"].rstrip("/"))

def _post(path, params):
    _, token, _ = _env()
    data = urllib.parse.urlencode({**params, "access_token": token}).encode()
    req = urllib.request.Request(f"{BASE}/{path}", data=data, method="POST")
    with urllib.request.urlopen(req) as r:
        return json.load(r)

def _get(path, params):
    _, token, _ = _env()
    q = urllib.parse.urlencode({**params, "access_token": token})
    with urllib.request.urlopen(f"{BASE}/{path}?{q}") as r:
        return json.load(r)

def wait_for_url(url, tries=10, delay=6):
    """raw.githubusercontent can lag a few seconds after a push."""
    for _ in range(tries):
        try:
            req = urllib.request.Request(url, method="HEAD")
            with urllib.request.urlopen(req) as r:
                if r.status == 200:
                    return True
        except Exception:
            pass
        time.sleep(delay)
    return False

def publish_single(image_url, caption):
    uid = _env()[0]
    c = _post(f"{uid}/media", {"image_url": image_url, "caption": caption})
    return _post(f"{uid}/media_publish", {"creation_id": c["id"]})

def publish_carousel(image_urls, caption):
    uid = _env()[0]
    children = []
    for u in image_urls:
        ch = _post(f"{uid}/media", {"image_url": u, "is_carousel_item": "true"})
        children.append(ch["id"])
    c = _post(f"{uid}/media", {
        "media_type": "CAROUSEL", "children": ",".join(children), "caption": caption})
    return _post(f"{uid}/media_publish", {"creation_id": c["id"]})

def publish_reel(video_url, caption):
    uid = _env()[0]
    c = _post(f"{uid}/media", {
        "media_type": "REELS", "video_url": video_url, "caption": caption})
    # reels must finish processing before publish
    for _ in range(30):
        st = _get(c["id"], {"fields": "status_code"})
        if st.get("status_code") == "FINISHED":
            break
        if st.get("status_code") == "ERROR":
            raise RuntimeError(f"reel processing error: {st}")
        time.sleep(15)
    return _post(f"{uid}/media_publish", {"creation_id": c["id"]})

def publish_post(post, public_base):
    """post = {caption, images:[rel...]} or {caption, video: rel}."""
    caption = post["caption"]
    if post.get("video"):
        url = f"{public_base}/{post['video']}"
        if not wait_for_url(url):
            raise RuntimeError(f"media not reachable: {url}")
        return publish_reel(url, caption)
    urls = [f"{public_base}/{rel}" for rel in post["images"]]
    for u in urls:
        if not wait_for_url(u):
            raise RuntimeError(f"media not reachable: {u}")
    return publish_carousel(urls, caption) if len(urls) > 1 else publish_single(urls[0], caption)

def main():
    post_json = os.environ.get("POST_JSON") or (sys.argv[1] if len(sys.argv) > 1 else None)
    if not post_json:
        sys.exit("usage: POST_JSON=path publish_instagram.py  (or pass path as arg)")
    with open(post_json) as f:
        post = json.load(f)
    res = publish_post(post, _env()[2])
    print("PUBLISHED media id:", res.get("id"))

if __name__ == "__main__":
    main()
