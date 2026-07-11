#!/usr/bin/env python3
"""Publish a staged post to Instagram via the Meta Graph API.

Instagram's Content Publishing API does not accept file uploads — it fetches
media from a PUBLIC URL. In the GitHub Actions flow, the image is committed to
the repo first, so it is reachable at raw.githubusercontent.com. This script
turns the staged image(s) into that public URL, creates a media container, and
publishes it.

Uses the Instagram API with Instagram Login (graph.instagram.com). The token is
an Instagram user access token (starts with "IGAA...") and IG_USER_ID is the
Instagram-scoped account id shown when the token was generated.

Env vars:
    IG_USER_ID        Instagram account id (numeric, e.g. 178414...)
    IG_ACCESS_TOKEN   Instagram user access token (IGAA...)
    PUBLIC_BASE       e.g. https://raw.githubusercontent.com/<owner>/<repo>/main
    POST_JSON         path to the staged post.json (default from arg)
Optional:
    GRAPH_VERSION     default v21.0
"""
import os, sys, json, time, urllib.parse, urllib.request, urllib.error

GRAPH = os.environ.get("GRAPH_VERSION", "v21.0")
BASE = f"https://graph.instagram.com/{GRAPH}"

def _env():
    return (os.environ["IG_USER_ID"], os.environ["IG_ACCESS_TOKEN"],
            os.environ["PUBLIC_BASE"].rstrip("/"))

def _open(req_or_url):
    """Open a request and surface Meta's real error body on failure."""
    try:
        with urllib.request.urlopen(req_or_url) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", "ignore")
        raise RuntimeError(f"Graph API {e.code}: {body}") from None

def _post(path, params):
    _, token, _ = _env()
    data = urllib.parse.urlencode({**params, "access_token": token}).encode()
    return _open(urllib.request.Request(f"{BASE}/{path}", data=data, method="POST"))

def _get(path, params):
    _, token, _ = _env()
    q = urllib.parse.urlencode({**params, "access_token": token})
    return _open(f"{BASE}/{path}?{q}")

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

def _wait_ready(container_id, tries=30, delay=6):
    """Poll a container until Instagram has processed it. Missing status = keep waiting."""
    seen_status = False
    for _ in range(tries):
        st = _get(container_id, {"fields": "status_code"})
        code = st.get("status_code")
        if code == "FINISHED":
            return
        if code == "ERROR":
            raise RuntimeError(f"container processing error: {st}")
        if code is None and seen_status:
            return                      # field stopped being reported -> treat as done
        seen_status = seen_status or code is not None
        time.sleep(delay)
    # fall through: let the publish-retry handle final readiness

def _publish(uid, container_id):
    """Publish, retrying when Instagram says the media isn't ready yet (2207027)."""
    _wait_ready(container_id)
    last = None
    for _ in range(12):
        try:
            return _post(f"{uid}/media_publish", {"creation_id": container_id})
        except RuntimeError as e:
            last = e
            s = str(e)
            if "2207027" in s or "not ready" in s.lower() or '"code":9007' in s:
                time.sleep(8); continue
            raise
    raise last

_FETCH_ERRS = ("2207052", "2207003", "9004", "could not be fetched",
               "media download has failed", "not be fetched")

def _create(uid, params):
    """Create a media container, retrying when Instagram transiently fails to
    fetch the media from the raw URL (CDN hiccups clear on retry)."""
    last = None
    for _ in range(6):
        try:
            return _post(f"{uid}/media", params)
        except RuntimeError as e:
            last = e; s = str(e)
            if any(k in s for k in _FETCH_ERRS):
                time.sleep(10); continue
            raise
    raise last

def publish_single(image_url, caption):
    uid = _env()[0]
    c = _create(uid, {"image_url": image_url, "caption": caption})
    return _publish(uid, c["id"])

def publish_carousel(image_urls, caption):
    uid = _env()[0]
    children = []
    for u in image_urls:
        ch = _create(uid, {"image_url": u, "is_carousel_item": "true"})
        _wait_ready(ch["id"])
        children.append(ch["id"])
    c = _create(uid, {
        "media_type": "CAROUSEL", "children": ",".join(children), "caption": caption})
    return _publish(uid, c["id"])

def publish_reel(video_url, caption, cover_url=None):
    uid = _env()[0]
    params = {"media_type": "REELS", "video_url": video_url, "caption": caption}
    if cover_url:
        params["cover_url"] = cover_url
    c = _create(uid, params)
    return _publish(uid, c["id"])

def publish_story(media_url, is_video=False):
    uid = _env()[0]
    params = {"media_type": "STORIES", ("video_url" if is_video else "image_url"): media_url}
    c = _create(uid, params)
    return _publish(uid, c["id"])   # waits until Instagram finishes processing

def _also_story(media_url, is_video):
    """Best effort: mirror the post to the Story. Never fails the feed post."""
    try:
        r = publish_story(media_url, is_video)
        print(f"  story posted -> {r.get('id')}")
    except Exception as e:
        print(f"  story skipped: {e}")

def _post_story(post, public_base, fallback_url):
    """Story is always the branded 9:16 image (with 'see full post' prompt)."""
    story_url = f"{public_base}/{post['story']}" if post.get("story") else fallback_url
    if not post.get("story") or wait_for_url(story_url):
        _also_story(story_url, is_video=False)

def publish_post(post, public_base):
    """post = {caption, images:[...]} or {caption, video: rel}. Also posts to Story."""
    caption = post["caption"]
    if post.get("video"):
        url = f"{public_base}/{post['video']}"
        if not wait_for_url(url):
            raise RuntimeError(f"media not reachable: {url}")
        cover_url = None
        if post.get("cover"):
            cover_url = f"{public_base}/{post['cover']}"
            if not wait_for_url(cover_url):
                cover_url = None
        res = publish_reel(url, caption, cover_url)
        _post_story(post, public_base, cover_url or url)
        return res
    urls = [f"{public_base}/{rel}" for rel in post["images"]]
    for u in urls:
        if not wait_for_url(u):
            raise RuntimeError(f"media not reachable: {u}")
    res = publish_carousel(urls, caption) if len(urls) > 1 else publish_single(urls[0], caption)
    _post_story(post, public_base, urls[0])
    return res

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
