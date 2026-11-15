"""Read-only herd questions, grounded in an exported dashboard demo snapshot."""
from datetime import datetime
import json
from pathlib import Path
import re

DATA = Path(__file__).with_name('data') / 'demo-herd.json'


def answer(text, context_tag=None, alert_tag=None):
    """Return (reply, next context tag) for questions, or None for alert feedback.

    Empty context means a cow number was requested. None means no lookup thread.
    There are no model calls, network requests or arbitrary database operations.
    """
    normalized = text.lower().replace('’', "'").strip()
    fields = re.search(r'\b(score|scores|gait|locomotion|estrus|heat|location|where|pasture|last seen)\b', normalized)
    question = ('?' in normalized or re.match(r"^(what|where|how|can you|could you|would you|please|tell me|show me|give me|look up|lookup|find|check|locate)\b", normalized))
    explicit = re.findall(r'\b(?:cow|cattle|tag|number)\s*(?:number\s*)?[#:]?\s*(\d+)\b', normalized)
    shorthand = re.fullmatch(r'(?:cow\s*)?#?(\d+)', normalized)
    clarification = context_tag == '' and shorthand
    short_field_request = fields and context_tag and re.fullmatch(r"(?:(?:and|her|his|its|the|that cow's|what about)\s+)*(?:score|location|gait score|pasture)[?.!]*", normalized)
    if not clarification and not short_field_request and not (question and (fields or explicit or re.search(r'\b(?:cow|cattle|\d+)\b', normalized))):
        return None
    # Never turn a review instruction into a read-only query.
    if re.search(r'\b(?:mark|confirm|record|false alarm|false positive)\b', normalized):
        return None
    tags = list(dict.fromkeys(explicit or re.findall(r'(?<![\w.])#?(\d{1,6})(?![\w./])', normalized)))
    if len(tags) > 1:
        return 'Which cow should I look up first? Send one cow number.', ''
    tag = tags[0] if tags else context_tag or alert_tag
    if not tag:
        return "Which cow do you mean? For example, ask: What's cow 718's score and location?", ''
    try:
        snapshot = json.loads(DATA.read_text(encoding='utf-8'))
        if snapshot.get('mode') != 'demo':
            raise ValueError('Not a demo snapshot')
        animal = next((row for row in snapshot['animals'] if row['tag'] == tag), None)
    except (OSError, ValueError, KeyError, TypeError):
        return "The demo herd data is unavailable. I can't verify that cow's score or location right now.", ''
    if not animal:
        return f"I couldn't find cow {tag} in the demo herd. Try cow 718, 904 or 652.", ''
    score = f"{animal['metric']} score: {animal['metricValue']}."
    if animal['metricValue'] == 'Not assessed':
        score = f"{animal['metric']} score: not assessed."
    if animal['observedAt'] is None:
        location = f"Assigned pasture: {animal['pasture']} ({animal['herd']}). No last-seen location is available; this cow wasn't observed in the demo sweep."
    else:
        observed = datetime.fromisoformat(animal['observedAt'])
        # Preserve the timestamp's offset; do not use the execution host's timezone.
        offset = observed.strftime('%z')
        clock = observed.strftime('%I:%M %p').lstrip('0')
        location = f"Last seen: {animal['pasture']} ({animal['herd']}), {observed.strftime('%b')} {observed.day}, {observed.year} at {clock} UTC{offset[:3]}:{offset[3:]}."
    return f"Cow {tag}\n{score}\n{location}\nDemo observations, not live GPS or a diagnosis.", tag
