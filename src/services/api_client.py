import asyncio

import httpx
from httpx import HTTPStatusError

from src.config import get_settings
from src.utils.logger import logger


class ApiClientError(Exception):
    """Generic API error."""


class NotFoundError(ApiClientError):
    """404 error."""


class UnauthorizedError(ApiClientError):
    """401 error."""


class RemnawaveApiClient:
    def __init__(self) -> None:
        self.settings = get_settings()
        # Увеличиваем таймауты для стабильности соединения
        # connect - таймаут на установку соединения
        # read - таймаут на чтение ответа
        # write - таймаут на отправку запроса
        # pool - таймаут на получение соединения из пула
        timeout_config = httpx.Timeout(
            connect=15.0,  # Увеличен с 20 до 15 для connect
            read=30.0,     # Увеличен до 30 для read
            write=15.0,    # Таймаут на запись
            pool=10.0      # Таймаут на получение из пула
        )
        # Убираем завершающий слеш из base_url, чтобы избежать двойного слеша при объединении с URL
        base_url = str(self.settings.api_base_url).rstrip("/")
        self._client = httpx.AsyncClient(
            base_url=base_url,
            headers=self._build_headers(),
            timeout=timeout_config,
            limits=httpx.Limits(max_keepalive_connections=10, max_connections=20),
            follow_redirects=True,  # Автоматически следовать редиректам (HTTP -> HTTPS)
        )

    def _build_headers(self) -> dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self.settings.api_token:
            headers["Authorization"] = f"Bearer {self.settings.api_token}"
        return headers

    async def _get(self, url: str, max_retries: int = 3) -> dict:
        """Выполняет GET запрос с retry для сетевых ошибок."""
        full_url = f"{self._client.base_url}{url}"
        last_exc = None
        for attempt in range(max_retries):
            try:
                logger.debug("GET request to %s (attempt %d/%d)", full_url, attempt + 1, max_retries)
                response = await self._client.get(url)
                response.raise_for_status()
                return response.json()
            except HTTPStatusError as exc:
                status = exc.response.status_code
                if status in (401, 403):
                    raise UnauthorizedError from exc
                if status == 404:
                    raise NotFoundError from exc
                # 308 Permanent Redirect обычно означает HTTP -> HTTPS
                if status == 308:
                    https_url = full_url.replace("http://", "https://")
                    logger.error(
                        "API returned 308 Permanent Redirect. "
                        "Please use HTTPS in API_BASE_URL. "
                        "Current: %s -> Should be: %s",
                        full_url, https_url
                    )
                logger.warning("API error %s on GET %s: %s", status, full_url, exc.response.text)
                raise ApiClientError from exc
            except (httpx.RemoteProtocolError, httpx.ConnectError, httpx.ReadTimeout) as exc:
                last_exc = exc
                error_type = type(exc).__name__
                if attempt < max_retries - 1:
                    delay = 0.5 * (2 ** attempt)  # Экспоненциальная задержка: 0.5s, 1s, 2s
                    logger.warning(
                        "HTTP client error on GET %s: %s (%s), retrying in %.1fs (attempt %d/%d)",
                        full_url, exc, error_type, delay, attempt + 1, max_retries
                    )
                    await asyncio.sleep(delay)
                else:
                    logger.error(
                        "HTTP client error on GET %s: %s (%s) - max retries reached. "
                        "Server may be overloaded or network unstable.",
                        full_url, exc, error_type
                    )
            except httpx.HTTPError as exc:
                error_type = type(exc).__name__
                logger.warning("HTTP client error on GET %s: %s (%s)", full_url, exc, error_type)
                raise ApiClientError from exc
        
        # Если все попытки исчерпаны, выбрасываем последнюю ошибку
        raise ApiClientError(f"Failed to get {full_url} after {max_retries} attempts") from last_exc

    async def _post(self, url: str, json: dict | None = None, max_retries: int = 3) -> dict:
        """Выполняет POST запрос с retry для сетевых ошибок."""
        full_url = f"{self._client.base_url}{url}"
        last_exc = None
        for attempt in range(max_retries):
            try:
                logger.debug("POST request to %s (attempt %d/%d)", full_url, attempt + 1, max_retries)
                response = await self._client.post(url, json=json)
                response.raise_for_status()
                return response.json()
            except HTTPStatusError as exc:
                status = exc.response.status_code
                if status in (401, 403):
                    raise UnauthorizedError from exc
                if status == 404:
                    raise NotFoundError from exc
                logger.warning("API error %s on POST %s: %s", status, full_url, exc.response.text)
                raise ApiClientError from exc
            except (httpx.RemoteProtocolError, httpx.ConnectError, httpx.ReadTimeout) as exc:
                last_exc = exc
                error_type = type(exc).__name__
                if attempt < max_retries - 1:
                    delay = 0.5 * (2 ** attempt)  # Экспоненциальная задержка: 0.5s, 1s, 2s
                    logger.warning(
                        "HTTP client error on POST %s: %s (%s), retrying in %.1fs (attempt %d/%d)",
                        full_url, exc, error_type, delay, attempt + 1, max_retries
                    )
                    await asyncio.sleep(delay)
                else:
                    logger.error(
                        "HTTP client error on POST %s: %s (%s) - max retries reached. "
                        "Server may be overloaded or network unstable.",
                        full_url, exc, error_type
                    )
            except httpx.HTTPError as exc:
                error_type = type(exc).__name__
                logger.warning("HTTP client error on POST %s: %s (%s)", full_url, exc, error_type)
                raise ApiClientError from exc
        
        # Если все попытки исчерпаны, выбрасываем последнюю ошибку
        raise ApiClientError(f"Failed to post {full_url} after {max_retries} attempts") from last_exc

    async def _patch(self, url: str, json: dict | None = None, max_retries: int = 3) -> dict:
        """Выполняет PATCH запрос с retry для сетевых ошибок."""
        full_url = f"{self._client.base_url}{url}"
        last_exc = None
        for attempt in range(max_retries):
            try:
                logger.debug("PATCH request to %s (attempt %d/%d)", full_url, attempt + 1, max_retries)
                response = await self._client.patch(url, json=json)
                response.raise_for_status()
                return response.json()
            except HTTPStatusError as exc:
                status = exc.response.status_code
                if status in (401, 403):
                    raise UnauthorizedError from exc
                if status == 404:
                    raise NotFoundError from exc
                logger.warning("API error %s on PATCH %s: %s", status, full_url, exc.response.text)
                raise ApiClientError from exc
            except (httpx.RemoteProtocolError, httpx.ConnectError, httpx.ReadTimeout) as exc:
                last_exc = exc
                error_type = type(exc).__name__
                if attempt < max_retries - 1:
                    delay = 0.5 * (2 ** attempt)  # Экспоненциальная задержка: 0.5s, 1s, 2s
                    logger.warning(
                        "HTTP client error on PATCH %s: %s (%s), retrying in %.1fs (attempt %d/%d)",
                        full_url, exc, error_type, delay, attempt + 1, max_retries
                    )
                    await asyncio.sleep(delay)
                else:
                    logger.error(
                        "HTTP client error on PATCH %s: %s (%s) - max retries reached. "
                        "Server may be overloaded or network unstable.",
                        full_url, exc, error_type
                    )
            except httpx.HTTPError as exc:
                error_type = type(exc).__name__
                logger.warning("HTTP client error on PATCH %s: %s (%s)", full_url, exc, error_type)
                raise ApiClientError from exc
        
        # Если все попытки исчерпаны, выбрасываем последнюю ошибку
        raise ApiClientError(f"Failed to patch {full_url} after {max_retries} attempts") from last_exc

    # --- Settings ---
    async def get_settings(self) -> dict:
        return await self._get("/api/remnawave-settings")

    # --- Users ---
    async def get_user_by_username(self, username: str) -> dict:
        safe_username = username.lstrip("@")
        return await self._get(f"/api/users/by-username/{safe_username}")

    async def get_user_by_telegram_id(self, telegram_id: int) -> dict:
        return await self._get(f"/api/users/by-telegram-id/{telegram_id}")

    async def get_user_by_uuid(self, user_uuid: str) -> dict:
        return await self._get(f"/api/users/{user_uuid}")

    async def get_users(self, start: int = 0, size: int = 100) -> dict:
        return await self._get(f"/api/users?start={start}&size={size}")

    async def update_user(self, user_uuid: str, **fields) -> dict:
        payload = {"uuid": user_uuid}
        payload.update({k: v for k, v in fields.items() if v is not None})
        
        # Логируем payload для отладки
        logger.info("🔵 API: Updating user %s with payload: %s", user_uuid, payload)
        
        return await self._patch("/api/users", json=payload)

    async def disable_user(self, user_uuid: str) -> dict:
        return await self._post(f"/api/users/{user_uuid}/actions/disable")

    async def enable_user(self, user_uuid: str) -> dict:
        return await self._post(f"/api/users/{user_uuid}/actions/enable")

    async def reset_user_traffic(self, user_uuid: str) -> dict:
        return await self._post(f"/api/users/{user_uuid}/actions/reset-traffic")

    async def revoke_user_subscription(self, user_uuid: str, short_uuid: str | None = None) -> dict:
        """Отзывает подписку пользователя. short_uuid опционален - если не указан, будет сгенерирован автоматически."""
        payload: dict[str, object] = {}
        if short_uuid:
            payload["shortUuid"] = short_uuid
        return await self._post(f"/api/users/{user_uuid}/actions/revoke", json=payload)

    async def get_internal_squads(self) -> dict:
        """Получает список внутренних squads с увеличенным таймаутом и retry."""
        return await self._get_with_timeout("/api/internal-squads", timeout=30.0, max_retries=3)

    async def get_external_squads(self) -> dict:
        """Получает список внешних squads с увеличенным таймаутом и retry."""
        return await self._get_with_timeout("/api/external-squads", timeout=30.0, max_retries=3)

    async def _get_with_timeout(self, url: str, timeout: float = 30.0, max_retries: int = 3) -> dict:
        """Выполняет GET запрос с кастомным таймаутом и retry для сетевых ошибок."""
        full_url = f"{self._client.base_url}{url}"
        last_exc = None
        custom_timeout = httpx.Timeout(timeout, connect=15.0, read=timeout, write=15.0, pool=10.0)
        
        for attempt in range(max_retries):
            try:
                logger.debug("GET request to %s with timeout %.1fs (attempt %d/%d)", full_url, timeout, attempt + 1, max_retries)
                response = await self._client.get(url, timeout=custom_timeout)
                response.raise_for_status()
                return response.json()
            except HTTPStatusError as exc:
                status = exc.response.status_code
                if status in (401, 403):
                    raise UnauthorizedError from exc
                if status == 404:
                    raise NotFoundError from exc
                logger.warning("API error %s on GET %s: %s", status, full_url, exc.response.text)
                raise ApiClientError from exc
            except (httpx.RemoteProtocolError, httpx.ConnectError, httpx.ReadTimeout) as exc:
                last_exc = exc
                error_type = type(exc).__name__
                if attempt < max_retries - 1:
                    delay = 0.5 * (2 ** attempt)  # Экспоненциальная задержка: 0.5s, 1s, 2s
                    logger.warning(
                        "HTTP client error on GET %s: %s (%s), retrying in %.1fs (attempt %d/%d)",
                        full_url, exc, error_type, delay, attempt + 1, max_retries
                    )
                    await asyncio.sleep(delay)
                else:
                    logger.error(
                        "HTTP client error on GET %s: %s (%s) - max retries reached. "
                        "Server may be overloaded or network unstable.",
                        full_url, exc, error_type
                    )
            except httpx.HTTPError as exc:
                error_type = type(exc).__name__
                logger.warning("HTTP client error on GET %s: %s (%s)", full_url, exc, error_type)
                raise ApiClientError from exc
        
        # Если все попытки исчерпаны, выбрасываем последнюю ошибку
        raise ApiClientError(f"Failed to get {full_url} after {max_retries} attempts") from last_exc

    async def create_user(
        self,
        username: str,
        expire_at: str,
        telegram_id: int | None = None,
        traffic_limit_bytes: int | None = None,
        hwid_device_limit: int | None = None,
        description: str | None = None,
        external_squad_uuid: str | None = None,
        active_internal_squads: list[str] | None = None,
        traffic_limit_strategy: str = "MONTH",
    ) -> dict:
        payload: dict[str, object] = {"username": username, "expireAt": expire_at}
        if telegram_id is not None:
            payload["telegramId"] = telegram_id
        if traffic_limit_bytes is not None:
            payload["trafficLimitBytes"] = traffic_limit_bytes
        if traffic_limit_strategy:
            payload["trafficLimitStrategy"] = traffic_limit_strategy
        if hwid_device_limit is not None:
            payload["hwidDeviceLimit"] = hwid_device_limit
        if description:
            payload["description"] = description
        if external_squad_uuid:
            payload["externalSquadUuid"] = external_squad_uuid
        if active_internal_squads:
            payload["activeInternalSquads"] = active_internal_squads
        
        # Логируем payload для отладки
        logger.info("🔵 API: Creating user with payload: %s", payload)
        
        return await self._post("/api/users", json=payload)

    # --- System ---
    async def get_health(self) -> dict:
        return await self._get("/api/system/health")

    async def get_stats(self) -> dict:
        return await self._get("/api/system/stats")

    async def get_bandwidth_stats(self) -> dict:
        return await self._get("/api/system/stats/bandwidth")

    # --- Nodes ---
    async def get_nodes(self) -> dict:
        return await self._get("/api/nodes")

    async def get_node(self, node_uuid: str) -> dict:
        return await self._get(f"/api/nodes/{node_uuid}")

    async def create_node(
        self,
        name: str,
        address: str,
        config_profile_uuid: str,
        active_inbounds: list[str],
        port: int | None = None,
        country_code: str | None = None,
        provider_uuid: str | None = None,
        is_traffic_tracking_active: bool = False,
        traffic_limit_bytes: int | None = None,
        notify_percent: int | None = None,
        traffic_reset_day: int | None = None,
        consumption_multiplier: float | None = None,
        tags: list[str] | None = None,
    ) -> dict:
        """Создание новой ноды."""
        payload: dict[str, object] = {
            "name": name,
            "address": address,
            "configProfile": {
                "activeConfigProfileUuid": config_profile_uuid,
                "activeInbounds": active_inbounds,
            },
        }
        if port is not None:
            payload["port"] = port
        if country_code:
            payload["countryCode"] = country_code
        if provider_uuid:
            payload["providerUuid"] = provider_uuid
        if is_traffic_tracking_active:
            payload["isTrafficTrackingActive"] = is_traffic_tracking_active
        if traffic_limit_bytes is not None:
            payload["trafficLimitBytes"] = traffic_limit_bytes
        if notify_percent is not None:
            payload["notifyPercent"] = notify_percent
        if traffic_reset_day is not None:
            payload["trafficResetDay"] = traffic_reset_day
        if consumption_multiplier is not None:
            payload["consumptionMultiplier"] = consumption_multiplier
        if tags:
            payload["tags"] = tags
        return await self._post("/api/nodes", json=payload)

    async def enable_node(self, node_uuid: str) -> dict:
        return await self._post(f"/api/nodes/{node_uuid}/actions/enable")

    async def disable_node(self, node_uuid: str) -> dict:
        return await self._post(f"/api/nodes/{node_uuid}/actions/disable")

    async def restart_node(self, node_uuid: str) -> dict:
        return await self._post(f"/api/nodes/{node_uuid}/actions/restart")

    async def reset_node_traffic(self, node_uuid: str) -> dict:
        return await self._post(f"/api/nodes/{node_uuid}/actions/reset-traffic")

    async def update_node(
        self,
        node_uuid: str,
        name: str | None = None,
        address: str | None = None,
        port: int | None = None,
        country_code: str | None = None,
        provider_uuid: str | None = None,
        config_profile_uuid: str | None = None,
        active_inbounds: list[str] | None = None,
        is_traffic_tracking_active: bool | None = None,
        traffic_limit_bytes: int | None = None,
        notify_percent: int | None = None,
        traffic_reset_day: int | None = None,
        consumption_multiplier: float | None = None,
        tags: list[str] | None = None,
    ) -> dict:
        """Обновление ноды."""
        payload: dict[str, object] = {"uuid": node_uuid}
        if name is not None:
            payload["name"] = name
        if address is not None:
            payload["address"] = address
        if port is not None:
            payload["port"] = port
        if country_code is not None:
            payload["countryCode"] = country_code
        if provider_uuid is not None:
            payload["providerUuid"] = provider_uuid
        if config_profile_uuid is not None and active_inbounds is not None:
            payload["configProfile"] = {
                "activeConfigProfileUuid": config_profile_uuid,
                "activeInbounds": active_inbounds,
            }
        if is_traffic_tracking_active is not None:
            payload["isTrafficTrackingActive"] = is_traffic_tracking_active
        if traffic_limit_bytes is not None:
            payload["trafficLimitBytes"] = traffic_limit_bytes
        if notify_percent is not None:
            payload["notifyPercent"] = notify_percent
        if traffic_reset_day is not None:
            payload["trafficResetDay"] = traffic_reset_day
        if consumption_multiplier is not None:
            payload["consumptionMultiplier"] = consumption_multiplier
        if tags is not None:
            payload["tags"] = tags
        return await self._patch("/api/nodes", json=payload)

    async def delete_node(self, node_uuid: str) -> dict:
        """Удаление ноды."""
        try:
            response = await self._client.delete(f"/api/nodes/{node_uuid}")
            response.raise_for_status()
            return response.json()
        except HTTPStatusError as exc:
            status = exc.response.status_code
            if status in (401, 403):
                raise UnauthorizedError from exc
            if status == 404:
                raise NotFoundError from exc
            logger.warning("API error %s on DELETE /api/nodes/%s: %s", status, node_uuid, exc.response.text)
            raise ApiClientError from exc
        except httpx.HTTPError as exc:
            error_type = type(exc).__name__
            logger.warning("HTTP client error on DELETE /api/nodes/%s: %s (%s)", node_uuid, exc, error_type)
            raise ApiClientError from exc

    async def get_nodes_realtime_usage(self) -> dict:
        return await self._get("/api/bandwidth-stats/nodes/realtime")

    async def get_nodes_usage_range(self, start: str, end: str, top_nodes_limit: int = 10) -> dict:
        return await self._get(f"/api/bandwidth-stats/nodes?start={start}&end={end}&topNodesLimit={top_nodes_limit}")

    # --- Hosts ---
    async def get_hosts(self) -> dict:
        return await self._get("/api/hosts")

    async def get_host(self, host_uuid: str) -> dict:
        return await self._get(f"/api/hosts/{host_uuid}")

    async def enable_hosts(self, host_uuids: list[str]) -> dict:
        return await self._post("/api/hosts/bulk/enable", json={"uuids": host_uuids})

    async def disable_hosts(self, host_uuids: list[str]) -> dict:
        return await self._post("/api/hosts/bulk/disable", json={"uuids": host_uuids})

    async def create_host(
        self,
        remark: str,
        address: str,
        port: int,
        config_profile_uuid: str,
        config_profile_inbound_uuid: str,
        tag: str | None = None,
    ) -> dict:
        """Создание нового хоста."""
        payload: dict[str, object] = {
            "remark": remark,
            "address": address,
            "port": port,
            "inbound": {
                "configProfileUuid": config_profile_uuid,
                "configProfileInboundUuid": config_profile_inbound_uuid,
            },
        }
        if tag:
            payload["tag"] = tag
        return await self._post("/api/hosts", json=payload)

    async def update_host(
        self,
        host_uuid: str,
        remark: str | None = None,
        address: str | None = None,
        port: int | None = None,
        tag: str | None = None,
        inbound: dict | None = None,
    ) -> dict:
        """Обновление хоста."""
        payload: dict[str, object] = {"uuid": host_uuid}
        if remark is not None:
            payload["remark"] = remark
        if address is not None:
            payload["address"] = address
        if port is not None:
            payload["port"] = port
        if tag is not None:
            payload["tag"] = tag
        if inbound is not None:
            payload["inbound"] = inbound
        return await self._patch("/api/hosts", json=payload)

    # --- Subscriptions ---
    async def get_subscription_info(self, short_uuid: str) -> dict:
        return await self._get(f"/api/sub/{short_uuid}/info")

    async def encrypt_happ_crypto_link(self, link_to_encrypt: str) -> dict:
        """Шифрует ссылку подписки для Happ."""
        return await self._post("/api/system/tools/happ/encrypt", json={"linkToEncrypt": link_to_encrypt})

    # --- User Statistics ---
    async def get_user_subscription_request_history(self, user_uuid: str) -> dict:
        """Получает историю запросов подписки пользователя (последние 24 записи)."""
        return await self._get(f"/api/users/{user_uuid}/subscription-request-history")

    async def get_user_traffic_stats(self, user_uuid: str, start: str, end: str, top_nodes_limit: int = 10) -> dict:
        """Получает статистику трафика пользователя по нодам за период."""
        return await self._get(f"/api/bandwidth-stats/users/{user_uuid}?start={start}&end={end}&topNodesLimit={top_nodes_limit}")

    async def get_user_traffic_stats_legacy(self, user_uuid: str, start: str, end: str) -> dict:
        """Получает статистику трафика пользователя (legacy формат)."""
        return await self._get(f"/api/bandwidth-stats/users/{user_uuid}/legacy?start={start}&end={end}")

    async def get_user_accessible_nodes(self, user_uuid: str) -> dict:
        """Получает список доступных нод для пользователя."""
        return await self._get(f"/api/users/{user_uuid}/accessible-nodes")

    async def get_node_users_usage(self, node_uuid: str, start: str, end: str, top_users_limit: int = 10) -> dict:
        """Получает статистику использования ноды пользователями."""
        return await self._get(f"/api/bandwidth-stats/nodes/{node_uuid}/users?start={start}&end={end}&topUsersLimit={top_users_limit}")

    async def get_hwid_devices_stats(self) -> dict:
        """Получает статистику по устройствам (HWID)."""
        return await self._get("/api/hwid/devices/stats")

    async def get_all_hwid_devices(self, start: int = 0, size: int = 100) -> dict:
        """Получает все HWID устройства всех пользователей."""
        return await self._get(f"/api/hwid/devices?start={start}&size={size}")

    async def get_user_hwid_devices(self, user_uuid: str) -> dict:
        """Получает HWID устройства конкретного пользователя."""
        return await self._get(f"/api/hwid/devices/{user_uuid}")

    async def create_user_hwid_device(self, user_uuid: str, hwid: str) -> dict:
        """Создает HWID устройство для пользователя."""
        return await self._post("/api/hwid/devices", json={"userUuid": user_uuid, "hwid": hwid})

    async def delete_user_hwid_device(self, user_uuid: str, hwid: str) -> dict:
        """Удаляет конкретное HWID устройство пользователя."""
        return await self._post("/api/hwid/devices/delete", json={"userUuid": user_uuid, "hwid": hwid})

    async def delete_all_user_hwid_devices(self, user_uuid: str) -> dict:
        """Удаляет все HWID устройства пользователя."""
        return await self._post("/api/hwid/devices/delete-all", json={"userUuid": user_uuid})

    async def get_top_users_by_hwid_devices(self, limit: int = 10) -> dict:
        """Получает топ пользователей по количеству HWID устройств."""
        return await self._get(f"/api/hwid/devices/top-users?limit={limit}")

    # --- API Tokens ---
    async def get_tokens(self) -> dict:
        return await self._get("/api/tokens")

    async def create_token(self, token_name: str) -> dict:
        return await self._post("/api/tokens", json={"tokenName": token_name})

    async def delete_token(self, token_uuid: str) -> dict:
        try:
            response = await self._client.delete(f"/api/tokens/{token_uuid}")
            response.raise_for_status()
            return response.json()
        except HTTPStatusError as exc:
            status = exc.response.status_code
            if status in (401, 403):
                raise UnauthorizedError from exc
            if status == 404:
                raise NotFoundError from exc
            logger.warning("API error %s on DELETE %s: %s", status, response.url, exc.response.text)
            raise ApiClientError from exc
        except httpx.HTTPError as exc:
            error_type = type(exc).__name__
            logger.warning("HTTP client error on DELETE /api/tokens/%s: %s (%s)", token_uuid, exc, error_type)
            raise ApiClientError from exc

    # --- Subscription templates ---
    async def get_templates(self) -> dict:
        return await self._get("/api/subscription-templates")

    async def get_template(self, template_uuid: str) -> dict:
        return await self._get(f"/api/subscription-templates/{template_uuid}")

    async def delete_template(self, template_uuid: str) -> dict:
        try:
            response = await self._client.delete(f"/api/subscription-templates/{template_uuid}")
            response.raise_for_status()
            return response.json()
        except HTTPStatusError as exc:
            status = exc.response.status_code
            if status == 401:
                raise UnauthorizedError from exc
            if status == 404:
                raise NotFoundError from exc
            logger.warning("API error %s on DELETE %s: %s", status, response.url, exc.response.text)
            raise ApiClientError from exc
        except httpx.HTTPError as exc:
            error_type = type(exc).__name__
            logger.warning("HTTP client error on DELETE /api/subscription-templates/%s: %s (%s)", template_uuid, exc, error_type)
            raise ApiClientError from exc
    async def create_template(self, name: str, template_type: str) -> dict:
        return await self._post(
            "/api/subscription-templates", json={"name": name, "templateType": template_type}
        )

    async def update_template(
        self, template_uuid: str, name: str | None = None, template_json: dict | None = None
    ) -> dict:
        payload: dict[str, object] = {"uuid": template_uuid}
        if name:
            payload["name"] = name
        if template_json is not None:
            payload["templateJson"] = template_json
        return await self._patch("/api/subscription-templates", json=payload)

    async def reorder_templates(self, uuids_in_order: list[str]) -> dict:
        items = [{"uuid": uuid, "viewPosition": idx + 1} for idx, uuid in enumerate(uuids_in_order)]
        return await self._post("/api/subscription-templates/actions/reorder", json={"items": items})

    # --- Snippets ---
    async def get_snippets(self) -> dict:
        return await self._get("/api/snippets")

    async def create_snippet(self, name: str, snippet: list[dict] | dict) -> dict:
        return await self._post("/api/snippets", json={"name": name, "snippet": snippet})

    async def update_snippet(self, name: str, snippet: list[dict] | dict) -> dict:
        return await self._patch("/api/snippets", json={"name": name, "snippet": snippet})

    async def delete_snippet(self, name: str) -> dict:
        try:
            response = await self._client.delete("/api/snippets", json={"name": name})
            response.raise_for_status()
            return response.json()
        except HTTPStatusError as exc:
            status = exc.response.status_code
            if status == 401:
                raise UnauthorizedError from exc
            if status == 404:
                raise NotFoundError from exc
            logger.warning("API error %s on DELETE /api/snippets: %s", status, exc.response.text)
            raise ApiClientError from exc
        except httpx.HTTPError as exc:
            error_type = type(exc).__name__
            logger.warning("HTTP client error on DELETE /api/snippets: %s (%s)", exc, error_type)
            raise ApiClientError from exc

    # --- Config profiles ---
    async def get_config_profiles(self) -> dict:
        return await self._get("/api/config-profiles")

    async def get_config_profile_computed(self, profile_uuid: str) -> dict:
        return await self._get(f"/api/config-profiles/{profile_uuid}/computed-config")

    # --- Infra billing ---
    async def get_infra_billing_history(self) -> dict:
        return await self._get("/api/infra-billing/history")

    async def get_infra_providers(self) -> dict:
        return await self._get("/api/infra-billing/providers")

    async def get_infra_provider(self, provider_uuid: str) -> dict:
        return await self._get(f"/api/infra-billing/providers/{provider_uuid}")

    async def create_infra_provider(
        self, name: str, favicon_link: str | None = None, login_url: str | None = None
    ) -> dict:
        payload: dict[str, object] = {"name": name}
        if favicon_link:
            payload["faviconLink"] = favicon_link
        if login_url:
            payload["loginUrl"] = login_url
        return await self._post("/api/infra-billing/providers", json=payload)

    async def update_infra_provider(
        self,
        provider_uuid: str,
        name: str | None = None,
        favicon_link: str | None = None,
        login_url: str | None = None,
    ) -> dict:
        payload: dict[str, object] = {"uuid": provider_uuid}
        if name:
            payload["name"] = name
        if favicon_link is not None:
            payload["faviconLink"] = favicon_link
        if login_url is not None:
            payload["loginUrl"] = login_url
        return await self._patch("/api/infra-billing/providers", json=payload)

    async def delete_infra_provider(self, provider_uuid: str) -> dict:
        try:
            response = await self._client.delete(f"/api/infra-billing/providers/{provider_uuid}")
            response.raise_for_status()
            return response.json()
        except HTTPStatusError as exc:
            status = exc.response.status_code
            if status == 401:
                raise UnauthorizedError from exc
            if status == 404:
                raise NotFoundError from exc
            logger.warning("API error %s on DELETE /api/infra-billing/providers/%s: %s", status, provider_uuid, exc.response.text)
            raise ApiClientError from exc
        except httpx.HTTPError as exc:
            error_type = type(exc).__name__
            logger.warning("HTTP client error on DELETE /api/infra-billing/providers/%s: %s (%s)", provider_uuid, exc, error_type)
            raise ApiClientError from exc

    async def create_infra_billing_record(self, provider_uuid: str, amount: float, billed_at: str) -> dict:
        return await self._post(
            "/api/infra-billing/history", json={"providerUuid": provider_uuid, "amount": amount, "billedAt": billed_at}
        )

    async def delete_infra_billing_record(self, record_uuid: str) -> dict:
        try:
            response = await self._client.delete(f"/api/infra-billing/history/{record_uuid}")
            response.raise_for_status()
            return response.json()
        except HTTPStatusError as exc:
            status = exc.response.status_code
            if status == 401:
                raise UnauthorizedError from exc
            if status == 404:
                raise NotFoundError from exc
            logger.warning(
                "API error %s on DELETE /api/infra-billing/history/%s: %s", status, record_uuid, exc.response.text
            )
            raise ApiClientError from exc
        except httpx.HTTPError as exc:
            error_type = type(exc).__name__
            logger.warning("HTTP client error on DELETE /api/infra-billing/history/%s: %s (%s)", record_uuid, exc, error_type)
            raise ApiClientError from exc

    async def create_infra_billing_node(
        self, provider_uuid: str, node_uuid: str, next_billing_at: str | None = None
    ) -> dict:
        payload: dict[str, object] = {"providerUuid": provider_uuid, "nodeUuid": node_uuid}
        if next_billing_at:
            payload["nextBillingAt"] = next_billing_at
        return await self._post("/api/infra-billing/nodes", json=payload)

    async def update_infra_billing_nodes(self, uuids: list[str], next_billing_at: str) -> dict:
        return await self._patch("/api/infra-billing/nodes", json={"uuids": uuids, "nextBillingAt": next_billing_at})

    async def delete_infra_billing_node(self, record_uuid: str) -> dict:
        try:
            response = await self._client.delete(f"/api/infra-billing/nodes/{record_uuid}")
            response.raise_for_status()
            return response.json()
        except HTTPStatusError as exc:
            status = exc.response.status_code
            if status == 401:
                raise UnauthorizedError from exc
            if status == 404:
                raise NotFoundError from exc
            logger.warning(
                "API error %s on DELETE /api/infra-billing/nodes/%s: %s", status, record_uuid, exc.response.text
            )
            raise ApiClientError from exc
        except httpx.HTTPError as exc:
            error_type = type(exc).__name__
            logger.warning("HTTP client error on DELETE /api/infra-billing/nodes/%s: %s (%s)", record_uuid, exc, error_type)
            raise ApiClientError from exc

    # --- Users bulk ---
    async def bulk_reset_traffic_all_users(self) -> dict:
        return await self._post("/api/users/bulk/all/reset-traffic")

    async def bulk_delete_users_by_status(self, status: str) -> dict:
        return await self._post("/api/users/bulk/delete-by-status", json={"status": status})

    async def bulk_delete_users(self, uuids: list[str]) -> dict:
        return await self._post("/api/users/bulk/delete", json={"uuids": uuids})

    async def bulk_revoke_subscriptions(self, uuids: list[str]) -> dict:
        return await self._post("/api/users/bulk/revoke-subscription", json={"uuids": uuids})

    async def bulk_reset_traffic_users(self, uuids: list[str]) -> dict:
        return await self._post("/api/users/bulk/reset-traffic", json={"uuids": uuids})

    async def bulk_extend_users(self, uuids: list[str], days: int) -> dict:
        return await self._post("/api/users/bulk/extend-expiration-date", json={"uuids": uuids, "extendDays": days})

    async def bulk_extend_all_users(self, days: int) -> dict:
        return await self._post("/api/users/bulk/all/extend-expiration-date", json={"extendDays": days})

    async def bulk_update_users_status(self, uuids: list[str], status: str) -> dict:
        return await self._post("/api/users/bulk/update", json={"uuids": uuids, "fields": {"status": status}})

    # --- Infra billing nodes ---
    async def get_infra_billing_nodes(self) -> dict:
        return await self._get("/api/infra-billing/nodes")

    # --- Hosts bulk ---
    async def bulk_enable_hosts(self, uuids: list[str]) -> dict:
        return await self._post("/api/hosts/bulk/enable", json={"uuids": uuids})

    async def bulk_disable_hosts(self, uuids: list[str]) -> dict:
        return await self._post("/api/hosts/bulk/disable", json={"uuids": uuids})

    async def bulk_delete_hosts(self, uuids: list[str]) -> dict:
        return await self._post("/api/hosts/bulk/delete", json={"uuids": uuids})

    # --- Nodes bulk ---
    async def bulk_nodes_profile_modification(
        self, node_uuids: list[str], profile_uuid: str, inbound_uuids: list[str]
    ) -> dict:
        return await self._post(
            "/api/nodes/bulk-actions/profile-modification",
            json={
                "uuids": node_uuids,
                "configProfile": {"activeConfigProfileUuid": profile_uuid, "activeInbounds": inbound_uuids},
            },
        )

    async def close(self) -> None:
        await self._client.aclose()


# Single shared instance
api_client = RemnawaveApiClient()
