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


def test_the_brain_showcase_is_translated():
    dictionary = (WEB / "i18n.js").read_text(encoding="utf-8")
    for text, chinese in [("Showcase", "展示模式"), ("Fictional demo data", "虚构的演示数据"), ("Close", "关闭"),
                          ("Loading the memory map…", "正在加载记忆图…"),
                          ("No memories yet. Talk with your agent, then come back.", "还没有记忆")]:
        assert re.search(rf'"{re.escape(text)}": "{re.escape(chinese)}', dictionary), text
    # The caption the showcase builds ("37 memories · 22 links") matches its Chinese pattern.
    script = (WEB / "showcase.js").read_text(encoding="utf-8")
    assert '"memory" : "memories"} · ${links.length} ${links.length === 1 ? "link" : "links"}' in script
    pattern = re.search(r"\[/(\^\(\\d\+\) memor\(\?:y\|ies\).*?)/, ", dictionary).group(1)
    for sample in ("37 memories · 22 links", "1 memory · 1 link", "1 memory · 0 links"):
        assert re.match(pattern, sample), sample
