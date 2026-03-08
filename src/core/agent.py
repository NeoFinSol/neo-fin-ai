import aiohttp


class Agent:
	def __init__(self):
		self._auth_token: str = ""
		self._url: str = ""
		self.model: str = "qwen3.5-plus"

	def set_config(self, auth_token: str, url: str):
		self._auth_token = auth_token
		self._url = url

	async def request(self, chat_id: str, message: str, *, parent_id: str | None = None, system: str | None = None):
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

		async with aiohttp.ClientSession() as session:
			async with session.post(self._url + "/chat", json=req_json, headers=headers) as res:
				try:
					return await res.json()
				except aiohttp.ContentTypeError:
					print(await res.text())
					return None


agent = Agent()
