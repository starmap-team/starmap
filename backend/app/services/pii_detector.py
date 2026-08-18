"""PII detector — 检测导入文本中的个人信息 (Task 3.5, Fix H2).

检测项:
- 中国大陆手机号 (+86 11位, 13/14/15/16/17/18/19 开头)
- 邮箱地址 (RFC 5322 简化版)
- 身份证号 (18 位)
"""
from __future__ import annotations

import re

# 中国大陆手机号 (+86 可选前缀)
PHONE_PATTERN = re.compile(r'(?:\+86[-\s]?)?1[3-9]\d{9}')

# 邮箱 (RFC 5322 简化版)
EMAIL_PATTERN = re.compile(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}')

# 身份证 (18 位，含校验位 X/x)
IDCARD_PATTERN = re.compile(r'[1-9]\d{5}(?:18|19|20)\d{2}(?:0[1-9]|1[0-2])(?:0[1-9]|[12]\d|3[01])\d{3}[\dXx]')

def detect_pii(text: str) -> list[str]:
 """返回检测到的 PII 类型列表。

 Examples:
 >>> detect_pii("联系我 13800138000 或 test@example.com")
 ['phone', 'email']
 """
 if not text:
 return []
 types = []
 if PHONE_PATTERN.search(text):
 types.append("phone")
 if EMAIL_PATTERN.search(text):
 types.append("email")
 if IDCARD_PATTERN.search(text):
 types.append("idcard")
 return types
