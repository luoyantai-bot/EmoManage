# ===========================================
# Device Sync Service
# ===========================================
"""
Sync device information from Cushion Cloud to local database

Provides:
- Sync single device from cloud
- Batch sync all devices
- Check device status from Redis or cloud
"""

from datetime import datetime
from typing import Dict, List, Optional
from uuid import UUID

from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.device import Device
from app.models.tenant import Tenant
from app.services.cushion_cloud_client import CushionCloudClient, CushionCloudError
from app.services.redis_client import RedisClient, RedisKeys


# Device status mapping (manufacturer code -> local status)
STATUS_MAPPING = {
    "02": "offline",    # Offline
    "04": "offline",    # Out of bed
    "01": "online",     # Online
    "03": "in_use",     # In bed / in use
}


class DeviceSyncService:
    """
    Sync device information from Cushion Cloud
    
    Handles:
    - Syncing device info from manufacturer API
    - Creating/updating local device records
    - Checking device status from Redis or cloud
    """
    
    def __init__(self, db: AsyncSession, redis: Optional[RedisClient] = None):
        """
        Initialize service
        
        Args:
            db: Database session
            redis: Redis client (optional)
        """
        self.db = db
        self.redis = redis
    
    async def sync_device(
        self,
        device_code: str,
        tenant_id: UUID,
        client: Optional[CushionCloudClient] = None
    ) -> Device:
        """
        Sync a single device from Cushion Cloud
        
        1. Call CushionCloudClient.get_device_list(device_code)
        2. If device doesn't exist locally, create it
        3. If exists, update status, onlineTime, firmwareVersion, etc.
        
        Args:
            device_code: Device code (SN number)
            tenant_id: Tenant ID for new device
            client: CushionCloudClient instance (optional)
        
        Returns:
            Device object
        
        Raises:
            CushionCloudError: Cloud API call failed
            ValueError: Device not found in cloud
        """
        logger.info(f"Syncing device: {device_code}")
        
        # Get device info from cloud
        should_close = False
        if client is None:
            client = CushionCloudClient()
            should_close = True
        
        try:
            cloud_data = await client.get_device_list(device_code)
            
            if not cloud_data:
                raise ValueError(f"Device not found in cloud: {device_code}")
            
            # Parse cloud data (may be list or dict)
            if isinstance(cloud_data, list):
                if not cloud_data:
                    raise ValueError(f"Device not found in cloud: {device_code}")
                cloud_device = cloud_data[0]
            else:
                cloud_device = cloud_data
            
            # Check if device exists locally
            result = await self.db.execute(
                select(Device).where(Device.device_code == device_code)
            )
            device = result.scalar_one_or_none()
            
            if device:
                # Update existing device
                device = self._update_device_from_cloud(device, cloud_device)
                logger.info(f"Updated existing device: {device_code}")
            else:
                # Create new device
                device = await self._create_device_from_cloud(
                    device_code, tenant_id, cloud_device
                )
                logger.info(f"Created new device: {device_code}")
            
            await self.db.commit()
            await self.db.refresh(device)
            
            return device
            
        except CushionCloudError as e:
            logger.error(f"Failed to sync device {device_code}: {e}")
            raise
        finally:
            if should_close:
                await client.close()
    
    def _update_device_from_cloud(self, device: Device, cloud_data: Dict) -> Device:
        """
        Update device from cloud data
        
        Args:
            device: Existing device object
            cloud_data: Cloud API response
        
        Returns:
            Updated device object
        """
        # Map device status
        cloud_status = str(cloud_data.get("deviceStatus", ""))
        device.status = STATUS_MAPPING.get(cloud_status, "offline")
        
        # Update device info if provided
        if cloud_data.get("deviceType"):
            device.device_type = cloud_data["deviceType"]
        
        if cloud_data.get("bleMac"):
            device.ble_mac = cloud_data["bleMac"]
        
        if cloud_data.get("wifiMac"):
            device.wifi_mac = cloud_data["wifiMac"]
        
        if cloud_data.get("firmwareVersion"):
            device.firmware_version = cloud_data["firmwareVersion"]
        
        if cloud_data.get("hardwareVersion"):
            device.hardware_version = cloud_data["hardwareVersion"]
        
        if cloud_data.get("deviceId"):
            device.cloud_device_id = cloud_data["deviceId"]
        
        # Update online time if device is active
        if device.status in ["online", "in_use"]:
            device.last_online_at = datetime.utcnow()
        
        return device
    
    async def _create_device_from_cloud(
        self,
        device_code: str,
        tenant_id: UUID,
        cloud_data: Dict
    ) -> Device:
        """
        Create new device from cloud data
        
        Args:
            device_code: Device code
            tenant_id: Tenant ID
            cloud_data: Cloud API response
        
        Returns:
            New device object
        """
        cloud_status = str(cloud_data.get("deviceStatus", ""))
        status = STATUS_MAPPING.get(cloud_status, "offline")
        
        device = Device(
            device_code=device_code,
            tenant_id=tenant_id,
            status=status,
            device_type=cloud_data.get("deviceType"),
            ble_mac=cloud_data.get("bleMac"),
            wifi_mac=cloud_data.get("wifiMac"),
            firmware_version=cloud_data.get("firmwareVersion"),
            hardware_version=cloud_data.get("hardwareVersion"),
            cloud_device_id=cloud_data.get("deviceId"),
            last_online_at=datetime.utcnow() if status in ["online", "in_use"] else None
        )
        
        self.db.add(device)
        return device
    
    async def sync_all_devices(
        self,
        tenant_id: UUID,
        device_codes: Optional[List[str]] = None
    ) -> Dict[str, any]:
        """
        Sync all devices for a tenant
        
        Args:
            tenant_id: Tenant ID
            device_codes: List of device codes to sync (optional, syncs all if not provided)
        
        Returns:
            Sync statistics
        """
        logger.info(f"Starting batch sync for tenant: {tenant_id}")
        
        # Get device codes if not provided
        if device_codes is None:
            result = await self.db.execute(
                select(Device.device_code).where(Device.tenant_id == tenant_id)
            )
            device_codes = [row[0] for row in result.fetchall()]
        
        stats = {
            "total": len(device_codes),
            "success": 0,
            "failed": 0,
            "created": 0,
            "updated": 0,
            "errors": []
        }
        
        async with CushionCloudClient() as client:
            for device_code in device_codes:
                try:
                    # Check if device exists
                    result = await self.db.execute(
                        select(Device).where(Device.device_code == device_code)
                    )
                    exists = result.scalar_one_or_none() is not None
                    
                    await self.sync_device(device_code, tenant_id, client)
                    stats["success"] += 1
                    if exists:
                        stats["updated"] += 1
                    else:
                        stats["created"] += 1
                        
                except Exception as e:
                    stats["failed"] += 1
                    stats["errors"].append({
                        "device_code": device_code,
                        "error": str(e)
                    })
                    logger.error(f"Failed to sync {device_code}: {e}")
        
        logger.info(f"Batch sync completed: {stats['success']}/{stats['total']}")
        return stats
    
    async def check_device_status(
        self,
        device_code: str,
        client: Optional[CushionCloudClient] = None
    ) -> str:
        """
        Check device current status
        
        First checks Redis for latest data, then falls back to cloud API.
        
        Args:
            device_code: Device code
            client: CushionCloudClient instance (optional)
        
        Returns:
            Device status: "online" / "offline" / "in_use"
        """
        # First check Redis for latest data
        if self.redis:
            latest_data = await self.redis.get_device_latest(device_code)
            if latest_data:
                # Check if data is recent (within 60 seconds)
                updated_at = latest_data.get("updated_at")
                if updated_at:
                    from datetime import datetime, timedelta
                    try:
                        last_update = datetime.fromisoformat(updated_at)
                        if datetime.utcnow() - last_update < timedelta(seconds=60):
                            # Device is active
                            bed_status = latest_data.get("bed_status")
                            return "in_use" if bed_status == "1" else "online"
                    except (ValueError, TypeError):
                        pass
        
        # Fall back to database status
        result = await self.db.execute(
            select(Device.status).where(Device.device_code == device_code)
        )
        status = result.scalar_one_or_none()
        
        if status:
            return status
        
        # Finally try cloud API
        should_close = False
        if client is None:
            client = CushionCloudClient()
            should_close = True
        
        try:
            cloud_data = await client.get_device_list(device_code)
            if cloud_data:
                if isinstance(cloud_data, list):
                    cloud_device = cloud_data[0]
                else:
                    cloud_device = cloud_data
                
                cloud_status = str(cloud_device.get("deviceStatus", ""))
                return STATUS_MAPPING.get(cloud_status, "offline")
            
            return "offline"
            
        except Exception as e:
            logger.warning(f"Failed to check device status from cloud: {e}")
            return "offline"
        finally:
            if should_close:
                await client.close()
    
    async def update_device_status_from_webhook(
        self,
        device_code: str,
        bed_status: str
    ) -> Optional[Device]:
        """
        Update device status based on webhook data
        
        Args:
            device_code: Device code
            bed_status: Bed status from webhook (1=in bed, 0=out of bed)
        
        Returns:
            Updated device or None
        """
        result = await self.db.execute(
            select(Device).where(Device.device_code == device_code)
        )
        device = result.scalar_one_or_none()
        
        if not device:
            logger.warning(f"Device not found for status update: {device_code}")
            return None
        
        # Update status based on bed status
        if bed_status == "1":
            device.status = "in_use"
        else:
            device.status = "online"
        
        device.last_online_at = datetime.utcnow()
        
        await self.db.commit()
        await self.db.refresh(device)
        
        logger.debug(f"Updated device status: {device_code} -> {device.status}")
        return device
