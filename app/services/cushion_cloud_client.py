# ===========================================
# 点点甜睡智能坐垫云服务 API 客户端
# ===========================================
"""
封装点点甜睡厂家云服务的所有API调用

主要功能:
- 登录认证和Token管理
- 设备信息查询
- 睡眠数据获取
- 报告数据获取
- 数据对比分析
"""

import json
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

import httpx
from loguru import logger
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
)

from app.config import settings


class CushionCloudError(Exception):
    """
    点点甜睡云服务异常
    
    用于表示所有与厂家API交互过程中的错误
    """
    def __init__(self, message: str, status_code: Optional[int] = None, response_data: Optional[dict] = None):
        self.message = message
        self.status_code = status_code
        self.response_data = response_data
        super().__init__(self.message)

    def __str__(self) -> str:
        if self.status_code:
            return f"[{self.status_code}] {self.message}"
        return self.message


class CushionCloudClient:
    """
    点点甜睡智能坐垫云服务API客户端
    
    使用httpx异步客户端进行HTTP请求，支持连接池复用。
    Token自动管理，缓存到Redis，过期自动重新登录。
    所有方法包含完善的错误处理和重试机制。
    
    使用示例:
        async with CushionCloudClient() as client:
            devices = await client.get_device_list("TA0096400014")
    """
    
    # API基础URL
    BASE_URL = "https://sleepiotapi.hliit.com"
    
    # Token缓存配置
    TOKEN_CACHE_KEY = "cushion_cloud_token"
    TOKEN_TTL = 23 * 60 * 60  # 23小时（厂家token有效期24小时）
    
    def __init__(
        self,
        username: Optional[str] = None,
        password: Optional[str] = None,
        redis_client: Optional[Any] = None
    ):
        """
        初始化客户端
        
        Args:
            username: 点点甜睡账号，不传则从配置读取
            password: 点点甜睡密码，不传则从配置读取
            redis_client: Redis客户端实例，用于缓存Token
        """
        self.username = username or settings.CUSHION_CLOUD_USERNAME
        self.password = password or settings.CUSHION_CLOUD_PASSWORD
        self.redis_client = redis_client
        self._token: Optional[str] = None
        self._client: Optional[httpx.AsyncClient] = None
    
    async def __aenter__(self) -> "CushionCloudClient":
        """异步上下文管理器入口"""
        await self._init_client()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """异步上下文管理器出口"""
        await self.close()
    
    async def _init_client(self):
        """初始化HTTP客户端"""
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=self.BASE_URL,
                timeout=30.0,
                follow_redirects=True,
                headers={
                    "Content-Type": "application/json",
                    "Accept": "application/json",
                }
            )
    
    async def close(self):
        """关闭HTTP客户端"""
        if self._client:
            await self._client.aclose()
            self._client = None
    
    def _get_client(self) -> httpx.AsyncClient:
        """获取HTTP客户端实例"""
        if self._client is None:
            raise CushionCloudError("HTTP客户端未初始化，请使用 async with 上下文管理器")
        return self._client
    
    async def _get_token(self) -> str:
        """
        获取访问Token
        
        优先从Redis缓存获取，缓存不存在或过期则重新登录
        
        Returns:
            Token字符串
        """
        # 尝试从Redis获取缓存的Token
        if self.redis_client:
            try:
                cached_token = await self.redis_client.get(self.TOKEN_CACHE_KEY)
                if cached_token:
                    logger.debug("从Redis获取缓存的Token")
                    return cached_token.decode() if isinstance(cached_token, bytes) else cached_token
            except Exception as e:
                logger.warning(f"从Redis获取Token失败: {e}")
        
        # 如果内存中有Token则直接使用
        if self._token:
            return self._token
        
        # 重新登录获取Token
        return await self._login()
    
    async def _login(self) -> str:
        """
        登录获取Token
        
        POST /yunLogin
        请求体: {"username": "xxx", "password": "xxx"}
        
        Returns:
            Token字符串
        """
        logger.info("正在登录点点甜睡云服务...")
        
        client = self._get_client()
        
        try:
            response = await client.post(
                "/yunLogin",
                json={
                    "username": self.username,
                    "password": self.password
                }
            )
            
            response.raise_for_status()
            
            data = response.json()
            
            # 检查响应
            if data.get("code") != 200:
                raise CushionCloudError(
                    f"登录失败: {data.get('msg', '未知错误')}",
                    response_data=data
                )
            
            # 提取Token
            token = data.get("data")
            if not token:
                raise CushionCloudError("登录响应中未找到Token")
            
            # 缓存Token到Redis
            if self.redis_client:
                try:
                    await self.redis_client.setex(
                        self.TOKEN_CACHE_KEY,
                        self.TOKEN_TTL,
                        token
                    )
                    logger.debug("Token已缓存到Redis")
                except Exception as e:
                    logger.warning(f"Token缓存到Redis失败: {e}")
            
            # 内存缓存
            self._token = token
            
            logger.info("登录成功")
            return token
            
        except httpx.HTTPStatusError as e:
            raise CushionCloudError(
                f"登录请求失败: {e.response.status_code}",
                status_code=e.response.status_code
            )
        except httpx.RequestError as e:
            raise CushionCloudError(f"网络请求错误: {e}")
    
    def _get_auth_headers(self) -> Dict[str, str]:
        """获取带认证的请求头"""
        return {
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type(CushionCloudError),
        reraise=True
    )
    async def _request(
        self,
        method: str,
        url: str,
        params: Optional[Dict[str, Any]] = None,
        json_data: Optional[Dict[str, Any]] = None,
        require_auth: bool = True
    ) -> Dict[str, Any]:
        """
        发送HTTP请求
        
        Args:
            method: HTTP方法 (GET/POST等)
            url: 请求路径
            params: URL参数
            json_data: JSON请求体
            require_auth: 是否需要认证
        
        Returns:
            响应数据
        """
        client = self._get_client()
        
        # 准备请求头
        headers = {}
        if require_auth:
            token = await self._get_token()
            headers["Authorization"] = token
        
        try:
            response = await client.request(
                method=method,
                url=url,
                params=params,
                json=json_data,
                headers=headers
            )
            
            response.raise_for_status()
            
            data = response.json()
            
            # 检查业务状态码
            if data.get("code") != 200:
                # Token过期，清除缓存并重试
                if data.get("code") == 401 or "token" in data.get("msg", "").lower():
                    logger.warning("Token已过期，清除缓存重新登录")
                    self._token = None
                    if self.redis_client:
                        try:
                            await self.redis_client.delete(self.TOKEN_CACHE_KEY)
                        except Exception:
                            pass
                    raise CushionCloudError("Token过期，需要重新登录", status_code=401)
                
                raise CushionCloudError(
                    f"API请求失败: {data.get('msg', '未知错误')}",
                    status_code=data.get("code"),
                    response_data=data
                )
            
            return data
            
        except httpx.HTTPStatusError as e:
            raise CushionCloudError(
                f"HTTP请求失败: {e.response.status_code}",
                status_code=e.response.status_code
            )
        except httpx.RequestError as e:
            raise CushionCloudError(f"网络请求错误: {e}")
    
    # ===========================================
    # 设备相关API
    # ===========================================
    
    async def get_device_list(self, device_code: str) -> Dict[str, Any]:
        """
        获取设备信息列表
        
        GET /yun/service/deviceList?deviceCode={device_code}
        
        返回设备信息，包含:
        - deviceId: 设备ID
        - deviceCode: 设备编码(SN号)
        - deviceStatus: 设备状态 (离线=02, 离床=04, 在线/在床=其他)
        - onlineTime: 上线时间
        - bleMac: 蓝牙MAC
        - wifiMac: WiFi MAC
        - deviceType: 设备型号
        - firmwareVersion: 固件版本
        
        Args:
            device_code: 设备编码(SN号)，如"TA0096400014"
        
        Returns:
            设备信息字典
        """
        logger.info(f"获取设备信息: {device_code}")
        
        data = await self._request(
            "GET",
            "/yun/service/deviceList",
            params={"deviceCode": device_code}
        )
        
        return data.get("data", {})
    
    async def get_device_data(
        self,
        device_code: str,
        start_time: str,
        end_time: str,
        page_size: int = 10,
        page_num: int = 1
    ) -> Dict[str, Any]:
        """
        获取设备原始数据
        
        GET /yun/service/sleepDataList
        
        返回原始数据，包含:
        - heartRate: 心率 (取大于0的一分钟平均值更准确)
        - breathing: 呼吸频率
        - signal: 信号强度
        - sosType: SOS事件类型 (5=SOS, 6=床垫拔出, 7=剪断, 8=湿床, 9=疑似生命异常)
        - bedStatus: 在床状态 (1=在床, 0=离床)
        - sleepStatus: 睡眠状态 (0=离枕, 1=正常, 2=打鼾, 3=翻身, 4=呼吸暂停)
        
        Args:
            device_code: 设备编码
            start_time: 开始时间 (格式: "2024-01-01 00:00:00")
            end_time: 结束时间
            page_size: 每页记录数
            page_num: 页码
        
        Returns:
            数据字典
        """
        logger.info(f"获取设备数据: {device_code}, {start_time} ~ {end_time}")
        
        data = await self._request(
            "GET",
            "/yun/service/sleepDataList",
            params={
                "deviceCode": device_code,
                "startTime": start_time,
                "endTime": end_time,
                "pageSize": page_size,
                "pageNum": page_num
            }
        )
        
        return data.get("data", {})
    
    # ===========================================
    # 报告相关API
    # ===========================================
    
    async def get_report_list(
        self,
        device_code: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        page_size: int = 10,
        page_num: int = 1
    ) -> Dict[str, Any]:
        """
        获取睡眠报告列表
        
        GET /yun/service/reportList
        
        返回睡眠报告列表，包含:
        - reportId: 报告ID
        - startTime: 开始时间
        - endTime: 结束时间
        - totalTimes: 总时长
        - heartAvg/Max/Min: 心率统计
        - breathAvg/Max/Min: 呼吸统计
        - score: 睡眠评分
        - cycleData: 睡眠周期数据
        
        Args:
            device_code: 设备编码 (必填)
            start_date: 开始日期 (格式: "2024-01-01")
            end_date: 结束日期
            page_size: 每页记录数
            page_num: 页码
        
        Returns:
            报告列表数据
        """
        logger.info(f"获取报告列表: {device_code}")
        
        params = {
            "deviceCode": device_code,
            "pageSize": page_size,
            "pageNum": page_num
        }
        
        if start_date:
            params["startDate"] = start_date
        if end_date:
            params["endDate"] = end_date
        
        data = await self._request(
            "GET",
            "/yun/service/reportList",
            params=params
        )
        
        return data.get("data", {})
    
    async def get_report_chart_data(
        self,
        terminal_id: str,
        start_time: str,
        end_time: str,
        page_size: int = 100,
        page_num: int = 1
    ) -> Dict[str, Any]:
        """
        获取报告图表数据(时序数据)
        
        POST /yun/service/sleepHeathData?pageSize=100&pageNum=1
        请求体: {"terminalId": "xxx", "createTime": "xxx", "updateTime": "xxx"}
        
        返回时序心率和呼吸数据数组:
        [{createTime, heartRate, breathing}, ...]
        
        Args:
            terminal_id: 终端ID/报告ID
            start_time: 开始时间
            end_time: 结束时间
            page_size: 每页记录数
            page_num: 页码
        
        Returns:
            时序数据
        """
        logger.info(f"获取报告图表数据: {terminal_id}")
        
        data = await self._request(
            "POST",
            "/yun/service/sleepHeathData",
            params={"pageSize": page_size, "pageNum": page_num},
            json_data={
                "terminalId": terminal_id,
                "createTime": start_time,
                "updateTime": end_time
            }
        )
        
        return data.get("data", {})
    
    async def get_report_deductions(
        self,
        report_id: int,
        device_code: str
    ) -> Dict[str, Any]:
        """
        获取报告扣分项
        
        GET /yun/service/scoreDeducts?reportId={id}&deviceCode={code}
        
        Args:
            report_id: 报告ID
            device_code: 设备编码
        
        Returns:
            扣分项列表
        """
        logger.info(f"获取报告扣分项: report_id={report_id}")
        
        data = await self._request(
            "GET",
            "/yun/service/scoreDeducts",
            params={
                "reportId": report_id,
                "deviceCode": device_code
            }
        )
        
        return data.get("data", {})
    
    # ===========================================
    # 统计分析API
    # ===========================================
    
    async def get_weekly_monthly_stats(
        self,
        device_code: str,
        start_time: str,
        end_time: str
    ) -> Dict[str, Any]:
        """
        获取周/月统计数据(按日聚合)
        
        POST /yun/service/sleepDataDateList
        请求体: {"deviceCode": "xxx", "startTime": "xxx", "endTime": "xxx"}
        
        Args:
            device_code: 设备编码
            start_time: 开始时间
            end_time: 结束时间
        
        Returns:
            按日聚合的统计数据
        """
        logger.info(f"获取周/月统计: {device_code}")
        
        data = await self._request(
            "POST",
            "/yun/service/sleepDataDateList",
            json_data={
                "deviceCode": device_code,
                "startTime": start_time,
                "endTime": end_time
            }
        )
        
        return data.get("data", {})
    
    async def get_period_comparison(
        self,
        device_code: str,
        last_start: str,
        last_end: str,
        current_start: str,
        current_end: str
    ) -> Dict[str, Any]:
        """
        获取时段对比数据
        
        POST /yun/service/sleepDataCompare
        请求体包含上期和本期的日期范围
        
        Args:
            device_code: 设备编码
            last_start: 上期开始时间
            last_end: 上期结束时间
            current_start: 本期开始时间
            current_end: 本期结束时间
        
        Returns:
            各指标的对比数据
        """
        logger.info(f"获取时段对比: {device_code}")
        
        data = await self._request(
            "POST",
            "/yun/service/sleepDataCompare",
            json_data={
                "deviceCode": device_code,
                "lastStartTime": last_start,
                "lastEndTime": last_end,
                "currentStartTime": current_start,
                "currentEndTime": current_end
            }
        )
        
        return data.get("data", {})
    
    async def get_device_adc(
        self,
        terminal_id: str,
        extend_int1: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        获取ADC原始波形数据
        
        GET /yun/service/getDeviceAdc?terminalId={id}&extendInt1={timestamp}
        
        Args:
            terminal_id: 终端ID
            extend_int1: 时间戳(可选)
        
        Returns:
            ADC波形数据数组
        """
        logger.info(f"获取ADC波形数据: {terminal_id}")
        
        params = {"terminalId": terminal_id}
        if extend_int1:
            params["extendInt1"] = extend_int1
        
        data = await self._request(
            "GET",
            "/yun/service/getDeviceAdc",
            params=params
        )
        
        return data.get("data", [])
    
    # ===========================================
    # Webhook数据接收
    # ===========================================
    
    @staticmethod
    def verify_webhook_signature(
        payload: bytes,
        signature: str,
        secret: str
    ) -> bool:
        """
        验证Webhook签名
        
        使用MD5签名验证请求来源的合法性
        
        Args:
            payload: 原始请求体
            signature: 请求头中的签名
            secret: Webhook密钥
        
        Returns:
            签名是否有效
        """
        import hashlib
        
        # 计算MD5签名
        sign_str = payload.decode() + secret
        calculated = hashlib.md5(sign_str.encode()).hexdigest()
        
        return calculated == signature
    
    @staticmethod
    def parse_webhook_data(data: Dict[str, Any]) -> Dict[str, Any]:
        """
        解析Webhook推送的数据
        
        厂家推送的数据格式可能包含:
        - 设备状态变更
        - 实时检测数据
        - 报告生成通知
        
        Args:
            data: Webhook请求体
        
        Returns:
            解析后的结构化数据
        """
        event_type = data.get("type") or data.get("eventType")
        
        if event_type == "device_status":
            return {
                "event_type": "device_status",
                "device_code": data.get("deviceCode"),
                "status": data.get("deviceStatus"),
                "timestamp": data.get("timestamp")
            }
        
        elif event_type == "realtime_data":
            return {
                "event_type": "realtime_data",
                "device_code": data.get("deviceCode"),
                "heart_rate": data.get("heartRate"),
                "breathing": data.get("breathing"),
                "bed_status": data.get("bedStatus"),
                "timestamp": data.get("timestamp")
            }
        
        elif event_type == "report_ready":
            return {
                "event_type": "report_ready",
                "device_code": data.get("deviceCode"),
                "report_id": data.get("reportId"),
                "timestamp": data.get("timestamp")
            }
        
        else:
            return {
                "event_type": "unknown",
                "raw_data": data
            }
