#!/bin/bash
# StarMap 后端编码修复脚本
# 将所有 .py 文件统一转换为 UTF-8 编码

set -e

echo "🔧 StarMap 后端编码修复"
echo "========================"

# 检查 iconv 是否可用
if ! command -v iconv &> /dev/null; then
    echo "❌ 错误: iconv 命令不可用"
    echo "   请安装 iconv:"
    echo "   - Ubuntu/Debian: sudo apt-get install libc6-dev"
    echo "   - macOS: 已内置"
    echo "   - Windows: 使用 Git Bash 或 WSL"
    exit 1
fi

# 统计变量
total_files=0
fixed_files=0
skipped_files=0
error_files=0

# 修复单个文件的函数
fix_file() {
    local file="$1"
    local basename=$(basename "$file")
    
    # 跳过 __pycache__ 目录
    if [[ "$file" == *"__pycache__"* ]]; then
        return
    fi
    
    total_files=$((total_files + 1))
    
    # 检查文件编码
    local encoding
    if command -v file &> /dev/null; then
        encoding=$(file -b --mime-encoding "$file" 2>/dev/null || echo "unknown")
    else
        encoding="unknown"
    fi
    
    echo "📝 处理: $file"
    echo "   当前编码: $encoding"
    
    # 尝试转换为 UTF-8
    local temp_file="${file}.tmp"
    
    if iconv -f GBK -t UTF-8 "$file" > "$temp_file" 2>/dev/null; then
        mv "$temp_file" "$file"
        echo "   ✅ 已从 GBK 转换为 UTF-8"
        fixed_files=$((fixed_files + 1))
    elif iconv -f GB18030 -t UTF-8 "$file" > "$temp_file" 2>/dev/null; then
        mv "$temp_file" "$file"
        echo "   ✅ 已从 GB18030 转换为 UTF-8"
        fixed_files=$((fixed_files + 1))
    elif iconv -f UTF-8 -t UTF-8 "$file" > "$temp_file" 2>/dev/null; then
        # 文件已经是 UTF-8
        rm -f "$temp_file"
        echo "   ✅ 已经是 UTF-8 编码"
        skipped_files=$((skipped_files + 1))
    else
        rm -f "$temp_file"
        echo "   ⚠️  无法确定编码，跳过"
        error_files=$((error_files + 1))
    fi
}

# 遍历后端目录
echo ""
echo "📂 扫描目录: backend/app/api/v1/"

for file in backend/app/api/v1/*.py; do
    if [ -f "$file" ]; then
        fix_file "$file"
    fi
done

# 也检查其他可能的后端目录
echo ""
echo "📂 扫描目录: backend/app/"

find backend/app -name "*.py" -type f | while read -r file; do
    # 跳过已处理的文件和 __pycache__
    if [[ "$file" != *"__pycache__"* ]]; then
        # 只处理尚未处理的文件
        if [[ "$file" != backend/app/api/v1/* ]]; then
            fix_file "$file"
        fi
    fi
done

# 输出统计
echo ""
echo "========================"
echo "📊 修复统计:"
echo "   总文件数: $total_files"
echo "   已修复:   $fixed_files"
echo "   已跳过:   $skipped_files"
echo "   错误:     $error_files"
echo ""

if [ $error_files -gt 0 ]; then
    echo "⚠️  有 $error_files 个文件无法处理，请手动检查"
    exit 1
else
    echo "✅ 编码修复完成！"
    exit 0
fi
