"""
title: Publish daily check-in
author: Marvin
version: 0.2.1
description: Publishes the automation's final answer to the #daily-checkin webhook, then deletes the run's chat.
"""

import asyncio

import httpx
from pydantic import BaseModel


# Keep scheduled deletions alive until they finish.
_background_tasks = set()


class Filter:
    class Valves(BaseModel):
        webhook_url: str = ""
        marker: str = "[[daily-checkin]]"
        api_base_url: str = "http://open-webui:8080"
        delete_api_key: str = ""
        delete_chat: bool = True
        delete_delay_seconds: int = 90

    def __init__(self):
        self.valves = self.Valves()

    async def outlet(self, body: dict, __metadata__: dict = None) -> dict:
        messages = body.get("messages") or []

        # Only the latest user message should trigger publishing.
        user_index = next(
            (
                index
                for index in range(len(messages) - 1, -1, -1)
                if messages[index].get("role") == "user"
            ),
            None,
        )
        if user_index is None:
            return body

        marker = self.valves.marker.strip()
        user_content = messages[user_index].get("content", "")
        if (
            not marker
            or not isinstance(user_content, str)
            or marker not in user_content
        ):
            return body

        webhook_url = self.valves.webhook_url.strip()
        if not webhook_url:
            print("[checkin-publish] no webhook_url set", flush=True)
            return body

        # Do not accidentally select an assistant message from an older turn.
        answer = next(
            (
                message.get("content")
                for message in reversed(messages[user_index + 1 :])
                if message.get("role") == "assistant"
            ),
            None,
        )
        if not isinstance(answer, str) or not answer.strip():
            print("[checkin-publish] marker matched but no answer", flush=True)
            return body

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.post(
                    webhook_url,
                    json={"content": answer},
                )
                response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            print(
                f"[checkin-publish] post failed: HTTP {exc.response.status_code}",
                flush=True,
            )
        except Exception as exc:
            # Exception messages can contain the webhook URL.
            print(
                f"[checkin-publish] post failed: {type(exc).__name__}",
                flush=True,
            )
        else:
            print(
                f"[checkin-publish] published: HTTP {response.status_code}, "
                f"len={len(answer)}",
                flush=True,
            )
            self._schedule_delete(__metadata__)

        return body

    def _schedule_delete(self, metadata: dict) -> None:
        if not self.valves.delete_chat:
            return

        base = self.valves.api_base_url.strip().rstrip("/")
        key = self.valves.delete_api_key.strip()
        if not base or not key:
            print(
                "[checkin-delete] skipped: api_base_url or delete_api_key unset",
                flush=True,
            )
            return

        chat_id = (metadata or {}).get("chat_id")
        if not chat_id:
            print("[checkin-delete] skipped: no chat_id in __metadata__", flush=True)
            return

        delay = max(0, int(self.valves.delete_delay_seconds))
        task = asyncio.create_task(self._delete_later(base, key, chat_id, delay))
        _background_tasks.add(task)
        task.add_done_callback(_background_tasks.discard)

    async def _delete_later(
        self, base: str, key: str, chat_id: str, delay: int
    ) -> None:
        await asyncio.sleep(delay)

        url = f"{base}/api/v1/chats/{chat_id}"
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.delete(
                    url,
                    headers={"Authorization": f"Bearer {key}"},
                )
        except Exception as exc:
            print(
                f"[checkin-delete] failed: {type(exc).__name__}",
                flush=True,
            )
            return

        if response.status_code == 404:
            print(f"[checkin-delete] already gone: {chat_id}", flush=True)
        elif response.is_success:
            print(
                f"[checkin-delete] deleted: {chat_id} "
                f"(HTTP {response.status_code})",
                flush=True,
            )
        else:
            print(
                f"[checkin-delete] failed: HTTP {response.status_code}",
                flush=True,
            )
