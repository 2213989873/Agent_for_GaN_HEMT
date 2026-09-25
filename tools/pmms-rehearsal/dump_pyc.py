# -*- coding: utf-8 -*-
"""从 pyc 中递归提取代码对象的常量与名称（PyInstaller 取证用）"""
import marshal
import sys
import types


def walk(code, depth=0, seen=None):
    if seen is None:
        seen = set()
    if id(code) in seen:
        return
    seen.add(id(code))
    pad = "  " * depth
    print(f"{pad}### CODE {code.co_name} (args={code.co_varnames[:code.co_argcount]})")
    for c in code.co_consts:
        if isinstance(c, types.CodeType):
            walk(c, depth + 1, seen)
        elif isinstance(c, (str, int, float)) and c is not None:
            s = repr(c)
            if len(s) > 300:
                s = s[:300] + "..."
            print(f"{pad}  const: {s}")
    for n in code.co_names:
        print(f"{pad}  name: {n}")


def main(path):
    with open(path, "rb") as f:
        data = f.read()
    # pyc: 16-byte header (3.7+)
    code = marshal.loads(data[16:])
    walk(code)


if __name__ == "__main__":
    main(sys.argv[1])
