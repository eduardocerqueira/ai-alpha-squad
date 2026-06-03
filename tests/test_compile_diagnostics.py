"""Tests for compile log parsing."""

from ai_alpha_squad.compile_diagnostics import format_compile_fix_list, parse_compile_diagnostics


def test_parse_maven_error():
    log = "[ERROR] src/main/java/io/Foo.java:[62,8] cannot find symbol"
    items = parse_compile_diagnostics(log)
    assert len(items) == 1
    assert items[0].file == "Foo.java"
    assert items[0].line == 62
    assert "cannot find symbol" in items[0].message


def test_format_compile_fix_list():
    log = "[ERROR] src/Foo.java:[10,1] bad type"
    text = format_compile_fix_list(log)
    assert "[BLOCKER]" in text
    assert "Foo.java:10" in text


def test_deduplicates_same_error():
    log = "\n".join(
        ["[ERROR] src/Foo.java:[10,1] bad type"] * 3
    )
    assert len(parse_compile_diagnostics(log)) == 1
