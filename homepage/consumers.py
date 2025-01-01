import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.core.cache import cache
from asgiref.sync import sync_to_async
import logging

logger = logging.getLogger(__name__)

class ChatConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        """WebSocket接続時の処理"""
        self.room_name = self.scope['url_route']['kwargs']['room_name']
        self.room_group_name = f'chat_{self.room_name}'

        # ルームグループに参加
        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )

        # 接続を受け入れる
        await self.accept()

        # Redisから過去のメッセージを取得
        messages = await sync_to_async(cache.get)(f'chat_history_{self.room_name}', [])
        if messages:
            await self.send(text_data=json.dumps({
                'type': 'history',
                'messages': messages
            }))

    async def disconnect(self, close_code):
        """WebSocket切断時の処理"""
        # ルームグループから離脱
        await self.channel_layer.group_discard(
            self.room_group_name,
            self.channel_name
        )

    async def receive(self, text_data):
        """WebSocketでメッセージを受信したときの処理"""
        text_data_json = json.loads(text_data)
        message = text_data_json['message']

        # メッセージをRedisに保存
        messages = await sync_to_async(cache.get)(f'chat_history_{self.room_name}', [])
        messages.append(message)
        await sync_to_async(cache.set)(
            f'chat_history_{self.room_name}',
            messages[-50:],  # 最新50件のみ保持
            timeout=86400  # 24時間保持
        )

        # ルームグループにメッセージをブロードキャスト
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'chat_message',
                'message': message
            }
        )

    async def chat_message(self, event):
        """チャットメッセージを送信する"""
        message = event['message']

        # WebSocketにメッセージを送信
        await self.send(text_data=json.dumps({
            'type': 'message',
            'message': message
        }))
