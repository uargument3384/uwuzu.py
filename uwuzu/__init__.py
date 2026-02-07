import requests
import json
import base64
import time
from typing import Optional, List, Dict, Union, Any, Generator, Callable

class UwuzuError(Exception):
    pass

class UwuzuObject:
    def __init__(self, client, data: Dict):
        self._client = client
        self._data = data
        for key, value in data.items():
            if not hasattr(self, key):
                setattr(self, key, value)

    def __repr__(self):
        return f"<{self.__class__.__name__} {self._data}>"

    def get(self, key, default=None):
        return self._data.get(key, default)

class User(UwuzuObject):
    @property
    def id(self):
        return self._data.get('userid')

    @property
    def name(self):
        return self._data.get('username')

    def follow(self):
        return self._client.follow(self.id)

    def unfollow(self):
        return self._client.unfollow(self.id)
    
    def get_details(self):
        return self._client.get_user(self.id)

class Post(UwuzuObject):
    @property
    def id(self):
        return self._data.get('uniqid')

    @property
    def author(self):
        return User(self._client, self._data.get('account', {}))

    @property
    def text_content(self):
        return self._data.get('text', '')

    def reply(self, text: str, nsfw: bool = False, image_paths: Optional[List[str]] = None):
        return self._client.create_post(text, replyid=self.id, nsfw=nsfw, image_paths=image_paths)

    def reuse(self):
        return self._client.create_post("", reuseid=self.id)

    def favorite(self):
        return self._client.favorite_change(self.id)

    def get_favorites_list(self):
        return self._client.favorite_get(self.id)

    def delete(self):
        return self._client.delete_post(self.id)

    def get_replies(self, limit: int = None):
        return self._client.get_replies(self.id, limit=limit)

class Notification(UwuzuObject):
    @property
    def from_user(self):
        return User(self._client, self._data.get('from', {}))

class Uwuzu:
    def __init__(self, domain: str, token: str):
        self.base_url = f"https://{domain}/api"
        self.token = token
        self.session = requests.Session()
        self.session.headers.update({
            'Content-Type': 'application/json',
            'User-Agent': 'UwuzuPythonClient/Complete'
        })

    @staticmethod
    def get_access_token(domain: str, session_id: str) -> Dict:
        url = f"https://{domain}/api/token/get"
        try:
            response = requests.post(url, json={"session": session_id})
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            raise UwuzuError(f"Failed to get token: {e}")

    def _encode_image(self, file_path: str) -> str:
        with open(file_path, "rb") as image_file:
            return base64.b64encode(image_file.read()).decode('utf-8')

    def _request(self, endpoint: str, method: str = "POST", params: Optional[Dict] = None, data: Optional[Dict] = None) -> Union[Dict, List, Any]:
        url = f"{self.base_url}{endpoint}"
        try:
            if method == "GET":
                if params is None: params = {}
                params['token'] = self.token
                response = self.session.get(url, params=params)
            else:
                if data is None: data = {}
                data['token'] = self.token
                response = self.session.post(url, json=data)

            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            raise UwuzuError(f"API Request failed: {e}")
        except json.JSONDecodeError:
            raise UwuzuError(f"Failed to decode JSON response from {url}")

    def _wrap_list(self, data: List, cls) -> List:
        if not isinstance(data, list): return []
        return [cls(self, item) for item in data]

    def get_server_info(self) -> Dict:
        return self._request("/serverinfo-api", method="GET")

    def get_me(self) -> User:
        data = self._request("/me/", method="GET")
        return User(self, data)

    def get_notifications(self, limit: int = None, page: int = None) -> List[Notification]:
        params = {}
        if limit: params['limit'] = limit
        if page: params['page'] = page
        data = self._request("/me/notification/", method="GET", params=params)
        
        notif_list = []
        if isinstance(data, dict):
            for k, v in data.items():
                if k.isdigit() and isinstance(v, dict):
                    notif_list.append(v)
        return self._wrap_list(notif_list, Notification)

    def read_notifications(self) -> Dict:
        return self._request("/me/notification/read", method="POST")

    def update_profile(self, username: str = None, profile: str = None, icon_path: str = None, header_path: str = None) -> Dict:
        payload = {}
        if username: payload['username'] = username
        if profile: payload['profile'] = profile
        if icon_path: payload['icon'] = self._encode_image(icon_path)
        if header_path: payload['header'] = self._encode_image(header_path)
        return self._request("/me/settings/", method="POST", data=payload)

    def get_user(self, userid: str) -> User:
        data = self._request("/users/", method="GET", params={"userid": userid})
        return User(self, data)

    def follow(self, userid: str) -> Dict:
        return self._request("/users/follow", method="POST", data={"userid": userid})

    def unfollow(self, userid: str) -> Dict:
        return self._request("/users/unfollow", method="POST", data={"userid": userid})

    def get_timeline(self, limit: int = 25, page: int = None) -> List[Post]:
        params = {'limit': limit}
        if page: params['page'] = page
        data = self._request("/ueuse/", method="GET", params=params)
        return self._wrap_list(data, Post)

    def get_post(self, uniqid: str) -> Post:
        data = self._request("/ueuse/get", method="GET", params={"uniqid": uniqid})
        if isinstance(data, list) and data:
            return Post(self, data[0])
        return None

    def get_replies(self, uniqid: str, limit: int = None, page: int = None) -> List[Post]:
        params = {'uniqid': uniqid}
        if limit: params['limit'] = limit
        if page: params['page'] = page
        data = self._request("/ueuse/replies", method="GET", params=params)
        return self._wrap_list(data, Post)

    def get_mentions(self, limit: int = None, page: int = None) -> List[Post]:
        params = {}
        if limit: params['limit'] = limit
        if page: params['page'] = page
        data = self._request("/ueuse/mentions", method="GET", params=params)
        return self._wrap_list(data, Post)

    def search(self, keyword: str, limit: int = None, page: int = None) -> List[Post]:
        params = {'keyword': keyword}
        if limit: params['limit'] = limit
        if page: params['page'] = page
        data = self._request("/ueuse/search", method="GET", params=params)
        return self._wrap_list(data, Post)

    def create_post(self, text: str, replyid: str = None, reuseid: str = None, nsfw: bool = False, image_paths: List[str] = None) -> Dict:
        payload = {"text": text, "nsfw": nsfw}
        if replyid: payload["replyid"] = replyid
        if reuseid: payload["reuseid"] = reuseid
        if image_paths:
            for i, path in enumerate(image_paths[:4]):
                payload[f"image{i+1}"] = self._encode_image(path)
        return self._request("/ueuse/create", method="POST", data=payload)

    def delete_post(self, uniqid: str) -> Dict:
        return self._request("/ueuse/delete", method="POST", data={"uniqid": uniqid})
    
    def get_bookmarks(self, limit: int = None, page: int = None) -> List[Post]:
        params = {}
        if limit: params['limit'] = limit
        if page: params['page'] = page
        data = self._request("/ueuse/bookmark/", method="GET", params=params)
        return self._wrap_list(data, Post)

    def favorite_change(self, uniqid: str) -> Dict:
        return self._request("/farovite/change", method="POST", data={"uniqid": uniqid})

    def favorite_get(self, uniqid: str) -> Dict:
        return self._request("/farovite/get", method="GET", params={"uniqid": uniqid})

    def admin_get_user(self, userid: str) -> User:
        data = self._request("/admin/users/", method="POST", data={"userid": userid})
        return User(self, data)

    def admin_sanction(self, userid: str, type: str, title: str = None, message: str = None, really: str = None) -> Dict:
        payload = {"userid": userid, "type": type}
        if title: payload["notification_title"] = title
        if message: payload["notification_message"] = message
        if really: payload["really"] = really
        return self._request("/admin/users/sanction", method="POST", data=payload)

    def admin_get_reports(self, limit: int = None, page: int = None) -> Dict:
        data = {}
        if limit: data["limit"] = limit
        if page: data["page"] = page
        return self._request("/admin/reports/", method="POST", data=data)

    def admin_resolve_report(self, reported_userid: str = None, uniqid: str = None) -> Dict:
        data = {}
        if reported_userid: data["reported_userid"] = reported_userid
        if uniqid: data["uniqid"] = uniqid
        return self._request("/admin/reports/resolve", method="POST", data=data)

    def iter_timeline(self, limit_per_request: int = 25, max_pages: int = 10) -> Generator[Post, None, None]:
        for page in range(1, max_pages + 1):
            posts = self.get_timeline(limit=limit_per_request, page=page)
            if not posts:
                break
            for post in posts:
                yield post
            time.sleep(0.5)

    def watch_timeline(self, interval: int = 60, callback: Callable[[Post], None] = None):
        seen_ids = set()
        first_run = True
        
        while True:
            try:
                posts = self.get_timeline(limit=10)
                if first_run:
                    seen_ids = {p.id for p in posts}
                    first_run = False
                else:
                    new_posts = [p for p in posts if p.id not in seen_ids]
                    for post in reversed(new_posts):
                        seen_ids.add(post.id)
                        if callback:
                            callback(post)
            except Exception as e:
                print(f"Watch Error: {e}")
            
            time.sleep(interval)
