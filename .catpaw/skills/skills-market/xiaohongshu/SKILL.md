---
name: xiaohongshu
description: >
  Automate Xiaohongshu (RedNote) content operations using a Python client for the xiaohongshu-mcp server.
  Use for: (1) Publishing image, text, and video content, (2) Searching for notes and trends,
  (3) Analyzing post details and comments, (4) Managing user profiles and content feeds.
  Triggers: xiaohongshu automation, rednote content, publish to xiaohongshu, xiaohongshu search, social media management.
---

# Xiaohongshu MCP Skill (with Python Client)

Automate content operations on Xiaohongshu (小红书) using a bundled Python script that interacts with the `xpzouying/xiaohongshu-mcp` server (8.4k+ stars).

**Project:** [xpzouying/xiaohongshu-mcp](https://github.com/xpzouying/xiaohongshu-mcp)

## 1. Local Server Setup

This skill requires the `xiaohongshu-mcp` server to be running on your local machine.

### Step 1: Download Binaries

Download the appropriate binaries for your system from the [GitHub Releases](https://github.com/xpzouying/xiaohongshu-mcp/releases) page.

| Platform | MCP Server | Login Tool |
| -------- | ---------- | ---------- |
| macOS (Apple Silicon) | `xiaohongshu-mcp-darwin-arm64` | `xiaohongshu-login-darwin-arm64` |
| macOS (Intel) | `xiaohongshu-mcp-darwin-amd64` | `xiaohongshu-login-darwin-amd64` |
| Windows | `xiaohongshu-mcp-windows-amd64.exe` | `xiaohongshu-login-windows-amd64.exe` |
| Linux | `xiaohongshu-mcp-linux-amd64` | `xiaohongshu-login-linux-amd64` |

Grant execute permission to the downloaded files:
```shell
chmod +x xiaohongshu-mcp-darwin-arm64 xiaohongshu-login-darwin-arm64
```

### Step 2: Login (First Time Only)

Run the login tool. It will open a browser window with a QR code. Scan it with your Xiaohongshu mobile app.

```shell
./xiaohongshu-login-darwin-arm64
```

> **Important**: Do not log into the same Xiaohongshu account on any other web browser, as this will invalidate the server's session.

### Step 3: Start the MCP Server

Run the MCP server in a separate terminal window. It will run in the background.

```shell
# Run in headless mode (recommended)
./xiaohongshu-mcp-darwin-arm64

# Or, run with a visible browser for debugging
./xiaohongshu-mcp-darwin-arm64 -headless=false
```

The server will be available at `http://localhost:18060`.

## 2. Using the Skill

This skill includes a Python client (`scripts/xhs_client.py`) to interact with the local server. You can use it directly from the shell.

### Available Commands

| Command | Description | Example |
| --- | --- | --- |
| `status` | Check login status | `python scripts/xhs_client.py status` |
| `qrcode` | Get login QR code (Base64) | `python scripts/xhs_client.py qrcode` |
| `logout` | Delete cookies and reset login | `python scripts/xhs_client.py logout` |
| `search <keyword>` | Search for notes | `python scripts/xhs_client.py search "咖啡"` |
| `detail <id> <token>` | Get note details | `python scripts/xhs_client.py detail "note_id" "xsec_token"` |
| `feeds` | Get recommended feed | `python scripts/xhs_client.py feeds` |
| `publish <title> <content> <images>` | Publish a note with images | `python scripts/xhs_client.py publish "Title" "Content" "/path/to/image.jpg"` |
| `publish_video <title> <content> <video>` | Publish a note with video | `python scripts/xhs_client.py publish_video "Title" "Content" "/path/to/video.mp4"` |
| `comment <feed_id> <token> <content>` | Post a comment to a note | `python scripts/xhs_client.py comment "feed_id" "xsec_token" "Comment"` |
| `reply <feed_id> <token> <content>` | Reply to a comment | `python scripts/xhs_client.py reply "feed_id" "token" "Reply" --comment-id "id"` |
| `like <feed_id> <token>` | Like/unlike a note | `python scripts/xhs_client.py like "feed_id" "token"` or `--unlike` |
| `favorite <feed_id> <token>` | Favorite/unfavorite a note | `python scripts/xhs_client.py favorite "feed_id" "token"` or `--unfavorite` |
| `user <user_id> <token>` | Get user profile information | `python scripts/xhs_client.py user "user_id" "xsec_token"` |

### Example Workflow: Market Research

1.  **Check Status**: First, ensure the server is running and you are logged in.
    ```shell
    python ~/clawd/skills/xiaohongshu-mcp/scripts/xhs_client.py status
    ```

2.  **Search for a Keyword**: Find notes related to your research topic. The output will include the `feed_id` and `xsec_token` needed for the next step.
    ```shell
    python ~/clawd/skills/xiaohongshu-mcp/scripts/xhs_client.py search "户外电源"
    ```

3.  **Get Note Details**: Use the `feed_id` and `xsec_token` from the search results to get the full content and comments of a specific note.
    ```shell
    python ~/clawd/skills/xiaohongshu-mcp/scripts/xhs_client.py detail "64f1a2b3c4d5e6f7a8b9c0d1" "security_token_here"
    ```

4.  **Analyze**: Review the note's content, comments, and engagement data to gather insights.

## 3. Advanced Features

### Publishing Content

#### Publish with Images
Publish a note with one or more images. Images can be local file paths or HTTP(S) URLs.

```shell
# Single image
python scripts/xhs_client.py publish "My Title" "My content" "/path/to/image.jpg"

# Multiple images (comma-separated)
python scripts/xhs_client.py publish "My Title" "My content" "/path/image1.jpg,/path/image2.jpg"

# With tags
python scripts/xhs_client.py publish "My Title" "My content" "/path/image.jpg" --tags "标签1,标签2"
```

#### Publish with Video
Publish a note with a video. Videos must be local files (absolute paths only).

```shell
python scripts/xhs_client.py publish_video "Video Title" "Video description" "/path/to/video.mp4"

# With tags
python scripts/xhs_client.py publish_video "Video Title" "Video description" "/path/to/video.mp4" --tags "标签1,标签2"
```

### Community Engagement

#### Post Comments
Reply to notes with your own comments. Use the `feed_id` and `xsec_token` from search results or note details.

```shell
python scripts/xhs_client.py comment "feed_id" "xsec_token" "Great content! Love this!"
```

#### User Profiles
View detailed user profile information, including follower counts and content statistics.

```shell
python scripts/xhs_client.py user "user_id" "xsec_token"
```

## 4. Login Management

### Get QR Code
Get a Base64 encoded QR code for scanning with your Xiaohongshu app:

```shell
python scripts/xhs_client.py qrcode
```

### Logout
Reset login status by deleting cookies:

```shell
python scripts/xhs_client.py logout
```

## 5. Interaction Features

### Like/Unlike Notes
```shell
# Like a note
python scripts/xhs_client.py like "feed_id" "xsec_token"

# Unlike a note
python scripts/xhs_client.py like "feed_id" "xsec_token" --unlike
```

### Favorite/Unfavorite Notes
```shell
# Favorite a note
python scripts/xhs_client.py favorite "feed_id" "xsec_token"

# Unfavorite a note
python scripts/xhs_client.py favorite "feed_id" "xsec_token" --unfavorite
```

### Reply to Comments
```shell
# Reply to a specific comment
python scripts/xhs_client.py reply "feed_id" "xsec_token" "Reply content" --comment-id "comment_id"

# Reply to a user's comment
python scripts/xhs_client.py reply "feed_id" "xsec_token" "Reply content" --user-id "user_id"
```

## 6. MCP Tools Mapping

The Python client provides command-line access to all 13 MCP server capabilities:

| MCP Tool | Python Command | Purpose |
| --- | --- | --- |
| `check_login_status` | `status` | Verify login status |
| `get_login_qrcode` | `qrcode` | Get login QR code |
| `delete_cookies` | `logout` | Reset login status |
| `publish_content` | `publish` | Publish image/text notes |
| `publish_with_video` | `publish_video` | Publish video notes |
| `list_feeds` | `feeds` | Get recommended feed |
| `search_feeds` | `search` | Search for notes |
| `get_feed_detail` | `detail` | Get note details |
| `post_comment_to_feed` | `comment` | Post comments |
| `reply_comment_in_feed` | `reply` | Reply to comments |
| `like_feed` | `like` | Like/unlike notes |
| `favorite_feed` | `favorite` | Favorite/unfavorite notes |
| `user_profile` | `user` | Get user profile |

## 7. JSON Output Mode

All commands support `--json` flag to output raw JSON responses for programmatic processing:

```shell
python scripts/xhs_client.py search "coffee" --json
python scripts/xhs_client.py detail "feed_id" "token" --json
python scripts/xhs_client.py user "user_id" "token" --json
python scripts/xhs_client.py like "feed_id" "token" --json
python scripts/xhs_client.py reply "feed_id" "token" "content" --comment-id "id" --json
```

## 8. Complete MCP Coverage

✅ **All 13 MCP server functions are now fully implemented in the Python client:**
- Authentication: login status, QR code, logout
- Publishing: images, video
- Discovery: feeds, search, user profiles
- Interaction: comments, replies, likes, favorites
