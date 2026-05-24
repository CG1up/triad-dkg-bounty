#!/usr/bin/env python3
"""
Reading Queue Worker — no_agent cron script for Cleo.

Processes one link per tick from New Batches/ via Gemma 4 26B on Ollama.
Outputs nothing when idle (silent no_agent cron). Outputs status when work is done.
"""

import hashlib
import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

# ── Config ───────────────────────────────────────────────────────────
BRAINIAC = Path(os.path.expanduser("~/Brainiac"))
MASTER_FILE = BRAINIAC / "Reading List" / "Curated Links.md"
NEW_DIR = BRAINIAC / "Reading List" / "New Batches"
PROCESSED_DIR = BRAINIAC / "Reading List" / "Processed Batches"
OLLAMA_URL = "http://localhost:11434/api/generate"
GEMMA_MODEL = "gemma4:26b"
OLLAMA_TIMEOUT = 180  # seconds — Gemma needs time to load

# ── DKG v10 Config ───────────────────────────────────────────────────
DKG_CONFIG_PATH = Path(__file__).parent / ".dkg-config.json"
DKG_CONTEXT_GRAPH = "triad-research"
DKG_COLLECTION = "reading-queue"
DKG_AGENT = "cleo"
DKG_MODEL = "ollama:gemma4:26b"
DKG_ENABLED = True  # set False to disable DKG writes temporarily

# Load token from config file or env
_dkg_config = {}
if DKG_CONFIG_PATH.exists():
    _dkg_config = json.loads(DKG_CONFIG_PATH.read_text())
DKG_AUTH_TOKEN = _dkg_config.get("auth_token", os.environ.get("DKG_AUTH_TOKEN", ""))
DKG_NODE_URL = _dkg_config.get("dkg_node_url", "http://127.0.0.1:9200")

# ── Original Config ──────────────────────────────────────────────────
VALID_CATEGORIES = [
    "AI/ML Agent Frameworks & Orchestration",
    "AI/ML Research",
    "AI/ML Infrastructure",
    "Editor/Tools",
    "Security",
    "Business/Tech Industry",
    "DevOps/Infrastructure",
    "Education/Academia",
    "Data Engineering",
    "Science/Physics",
    "Crypto/Blockchain",
    "Gaming",
    "Open Source",
    "SEO/Marketing",
    "Internal / Our Projects",
    "Misc",
]

# URL pattern categorization (for when Gemma fails)
URL_CATEGORY_MAP = [
    (re.compile(r'huggingface\.co/papers/'), 'AI/ML Research'),
    (re.compile(r'venturebeat\.com/orchestration/'), 'AI/ML Agent Frameworks & Orchestration'),
    (re.compile(r'venturebeat\.com/infrastructure/'), 'AI/ML Infrastructure'),
    (re.compile(r'venturebeat\.com/data/'), 'Data Engineering'),
    (re.compile(r'venturebeat\.com/security/'), 'Security'),
    (re.compile(r'venturebeat\.com/technology/'), 'Open Source'),
    (re.compile(r'venturebeat\.com/ai/'), 'AI/ML Research'),
    (re.compile(r'techcrunch\.com/'), 'Business/Tech Industry'),
    (re.compile(r'reuters\.com/'), 'Business/Tech Industry'),
    (re.compile(r'bloomberg\.com/'), 'Business/Tech Industry'),
    (re.compile(r'forbes\.com/'), 'Business/Tech Industry'),
    (re.compile(r'wsj\.com/'), 'Business/Tech Industry'),
    (re.compile(r'seekingalpha\.com/'), 'Business/Tech Industry'),
    (re.compile(r'xda-developers\.com/'), 'Editor/Tools'),
    (re.compile(r'godotengine\.org/'), 'Editor/Tools'),
    (re.compile(r'thenewstack\.io/'), 'Editor/Tools'),
    (re.compile(r'github\.com/.*/skills'), 'Editor/Tools'),
    (re.compile(r'nature\.com/'), 'AI/ML Research'),
    (re.compile(r'sciencedaily\.com/'), 'Science/Physics'),
    (re.compile(r'newscientist\.com/'), 'Science/Physics'),
    (re.compile(r'neurosciencenews\.com/'), 'Science/Physics'),
    (re.compile(r'theconversation\.com/'), 'Science/Physics'),
    (re.compile(r'thehackernews\.com/'), 'Security'),
    (re.compile(r'helpnetsecurity\.com/'), 'Security'),
    (re.compile(r'securityweek\.com/'), 'Security'),
    (re.compile(r'cybersecuritynews\.com/'), 'Security'),
    (re.compile(r'theregister\.com/security/'), 'Security'),
    (re.compile(r'searchengineland\.com/'), 'SEO/Marketing'),
    (re.compile(r'kdnuggets\.com/'), 'AI/ML Infrastructure'),
    (re.compile(r'marktechpost\.com/'), 'AI/ML Research'),
    (re.compile(r'infoq\.com/news/'), 'AI/ML Infrastructure'),
    (re.compile(r'towardsdatascience\.com/'), 'AI/ML Infrastructure'),
    (re.compile(r'devblogs\.microsoft\.com/agent'), 'AI/ML Agent Frameworks & Orchestration'),
    (re.compile(r'timesofindia\.indiatimes\.com/'), 'Education/Academia'),
    (re.compile(r'businessinsider\.com/'), 'Education/Academia'),
    (re.compile(r'androidpolice\.com/'), 'AI/ML Agent Frameworks & Orchestration'),
    (re.compile(r'entrepreneur\.com/'), 'Business/Tech Industry'),
    (re.compile(r'bain\.com/'), 'Business/Tech Industry'),
    (re.compile(r'amazon\.com/blogs/'), 'AI/ML Infrastructure'),
    (re.compile(r'developer\.nvidia\.com/'), 'AI/ML Infrastructure'),
    (re.compile(r'decrypt\.co/'), 'Crypto/Blockchain'),
    (re.compile(r'polymarket\.com/'), 'Crypto/Blockchain'),
    (re.compile(r'finbold\.com/'), 'Business/Tech Industry'),
    (re.compile(r'gamesradar\.com/'), 'Gaming'),
    (re.compile(r'9to5linux\.com/'), 'DevOps/Infrastructure'),
]


def is_ollama_ready():
    """Check if Ollama is running and Gemma model is available."""
    try:
        result = subprocess.run(
            ["curl", "-s", "http://localhost:11434/api/tags"],
            capture_output=True, text=True, timeout=10
        )
        if result.returncode != 0:
            return False
        data = json.loads(result.stdout)
        models = [m["name"] for m in data.get("models", [])]
        return GEMMA_MODEL in models
    except (json.JSONDecodeError, subprocess.TimeoutExpired, OSError):
        return False


def call_gemma(url):
    """Send a URL to Gemma 4 26B for categorization."""
    prompt = (
        f"You categorize web links. Give me two things for this URL:\n"
        f"1. Category — choose from: {', '.join(VALID_CATEGORIES)}\n"
        f"2. A one-sentence summary (12 words max)\n\n"
        f"URL: {url}\n\n"
        f"Format your answer like:\n"
        f"Category: <name>\n"
        f"Summary: <1 sentence>"
    )
    payload = json.dumps({
        "model": GEMMA_MODEL,
        "prompt": prompt,
        "stream": False,
        "num_predict": 512,
        "temperature": 0.1,
    })
    try:
        result = subprocess.run(
            ["curl", "-s", "--max-time", str(OLLAMA_TIMEOUT),
             "-d", payload, OLLAMA_URL],
            capture_output=True, text=True, timeout=OLLAMA_TIMEOUT + 10
        )
        if result.returncode != 0:
            return None, f"curl failed: {result.stderr[:100]}"
        data = json.loads(result.stdout)
        response = data.get("response", "").strip()
        if not response:
            return None, "Gemma returned empty response"

        # Parse category and summary
        category = None
        summary = None
        for line in response.split("\n"):
            line = line.strip()
            if line.lower().startswith("category:"):
                cat = line.split(":", 1)[1].strip()
                # Match against valid categories
                for valid in VALID_CATEGORIES:
                    if cat.lower() == valid.lower() or valid.lower().startswith(cat.lower()):
                        category = valid
                        break
                if not category:
                    category = cat  # use as-is, will be normalized
            elif line.lower().startswith("summary:"):
                summary = line.split(":", 1)[1].strip()

        return (category, summary), None
    except json.JSONDecodeError as e:
        return None, f"JSON parse error: {e}"
    except subprocess.TimeoutExpired:
        return None, "Gemma timed out (180s)"
    except Exception as e:
        return None, f"Error: {e}"


def categorize_by_url(url):
    """Fallback: infer category from URL pattern."""
    for pattern, category in URL_CATEGORY_MAP:
        if pattern.search(url):
            return category
    return None


def get_title_from_url(url):
    """Try to get a page title via r.jina.ai."""
    try:
        result = subprocess.run(
            ["curl", "-s", "--max-time", "20",
             f"https://r.jina.ai/{url}"],
            capture_output=True, text=True, timeout=25
        )
        if result.returncode == 0:
            for line in result.stdout.split("\n"):
                if line.startswith("Title:"):
                    title = line.split(":", 1)[1].strip()
                    return title[:80]  # keep it short
    except:
        pass
    return None


def extract_title_from_url(url):
    """Extract a human-readable title from the URL itself."""
    # Try GitHub repo pattern
    gh_match = re.search(r'github\.com/([^/]+/[^/]+)', url)
    if gh_match:
        return gh_match.group(1)
    # YouTube video
    yt_match = re.search(r'youtube\.com/watch\?v=([^&]+)', url)
    if yt_match:
        return f"YouTube Video ({yt_match.group(1)})"
    # Domain-based
    domain_match = re.search(r'https?://([^/]+)', url)
    if domain_match:
        domain = domain_match.group(1).replace("www.", "")
        return domain
    return url[:60]


def load_existing_urls():
    """Load all URLs already in the master file for dedup."""
    if not MASTER_FILE.exists():
        return set()
    urls = set()
    with open(MASTER_FILE) as f:
        for line in f:
            m = re.search(r'\]\(([^)]+)\)', line)
            if m:
                urls.add(m.group(1))
    return urls


def extract_first_link(text):
    """Extract the first URL from text (one per line format)."""
    for line in text.split("\n"):
        line = line.strip()
        if not line or line.startswith("#") or line.startswith("-"):
            continue
        # Find URL in the line
        m = re.search(r'https?://[^\s\)]+', line)
        if m:
            url = m.group(0).rstrip(".,)]")
            return url, line
    return None, None


def append_to_master(category, title, url, summary):
    """Append an entry under the correct category section in Curated Links.md."""
    if not MASTER_FILE.exists():
        print("ERROR: Master file not found", file=sys.stderr)
        return False

    entry = f"- [ ] [{title}]({url}) — {summary}"

    with open(MASTER_FILE) as f:
        content = f.read()

    # Find the right category section
    section_header = f"## {category}"
    if section_header not in content:
        # Add new category before Misc or at the end
        insert_before = "## Misc" if "## Misc" in content else None
        if insert_before:
            content = content.replace(insert_before, f"{section_header}\n\n{entry}\n\n{insert_before}")
        else:
            content += f"\n{section_header}\n\n{entry}\n"
    else:
        # Find the section and add at the end of it
        sections = re.split(r'(?=^## )', content, flags=re.MULTILINE)
        new_sections = []
        inserted = False
        for section in sections:
            if section.startswith(f"## {category}") and not inserted:
                # Add before the next section header
                lines = section.split("\n")
                # Find insertion point — after the header
                insert_point = 2 if len(lines) > 1 and lines[1].strip() == "" else 1
                lines.insert(insert_point + 1, entry)
                new_sections.append("\n".join(lines))
                inserted = True
            else:
                new_sections.append(section)
        content = "".join(new_sections)

    with open(MASTER_FILE, "w") as f:
        f.write(content)
    return True


def remove_link_from_batch(batch_path, url, line_content):
    """Remove the processed link from the batch file."""
    with open(batch_path) as f:
        lines = f.readlines()

    new_lines = [l for l in lines if url not in l and line_content.strip() not in l.strip()]

    # If all lines are empty/whitespace, move to processed
    remaining = [l.strip() for l in new_lines if l.strip() and not l.strip().startswith("#")]
    if not remaining:
        batch_path.rename(PROCESSED_DIR / batch_path.name)
        return "empty → moved to processed"
    else:
        with open(batch_path, "w") as f:
            f.writelines(new_lines)
        return "removed"


def update_header_total():
    """Update the total count in the master file header."""
    with open(MASTER_FILE) as f:
        content = f.read()

    # Count entries with checkboxes
    count = len(re.findall(r'^- \[[ x~]\] ', content, re.MULTILINE))
    # Update the total line
    content = re.sub(
        r'\*\*Total: \d+ links\*\*',
        f"**Total: {count} links**",
        content
    )
    with open(MASTER_FILE, "w") as f:
        f.write(content)
    return count


def dkg_publish(category, title, url, summary):
    """Write a Knowledge Asset to DKG Working Memory.

    Uses `dkg workspace write` with an N-Quads temp file to stage triples
    in the triad-research context graph. This is the free ($0) Working Memory layer.
    """
    if not DKG_ENABLED:
        return None, "DKG writes disabled"
    if not DKG_AUTH_TOKEN:
        return None, "No DKG auth token configured"

    timestamp = datetime.now(timezone.utc).isoformat()
    asset_id = hashlib.sha256(url.encode()).hexdigest()[:16]
    ual = f"did:dkg:working:{asset_id}"

    safe_title = (title or url[:60]).replace('"', '\\"')
    safe_summary = summary.replace('"', '\\"')

    # Build N-Quads
    nquads = f"""<{ual}> <http://www.w3.org/1999/02/22-rdf-syntax-ns#type> <http://triad/ns/KnowledgeAsset> .
<{ual}> <http://triad/ns/collection> "{DKG_COLLECTION}" .
<{ual}> <http://triad/ns/title> "{safe_title}" .
<{ual}> <http://triad/ns/url> "{url}" .
<{ual}> <http://triad/ns/summary> "{safe_summary}" .
<{ual}> <http://triad/ns/category> "{category}" .
<{ual}> <http://triad/ns/status> "draft" .
<{ual}> <http://triad/ns/provenanceAgent> "{DKG_AGENT}" .
<{ual}> <http://triad/ns/provenanceModel> "{DKG_MODEL}" .
<{ual}> <http://triad/ns/provenanceTimestamp> "{timestamp}" .
"""

    try:
        import tempfile
        with tempfile.NamedTemporaryFile(mode='w', suffix='.nq', delete=False) as f:
            f.write(nquads)
            tmp_path = f.name

        result = subprocess.run(
            ["dkg", "workspace", "write", DKG_CONTEXT_GRAPH, "-f", tmp_path],
            capture_output=True, text=True, timeout=15,
            env={**os.environ, "DKG_AUTH_TOKEN": DKG_AUTH_TOKEN}
        )
        os.unlink(tmp_path)

        if result.returncode == 0:
            name_match = re.search(r'Assertion name:\s+(\S+)', result.stdout)
            assertion_name = name_match.group(1) if name_match else "unknown"
            return {"ual": ual, "assertion": assertion_name}, None
        else:
            return None, f"dkg exit {result.returncode}: {result.stderr[:120]}"
    except subprocess.TimeoutExpired:
        return None, "DKG write timed out (15s)"
    except FileNotFoundError:
        return None, "DKG CLI not found in PATH"
    except Exception as e:
        return None, f"DKG error: {e}"


def main():
    # Check if Ollama is running
    if not is_ollama_ready():
        print("⚠️  Ollama/Gemma 4 26B not available — skipping tick")
        return

    # Ensure directories exist
    NEW_DIR.mkdir(parents=True, exist_ok=True)
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

    # Find first batch file (alphabetical, .md files only)
    batch_files = sorted(NEW_DIR.glob("*.md"))
    if not batch_files:
        return  # silent exit = no message

    batch = batch_files[0]

    # Read batch file
    text = batch.read_text().strip()
    if not text:
        batch.rename(PROCESSED_DIR / batch.name)
        return  # silent

    # Extract first link
    url, line_content = extract_first_link(text)
    if not url:
        # No URLs left — move to processed
        batch.rename(PROCESSED_DIR / batch.name)
        return

    # Dedup check
    existing = load_existing_urls()
    if url in existing:
        remove_link_from_batch(batch, url, line_content or url)
        print(f"⏭️  Duplicate — removed: {url[:60]}")
        return

    # Short URLs or clearly incomplete URLs get skipped
    if len(url) < 15:
        remove_link_from_batch(batch, url, line_content or url)
        return

    print(f"📖 Processing: {url[:80]}...")

    # Try Gemma first
    result, error = call_gemma(url)

    if result:
        category, summary = result
        if not category:
            category = categorize_by_url(url) or "Misc"
        if not summary:
            summary = "Interesting link."
    else:
        # Fallback: infer from URL
        category = categorize_by_url(url) or "Misc"
        summary = f"Auto-categorized by domain."
        print(f"  ⚠️  Gemma error: {error}, falling back to URL pattern")

    # Get title
    title = get_title_from_url(url)
    if not title:
        title = extract_title_from_url(url)

    # Append to master file
    if append_to_master(category, title, url, summary):
        count = update_header_total()
        remove_link_from_batch(batch, url, line_content or url)
        print(f"✅ [{category}] {title}")
        print(f"   Total: {count} links in master")

        # ── DKG Working Memory write ──
        dkg_result, dkg_error = dkg_publish(category, title, url, summary)
        if dkg_result:
            print(f"   🔗 DKG: {dkg_result['ual']}")
        elif dkg_error:
            print(f"   ⚠️  DKG skipped: {dkg_error}")
    else:
        print(f"❌ Failed to write: {url[:60]}")


if __name__ == "__main__":
    main()
