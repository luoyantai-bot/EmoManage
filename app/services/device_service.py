# ===========================================
# 设备业务服务
# ===========================================
"""
设备相关的业务逻辑处理

主要功能:
- 设备状态同步
- 设备数据采集
- 设备健康检查
"""

from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
from uuid import UUID

from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.device import Device
from app.models.tenant import Tenant
from app.services.cushion_cloud_client import CushionCloudClient, CushionCloudError


class DeviceService:
    """
    设备业务服务
    
    封装设备相关的复杂业务逻辑，包括:
    - 与厂家云服务的交互
    - 设备状态同步和更新
    - 设备数据的本地缓存
    """
    
    # 设备状态映射 (厂家状态码 -> 本地状态)
    STATUS_MAPPING = {
        "02": "offline",  # 离线
        "04": "offline",  # 离床
        "01": "online",   # 在线
        "03": "in_use",   # 在床使用中
    }
    
    def __init__(self, db: AsyncSession):
        """
        初始化设备服务
        
        Args:
            db: 数据库会话
        """
        self.db = db
    
    async def sync_device_from_cloud(
        self,
        device_code: str,
        client: Optional[CushionCloudClient] = None
    ) -> Device:
        """
        从厂家云平台同步设备信息
        
        调用厂家API获取设备最新信息并更新本地数据库
        
        Args:
            device_code: 设备编码(SN号)
            client: CushionCloudClient实例(可选，不传则自动创建)
        
        Returns:
            更新后的设备对象
        
        Raises:
            CushionCloudError: 云服务调用失败
            ValueError: 设备不存在
        """
        logger.info(f"开始同步设备信息: {device_code}")
        
        # 查询本地设备
        result = await self.db.execute(
            select(Device).where(Device.device_code == device_code)
        )
        device = result.scalar_one_or_none()
        
        if not device:
            raise ValueError(f"设备不存在: {device_code}")
        
        # 获取云服务设备信息
        should_close = False
        if client is None:
            client = CushionCloudClient()
            should_close = True
        
        try:
            cloud_data = await client.get_device_list(device_code)
            
            if cloud_data:
                # 解析云服务返回的数据
                device_list = cloud_data if isinstance(cloud_data, list) else [cloud_data]
                
                if device_list:
                    cloud_device = device_list[0]
                    
                    # 更新设备信息
                    self._update_device_from_cloud(device, cloud_device)
                    
                    # 保存更新
                    await self.db.commit()
                    await self.db.refresh(device)
                    
                    logger.info(f"设备信息同步完成: {device_code}")
            
            return device
            
        except CushionCloudError as e:
            logger.error(f"同步设备信息失败: {e}")
            raise
        finally:
            if should_close:
                await client.close()
    
    def _update_device_from_cloud(self, device: Device, cloud_data: Dict[str, Any]):
        """
        使用云服务数据更新设备
        
        Args:
            device: 本地设备对象
            cloud_data: 云服务返回的设备数据
        """
        # 映射设备状态
        cloud_status = str(cloud_data.get("deviceStatus", ""))
        device.status = self.STATUS_MAPPING.get(cloud_status, "offline")
        
        # 更新设备信息
        if cloud_data.get("deviceType"):
            device.device_type = cloud_data["deviceType"]
        
        if cloud_data.get("bleMac"):
            device.ble_mac = cloud_data["bleMac"]
        
        if cloud_data.get("wifiMac"):
            device.wifi_mac = cloud_data["wifiMac"]
        
        if cloud_data.get("firmwareVersion"):
            device.firmware_version = cloud_data["firmwareVersion"]
        
        if cloud_data.get("deviceId"):
            device.cloud_device_id = cloud_data["deviceId"]
        
        # 更新在线时间
        if device.status in ["online", "in_use"]:
            device.last_online_at = datetime.utcnow()
    
    async def batch_sync_devices(
        self,
        tenant_id: Optional[UUID] = None
    ) -> Dict[str, Any]:
        """
        批量同步设备状态
        
        批量从厂家云平台同步所有设备的状态
        
        Args:
            tenant_id: 租户ID(可选，不传则同步所有设备)
        
        Returns:
            同步结果统计
        """
        logger.info("开始批量同步设备状态")
        
        # 查询需要同步的设备
        query = select(Device)
        if tenant_id:
            query = query.where(Device.tenant_id == tenant_id)
        
        result = await self.db.execute(query)
        devices = result.scalars().all()
        
        stats = {
            "total": len(devices),
            "success": 0,
            "failed": 0,
            "errors": []
        }
        
        async with CushionCloudClient() as client:
            for device in devices:
                try:
                    await self.sync_device_from_cloud(device.device_code, client)
                    stats["success"] += 1
                except Exception as e:
                    stats["failed"] += 1
                    stats["errors"].append({
                        "device_code": device.device_code,
                        "error": str(e)
                    })
                    logger.error(f"同步设备失败: {device.device_code}, 错误: {e}")
        
        logger.info(f"批量同步完成: 成功 {stats['success']}, 失败 {stats['failed']}")
        return stats
    
    async def get_device_realtime_data(
        self,
        device_code: str,
        duration_minutes: int = 30
    ) -> Dict[str, Any]:
        """
        获取设备实时数据
        
        获取设备最近一段时间的检测数据
        
        Args:
            device_code: 设备编码
            duration_minutes: 时间范围(分钟)
        
        Returns:
            实时数据摘要
        """
        logger.info(f"获取设备实时数据: {device_code}")
        
        end_time = datetime.utcnow()
        start_time = end_time - timedelta(minutes=duration_minutes)
        
        async with CushionCloudClient() as client:
            data = await client.get_device_data(
                device_code=device_code,
                start_time=start_time.strftime("%Y-%m-%d %H:%M:%S"),
                end_time=end_time.strftime("%Y-%m-%d %H:%M:%S"),
                page_size=1000
            )
        
        # 处理原始数据
        return self._process_realtime_data(data)
    
    def _process_realtime_data(self, raw_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        处理实时数据
        
        从原始数据中提取有效的统计信息
        
        Args:
            raw_data: 原始数据
        
        Returns:
            处理后的数据摘要
        """
        data_list = raw_data.get("list", []) or raw_data.get("data", [])
        
        if not data_list:
            return {
                "has_data": False,
                "message": "暂无数据"
            }
        
        # 提取有效的心率和呼吸数据(大于0的值)
        heart_rates = [
            d.get("heartRate", 0) for d in data_list
            if d.get("heartRate", 0) > 0
        ]
        breathings = [
            d.get("breathing", 0) for d in data_list
            if d.get("breathing", 0) > 0
        ]
        
        result = {
            "has_data": True,
            "data_count": len(data_list),
            "heart_rate": {},
            "breathing": {},
            "bed_status": {}
        }
        
        # 心率统计
        if heart_rates:
            result["heart_rate"] = {
                "avg": round(sum(heart_rates) / len(heart_rates), 1),
                "max": max(heart_rates),
                "min": min(heart_rates),
                "count": len(heart_rates)
            }
        
        # 呼吸统计
        if breathings:
            result["breathing"] = {
                "avg": round(sum(breathings) / len(breathings), 1),
                "max": max(breathings),
                "min": min(breathings),
                "count": len(breathings)
            }
        
        # 在床状态统计
        bed_status_count = {}
        for d in data_list:
            status = d.get("bedStatus", "unknown")
            bed_status_count[status] = bed_status_count.get(status, 0) + 1
        result["bed_status"] = bed_status_count
        
        return result
    
    async def check_device_health(
        self,
        device_id: UUID
    ) -> Dict[str, Any]:
        """
        检查设备健康状态
        
        综合评估设备的在线状态、数据质量等
        
        Args:
            device_id: 设备ID
        
        Returns:
            健康检查结果
        """
        logger.info(f"检查设备健康状态: {device_id}")
        
        # 查询设备
        result = await self.db.execute(
            select(Device).where(Device.id == device_id)
        )
        device = result.scalar_one_or_none()
        
        if not device:
            raise ValueError(f"设备不存在: {device_id}")
        
        health = {
            "device_id": str(device_id),
            "device_code": device.device_code,
            "status": device.status,
            "is_healthy": True,
            "issues": []
        }
        
        # 检查在线状态
        if device.status == "offline":
            health["is_healthy"] = False
            health["issues"].append("设备离线")
        
        # 检查最后在线时间
        if device.last_online_at:
            offline_duration = datetime.utcnow() - device.last_online_at
            if offline_duration.days > 7:
                health["is_healthy"] = False
                health["issues"].append(f"设备已离线 {offline_duration.days} 天")
        else:
            health["issues"].append("设备从未在线")
        
        # 检查固件版本
        if not device.firmware_version:
            health["issues"].append("固件版本未知")
        
        return health
