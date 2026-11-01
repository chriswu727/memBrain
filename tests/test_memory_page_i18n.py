import html.parser
import re
from pathlib import Path

WEB = Path(__file__).parents[1] / "src" / "membrain" / "web"
UNTRANSLATED = {"memBrain", "Claude Code", "Codex", "membrain plugin ui", "<private>…</private>"}


def test_every_interface_sentence_on_the_memory_page_has_a_chinese_translation():
    texts = []

    class Collect(html.parser.HTMLParser):
        def handle_data(self, data):
            text = " ".join(data.split())
            if re.search("[A-Za-z]{2}", text):
                texts.append(text)

        def handle_starttag(self, tag, attrs):
            texts.extend(" ".join(value.split()) for name, value in attrs
                         if name in ("placeholder", "aria-label", "title") and value)

    Collect().feed((WEB / "memory.html").read_text(encoding="utf-8"))
    dictionary = (WEB / "i18n.js").read_text(encoding="utf-8")
    missing = [text for text in texts if text not in UNTRANSLATED and f'"{text}"' not in dictionary]
    assert missing == []
    assert '<script src="/static/i18n.js" defer></script>' in (WEB / "memory.html").read_text(encoding="utf-8")


def test_text_people_wrote_is_marked_so_it_is_never_translated():
    script = (WEB / "memory.js").read_text(encoding="utf-8")
    assert 'element("p", message.text)' not in script and 'element("p", parsed.sentence)' not in script
    assert script.count('"user-text"') >= 4
