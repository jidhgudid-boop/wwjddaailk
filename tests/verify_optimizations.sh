#!/bin/bash
# 性能优化验证脚本
# 验证所有优化点是否正确实施

echo "======================================================================"
echo "FastAPI 性能优化验证"
echo "======================================================================"
echo ""

PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$PROJECT_DIR"

PASS_COUNT=0
FAIL_COUNT=0

# 辅助函数
pass_test() {
    echo "✓ PASS: $1"
    ((PASS_COUNT++))
}

fail_test() {
    echo "✗ FAIL: $1"
    ((FAIL_COUNT++))
}

# 测试 1: 检查 stream_proxy.py 是否正确保留 Content-Length
echo "[测试 1] 检查 stream_proxy.py 的 Content-Length 处理"
echo "----------------------------------------------------------------------"

if grep -q '# "content-length" - 保留以确保显示文件总大小' services/stream_proxy.py; then
    pass_test "Content-Length 注释存在，说明已被保留"
else
    fail_test "Content-Length 注释不存在"
fi

# Content-Length 不再需要显式设置，因为它不在 excluded_headers 中
if grep -q '"content-length".*excluded_headers' services/stream_proxy.py || grep -q 'excluded_headers.*"content-length"' services/stream_proxy.py; then
    fail_test "Content-Length 仍在排除列表中"
else
    pass_test "Content-Length 不在排除列表中（会自动包含）"
fi

if grep -q 'proxy_headers\["Accept-Ranges"\] = "bytes"' services/stream_proxy.py; then
    pass_test "Accept-Ranges 头已添加"
else
    fail_test "Accept-Ranges 头未添加"
fi

if grep -q '@router.head.*path:path' routes/proxy.py; then
    pass_test "HEAD 请求支持已添加"
else
    fail_test "HEAD 请求支持未添加"
fi

echo ""

# 测试 2: 检查 app.py 的 CORS 配置
echo "[测试 2] 检查 app.py 的 CORS expose_headers"
echo "----------------------------------------------------------------------"

if grep -q 'expose_headers=\["Content-Length"' app.py; then
    pass_test "CORS expose_headers 包含 Content-Length"
else
    fail_test "CORS expose_headers 未包含 Content-Length"
fi

if grep -q '"Content-Range"' app.py && grep -q '"Accept-Ranges"' app.py; then
    pass_test "CORS expose_headers 包含 Content-Range 和 Accept-Ranges"
else
    fail_test "CORS expose_headers 缺少 Content-Range 或 Accept-Ranges"
fi

echo ""

# 测试 3: 检查 run.sh 的优化
echo "[测试 3] 检查 run.sh 的性能优化"
echo "----------------------------------------------------------------------"

if grep -q 'TOTAL_MEM.*free -m' run.sh; then
    pass_test "run.sh 包含内存检测逻辑"
else
    fail_test "run.sh 缺少内存检测逻辑"
fi

if grep -q 'PYTHONUNBUFFERED=1' run.sh; then
    pass_test "run.sh 设置 PYTHONUNBUFFERED"
else
    fail_test "run.sh 未设置 PYTHONUNBUFFERED"
fi

if grep -q '\-\-loop uvloop' run.sh; then
    pass_test "run.sh 开发模式使用 uvloop"
else
    fail_test "run.sh 开发模式未使用 uvloop"
fi

if grep -q '\-\-http httptools' run.sh; then
    pass_test "run.sh 开发模式使用 httptools"
else
    fail_test "run.sh 开发模式未使用 httptools"
fi

if grep -q 'GUNICORN_WORKERS' run.sh; then
    pass_test "run.sh 通过环境变量传递 worker 数量"
else
    fail_test "run.sh 未通过环境变量传递 worker 数量"
fi

echo ""

# 测试 4: 检查 gunicorn_fastapi.conf.py 的优化
echo "[测试 4] 检查 gunicorn_fastapi.conf.py 的优化"
echo "----------------------------------------------------------------------"

if grep -q 'os.environ.get.*GUNICORN_WORKERS' gunicorn_fastapi.conf.py; then
    pass_test "gunicorn 使用环境变量控制 worker 数量"
else
    fail_test "gunicorn 未使用环境变量控制 worker 数量"
fi

if grep -q 'keepalive = 65' gunicorn_fastapi.conf.py; then
    pass_test "gunicorn keepalive 设置为 65 秒"
else
    fail_test "gunicorn keepalive 未正确设置"
fi

if grep -q 'max_requests = 10000' gunicorn_fastapi.conf.py; then
    pass_test "gunicorn max_requests 设置为 10000"
else
    fail_test "gunicorn max_requests 未正确设置"
fi

if grep -q 'backlog = 2048' gunicorn_fastapi.conf.py; then
    pass_test "gunicorn backlog 设置为 2048"
else
    fail_test "gunicorn backlog 未设置"
fi

echo ""

# 测试 5: 检查文档
echo "[测试 5] 检查文档"
echo "----------------------------------------------------------------------"

if [ -f "docs/PERFORMANCE_OPTIMIZATION_SUMMARY.md" ]; then
    pass_test "性能优化文档存在"
else
    fail_test "性能优化文档不存在"
fi

echo ""

# 测试 6: 检查测试文件
echo "[测试 6] 检查测试文件"
echo "----------------------------------------------------------------------"

if [ -f "tests/test_content_length_streaming.py" ]; then
    pass_test "Content-Length 流式传输测试存在"
else
    fail_test "Content-Length 流式传输测试不存在"
fi

echo ""

# 测试 7: 运行实际功能测试
echo "[测试 7] 运行功能测试"
echo "----------------------------------------------------------------------"

if python tests/test_content_length.py > /tmp/test_output.log 2>&1; then
    pass_test "test_content_length.py 测试通过"
else
    fail_test "test_content_length.py 测试失败"
    echo "查看日志: cat /tmp/test_output.log"
fi

if python tests/test_content_length_streaming.py > /tmp/test_streaming_output.log 2>&1; then
    pass_test "test_content_length_streaming.py 测试通过"
else
    fail_test "test_content_length_streaming.py 测试失败"
    echo "查看日志: cat /tmp/test_streaming_output.log"
fi

if python tests/test_head_request.py > /tmp/test_head_output.log 2>&1; then
    pass_test "test_head_request.py 测试通过（HEAD 请求支持）"
else
    fail_test "test_head_request.py 测试失败"
    echo "查看日志: cat /tmp/test_head_output.log"
fi

echo ""

# 总结
echo "======================================================================"
echo "测试总结"
echo "======================================================================"
echo "通过: $PASS_COUNT"
echo "失败: $FAIL_COUNT"
echo ""

if [ $FAIL_COUNT -eq 0 ]; then
    echo "✓ 所有测试通过！优化已正确实施。"
    exit 0
else
    echo "✗ 有 $FAIL_COUNT 个测试失败，请检查上述输出。"
    exit 1
fi
