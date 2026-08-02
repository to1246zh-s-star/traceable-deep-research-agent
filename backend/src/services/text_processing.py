"""Utility helpers for normalizing agent generated text."""

from __future__ import annotations


TOOL_CALL_PREFIX = "[TOOL_CALL:"


def strip_tool_calls(text: str) -> str:
    """移除文本中的完整 TOOL_CALL 标记。

    工具参数可能包含 JSON 数组，例如：
    [TOOL_CALL:note:{"tags":["a","b"],"content":"..."}]

    因此不能使用简单的 ``[^]]+`` 正则表达式，而需要正确处理：
    - 嵌套的方括号
    - JSON 字符串
    - 字符串中的转义字符
    """

    if not text:
        return text

    output: list[str] = []
    cursor = 0
    text_length = len(text)

    while cursor < text_length:
        start = text.find(TOOL_CALL_PREFIX, cursor)

        if start == -1:
            output.append(text[cursor:])
            break

        # 保留工具调用之前的正常文本。
        output.append(text[cursor:start])

        index = start
        bracket_depth = 0
        in_string = False
        escaped = False
        call_end: int | None = None

        while index < text_length:
            char = text[index]

            if in_string:
                if escaped:
                    escaped = False
                elif char == "\\":
                    escaped = True
                elif char == '"':
                    in_string = False
            else:
                if char == '"':
                    in_string = True
                elif char == "[":
                    bracket_depth += 1
                elif char == "]":
                    bracket_depth -= 1

                    if bracket_depth == 0:
                        call_end = index + 1
                        break

            index += 1

        if call_end is None:
            # 工具调用不完整时，丢弃从 TOOL_CALL 开始的残缺内容。
            break

        cursor = call_end

    return "".join(output)
