#!/bin/bash

#=============================================================================
# FastAPI 文件代理服务器启动脚本
# 支持系统：Debian/Ubuntu
# 用途：自动安装系统依赖、创建虚拟环境、安装 Python 包、启动服务器
#=============================================================================

set -e  # 遇到错误立即退出

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 项目配置
PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
VENV_DIR="$PROJECT_DIR/venv"
PORT=7889  # FastAPI 默认端口
WORKER_COUNT=$(nproc)  # 自动检测 CPU 核数

# 性能优化配置
# 根据系统内存自动调整 worker 数量
# 检测操作系统类型以使用正确的内存检测命令
if command -v free >/dev/null 2>&1; then
    # Linux 系统使用 free 命令
    TOTAL_MEM=$(free -m | awk '/^Mem:/{print $2}')
elif command -v sysctl >/dev/null 2>&1; then
    # macOS/BSD 系统使用 sysctl
    TOTAL_MEM=$(sysctl -n hw.memsize 2>/dev/null | awk '{print int($1/1024/1024)}')
else
    # 无法检测内存，使用保守默认值
    TOTAL_MEM=4096
    echo -e "${YELLOW}⚠️  无法检测系统内存，使用默认值: ${TOTAL_MEM}MB${NC}"
fi

if [ "$TOTAL_MEM" -lt 4096 ]; then
    # 小于 4GB 内存，使用较少的 worker
    WORKER_COUNT=$(( $(nproc) > 2 ? 2 : $(nproc) ))
elif [ "$TOTAL_MEM" -lt 8192 ]; then
    # 4-8GB 内存，使用 CPU 核数
    WORKER_COUNT=$(nproc)
else
    # 大于 8GB 内存，使用 CPU 核数 * 2 + 1（nginx 风格）
    WORKER_COUNT=$(( $(nproc) * 2 + 1 ))
fi

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}  FastAPI 文件代理服务器启动脚本${NC}"
echo -e "${BLUE}========================================${NC}"
echo -e "${GREEN}📁 项目目录：${NC}$PROJECT_DIR"
echo -e "${GREEN}🔢 CPU 核数：${NC}$WORKER_COUNT"
echo -e "${GREEN}🔌 服务端口：${NC}$PORT"
echo ""

#=============================================================================
# 1. 检查操作系统
#=============================================================================
echo -e "${BLUE}[1/7] 检查操作系统...${NC}"

if [ -f /etc/os-release ]; then
    . /etc/os-release
    OS=$ID
    VERSION=$VERSION_ID
    echo -e "${GREEN}✓ 检测到系统：${NC}$OS $VERSION"
    
    if [[ "$OS" != "ubuntu" && "$OS" != "debian" ]]; then
        echo -e "${YELLOW}⚠️  警告：此脚本针对 Ubuntu/Debian 优化，当前系统为 $OS${NC}"
    fi
else
    echo -e "${RED}✗ 无法检测操作系统${NC}"
    exit 1
fi

#=============================================================================
# 2. 检查并安装系统依赖
#=============================================================================
echo -e "${BLUE}[2/7] 检查系统依赖...${NC}"

# 需要的系统包
REQUIRED_PACKAGES=(
    "python3"           # Python 3
    "python3-pip"       # pip 包管理器
    "python3-venv"      # 虚拟环境
    "python3-dev"       # Python 开发头文件（uvloop 编译需要）
    "build-essential"   # 编译工具（uvloop 编译需要）
    "redis-server"      # Redis 服务器（可选，如果本地运行）
    "lsof"              # 端口检查工具
    "curl"              # HTTP 客户端（健康检查）
)

MISSING_PACKAGES=()

for package in "${REQUIRED_PACKAGES[@]}"; do
    if ! dpkg -l | grep -q "^ii  $package "; then
        MISSING_PACKAGES+=("$package")
    fi
done

if [ ${#MISSING_PACKAGES[@]} -gt 0 ]; then
    echo -e "${YELLOW}⚠️  缺少以下系统包：${NC}${MISSING_PACKAGES[*]}"
    echo -e "${BLUE}正在安装系统依赖...${NC}"
    
    
    apt-get update -qq
    apt-get install -y "${MISSING_PACKAGES[@]}"
    echo -e "${GREEN}✓ 系统依赖安装完成${NC}"
else
    echo -e "${GREEN}✓ 所有系统依赖已安装${NC}"
fi

#=============================================================================
# 3. 检查 Python 版本
#=============================================================================
echo -e "${BLUE}[3/7] 检查 Python 版本...${NC}"

PYTHON_VERSION=$(python3 --version | awk '{print $2}')
PYTHON_MAJOR=$(echo $PYTHON_VERSION | cut -d. -f1)
PYTHON_MINOR=$(echo $PYTHON_VERSION | cut -d. -f2)

echo -e "${GREEN}✓ Python 版本：${NC}$PYTHON_VERSION"

if [ "$PYTHON_MAJOR" -lt 3 ] || ([ "$PYTHON_MAJOR" -eq 3 ] && [ "$PYTHON_MINOR" -lt 8 ]); then
    echo -e "${RED}✗ 需要 Python 3.8 或更高版本${NC}"
    exit 1
fi

#=============================================================================
# 4. 创建虚拟环境
#=============================================================================
echo -e "${BLUE}[4/7] 创建/激活虚拟环境...${NC}"

if [ ! -d "$VENV_DIR" ]; then
    echo -e "${YELLOW}🛠️  创建虚拟环境...${NC}"
    python3 -m venv "$VENV_DIR"
    echo -e "${GREEN}✓ 虚拟环境创建完成${NC}"
else
    echo -e "${GREEN}✓ 虚拟环境已存在${NC}"
fi

# 激活虚拟环境
source "$VENV_DIR/bin/activate"

#=============================================================================
# 5. 安装 Python 依赖
#=============================================================================
echo -e "${BLUE}[5/7] 安装 Python 依赖...${NC}"

# 升级 pip
echo -e "${YELLOW}📦 升级 pip...${NC}"
pip install --upgrade pip setuptools wheel -q

# 检查 requirements.txt 是否存在
if [ ! -f "$PROJECT_DIR/requirements.txt" ]; then
    echo -e "${RED}✗ 找不到 requirements.txt 文件${NC}"
    exit 1
fi

# 安装依赖
echo -e "${YELLOW}📦 安装项目依赖...${NC}"
pip install -r "$PROJECT_DIR/requirements.txt" -q

echo -e "${GREEN}✓ Python 依赖安装完成${NC}"

# 验证关键包
echo -e "${BLUE}验证关键包安装...${NC}"
CRITICAL_PACKAGES=("fastapi" "uvicorn" "httpx" "redis" "uvloop")
for pkg in "${CRITICAL_PACKAGES[@]}"; do
    if python -c "import $pkg" 2>/dev/null; then
        VERSION=$(pip show "$pkg" 2>/dev/null | grep "Version:" | awk '{print $2}')
        echo -e "${GREEN}  ✓ $pkg${NC} ($VERSION)"
    else
        echo -e "${RED}  ✗ $pkg 未安装${NC}"
        exit 1
    fi
done

#=============================================================================
# 6. 检查并处理端口占用
#=============================================================================
echo -e "${BLUE}[6/7] 检查端口 $PORT...${NC}"

if lsof -Pi :$PORT -sTCP:LISTEN -t >/dev/null 2>&1; then
    PIDS=$(lsof -t -i:$PORT)
    echo -e "${YELLOW}⚠️  端口 $PORT 被以下进程占用：${NC}"
    lsof -i :$PORT
    
    read -p "是否杀死这些进程? (y/N): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        echo -e "${YELLOW}🛑 正在杀死进程...${NC}"
        kill -9 $PIDS
        sleep 1
        echo -e "${GREEN}✓ 进程已杀死${NC}"
    else
        echo -e "${RED}✗ 请手动处理端口占用或更改端口${NC}"
        exit 1
    fi
else
    echo -e "${GREEN}✓ 端口 $PORT 可用${NC}"
fi

#=============================================================================
# 7. 启动 FastAPI 服务器
#=============================================================================
echo -e "${BLUE}[7/7] 启动 FastAPI 服务器...${NC}"
echo ""

# 创建日志目录（如果不存在）
mkdir -p "$PROJECT_DIR/logs"
echo -e "${GREEN}✓ 日志目录已创建：${NC}$PROJECT_DIR/logs"
echo ""

# 性能优化环境变量
export PYTHONUNBUFFERED=1  # 禁用 Python 输出缓冲
export PYTHONUTF8=1  # 强制 UTF-8 编码
export GUNICORN_WORKERS="$WORKER_COUNT"  # 传递 worker 数量给 gunicorn 配置

# 检查是否使用生产环境配置
if [ -f "$PROJECT_DIR/gunicorn_fastapi.conf.py" ]; then
    echo -e "${GREEN}🚀 使用 gunicorn 启动生产服务器...${NC}"
    echo -e "${BLUE}配置：${NC}"
    echo -e "  • Workers: $WORKER_COUNT (自动优化)"
    echo -e "  • 端口: $PORT"
    echo -e "  • Worker 类: uvicorn.workers.UvicornWorker"
    echo -e "  • 日志目录: $PROJECT_DIR/logs"
    echo -e "  • 系统内存: ${TOTAL_MEM}MB"
    echo -e "  • 性能优化: uvloop + HTTP/2 + 流式传输"
    echo -e "  • 网络支持: IPv4 + IPv6 (双栈)"
    echo ""
    
    # 使用 gunicorn 启动（worker 数量从环境变量读取）
    # 注意: 绑定地址使用 [::] 支持IPv4和IPv6双栈
    exec gunicorn -c "$PROJECT_DIR/gunicorn_fastapi.conf.py" \
        --bind "[::]:$PORT" \
        app:app
else
    echo -e "${YELLOW}⚠️  未找到 gunicorn 配置文件，使用开发模式启动...${NC}"
    echo -e "${BLUE}配置：${NC}"
    echo -e "  • Workers: 1"
    echo -e "  • 端口: $PORT"
    echo -e "  • 热重载: 启用"
    echo -e "  • 日志级别: info"
    echo -e "  • 性能优化: uvloop + HTTP/2"
    echo -e "  • 网络支持: IPv4 + IPv6 (双栈)"
    echo ""
    
    # 开发模式使用 uvicorn 直接启动
    # 注意: 使用 :: 支持IPv4和IPv6双栈
    exec uvicorn app:app \
        --host :: \
        --port "$PORT" \
        --reload \
        --log-level info \
        --loop uvloop \
        --http httptools \
        --access-log \
        --use-colors
fi

#=============================================================================
# 注意：
# - 如果需要修改端口，请编辑本脚本顶部的 PORT 变量
# - 如果需要修改 worker 数量，请编辑 WORKER_COUNT 变量或修改 gunicorn_fastapi.conf.py
# - 生产环境建议使用 systemd 服务而不是直接运行此脚本
# - Redis 连接配置请参考 models/config.py
#=============================================================================