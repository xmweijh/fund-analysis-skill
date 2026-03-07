#!/usr/bin/env python3
"""
Xiaohongshu MCP Client - A Python client for xiaohongshu-mcp HTTP API.

Usage:
    python xhs_client.py <command> [options]

Commands:
    status                          Check login status
    qrcode                          Get login QR code (Base64 image)
    logout                          Delete cookies and reset login
    search <keyword>                Search notes by keyword
    detail <feed_id> <xsec_token>   Get note details
    feeds                           Get recommended feed list
    publish <title> <content> <images>              Publish a note with images
    publish_video <title> <content> <video_path>   Publish a note with video
    comment <feed_id> <xsec_token> <content>       Post a comment to a note
    reply <feed_id> <xsec_token> <content>         Reply to a comment (requires comment_id or user_id)
    like <feed_id> <xsec_token>                    Like a note (or unlike with --unlike flag)
    favorite <feed_id> <xsec_token>                Favorite a note (or unfavorite with --unfavorite flag)
    user <user_id> <xsec_token>                    Get user profile information

Examples:
    python xhs_client.py status
    python xhs_client.py qrcode
    python xhs_client.py logout
    python xhs_client.py search "咖啡推荐"
    python xhs_client.py detail "abc123" "token456"
    python xhs_client.py feeds
    python xhs_client.py publish "标题" "内容" "/path/to/image.jpg"
    python xhs_client.py publish_video "标题" "内容" "/path/to/video.mp4"
    python xhs_client.py comment "abc123" "token456" "这是评论内容"
    python xhs_client.py reply "abc123" "token456" "这是回复内容" --comment-id "comment456"
    python xhs_client.py like "abc123" "token456"
    python xhs_client.py like "abc123" "token456" --unlike
    python xhs_client.py favorite "abc123" "token456"
    python xhs_client.py user "user123" "token456"
"""

import argparse
import json
import sys
import requests

BASE_URL = "http://localhost:18060"
TIMEOUT = 60


def check_status():
    """Check login status."""
    try:
        resp = requests.get(f"{BASE_URL}/api/v1/login/status", timeout=TIMEOUT)
        data = resp.json()
        if data.get("success"):
            login_info = data.get("data", {})
            if login_info.get("is_logged_in"):
                print(f"✅ Logged in as: {login_info.get('username', 'Unknown')}")
            else:
                print("❌ Not logged in. Please run the login tool first.")
        else:
            print(f"❌ Error: {data.get('error', 'Unknown error')}")
        return data
    except requests.exceptions.ConnectionError:
        print("❌ Cannot connect to MCP server. Make sure xiaohongshu-mcp is running on localhost:18060")
        sys.exit(1)


def search_notes(keyword, sort_by="综合", note_type="不限", publish_time="不限"):
    """Search notes by keyword with optional filters."""
    try:
        payload = {
            "keyword": keyword,
            "filters": {
                "sort_by": sort_by,
                "note_type": note_type,
                "publish_time": publish_time
            }
        }
        resp = requests.post(
            f"{BASE_URL}/api/v1/feeds/search",
            json=payload,
            timeout=TIMEOUT
        )
        data = resp.json()
        
        if data.get("success"):
            feeds = data.get("data", {}).get("feeds", [])
            print(f"🔍 Found {len(feeds)} notes for '{keyword}':\n")
            
            for i, feed in enumerate(feeds, 1):
                note_card = feed.get("noteCard", {})
                user = note_card.get("user", {})
                interact = note_card.get("interactInfo", {})
                
                print(f"[{i}] {note_card.get('displayTitle', 'No title')}")
                print(f"    Author: {user.get('nickname', 'Unknown')}")
                print(f"    Likes: {interact.get('likedCount', '0')} | Collects: {interact.get('collectedCount', '0')} | Comments: {interact.get('commentCount', '0')}")
                print(f"    feed_id: {feed.get('id')}")
                print(f"    xsec_token: {feed.get('xsecToken').strip('=')}")
                print()
        else:
            print(f"❌ Search failed: {data.get('error', 'Unknown error')}")
        
        return data
    except requests.exceptions.ConnectionError:
        print("❌ Cannot connect to MCP server.")
        sys.exit(1)


def get_note_detail(feed_id, xsec_token, load_comments=False):
    """Get detailed information about a specific note."""
    try:
        payload = {
            "feed_id": feed_id,
            "xsec_token": xsec_token,
            "load_all_comments": load_comments
        }
        resp = requests.post(
            f"{BASE_URL}/api/v1/feeds/detail",
            json=payload,
            timeout=TIMEOUT
        )
        data = resp.json()
        
        if data.get("success"):
            note_data = data.get("data", {}).get("data", {})
            note = note_data.get("note", {})
            comments = note_data.get("comments", {})
            
            print(f"📝 Note Details:\n")
            print(f"Title: {note.get('title', 'No title')}")
            print(f"Author: {note.get('user', {}).get('nickname', 'Unknown')}")
            print(f"Location: {note.get('ipLocation', 'Unknown')}")
            print(f"\nContent:\n{note.get('desc', 'No content')}\n")
            
            interact = note.get("interactInfo", {})
            print(f"Likes: {interact.get('likedCount', '0')} | Collects: {interact.get('collectedCount', '0')} | Comments: {interact.get('commentCount', '0')}")
            
            comment_list = comments.get("list", [])
            if comment_list:
                print(f"\n💬 Top Comments ({len(comment_list)}):")
                for c in comment_list[:5]:
                    user_info = c.get("userInfo", {})
                    print(f"  - {user_info.get('nickname', 'Anonymous')}: {c.get('content', '')}")
        else:
            print(f"❌ Failed to get details: {data.get('error', 'Unknown error')}")
        
        return data
    except requests.exceptions.ConnectionError:
        print("❌ Cannot connect to MCP server.")
        sys.exit(1)


def get_feeds():
    """Get recommended feed list."""
    try:
        resp = requests.get(f"{BASE_URL}/api/v1/feeds/list", timeout=TIMEOUT)
        data = resp.json()
        
        if data.get("success"):
            feeds = data.get("data", {}).get("feeds", [])
            print(f"📋 Recommended Feeds ({len(feeds)} notes):\n")
            
            for i, feed in enumerate(feeds, 1):
                note_card = feed.get("noteCard", {})
                user = note_card.get("user", {})
                interact = note_card.get("interactInfo", {})
                
                print(f"[{i}] {note_card.get('displayTitle', 'No title')}")
                print(f"    Author: {user.get('nickname', 'Unknown')}")
                print(f"    Likes: {interact.get('likedCount', '0')}")
                print()
        else:
            print(f"❌ Failed to get feeds: {data.get('error', 'Unknown error')}")
        
        return data
    except requests.exceptions.ConnectionError:
        print("❌ Cannot connect to MCP server.")
        sys.exit(1)


def publish_note(title, content, images, tags=None):
    """Publish a new note with images."""
    try:
        payload = {
            "title": title,
            "content": content,
            "images": images if isinstance(images, list) else [images]
        }
        if tags:
            payload["tags"] = tags if isinstance(tags, list) else [tags]
        
        resp = requests.post(
            f"{BASE_URL}/api/v1/publish",
            json=payload,
            timeout=120
        )
        data = resp.json()
        
        if data.get("success"):
            print(f"✅ Note published successfully!")
            print(f"   Post ID: {data.get('data', {}).get('post_id', 'Unknown')}")
        else:
            print(f"❌ Publish failed: {data.get('error', 'Unknown error')}")
        
        return data
    except requests.exceptions.ConnectionError:
        print("❌ Cannot connect to MCP server.")
        sys.exit(1)


def publish_video(title, content, video_path, tags=None):
    """Publish a new note with video."""
    try:
        payload = {
            "title": title,
            "content": content,
            "video": video_path
        }
        if tags:
            payload["tags"] = tags if isinstance(tags, list) else [tags]
        
        resp = requests.post(
            f"{BASE_URL}/api/v1/publish_with_video",
            json=payload,
            timeout=120
        )
        data = resp.json()
        
        if data.get("success"):
            print(f"✅ Video note published successfully!")
            print(f"   Post ID: {data.get('data', {}).get('post_id', 'Unknown')}")
        else:
            print(f"❌ Video publish failed: {data.get('error', 'Unknown error')}")
        
        return data
    except requests.exceptions.ConnectionError:
        print("❌ Cannot connect to MCP server.")
        sys.exit(1)


def post_comment(feed_id, xsec_token, content):
    """Post a comment to a note."""
    try:
        payload = {
            "feed_id": feed_id,
            "xsec_token": xsec_token,
            "content": content
        }
        resp = requests.post(
            f"{BASE_URL}/api/v1/feeds/comment",
            json=payload,
            timeout=TIMEOUT
        )
        data = resp.json()
        
        if data.get("success"):
            print(f"✅ Comment posted successfully!")
            print(f"   Comment ID: {data.get('data', {}).get('comment_id', 'Unknown')}")
        else:
            print(f"❌ Post comment failed: {data.get('error', 'Unknown error')}")
        
        return data
    except requests.exceptions.ConnectionError:
        print("❌ Cannot connect to MCP server.")
        sys.exit(1)


def get_user_profile(user_id, xsec_token):
    """Get user profile information."""
    try:
        payload = {
            "user_id": user_id,
            "xsec_token": xsec_token
        }
        resp = requests.post(
            f"{BASE_URL}/api/v1/user/profile",
            json=payload,
            timeout=TIMEOUT
        )
        data = resp.json()
        
        if data.get("success"):
            user = data.get("data", {}).get("user", {})
            
            print(f"👤 User Profile:\n")
            print(f"Username: {user.get('nickname', 'Unknown')}")
            print(f"User ID: {user.get('id', 'Unknown')}")
            print(f"Bio: {user.get('signature', 'No bio')}")
            
            stats = user.get("stats", {})
            print(f"\nStats:")
            print(f"  Followers: {stats.get('followerCount', '0')}")
            print(f"  Following: {stats.get('followingCount', '0')}")
            print(f"  Notes: {stats.get('noteCount', '0')}")
            print(f"  Likes: {stats.get('likeCount', '0')}")
            
            if user.get("avatar"):
                print(f"\nAvatar: {user.get('avatar')}")
        else:
            print(f"❌ Failed to get user profile: {data.get('error', 'Unknown error')}")
        
        return data
    except requests.exceptions.ConnectionError:
        print("❌ Cannot connect to MCP server.")
        sys.exit(1)


def get_login_qrcode():
    """Get login QR code (Base64 encoded)."""
    try:
        resp = requests.get(f"{BASE_URL}/api/v1/login/qrcode", timeout=TIMEOUT)
        data = resp.json()
        
        if data.get("success"):
            qrcode_data = data.get("data", {})
            qrcode_image = qrcode_data.get("qrcode", "")
            timeout_info = qrcode_data.get("timeout", "Unknown")
            
            print(f"🔐 Login QR Code:\n")
            print(f"Timeout: {timeout_info}")
            print(f"\nQR Code (Base64 encoded):\n")
            print(qrcode_image[:100] + "..." if len(qrcode_image) > 100 else qrcode_image)
            print(f"\n💡 Tip: Scan this QR code with your Xiaohongshu app to log in.")
        else:
            print(f"❌ Failed to get QR code: {data.get('error', 'Unknown error')}")
        
        return data
    except requests.exceptions.ConnectionError:
        print("❌ Cannot connect to MCP server.")
        sys.exit(1)


def delete_cookies():
    """Delete cookies and reset login status."""
    try:
        resp = requests.post(f"{BASE_URL}/api/v1/login/logout", timeout=TIMEOUT)
        data = resp.json()
        
        if data.get("success"):
            print(f"✅ Cookies deleted successfully!")
            print(f"🔄 Login status has been reset. Please use the qrcode command to log in again.")
        else:
            print(f"❌ Failed to delete cookies: {data.get('error', 'Unknown error')}")
        
        return data
    except requests.exceptions.ConnectionError:
        print("❌ Cannot connect to MCP server.")
        sys.exit(1)


def reply_comment(feed_id, xsec_token, content, comment_id=None, user_id=None):
    """Reply to a comment on a note."""
    try:
        if not comment_id and not user_id:
            print("❌ Error: Must provide either comment_id or user_id")
            return None
        
        payload = {
            "feed_id": feed_id,
            "xsec_token": xsec_token,
            "content": content
        }
        if comment_id:
            payload["comment_id"] = comment_id
        if user_id:
            payload["user_id"] = user_id
        
        resp = requests.post(
            f"{BASE_URL}/api/v1/feeds/reply_comment",
            json=payload,
            timeout=TIMEOUT
        )
        data = resp.json()
        
        if data.get("success"):
            print(f"✅ Reply posted successfully!")
            print(f"   Reply ID: {data.get('data', {}).get('reply_id', 'Unknown')}")
        else:
            print(f"❌ Post reply failed: {data.get('error', 'Unknown error')}")
        
        return data
    except requests.exceptions.ConnectionError:
        print("❌ Cannot connect to MCP server.")
        sys.exit(1)


def like_feed(feed_id, xsec_token, unlike=False):
    """Like or unlike a note."""
    try:
        payload = {
            "feed_id": feed_id,
            "xsec_token": xsec_token,
            "unlike": unlike
        }
        resp = requests.post(
            f"{BASE_URL}/api/v1/feeds/like",
            json=payload,
            timeout=TIMEOUT
        )
        data = resp.json()
        
        if data.get("success"):
            action = "unliked" if unlike else "liked"
            print(f"✅ Note {action} successfully!")
        else:
            print(f"❌ Like operation failed: {data.get('error', 'Unknown error')}")
        
        return data
    except requests.exceptions.ConnectionError:
        print("❌ Cannot connect to MCP server.")
        sys.exit(1)


def favorite_feed(feed_id, xsec_token, unfavorite=False):
    """Favorite or unfavorite a note."""
    try:
        payload = {
            "feed_id": feed_id,
            "xsec_token": xsec_token,
            "unfavorite": unfavorite
        }
        resp = requests.post(
            f"{BASE_URL}/api/v1/feeds/favorite",
            json=payload,
            timeout=TIMEOUT
        )
        data = resp.json()
        
        if data.get("success"):
            action = "unfavorited" if unfavorite else "favorited"
            print(f"✅ Note {action} successfully!")
        else:
            print(f"❌ Favorite operation failed: {data.get('error', 'Unknown error')}")
        
        return data
    except requests.exceptions.ConnectionError:
        print("❌ Cannot connect to MCP server.")
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(
        description="Xiaohongshu MCP Client",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    subparsers = parser.add_subparsers(dest="command", help="Available commands")
    
    # status command
    subparsers.add_parser("status", help="Check login status")
    
    # search command
    search_parser = subparsers.add_parser("search", help="Search notes")
    search_parser.add_argument("keyword", help="Search keyword")
    search_parser.add_argument("--sort", default="综合", 
                               choices=["综合", "最新", "最多点赞", "最多评论", "最多收藏"],
                               help="Sort by")
    search_parser.add_argument("--type", default="不限",
                               choices=["不限", "视频", "图文"],
                               help="Note type")
    search_parser.add_argument("--time", default="不限",
                               choices=["不限", "一天内", "一周内", "半年内"],
                               help="Publish time")
    search_parser.add_argument("--json", action="store_true", help="Output raw JSON")
    
    # detail command
    detail_parser = subparsers.add_parser("detail", help="Get note details")
    detail_parser.add_argument("feed_id", help="Feed ID")
    detail_parser.add_argument("xsec_token", help="Security token")
    detail_parser.add_argument("--comments", action="store_true", help="Load all comments")
    detail_parser.add_argument("--json", action="store_true", help="Output raw JSON")
    
    # feeds command
    feeds_parser = subparsers.add_parser("feeds", help="Get recommended feeds")
    feeds_parser.add_argument("--json", action="store_true", help="Output raw JSON")
    
    # publish command
    publish_parser = subparsers.add_parser("publish", help="Publish a note with images")
    publish_parser.add_argument("title", help="Note title")
    publish_parser.add_argument("content", help="Note content")
    publish_parser.add_argument("images", help="Image paths/URLs (comma-separated)")
    publish_parser.add_argument("--tags", help="Tags (comma-separated)")
    publish_parser.add_argument("--json", action="store_true", help="Output raw JSON")
    
    # publish_video command
    video_parser = subparsers.add_parser("publish_video", help="Publish a note with video")
    video_parser.add_argument("title", help="Note title")
    video_parser.add_argument("content", help="Note content")
    video_parser.add_argument("video", help="Local video file path (required)")
    video_parser.add_argument("--tags", help="Tags (comma-separated)")
    video_parser.add_argument("--json", action="store_true", help="Output raw JSON")
    
    # comment command
    comment_parser = subparsers.add_parser("comment", help="Post a comment to a note")
    comment_parser.add_argument("feed_id", help="Feed ID")
    comment_parser.add_argument("xsec_token", help="Security token")
    comment_parser.add_argument("content", help="Comment content")
    comment_parser.add_argument("--json", action="store_true", help="Output raw JSON")
    
    # user command
    user_parser = subparsers.add_parser("user", help="Get user profile information")
    user_parser.add_argument("user_id", help="User ID")
    user_parser.add_argument("xsec_token", help="Security token")
    user_parser.add_argument("--json", action="store_true", help="Output raw JSON")
    
    # qrcode command
    qrcode_parser = subparsers.add_parser("qrcode", help="Get login QR code")
    qrcode_parser.add_argument("--json", action="store_true", help="Output raw JSON")
    
    # logout command
    logout_parser = subparsers.add_parser("logout", help="Delete cookies and reset login")
    logout_parser.add_argument("--json", action="store_true", help="Output raw JSON")
    
    # reply command
    reply_parser = subparsers.add_parser("reply", help="Reply to a comment")
    reply_parser.add_argument("feed_id", help="Feed ID")
    reply_parser.add_argument("xsec_token", help="Security token")
    reply_parser.add_argument("content", help="Reply content")
    reply_parser.add_argument("--comment-id", help="Target comment ID")
    reply_parser.add_argument("--user-id", help="Target comment user ID")
    reply_parser.add_argument("--json", action="store_true", help="Output raw JSON")
    
    # like command
    like_parser = subparsers.add_parser("like", help="Like or unlike a note")
    like_parser.add_argument("feed_id", help="Feed ID")
    like_parser.add_argument("xsec_token", help="Security token")
    like_parser.add_argument("--unlike", action="store_true", help="Unlike instead of like")
    like_parser.add_argument("--json", action="store_true", help="Output raw JSON")
    
    # favorite command
    favorite_parser = subparsers.add_parser("favorite", help="Favorite or unfavorite a note")
    favorite_parser.add_argument("feed_id", help="Feed ID")
    favorite_parser.add_argument("xsec_token", help="Security token")
    favorite_parser.add_argument("--unfavorite", action="store_true", help="Unfavorite instead of favorite")
    favorite_parser.add_argument("--json", action="store_true", help="Output raw JSON")
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        sys.exit(1)
    
    if args.command == "status":
        result = check_status()
    elif args.command == "qrcode":
        result = get_login_qrcode()
        if hasattr(args, 'json') and args.json:
            print(json.dumps(result, ensure_ascii=False, indent=2))
    elif args.command == "logout":
        result = delete_cookies()
        if hasattr(args, 'json') and args.json:
            print(json.dumps(result, ensure_ascii=False, indent=2))
    elif args.command == "search":
        result = search_notes(args.keyword, args.sort, args.type, args.time)
        if hasattr(args, 'json') and args.json:
            print(json.dumps(result, ensure_ascii=False, indent=2))
    elif args.command == "detail":
        result = get_note_detail(args.feed_id, args.xsec_token, args.comments)
        if hasattr(args, 'json') and args.json:
            print(json.dumps(result, ensure_ascii=False, indent=2))
    elif args.command == "feeds":
        result = get_feeds()
        if hasattr(args, 'json') and args.json:
            print(json.dumps(result, ensure_ascii=False, indent=2))
    elif args.command == "publish":
        images = args.images.split(",")
        tags = args.tags.split(",") if args.tags else None
        result = publish_note(args.title, args.content, images, tags)
        if hasattr(args, 'json') and args.json:
            print(json.dumps(result, ensure_ascii=False, indent=2))
    elif args.command == "publish_video":
        tags = args.tags.split(",") if args.tags else None
        result = publish_video(args.title, args.content, args.video, tags)
        if hasattr(args, 'json') and args.json:
            print(json.dumps(result, ensure_ascii=False, indent=2))
    elif args.command == "comment":
        result = post_comment(args.feed_id, args.xsec_token, args.content)
        if hasattr(args, 'json') and args.json:
            print(json.dumps(result, ensure_ascii=False, indent=2))
    elif args.command == "reply":
        comment_id = args.comment_id if hasattr(args, 'comment_id') else None
        user_id = args.user_id if hasattr(args, 'user_id') else None
        result = reply_comment(args.feed_id, args.xsec_token, args.content, comment_id, user_id)
        if result and hasattr(args, 'json') and args.json:
            print(json.dumps(result, ensure_ascii=False, indent=2))
    elif args.command == "like":
        result = like_feed(args.feed_id, args.xsec_token, args.unlike)
        if hasattr(args, 'json') and args.json:
            print(json.dumps(result, ensure_ascii=False, indent=2))
    elif args.command == "favorite":
        result = favorite_feed(args.feed_id, args.xsec_token, args.unfavorite)
        if hasattr(args, 'json') and args.json:
            print(json.dumps(result, ensure_ascii=False, indent=2))
    elif args.command == "user":
        result = get_user_profile(args.user_id, args.xsec_token)
        if hasattr(args, 'json') and args.json:
            print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
