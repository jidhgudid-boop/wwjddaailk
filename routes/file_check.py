"""
文件存在性检查路由
API interface for checking if video files exist (single or batch)
"""
import os
import logging
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field

from fastapi import APIRouter, Header, Request
from fastapi.responses import JSONResponse

from models.config import config
from services.http_client import http_client_service
from utils.helpers import get_client_ip, validate_api_key

logger = logging.getLogger(__name__)

router = APIRouter()


class FileCheckRequest(BaseModel):
    """单个文件检查请求"""
    path: str = Field(..., description="文件路径")


class BatchFileCheckRequest(BaseModel):
    """批量文件检查请求"""
    paths: List[str] = Field(..., description="文件路径列表", min_length=1, max_length=100)


class FileCheckResponse(BaseModel):
    """文件检查响应"""
    path: str
    exists: bool
    error: Optional[str] = None


class BatchFileCheckResponse(BaseModel):
    """批量文件检查响应"""
    results: List[FileCheckResponse]
    total: int
    exists_count: int
    not_found_count: int
    error_count: int


async def check_file_exists_filesystem(file_path: str) -> Dict[str, Any]:
    """
    检查文件系统中的文件是否存在
    
    Args:
        file_path: 文件路径
        
    Returns:
        包含exists和error字段的字典
    """
    try:
        # 构建完整的文件路径
        full_path = os.path.join(config.BACKEND_FILESYSTEM_ROOT, file_path.lstrip('/'))
        
        # 安全检查：防止路径遍历攻击
        resolved_path = os.path.abspath(full_path)
        root_path = os.path.abspath(config.BACKEND_FILESYSTEM_ROOT)
        
        if not resolved_path.startswith(root_path):
            logger.warning(f"路径遍历尝试被阻止: {file_path}")
            return {
                "exists": False,
                "error": "Invalid path"
            }
        
        # 检查文件是否存在且是文件（不是目录）
        exists = os.path.isfile(resolved_path)
        
        return {
            "exists": exists,
            "error": None
        }
    except Exception as e:
        logger.error(f"检查文件系统文件失败: {file_path} - {str(e)}")
        return {
            "exists": False,
            "error": "Internal error"
        }


async def check_file_exists_http(file_path: str) -> Dict[str, Any]:
    """
    检查HTTP后端的文件是否存在（使用HEAD请求）
    
    Args:
        file_path: 文件路径
        
    Returns:
        包含exists和error字段的字典
    """
    try:
        # 构建远程URL
        backend_scheme = "https" if config.BACKEND_USE_HTTPS else "http"
        remote_url = f"{backend_scheme}://{config.BACKEND_HOST}:{config.BACKEND_PORT}/{file_path.lstrip('/')}"
        
        headers = {
            "Host": config.PROXY_HOST_HEADER,
            "User-Agent": "FileProxy-CheckService/1.0"
        }
        
        # 获取HTTP客户端
        client = await http_client_service.get_client()
        
        # 使用HEAD请求检查文件是否存在
        response = await client.head(
            remote_url,
            headers=headers,
            follow_redirects=True,
            timeout=10.0
        )
        
        # 2xx 和 3xx 状态码表示文件存在
        exists = 200 <= response.status_code < 400
        
        if not exists and response.status_code != 404:
            # 如果不是404，记录详细错误
            error_msg = f"HTTP {response.status_code}"
            logger.warning(f"检查HTTP文件异常状态: {remote_url} - {error_msg}")
            return {
                "exists": False,
                "error": error_msg
            }
        
        return {
            "exists": exists,
            "error": None
        }
    except Exception as e:
        logger.error(f"检查HTTP文件失败: {file_path} - {str(e)}")
        return {
            "exists": False,
            "error": "Internal error"
        }


@router.post("/api/file/check")
async def check_file_existence(
    request_data: FileCheckRequest,
    request: Request,
    authorization: Optional[str] = Header(None)
):
    """
    检查单个文件是否存在
    
    需要 API Key 认证
    
    请求体:
    {
        "path": "/path/to/file.mp4"
    }
    
    响应:
    {
        "path": "/path/to/file.mp4",
        "exists": true,
        "error": null
    }
    """
    client_ip = get_client_ip(request)
    
    # 验证 API Key
    if not validate_api_key(authorization, config.API_KEY):
        logger.warning(f"文件检查失败: 无效或缺失的API密钥，来自 {client_ip}")
        return JSONResponse(
            content={"error": "Invalid or missing API key"},
            status_code=403
        )
    
    file_path = request_data.path
    
    # 根据后端模式检查文件
    if config.BACKEND_MODE == "filesystem":
        result = await check_file_exists_filesystem(file_path)
    elif config.BACKEND_MODE == "http":
        result = await check_file_exists_http(file_path)
    else:
        logger.error(f"不支持的后端模式: {config.BACKEND_MODE}")
        return JSONResponse(
            content={"error": f"Unsupported backend mode: {config.BACKEND_MODE}"},
            status_code=500
        )
    
    response_data = {
        "path": file_path,
        "exists": result["exists"],
        "error": result["error"]
    }
    
    logger.info(f"文件检查: path={file_path}, exists={result['exists']}, client_ip={client_ip}")
    
    return JSONResponse(content=response_data, status_code=200)


@router.post("/api/file/check/batch")
async def check_files_existence_batch(
    request_data: BatchFileCheckRequest,
    request: Request,
    authorization: Optional[str] = Header(None)
):
    """
    批量检查文件是否存在
    
    需要 API Key 认证
    
    请求体:
    {
        "paths": [
            "/path/to/file1.mp4",
            "/path/to/file2.mp4",
            "/path/to/file3.mp4"
        ]
    }
    
    响应:
    {
        "results": [
            {
                "path": "/path/to/file1.mp4",
                "exists": true,
                "error": null
            },
            {
                "path": "/path/to/file2.mp4",
                "exists": false,
                "error": null
            },
            {
                "path": "/path/to/file3.mp4",
                "exists": true,
                "error": null
            }
        ],
        "total": 3,
        "exists_count": 2,
        "not_found_count": 1,
        "error_count": 0
    }
    """
    client_ip = get_client_ip(request)
    
    # 验证 API Key
    if not validate_api_key(authorization, config.API_KEY):
        logger.warning(f"批量文件检查失败: 无效或缺失的API密钥，来自 {client_ip}")
        return JSONResponse(
            content={"error": "Invalid or missing API key"},
            status_code=403
        )
    
    paths = request_data.paths
    results = []
    exists_count = 0
    not_found_count = 0
    error_count = 0
    
    # 根据后端模式检查文件
    for file_path in paths:
        if config.BACKEND_MODE == "filesystem":
            result = await check_file_exists_filesystem(file_path)
        elif config.BACKEND_MODE == "http":
            result = await check_file_exists_http(file_path)
        else:
            result = {
                "exists": False,
                "error": f"Unsupported backend mode: {config.BACKEND_MODE}"
            }
        
        results.append({
            "path": file_path,
            "exists": result["exists"],
            "error": result["error"]
        })
        
        # Count results: exists_count + not_found_count + error_count = total
        if result["error"] is not None:
            error_count += 1
        elif result["exists"]:
            exists_count += 1
        else:
            not_found_count += 1
    
    response_data = {
        "results": results,
        "total": len(paths),
        "exists_count": exists_count,
        "not_found_count": not_found_count,
        "error_count": error_count
    }
    
    logger.info(f"批量文件检查: 总数={len(paths)}, 存在={exists_count}, 未找到={not_found_count}, 错误={error_count}, client_ip={client_ip}")
    
    return JSONResponse(content=response_data, status_code=200)
