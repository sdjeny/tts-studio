import re

text = "[rate=-30%]开始慢说[/rate][pause=300][emphasis=strong]重点强调[/emphasis][pause=200][rate=+40%]快速结束[/rate]"

# 新正则
pattern = r'\[(\w+)=([^\]]+)\](?:\s*(.*?)\[/\1\]|(?=\[|$))'

print("原始文本:")
print(text)
print(f"\n长度: {len(text)}")

print("\n匹配结果:")
for i, match in enumerate(re.finditer(pattern, text)):
    print(f"  [{i}] start={match.start()}, end={match.end()}")
    print(f"      tag={match.group(1)}, value={match.group(2)}, content='{match.group(3)}'")
    print(f"      匹配文本: '{text[match.start():match.end()]}'")
