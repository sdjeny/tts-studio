import re

text = "前面[pause=500]后面"

# 新正则
pattern = r'\[(\w+)=([^\]]+)\](?:\s*(.*?)(?=\[/\1\]|\[|$))'

print("原始文本:")
print(text)
print(f"\n长度: {len(text)}")

print("\n匹配结果:")
for i, match in enumerate(re.finditer(pattern, text)):
    print(f"  [{i}] start={match.start()}, end={match.end()}")
    print(f"      tag={match.group(1)}, value={match.group(2)}, content='{match.group(3)}'")
    print(f"      匹配文本: '{text[match.start():match.end()]}'")

print("\n未匹配部分:")
last_end = 0
for match in re.finditer(pattern, text):
    if match.start() > last_end:
        print(f"  '{text[last_end:match.start()]}'")
    last_end = match.end()
if last_end < len(text):
    print(f"  '{text[last_end:]}'")
