import asyncio
import logging
import aiohttp

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT = 120  # seconds


class Agent:
	def __init__(self, timeout: int = DEFAULT_TIMEOUT):
		self._auth_token: str = ""
		self._url: str = ""
		self.model: str = "qwen3.5-plus"
		self.timeout = timeout

	def set_config(self, auth_token: str | None, url: str | None):
		"""Configure agent with API credentials."""
		if auth_token:
			self._auth_token = auth_token
		if url:
			self._url = url

	async def invoke(self, input: dict, timeout: int | None = None) -> str | None:
		"""Invoke the agent with timeout support."""
		actual_timeout = timeout or self.timeout
		try:
			async with asyncio.timeout(actual_timeout):
				return await self.request(
					chat_id=input.get("chat_id", "default"),
					message=input.get("tool_input", ""),
				)
		except asyncio.TimeoutError:
			logger.error("Agent request timeout after %d seconds", actual_timeout)
			raise

	async def request(self, chat_id: str, message: str, *, parent_id: str | None = None, system: str | None = None, timeout: int | None = None) -> str | None:
		"""Send request to Qwen API."""
		if not self._url or not self._auth_token:
			logger.warning("Agent not configured with URL or auth token")
			return None

		headers: dict = {
			"Authorization": f"Bearer {self._auth_token}"
		}

		req_json: dict = {
			"model": self.model,
			"message": message,
			"chat_id": chat_id
		}

		if system is not None:
			req_json["system"] = system
		if parent_id is not None:
			req_json["parent_id"] = parent_id

		actual_timeout = timeout or self.timeout
		try:
			async with aiohttp.ClientSession() as session:
				async with session.post(
					self._url + "/chat",
					json=req_json,
					headers=headers,
					timeout=aiohttp.ClientTimeout(total=actual_timeout)
				) as res:
					try:
						data = await res.json()
						return data.get("response") if isinstance(data, dict) else str(data)
					except aiohttp.ContentTypeError:
						text = await res.text()
						logger.error("Unexpected response from Qwen API: %s", text[:200])
						return text
		except asyncio.TimeoutError:
			logger.error("Timeout connecting to Qwen API after %d seconds", actual_timeout)
			raise
		except Exception as e:
			logger.exception("Error calling Qwen API: %s", e)
			return None


agent = Agent()
