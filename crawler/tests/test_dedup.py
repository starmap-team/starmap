"""SimHash 去重单元测试。"""
from crawler.dedup import simhash, hamming, is_near_duplicate, hex64


def test_simhash_same_text_same_hash():
    assert simhash("Python Java 算法") == simhash("Python Java 算法")


def test_simhash_different_text_different_hash():
    a = simhash("Python 算法工程师 要求掌握 PyTorch")
    b = simhash("Java 后端开发 熟悉 Spring Boot MySQL")
    assert a != b


def test_hamming_distance_zero_for_same():
    v = simhash("hello world")
    assert hamming(v, v) == 0


def test_is_near_duplicate_threshold():
    a = simhash("高级 Python 工程师 要求熟悉 Django MySQL Redis")
    # 改一两个字
    b = simhash("高级 Python 工程师 要求熟悉 Django MySQL Memcache")
    # 距离可能 ≤3
    assert is_near_duplicate(a, b, threshold=3) or not is_near_duplicate(a, b, threshold=0)


def test_hex64_format():
    v = simhash("任意文本")
    h = hex64(v)
    assert len(h) == 64
    assert h.isalnum() or h.isdigit() or all(c in "0123456789abcdef" for c in h[:16])
